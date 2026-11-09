"""Bounded document table defaults, declared by official swconst symbol names."""

from copy import deepcopy

LINE_WEIGHTS = {
    "none": -1, "thin": 0, "normal": 1, "thick": 2, "thick2": 3,
    "thick3": 4, "thick4": 5, "thick5": 6, "thick6": 7,
    "number": 8, "layer": 9, "custom": 10,
}
# See docs/design/document-table-defaults.md. General defaults are drawing-only.
TABLE_FIELDS = {
    "all.use_template_settings": {"kind": "Toggle", "symbol": "swDetailingTablesUseTemplateSettings", "types": (1, 2, 3)},
    "bom.box_border": {"kind": "Integer", "symbol": "swDetailingBillOfMaterialBorderLineWeight", "types": (1, 2, 3)},
    "bom.grid_border": {"kind": "Integer", "symbol": "swDetailingBillOfMaterialGridLineWeight", "types": (1, 2, 3)},
    "general.box_border": {"kind": "Integer", "symbol": "swDetailingGeneralTableBorderLineWeight", "types": (3,)},
    "general.grid_border": {"kind": "Integer", "symbol": "swDetailingGeneralTableGridLineWeight", "types": (3,)},
}


def table_value_schema(field):
    return ({"type": "boolean"} if TABLE_FIELDS[field]["kind"] == "Toggle" else
            {"type": "string", "enum": ["thin", "normal", "thick"]})


def validate_table_value(field, value):
    if field not in TABLE_FIELDS:
        raise ValueError("unsupported document table field")
    if TABLE_FIELDS[field]["kind"] == "Toggle":
        valid = type(value) is bool
    else:
        valid = type(value) is str and value in ("thin", "normal", "thick")
    if not valid:
        raise ValueError("unsupported value for document table field " + field)
    return value


def table_options_schema():
    properties = {}
    for field, spec in TABLE_FIELDS.items():
        if spec["kind"] == "Toggle":
            scalar = {"type": "object", "additionalProperties": False,
                      "properties": {"value": {"type": "boolean"}, "native_value": {"type": "boolean"}},
                      "required": ["value", "native_value"]}
        else:
            scalar = {"type": "object", "additionalProperties": False,
                      "properties": {"value": {"type": "string", "enum": [*LINE_WEIGHTS, "other"]},
                                     "native_value": {"type": "integer"}},
                      "required": ["value", "native_value"]}
        # Explicit unavailable entries keep the CAS snapshot complete across types.
        unavailable = {"type": "object", "additionalProperties": False,
                       "properties": {"unavailable": {"type": "string", "enum": ["document_type"]}},
                       "required": ["unavailable"]}
        properties[field] = {"anyOf": [scalar, unavailable]} if spec["types"] == (3,) else scalar
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(TABLE_FIELDS)}


TABLE_OPTIONS_SCHEMA = table_options_schema()


def validate_table_options(options):
    # The complete shape is also published in request and result JSON schemas.
    from jsonschema import Draft202012Validator
    if not Draft202012Validator(TABLE_OPTIONS_SCHEMA).is_valid(options):
        raise ValueError("expected_options must be a complete document table snapshot")
    for field, entry in options.items():
        if "unavailable" in entry:
            continue
        native = entry["native_value"]
        value = (native if TABLE_FIELDS[field]["kind"] == "Toggle" else
                 next((name for name, number in LINE_WEIGHTS.items() if number == native), "other"))
        if type(value) is not type(entry["value"]) or value != entry["value"]:
            raise ValueError("inconsistent document table scalar/native value")
    return deepcopy(options)
