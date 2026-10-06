"""Typed feature creation using exact handles on the resident COM thread."""

from __future__ import annotations

import math
from typing import Any, Dict

from .windows import _com_value, _error
from .windows_documents import _diagnose_features, _inspect_bodies
from .windows_sketches import _features

_DEPTH_TOLERANCE_MM = 1e-6


def extrude_sketch_windows(
    *,
    app: Any,
    document: Any,
    sketch_feature: Any,
    depth_mm: float,
    reverse: bool = False,
    merge: bool = True,
) -> Dict[str, Any]:
    """Create a one-direction blind solid boss; never guess an active sketch."""

    result: Dict[str, Any] = {"ok": False, "action": "feature.extrude"}
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
                "message": "solid extrusions currently require a part document",
            }
            return result
        if (
            _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
            is not None
        ):
            result["error"] = {
                "type": "SketchEditInProgress",
                "message": "finish the existing sketch edit before creating an extrusion",
            }
            return result
        # Only an unabsorbed top-level 2D sketch is currently supported. Native
        # identity detects deleted, consumed and cross-document handles before
        # changing selections. A feature name or most-recent sketch is not a fallback.
        live = next(
            (f for f in _features(document) if int(app.IsSame(f, sketch_feature)) == 1),
            None,
        )
        if (
            live is None
            or _com_value(live, "GetTypeName2") != "ProfileFeature"
            or _com_value(live, "GetOwnerFeature") is not None
        ):
            result["error"] = {
                "type": "SketchUnavailable",
                "message": "the sketch is no longer an unabsorbed 2D profile in the selected document",
            }
            return result

        document.ClearSelection2(True)
        selected = True
        if not sketch_feature.Select2(False, 0):
            result["error"] = {
                "type": "SketchSelectionFailed",
                "message": "SOLIDWORKS could not select the registered sketch",
            }
            return result
        feature = _com_value(document, "FeatureManager").FeatureExtrusion3(
            True,
            False,
            reverse,
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
            merge,
            True,
            True,
            0,
            0.0,
            False,
        )
        if feature is None:
            result["error"] = {
                "type": "ExtrusionFailed",
                "message": "SOLIDWORKS did not create the extrusion feature",
            }
            return result
        result.update(
            {
                "depth_mm": depth_mm,
                "reverse": reverse,
                "merge": merge,
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
                "message": "created extrusion did not pass rebuild diagnostics",
            }
            return result

        result["bodies"] = _inspect_bodies(document)
        definition = _com_value(feature, "GetDefinition")
        actual_depth = float(definition.GetDepth(True)) * 1000.0
        if not math.isfinite(actual_depth):
            raise RuntimeError("SOLIDWORKS returned a nonfinite extrusion depth")
        actual_reverse = bool(_com_value(definition, "ReverseDirection"))
        actual_merge = bool(_com_value(definition, "Merge"))
        end_condition = int(definition.GetEndCondition(True))
        both_directions = bool(_com_value(definition, "BothDirections"))
        solid_count = sum(
            b["type"]["name"] == "solid" for b in result["bodies"]["items"]
        )
        passed = (
            math.isclose(
                actual_depth, depth_mm, rel_tol=0.0, abs_tol=_DEPTH_TOLERANCE_MM
            )
            and actual_reverse == reverse
            and actual_merge == merge
            and end_condition == 0
            and not both_directions
            and solid_count > 0
        )
        result["geometry_verification"] = {
            "passed": passed,
            "method": "native-extrusion-definition",
            "actual_depth_mm": actual_depth,
            "actual_reverse": actual_reverse,
            "actual_merge": actual_merge,
            "end_condition": end_condition,
            "both_directions": both_directions,
            "solid_body_count": solid_count,
            "absolute_tolerance_mm": _DEPTH_TOLERANCE_MM,
        }
        if not passed:
            result["error"] = {
                "type": "ExtrusionVerificationFailed",
                "message": "native extrusion definition or solid-body evidence did not match the request",
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
