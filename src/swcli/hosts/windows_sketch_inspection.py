"""Read-only native geometry of an exact registered 2D sketch."""

from __future__ import annotations

import math
from typing import Any, Dict

from .windows import _com_value, _error
from .windows_sketches import _features


def _point_mm(point: Any) -> Dict[str, float]:
    values = {axis.lower(): float(_com_value(point, axis)) * 1000 for axis in "XYZ"}
    if not all(math.isfinite(value) for value in values.values()):
        raise RuntimeError("SOLIDWORKS returned nonfinite sketch coordinates")
    return values


def _segment(segment: Any, index: int) -> Dict[str, Any]:
    kind = int(_com_value(segment, "GetType"))
    item: Dict[str, Any] = {
        "index": index,
        "type_code": kind,
        "construction": bool(_com_value(segment, "ConstructionGeometry")),
        "geometry": None,
    }
    if kind == 0:
        item["geometry"] = {
            "kind": "line",
            "start_mm": _point_mm(_com_value(segment, "GetStartPoint2")),
            "end_mm": _point_mm(_com_value(segment, "GetEndPoint2")),
        }
    elif kind == 1:
        radius = float(_com_value(segment, "GetRadius")) * 1000
        if not math.isfinite(radius) or radius <= 0:
            raise RuntimeError("SOLIDWORKS returned an invalid sketch arc radius")
        item["geometry"] = {
            "kind": "arc",
            "complete_circle": int(_com_value(segment, "IsCircle")) == 1,
            "radius_mm": radius,
            "center_mm": _point_mm(_com_value(segment, "GetCenterPoint2")),
        }
        if not item["geometry"]["complete_circle"]:
            item["geometry"].update(
                start_mm=_point_mm(_com_value(segment, "GetStartPoint2")),
                end_mm=_point_mm(_com_value(segment, "GetEndPoint2")),
            )
    return item


def inspect_sketch_windows(
    *, app: Any, document: Any, sketch_feature: Any, max_segments: int = 1000
) -> Dict[str, Any]:
    """Observe without selection, activation, rebuild or entering sketch edit."""
    result: Dict[str, Any] = {"ok": False, "action": "sketch.inspect"}
    if (
        isinstance(max_segments, bool)
        or not isinstance(max_segments, int)
        or max_segments < 1
    ):
        result["error"] = {
            "type": "InvalidArgument",
            "message": "max_segments must be a positive integer",
        }
        return result
    try:
        if int(_com_value(document, "GetType")) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "sketch inspection currently requires a part",
            }
            return result
        feature = next(
            (f for f in _features(document) if int(app.IsSame(f, sketch_feature)) == 1),
            None,
        )
        if feature is None or _com_value(feature, "GetTypeName2") != "ProfileFeature":
            result["error"] = {
                "type": "SketchUnavailable",
                "message": "registered sketch is no longer a 2D profile in the selected document",
            }
            return result
        sketch = _com_value(feature, "GetSpecificFeature2")
        if sketch is None:
            raise RuntimeError("SOLIDWORKS did not return the registered sketch")
        segments = tuple(_com_value(sketch, "GetSketchSegments") or ())
        if len(segments) > max_segments:
            result["error"] = {
                "type": "SketchInspectionLimitExceeded",
                "message": f"sketch has {len(segments)} segments; limit is {max_segments}",
            }
            return result
        items = [_segment(segment, index) for index, segment in enumerate(segments)]
        transform = [
            float(v)
            for v in _com_value(
                _com_value(sketch, "ModelToSketchTransform"), "ArrayData"
            )
        ]
        if len(transform) != 16 or not all(math.isfinite(v) for v in transform):
            raise RuntimeError(
                "SOLIDWORKS returned an invalid sketch coordinate transform"
            )
        owner = _com_value(feature, "GetOwnerFeature")
        active = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
        unreported = [item["index"] for item in items if item["geometry"] is None]
        result.update(
            {
                "sketch": {
                    "name": str(_com_value(feature, "Name")),
                    "type": "ProfileFeature",
                    "constraint_status": int(
                        _com_value(sketch, "GetConstrainedStatus")
                    ),
                    "absorbed": owner is not None,
                    "owner": (
                        None
                        if owner is None
                        else {
                            "name": str(_com_value(owner, "Name")),
                            "type": str(_com_value(owner, "GetTypeName2")),
                        }
                    ),
                },
                "editing": active is not None and int(app.IsSame(active, sketch)) == 1,
                "coordinate_system": "sketch-local",
                "unit": "millimeter",
                "model_to_sketch_transform": transform,
                "segments": items,
                "segment_count": len(items),
                "profile_segment_count": sum(
                    not item["construction"] for item in items
                ),
                "geometry_complete": not unreported,
            }
        )
        if unreported:
            result["warnings"] = [
                {
                    "code": "sketch-geometry-not-reported",
                    "message": f"only line/arc geometry is decoded; segments {unreported} have type metadata only",
                }
            ]
        result["ok"] = True
    except Exception as exc:
        result["error"] = _error(exc)
    return result
