"""Windows annotation-font adapter for the wired development operations.

The dispatcher enforces document/session/lease/update-stamp guards. This batch's
native and public acceptance is incomplete; registration is not release proof.
"""

from typing import Any

from ..document_annotation_fonts import (
    ANNOTATION_FONT_MEMBERS, ANNOTATION_FONT_PREFERENCE,
    annotation_font_matches, annotation_font_requested_value_matches,
    annotation_font_native_normalizations, annotation_font_snapshot,
    validate_annotation_font_snapshot, validate_annotation_font_value,
)
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context


class DocumentAnnotationFontConflict(RuntimeError):
    """Any observed annotation font field changed since the supplied snapshot."""


def _read_member(font, member):
    def read():
        value = getattr(font, member)
        return value() if callable(value) else value

    method = "ITextFormat." + member + ("" if member == "IsHeightSpecifiedInPts" else ".get")
    return native_call("document-annotation-font", method, read)


def _read_font(document):
    extension = _com_value(document, "Extension")
    font = native_call(
        "document-annotation-font", "IModelDocExtension.GetUserPreferenceTextFormat",
        lambda: extension.GetUserPreferenceTextFormat(
            ANNOTATION_FONT_PREFERENCE["preference"], ANNOTATION_FONT_PREFERENCE["option"]),
    )
    if font is None:
        raise RuntimeError("native document annotation font is unavailable")
    native = {member: _read_member(font, member) for member in ANNOTATION_FONT_MEMBERS.values()}
    return font, annotation_font_snapshot(native), native


def read_document_annotation_font_windows(*, app: Any, document: Any) -> dict:
    result = {"ok": False, "action": "document.annotation-font"}
    try:
        foreground = _com_value(app, "ActiveDoc")
        edit = _edit_context(document)
        state = _state(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        _, font, native = _read_font(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, font=font, native_font=native)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_annotation_font_windows(
    *, app: Any, document: Any, field: str, value: Any, expected_font: dict,
) -> dict:
    """Draft guarded setter, not evidence of native support or persistence.

    A TextFormat property assignment may affect a live object before the final
    document setter. Mutation evidence therefore begins before that assignment.
    """
    result = {"ok": False, "action": "document.annotation-font-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_annotation_font_value(field, value)
        validate_annotation_font_snapshot(expected_font)
        foreground = _com_value(app, "ActiveDoc")
        edit = _edit_context(document)
        _require_writable(document)
        state = _state(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        format_object, before, native_before = _read_font(document)
        result.update(field=field, before=before, native_before=native_before)
        if not annotation_font_matches(before, expected_font):
            raise DocumentAnnotationFontConflict("document annotation font no longer matches the expected snapshot")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if annotation_font_requested_value_matches(before, field, value):
            result.update(ok=True, font=before, native_font=native_before, changed=False,
                          native_normalizations=[])
            return result
        if not _writable_context(app, edit):
            raise ValueError("annotation font editing requires a normal drawing sheet or no active model sketch")
        member = ANNOTATION_FONT_MEMBERS[field]
        native_value = value / 1000.0 if field == "height_mm" else value
        extension = _com_value(document, "Extension")
        _require_writable(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        _require_writable(document)
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        native_call("document-annotation-font", "ITextFormat." + member + ".set",
                    lambda: setattr(format_object, member, native_value))
        # A live property assignment can advance stamp/dirty. It must not move
        # the document into another configuration, edit context or foreground.
        _require_writable(document)
        _verify_context(app, document, edit)
        property_state = _state(document)
        if (property_state[0], property_state[3]) != (state[0], state[3]):
            raise RuntimeError("document context changed during annotation font property assignment")
        _verify_metadata_state(app, document, property_state, foreground, changed=False)
        _require_writable(document)
        returned = native_call(
            "document-annotation-font", "IModelDocExtension.SetUserPreferenceTextFormat",
            lambda: extension.SetUserPreferenceTextFormat(
                ANNOTATION_FONT_PREFERENCE["preference"], ANNOTATION_FONT_PREFERENCE["option"], format_object),
        )
        if returned is not True:
            raise RuntimeError("native document annotation font setter did not return success")
        post_setter_state = _state(document)
        _, after, native_after = _read_font(document)
        result.update(observed_font=after, observed_native_font=native_after)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_setter_state, foreground, changed=False)
        if not annotation_font_requested_value_matches(after, field, value):
            raise RuntimeError("native document annotation font setter did not round-trip the requested value and mode")
        normalizations = annotation_font_native_normalizations(native_before, native_after, member)
        result["native_normalizations"] = normalizations
        _require_writable(document)
        _verify_metadata_state(app, document, state, foreground, changed=True, require_writable=True)
        _verify_context(app, document, edit)
        post_write_state = _state(document)
        _, final, native_final = _read_font(document)
        if final != after or native_final != native_after:
            raise RuntimeError("annotation font changed while marking the document for saving")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_write_state, foreground, changed=False)
        result.update(ok=True, font=after, native_font=native_after, changed=True,
                      native_normalizations=normalizations)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
