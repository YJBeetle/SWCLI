"""Guarded part image quality candidate. No GLB options or global writes."""
import os
from typing import Any

from ..document_image_quality import (IMAGE_QUALITY_FIELDS, NATIVE_FIELDS, SHADED_MODES,
    exact_snapshot, finite_number, linked_changes, matches, quality_snapshot, validate_quality, validate_value)
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state as _metadata_state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context


class DocumentImageQualityUnsupported(RuntimeError):
    """Writes remain closed outside explicitly enabled internal calibration."""


class DocumentImageQualityConflict(RuntimeError):
    """The full image quality snapshot differs from the expected observation."""


def _range(extension):
    import pythoncom
    from win32com.client import VARIANT
    outputs = [VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, float("nan")) for _ in range(3)]
    status = native_call("document-image-quality", "IModelDocExtension.GetUserPreferenceDoubleValueRange",
                         lambda: extension.GetUserPreferenceDoubleValueRange(32, *outputs))
    return status, *(item.value for item in outputs)


def _read_quality(document):
    extension = _com_value(document, "Extension")
    raw = {}
    for key, (kind, preference) in NATIVE_FIELDS.items():
        method = "GetUserPreference" + kind
        raw[key] = native_call("document-image-quality", "IModelDocExtension." + method,
                              lambda method=method, preference=preference: getattr(extension, method)(preference, 0))
    status, current, low, high = _range(extension)
    if type(status) is not int or status not in (0, 1):
        raise RuntimeError("native image quality deviation range could not be read")
    if not finite_number(current, positive=True) or current != raw["shaded_deviation_m"]:
        raise RuntimeError("native image quality deviation changed during range observation")
    return quality_snapshot(raw, {"status": status, "bounds_m": [low, high] if status == 0 else []})


def _state(document):
    identity = tuple(_com_value(document, name) for name in
                     ("GetPathName", "GetTitle", "IsOpenedReadOnly", "IsOpenedViewOnly"))
    if any(type(value) is not str for value in identity[:2]) or any(type(value) is not bool for value in identity[2:]):
        raise RuntimeError("document identity or access mode is unreadable")
    return _metadata_state(document) + identity


def _verify(app, document, state, foreground, edit):
    _verify_context(app, document, edit)
    if _state(document)[4:] != state[4:]:
        raise RuntimeError("document identity or access mode changed during image quality operation")
    _verify_metadata_state(app, document, state[:4], foreground, changed=False)


def _baseline(app, document):
    foreground = _com_value(app, "ActiveDoc")
    edit = _edit_context(document)
    state = _state(document)
    _verify(app, document, state, foreground, edit)
    if state[0] != 1:
        raise ValueError("the first image quality profile supports part documents only")
    return state, foreground, edit


def read_document_image_quality_windows(*, app: Any, document: Any) -> dict:
    result = {"ok": False, "action": "document.image-quality"}
    try:
        state, foreground, edit = _baseline(app, document)
        quality = _read_quality(document)
        _verify(app, document, state, foreground, edit)
        result.update(ok=True, quality=quality)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_image_quality_windows(*, app: Any, document: Any, field: str, value: Any, expected_quality: dict) -> dict:
    result = {"ok": False, "action": "document.image-quality-set", "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_value(field, value); validate_quality(expected_quality)
        if os.environ.get("SWCLI_IMAGE_QUALITY_CALIBRATION") != "1":
            raise DocumentImageQualityUnsupported(
                "image quality writes require internal calibration; GLB tessellation control is unproven")
        state, foreground, edit = _baseline(app, document)
        _require_writable(document)
        before = _read_quality(document)
        result.update(field=field, before=before)
        _verify(app, document, state, foreground, edit)
        if not exact_snapshot(before, expected_quality):
            raise DocumentImageQualityConflict("document image quality differs from the complete expected snapshot")
        if matches(field, before[field], value):
            result.update(ok=True, quality=before, changed=False, linked_changes=[])
            return result
        if not _writable_context(app, edit):
            raise ValueError("image quality editing requires no active part sketch")
        if before["apply_to_referenced_parts"] is not False or before["shaded_mode"] == "other":
            raise ValueError("image quality editing requires a known, non-propagating part profile")
        if field == "shaded_deviation_mm":
            bounds = before["deviation_range"]
            native = value / 1000.0
            if before["shaded_mode"] != "custom":
                raise ValueError("set shaded_mode to custom explicitly before changing its deviation")
            if bounds["status"] != 0 or not bounds["bounds_m"][0] <= native <= bounds["bounds_m"][1]:
                raise ValueError("deviation is outside the observed native range or range is unavailable")
        else:
            native = SHADED_MODES[value] if field == "shaded_mode" else value
        spec = IMAGE_QUALITY_FIELDS[field]
        extension = _com_value(document, "Extension")
        method = "SetUserPreference" + spec["kind"]
        _verify(app, document, state, foreground, edit)
        _require_writable(document)
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-image-quality", "IModelDocExtension." + method,
                              lambda: getattr(extension, method)(spec["preference"], 0, native))
        # Preserve unexpected native evidence without letting a result-schema
        # error replace the first real failure. Never invoke a fallback setter.
        result["native_return"] = (returned if returned is None or type(returned) in (str, bool, int)
                                   or finite_number(returned) else {"type": type(returned).__name__})
        if returned is not True:
            raise RuntimeError("native image quality setter did not return success; no retry")
        post = _state(document)
        if (post[0], post[3], post[4:]) != (state[0], state[3], state[4:]):
            raise RuntimeError("document identity or configuration changed during image quality setter")
        _require_writable(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post[:4], foreground, changed=False)
        after = _read_quality(document)
        result["observed_quality"] = after
        _verify(app, document, post, foreground, edit)
        if not matches(field, after[field], value):
            raise RuntimeError("native image quality setter did not read back the requested value")
        changes = linked_changes(before, after, field)
        # Recheck writable/context before the sole possible dirty mutation.
        _verify(app, document, post, foreground, edit)
        _require_writable(document)
        _verify_metadata_state(app, document, state[:4], foreground, changed=True)
        post_dirty = _state(document)
        if post_dirty[4:] != state[4:]:
            raise RuntimeError("document identity or access mode changed while marking image quality dirty")
        _verify(app, document, post_dirty, foreground, edit)
        final = _read_quality(document)
        _verify(app, document, post_dirty, foreground, edit)
        if not exact_snapshot(final, after):
            raise RuntimeError("image quality changed while marking the document for saving")
        result.update(ok=True, quality=after, changed=True, linked_changes=changes)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
