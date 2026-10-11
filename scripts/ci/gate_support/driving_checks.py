import math
from pathlib import (
    PurePosixPath,
    PureWindowsPath,
)
import re

from swcli.result_schemas import validate_operation_result


# Lease guards remain independent of configured request/phase deadlines.
LEASE_TTL_SECONDS = 600
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
MAX_REQUEST_TIMEOUT_SECONDS = 3600
CLI_TIMEOUT_GRACE_SECONDS = 15
ORIGIN_FIXTURE = "rectangle-origin-bound.SLDPRT"
ORIGIN_FIXTURE_SHA256 = "0cea2c4681bb6fe98ea8aea8c72790742faf1df5b50df88b9932ca7b9f08ce98"

def host_path(directory, filename):
    # Protocol paths are deliberately in the daemon's namespace, unlike the
    # local JSON record. Do not silently convert a Linux path into a Win path.
    path_type = (
        PureWindowsPath
        if re.match(r"^[A-Za-z]:[\\/]", directory) or directory.startswith("\\\\")
        else PurePosixPath
    )
    return str(path_type(directory) / filename)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def close_enough(value, expected, message):
    require(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-6),
        message,
    )


def assert_dimension(result, dimension_id, sketch_id, value):
    dimension = result["dimension"]
    require(
        re.fullmatch(r"m-[a-z0-9]{6}", dimension["dimension_id"]) is not None,
        "dimension did not receive a short registered handle",
    )
    require(
        dimension["dimension_id"] == dimension_id
        and dimension["sketch_id"] == sketch_id
        and dimension["kind"] == "diameter"
        and dimension["unit"] == "millimeter"
        and dimension["driven_state"] == 2
        and not dimension["read_only"]
        and bool(dimension["configuration"])
        and bool(dimension["native_name"]),
        "dimension identity, units, configuration or driving state changed",
    )
    close_enough(dimension["value"], value, "native diameter value is incorrect")


def assert_circle(result, radius, *, absorbed):
    require(
        result["geometry_complete"]
        and not result["editing"]
        and result["coordinate_system"] == "sketch-local"
        and result["profile_segment_count"] == 1
        and result["segment_count"] == 1
        and result["sketch"]["absorbed"] == absorbed,
        "circle observation is incomplete or its ownership/edit state changed",
    )
    segment = result["segments"][0]
    geometry = segment["geometry"]
    require(
        not segment["construction"]
        and geometry["kind"] == "arc"
        and geometry["complete_circle"],
        "profile is not one complete non-construction circle",
    )
    close_enough(geometry["radius_mm"], radius, "circle radius did not follow diameter")
    for axis, expected in (("x", 3), ("y", 4), ("z", 0)):
        close_enough(
            geometry["center_mm"][axis],
            expected,
            "driving edit moved the circle center",
        )


def assert_measurement(result, radius):
    metrics = result["metrics"]
    require(metrics["solid_body_count"] == 1, "expected one native solid body")
    close_enough(
        metrics["volume_mm3"], math.pi * radius**2 * 10, "cylinder volume is incorrect"
    )
    close_enough(
        metrics["surface_area_mm2"],
        2 * math.pi * radius * (radius + 10),
        "cylinder surface area is incorrect",
    )


def assert_fixed_center(result, sketch_id, *, created):
    validate_operation_result("sketch.fix-center", result)
    require(
        result["sketch_id"] == sketch_id and result["created"] is created,
        "center fixing targeted a different sketch or duplicated an existing fix",
    )
    geometry = result["center"]["geometry"]
    close_enough(geometry["width_mm"], 40, "center fixing changed rectangle width")
    close_enough(geometry["height_mm"], 30, "center fixing changed rectangle height")
    for axis, value in (("x", 3), ("y", 4), ("z", 0)):
        close_enough(
            geometry["center_mm"][axis], value, "center fixing moved the center"
        )
    for actual, expected in zip(geometry["bounds_mm"], (-17, -11, 23, 19)):
        close_enough(actual, expected, "center fixing changed rectangle bounds")


def assert_linear_dimension(result, dimension_id, sketch_id, kind, width, height):
    validate_operation_result("dimension.inspect", result)
    dimension = result["dimension"]
    require(
        dimension["dimension_id"] == dimension_id
        and dimension["sketch_id"] == sketch_id
        and dimension["kind"] == kind
        and dimension["driven_state"] == 2
        and dimension["read_only"] is False
        and result["editing"] is False
        and result["equation_control"]["controlled"] is False
        and result["design_table_controlled"] is False,
        "linear dimension identity or native controls are incorrect",
    )
    close_enough(
        dimension["value"],
        width if kind == "width" else height,
        "linear native value is incorrect",
    )
    geometry = result["geometry_verification"]
    require(
        geometry["passed"] is True, "rectangle geometry disagrees with its dimension"
    )
    close_enough(geometry["actual_width_mm"], width, "rectangle width is incorrect")
    close_enough(geometry["actual_height_mm"], height, "rectangle height is incorrect")
    for axis, expected in (("x", 3), ("y", 4), ("z", 0)):
        close_enough(
            geometry["actual_center_mm"][axis],
            expected,
            "size edit moved the fixed rectangle center",
        )


def assert_discovered_diameter(result, dimension_id, sketch_id, stamp):
    assert_dimension(result, dimension_id, sketch_id, 20)
    dimension = result["dimension"]
    require(
        result["sketch_id"] == sketch_id
        and type(dimension["driven_state"]) is int
        and dimension["read_only"] is False
        and isinstance(dimension["native_name"], str)
        and bool(dimension["native_name"].strip())
        and result["editing"] is False
        and result["equation_control"] == {"controlled": False, "equation_indices": []}
        and result["equation_control"]["controlled"] is False
        and result["design_table_controlled"] is False,
        "discovered diameter ownership or native control state is incorrect",
    )
    geometry = result["geometry_verification"]
    require(
        geometry["passed"] is True
        and geometry["method"] == "sketch-local-circle"
        and geometry["complete_circle"] is True
        and geometry["segment_count"] == 1
        and geometry["profile_segment_count"] == 1,
        "discovered diameter geometry verification is incomplete or failed",
    )
    close_enough(
        geometry["actual_radius_mm"], 10, "discovered diameter radius is incorrect"
    )
    for axis, expected in (("x", 3), ("y", 4), ("z", 0)):
        close_enough(
            geometry["actual_center_mm"][axis],
            expected,
            "discovered diameter circle center changed",
        )
    observation = result["observation"]
    before, after = observation["before"], observation["after"]
    require(
        observation["unchanged"] is True
        and observation["configuration_matched"] is True
        and before == after
        and all(
            type(state["update_stamp"]) is int
            and state["update_stamp"] == stamp
            and isinstance(state["configuration"], str)
            and bool(state["configuration"].strip())
            and state["configuration"] == dimension["configuration"]
            and state["editing"] is False
            for state in (before, after)
        ),
        "diameter discovery observation changed stamp, configuration or edit state",
    )
