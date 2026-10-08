"""Read-only exact rectangle observation for the next dimension adapter.

This is an internal primitive, not a public operation or a constraint solver.
Returned native edges belong to this observation only, not persistent handles.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Tuple

from .windows import _com_value

_TOLERANCE_MM = 1e-6
_SEGMENT_LIMIT = 64


class RectangleObservationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RectangleProfile:
    width_mm: float
    height_mm: float
    center_mm: Tuple[float, float]
    # min_x, min_y, max_x, max_y, in sketch-local coordinates.
    bounds_mm: Tuple[float, float, float, float]
    bottom_edge: Any
    left_edge: Any
    native_segment_count: int
    construction_segment_count: int
    max_abs_z_mm: float


def _unavailable(message: str) -> RectangleObservationError:
    return RectangleObservationError("DimensionObservationUnavailable", message)


def _unsupported(message: str) -> RectangleObservationError:
    return RectangleObservationError("UnsupportedDimensionProfile", message)


def _point_mm(point: Any) -> Tuple[float, float, float]:
    if point is None:
        raise _unavailable("native rectangle endpoint is unavailable")
    coordinates = []
    for axis in "XYZ":
        value = _com_value(point, axis)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _unavailable(f"native rectangle {axis} is not numeric")
        try:
            millimeters = float(value) * 1000
        except OverflowError as exc:
            raise _unavailable(f"native rectangle {axis} is invalid") from exc
        if not math.isfinite(millimeters):
            raise _unavailable(f"native rectangle {axis} is not finite")
        if math.ulp(millimeters) > _TOLERANCE_MM:
            raise _unavailable("native coordinates cannot resolve rectangle tolerance")
        coordinates.append(millimeters)
    return tuple(coordinates)


def observe_rectangle_profile(sketch: Any) -> RectangleProfile:
    """Read four unique connected axis-aligned native lines; never mutate CAD.

    A matching bounding box alone is insufficient: every endpoint must identify
    exactly one corner and the four unique sides must form the rectangle cycle.
    Native construction flags/types/numbers are not truthiness-coerced.
    """
    segments = _com_value(sketch, "GetSketchSegments")
    if not isinstance(segments, (tuple, list)):
        raise _unavailable("native sketch segment collection is unreadable")
    if len(segments) > _SEGMENT_LIMIT:
        raise _unavailable("rectangle segment observation exceeded its safety limit")
    profile = []
    construction_count = 0
    for segment in segments:
        construction = _com_value(segment, "ConstructionGeometry")
        if not isinstance(construction, bool):
            raise _unavailable("native construction flag is not a boolean")
        if construction:
            construction_count += 1
            continue
        kind = _com_value(segment, "GetType")
        if isinstance(kind, bool) or not isinstance(kind, int):
            raise _unavailable("native profile segment type is not an integer")
        if kind != 0:
            raise _unsupported("rectangle dimensions require straight profile edges")
        profile.append(segment)
    if len(profile) != 4:
        raise _unsupported("rectangle dimensions require exactly four profile edges")

    endpoints = [
        (_point_mm(_com_value(edge, "GetStartPoint2")),
         _point_mm(_com_value(edge, "GetEndPoint2")))
        for edge in profile
    ]
    points = [point for pair in endpoints for point in pair]
    max_abs_z = max(abs(point[2]) for point in points)
    if max_abs_z > _TOLERANCE_MM:
        raise _unsupported("rectangle profile is not in the sketch-local XY plane")
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    width, height = max_x - min_x, max_y - min_y
    if width <= 2 * _TOLERANCE_MM or height <= 2 * _TOLERANCE_MM:
        raise _unsupported("rectangle corners are degenerate or tolerance-ambiguous")
    corners = ((min_x, min_y), (max_x, min_y),
               (max_x, max_y), (min_x, max_y))
    sides = {}
    for edge, pair in zip(profile, endpoints):
        corner_ids = []
        for point in pair:
            matches = [
                index for index, corner in enumerate(corners)
                if all(math.isclose(point[axis], corner[axis], rel_tol=0,
                                    abs_tol=_TOLERANCE_MM) for axis in (0, 1))
            ]
            if len(matches) != 1:
                raise _unsupported("rectangle endpoint is not one unique corner")
            corner_ids.append(matches[0])
        side = tuple(sorted(corner_ids))
        if side in sides:
            raise _unsupported("rectangle has duplicate profile sides")
        sides[side] = edge
    if set(sides) != {(0, 1), (1, 2), (2, 3), (0, 3)}:
        raise _unsupported("profile sides do not form an axis-aligned rectangle")
    return RectangleProfile(
        width_mm=width, height_mm=height,
        center_mm=(min_x / 2 + max_x / 2, min_y / 2 + max_y / 2),
        bounds_mm=(min_x, min_y, max_x, max_y),
        bottom_edge=sides[(0, 1)], left_edge=sides[(0, 3)],
        native_segment_count=len(segments),
        construction_segment_count=construction_count,
        max_abs_z_mm=max_abs_z,
    )
