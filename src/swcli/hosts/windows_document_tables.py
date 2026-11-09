"""Protected table defaults; uncalibrated public writes fail before any setter."""

import ctypes
from pathlib import Path
import sys
from typing import Any

from ..document_tables import TABLE_FIELDS, LINE_WEIGHTS, validate_table_options, validate_table_value
from ..document_table_profiles import PROFILES as _CALIBRATED_PROFILES
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context
from .windows_feature_inspection import _same

# Internal native calibration is not public acceptance. No environment bypass.


class DocumentTableConflict(RuntimeError):
    """The complete table defaults no longer match the caller's snapshot."""


class DocumentTableCalibrationRequired(RuntimeError):
    """The runtime or document/version lacks accepted public write evidence."""


def _native_windows_runtime():
    if sys.platform != "win32":
        return False
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        module = kernel.GetModuleHandleW
        module.argtypes = [ctypes.c_wchar_p]
        module.restype = ctypes.c_void_p
        address = kernel.GetProcAddress
        address.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        address.restype = ctypes.c_void_p
        ntdll = module("ntdll.dll")
        if type(ntdll) is not int or ntdll <= 0:
            return False
        known = address(ntdll, b"NtClose")
        if type(known) is not int or known <= 0:
            return False
        ctypes.set_last_error(0)
        wine = address(ntdll, b"wine_get_version")
        error = ctypes.get_last_error()
        return wine is None and type(error) is int and error == 127
    except Exception:
        # Only a functioning lookup with ERROR_PROC_NOT_FOUND proves absence.
        return False


def _read_constants(path):
    import pythoncom
    wanted = {spec["symbol"] for spec in TABLE_FIELDS.values()} | {"swDetailingNoOptionSpecified"}
    wanted |= {"swLW_" + name.upper() for name in LINE_WEIGHTS}
    library = pythoncom.LoadTypeLib(str(path))
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attributes.cVars):
            descriptor = info.GetVarDesc(offset)
            name = info.GetDocumentation(descriptor[0])[0]
            if name in wanted:
                if name in found or type(descriptor.value) is not int:
                    raise RuntimeError("invalid or duplicate table enum in official swconst")
                found[name] = descriptor.value
    if set(found) != wanted or found["swDetailingNoOptionSpecified"] != 0 or any(
            found["swLW_" + name.upper()] != code for name, code in LINE_WEIGHTS.items()):
        raise RuntimeError("official swconst lacks the expected table enum catalog")
    return found


def _constants(app):
    # Official GetExecutablePath returns the installation directory, without a
    # trailing slash. Do not guess IDs or load a caller-supplied type library.
    folder = _com_value(app, "GetExecutablePath")
    if type(folder) is not str or not folder:
        raise RuntimeError("native SOLIDWORKS installation path is unavailable")
    path = Path(folder) / "swconst.tlb"
    if not path.is_file():
        raise RuntimeError("official installed swconst.tlb is unavailable")
    return native_call("document-tables", "swconst.LoadTypeLib", lambda: _read_constants(path))


def _identity(document):
    values = (_com_value(document, "GetTitle"), _com_value(document, "GetPathName"))
    if any(type(value) is not str for value in values) or not values[0]:
        raise RuntimeError("native document identity is unreadable")
    return values


def _permissions(document):
    values = (_com_value(document, "IsOpenedReadOnly"), _com_value(document, "IsOpenedViewOnly"))
    if any(type(value) is not bool for value in values):
        raise RuntimeError("table document permissions are unreadable")
    return values


def _capture(app, document):
    foreground = _com_value(app, "ActiveDoc")
    peer = foreground if foreground is not None and not _same(app, foreground, document) else None
    extension = _com_value(document, "Extension")
    peer_extension = _com_value(peer, "Extension") if peer is not None else None
    if extension is None or (peer is not None and peer_extension is None):
        raise RuntimeError("table document extension identity is unreadable")
    return dict(state=_state(document), identity=_identity(document), extension=extension, foreground=foreground,
                foreground_state=_state(foreground) if foreground is not None else None,
                foreground_identity=_identity(foreground) if foreground is not None else None,
                foreground_extension=peer_extension, foreground_edit=_edit_context(peer) if peer is not None else None,
                foreground_permissions=_permissions(peer) if peer is not None else None, edit=_edit_context(document))


def _verify_identity_and_peer(app, document, snapshot):
    if (_identity(document) != snapshot["identity"]
            or not _same(app, _com_value(document, "Extension"), snapshot["extension"])):
        raise RuntimeError("table operation changed document identity")
    documents = _com_value(app, "GetDocuments")
    if not isinstance(documents, (list, tuple)) or not any(_same(app, document, item) for item in documents):
        raise RuntimeError("table document is no longer open")
    _verify_context(app, document, snapshot["edit"])
    foreground = snapshot["foreground"]
    if not _same(app, foreground, _com_value(app, "ActiveDoc")):
        raise RuntimeError("table operation changed the foreground document")
    if foreground is not None and not _same(app, foreground, document):
        identity = _identity(foreground)
        extension = _com_value(foreground, "Extension")
        _verify_context(app, foreground, snapshot["foreground_edit"])
        permissions = _permissions(foreground)
        if (_state(foreground) != snapshot["foreground_state"] or identity != snapshot["foreground_identity"]
                or not _same(app, extension, snapshot["foreground_extension"])
                or permissions != snapshot["foreground_permissions"]):
            raise RuntimeError("table operation changed the background document's foreground peer")
    if not _same(app, foreground, _com_value(app, "ActiveDoc")):
        raise RuntimeError("table operation changed the foreground document during verification")


def _verify(app, document, snapshot, *, state=None, writable=False):
    _verify_identity_and_peer(app, document, snapshot)
    _verify_metadata_state(app, document, snapshot["state"] if state is None else state,
                           snapshot["foreground"], changed=False)
    if writable:
        _require_writable(document)
    # Target state/permission reads may dispatch events that change the peer.
    _verify_identity_and_peer(app, document, snapshot)


def _verify_before_mutation(app, document, snapshot, *, state=None):
    _verify(app, document, snapshot, state=state, writable=True)
    if not _writable_context(app, snapshot["edit"]):
        raise ValueError("table default editing requires a normal drawing sheet or no active model sketch")
    _require_writable(document)
    _verify_identity_and_peer(app, document, snapshot)


def _read_options(document, constants):
    kind = _com_value(document, "GetType")
    extension = _com_value(document, "Extension")
    options = {}
    for field, spec in TABLE_FIELDS.items():
        if kind not in spec["types"]:
            options[field] = {"unavailable": "document_type"}
            continue
        method = "GetUserPreference" + spec["kind"]
        raw = native_call("document-tables", "IModelDocExtension." + method,
                          lambda spec=spec, method=method: getattr(extension, method)(
                              constants[spec["symbol"]], constants["swDetailingNoOptionSpecified"]))
        expected = bool if spec["kind"] == "Toggle" else int
        if type(raw) is not expected:
            raise RuntimeError("native table field is unreadable: " + field)
        value = raw if expected is bool else next((name for name, code in LINE_WEIGHTS.items() if code == raw), "other")
        options[field] = {"value": value, "native_value": raw}
    return options


def read_document_table_options_windows(*, app: Any, document: Any) -> dict:
    result = {"ok": False, "action": "document.table-options"}
    try:
        snapshot = _capture(app, document)
        constants = _constants(app)
        options = _read_options(document, constants)
        _verify(app, document, snapshot)
        result.update(ok=True, options=options)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def _edit_table_option(*, app, document, field, value, expected_options, calibration=False):
    result = {"ok": False, "action": "document.table-option-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        if not _native_windows_runtime():
            raise DocumentTableCalibrationRequired("table default writes require a confirmed native Windows runtime")
        validate_table_value(field, value)
        expected = validate_table_options(expected_options)
        _require_writable(document)
        snapshot = _capture(app, document)
        spec = TABLE_FIELDS[field]
        if snapshot["state"][0] not in spec["types"]:
            raise ValueError("this table default is unavailable for the selected document type")
        revision = _com_value(app, "RevisionNumber")
        native = value if spec["kind"] == "Toggle" else LINE_WEIGHTS[value]
        transition = (expected[field]["native_value"], native)
        if not calibration and transition not in _CALIBRATED_PROFILES.get((revision, snapshot["state"][0]), {}).get(field, ()):
            raise DocumentTableCalibrationRequired("table default writes await native public acceptance for this version/type")
        constants = _constants(app)
        before = _read_options(document, constants)
        result.update(field=field, before=before)
        # Includes every readable raw scalar and explicit unavailable entries.
        if before != expected:
            raise DocumentTableConflict("document table defaults no longer match expected_options")
        _verify(app, document, snapshot, writable=True)
        if type(before[field]["value"]) is type(value) and before[field]["value"] == value:
            result.update(ok=True, options=before, changed=False)
            return result
        method = "SetUserPreference" + spec["kind"]
        setter = getattr(snapshot["extension"], method)
        _verify_before_mutation(app, document, snapshot)
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-tables", "IModelDocExtension." + method,
                               lambda: setter(constants[spec["symbol"]], 0, native))
        if type(returned) is bool:
            result["native_returned"] = returned
        # Toggle documentation describes a state return; the baseline native
        # annotation calibration observed success booleans. Until this exact
        # field is proven, False remains a recorded, fail-closed outcome.
        if returned is not True:
            raise RuntimeError("native table setter did not return success")
        post_setter = _state(document)
        after = _read_options(document, constants)
        _verify(app, document, snapshot, state=post_setter, writable=True)
        if after[field] != {"value": value, "native_value": native}:
            raise RuntimeError("native table setter did not round-trip the requested value")
        if any(after[key] != before[key] for key in TABLE_FIELDS if key != field):
            raise RuntimeError("native table setter changed an unrequested field")
        # Check type/configuration/foreground before marking dirty at most once.
        if (post_setter[0], post_setter[3]) != (snapshot["state"][0], snapshot["state"][3]):
            raise RuntimeError("table setter changed document type or configuration")
        if not post_setter[2]:
            mark_dirty = document.SetSaveFlag
            _verify_before_mutation(app, document, snapshot, state=post_setter)
            native_call("document-metadata", "IModelDoc2.SetSaveFlag", mark_dirty)
        post_write = _state(document)
        if not post_write[2] or (post_write[0], post_write[3]) != (snapshot["state"][0], snapshot["state"][3]):
            raise RuntimeError("table write did not preserve context and mark the document for saving")
        final = _read_options(document, constants)
        if final != after:
            raise RuntimeError("table defaults changed while marking the document for saving")
        _verify(app, document, snapshot, state=post_write, writable=True)
        result.update(ok=True, options=after, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_table_option_windows(*, app: Any, document: Any, field: str, value: Any, expected_options: dict) -> dict:
    return _edit_table_option(app=app, document=document, field=field, value=value, expected_options=expected_options)
