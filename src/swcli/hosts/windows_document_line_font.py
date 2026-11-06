"""Drawing Line Font defaults restricted to independently calibrated conversions."""

from pathlib import Path
from ..document_line_font import (LINE_FONT_FIELDS, validate_edit, CALIBRATED_LINE_FONT_REVISION,
                                  CALIBRATED_LINE_FONT_TRANSITIONS)
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context
from .windows_feature_inspection import _same


class DocumentLineFontConflict(RuntimeError):
    pass


class DocumentLineFontUncalibrated(RuntimeError):
    pass


def _constants():
    # Read only the installed vendor type library, never guess numeric preference IDs.
    import pythoncom
    library = pythoncom.LoadTypeLib(str(Path(r"C:\Program Files\SOLIDWORKS\swconst.tlb")))
    wanted = set(LINE_FONT_FIELDS.values()) | {"swDetailingNoOptionSpecified"}
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attr = info.GetTypeAttr()
        if attr.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attr.cVars):
            var = info.GetVarDesc(offset)
            name = info.GetDocumentation(var[0])[0]
            if name in wanted:
                if name in found or type(var.value) is not int:
                    raise RuntimeError("ambiguous official line font enum")
                found[name] = var.value
    if set(found) != wanted:
        raise RuntimeError("installed official swconst lacks line font enums")
    return found


def _read(document, constants):
    extension = _com_value(document, "Extension")
    options = {}
    for field, preference in LINE_FONT_FIELDS.items():
        raw = native_call("document-line-font", "IModelDocExtension.GetUserPreferenceInteger",
                          lambda preference=preference: extension.GetUserPreferenceInteger(
                              constants[preference], constants["swDetailingNoOptionSpecified"]))
        if type(raw) is not int:
            raise RuntimeError("line font getter returned a non-integer")
        options[field] = raw
    return options


def _drawing(document):
    if _com_value(document, "GetType") != 3:
        raise ValueError("line font defaults currently support drawing documents only")


def _identity(document):
    identity = (_com_value(document, "GetTitle"), _com_value(document, "GetPathName"))
    if any(type(value) is not str for value in identity) or not identity[0]:
        raise RuntimeError("line font document identity is unreadable")
    return identity


def _access(document):
    access = (_com_value(document, "IsOpenedReadOnly"), _com_value(document, "IsOpenedViewOnly"))
    if any(type(value) is not bool for value in access):
        raise RuntimeError("line font document access is unreadable")
    return access


def _capture_guard(app, document, foreground):
    peer = None
    if foreground is not None and not _same(app, foreground, document):
        peer = dict(state=_state(foreground), identity=_identity(foreground),
                    access=_access(foreground), edit=_edit_context(foreground))
    return dict(identity=_identity(document), access=_access(document), peer=peer)


def _verify_guard(app, document, foreground, guard):
    if _identity(document) != guard["identity"] or _access(document) != guard["access"]:
        raise RuntimeError("line font operation changed target document identity or access")
    opened = _com_value(app, "GetDocuments")
    if (not isinstance(opened, (tuple, list))
            or not any(_same(app, document, item) for item in opened)):
        raise RuntimeError("line font target document is no longer open")
    if not _same(app, foreground, _com_value(app, "ActiveDoc")):
        raise RuntimeError("line font operation changed the foreground document")
    peer = guard["peer"]
    if peer is not None:
        if (not any(_same(app, foreground, item) for item in opened)
                or _state(foreground) != peer["state"]
                or _identity(foreground) != peer["identity"]
                or _access(foreground) != peer["access"]):
            raise RuntimeError("line font operation changed foreground document state, identity or access")
        _verify_context(app, foreground, peer["edit"])
        if _state(foreground) != peer["state"] or _identity(foreground) != peer["identity"]:
            raise RuntimeError("foreground document changed during line font verification")


def read_document_line_font_windows(*, app, document):
    result = {"ok": False, "action": "document.line-font"}
    try:
        _drawing(document)
        state, foreground, context = _state(document), _com_value(app, "ActiveDoc"), _edit_context(document)
        guard = _capture_guard(app, document, foreground)
        options = _read(document, _constants())
        _verify_context(app, document, context)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        _verify_guard(app, document, foreground, guard)
        result.update(ok=True, options=options)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_line_font_windows(*, app, document, field, value, expected_options,
                                   _internal_calibration=False):
    result = {"ok": False, "action": "document.line-font-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_edit(field, value, expected_options)
        _drawing(document)
        _require_writable(document)
        state, foreground, context = _state(document), _com_value(app, "ActiveDoc"), _edit_context(document)
        guard = _capture_guard(app, document, foreground)
        constants = _constants()
        before = _read(document, constants)
        result.update(field=field, before=before)
        if before != expected_options:
            raise DocumentLineFontConflict("complete line font snapshot no longer matches")
        _verify_context(app, document, context)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        _verify_guard(app, document, foreground, guard)
        if not _internal_calibration:
            try:
                revision = _com_value(app, "RevisionNumber")
            except Exception as exc:
                raise DocumentLineFontUncalibrated("host revision is unavailable") from exc
            if (revision != CALIBRATED_LINE_FONT_REVISION
                    or (before[field] != value and (before[field], value) != CALIBRATED_LINE_FONT_TRANSITIONS[field])):
                raise DocumentLineFontUncalibrated("line font revision or conversion lacks recorded native calibration")
            _verify_context(app, document, context)
            _verify_metadata_state(app, document, state, foreground, changed=False)
            _verify_guard(app, document, foreground, guard)
        if not _writable_context(app, context):
            raise ValueError("line font editing requires a normal drawing sheet")
        if before[field] == value:
            result.update(ok=True, options=before, changed=False)
            return result
        extension = _com_value(document, "Extension")
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-line-font", "IModelDocExtension.SetUserPreferenceInteger",
                               lambda: extension.SetUserPreferenceInteger(
                                   constants[LINE_FONT_FIELDS[field]], constants["swDetailingNoOptionSpecified"], value))
        if returned is not True:
            raise RuntimeError("line font setter did not return success")
        post = _state(document)
        after = _read(document, constants)
        _verify_context(app, document, context)
        _verify_metadata_state(app, document, post, foreground, changed=False)
        _verify_guard(app, document, foreground, guard)
        if after != {**before, field: value}:
            raise RuntimeError("line font setter changed unexpected defaults or failed readback")
        _verify_guard(app, document, foreground, guard)
        _verify_metadata_state(app, document, state, foreground, changed=True)
        post = _state(document)
        if _read(document, constants) != after:
            raise RuntimeError("line font defaults changed while marking dirty")
        _verify_context(app, document, context)
        _verify_metadata_state(app, document, post, foreground, changed=False)
        _verify_guard(app, document, foreground, guard)
        result.update(ok=True, options=after, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
