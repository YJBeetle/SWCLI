"""Bounded dimension display catalog, separate from units and tolerances."""

# Official SOLIDWORKS 2025 SDK swconst.h; rechecked against swconst.tlb in CI.
POSITIONS = {"right": 1, "top": 2, "left": 3, "bottom": 4}
DIMENSION_FORMAT_FIELDS = {
    "dual_display": {"kind": "Toggle", "preference": 43, "option": 200,
                     "symbol": "swDetailingDualDimensions", "option_symbol": "swDetailingDimension"},
    "dual_position": {"kind": "Integer", "preference": 14, "option": 200,
                      "symbol": "swDetailingDualDimPosition", "option_symbol": "swDetailingDimension"},
    "parentheses": {"kind": "Toggle", "preference": 48, "option": 0,
                    "symbol": "swDetailingDimsShowParenthesisByDefault", "option_symbol": "swDetailingNoOptionSpecified"},
}
# Development-branch public-acceptance candidate: internal run 42277961301
# calibrated these exact native Windows profiles. Installed CLI/daemon
# acceptance is still required before integration; see WORK_HANDOFF.md.
CALIBRATED_DOCUMENT_TYPES = frozenset({1, 2, 3})
CALIBRATED_HOST_REVISIONS = frozenset({"33.5.0"})


def format_schema():
    return {"type": "object", "additionalProperties": False,
            "required": list(DIMENSION_FORMAT_FIELDS), "properties": {
                "dual_display": {"type": "boolean"},
                "dual_position": {"type": "integer"},
                "parentheses": {"type": "boolean"},
            }}


def value_schema(field):
    return ({"type": "string", "enum": list(POSITIONS)} if field == "dual_position"
            else {"type": "boolean"})


def validate_format(values):
    if (type(values) is not dict or set(values) != set(DIMENSION_FORMAT_FIELDS)
            or type(values["dual_display"]) is not bool
            or type(values["parentheses"]) is not bool
            or type(values["dual_position"]) is not int):
        raise ValueError("expected_format must contain the complete native dimension display snapshot")


def validate_value(field, value):
    if field not in DIMENSION_FORMAT_FIELDS:
        raise ValueError("unsupported dimension display field")
    valid = (type(value) is str and value in POSITIONS if field == "dual_position"
             else type(value) is bool)
    if not valid:
        raise ValueError("unsupported value for dimension display field " + field)


def native_value(field, value):
    validate_value(field, value)
    return POSITIONS[value] if field == "dual_position" else value
