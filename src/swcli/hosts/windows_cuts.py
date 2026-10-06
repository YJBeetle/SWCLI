"""Explicit blind material removal with native definition and volume evidence."""

from __future__ import annotations

import math
from typing import Any, Dict

from .windows import _com_value, _error
from .windows_documents import _diagnose_features, _inspect_bodies
from .windows_measurements import measure_part_windows
from .windows_sketches import _unabsorbed_profile


def cut_extrude_sketch_windows(
    *,
    app: Any,
    document: Any,
    sketch_feature: Any,
    depth_mm: float,
    reverse: bool = False,
) -> Dict[str, Any]:
    """Cut all intersected solids along sketch normal (or its explicit reverse)."""
    result: Dict[str, Any] = {"ok": False, "action": "feature.cut-extrude"}
    if not math.isfinite(depth_mm) or depth_mm <= 0 or depth_mm / 1000 <= 0:
        result["error"] = {
            "type": "InvalidArgument",
            "message": "depth_mm must be a positive representable finite length",
        }
        return result
    selected = False
    try:
        if int(_com_value(document, "GetType")) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "cut extrusion currently requires a part document",
            }
            return result
        if (
            _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
            is not None
        ):
            result["error"] = {
                "type": "SketchEditInProgress",
                "message": "finish the existing sketch edit before creating a cut",
            }
            return result
        if _unabsorbed_profile(app, document, sketch_feature) is None:
            result["error"] = {
                "type": "SketchUnavailable",
                "message": "the sketch is no longer an unabsorbed 2D profile in the selected document",
            }
            return result
        before = measure_part_windows(document=document)
        if not before["ok"]:
            result["error"] = before["error"]
            return result
        result["measurement_before"] = before["metrics"]
        document.ClearSelection2(True)
        selected = True
        if not sketch_feature.Select2(False, 0):
            result["error"] = {
                "type": "SketchSelectionFailed",
                "message": "SOLIDWORKS could not select the registered sketch",
            }
            return result
        # Native cuts default opposite the sketch normal, unlike bosses. Invert
        # Dir so this CLI's --reverse consistently means opposite the normal.
        # UseFeatScope=False affects all solids; no implicit body selection.
        feature = _com_value(document, "FeatureManager").FeatureCut4(
            True,
            False,
            not reverse,
            0,
            0,
            depth_mm / 1000,
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
            True,
            False,
            False,
            False,
            0,
            0.0,
            False,
            False,
        )
        if feature is None:
            result["error"] = {
                "type": "CutExtrusionFailed",
                "message": "SOLIDWORKS did not create the cut feature",
            }
            return result
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
        result["rebuilt"] = bool(_com_value(document, "EditRebuild3"))
        result["diagnostics"] = _diagnose_features(document, 500)
        if not result["rebuilt"] or not result["diagnostics"]["healthy"]:
            result["error"] = {
                "type": "ModelInvalid",
                "message": "created cut did not pass rebuild diagnostics",
            }
            return result
        after = measure_part_windows(document=document)
        if not after["ok"]:
            result["error"] = after["error"]
            return result
        result["measurement_after"] = after["metrics"]
        result["bodies"] = _inspect_bodies(document)
        definition = _com_value(feature, "GetDefinition")
        actual_depth = float(definition.GetDepth(True)) * 1000
        if not math.isfinite(actual_depth):
            raise RuntimeError("SOLIDWORKS returned a nonfinite cut depth")
        native_reverse = bool(_com_value(definition, "ReverseDirection"))
        actual_reverse = not native_reverse
        end = int(definition.GetEndCondition(True))
        both = bool(_com_value(definition, "BothDirections"))
        removed = before["metrics"]["volume_mm3"] - after["metrics"]["volume_mm3"]
        tolerance = max(1e-6, before["metrics"]["volume_mm3"] * 1e-12)
        passed = (
            math.isclose(actual_depth, depth_mm, rel_tol=0, abs_tol=1e-6)
            and actual_reverse == reverse
            and end == 0
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
            "absolute_depth_tolerance_mm": 1e-6,
        }
        if not passed:
            result["error"] = {
                "type": "CutVerificationFailed",
                "message": "cut definition or measured material removal did not match the requested operation",
            }
            return result
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        if selected:
            try:
                document.ClearSelection2(True)
            except Exception as exc:
                result.setdefault("warnings", []).append(
                    {"code": "selection-cleanup-failed", "message": str(exc)}
                )
