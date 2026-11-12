"""Independent analytic STEP fixture checks; no COM or export implementation."""
import math


def require(value, message):
    if not value:
        raise RuntimeError(message)


def wire_expected_lengths(geometry):
    lengths = [10.0] * 4 + [30.0] * 4 + [40.0] * 4  # Twelve box edges.
    if geometry == "wireframe-sketches":
        # CreateCenterRectangle's verified source sketch contains four outline
        # lines and two construction diagonals: 140 + 2*hypot(40,30) = 240 mm.
        lengths += [30.0] * 2 + [40.0] * 2 + [math.hypot(40.0, 30.0)] * 2
    else:
        require(geometry == "wireframe", "unknown wireframe fixture profile")
    return sorted(lengths)


def verify_source_sketch(observation):
    require(observation["ok"] is True and observation["editing"] is False
            and observation["geometry_complete"] is True, "source sketch inspection is incomplete/editing")
    require(observation["segment_count"] == 6 and observation["profile_segment_count"] == 4
            and len(observation["segments"]) == 6, "center-rectangle fixture must have four outlines and two diagonals")
    normal, construction = [], []
    for item in observation["segments"]:
        require(type(item["construction"]) is bool and item["geometry"]["kind"] == "line",
                "source rectangle contains an unknown segment")
        points = [tuple(item["geometry"][key][axis] for axis in ("x", "y", "z"))
                  for key in ("start_mm", "end_mm")]
        require(all(math.isfinite(value) for point in points for value in point), "source sketch point is nonfinite")
        (construction if item["construction"] else normal).append(math.dist(*points))
    for values, expected in ((sorted(normal), [30.0, 30.0, 40.0, 40.0]),
                             (sorted(construction), [math.hypot(40.0, 30.0)] * 2)):
        require(len(values) == len(expected) and all(math.isclose(value, target, rel_tol=0, abs_tol=1e-9)
                for value, target in zip(values, expected)), "source rectangle/diagonal geometry differs from fixture")
    return {"normal_lengths_mm": sorted(normal), "construction_lengths_mm": sorted(construction),
            "source_total_length_mm": math.fsum(normal + construction),
            "expected_wireframe_sketch_lengths_mm": wire_expected_lengths("wireframe-sketches")}


def verify_wire_geometry(observation, geometry):
    expected = wire_expected_lengths(geometry)
    require(observation["segment_count"] == len(expected) == len(observation["lengths_mm"]),
            "wireframe/sketch exact segment count differs")
    for value, target in zip(observation["lengths_mm"], expected):
        require(math.isfinite(value) and value > 0 and math.isclose(value, target, rel_tol=0, abs_tol=1e-9),
                "wireframe/sketch exact segment length differs")
    require(math.isfinite(observation["total_length_mm"]) and
            math.isclose(observation["total_length_mm"], math.fsum(expected), rel_tol=1e-7, abs_tol=1e-5),
            "wireframe/sketch analytic length differs")
