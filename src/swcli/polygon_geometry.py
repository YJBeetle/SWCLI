"""Pure simple-polygon eligibility and independent analytic measurements.

No CAD imports or repairs: preserve the supplied cycle and reject ambiguity.
Coordinates and the observation tolerance are in sketch-local millimeters.
"""

from dataclasses import dataclass
import math
from typing import Tuple


TOLERANCE_MM = 1e-6
MAX_VERTICES = 64


@dataclass(frozen=True)
class PolygonGeometry:
    vertices_mm: Tuple[Tuple[float, float], ...]
    signed_area_mm2: float
    perimeter_mm: float
    centroid_mm: Tuple[float, float]


def _distance(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _cross(a, b, c):
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if not math.isfinite(value):
        raise ValueError("polygon arithmetic is not representable")
    return value


def _point_segment_distance(p, a, b):
    length = _distance(a, b)
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    projection = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
    if projection < 0:
        return _distance(p, a)
    if projection > length:
        return _distance(p, b)
    return abs(_cross(a, b, p)) / length


def validate_polygon(vertices_mm):
    """Accept 3–64 distinct ordered {x,y} objects, with implicit closure.

    Both windings and concavity are supported. No duplicate closing point,
    redundant collinear corner, touching or tolerance-ambiguous contour passes.
    The returned area/perimeter/centroid are analytic, not a CAD measurement.
    """
    if not isinstance(vertices_mm, (list, tuple)) or not 3 <= len(vertices_mm) <= MAX_VERTICES:
        raise ValueError("polygon requires 3 to 64 vertices")
    points = []
    for vertex in vertices_mm:
        if not isinstance(vertex, dict) or set(vertex) != {"x", "y"}:
            raise ValueError("each polygon vertex requires exactly x and y")
        point = []
        for axis in ("x", "y"):
            raw = vertex[axis]
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError("polygon coordinates must be finite numbers")
            try:
                value = float(raw)
            except (OverflowError, ValueError) as exc:
                raise ValueError("polygon coordinate is not representable") from exc
            if (not math.isfinite(value)
                    or math.ulp(value) > TOLERANCE_MM
                    or math.ulp(value / 1000) * 1000 > TOLERANCE_MM):
                raise ValueError("polygon coordinate cannot resolve the observation tolerance")
            point.append(value)
        points.append(tuple(point))
    count = len(points)
    edges = [(points[i], points[(i + 1) % count]) for i in range(count)]
    for i, p in enumerate(points):
        for q in points[i + 1:]:
            if _distance(p, q) <= 2 * TOLERANCE_MM:
                raise ValueError("polygon vertices are duplicate or tolerance-ambiguous")
        before, after = points[(i - 1) % count], points[(i + 1) % count]
        if abs(_cross(before, p, after)) / _distance(before, p) <= 2 * TOLERANCE_MM:
            raise ValueError("polygon has a collinear or tolerance-ambiguous corner")
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            c, d = edges[j]
            # Proper crossings plus endpoint/edge proximity cover touching,
            # overlap and narrow gaps; never repair an invalid edge cycle.
            ab_c, ab_d = _cross(a, b, c), _cross(a, b, d)
            cd_a, cd_b = _cross(c, d, a), _cross(c, d, b)
            if ((ab_c < 0 < ab_d or ab_d < 0 < ab_c)
                    and (cd_a < 0 < cd_b or cd_b < 0 < cd_a)) or min(
                        _point_segment_distance(a, c, d), _point_segment_distance(b, c, d),
                        _point_segment_distance(c, a, b), _point_segment_distance(d, a, b),
                    ) <= 2 * TOLERANCE_MM:
                raise ValueError("polygon edges cross, touch or are tolerance-ambiguous")
    origin = points[0]
    local = [(p[0] - origin[0], p[1] - origin[1]) for p in points]
    terms = [_cross((0, 0), local[i], local[i + 1]) for i in range(1, count - 1)]
    doubled_area = math.fsum(terms)
    perimeter = math.fsum(_distance(a, b) for a, b in edges)
    if not math.isfinite(doubled_area) or abs(doubled_area) <= 2 * TOLERANCE_MM * perimeter:
        raise ValueError("polygon area is zero or tolerance-ambiguous")
    centroid = tuple(origin[axis] + math.fsum(
        (local[i][axis] + local[i + 1][axis]) * terms[i - 1]
        for i in range(1, count - 1)
    ) / (3 * doubled_area) for axis in (0, 1))
    if not all(math.isfinite(v) for v in (*centroid, perimeter)):
        raise ValueError("polygon measurements are not representable")
    return PolygonGeometry(tuple(points), doubled_area / 2, perimeter, centroid)
