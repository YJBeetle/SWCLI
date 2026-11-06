"""Bounded revolve intent and independent cylinder geometry oracle."""

import math

TOLERANCE_MM = 1e-6


def validate_revolve_intent(expected_profile_mm, axis_mm, angle_deg):
    """Complete rectangle bounds CAS; one axis side, full turn only.

    Bounds are (min_x,min_y,max_x,max_y); axis is (x1,y1,x2,y2).
    Numeric geometry is bounded so mm tolerance remains meaningful.
    """
    for name, values in (("expected_profile_mm", expected_profile_mm), ("axis_mm", axis_mm)):
        if not isinstance(values, (list, tuple)) or len(values) != 4:
            raise ValueError(name + " requires four coordinates")
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e6 for v in values):
            raise ValueError(name + " requires finite coordinates within +/-1e6 mm")
    if type(angle_deg) not in (int, float) or angle_deg != 360:
        raise ValueError("the first revolve slice requires explicit angle_deg=360")
    x0, y0, x1, y1 = expected_profile_mm
    if x0 != 0 or x1 <= 2 * TOLERANCE_MM or y1 - y0 <= 2 * TOLERANCE_MM:
        raise ValueError("revolve requires a nondegenerate rectangle to the right of sketch x=0")
    if tuple(axis_mm) != (0, y0, 0, y1):
        raise ValueError("axis_mm must explicitly identify the entire left rectangle edge")
    return x1, y1 - y0, (y0 + y1) / 2


def cylinder_expectation(bounds_mm, model_to_sketch):
    radius, height, center_y = validate_revolve_intent(bounds_mm,
        (0, bounds_mm[1], 0, bounds_mm[3]), 360)
    if (not isinstance(model_to_sketch, (list, tuple)) or len(model_to_sketch) != 16
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in model_to_sketch)):
        raise ValueError("native model-to-sketch transform is unreadable")
    # SOLIDWORKS MathTransform: rotation[0:9], translation[9:12], scale[12].
    # First slice accepts only a rigid origin-plane transform, independently
    # checks orthonormality and uses its inverse for the local cylinder center.
    t = model_to_sketch
    if not math.isclose(t[12], 1, abs_tol=1e-12, rel_tol=0):
        raise ValueError("scaled sketch frames are unsupported")
    rows = [t[i:i+3] for i in (0, 3, 6)]
    for i in range(3):
        for j in range(3):
            if not math.isclose(sum(rows[i][k]*rows[j][k] for k in range(3)),
                                float(i == j), abs_tol=1e-12, rel_tol=0):
                raise ValueError("sketch frame is not orthonormal")
    if any(abs(v) > 1e-12 for v in t[9:12]):
        raise ValueError("the first revolve slice requires an origin plane")
    # Local point (0,center_y,0) transformed by the transpose rotation.
    return dict(solid_body_count=1, volume_mm3=math.pi*radius**2*height,
                surface_area_mm2=2*math.pi*radius*(radius+height),
                centroid_mm=dict(zip("xyz", (t[3*i+1]*center_y for i in range(3)))))


def verify_cylinder_metrics(actual, expected):
    if type(actual.get("solid_body_count")) is not int or actual["solid_body_count"] != 1:
        raise ValueError("revolve must produce exactly one solid")
    for key in ("volume_mm3", "surface_area_mm2"):
        value = actual[key]
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not math.isclose(value, expected[key], rel_tol=1e-8, abs_tol=1e-6)):
            raise ValueError("revolve " + key + " differs from analytic cylinder")
    for axis in "xyz":
        value = actual["centroid_mm"][axis]
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not math.isclose(value, expected["centroid_mm"][axis], rel_tol=0, abs_tol=TOLERANCE_MM)):
            raise ValueError("revolve centroid differs from analytic cylinder")
