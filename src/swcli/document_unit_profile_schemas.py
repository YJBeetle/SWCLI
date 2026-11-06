"""Finite unit-profile JSON contracts shared by CLI and generated SDK."""
from .document_unit_profile import FIELDS, LINKAGE, PROFILE, NATIVE_UNITS


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

INT32 = {"type": "integer", "minimum": -2147483648, "maximum": 2147483647}
SHORT = {"type": "integer", "minimum": -32768, "maximum": 32767}


def target_schema(field):
    spec = FIELDS[field]
    return {"type": "string", "enum": list(spec["targets"])} if "enum" in spec else {"type": "integer", "minimum": 0, "maximum": 8}


def row_schema(field):
    spec = FIELDS[field]
    value = {"type": "string", "enum": list(spec["enum"]) + ["other"]} if "enum" in spec else {"anyOf": [{"type": "integer", "minimum": 0, "maximum": 8}, {"type": "string", "enum": ["other"]}]}
    return obj({"value": value, "native_value": INT32})

UNIT_PROFILE_SCHEMA = obj({
    "profile": {"type": "string", "enum": [PROFILE]}, "document_type": {"type": "integer", "minimum": 1, "maximum": 3},
    "values": obj({field: row_schema(field) for field in FIELDS}),
    "native_units": obj(dict.fromkeys(NATIVE_UNITS, SHORT)),
    "linkage": obj({name: {"type": "boolean"} if family == "Toggle" else INT32 for name, (family, _) in LINKAGE.items()}),
})
