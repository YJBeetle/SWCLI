"""Bounded drawing document defaults; IDs are resolved from official swconst."""

LINE_FONT_FIELDS = {
    "visible_edges.style": "swLineFontVisibleEdgesStyle",
    "visible_edges.weight": "swLineFontVisibleEdgesThickness",
    "hidden_edges.style": "swLineFontHiddenEdgesStyle",
    "hidden_edges.weight": "swLineFontHiddenEdgesThickness",
}
# Style continuous/hidden; weight thin/normal. No custom size or layer sentinel.
LINE_FONT_VALUES = {field: [0, 1]
                    for field in LINE_FONT_FIELDS}
LINE_FONT_SNAPSHOT = {
    "type": "object", "properties": {field: {"type": "integer"} for field in LINE_FONT_FIELDS},
    "required": list(LINE_FONT_FIELDS), "additionalProperties": False,
}


def validate_snapshot(options):
    if (type(options) is not dict or set(options) != set(LINE_FONT_FIELDS)
            or any(type(v) is not int for v in options.values())):
        raise ValueError("expected_options must contain all four exact native integer values")


def validate_edit(field, value, expected_options):
    validate_snapshot(expected_options)
    if field not in LINE_FONT_VALUES or type(value) is not int or value not in LINE_FONT_VALUES[field]:
        raise ValueError("unsupported drawing line font value")

# Independently audited run 42260712677, head 6f531a595a50bbadeeab2c0f005d89c0246c7ee5.
# Public CLI validation remains a separate gate. Reverse conversions stay closed.
CALIBRATED_LINE_FONT_REVISION = "33.5.0"
CALIBRATED_LINE_FONT_TRANSITIONS = {
    "visible_edges.style": (0, 1),
    "visible_edges.weight": (1, 0),
    "hidden_edges.style": (1, 0),
    "hidden_edges.weight": (0, 1),
}
