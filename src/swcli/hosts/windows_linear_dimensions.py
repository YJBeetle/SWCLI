"""Internal exact rectangle-dimension reads on the owning COM STA.

This is not generic length discovery or a public linear inspect/set capability.
The role comes from a verified live binding, never a name or a matching value.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from .windows import _com_value
from .windows_dimension_discovery import _displays, _profile, _state
from .windows_dimensions import (
    _DimensionError,
    _TOLERANCE_MM,
    _boolean,
    _descriptor,
    _equation_control,
    _failure,
    _integer,
    _same,
    _same_dimension,
)
from .windows_rectangle_profiles import (
    RectangleObservationError,
    observe_rectangle_profile,
)


def inspect_rectangle_dimension_windows(
    *, app: Any, document: Any, sketch_feature: Any, dimension: Any, kind: str
) -> Dict[str, Any]:
    """Read an exact bound width/height without selection, activation or edits.

    Writable state is observed, not required for reading. Geometry mismatch is
    reported as verification evidence, not silently corrected. Incomplete or
    changing observations never report success.
    """
    result: Dict[str, Any] = {"ok": False, "action": "dimension.inspect"}
    before = edit_before = None
    try:
        if kind not in ("width", "height"):
            raise _DimensionError(
                "InvalidArgument", "a rectangle binding must specify width or height"
            )
        if _integer(document, "GetType") != 1:
            raise _DimensionError(
                "UnsupportedDocumentType", "rectangle dimension reads require a part"
            )
        before, edit_before = _state(document)
        result["observation"] = {"before": before, "unchanged": False}
        feature, sketch = _profile(app, document, sketch_feature)
        if dimension is None:
            raise _DimensionError("DimensionUnavailable", "native dimension is absent")
        owner = _com_value(dimension, "GetFeatureOwner")
        if owner is None or not _same(app, owner, feature):
            raise _DimensionError(
                "DimensionUnavailable", "dimension has a different owning profile"
            )
        if _integer(dimension, "GetType") != 0:
            raise _DimensionError(
                "DimensionVerificationFailed",
                "native rectangle parameter is not a length",
            )

        found = False
        # Exhaust the complete display chain; a first match cannot hide a later
        # cycle, unreadable parameter or contradictory native presentation.
        for display in _displays(app, feature):
            native = display.GetDimension2(0)
            if native is None:
                raise _DimensionError(
                    "DimensionObservationUnavailable",
                    "an observable display has no readable native parameter",
                )
            if not _same_dimension(app, native, dimension):
                continue
            if _integer(display, "Type2") != {"width": 11, "height": 12}[kind]:
                raise _DimensionError(
                    "DimensionVerificationFailed",
                    "native display contradicts the registered linear role",
                )
            found = True
        if not found:
            raise _DimensionError(
                "DimensionUnavailable", "the exact dimension is no longer observable"
            )
        descriptor = _descriptor(document, dimension, kind=kind)
        matched = descriptor["configuration"] == before["configuration"]
        result["observation"]["configuration_matched"] = matched
        if not matched:
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "native configuration changed during reading",
            )
        try:
            profile = observe_rectangle_profile(sketch)
        except RectangleObservationError as exc:
            raise _DimensionError(exc.code, str(exc)) from exc
        actual_value = profile.width_mm if kind == "width" else profile.height_mm
        result.update(
            dimension=descriptor,
            geometry_verification={
                "method": "sketch-local-rectangle",
                "passed": math.isclose(
                    actual_value, descriptor["value"], rel_tol=0, abs_tol=_TOLERANCE_MM
                ),
                "dimension_kind": kind,
                "expected_value_mm": descriptor["value"],
                "actual_width_mm": profile.width_mm,
                "actual_height_mm": profile.height_mm,
                "actual_center_mm": {
                    "x": profile.center_mm[0],
                    "y": profile.center_mm[1],
                    "z": 0,
                },
                "bounds_mm": list(profile.bounds_mm),
                "profile_segment_count": 4,
                "construction_segment_count": profile.construction_segment_count,
                "max_abs_z_mm": profile.max_abs_z_mm,
                "absolute_tolerance_mm": _TOLERANCE_MM,
            },
            constraint_status=_integer(sketch, "GetConstrainedStatus"),
            editing=before["editing"],
            equation_control=_equation_control(document, descriptor["native_name"]),
            design_table_controlled=_boolean(dimension, "IsDesignTableDimension"),
        )
    except Exception as exc:
        _failure(result, exc)
    finally:
        if before is not None:
            try:
                after, edit_after = _state(document)
                result["observation"]["after"] = after
                unchanged = (
                    before == after
                    and result["observation"].get("configuration_matched", True)
                    and (edit_before is None or _same(app, edit_before, edit_after))
                )
                result["observation"]["unchanged"] = unchanged
                if not unchanged:
                    raise _DimensionError(
                        "DimensionObservationUnavailable",
                        "native update stamp, configuration or sketch edit changed during reading",
                    )
            except Exception as exc:
                if "error" in result:
                    result.setdefault("warnings", []).append(
                        {
                            "code": "dimension-inspect-state-check-failed",
                            "message": str(exc),
                        }
                    )
                else:
                    _failure(result, exc)
    result["ok"] = "error" not in result
    return result
