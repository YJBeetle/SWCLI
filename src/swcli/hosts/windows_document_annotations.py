"""Protected document-specific annotation scalars; no font or standard writes."""

from math import isclose, isfinite
from typing import Any

from ..document_annotations import ANNOTATION_FIELDS, validate_annotation_value
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_units import _verify_edit_state


class DocumentAnnotationConflict(RuntimeError):
    """The selected annotation value no longer matches the caller's observation."""


def _read_options(document: Any) -> dict:
    extension = _com_value(document, "Extension")
    options = {}
    for field, spec in ANNOTATION_FIELDS.items():
        method = "GetUserPreference" + spec["kind"]
        raw = native_call("document-annotations", "IModelDocExtension." + method,
                          lambda spec=spec, method=method: getattr(extension, method)(
                              spec["preference"], spec["option"]))
        if spec["kind"] == "Toggle":
            valid, value = type(raw) is bool, raw
        elif spec["kind"] == "Double":
            valid = type(raw) in (int, float) and isfinite(raw) and raw > 0
            value = raw * 1000.0
            valid = valid and isfinite(value)
        else:
            valid = type(raw) is int
            value = next((name for name, code in spec["values"].items() if code == raw), "other")
        if not valid:
            raise RuntimeError(f"native document annotation field {field} is unreadable")
        options[field] = {"value": value, "native_value": raw}
    return options


def _matches(field, actual, expected):
    if ANNOTATION_FIELDS[field]["kind"] == "Double":
        return type(actual) in (int, float) and isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    return type(actual) is type(expected) and actual == expected


def read_document_annotation_options_windows(*, app: Any, document: Any) -> dict:
    result = {"ok": False, "action": "document.annotation-options"}
    try:
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        edit = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
        options = _read_options(document)
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, options=options)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_annotation_option_windows(
    *, app: Any, document: Any, field: str, value: Any, expected_value: Any,
) -> dict:
    result = {"ok": False, "action": "document.annotation-option-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_annotation_value(field, value)
        validate_annotation_value(field, expected_value, writable=False)
        _require_writable(document)
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        edit = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
        before = _read_options(document)
        result.update(field=field, before=before)
        if not _matches(field, before[field]["value"], expected_value):
            raise DocumentAnnotationConflict("document annotation value no longer matches the expected value")
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if _matches(field, before[field]["value"], value):
            result.update(ok=True, options=before, changed=False)
            return result
        if edit is not None:
            raise ValueError("annotation editing requires no active sketch")
        spec = ANNOTATION_FIELDS[field]
        native = (spec["values"][value] if spec["kind"] == "Integer" else
                  value / 1000.0 if spec["kind"] == "Double" else value)
        extension = _com_value(document, "Extension")
        method = "SetUserPreference" + spec["kind"]
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-annotations", "IModelDocExtension." + method,
                               lambda: getattr(extension, method)(spec["preference"], spec["option"], native))
        # On calibrated Windows 2025 all setters, including Toggle(false), return
        # True on success. False is a failed call, never a reason to retry.
        if returned is not True:
            raise RuntimeError("native document annotation setter did not return success")
        # A setter may legitimately alter the stamp/dirty flag. Its subsequent
        # getters are observations and must preserve the post-setter state.
        post_setter_state = _state(document)
        after = _read_options(document)
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, post_setter_state, foreground, changed=False)
        if not _matches(field, after[field]["value"], value):
            raise RuntimeError("native document annotation setter did not round-trip the requested value")
        if any(after[key] != before[key] for key in ANNOTATION_FIELDS if key != field):
            raise RuntimeError("native document annotation setter changed an unrequested field")
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=True)
        _verify_edit_state(app, document, edit)
        # Mark dirty at most once. The final read cannot clear it or advance the
        # stamp and then be silently repaired by another SetSaveFlag call.
        post_write_state = _state(document)
        final = _read_options(document)
        if final != after:
            raise RuntimeError("annotation options changed while marking the document for saving")
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, post_write_state, foreground, changed=False)
        result.update(ok=True, options=after, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
