"""Internal standard candidate with a fixed, bounded observation profile.

The dispatcher enforces selected document/session/lease/update-stamp guards.
This development batch still requires native and installed public acceptance;
its finite transition whitelist is not populated by expectation.
"""

import ctypes
import json
import sys
from typing import Any

from ..document_annotation_fonts import ANNOTATION_FONT_MEMBERS
from ..document_annotations import ANNOTATION_FIELDS
from ..document_display_options import display_fields_for_document, resolve_display_preference_ids
from ..document_drafting_standard import (
    BASE_STANDARD_OPTIONS, CALIBRATED_DRAFTING_TRANSITIONS, CALIBRATED_DRAFTING_WINDOWS_REVISIONS, DRAFTING_DEFAULTS_PROFILE,
    DRAFTING_STANDARD_OPTION, DRAFTING_STANDARD_PREFERENCE, DRAFTING_STANDARDS,
    LENGTH_UNIT_NATIVE_FIELDS, drafting_defaults_coverage, drafting_standard_observation, validate_drafting_standard,
)
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotation_fonts import _read_font
from .windows_document_annotations import (
    _edit_context, _read_options as _read_annotations, _verify_context, _writable_context,
)
from .windows_document_display_options import _read_options as _read_display
from .windows_document_units import _read_units
from .windows_feature_inspection import _same


class DocumentDraftingStandardConflict(RuntimeError):
    """The standard or fixed observed defaults differ from the caller's snapshot."""


def _capture_state(app, document, *, writable=False):
    foreground = _com_value(app, "ActiveDoc")
    edit = _edit_context(document)
    if writable:
        _require_writable(document)
    state = _state(document)
    _verify_context(app, document, edit)
    if not _same(app, foreground, _com_value(app, "ActiveDoc")):
        raise RuntimeError("document foreground changed while capturing drafting metadata state")
    _verify_metadata_state(app, document, state, foreground, changed=False)
    return state, foreground, edit


def _read_standard(document, option=DRAFTING_STANDARD_OPTION):
    extension = _com_value(document, "Extension")
    raw = native_call(
        "document-drafting-standard", "IModelDocExtension.GetUserPreferenceInteger",
        lambda: extension.GetUserPreferenceInteger(DRAFTING_STANDARD_PREFERENCE, option),
    )
    return drafting_standard_observation(raw)


def _coverage(kind):
    return drafting_defaults_coverage(kind)


def _read_observed_defaults(document, kind):
    """Read only this fixed profile, with flat native-call traces from helpers.

    This is an audit of selected defaults, not a promise to observe every effect
    of changing a drafting standard. No caller-supplied reader or path is used.
    """
    annotations = _read_annotations(document)
    _, font, native_font = _read_font(document)
    units = _read_units(document)
    display = _read_display(document, kind, resolve_display_preference_ids())
    base = {name: _read_standard(document, spec["option"])
            for name, spec in BASE_STANDARD_OPTIONS.items()}
    return {
        "profile": DRAFTING_DEFAULTS_PROFILE, "document_type": kind,
        "coverage": _coverage(kind), "annotations": annotations,
        "annotation_font": {"font": font, "native_font": native_font},
        "length_units": units, "display": display, "base_standards": base,
    }


def _snapshot_key(value):
    # Unlike Python equality, JSON distinguishes booleans from integer prevalues.
    def check(item):
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("drafting snapshot keys must be strings")
            for child in item.values():
                check(child)
        elif type(item) is list:
            for child in item:
                check(child)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise ValueError("drafting snapshot must contain only JSON values")
    check(value)
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _keys(value, keys):
    return type(value) is dict and value.keys() == set(keys)


def _validate_snapshot(snapshot):
    if not _keys(snapshot, ("standard", "observed_defaults")):
        raise ValueError("a complete fixed drafting snapshot is required")
    standard, observed = snapshot["standard"], snapshot["observed_defaults"]
    if (not _keys(standard, ("value", "native_value"))
            or drafting_standard_observation(standard["native_value"]) != standard
            or not _keys(observed, ("profile", "document_type", "coverage", "annotations",
                                    "annotation_font", "length_units", "display", "base_standards"))):
        raise ValueError("drafting snapshot fields are incomplete or inconsistent")
    kind = observed["document_type"]
    if (type(kind) is not int or kind not in (1, 2, 3)
            or observed["profile"] != DRAFTING_DEFAULTS_PROFILE
            or _snapshot_key(observed["coverage"]) != _snapshot_key(_coverage(kind))):
        raise ValueError("drafting snapshot profile or coverage differs")
    font, units = observed["annotation_font"], observed["length_units"]
    if (not _keys(observed["annotations"], ANNOTATION_FIELDS)
            or not _keys(observed["display"], display_fields_for_document(kind))
            or not _keys(observed["base_standards"], BASE_STANDARD_OPTIONS)
            or not _keys(font, ("font", "native_font"))
            or not _keys(font["font"], ANNOTATION_FONT_MEMBERS)
            or not _keys(font["native_font"], ANNOTATION_FONT_MEMBERS.values())
            or not _keys(units, ("length_unit", "decimal_places", "native_units"))
            or not _keys(units["native_units"], LENGTH_UNIT_NATIVE_FIELDS)):
        raise ValueError("drafting snapshot observed defaults are incomplete")
    for group in ("annotations", "display", "base_standards"):
        if any(not _keys(row, ("value", "native_value")) for row in observed[group].values()):
            raise ValueError("drafting snapshot scalar observations are incomplete")
    _snapshot_key(snapshot)
    return snapshot


def _read_snapshot(document, kind):
    return _validate_snapshot({"standard": _read_standard(document),
                               "observed_defaults": _read_observed_defaults(document, kind)})


def read_document_drafting_standard_windows(*, app: Any, document: Any) -> dict:
    result = {"ok": False, "action": "document.drafting-standard"}
    try:
        state, foreground, edit = _capture_state(app, document)
        snapshot = _read_snapshot(document, state[0])
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, **snapshot)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def _require_calibrated_native_host(app):
    # No Windows calibration is promoted to Wine or another revision. Unknown
    # native-runtime detection is closed. The export check mirrors the existing
    # Windows tray detector, without treating loader failure as native Windows.
    message = "drafting-standard changes require calibration for this native host"
    if sys.platform != "win32":
        raise ValueError(message)
    try:
        ntdll = ctypes.WinDLL("ntdll")
    except (AttributeError, OSError) as error:
        raise ValueError(message) from error
    if getattr(ntdll, "wine_get_version", None) is not None:
        raise ValueError(message)
    revision = _com_value(app, "RevisionNumber")
    if type(revision) is not str or revision not in CALIBRATED_DRAFTING_WINDOWS_REVISIONS:
        raise ValueError(message)


def set_document_drafting_standard_windows(
    *, app: Any, document: Any, value: str, expected_snapshot: dict,
) -> dict:
    result = {"ok": False, "action": "document.drafting-standard-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_drafting_standard(value)
        _validate_snapshot(expected_snapshot)
        expected_key = _snapshot_key(expected_snapshot)
        state, foreground, edit = _capture_state(app, document, writable=True)
        before = _read_snapshot(document, state[0])
        result["before"] = before
        if _snapshot_key(before) != expected_key:
            raise DocumentDraftingStandardConflict("document drafting settings no longer match the expected snapshot")
        source = before["standard"]["value"]
        if source in ("custom", "other"):
            raise ValueError("custom or unknown document drafting standards are read-only")
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if source == value:
            result.update(ok=True, changed=False, **before)
            return result
        transition = (state[0], before["standard"]["native_value"],
                      DRAFTING_STANDARDS[value], DRAFTING_DEFAULTS_PROFILE)
        if transition not in CALIBRATED_DRAFTING_TRANSITIONS:
            raise ValueError("this document drafting standard transition requires native calibration")
        _require_calibrated_native_host(app)
        if not _writable_context(app, edit):
            raise ValueError("drafting standard editing requires a normal drawing sheet or no active model sketch")
        extension = _com_value(document, "Extension")
        _require_writable(document)
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        _require_writable(document)
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call(
            "document-drafting-standard", "IModelDocExtension.SetUserPreferenceInteger",
            lambda: extension.SetUserPreferenceInteger(
                DRAFTING_STANDARD_PREFERENCE, DRAFTING_STANDARD_OPTION, DRAFTING_STANDARDS[value]),
        )
        if returned is not True:
            raise RuntimeError("native document drafting standard setter did not return success")
        post_setter_state = _state(document)
        after = _read_snapshot(document, state[0])
        result["after"] = after
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_setter_state, foreground, changed=False)
        if after["standard"]["value"] != value:
            raise RuntimeError("native document drafting standard did not round-trip the requested value")
        result["observed_defaults_changed"] = (
            _snapshot_key(before["observed_defaults"]) != _snapshot_key(after["observed_defaults"]))
        _require_writable(document)
        _verify_metadata_state(app, document, state, foreground, changed=True, require_writable=True)
        _verify_context(app, document, edit)
        post_write_state = _state(document)
        final = _read_snapshot(document, state[0])
        result["final"] = final
        _verify_context(app, document, edit)
        _verify_metadata_state(app, document, post_write_state, foreground, changed=False)
        if _snapshot_key(final) != _snapshot_key(after):
            raise RuntimeError("drafting settings changed while marking the document for saving")
        result.update(ok=True, changed=True, **after)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
