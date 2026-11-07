"""Windows adapter for the wired, bounded document display operation pair.

Read-r1 proves IDs/getter applicability; batch native/public acceptance remains
in progress. The optional private mapping is only an internal probe/test seam.
"""

from math import isclose
from typing import Any, Optional

from ..document_display_options import (
    DISPLAY_FIELDS, display_fields_for_document, display_native_value,
    display_observation, resolve_display_preference_ids, validate_display_value,
)
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state
from .windows_document_preferences_guard import (capture_foreground, verify_metadata_state as _verify_metadata_state,
                                                 require_calibrated_native_host as _require_calibrated_native_host)
from .windows_document_annotations import _edit_context, _verify_context, _writable_context


class DocumentDisplayConflict(RuntimeError):
    """The selected display field no longer matches its observed prevalue."""


def _read_options(document, kind, preference_ids):
    extension = _com_value(document, "Extension")
    options = {}
    for field, spec in display_fields_for_document(kind).items():
        method = "GetUserPreference" + spec["kind"]
        raw = native_call(
            "document-display-options", "IModelDocExtension." + method,
            lambda spec=spec, method=method: getattr(extension, method)(
                preference_ids[spec["symbol"]], spec["option"]),
        )
        options[field] = display_observation(field, raw)
    return options


def _matches(field, actual, expected):
    if DISPLAY_FIELDS[field]["kind"] == "Double":
        return type(actual) in (int, float) and isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    return type(actual) is type(expected) and actual == expected


def _cas_matches(field, actual, expected):
    """Observed old values are exact; float tolerance is only for targets."""
    if DISPLAY_FIELDS[field]["kind"] == "Double":
        return type(actual) in (int, float) and type(expected) in (int, float) and actual == expected
    return type(actual) is type(expected) and actual == expected


def read_document_display_options_windows(
    *, app: Any, document: Any, _preference_ids: Optional[dict] = None,
) -> dict:
    result = {"ok": False, "action": "document.display-options"}
    try:
        preference_ids = resolve_display_preference_ids(_preference_ids)
        foreground = capture_foreground(app, document)
        edit = _edit_context(document)
        state = _state(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        options = _read_options(document, state[0], preference_ids)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, options=options)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_display_option_windows(
    *, app: Any, document: Any, field: str, value: Any, expected_value: Any,
    _preference_ids: Optional[dict] = None,
) -> dict:
    result = {"ok": False, "action": "document.display-option-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_display_value(field, value)
        validate_display_value(field, expected_value, writable=False)
        preference_ids = resolve_display_preference_ids(_preference_ids)
        foreground = capture_foreground(app, document)
        edit = _edit_context(document)
        _require_writable(document)
        state = _state(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if field not in display_fields_for_document(state[0]):
            raise ValueError("the selected display field is not applicable to this document type")
        before = _read_options(document, state[0], preference_ids)
        result.update(field=field, before=before)
        if not _cas_matches(field, before[field]["value"], expected_value):
            raise DocumentDisplayConflict("document display value no longer matches the expected value")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if _matches(field, before[field]["value"], value):
            result.update(ok=True, options=before, changed=False)
            return result
        _require_calibrated_native_host(app)
        if not _writable_context(app, edit):
            raise ValueError("display editing requires a normal drawing sheet or no active model sketch")
        spec = DISPLAY_FIELDS[field]
        native_value = display_native_value(field, value)
        extension = _com_value(document, "Extension")
        method = "SetUserPreference" + spec["kind"]
        _require_writable(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        _require_writable(document)
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call(
            "document-display-options", "IModelDocExtension." + method,
            lambda: getattr(extension, method)(preference_ids[spec["symbol"]], spec["option"], native_value),
        )
        if returned is not True:
            raise RuntimeError("native document display setter did not return success")
        post_setter_state = _state(document)
        after = _read_options(document, state[0], preference_ids)
        result["observed_options"] = after
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_setter_state, foreground, changed=False)
        if not _matches(field, after[field]["value"], value):
            raise RuntimeError("native document display setter did not round-trip the requested value")
        if any(after[key] != before[key] for key in before if key != field):
            raise RuntimeError("native document display setter changed an unrequested field")
        _require_writable(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=True, require_writable=True)
        _verify_context(app, document, edit)
        post_write_state = _state(document)
        final = _read_options(document, state[0], preference_ids)
        if final != after:
            raise RuntimeError("display options changed while marking the document for saving")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_write_state, foreground, changed=False)
        result.update(ok=True, options=after, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
