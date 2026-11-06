"""Protected drawing defaults; never insert marks or alter existing views."""

import ctypes
from functools import lru_cache
import sys
from pathlib import Path

from ..document_detailing import DETAILING_FIELDS, validate_detailing_options
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_feature_inspection import _same
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context

# Exact revision proven by retained native save/reopen evidence:
# docs/evidence/detailing-internal-42260661085.json. Other revisions fail closed.
# Internal calibration scopes its own allowlist; no wire/environment override.
CALIBRATED_REVISIONS = frozenset({"33.5.0"})


@lru_cache(maxsize=8)
def _load_constants(path):
    import pythoncom
    library = pythoncom.LoadTypeLib(path)
    wanted = set(DETAILING_FIELDS.values()) | {"swDetailingNoOptionSpecified"}
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
                    raise RuntimeError("official detailing enum is ambiguous or unreadable")
                found[name] = descriptor.value
    if set(found) != wanted or found["swDetailingNoOptionSpecified"] != 0:
        raise RuntimeError("official type library lacks the required detailing enums")
    return found


def _constants(app):
    executable = _com_value(app, "GetExecutablePath")
    if type(executable) is not str or not executable:
        raise RuntimeError("SOLIDWORKS installation path is unavailable")
    directory = Path(executable)
    if directory.suffix.lower() == ".exe":
        directory = directory.parent
    path = directory / "swconst.tlb"
    if not path.is_file():
        raise RuntimeError("official swconst type library is unavailable beside SOLIDWORKS")
    return _load_constants(str(path.resolve()))


def _native_windows():
    if sys.platform != "win32":
        return False
    # A Wine Python reports win32 too. Unknown runtime discovery fails before
    # mutation; native Windows evidence must not silently enable Wine writes.
    return getattr(ctypes.WinDLL("ntdll"), "wine_get_version", None) is None


def _read_options(document, constants):
    extension = _com_value(document, "Extension")
    options = {}
    for field, symbol in DETAILING_FIELDS.items():
        value = native_call("document-detailing", "IModelDocExtension.GetUserPreferenceToggle",
                            lambda symbol=symbol: extension.GetUserPreferenceToggle(
                                constants[symbol], constants["swDetailingNoOptionSpecified"]))
        if type(value) is not bool:
            raise RuntimeError("native drawing detailing option is unreadable: " + field)
        options[field] = value
    return options


def _identity(document):
    value = (_com_value(document, "GetTitle"), _com_value(document, "GetPathName"))
    if any(type(item) is not str for item in value):
        raise RuntimeError("drawing identity is unreadable")
    return value


def _snapshot(app, document):
    state = _state(document)
    if state[0] != 3:
        raise ValueError("detailing defaults require a drawing document")
    foreground = _com_value(app, "ActiveDoc")
    return (state, foreground, _edit_context(document), _identity(document),
            None if foreground is None or _same(app, foreground, document) else _state(foreground))


def _verify(app, document, snapshot, *, changed=False):
    state, foreground, edit, identity, foreground_state = snapshot
    _verify_context(app, document, edit)
    if _identity(document) != identity:
        raise RuntimeError("drawing identity changed during detailing operation")
    if foreground_state is not None and _state(foreground) != foreground_state:
        raise RuntimeError("foreground document changed during background detailing operation")
    _verify_metadata_state(app, document, state, foreground, changed=changed)


def read_document_detailing_options_windows(*, app, document):
    result = {"ok": False, "action": "document.detailing-options"}
    try:
        snapshot = _snapshot(app, document)
        options = _read_options(document, _constants(app))
        _verify(app, document, snapshot)
        result.update(ok=True, options=options)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_detailing_option_windows(
    *, app, document, field, value, expected_options,
):
    result = {"ok": False, "action": "document.detailing-option-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        if field not in DETAILING_FIELDS or type(value) is not bool:
            raise ValueError("unsupported drawing detailing field or non-boolean value")
        validate_detailing_options(expected_options)
        _require_writable(document)
        snapshot = _snapshot(app, document)
        constants = _constants(app)
        before = _read_options(document, constants)
        result.update(field=field, before=before)
        if before != expected_options:
            raise ValueError("drawing detailing snapshot no longer matches expected_options")
        _verify(app, document, snapshot)
        if before[field] is value:
            result.update(ok=True, options=before, changed=False)
            return result
        if not _writable_context(app, snapshot[2]):
            raise ValueError("detailing editing requires a normal drawing sheet")
        if not _native_windows() or _com_value(app, "RevisionNumber") not in CALIBRATED_REVISIONS:
            raise ValueError("drawing detailing writes lack native calibration for this SOLIDWORKS revision")
        desired = {**before, field: value}
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-detailing", "IModelDocExtension.SetUserPreferenceToggle",
                               lambda: _com_value(document, "Extension").SetUserPreferenceToggle(
                                   constants[DETAILING_FIELDS[field]],
                                   constants["swDetailingNoOptionSpecified"], value))
        # The official return description is ambiguous for false. Retain it and
        # require calibrated success semantics; never retry a false/odd return.
        result["native_return"] = returned if type(returned) is bool else None
        if returned is not True:
            raise RuntimeError("native drawing detailing setter did not return calibrated success")
        post = _snapshot(app, document)
        after = _read_options(document, constants)
        _verify(app, document, post)
        if after != desired:
            raise RuntimeError("native drawing detailing setter changed an unrequested value or failed readback")
        _verify(app, document, snapshot, changed=True)
        final_state = _snapshot(app, document)
        final = _read_options(document, constants)
        if final != desired:
            raise RuntimeError("drawing detailing options changed while marking for saving")
        _verify(app, document, final_state)
        _verify(app, document, (final_state[0], *snapshot[1:]))
        result.update(ok=True, options=final, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
