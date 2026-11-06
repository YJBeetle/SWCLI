"""Closed catalog of document font defaults; no caller-supplied COM names."""

from .font_snapshot import FONT_MEMBERS, validate_font_snapshot, validate_font_value

FONT_SCOPES = {
    "dimensions": ("swDetailingDimensionTextFormat", "swDetailingDimension"),
    "notes": ("swDetailingNoteTextFormat", "swDetailingNoOptionSpecified"),
    "tables": ("swDetailingTableTextFormat", "swDetailingNoOptionSpecified"),
    "annotations": ("swDetailingAnnotationTextFormat", "swDetailingNoOptionSpecified"),
}
WRITABLE_FONT_SCOPES = ("dimensions", "notes", "tables")


def validate_font_scopes(snapshot):
    if type(snapshot) is not dict or snapshot.keys() != FONT_SCOPES.keys():
        raise ValueError("expected_fonts must contain all four complete scope snapshots")
    for font in snapshot.values():
        validate_font_snapshot(font)
    return snapshot


def validate_font_edit(scope, field, value, expected_fonts):
    if type(scope) is not str or scope not in WRITABLE_FONT_SCOPES:
        raise ValueError("unsupported document font scope")
    validate_font_value(field, value)
    validate_font_scopes(expected_fonts)


def font_schema():
    booleans = {"bold", "italic", "underline", "strikeout", "backwards", "upside_down", "vertical"}
    props = {field: ({"type": "boolean"} if field in booleans else
                    {"type": "string"} if field == "typeface" else
                    {"type": "string", "enum": ["millimeters", "points"]} if field == "height_mode" else
                    {"type": "integer", "minimum": 0, "maximum": 2147483647} if field == "height_points" else
                    {"type": "number"}) for field in FONT_MEMBERS}
    props["height_mm"]["exclusiveMinimum"] = 0
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": list(props),
            "allOf": [{"if": {"properties": {"height_mode": {"const": "points"}}},
                       "then": {"properties": {"height_points": {"minimum": 1}}}}]}


def font_scopes_schema():
    return {"type": "object", "additionalProperties": False,
            "properties": {scope: font_schema() for scope in FONT_SCOPES}, "required": list(FONT_SCOPES)}


def font_value_schema(field):
    if field == "typeface":
        return {"type": "string", "minLength": 1, "pattern": r"^[^\s\x00-\x1f\x7f](?:[^\x00-\x1f\x7f]*[^\s\x00-\x1f\x7f])?$"}
    if field == "height_mm":
        return {"type": "number", "exclusiveMinimum": 0}
    if field == "height_points":
        return {"type": "integer", "minimum": 1, "maximum": 2147483647}
    return {"type": "boolean"}
