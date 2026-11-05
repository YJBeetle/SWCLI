"""Explicit document annotation scalar catalog; never application preferences."""

from math import isfinite

ARROW_STYLES = {
    "open": 0, "closed": 1, "slash": 2, "dot": 3, "origin": 4, "wide": 5,
    "iso_wide": 6, "gost": 7, "closed_top": 8, "closed_bottom": 9,
    "none": 10, "shoulder": 11, "smart": 12,
}
LEADING_ZERO_STYLES = {"standard": 1, "show": 2, "remove": 3}
TRAILING_ZERO_STYLES = {"show": 1, "remove": 2, "remove_only_on_zero": 4, "same_as_source": 5}
# IDs come from the installed official SOLIDWORKS 2025 swconst type library.
# Arrow setters are deliberately narrower than the readable enum catalog.
ANNOTATION_FIELDS = {
    "arrow.edge_vertex": {"kind": "Integer", "preference": 38, "option": 0,
                          "values": ARROW_STYLES, "writable": ("closed", "dot")},
    "arrow.face_surface": {"kind": "Integer", "preference": 39, "option": 0,
                           "values": ARROW_STYLES, "writable": ("closed", "dot")},
    "arrow.unattached": {"kind": "Integer", "preference": 40, "option": 0,
                         "values": ARROW_STYLES, "writable": ("closed", "none")},
    "bent_leader.enabled": {"kind": "Toggle", "preference": 375, "option": 0},
    "bent_leader.length_mm": {"kind": "Double", "preference": 113, "option": 0},
    "zero.leading": {"kind": "Integer", "preference": 265, "option": 100,
                     "values": LEADING_ZERO_STYLES, "writable": tuple(LEADING_ZERO_STYLES)},
    "zero.trailing": {"kind": "Integer", "preference": 15, "option": 100,
                      "values": TRAILING_ZERO_STYLES, "writable": tuple(TRAILING_ZERO_STYLES)},
}


def annotation_value_schema(field, *, writable=True):
    spec = ANNOTATION_FIELDS[field]
    if spec["kind"] == "Toggle":
        return {"type": "boolean"}
    if spec["kind"] == "Double":
        return {"type": "number", "exclusiveMinimum": 0}
    return {"type": "string", "enum": list(spec["writable"] if writable else spec["values"])}


def validate_annotation_value(field, value, *, writable=True):
    if field not in ANNOTATION_FIELDS:
        raise ValueError("unsupported document annotation field")
    spec = ANNOTATION_FIELDS[field]
    if spec["kind"] == "Toggle":
        valid = type(value) is bool
    elif spec["kind"] == "Double":
        try:
            valid = type(value) in (int, float) and isfinite(value) and value > 0
            if valid:
                valid = isfinite(value / 1000.0) and value / 1000.0 > 0
        except (OverflowError, TypeError):
            valid = False
    else:
        valid = type(value) is str and value in (spec["writable"] if writable else spec["values"])
    if not valid:
        raise ValueError(f"unsupported value for document annotation field {field}")
    return value
