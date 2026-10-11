import argparse
import math
from pathlib import PureWindowsPath


# Bound read-only observation groups independently of request/phase deadlines.
# The daemon lease default stays unchanged; holder writes still renew.
LEASE_TTL_SECONDS = 600
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_DEPTH_REQUEST_TIMEOUT_SECONDS = 600
MAX_REQUEST_TIMEOUT_SECONDS = 3600
CLI_TIMEOUT_GRACE_SECONDS = 15

def host_directory(value):
    path = PureWindowsPath(value)
    if "\0" in value or not path.is_absolute():
        raise argparse.ArgumentTypeError(
            "host paths must be absolute Windows/UNC paths"
        )
    return value


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def near(actual, expected, message, tolerance=0.00001):
    require(
        type(actual) in (int, float)
        and math.isfinite(actual)
        and abs(actual - expected) <= tolerance,
        message,
    )


def unchanged_depth_metrics(before, after):
    # Independent kernel reads can differ by a few floating-point ULPs even
    # without a setter/rebuild. Keep every metric guarded, not dict equality.
    require(
        type(before["solid_body_count"]) is int
        and type(after["solid_body_count"]) is int
        and before["solid_body_count"] == after["solid_body_count"],
        "equal depth changed the solid body count",
    )
    pairs = [
        (key, before[key], after[key]) for key in ("volume_mm3", "surface_area_mm2")
    ] + [
        (f"centroid_mm.{axis}", before["centroid_mm"][axis], after["centroid_mm"][axis])
        for axis in "xyz"
    ]
    for label, expected, actual in pairs:
        require(
            type(expected) in (int, float) and math.isfinite(expected),
            f"equal depth has invalid baseline {label}",
        )
        near(
            actual,
            expected,
            f"equal depth changed {label}: {expected!r} -> {actual!r}",
            max(1e-6, abs(expected) * 1e-12),
        )


def verify_fixture_edges(edges, *, depth, hole_depth):
    """Check geometry, not identity, of the existing box/blind-hole fixture.

    Native raw endpoints are checked without deriving public length, normalized
    trim or closure semantics. Opposite curve sense and traversal order are valid.
    """
    lines = [edge for edge in edges if edge["curve_kind"] == "line"]
    circles = [edge for edge in edges if edge["curve_kind"] == "circle"]
    require(len(edges) == 14 and len(lines) == 12 and len(circles) == 2,
            "depth fixture edge enumeration/classification is incomplete")
    bounds = ((-40, 60), (-5, 45), (0, depth))
    expected_pairs = []
    for axis in range(3):
        other_axes = [index for index in range(3) if index != axis]
        for first in bounds[other_axes[0]]:
            for second in bounds[other_axes[1]]:
                start, end = [0, 0, 0], [0, 0, 0]
                for point in (start, end):
                    point[other_axes[0]], point[other_axes[1]] = first, second
                start[axis], end[axis] = bounds[axis]
                expected_pairs.append((start, end, axis))

    def same_point(first, second):
        return all(abs(a - b) <= 1e-5 for a, b in zip(first, second))

    for edge in lines:
        parameters = edge["parameter_data"]
        start, end = parameters["start_point_mm"], parameters["end_point_mm"]
        matches = [index for index, (a, b, _) in enumerate(expected_pairs)
                   if (same_point(start, a) and same_point(end, b))
                   or (same_point(start, b) and same_point(end, a))]
        require(len(matches) == 1, "fixture edge endpoints are missing, duplicated or misplaced")
        _, _, axis = expected_pairs.pop(matches[0])
        line = edge["curve_geometry"]["line"]
        direction, root = line["direction"], line["root_point_mm"]
        near(abs(direction[axis]), 1, "fixture line direction tilted", 1e-9)
        for index in range(3):
            if index != axis:
                near(direction[index], 0, "fixture line direction tilted", 1e-9)
                near(root[index], start[index], "untrimmed line does not contain native endpoints")
    require(not expected_pairs, "fixture line set is incomplete")
    levels = [0, hole_depth]
    for edge in circles:
        circle = edge["curve_geometry"]["circle"]
        center, axis = circle["center_mm"], circle["axis_direction"]
        near(circle["radius_mm"], 3, "fixture circle radius changed")
        near(center[0], 10, "fixture circle center moved")
        near(center[1], 20, "fixture circle center moved")
        near(axis[0], 0, "fixture circle axis tilted", 1e-9)
        near(axis[1], 0, "fixture circle axis tilted", 1e-9)
        near(abs(axis[2]), 1, "fixture circle axis tilted", 1e-9)
        matches = [index for index, z in enumerate(levels) if abs(center[2] - z) <= 1e-5]
        require(len(matches) == 1, "fixture circle levels are missing, duplicated or misplaced")
        levels.pop(matches[0])
        for key in ("start_point_mm", "end_point_mm"):
            point = edge["parameter_data"][key]
            near(point[2], center[2], "native circle endpoint left its plane")
            near(math.hypot(point[0] - center[0], point[1] - center[1]), 3,
                 "native circle endpoint left its untrimmed curve")
    require(not levels, "fixture circle set is incomplete")
