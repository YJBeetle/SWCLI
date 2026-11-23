"""Candidate view-creation line defaults; existing center marks are CAS guards."""

from .document_detailing import DETAILING_FIELDS

DETAILING_LINE_FIELDS = {
    "auto_center_lines.enabled": "swDetailingAutoInsertCenterLines",
    "auto_center_marks.hole_pattern_connection_lines": "swDetailingConnectionLinesHolePatternsCenterMarks",
}
DETAILING_LINE_SNAPSHOT_FIELDS = {**DETAILING_FIELDS, **DETAILING_LINE_FIELDS}


def detailing_line_options_schema():
    return {"type": "object", "additionalProperties": False,
            "properties": {field: {"type": "boolean"} for field in DETAILING_LINE_SNAPSHOT_FIELDS},
            "required": list(DETAILING_LINE_SNAPSHOT_FIELDS)}


def validate_detailing_line_edit(field, value, expected_options):
    if field not in DETAILING_LINE_FIELDS or type(value) is not bool:
        raise ValueError("unsupported drawing line default or non-boolean value")
    if (type(expected_options) is not dict or set(expected_options) != set(DETAILING_LINE_SNAPSHOT_FIELDS)
            or any(type(item) is not bool for item in expected_options.values())):
        raise ValueError("expected_options must contain all four boolean drawing defaults")
