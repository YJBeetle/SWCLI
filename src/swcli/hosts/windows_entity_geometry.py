"""Internal analytic surface evidence, never trimmed bounds or identity keys.

All coordinates are part-model coordinates. Native arrays and direction/sense
agreement must be proved; malformed supported geometry is not silently omitted.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from .windows import _com_value

_DIRECTION_TOLERANCE = 1e-9


class EntityGeometryUnavailable(RuntimeError):
    """A supported analytic surface's native geometry cannot be verified."""


def _numbers(value: Any, length: int, member: str) -> List[float]:
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise EntityGeometryUnavailable(f"native {member} array is incomplete")
    numbers = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise EntityGeometryUnavailable(f"native {member} is not numeric")
        try:
            number = float(item)
        except (OverflowError, ValueError) as exc:
            raise EntityGeometryUnavailable(f"native {member} overflowed") from exc
        if not math.isfinite(number):
            raise EntityGeometryUnavailable(f"native {member} is not finite")
        numbers.append(number)
    return numbers


def _direction(value: List[float], member: str) -> List[float]:
    if not math.isclose(
        math.hypot(*value), 1.0, rel_tol=0.0, abs_tol=_DIRECTION_TOLERANCE
    ):
        # Do not normalize an invalid native vector into apparently valid data.
        raise EntityGeometryUnavailable(f"native {member} is not a unit direction")
    return value


def _millimeters(value: List[float], member: str) -> List[float]:
    converted = [item * 1000.0 for item in value]
    if any(not math.isfinite(item) for item in converted):
        raise EntityGeometryUnavailable(f"native {member} conversion overflowed")
    return converted


def observe_surface_geometry(face: Any, surface: Any, kind: str) -> Dict[str, Any]:
    """Observe calibrated planes/cylinders; explicitly mark other kinds absent.

    FaceInSurfaceSense true means *opposite* surface/face normals. Cylinder
    axis orientation is not a constant face normal or an inside/outside label.
    """
    if kind not in ("plane", "cylinder"):
        return {"available": False, "reason": "unsupported-surface-kind"}
    sense = _com_value(face, "FaceInSurfaceSense")
    if not isinstance(sense, bool):
        raise EntityGeometryUnavailable("native face/surface sense is not a boolean")
    result: Dict[str, Any] = {
        "available": True,
        "coordinate_system": "part-model",
        "boundary": "untrimmed-surface",
        "face_normal_opposes_surface": sense,
    }
    if kind == "plane":
        values = _numbers(_com_value(surface, "PlaneParams"), 6, "PlaneParams")
        normal = _direction(values[:3], "plane normal")
        outward = _direction(
            _numbers(_com_value(face, "Normal"), 3, "Normal"), "face normal"
        )
        expected = [-item for item in normal] if sense else normal
        if any(
            not math.isclose(a, b, rel_tol=0.0, abs_tol=_DIRECTION_TOLERANCE)
            for a, b in zip(outward, expected)
        ):
            raise EntityGeometryUnavailable("native face normal disagrees with sense")
        result["plane"] = {
            "point_mm": _millimeters(values[3:], "plane point"),
            "surface_normal": normal,
            "outward_normal": outward,
        }
    else:
        values = _numbers(_com_value(surface, "CylinderParams"), 7, "CylinderParams")
        radius = _millimeters(values[6:], "cylinder radius")[0]
        if radius <= 0:
            raise EntityGeometryUnavailable("native cylinder radius is not positive")
        result["cylinder"] = {
            "axis_point_mm": _millimeters(values[:3], "cylinder axis point"),
            "axis_direction": _direction(values[3:6], "cylinder axis"),
            "radius_mm": radius,
        }
    return result
