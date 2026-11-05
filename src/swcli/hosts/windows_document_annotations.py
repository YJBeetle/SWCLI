"""Protected document-specific annotation scalars; no font or standard writes."""

from math import isclose, isfinite
from typing import Any

from ..document_annotations import ANNOTATION_FIELDS, validate_annotation_value
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_feature_inspection import _same


class DocumentAnnotationConflict(RuntimeError):
    """The selected annotation value no longer matches the caller's observation."""


def _edit_context(document):
    context = {"sketch": _com_value(_com_value(document, "SketchManager"), "ActiveSketch")}
    if _com_value(document, "GetType") != 3:
        return context

    sheet = _com_value(document, "GetCurrentSheet")
    view = _com_value(document, "GetFirstView")
    if sheet is None or view is None:
        raise RuntimeError("drawing sheet context is unavailable")
    context.update(
        sheet=sheet, sheet_view=view,
        sheet_sketch=_com_value(view, "GetSketch"),
        template_sketch=_com_value(sheet, "GetTemplateSketch"),
        edit_sheet=_com_value(document, "GetEditSheet"),
        active_view=_com_value(document, "ActiveDrawingView"),
        sheet_name=_com_value(sheet, "GetName"),
        sheet_view_name=_com_value(view, "GetName2"),
        sheet_view_model=_com_value(view, "GetReferencedModelName"),
    )
    if (type(context["edit_sheet"]) is not bool
            or any(type(context[key]) is not str for key in ("sheet_name", "sheet_view_name", "sheet_view_model"))):
        raise RuntimeError("drawing sheet context is unreadable")
    return context


def _verify_context(app, document, before):
    after = _edit_context(document)
    if before.keys() != after.keys():
        raise RuntimeError("document editing context changed during annotation operation")
    references = {"sketch", "sheet", "sheet_view", "sheet_sketch", "template_sketch", "active_view"}
    if any(not _same(app, before[key], after[key]) if key in references else before[key] != after[key]
           for key in before):
        raise RuntimeError("document editing context changed during annotation operation")


def _writable_context(app, context):
    if "sheet" not in context:
        return context["sketch"] is None
    return (context["edit_sheet"] is True and context["active_view"] is None
            and context["sheet_view_model"] == ""
            and bool(context["sheet_name"] and context["sheet_view_name"])
            and all(context[key] is not None for key in ("sheet", "sheet_view", "sheet_sketch", "sketch", "template_sketch"))
            and _same(app, context["sketch"], context["sheet_sketch"])
            and not _same(app, context["sketch"], context["template_sketch"]))


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
        edit = _edit_context(document)
        options = _read_options(document)
        _verify_context(app, document, edit)
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
        edit = _edit_context(document)
        before = _read_options(document)
        result.update(field=field, before=before)
        if not _matches(field, before[field]["value"], expected_value):
            raise DocumentAnnotationConflict("document annotation value no longer matches the expected value")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if _matches(field, before[field]["value"], value):
            result.update(ok=True, options=before, changed=False)
            return result
        if not _writable_context(app, edit):
            raise ValueError("annotation editing requires a normal drawing sheet or no active model sketch")
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
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_setter_state, foreground, changed=False)
        if not _matches(field, after[field]["value"], value):
            raise RuntimeError("native document annotation setter did not round-trip the requested value")
        if any(after[key] != before[key] for key in ANNOTATION_FIELDS if key != field):
            raise RuntimeError("native document annotation setter changed an unrequested field")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=True)
        _verify_context(app, document, edit)
        # Mark dirty at most once. The final read cannot clear it or advance the
        # stamp and then be silently repaired by another SetSaveFlag call.
        post_write_state = _state(document)
        final = _read_options(document)
        if final != after:
            raise RuntimeError("annotation options changed while marking the document for saving")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_write_state, foreground, changed=False)
        result.update(ok=True, options=after, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
