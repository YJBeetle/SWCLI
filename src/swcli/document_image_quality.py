"""Bounded document image quality; independent of GLB/XR format options.

IDs and modes are declared in the official 2025 swconst library/SDK. Native
read/write/persistence and effects on GLB remain subject to the targeted CI gate.
No application preferences, registry changes or automatic restoration are used.
"""
from math import isclose, isfinite

SHADED_MODES = {"coarse": 1, "fine": 2, "custom": 3}
WRITABLE_SHADED_MODES = {"coarse": 1, "fine": 2}
IMAGE_QUALITY_FIELDS = {
    "shaded_mode": {"kind": "Integer", "symbol": "swImageQualityShaded", "preference": 44},
    "shaded_deviation_mm": {"kind": "Double", "symbol": "swImageQualityShadedDeviation", "preference": 32},
    "optimize_edge_length": {"kind": "Toggle", "symbol": "swImageQualityUseHighQualityEdgeSize", "preference": 210},
}
NATIVE_FIELDS = {"shaded_mode": ("Integer", 44), "shaded_deviation_m": ("Double", 32),
    "optimize_edge_length": ("Toggle", 210), "save_tessellation": ("Toggle", 255),
    "apply_to_referenced_parts": ("Toggle", 158)}
GLB_OPTIONS_STATUS = "unsupported: no verified public API mapping for XR format-specific options"


def finite_number(value, *, positive=False):
    try:
        return type(value) in (int, float) and isfinite(value) and (not positive or value > 0)
    except OverflowError:
        return False


def value_schema(field):
    if field == "shaded_mode":
        return {"type": "string", "enum": list(WRITABLE_SHADED_MODES)}
    if field == "shaded_deviation_mm":
        return {"type": "number", "exclusiveMinimum": 0}
    if field == "optimize_edge_length":
        return {"type": "boolean"}
    raise ValueError("unsupported document image quality field")


def validate_value(field, value):
    spec = value_schema(field)
    valid = (type(value) is str and value in WRITABLE_SHADED_MODES if spec["type"] == "string" else
             type(value) is bool if spec["type"] == "boolean" else
             finite_number(value, positive=True) and finite_number(value / 1000.0, positive=True))
    if not valid:
        raise ValueError("unsupported value for document image quality field " + field)
    return value


def _object(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def quality_schema():
    native = {key: {"type": "integer"} if kind == "Integer" else {"type": "number", "exclusiveMinimum": 0}
              if kind == "Double" else {"type": "boolean"} for key, (kind, _) in NATIVE_FIELDS.items()}
    return _object({"shaded_mode": {"type": "string", "enum": [*SHADED_MODES, "other"]},
        "shaded_deviation_mm": {"type": "number", "exclusiveMinimum": 0},
        "optimize_edge_length": {"type": "boolean"}, "save_tessellation": {"type": "boolean"},
        "apply_to_referenced_parts": {"type": "boolean"}, "native": _object(native),
        "deviation_range": _object({"status": {"type": "integer", "minimum": 0, "maximum": 1},
                                   "bounds_m": {"type": "array", "items": {"type": "number", "minimum": 0}, "maxItems": 2}})})


def quality_snapshot(native, deviation_range):
    if type(native) is not dict or set(native) != set(NATIVE_FIELDS):
        raise ValueError("native image quality snapshot is incomplete")
    for key, (kind, _) in NATIVE_FIELDS.items():
        value = native[key]
        valid = (type(value) is int and -2147483648 <= value <= 2147483647 if kind == "Integer" else
                 finite_number(value, positive=True) if kind == "Double" else type(value) is bool)
        if not valid:
            raise ValueError("unreadable native image quality field " + key)
    if type(deviation_range) is not dict or set(deviation_range) != {"status", "bounds_m"}:
        raise ValueError("deviation range snapshot is incomplete")
    status, bounds = deviation_range["status"], deviation_range["bounds_m"]
    if type(status) is not int or status not in (0, 1):
        raise ValueError("native image quality range status is invalid")
    if type(bounds) is not list:
        raise ValueError("native image quality range bounds must be an array")
    if status == 0:
        if len(bounds) != 2 or not (finite_number(bounds[0]) and finite_number(bounds[1]) and 0 <= bounds[0] <= bounds[1]):
            raise ValueError("native image quality range is invalid")
    elif bounds:
        raise ValueError("unavailable image quality range must use empty bounds")
    mm = native["shaded_deviation_m"] * 1000.0
    if not finite_number(mm, positive=True):
        raise ValueError("native image quality deviation cannot be represented in millimeters")
    return {"shaded_mode": next((name for name, code in SHADED_MODES.items() if code == native["shaded_mode"]), "other"),
        "shaded_deviation_mm": mm, **{key: native[key] for key in ("optimize_edge_length", "save_tessellation", "apply_to_referenced_parts")},
        "native": dict(native), "deviation_range": {"status": status, "bounds_m": list(bounds)}}


def exact_snapshot(first, second):
    """CAS uses exact numeric equality, with booleans never interchangeable."""
    if type(first) is dict and type(second) is dict:
        return first.keys() == second.keys() and all(exact_snapshot(first[key], second[key]) for key in first)
    if type(first) in (int, float) and type(second) in (int, float):
        return first == second
    return type(first) is type(second) and first == second


def validate_quality(value):
    if type(value) is not dict or set(value) != set(quality_schema()["properties"]):
        raise ValueError("expected_quality must be a complete image quality snapshot")
    expected = quality_snapshot(value["native"], value["deviation_range"])
    if not exact_snapshot(expected, value):
        raise ValueError("image quality normalized/native snapshot disagrees")
    return value


def matches(field, actual, expected):
    return (type(actual) in (int, float) and isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
            if field == "shaded_deviation_mm" else type(actual) is type(expected) and actual == expected)


def linked_changes(before, after, field):
    """Report the documented preset/deviation coupling; other fields stay exact."""
    validate_quality(before); validate_quality(after)
    allowed = {field, "native"}
    if field == "shaded_mode":
        allowed.add("shaded_deviation_mm")
    if field == "shaded_deviation_mm":
        allowed.add("shaded_mode")
        if not exact_snapshot(before, after) and after["shaded_mode"] != "custom":
            raise RuntimeError("deviation setter did not select the native custom mode")
    if any(not exact_snapshot(before[key], after[key]) for key in before if key not in allowed):
        raise RuntimeError("image quality setter changed an unrequested field")
    raw_field = "shaded_deviation_m" if field == "shaded_deviation_mm" else field
    raw_allowed = {"shaded_mode", "shaded_deviation_m"} if field in ("shaded_mode", "shaded_deviation_mm") else {raw_field}
    if any(not exact_snapshot(before["native"][key], after["native"][key]) for key in NATIVE_FIELDS if key not in raw_allowed):
        raise RuntimeError("image quality setter changed an unrequested native field")
    if field == "shaded_mode":
        return [{"field": key, "before": before[key], "after": after[key], "reason": "shaded-mode-coupling"}
                for key in ("shaded_deviation_mm",) if not exact_snapshot(before[key], after[key])]
    if field == "shaded_deviation_mm" and before["shaded_mode"] != after["shaded_mode"]:
        return [{"field": "shaded_mode", "before": before["shaded_mode"], "after": after["shaded_mode"],
                 "reason": "shaded-deviation-coupling"}]
    return []
