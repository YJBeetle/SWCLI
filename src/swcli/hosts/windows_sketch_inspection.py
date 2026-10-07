"""Read-only native geometry of an exact registered 2D sketch."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from .windows import _com_value, _error

_LIST_TRAVERSAL_LIMIT = 10000


class SketchTraversalCycle(RuntimeError):
    """The native feature/subfeature traversal contains an identity cycle."""


class SketchTraversalLimitExceeded(RuntimeError):
    """The bounded native traversal cannot establish a complete sketch list."""


class SketchListLimitExceeded(RuntimeError):
    """The selected document has more 2D sketches than the caller allows."""


class SketchFeatureIdConflict(RuntimeError):
    """A supposedly document-unique ID belongs to different native features."""


def _feature_id(feature: Any) -> int:
    value = _com_value(feature, "GetID")
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -(2**31) <= value < 2**31
    ):
        raise RuntimeError("SOLIDWORKS returned an invalid native feature ID")
    return value


def _same_feature(app: Any, first: Any, second: Any) -> bool:
    status = int(app.IsSame(first, second))
    if status not in (0, 1):
        raise RuntimeError("SOLIDWORKS could not compare native feature identity")
    return status == 1


def _list_features(app: Any, document: Any):
    """Traverse model roots and absorbed subfeatures, with native identity bounds.

    A feature can legitimately appear both as a root and under its consuming
    feature. Skip those duplicate observations, but reject repetitions inside
    one sibling chain or the current ancestor path. An explicit stack avoids
    Python recursion limits on deeply nested native features. GetID is unique
    within this document; only repeated IDs require a native IsSame comparison.
    Names never serve as identity, and no cross-document/persistent handle is
    inferred from this private traversal key.
    """
    visited: Dict[int, Any] = {}
    ancestors = set()
    frames = [
        ("feature", _com_value(document, "FirstFeature"), "GetNextFeature", set())
    ]
    observations = 0
    while frames:
        event, feature, next_member, siblings = frames.pop()
        if event == "leave":
            ancestors.remove(feature)
            continue
        if feature is None:
            continue
        observations += 1
        if observations > _LIST_TRAVERSAL_LIMIT:
            raise SketchTraversalLimitExceeded(
                "feature/subfeature traversal exceeded the sketch-list safety limit"
            )
        identity = _feature_id(feature)
        previous = visited.get(identity)
        if previous is not None and not _same_feature(app, feature, previous):
            raise SketchFeatureIdConflict(
                "a native feature ID refers to different objects in this document"
            )
        if identity in siblings or identity in ancestors:
            raise SketchTraversalCycle(
                "native feature/subfeature traversal repeats an ancestor or sibling"
            )
        siblings.add(identity)
        next_feature = _com_value(feature, next_member)
        frames.append(("feature", next_feature, next_member, siblings))
        if previous is not None:
            continue
        visited[identity] = feature
        yield feature
        subfeature = _com_value(feature, "GetFirstSubFeature")
        if subfeature is not None:
            ancestors.add(identity)
            frames.append(("leave", identity, None, None))
            frames.append(("feature", subfeature, "GetNextSubFeature", set()))


def _sketch_descriptor(feature: Any, sketch: Any) -> Dict[str, Any]:
    owner = _com_value(feature, "GetOwnerFeature")
    return {
        "name": str(_com_value(feature, "Name")),
        "type": "ProfileFeature",
        "constraint_status": int(_com_value(sketch, "GetConstrainedStatus")),
        "absorbed": owner is not None,
        "owner": (
            None
            if owner is None
            else {
                "name": str(_com_value(owner, "Name")),
                "type": str(_com_value(owner, "GetTypeName2")),
            }
        ),
    }


def list_sketches_windows_with_handles(
    *, app: Any, document: Any, max_sketches: int = 1000
) -> Tuple[Dict[str, Any], List[Any]]:
    """List exact 2D sketch features without native activation or mutation.

    Includes absorbed profiles; 3D sketches and other feature types are outside
    this operation's declared 2D scope. Incomplete traversal/read failures never
    return a partial successful list or publish partial native handles.
    """
    result: Dict[str, Any] = {"ok": False, "action": "sketch.list"}
    if (
        isinstance(max_sketches, bool)
        or not isinstance(max_sketches, int)
        or max_sketches < 1
    ):
        result["error"] = {
            "type": "InvalidArgument",
            "message": "max_sketches must be a positive integer",
        }
        return result, []
    try:
        if int(_com_value(document, "GetType")) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "sketch listing currently requires a part",
            }
            return result, []
        descriptors = []
        features = []
        for feature in _list_features(app, document):
            if _com_value(feature, "GetTypeName2") != "ProfileFeature":
                continue
            if len(features) >= max_sketches:
                raise SketchListLimitExceeded(
                    f"part has more than {max_sketches} 2D sketches; increase max_sketches"
                )
            sketch = _com_value(feature, "GetSpecificFeature2")
            if sketch is None:
                raise RuntimeError("SOLIDWORKS did not return an enumerated 2D sketch")
            descriptors.append(_sketch_descriptor(feature, sketch))
            features.append(feature)
        result.update(ok=True, sketches=descriptors, count=len(features))
        return result, features
    except Exception as exc:
        result["error"] = _error(exc)
        return result, []


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
        # Complete the same bounded root/subfeature traversal used by list.
        # Stopping at the first match could hide a later cycle or COM failure
        # and would reject profiles exposed only beneath their owning feature.
        live_features = tuple(_list_features(app, document))
        feature = next(
            (f for f in live_features if _same_feature(app, f, sketch_feature)), None
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
        active = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
        unreported = [item["index"] for item in items if item["geometry"] is None]
        result.update(
            {
                "sketch": _sketch_descriptor(feature, sketch),
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
