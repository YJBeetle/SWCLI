"""Document default tolerances. Never obtains IDimension or changes feature values."""
import ctypes
import sys
from copy import deepcopy

from ..document_tolerances import TOLERANCE_FIELDS, PUBLIC_WRITE_FIELDS, PUBLIC_WRITE_REVISIONS, CALIBRATED_PREVALUES, native_constants, validate_value
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context as _verify_edit_context, _writable_context
from .windows_feature_inspection import _same


def _native_windows():
    if sys.platform != "win32":
        return False
    # Match the accepted detailing guard: Wine reports win32 as well.
    # An unavailable native probe propagates to a closed failure receipt.
    return getattr(ctypes.WinDLL("ntdll"), "wine_get_version", None) is None


def _write_enabled(app):
    return (bool(PUBLIC_WRITE_FIELDS) and _native_windows()
            and _com_value(app, "RevisionNumber") in PUBLIC_WRITE_REVISIONS)


def _identity(document):
    identity = (_com_value(document, "GetTitle"), _com_value(document, "GetPathName"))
    if any(type(value) is not str for value in identity):
        raise RuntimeError("document identity is unreadable")
    return identity


def _context(app, document, foreground):
    return {"edit": _edit_context(document), "identity": _identity(document),
            "foreground": foreground,
            "foreground_state": ((_state(foreground), _identity(foreground))
                if foreground is not None and not _same(app, foreground, document) else None)}


def _verify_context(app, document, before):
    _verify_edit_context(app, document, before["edit"])
    if _identity(document) != before["identity"]:
        raise RuntimeError("document identity changed during tolerance operation")
    if before["foreground_state"] is not None:
        foreground = before["foreground"]
        if (_state(foreground), _identity(foreground)) != before["foreground_state"]:
            raise RuntimeError("foreground document changed during background tolerance operation")


def _read_options(document):
    constants = native_constants()
    extension = _com_value(document, "Extension")
    options = {}
    for field, spec in TOLERANCE_FIELDS.items():
        raw = native_call("document-tolerances", "IModelDocExtension.GetUserPreferenceInteger",
                          lambda spec=spec: extension.GetUserPreferenceInteger(
                              constants[spec["preference"]], constants["swDetailingLinearDimension"]))
        if type(raw) is not int:
            raise RuntimeError("unreadable native document tolerance: " + field)
        value = next((name for name, code in spec["values"].items() if code == raw), "other")
        options[field] = {"value": value, "native_value": raw}
    return options


def read_document_tolerances_windows(*, app, document):
    result = {"ok": False, "action": "document.tolerances", "scope": "document_defaults_linear"}
    try:
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        edit = _context(app, document, foreground)
        options = _read_options(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, options=options, write_enabled=_write_enabled(app))
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_tolerance_windows(*, app, document, field, value, expected_options):
    result = {"ok": False, "action": "document.tolerance-set", "scope": "document_defaults_linear",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_value(field, value)
        if field not in PUBLIC_WRITE_FIELDS:
            raise ValueError("document tolerance writes require native public acceptance; disabled")
        if not _write_enabled(app):
            raise ValueError("document tolerance writes require the calibrated native Windows revision")
        _require_writable(document)
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        edit = _context(app, document, foreground)
        before = _read_options(document)
        result.update(field=field, before=deepcopy(before))
        if before != expected_options:
            raise ValueError("complete document tolerance snapshot no longer matches expected_options")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if any(before[key]["value"] not in CALIBRATED_PREVALUES[key] for key in before):
            raise ValueError("document tolerance prevalue profile is outside the calibrated scope")
        if before[field]["value"] == value:
            result.update(ok=True, changed=False, options=before)
            return result
        if not _writable_context(app, edit["edit"]):
            raise ValueError("tolerance editing requires a normal drawing sheet or no model sketch")
        constants = native_constants()
        spec = TOLERANCE_FIELDS[field]
        extension = _com_value(document, "Extension")
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-tolerances", "IModelDocExtension.SetUserPreferenceInteger",
                               lambda: extension.SetUserPreferenceInteger(constants[spec["preference"]],
                                   constants["swDetailingLinearDimension"], spec["values"][value]))
        if returned is not True:
            raise RuntimeError("native tolerance setter did not return success")
        post_setter = _state(document)
        after = _read_options(document)
        result["options"] = after
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_setter, foreground, changed=False)
        if after[field]["value"] != value or any(after[key] != before[key] for key in before if key != field):
            raise RuntimeError("native tolerance setter failed exact isolated round-trip")
        _verify_metadata_state(app, document, state, foreground, changed=True)
        _verify_context(app, document, edit)
        post_write = _state(document)
        final = _read_options(document)
        if final != after:
            raise RuntimeError("tolerance defaults drifted while marking document for saving")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_write, foreground, changed=False)
        result.update(ok=True, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
