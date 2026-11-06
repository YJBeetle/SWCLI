"""Drawing document Line Font defaults, with a closed public write gate."""

from pathlib import Path
from ..document_line_font import LINE_FONT_FIELDS, validate_edit
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context


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


def read_document_line_font_windows(*, app, document):
    result = {"ok": False, "action": "document.line-font"}
    try:
        _drawing(document)
        state, foreground, context = _state(document), _com_value(app, "ActiveDoc"), _edit_context(document)
        options = _read(document, _constants())
        _verify_context(app, document, context)
        _verify_metadata_state(app, document, state, foreground, changed=False)
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
        constants = _constants()
        before = _read(document, constants)
        result.update(field=field, before=before)
        if before != expected_options:
            raise DocumentLineFontConflict("complete line font snapshot no longer matches")
        _verify_context(app, document, context)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if not _internal_calibration:
            raise DocumentLineFontUncalibrated("public line font writes require recorded native acceptance")
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
        if after != {**before, field: value}:
            raise RuntimeError("line font setter changed unexpected defaults or failed readback")
        _verify_metadata_state(app, document, state, foreground, changed=True)
        post = _state(document)
        if _read(document, constants) != after:
            raise RuntimeError("line font defaults changed while marking dirty")
        _verify_context(app, document, context)
        _verify_metadata_state(app, document, post, foreground, changed=False)
        result.update(ok=True, options=after, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
