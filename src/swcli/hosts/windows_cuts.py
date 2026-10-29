"""Blind or one-direction through-all material removal with native definition and volume evidence."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from ..cut_termination import resolve_cut_termination
from .native_trace import native_call
from .windows_dimensions import _circle_geometry
from .windows_rectangle_profiles import observe_rectangle_profile
from .windows_feature_inspection import _boolean, _integer, _types
from .windows import _com_value, _error
from .windows_documents import _diagnose_features, _inspect_bodies
from .windows_measurements import measure_part_windows
from .windows_sketches import _unabsorbed_profile


_UNSET = object()


class _CutScopeError(ValueError):
    code = "UnsupportedCutScope"


def _single_solid(document: Any) -> None:
    # Include hidden solids and surfaces; measuring only solids can hide an
    # unsupported surface or multi-body target. This observation never selects.
    bodies = document.GetBodies2(-1, False)
    if (not isinstance(bodies, (tuple, list)) or len(bodies) != 1
            or _integer(_com_value(bodies[0], "GetType"), "Body.GetType") != 0):
        raise _CutScopeError("through-all requires exactly one solid and no other bodies")


def _through_all_preflight(document: Any, sketch_feature: Any) -> None:
    if _integer(_com_value(document, "SelectionManager").GetSelectedObjectCount2(-1),
                "GetSelectedObjectCount2") != 0:
        raise _CutScopeError("through-all requires an empty selection")
    _single_solid(document)
    sketch = _com_value(sketch_feature, "GetSpecificFeature2")
    if sketch is None or _boolean(_com_value(sketch, "Is3D"), "Is3D"):
        raise _CutScopeError("through-all requires a planar sketch")
    segments = _com_value(sketch, "GetSketchSegments")
    if not isinstance(segments, (tuple, list)) or not 1 <= len(segments) <= 64:
        raise _CutScopeError("through-all profile is unavailable or unsupported")
    if len(segments) == 1:
        _circle_geometry(sketch)
    else:
        observe_rectangle_profile(sketch)


def cut_extrude_sketch_windows_with_handle(
    *,
    app: Any,
    document: Any,
    sketch_feature: Any,
    depth_mm: Any = _UNSET,
    end_condition: str = "blind",
    reverse: bool = False,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Cut all intersected solids along sketch normal (or its explicit reverse)."""
    result: Dict[str, Any] = {"ok": False, "action": "feature.cut-extrude"}
    feature = None
    try:
        termination = resolve_cut_termination({
            "end_condition": end_condition,
            **({"depth_mm": depth_mm} if depth_mm is not _UNSET else {}),
        })
    except ValueError as exc:
        result["error"] = {"type": "InvalidArgument", "message": str(exc)}
        return result, feature
    through_all = termination.end_condition == "through-all"
    depth_mm = termination.depth_mm
    native_end = 1 if through_all else 0
    # FeatureCut4 requires this argument even when it is unused. Never report
    # this placeholder as through-all travel or material thickness.
    native_depth = 0.001 if through_all else depth_mm / 1000
    selected = False
    incomplete_native_cut = False
    try:
        if int(_com_value(document, "GetType")) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "cut extrusion currently requires a part document",
            }
            return result, feature
        if (
            _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
            is not None
        ):
            result["error"] = {
                "type": "SketchEditInProgress",
                "message": "finish the existing sketch edit before creating a cut",
            }
            return result, feature
        if _unabsorbed_profile(app, document, sketch_feature) is None:
            result["error"] = {
                "type": "SketchUnavailable",
                "message": "the sketch is no longer an unabsorbed 2D profile in the selected document",
            }
            return result, feature
        if through_all:
            native_call("cut-preflight", "through-all-eligibility",
                        lambda: _through_all_preflight(document, sketch_feature))
        before = native_call(
            "cut-preflight",
            "measure_part_windows",
            lambda: measure_part_windows(document=document),
        )
        if not before["ok"]:
            result["error"] = before["error"]
            return result, feature
        result["measurement_before"] = before["metrics"]
        native_call(
            "profile-select",
            "ModelDoc.ClearSelection2",
            lambda: document.ClearSelection2(True),
        )
        selected = True
        if not native_call(
            "profile-select",
            "Feature.Select2",
            lambda: sketch_feature.Select2(False, 0),
        ):
            result["error"] = {
                "type": "SketchSelectionFailed",
                "message": "SOLIDWORKS could not select the registered sketch",
            }
            return result, feature
        # Native cuts default opposite the sketch normal, unlike bosses. Invert
        # Dir so this CLI's --reverse consistently means opposite the normal.
        # UseFeatScope=False affects all solids; no implicit body selection.
        manager = _com_value(document, "FeatureManager")
        incomplete_native_cut = True
        feature = native_call(
            "feature-create",
            "FeatureManager.FeatureCut4",
            lambda: manager.FeatureCut4(
                True,
                False,
                not reverse,
                native_end,
                0,
                native_depth,
                0.0,
                False,
                False,
                False,
                False,
                0.0,
                0.0,
                False,
                False,
                False,
                False,
                False,
                False,
                not through_all,
                False,
                False,
                False,
                0,
                0.0,
                False,
                False,
            ),
        )
        if feature is None:
            result["error"] = {
                "type": "CutExtrusionFailed",
                "message": "SOLIDWORKS did not create the cut feature",
            }
            return result, feature
        incomplete_native_cut = False
        result.update(
            {
                "depth_mm": depth_mm,
                "reverse": reverse,
                "affected_scope": "all-solid-bodies",
                "feature": {
                    "name": str(_com_value(feature, "Name")),
                    "type": str(_com_value(feature, "GetTypeName2")),
                },
            }
        )
        if through_all:
            result["end_condition"] = "through-all"
            if _types(feature)[1] != "Cut":
                raise _CutScopeError("native creation returned a different feature kind")
        result["rebuilt"] = bool(_com_value(document, "EditRebuild3"))
        result["diagnostics"] = native_call(
            "cut-verify",
            "diagnose_features",
            lambda: _diagnose_features(document, 500),
        )
        if (not result["rebuilt"] or not result["diagnostics"]["healthy"]
                or (through_all and result["diagnostics"]["truncated"])):
            result["error"] = {
                "type": "ModelInvalid",
                "message": "created cut did not pass rebuild diagnostics",
            }
            return result, feature
        after = native_call(
            "cut-verify",
            "measure_part_windows",
            lambda: measure_part_windows(document=document),
        )
        if not after["ok"]:
            result["error"] = after["error"]
            return result, feature
        result["measurement_after"] = after["metrics"]
        result["bodies"] = native_call(
            "cut-verify",
            "inspect_bodies",
            lambda: _inspect_bodies(document),
        )
        definition = _com_value(feature, "GetDefinition")
        actual_depth = None
        if not through_all:
            actual_depth = float(native_call(
                "cut-definition", "ExtrudeFeatureData.GetDepth",
                lambda: definition.GetDepth(True),
            )) * 1000
            if not math.isfinite(actual_depth):
                raise RuntimeError("SOLIDWORKS returned a nonfinite cut depth")
        read_bool = _boolean if through_all else lambda value, member: bool(value)
        read_int = _integer if through_all else lambda value, member: int(value)
        native_reverse = read_bool(_com_value(definition, "ReverseDirection"), "ReverseDirection")
        actual_reverse = not native_reverse
        end = read_int(native_call(
            "cut-definition", "ExtrudeFeatureData.GetEndCondition",
            lambda: definition.GetEndCondition(True),
        ), "GetEndCondition")
        both = read_bool(_com_value(definition, "BothDirections"), "BothDirections")
        settings = {}
        if through_all:
            # Retain each readback before judging settings; partial failures
            # must retain the exact created feature and available evidence.
            result["through_all_settings"] = settings
            settings["thin"] = _boolean(_com_value(definition, "IsThinFeature"), "IsThinFeature")
            settings["feature_scope"] = _boolean(_com_value(definition, "FeatureScope"), "FeatureScope")
            settings["from_type"] = _integer(_com_value(definition, "FromType"), "FromType")
            settings["forward_draft"] = _boolean(native_call(
                "cut-definition", "ExtrudeFeatureData.GetDraftWhileExtruding",
                lambda: definition.GetDraftWhileExtruding(True)), "GetDraftWhileExtruding")
            settings["needs_rebuild"] = _integer(_com_value(_com_value(document, "Extension"), "NeedsRebuild2"), "NeedsRebuild2")
            _single_solid(document)
        removed = before["metrics"]["volume_mm3"] - after["metrics"]["volume_mm3"]
        tolerance = max(1e-6, before["metrics"]["volume_mm3"] * 1e-12)
        passed = (
            (through_all or math.isclose(actual_depth, depth_mm, rel_tol=0, abs_tol=1e-6))
            and actual_reverse == reverse
            and end == native_end
            and (not through_all or settings == dict(
                thin=False, feature_scope=False, from_type=0,
                forward_draft=False, needs_rebuild=0))
            and not both
            and removed > tolerance
        )
        result["geometry_verification"] = {
            "passed": passed,
            "method": "native-cut-definition-and-volume",
            "actual_depth_mm": actual_depth,
            "actual_reverse": actual_reverse,
            "native_reverse_direction": native_reverse,
            "end_condition": end,
            "both_directions": both,
            "volume_removed_mm3": removed,
            "minimum_volume_change_mm3": tolerance,
            "absolute_depth_tolerance_mm": None if through_all else 1e-6,
        }
        if not passed:
            result["error"] = {
                "type": "CutVerificationFailed",
                "message": "cut definition or measured material removal did not match the requested operation",
            }
            return result, feature
        result["ok"] = True
        return result, feature
    except Exception as exc:
        result["error"] = ({"type": exc.code, "message": str(exc)}
                           if through_all and hasattr(exc, "code") else _error(exc))
        return result, feature
    finally:
        if incomplete_native_cut:
            try:
                # A failed FeatureCut4 can leave ExtrudedCut running even with
                # no active sketch/UI. ClearSelection2 alone does not end it;
                # hidden hosts can fault after this document is closed. Finish
                # only our incomplete native command, preserving the cut error.
                native_call(
                    "cut-cleanup",
                    "ModelDoc.SetPickMode",
                    lambda: document.SetPickMode(),
                )
            except Exception as exc:
                result.setdefault("warnings", []).append(
                    {"code": "cut-command-cleanup-failed", "message": str(exc)}
                )
        if selected:
            try:
                native_call(
                    "selection-cleanup",
                    "ModelDoc.ClearSelection2",
                    lambda: document.ClearSelection2(True),
                )
                if through_all and _integer(
                    _com_value(document, "SelectionManager").GetSelectedObjectCount2(-1),
                    "GetSelectedObjectCount2",
                ) != 0:
                    raise RuntimeError("through-all selection cleanup did not leave an empty selection")
            except Exception as exc:
                result.setdefault("warnings", []).append(
                    {"code": "selection-cleanup-failed", "message": str(exc)}
                )
                if through_all and result.get("ok"):
                    result["ok"] = False
                    result["error"] = {"type": "SelectionCleanupFailed", "message": str(exc)}


def cut_extrude_sketch_windows(
    *,
    app: Any,
    document: Any,
    sketch_feature: Any,
    depth_mm: Any = _UNSET,
    end_condition: str = "blind",
    reverse: bool = False,
) -> Dict[str, Any]:
    """Result-only facade for the same guarded native cut implementation."""
    result, _ = cut_extrude_sketch_windows_with_handle(
        app=app, document=document, sketch_feature=sketch_feature,
        **({"depth_mm": depth_mm} if depth_mm is not _UNSET else {}),
        end_condition=end_condition, reverse=reverse,
    )
    return result
