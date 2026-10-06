"""Explicit, self-contained sketch operations on the worker's COM thread."""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional, Tuple

from .windows import _com_value, _error

STANDARD_PLANES = {"front": 2, "top": 1, "right": 0}
_FEATURE_LIMIT = 10000
_GEOMETRY_TOLERANCE_MM = 1e-6


def _features(document: Any):
    feature = _com_value(document, "FirstFeature")
    for _ in range(_FEATURE_LIMIT):
        if feature is None:
            return
        yield feature
        feature = _com_value(feature, "GetNextFeature")
    raise RuntimeError("feature traversal exceeded the modeling safety limit")


def _standard_plane(document: Any, plane: str) -> Any:
    """Find the first origin plane with the requested world-axis normal."""

    axis = STANDARD_PLANES[plane]
    for feature in _features(document):
        if _com_value(feature, "GetTypeName2") != "RefPlane":
            continue
        reference = _com_value(feature, "GetSpecificFeature2")
        transform = _com_value(reference, "Transform")
        values = tuple(float(v) for v in _com_value(transform, "ArrayData"))
        if len(values) < 13 or not all(math.isfinite(v) for v in values):
            continue
        # SOLIDWORKS uses row vectors: the local Z basis is entries 6..8;
        # entries 9..11 are translation in meters. Do not match plane names.
        if all(abs(v) <= 1e-9 for v in values[9:12]) and all(
            math.isclose(abs(v), 1.0 if i == axis else 0.0, abs_tol=1e-9)
            for i, v in enumerate(values[6:9])
        ):
            return feature
    return None


def _sketch_feature(app: Any, document: Any, sketch: Any) -> Any:
    for feature in _features(document):
        if (
            _com_value(feature, "GetTypeName2") == "ProfileFeature"
            and int(app.IsSame(_com_value(feature, "GetSpecificFeature2"), sketch)) == 1
        ):
            return feature
    return None


def _rectangle_verification(sketch: Any, expected: Dict[str, float]) -> Dict[str, Any]:
    segments = tuple(_com_value(sketch, "GetSketchSegments") or ())
    profile = [s for s in segments if not bool(_com_value(s, "ConstructionGeometry"))]
    points = []
    lines_only = all(int(_com_value(s, "GetType")) == 0 for s in profile)
    for segment in profile:
        if not lines_only:
            break
        for member in ("GetStartPoint2", "GetEndPoint2"):
            point = _com_value(segment, member)
            points.append(
                tuple(float(_com_value(point, a)) * 1000.0 for a in ("X", "Y", "Z"))
            )
    finite = bool(points) and all(math.isfinite(v) for p in points for v in p)
    bounds = (
        {
            "min_x": min(p[0] for p in points),
            "max_x": max(p[0] for p in points),
            "min_y": min(p[1] for p in points),
            "max_y": max(p[1] for p in points),
        }
        if finite
        else None
    )
    corners = (
        (expected["min_x"], expected["min_y"]),
        (expected["max_x"], expected["min_y"]),
        (expected["max_x"], expected["max_y"]),
        (expected["min_x"], expected["max_y"]),
    )
    corner_ids = [
        next(
            (
                i
                for i, corner in enumerate(corners)
                if all(
                    math.isclose(
                        p[a], corner[a], rel_tol=0.0, abs_tol=_GEOMETRY_TOLERANCE_MM
                    )
                    for a in (0, 1)
                )
            ),
            -1,
        )
        for p in points
    ]
    edges = {tuple(sorted(corner_ids[i : i + 2])) for i in range(0, len(corner_ids), 2)}
    passed = (
        len(profile) == 4
        and lines_only
        and finite
        and edges == {(0, 1), (1, 2), (2, 3), (0, 3)}
        and all(abs(p[2]) <= _GEOMETRY_TOLERANCE_MM for p in points)
        and all(
            math.isclose(
                bounds[key], value, rel_tol=0.0, abs_tol=_GEOMETRY_TOLERANCE_MM
            )
            for key, value in expected.items()
        )
    )
    return {
        "passed": passed,
        "method": "sketch-local-line-bounds",
        "segment_count": len(segments),
        "profile_segment_count": len(profile),
        "actual_bounds_mm": bounds,
        "absolute_tolerance_mm": _GEOMETRY_TOLERANCE_MM,
    }


def _circle_verification(
    sketch: Any, radius_mm: float, center_x_mm: float, center_y_mm: float
) -> Dict[str, Any]:
    segments = tuple(_com_value(sketch, "GetSketchSegments") or ())
    profile = [s for s in segments if not bool(_com_value(s, "ConstructionGeometry"))]
    actual_radius, center, complete = None, None, False
    if len(profile) == 1 and int(_com_value(profile[0], "GetType")) == 1:
        arc = profile[0]
        complete = int(_com_value(arc, "IsCircle")) == 1
        value = float(_com_value(arc, "GetRadius")) * 1000
        actual_radius = value if math.isfinite(value) else None
        point = _com_value(arc, "GetCenterPoint2")
        coordinates = [
            float(_com_value(point, axis)) * 1000 for axis in ("X", "Y", "Z")
        ]
        if all(math.isfinite(v) for v in coordinates):
            center = dict(zip(("x", "y", "z"), coordinates))
    passed = (
        complete
        and actual_radius is not None
        and center is not None
        and math.isclose(
            actual_radius, radius_mm, rel_tol=0, abs_tol=_GEOMETRY_TOLERANCE_MM
        )
        and all(
            math.isclose(
                center[axis], expected, rel_tol=0, abs_tol=_GEOMETRY_TOLERANCE_MM
            )
            for axis, expected in (("x", center_x_mm), ("y", center_y_mm), ("z", 0))
        )
    )
    return {
        "passed": passed,
        "method": "sketch-local-circle",
        "segment_count": len(segments),
        "profile_segment_count": len(profile),
        "complete_circle": complete,
        "actual_radius_mm": actual_radius,
        "actual_center_mm": center,
        "absolute_tolerance_mm": _GEOMETRY_TOLERANCE_MM,
    }


def create_circle_sketch_windows_with_handle(
    *,
    app: Any,
    document: Any,
    plane: str,
    radius_mm: float,
    center_x_mm: float = 0.0,
    center_y_mm: float = 0.0,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Create a full circle in a fresh sketch and verify its final native geometry."""
    result: Dict[str, Any] = {"ok": False, "action": "sketch.circle"}
    if (
        plane not in STANDARD_PLANES
        or not all(math.isfinite(v) for v in (radius_mm, center_x_mm, center_y_mm))
        or radius_mm <= 0
        or not math.isfinite(2 * radius_mm)
        or radius_mm / 1000 <= 0
        or any(
            not math.isfinite(center - radius_mm)
            or not math.isfinite(center + radius_mm)
            or not (center - radius_mm) / 1000 < (center + radius_mm) / 1000
            for center in (center_x_mm, center_y_mm)
        )
    ):
        result["error"] = {
            "type": "InvalidArgument",
            "message": "circle requires a supported plane and positive finite, representable radius and center",
        }
        return result, None
    return _create_profile_sketch_windows_with_handle(
        app=app,
        document=document,
        plane=plane,
        action="sketch.circle",
        dimensions={
            "unit": "millimeter",
            "radius": radius_mm,
            "center_x": center_x_mm,
            "center_y": center_y_mm,
        },
        create_segments=lambda manager: manager.CreateCircleByRadius(
            center_x_mm / 1000, center_y_mm / 1000, 0, radius_mm / 1000
        ),
        verify_sketch=lambda sketch: _circle_verification(
            sketch, radius_mm, center_x_mm, center_y_mm
        ),
    )


def create_rectangle_sketch_windows_with_handle(
    *,
    app: Any,
    document: Any,
    plane: str,
    width_mm: float,
    height_mm: float,
    center_x_mm: float = 0.0,
    center_y_mm: float = 0.0,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Create and close a fresh rectangle sketch; never leave implicit edit state."""

    result: Dict[str, Any] = {"ok": False, "action": "sketch.rectangle"}
    if (
        plane not in STANDARD_PLANES
        or not all(
            math.isfinite(v) for v in (width_mm, height_mm, center_x_mm, center_y_mm)
        )
        or width_mm <= 0
        or height_mm <= 0
    ):
        result["error"] = {
            "type": "InvalidArgument",
            "message": "rectangle requires a supported plane, positive finite size and finite center",
        }
        return result, None
    expected = {
        "min_x": center_x_mm - width_mm / 2,
        "max_x": center_x_mm + width_mm / 2,
        "min_y": center_y_mm - height_mm / 2,
        "max_y": center_y_mm + height_mm / 2,
    }
    if not all(math.isfinite(v) for v in expected.values()) or not (
        expected["min_x"] / 1000 < expected["max_x"] / 1000
        and expected["min_y"] / 1000 < expected["max_y"] / 1000
    ):
        result["error"] = {
            "type": "InvalidArgument",
            "message": "rectangle coordinates exceed representable modeling precision",
        }
        return result, None

    return _create_profile_sketch_windows_with_handle(
        app=app,
        document=document,
        plane=plane,
        action="sketch.rectangle",
        dimensions={
            "unit": "millimeter",
            "width": width_mm,
            "height": height_mm,
            "center_x": center_x_mm,
            "center_y": center_y_mm,
        },
        create_segments=lambda manager: manager.CreateCenterRectangle(
            center_x_mm / 1000,
            center_y_mm / 1000,
            0.0,
            expected["max_x"] / 1000,
            expected["max_y"] / 1000,
            0.0,
        ),
        verify_sketch=lambda sketch: _rectangle_verification(sketch, expected),
    )


def _create_profile_sketch_windows_with_handle(
    *,
    app: Any,
    document: Any,
    plane: str,
    action: str,
    dimensions: Dict[str, Any],
    create_segments: Callable[[Any], Any],
    verify_sketch: Callable[[Any], Dict[str, Any]],
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Own the fresh sketch edit lifecycle and return its exact feature handle."""
    result: Dict[str, Any] = {"ok": False, "action": action}
    feature = None
    manager = None
    entered = False
    try:
        if int(_com_value(document, "GetType")) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "profile sketches currently require a part document",
            }
            return result, None
        manager = _com_value(document, "SketchManager")
        if _com_value(manager, "ActiveSketch") is not None:
            result["error"] = {
                "type": "SketchEditInProgress",
                "message": "finish the existing sketch edit before creating a new sketch",
            }
            return result, None
        reference = _standard_plane(document, plane)
        if reference is None:
            result["error"] = {
                "type": "StandardPlaneUnavailable",
                "message": f"no origin plane aligned with '{plane}' was found",
            }
            return result, None
        document.ClearSelection2(True)
        if not reference.Select2(False, 0):
            result["error"] = {
                "type": "PlaneSelectionFailed",
                "message": "SOLIDWORKS could not select the requested plane",
            }
            return result, None
        entered = True
        manager.InsertSketch(True)
        sketch = _com_value(manager, "ActiveSketch")
        if sketch is None:
            raise RuntimeError("SOLIDWORKS did not enter a new sketch")
        feature = _sketch_feature(app, document, sketch)
        if feature is None:
            raise RuntimeError(
                "the new sketch could not be identified by native object identity"
            )
        transform = _com_value(sketch, "ModelToSketchTransform")
        transform_values = [float(v) for v in _com_value(transform, "ArrayData")]
        if len(transform_values) != 16 or not all(
            math.isfinite(v) for v in transform_values
        ):
            raise RuntimeError(
                "SOLIDWORKS returned an invalid sketch coordinate transform"
            )
        segments = create_segments(manager)
        if not segments:
            result["error"] = {
                "type": "SketchCreationFailed",
                "message": "SOLIDWORKS did not create profile segments",
            }
            return result, feature
        result["plane"] = plane
        result["coordinate_system"] = "sketch-local"
        result["model_to_sketch_transform"] = transform_values
        result["dimensions"] = dimensions
        result["sketch"] = {
            "name": str(_com_value(feature, "Name")),
            "type": "ProfileFeature",
            "constraint_status": int(_com_value(sketch, "GetConstrainedStatus")),
            "dimensions_created": False,
        }
        manager.InsertSketch(True)
        if _com_value(manager, "ActiveSketch") is not None:
            raise RuntimeError("SOLIDWORKS did not exit sketch editing")
        entered = False
        document.ClearSelection2(True)
        result["editing"] = False
        # Closing a sketch can trigger solving: verify the final native geometry,
        # not just the arguments or segments returned by the creation API.
        result["sketch"]["constraint_status"] = int(
            _com_value(sketch, "GetConstrainedStatus")
        )
        result["geometry_verification"] = verify_sketch(sketch)
        if not result["geometry_verification"]["passed"]:
            result["error"] = {
                "type": "SketchVerificationFailed",
                "message": "created profile did not match the requested local coordinates",
            }
            return result, feature
        result["ok"] = True
        return result, feature
    except Exception as exc:
        result["error"] = _error(exc)
        return result, feature
    finally:
        if entered and manager is not None:
            try:
                result["editing"] = _com_value(manager, "ActiveSketch") is not None
                if result["editing"]:
                    manager.InsertSketch(True)
                result["editing"] = _com_value(manager, "ActiveSketch") is not None
                if result["editing"]:
                    raise RuntimeError("sketch editing remained active after cleanup")
                document.ClearSelection2(True)
                result["editing"] = False
            except Exception as exc:
                result.setdefault("warnings", []).append(
                    {
                        "code": "sketch-cleanup-failed",
                        "message": str(exc),
                    }
                )
