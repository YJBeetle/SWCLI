"""Explicit, self-contained sketch operations on the worker's COM thread."""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional, Tuple

from .windows import _com_value, _error
from .native_trace import native_call
from .com_errors import com_hresult

STANDARD_PLANES = {"front": 2, "top": 1, "right": 0}
_FEATURE_LIMIT = 10000
_GEOMETRY_TOLERANCE_MM = 1e-6
_SKETCH_INFERENCE = 249  # swUserPreferenceToggle_e.swSketchInference (SW 2025)


def _observe(value: Any, member: str, context: Optional[Dict[str, str]]) -> Any:
    if context is not None:
        context["call"] = member
    return _com_value(value, member)


def _mark(context: Optional[Dict[str, str]], stage: str, call: str) -> None:
    if context is not None:
        context.update(stage=stage, call=call)


def _com_failure_warning(exc: Exception, context: Dict[str, str]) -> Dict[str, Any]:
    """Add evidence without rewriting the exception or its primary error."""
    native_error = _error(exc)
    hresult = com_hresult(exc)
    if hresult is not None:
        native_error["hresult"] = hresult if hresult < 2**31 else hresult - 2**32
        native_error["hresult_hex"] = f"0x{hresult:08X}"
    return {
        "code": "sketch-com-call-failed",
        "message": f"native sketch.circle failed during {context['stage']} ({context['call']})",
        **context,
        "native_error": native_error,
    }


def _features(document: Any, context: Optional[Dict[str, str]] = None):
    feature = _observe(document, "FirstFeature", context)
    for _ in range(_FEATURE_LIMIT):
        if feature is None:
            return
        yield feature
        feature = _observe(feature, "GetNextFeature", context)
    raise RuntimeError("feature traversal exceeded the modeling safety limit")


def _standard_plane(
    document: Any, plane: str, context: Optional[Dict[str, str]] = None
) -> Any:
    """Find the first origin plane with the requested world-axis normal."""

    axis = STANDARD_PLANES[plane]
    for feature in _features(document, context):
        if _observe(feature, "GetTypeName2", context) != "RefPlane":
            continue
        reference = _observe(feature, "GetSpecificFeature2", context)
        transform = _observe(reference, "Transform", context)
        values = tuple(float(v) for v in _observe(transform, "ArrayData", context))
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


def _unabsorbed_profile(app: Any, document: Any, sketch_feature: Any) -> Optional[Any]:
    """Resolve exact native identity and reject consumed/cross-document sketches."""
    feature = next(
        (f for f in _features(document) if int(app.IsSame(f, sketch_feature)) == 1),
        None,
    )
    if (
        feature is None
        or _com_value(feature, "GetTypeName2") != "ProfileFeature"
        or _com_value(feature, "GetOwnerFeature") is not None
    ):
        return None
    return feature


def _sketch_feature(
    app: Any, document: Any, sketch: Any, context: Optional[Dict[str, str]] = None
) -> Any:
    for feature in _features(document, context):
        if _observe(feature, "GetTypeName2", context) != "ProfileFeature":
            continue
        native = _observe(feature, "GetSpecificFeature2", context)
        if context is not None:
            context["call"] = "IsSame"
        if int(native_call(
            "exact-feature", "SldWorks.IsSame", lambda: app.IsSame(native, sketch)
        )) == 1:
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
    sketch: Any, radius_mm: float, center_x_mm: float, center_y_mm: float,
    context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    segments = tuple(_observe(sketch, "GetSketchSegments", context) or ())
    profile = [s for s in segments if not bool(_observe(s, "ConstructionGeometry", context))]
    actual_radius, center, complete = None, None, False
    if len(profile) == 1 and int(_observe(profile[0], "GetType", context)) == 1:
        arc = profile[0]
        complete = int(_observe(arc, "IsCircle", context)) == 1
        value = float(_observe(arc, "GetRadius", context)) * 1000
        actual_radius = value if math.isfinite(value) else None
        point = _observe(arc, "GetCenterPoint2", context)
        coordinates = [
            float(_observe(point, axis, context)) * 1000 for axis in ("X", "Y", "Z")
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
    state_warnings = []
    failure_context = {}
    result, feature = _create_profile_sketch_windows_with_handle(
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
        create_segments=lambda manager: _create_circle_without_inference(
            manager,
            center_x_mm / 1000,
            center_y_mm / 1000,
            radius_mm / 1000,
            state_warnings,
            failure_context,
        ),
        verify_sketch=lambda sketch: _circle_verification(
            sketch, radius_mm, center_x_mm, center_y_mm, failure_context
        ),
        failure_context=failure_context,
    )
    if state_warnings:
        result.setdefault("warnings", []).extend(state_warnings)
        if result["ok"]:
            result["ok"] = False
            result["error"] = {
                "type": "SketchStateRestoreFailed",
                "message": "circle geometry was created but the original sketch creation mode could not be restored",
            }
    return result, feature


def _create_circle_without_inference(
    manager: Any, x: float, y: float, radius: float, state_warnings: list,
    context: Optional[Dict[str, str]] = None,
) -> Any:
    return _create_without_inference(
        manager,
        lambda: manager.CreateCircleByRadius(x, y, 0, radius),
        state_warnings,
        context,
        native_method="CreateCircleByRadius",
        shape="circle",
    )


def _create_without_inference(
    manager: Any, create: Callable[[], Any], state_warnings: list,
    context: Optional[Dict[str, str]] = None, *, native_method: str, shape: str,
) -> Any:
    """Create exact API geometry rather than letting UI snapping redefine it."""

    # CreateCircleByRadius otherwise participates in UI inferencing, automatic
    # relations and grid/entity snapping. AddToDB is the documented escape from
    # these side effects. Composite rectangle creation additionally needs the
    # scoped application inference guard below; AddToDB alone is insufficient.
    def read_mode(*, observing=True):
        value = _observe(manager, "AddToDB", context if observing else None)
        if not isinstance(value, bool):
            raise RuntimeError("SOLIDWORKS returned an invalid AddToDB mode")
        return value

    original = read_mode()
    try:
        if context is not None:
            context["call"] = "AddToDB.set(True)"
        manager.AddToDB = True
        if not read_mode():
            raise RuntimeError(f"SOLIDWORKS could not enable direct {shape} creation")
        if context is not None:
            context["call"] = native_method
        return create()
    finally:
        try:
            manager.AddToDB = original
            if read_mode(observing=False) != original:
                raise RuntimeError(
                    "SOLIDWORKS did not restore the original AddToDB mode"
                )
        except Exception as exc:
            state_warnings.append(
                {"code": "sketch-creation-mode-restore-failed", "message": str(exc)}
            )


def _create_rectangle_without_inference(
    app: Any, manager: Any, create: Callable[[], Any], state_warnings: list,
) -> Any:
    """The native rectangle tool still snaps its center with AddToDB enabled."""

    def read_inference():
        value = native_call(
            "rectangle-inference", "SldWorks.GetUserPreferenceToggle(swSketchInference)",
            lambda: app.GetUserPreferenceToggle(_SKETCH_INFERENCE),
        )
        if not isinstance(value, bool):
            raise RuntimeError("SOLIDWORKS returned an invalid sketch inference mode")
        return value

    def set_inference(value):
        native_call(
            "rectangle-inference", "SldWorks.SetUserPreferenceToggle(swSketchInference)",
            lambda: app.SetUserPreferenceToggle(_SKETCH_INFERENCE, value),
        )

    original = read_inference()
    try:
        set_inference(False)
        if read_inference():
            raise RuntimeError("SOLIDWORKS could not disable rectangle inference")
        return _create_without_inference(
            manager, create, state_warnings,
            native_method="CreateCenterRectangle", shape="rectangle",
        )
    finally:
        try:
            set_inference(original)
            if read_inference() != original:
                raise RuntimeError("SOLIDWORKS did not restore sketch inference mode")
        except Exception as exc:
            state_warnings.append(
                {"code": "sketch-inference-restore-failed", "message": str(exc)}
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

    state_warnings = []
    result, feature = _create_profile_sketch_windows_with_handle(
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
        create_segments=lambda manager: _create_rectangle_without_inference(
            app, manager,
            lambda: native_call(
                "create", "SketchManager.CreateCenterRectangle",
                lambda: manager.CreateCenterRectangle(
                    center_x_mm / 1000, center_y_mm / 1000, 0.0,
                    expected["max_x"] / 1000, expected["max_y"] / 1000, 0.0,
                ),
            ),
            state_warnings,
        ),
        verify_sketch=lambda sketch: _rectangle_verification(sketch, expected),
    )
    if state_warnings:
        result.setdefault("warnings", []).extend(state_warnings)
        if result["ok"]:
            result["ok"] = False
            result["error"] = {
                "type": "SketchStateRestoreFailed",
                "message": "rectangle geometry was created but the original sketch creation mode could not be restored",
            }
    return result, feature


def _create_profile_sketch_windows_with_handle(
    *,
    app: Any,
    document: Any,
    plane: str,
    action: str,
    dimensions: Dict[str, Any],
    create_segments: Callable[[Any], Any],
    verify_sketch: Callable[[Any], Dict[str, Any]],
    failure_context: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Own the fresh sketch edit lifecycle and return its exact feature handle."""
    result: Dict[str, Any] = {"ok": False, "action": action}
    feature = None
    manager = None
    entered = False
    try:
        _mark(failure_context, "document-preflight", "GetType")
        if int(_observe(document, "GetType", failure_context)) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "profile sketches currently require a part document",
            }
            return result, None
        _mark(failure_context, "existing-edit-check", "SketchManager")
        manager = _observe(document, "SketchManager", failure_context)
        if _observe(manager, "ActiveSketch", failure_context) is not None:
            result["error"] = {
                "type": "SketchEditInProgress",
                "message": "finish the existing sketch edit before creating a new sketch",
            }
            return result, None
        _mark(failure_context, "plane-resolve", "_standard_plane")
        reference = _standard_plane(document, plane, failure_context)
        if reference is None:
            result["error"] = {
                "type": "StandardPlaneUnavailable",
                "message": f"no origin plane aligned with '{plane}' was found",
            }
            return result, None
        _mark(failure_context, "plane-select", "ClearSelection2")
        native_call(
            "plane-select", "ClearSelection2", lambda: document.ClearSelection2(True)
        )
        _mark(failure_context, "plane-select", "Select2")
        if not native_call("plane-select", "Select2", lambda: reference.Select2(False, 0)):
            result["error"] = {
                "type": "PlaneSelectionFailed",
                "message": "SOLIDWORKS could not select the requested plane",
            }
            return result, None
        entered = True
        _mark(failure_context, "sketch-enter", "InsertSketch")
        native_call(
            "sketch-enter", "SketchManager.InsertSketch", lambda: manager.InsertSketch(True)
        )
        sketch = _observe(manager, "ActiveSketch", failure_context)
        if sketch is None:
            raise RuntimeError("SOLIDWORKS did not enter a new sketch")
        _mark(failure_context, "exact-feature", "_sketch_feature")
        feature = _sketch_feature(app, document, sketch, failure_context)
        if feature is None:
            raise RuntimeError(
                "the new sketch could not be identified by native object identity"
            )
        _mark(failure_context, "transform", "ModelToSketchTransform")
        transform = _observe(sketch, "ModelToSketchTransform", failure_context)
        transform_values = [float(v) for v in _observe(transform, "ArrayData", failure_context)]
        if len(transform_values) != 16 or not all(
            math.isfinite(v) for v in transform_values
        ):
            raise RuntimeError(
                "SOLIDWORKS returned an invalid sketch coordinate transform"
            )
        _mark(failure_context, "create", "create_segments")
        segments = native_call("create", "create_segments", lambda: create_segments(manager))
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
        _mark(failure_context, "exact-feature", "Name")
        result["sketch"] = {
            "name": str(_observe(feature, "Name", failure_context)),
            "type": "ProfileFeature",
            "constraint_status": int(_observe(sketch, "GetConstrainedStatus", failure_context)),
            "dimensions_created": False,
        }
        _mark(failure_context, "close", "InsertSketch")
        native_call(
            "sketch-close", "SketchManager.InsertSketch", lambda: manager.InsertSketch(True)
        )
        if _observe(manager, "ActiveSketch", failure_context) is not None:
            raise RuntimeError("SOLIDWORKS did not exit sketch editing")
        entered = False
        _mark(failure_context, "close", "ClearSelection2")
        native_call(
            "sketch-close", "ClearSelection2", lambda: document.ClearSelection2(True)
        )
        result["editing"] = False
        # Closing a sketch can trigger solving: verify the final native geometry,
        # not just the arguments or segments returned by the creation API.
        _mark(failure_context, "verify", "GetConstrainedStatus")
        result["sketch"]["constraint_status"] = int(
            _observe(sketch, "GetConstrainedStatus", failure_context)
        )
        result["geometry_verification"] = native_call(
            "verify", "profile-geometry", lambda: verify_sketch(sketch)
        )
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
        if failure_context is not None and com_hresult(exc) is not None:
            result.setdefault("warnings", []).append(
                _com_failure_warning(exc, failure_context)
            )
        return result, feature
    finally:
        if entered and manager is not None:
            try:
                result["editing"] = _com_value(manager, "ActiveSketch") is not None
                if result["editing"]:
                    native_call(
                        "cleanup", "SketchManager.InsertSketch", lambda: manager.InsertSketch(True)
                    )
                result["editing"] = _com_value(manager, "ActiveSketch") is not None
                if result["editing"]:
                    raise RuntimeError("sketch editing remained active after cleanup")
                native_call("cleanup", "ClearSelection2", lambda: document.ClearSelection2(True))
                result["editing"] = False
            except Exception as exc:
                result.setdefault("warnings", []).append(
                    {
                        "code": "sketch-cleanup-failed",
                        "message": str(exc),
                    }
                )
