"""Calibrated SW2025 standard-view fixture checks, not a general layout engine."""

import math


def require(value, message):
    if not value:
        raise RuntimeError(message)


def numbers(values, count, label):
    require(isinstance(values, (tuple, list)) and len(values) == count
            and all(type(x) in (int, float) and math.isfinite(x) for x in values),
            "invalid " + label)
    return values


def standard_layout(snapshot, projection):
    """Classify exact native matrices, not localized names or array order.

    Supports only the observed native standard frame of the generated fixture.
    A custom model view frame must fail, not be relabeled as front/top/side.
    Values are sheet meters; geometric containment excludes title-block claims.
    """
    require(projection in ("first-angle", "third-angle"), "unknown projection")
    properties = numbers(snapshot["sheet"]["properties"], 8, "sheet properties")
    require(properties[4] == (projection == "first-angle"), "projection flag mismatch")
    width, height = properties[5:7]
    require(width > 0 and height > 0, "invalid sheet size")
    expected = {
        "front": (1, 0, 0, 0, 1, 0, 0, 0, 1),
        "top": (1, 0, 0, 0, 0, 1, 0, -1, 0),
        "left" if projection == "first-angle" else "right":
            (0, 0, -1, 0, 1, 0, 1, 0, 0) if projection == "first-angle"
            else (0, 0, 1, 0, 1, 0, -1, 0, 0),
    }
    require(len(snapshot["views"]) == 3, "expected three model views")
    classified = {}
    for view in snapshot["views"]:
        transform = numbers(view["transform"], 16, "view transform")
        position = numbers(view["position"], 2, "view position")
        outline = numbers(view["outline"], 4, "view outline")
        scale = numbers(view["scale"], 2, "view scale")
        require(min(scale) > 0 and math.isclose(transform[12], scale[0] / scale[1],
                rel_tol=1e-9, abs_tol=1e-12), "transform/scale mismatch")
        roles = [role for role, matrix in expected.items()
                 if all(abs(a - b) <= 1e-9 for a, b in zip(transform[:9], matrix))]
        require(len(roles) == 1 and roles[0] not in classified, "unknown or duplicate view orientation")
        require(0 <= outline[0] < outline[2] <= width and
                0 <= outline[1] < outline[3] <= height, "view outline outside sheet")
        classified[roles[0]] = view
    front, top = classified["front"], classified["top"]
    side_role = "left" if projection == "first-angle" else "right"
    side = classified[side_role]
    require(abs(top["position"][0] - front["position"][0]) <= 1e-6 and
            abs(side["position"][1] - front["position"][1]) <= 1e-6,
            "standard views are not aligned")
    require((top["position"][1] < front["position"][1]) if projection == "first-angle"
            else (top["position"][1] > front["position"][1]), "vertical projection layout mismatch")
    require(side["position"][0] > front["position"][0], "side projection layout mismatch")
    views = list(classified.values())
    for i, first in enumerate(views):
        a = first["outline"]
        for second in views[i+1:]:
            b = second["outline"]
            require(a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1],
                    "model view outlines overlap")
    return {"passed": True, "projection": projection,
            "roles": sorted(classified), "within_sheet": True, "overlap": False}
