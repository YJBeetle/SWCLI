"""Bounded drawing document defaults; IDs are resolved from official swconst."""

LINE_FONT_FIELDS = {
    "visible_edges.style": "swLineFontVisibleEdgesStyle",
    "visible_edges.weight": "swLineFontVisibleEdgesThickness",
    "hidden_edges.style": "swLineFontHiddenEdgesStyle",
    "hidden_edges.weight": "swLineFontHiddenEdgesThickness",
}
# Style continuous/hidden; weight thin/normal/thick. No custom size or layer sentinel.
LINE_FONT_VALUES = {field: ([0, 1] if field.endswith(".style") else [0, 1, 2])
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
