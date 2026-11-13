"""Candidate scalar storage only; never insert lines, marks, views or entities."""

from ..document_detailing_lines import (
    DETAILING_LINE_SNAPSHOT_FIELDS, validate_detailing_line_edit,
)
from . import windows_document_detailing as detailing
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable

# No native evidence exists for these fields. Do not inherit the legacy
# center-mark allowlist, and do not expose a wire/environment bypass.
CALIBRATED_LINE_REVISIONS = frozenset()


def _write_enabled(app):
    return bool(CALIBRATED_LINE_REVISIONS) and detailing._native_windows() and (
        _com_value(app, "RevisionNumber") in CALIBRATED_LINE_REVISIONS)


def _options(document, constants):
    return detailing._read_options(document, constants, fields=DETAILING_LINE_SNAPSHOT_FIELDS)


def read_document_detailing_line_options_windows(*, app, document):
    result = {"ok": False, "action": "document.detailing-line-options", "write_enabled": False}
    try:
        snapshot = detailing._snapshot(app, document)
        constants = detailing._constants(app, fields=DETAILING_LINE_SNAPSHOT_FIELDS)
        options = _options(document, constants)
        enabled = _write_enabled(app)
        detailing._verify(app, document, snapshot)
        result.update(ok=True, options=options, write_enabled=enabled)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_detailing_line_option_windows(*, app, document, field, value, expected_options):
    result = {"ok": False, "action": "document.detailing-line-option-set", "write_enabled": False,
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_detailing_line_edit(field, value, expected_options)
        if not _write_enabled(app):
            raise ValueError("drawing line default writes require field-specific native calibration")
        result["write_enabled"] = True
        _require_writable(document)
        snapshot = detailing._snapshot(app, document)
        constants = detailing._constants(app, fields=DETAILING_LINE_SNAPSHOT_FIELDS)
        before = _options(document, constants)
        result.update(field=field, before=before)
        if before != expected_options:
            raise ValueError("drawing line defaults no longer match the complete expected_options snapshot")
        detailing._verify(app, document, snapshot)
        if before[field] is value:
            result.update(ok=True, options=before, changed=False)
            return result
        if not detailing._writable_context(app, snapshot[2]):
            raise ValueError("drawing line default editing requires a normal drawing sheet")
        desired = {**before, field: value}
        extension = _com_value(document, "Extension")
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-detailing-lines", "IModelDocExtension.SetUserPreferenceToggle",
            lambda: extension.SetUserPreferenceToggle(constants[DETAILING_LINE_SNAPSHOT_FIELDS[field]],
                                                       constants["swDetailingNoOptionSpecified"], value))
        result["native_return"] = returned if type(returned) is bool else None
        # This candidate must not infer false-return success from another field.
        # The native plan records true/false returns before any allowlist change.
        if returned is not True:
            raise RuntimeError("native drawing line default setter did not return success")
        post = detailing._snapshot(app, document)
        after = _options(document, constants)
        detailing._verify(app, document, post)
        if after != desired:
            raise RuntimeError("native drawing line setter failed readback or changed an unrequested default")
        detailing._verify(app, document, snapshot, changed=True)
        final_state = detailing._snapshot(app, document)
        final = _options(document, constants)
        if final != desired:
            raise RuntimeError("drawing line defaults changed while marking for saving")
        detailing._verify(app, document, final_state)
        detailing._verify(app, document, (final_state[0], *snapshot[1:]))
        result.update(ok=True, options=final, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
