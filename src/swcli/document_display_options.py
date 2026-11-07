"""Exactly ten fixed document display fields for the wired operation pair.

IDs and getters have installed SOLIDWORKS 2025 read-r1 evidence. This development
batch has not completed native/public acceptance or visual validation.
"""

from math import isfinite


VIRTUAL_SHARP_STYLES = {"none": 0, "plus": 1, "star": 2, "witness": 3, "dot": 4}
_GRID_SOURCE = "https://help.solidworks.com/2025/English/api/swconst/DP_GridSnap.htm"
_SHARP_SOURCE = "https://help.solidworks.com/2025/english/api/swconst/DP_VirtualSharps.htm"
_PLANE_SOURCE = "https://help.solidworks.com/2024/english/api/swconst/DP_PlaneDisplay.htm"
DISPLAY_FIELDS = {
    "grid.display": {"symbol": "swGridDisplay", "kind": "Toggle", "preference": 57,
                     "option": 0, "document_types": (1, 2, 3), "source": _GRID_SOURCE},
    "grid.major_spacing_mm": {"symbol": "swGridMajorSpacing", "kind": "Double", "preference": 30,
                              "option": 0, "document_types": (1, 2, 3), "source": _GRID_SOURCE},
    "grid.minor_lines_per_major": {"symbol": "swGridMinorLinesPerMajor", "kind": "Integer",
                                  "preference": 42, "option": 0, "document_types": (1, 2, 3),
                                  "minimum": 1, "maximum": 2147483647, "source": _GRID_SOURCE},
    "grid.snap_points_per_minor": {"symbol": "swSnapPointsPerMinor", "kind": "Integer",
                                  "preference": 43, "option": 0, "document_types": (1, 2, 3),
                                  "minimum": 1, "maximum": 2147483647, "source": _GRID_SOURCE},
    "virtual_sharp.style": {"symbol": "swDetailingVirtualSharpStyle", "kind": "Integer",
                            "preference": 41, "option": 0, "document_types": (1, 2, 3),
                            "values": VIRTUAL_SHARP_STYLES, "source": _SHARP_SOURCE},
    "plane.front_face_color": {"symbol": "swPlaneDisplayFrontFaceColor", "kind": "Integer",
                               "preference": 145, "option": 0, "document_types": (1, 2),
                               "minimum": 0, "maximum": 16777215, "source": _PLANE_SOURCE},
    "plane.back_face_color": {"symbol": "swPlaneDisplayBackFaceColor", "kind": "Integer",
                              "preference": 146, "option": 0, "document_types": (1, 2),
                              "minimum": 0, "maximum": 16777215, "source": _PLANE_SOURCE},
    "plane.intersection_line_color": {"symbol": "swPlaneDisplayIntersectionLineColor", "kind": "Integer",
                                      "preference": 148, "option": 0, "document_types": (1, 2),
                                      "minimum": 0, "maximum": 16777215, "source": _PLANE_SOURCE},
    "plane.transparency": {"symbol": "swPlaneDisplayTransparency", "kind": "Integer",
                           "preference": 147, "option": 0, "document_types": (1, 2),
                           "minimum": 0, "maximum": 100, "source": _PLANE_SOURCE},
    "plane.show_intersections": {"symbol": "swPlaneDisplayShowIntersections", "kind": "Toggle",
                                 "preference": 138, "option": 0, "document_types": (1, 2),
                                 "source": _PLANE_SOURCE},
}


def display_fields_for_document(kind):
    if type(kind) is not int or kind not in (1, 2, 3):
        raise ValueError("document display options require a part, assembly or drawing")
    return {field: spec for field, spec in DISPLAY_FIELDS.items() if kind in spec["document_types"]}


def resolve_display_preference_ids(_preference_ids=None):
    """Resolve installed IDs or an exact private ten-symbol probe/test mapping.

    Supplying a mapping is a test/probe integration seam, not evidence that its
    numbers are official. Product callers must use independently verified IDs.
    """
    symbols = {spec["symbol"] for spec in DISPLAY_FIELDS.values()}
    resolved = ({spec["symbol"]: spec["preference"] for spec in DISPLAY_FIELDS.values()}
                if _preference_ids is None else _preference_ids)
    if type(resolved) is not dict or resolved.keys() != symbols:
        raise ValueError("document display preference IDs require the exact ten-symbol mapping")
    if any(type(value) is not int or not 0 <= value <= 2147483647 for value in resolved.values()):
        raise ValueError("document display preference IDs are unconfigured or invalid")
    seen = set()
    for spec in DISPLAY_FIELDS.values():
        native_key = (spec["kind"], resolved[spec["symbol"]], spec["option"])
        if native_key in seen:
            raise ValueError("document display preference IDs alias another field in the same API family")
        seen.add(native_key)
    return dict(resolved)


def validate_display_value(field, value, *, writable=True):
    if type(field) is not str or field not in DISPLAY_FIELDS:
        raise ValueError("unsupported document display field")
    spec = DISPLAY_FIELDS[field]
    if spec["kind"] == "Toggle":
        valid = type(value) is bool
    elif spec["kind"] == "Double":
        try:
            valid = (type(value) in (int, float) and isfinite(value) and value > 0
                     and isfinite(value / 1000.0) and value / 1000.0 > 0)
        except OverflowError:
            valid = False
    elif "values" in spec:
        valid = type(value) is str and value in spec["values"]
    else:
        minimum, maximum = ((spec["minimum"], spec["maximum"]) if writable else (-2147483648, 2147483647))
        valid = type(value) is int and minimum <= value <= maximum
    if not valid:
        raise ValueError(f"unsupported value for document display field {field}")
    return value


def display_native_value(field, value):
    validate_display_value(field, value)
    spec = DISPLAY_FIELDS[field]
    if "values" in spec:
        return spec["values"][value]
    return value / 1000.0 if spec["kind"] == "Double" else value


def display_observation(field, raw):
    spec = DISPLAY_FIELDS[field]
    if spec["kind"] == "Toggle":
        valid, value = type(raw) is bool, raw
    elif spec["kind"] == "Double":
        try:
            valid = type(raw) in (int, float) and isfinite(raw) and raw > 0
            value = raw * 1000.0 if valid else None
            valid = valid and isfinite(value)
        except OverflowError:
            valid, value = False, None
    else:
        valid = type(raw) is int and -2147483648 <= raw <= 2147483647
        value = (next((name for name, code in spec["values"].items() if code == raw), "other")
                 if "values" in spec else raw)
    if not valid:
        raise RuntimeError(f"native document display field {field} is unreadable")
    return {"value": value, "native_value": raw}
