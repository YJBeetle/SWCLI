"""Approved tolerance-gate invariants; no native calls or state repair.

Only centroid equality has a user-authorized absolute bound of 1e-12 mm.
Body count, volume and surface area still require exact equality.
"""
from math import isfinite

CENTROID_EPSILON_MM = 1e-12


def verify_unchanged_geometry(before, after):
    if any(before[key] != after[key] for key in ("solid_body_count", "volume_mm3", "surface_area_mm2")):
        raise RuntimeError("document defaults changed exact body count, volume or surface area")
    for axis, expected in (("x", 0), ("y", 0), ("z", 5)):
        first, second = before["centroid_mm"][axis], after["centroid_mm"][axis]
        if (not isfinite(first) or not isfinite(second)
                or abs(first - second) > CENTROID_EPSILON_MM
                or abs(first - expected) > CENTROID_EPSILON_MM
                or abs(second - expected) > CENTROID_EPSILON_MM):
            raise RuntimeError("centroid differs from unchanged/analytic box expectation beyond 1e-12 mm")
