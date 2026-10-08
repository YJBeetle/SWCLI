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
    _CURRENT_CONFIGURATION,
    _DimensionError,
    _TOLERANCE_MM,
    _boolean,
    _descriptor,
    _equation_control,
    _failure,
    _integer,
    _measurement,
    _positive_length,
    _require_writable,
    _same,
    _same_dimension,
    _variant,
)
from .native_trace import native_call
from .windows_documents import _diagnose_features
from .windows_rectangle_dimensions import _observe, _verify
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


def set_rectangle_dimension_windows(
    *,
    app: Any,
    document: Any,
    sketch_feature: Any,
    dimension: Any,
    kind: str,
    value_mm: float,
) -> Dict[str, Any]:
    """Edit one internal width/height, preserving the other size and center.

    The caller owns activation and protocol guards. No implicit positioning,
    sketch editing, retry or rollback; even a failed setter may have mutated.
    """
    result: Dict[str, Any] = {"ok": False, "action": "dimension.set"}
    attempted = False
    try:
        if kind not in ("width", "height") or (
            not _positive_length(value_mm)
            or value_mm <= 2 * _TOLERANCE_MM
            or math.ulp(value_mm) > _TOLERANCE_MM
        ):
            raise _DimensionError(
                "InvalidArgument",
                "a bound width/height needs a positive, resolvable value_mm",
            )
        result["value_mm"] = value_mm
        if (
            _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
            is not None
        ):
            raise _DimensionError(
                "SketchEditInProgress", "finish the existing sketch edit first"
            )
        before = inspect_rectangle_dimension_windows(
            app=app,
            document=document,
            sketch_feature=sketch_feature,
            dimension=dimension,
            kind=kind,
        )
        result["before"] = before
        if not before["ok"]:
            result["error"] = before["error"]
            return result
        result.update(
            dimension=before["dimension"],
            before_value_mm=before["dimension"]["value"],
            equation_control=before["equation_control"],
            design_table_controlled=before["design_table_controlled"],
        )
        _require_writable(
            before["dimension"],
            before["equation_control"],
            before["design_table_controlled"],
        )
        if not before["geometry_verification"]["passed"]:
            raise _DimensionError(
                "DimensionVerificationFailed",
                "native parameter and rectangle disagree before editing",
            )
        geometry = before["geometry_verification"]
        center = geometry["actual_center_mm"]
        width = value_mm if kind == "width" else geometry["actual_width_mm"]
        height = value_mm if kind == "height" else geometry["actual_height_mm"]
        measurement_before = _measurement(document)
        result["downstream"] = {
            "applicable": measurement_before is not None,
            "measurement_before": measurement_before,
            "measurement_after": None,
        }
        pre_mutation_state, _ = _state(document)
        if pre_mutation_state != before["observation"]["after"]:
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "native state changed before the size edit",
            )
        attempted = True
        status = native_call(
            "rectangle-dimension-set",
            "Dimension.SetSystemValue3",
            lambda: dimension.SetSystemValue3(
                value_mm / 1000, _CURRENT_CONFIGURATION, _variant("empty", None)
            ),
        )
        if isinstance(status, bool) or not isinstance(status, int):
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "native setter status is not an integer",
            )
        result["native_status"] = status
        if status != 0:
            raise _DimensionError(
                "DimensionSetFailed", "SOLIDWORKS rejected the linear value"
            )
        result["rebuilt"] = _boolean(document, "EditRebuild3")
        result["needs_rebuild"] = _integer(
            _com_value(document, "Extension"), "NeedsRebuild2"
        )
        result["diagnostics"] = _diagnose_features(document, 500)
        after = inspect_rectangle_dimension_windows(
            app=app,
            document=document,
            sketch_feature=sketch_feature,
            dimension=dimension,
            kind=kind,
        )
        result["after"] = after
        if not after["ok"]:
            result["error"] = after["error"]
            result["modification_may_have_happened"] = True
            return result
        result.update(
            dimension=after["dimension"],
            equation_control=after["equation_control"],
            design_table_controlled=after["design_table_controlled"],
            editing=after["editing"],
            constraint_status=after["constraint_status"],
        )
        _require_writable(
            after["dimension"],
            after["equation_control"],
            after["design_table_controlled"],
            post_mutation=True,
        )
        _, sketch = _profile(app, document, sketch_feature)
        result["geometry_verification"] = _verify(
            _observe(sketch), width, height, (center["x"], center["y"])
        )
        measurement_after = _measurement(document)
        result["downstream"].update(
            applicable=measurement_before is not None or measurement_after is not None,
            measurement_after=measurement_after,
        )
        final_state, _ = _state(document)
        result["final_state"] = final_state
        if final_state != after["observation"]["after"]:
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "native state changed during final verification",
            )
        if (
            result["rebuilt"] is not True
            or result["needs_rebuild"] != 0
            or result["diagnostics"]["healthy"] is not True
            or result["diagnostics"]["truncated"] is not False
        ):
            raise _DimensionError(
                "ModelInvalid",
                "updated rectangle did not pass complete rebuild diagnostics",
            )
        if (
            not math.isclose(
                after["dimension"]["value"], value_mm, rel_tol=0, abs_tol=_TOLERANCE_MM
            )
            or after["dimension"]["configuration"]
            != before["dimension"]["configuration"]
            or not after["geometry_verification"]["passed"]
            or not result["geometry_verification"]["passed"]
            or after["editing"]
            or (measurement_before is not None and measurement_after is None)
        ):
            raise _DimensionError(
                "DimensionVerificationFailed",
                "linear value, other size, center, configuration or downstream evidence did not match",
            )
        result["ok"] = True
    except Exception as exc:
        _failure(result, exc)
        if attempted:
            result["modification_may_have_happened"] = True
    return result
