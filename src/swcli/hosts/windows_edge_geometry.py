"""Internal raw edge parameters and untrimmed analytic curve evidence.

No endpoint/interval normalization, edge length or closed-circle claim is made.
In particular Sense=False is retained, not treated as a calibrated trim range.
Ownership and unchanged document state must be verified by the caller.
"""

from __future__ import annotations

from typing import Any, Dict

from .native_trace import native_call
from .windows import _com_value
from .windows_entity_geometry import (
    EntityGeometryUnavailable,
    _direction,
    _millimeters,
    _numbers,
)

_CURVE_TYPES = {"line": 3001, "circle": 3002}


def _read(obj: Any, member: str, interface: str) -> Any:
    return native_call(
        "entity-edge-geometry", f"{interface}.{member}",
        lambda: _com_value(obj, member),
    )


def observe_edge_geometry(edge: Any) -> Dict[str, Any]:
    """Return native parameter-space data separately from underlying geometry.

    GetCurve must precede GetCurveParams3, including unsupported curve kinds.
    Equal endpoint coordinates or absent vertices do not prove a closed edge.
    Unsupported analytic kinds stay explicitly unavailable; malformed supported
    geometry or contradictory native classifications fail the whole observation.
    """
    curve = _read(edge, "GetCurve", "IEdge")
    if curve is None:
        raise EntityGeometryUnavailable("native edge curve is absent")
    parameters = _read(edge, "GetCurveParams3", "IEdge")
    if parameters is None:
        raise EntityGeometryUnavailable("native edge curve parameters are absent")
    line = _read(curve, "IsLine", "ICurve")
    circle = _read(curve, "IsCircle", "ICurve")
    if not isinstance(line, bool) or not isinstance(circle, bool) or (line and circle):
        raise EntityGeometryUnavailable("native curve classification is unreadable")
    kind = "line" if line else "circle" if circle else "unclassified"
    curve_type = _read(parameters, "CurveType", "ICurveParamData")
    if isinstance(curve_type, bool) or not isinstance(curve_type, int) or curve_type <= 0:
        raise EntityGeometryUnavailable("native curve type is not a positive integer")
    if ((kind in _CURVE_TYPES and curve_type != _CURVE_TYPES[kind])
            or (kind == "unclassified" and curve_type in _CURVE_TYPES.values())):
        raise EntityGeometryUnavailable("native curve type disagrees with classification")
    sense = _read(parameters, "Sense", "ICurveParamData")
    if not isinstance(sense, bool):
        raise EntityGeometryUnavailable("native curve/edge sense is not a boolean")
    points = {}
    for member, key in (("StartPoint", "start_point_mm"), ("EndPoint", "end_point_mm")):
        points[key] = _millimeters(
            _numbers(_read(parameters, member, "ICurveParamData"), 3, member), member
        )
    low = _numbers((_read(parameters, "UMinValue", "ICurveParamData"),), 1, "UMinValue")[0]
    high = _numbers((_read(parameters, "UMaxValue", "ICurveParamData"),), 1, "UMaxValue")[0]
    if low >= high:
        raise EntityGeometryUnavailable("native curve parameter interval is empty or reversed")
    result: Dict[str, Any] = {
        "kind": "edge",
        "curve_kind": kind,
        "parameter_data": {
            "coordinate_system": "part-model",
            "interpretation": "native-edge-parameter-data",
            **points,
            "u_min_native": low,
            "u_max_native": high,
            "curve_and_edge_same_direction": sense,
            "curve_type": curve_type,
        },
    }
    if kind == "unclassified":
        result["curve_geometry"] = {
            "available": False, "reason": "unsupported-curve-kind"
        }
        return result
    geometry: Dict[str, Any] = {
        "available": True, "coordinate_system": "part-model", "boundary": "untrimmed-curve"
    }
    if kind == "line":
        values = _numbers(_read(curve, "LineParams", "ICurve"), 6, "LineParams")
        geometry["line"] = {
            "root_point_mm": _millimeters(values[:3], "line root point"),
            "direction": _direction(values[3:], "line direction"),
        }
    else:
        values = _numbers(_read(curve, "CircleParams", "ICurve"), 7, "CircleParams")
        radius = _millimeters(values[6:], "circle radius")[0]
        if radius <= 0:
            raise EntityGeometryUnavailable("native circle radius is not positive")
        geometry["circle"] = {
            "center_mm": _millimeters(values[:3], "circle center"),
            "axis_direction": _direction(values[3:6], "circle axis"),
            "radius_mm": radius,
        }
    result["curve_geometry"] = geometry
    return result
