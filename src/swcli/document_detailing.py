"""Drawing-only defaults for future view creation, mapped by official enum names."""

DETAILING_FIELDS = {
    "auto_center_marks.part_holes": "swDetailingAutoInsertCenterMarksForHoles",
    "auto_center_marks.part_fillets": "swDetailingAutoInsertCenterMarksForFillets",
}


def detailing_options_schema():
    return {"type": "object", "additionalProperties": False,
            "properties": {field: {"type": "boolean"} for field in DETAILING_FIELDS},
            "required": list(DETAILING_FIELDS)}


def validate_detailing_options(options):
    if (type(options) is not dict or set(options) != set(DETAILING_FIELDS)
            or any(type(value) is not bool for value in options.values())):
        raise ValueError("expected_options must contain the complete two-boolean detailing snapshot")
