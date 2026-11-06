"""Pure JSON schema fragments and value checks for bounded document preferences.

No operation/result registry or host module is imported. Callers compose envelope
schemas themselves and invoke the semantic validators after JSON schema checks.
"""

from math import isfinite

from .document_annotation_fonts import (
    ANNOTATION_FONT_MEMBERS, ANNOTATION_FONT_WRITABLE_FIELDS,
    annotation_font_native_normalizations, annotation_font_snapshot,
    validate_annotation_font_snapshot, validate_annotation_font_value,
)
from .document_annotations import ANNOTATION_FIELDS
from .document_display_options import (
    DISPLAY_FIELDS, display_fields_for_document, display_observation, validate_display_value,
)
from .document_drafting_standard import (
    BASE_STANDARD_OPTIONS, DRAFTING_DEFAULTS_PROFILE, DRAFTING_STANDARDS,
    LENGTH_UNIT_NATIVE_FIELDS, NAMED_DRAFTING_STANDARDS,
    drafting_defaults_coverage, drafting_standard_observation, validate_drafting_standard,
)

_INT32 = {"type": "integer", "minimum": -2147483648, "maximum": 2147483647}
_INT16 = {"type": "integer", "minimum": -32768, "maximum": 32767}
_BOOL_FONT = {"bold", "italic", "underline", "strikeout", "backwards", "upside_down", "vertical"}
_OPERATIONS = (
    "document.annotation-font", "document.annotation-font-set",
    "document.display-options", "document.display-option-set",
    "document.drafting-standard", "document.drafting-standard-set",
)


def _object(properties, required=None):
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties if required is None else required)}


def _const(value):
    if type(value) is dict:
        return _object({key: _const(item) for key, item in value.items()})
    if type(value) is list:
        return {"type": "array", "prefixItems": [_const(item) for item in value],
                "items": False, "minItems": len(value), "maxItems": len(value)}
    kind = "boolean" if type(value) is bool else "integer" if type(value) is int else "string"
    return {"type": kind, "const": value}


def annotation_font_schema():
    properties = {}
    for field in ANNOTATION_FONT_MEMBERS:
        if field in _BOOL_FONT:
            spec = {"type": "boolean"}
        elif field == "typeface":
            spec = {"type": "string"}  # Read/CAS preserves unknown or empty native names.
        elif field == "height_mode":
            spec = {"type": "string", "enum": ["millimeters", "points"]}
        elif field == "height_points":
            spec = {"type": "integer", "minimum": 0, "maximum": 2147483647}
        else:
            spec = {"type": "number"}
            if field == "height_mm":
                spec["exclusiveMinimum"] = 0
        properties[field] = spec
    result = _object(properties)
    result["allOf"] = [{"if": {"properties": {"height_mode": {"const": "points"}}},
                        "then": {"properties": {"height_points": {"minimum": 1}}}}]
    return result


def native_annotation_font_schema():
    normalized = annotation_font_schema()["properties"]
    properties = {}
    for field, member in ANNOTATION_FONT_MEMBERS.items():
        if field == "height_mode":
            properties[member] = {"type": "boolean"}
        else:
            properties[member] = dict(normalized[field])
    result = _object(properties)
    result["allOf"] = [{"if": {"properties": {"IsHeightSpecifiedInPts": {"const": True}}},
                        "then": {"properties": {"CharHeightInPts": {"minimum": 1}}}}]
    return result


def annotation_font_pair_schema():
    return _object({"font": annotation_font_schema(), "native_font": native_annotation_font_schema()})


def native_font_normalizations_schema():
    variants = []
    for member in ("CharHeight", "CharHeightInPts"):
        number = ({"type": "number", "exclusiveMinimum": 0} if member == "CharHeight" else
                  {"type": "integer", "minimum": 0, "maximum": 2147483647})
        variants.append(_object({"member": {"type": "string", "const": member},
            "before": dict(number), "after": dict(number),
            "reason": {"type": "string", "const": "inactive-height-representation"}}))
    return {"type": "array", "maxItems": 1, "items": {"oneOf": variants}}


def _font_write_value_schema(field):
    if field == "typeface":
        # Backend additionally enforces str.strip() equality and no controls.
        return {"type": "string", "minLength": 1,
                "pattern": r"^\S(?:[\s\S]*\S)?$", "not": {"pattern": r"[\x00-\x1f\x7f]"}}
    if field == "height_points":
        return {"type": "integer", "minimum": 1, "maximum": 2147483647}
    if field == "height_mm":
        return {"type": "number", "exclusiveMinimum": 0}
    return {"type": "boolean"}


def _enum_observation(values):
    variants = [_object({"value": {"type": "string", "const": name},
                         "native_value": {**_INT32, "const": code}})
                for name, code in values.items()]
    variants.append(_object({"value": {"type": "string", "const": "other"},
        "native_value": {**_INT32, "not": {"enum": list(values.values())}}}))
    return {"oneOf": variants}


def display_value_schema(field, *, writable=True):
    spec = DISPLAY_FIELDS[field]
    if spec["kind"] == "Toggle":
        return {"type": "boolean"}
    if spec["kind"] == "Double":
        return {"type": "number", "exclusiveMinimum": 0}
    if "values" in spec:
        # Unknown raw enums can be read but cannot be CAS'd through a generic
        # "other" string: the current setter accepts only known enum prevalues.
        return {"type": "string", "enum": list(spec["values"])}
    return ({"type": "integer", "minimum": spec["minimum"], "maximum": spec["maximum"]}
            if writable else dict(_INT32))


def _scalar_observation(spec):
    if "values" in spec:
        return _enum_observation(spec["values"])
    value = ({"type": "boolean"} if spec["kind"] == "Toggle" else
             {"type": "number", "exclusiveMinimum": 0} if spec["kind"] == "Double" else dict(_INT32))
    return _object({"value": dict(value), "native_value": dict(value)})


def display_options_schema(kind=None):
    if kind is None:
        return {"oneOf": [display_options_schema(1), display_options_schema(3)]}
    return _object({field: _scalar_observation(spec)
                    for field, spec in display_fields_for_document(kind).items()})


def _annotation_options_schema():
    return _object({field: _scalar_observation(spec) for field, spec in ANNOTATION_FIELDS.items()})


def _length_units_schema():
    return _object({"length_unit": {"type": "string", "enum": ["mm", "inch", "other"]},
        "decimal_places": dict(_INT16),
        "native_units": _object({field: dict(_INT16) for field in LENGTH_UNIT_NATIVE_FIELDS})})


def drafting_snapshot_schema(kind=None):
    if kind is None:
        return {"oneOf": [drafting_snapshot_schema(number) for number in (1, 2, 3)]}
    coverage = drafting_defaults_coverage(kind)
    return _object({"standard": _enum_observation(DRAFTING_STANDARDS),
        "observed_defaults": _object({
            "profile": {"type": "string", "const": DRAFTING_DEFAULTS_PROFILE},
            "document_type": {"type": "integer", "const": kind},
            "coverage": _const(coverage), "annotations": _annotation_options_schema(),
            "annotation_font": annotation_font_pair_schema(), "length_units": _length_units_schema(),
            "display": display_options_schema(kind),
            "base_standards": _object({name: _enum_observation(DRAFTING_STANDARDS)
                                       for name in BASE_STANDARD_OPTIONS})})})


def document_preference_parameters(operation):
    """Return a fresh complete parameters object schema, without registration."""
    if operation not in _OPERATIONS:
        raise ValueError("unsupported document preference operation")
    if operation in ("document.annotation-font", "document.display-options", "document.drafting-standard"):
        return _object({})
    if operation == "document.annotation-font-set":
        variants = [_object({"field": {"type": "string", "const": field},
            "value": _font_write_value_schema(field), "expected_font": annotation_font_schema()})
            for field in ANNOTATION_FONT_WRITABLE_FIELDS]
        return {"oneOf": variants}
    if operation == "document.display-option-set":
        return {"oneOf": [_object({"field": {"type": "string", "const": field},
            "value": display_value_schema(field),
            "expected_value": display_value_schema(field, writable=False)}) for field in DISPLAY_FIELDS]}
    return _object({"value": {"type": "string", "enum": list(NAMED_DRAFTING_STANDARDS)},
                    "expected_snapshot": drafting_snapshot_schema()})


def document_preference_result_fields(operation):
    """Return (owned result properties, fields required when ok=true).

    Envelope fields such as ok/action/error/document/session belong to the
    caller's result schema. Failure receipts may contain only some owned fields.
    """
    if operation not in _OPERATIONS:
        raise ValueError("unsupported document preference operation")
    if operation.startswith("document.annotation-font"):
        fields = {"font": annotation_font_schema(), "native_font": native_annotation_font_schema()}
        if operation.endswith("-set"):
            fields.update({"field": {"type": "string", "enum": list(ANNOTATION_FONT_WRITABLE_FIELDS)},
                "before": annotation_font_schema(), "native_before": native_annotation_font_schema(),
                "observed_font": annotation_font_schema(), "observed_native_font": native_annotation_font_schema(),
                "changed": {"type": "boolean"}, "mutation": _mutation_schema(),
                "native_normalizations": native_font_normalizations_schema()})
            return fields, ("field", "before", "native_before", "font", "native_font", "changed", "mutation", "native_normalizations")
        return fields, ("font", "native_font")
    if operation.startswith("document.display-"):
        fields = {"options": display_options_schema()}
        if operation.endswith("-set"):
            fields.update({"field": {"type": "string", "enum": list(DISPLAY_FIELDS)},
                "before": display_options_schema(), "observed_options": display_options_schema(),
                "changed": {"type": "boolean"}, "mutation": _mutation_schema()})
            return fields, ("field", "before", "options", "changed", "mutation")
        return fields, ("options",)
    # A kind branch binds both document_type and its exact coverage/display set.
    fields = {"standard": _enum_observation(DRAFTING_STANDARDS),
              "observed_defaults": {"oneOf": [drafting_snapshot_schema(kind)["properties"]["observed_defaults"]
                                               for kind in (1, 2, 3)]}}
    if operation.endswith("-set"):
        fields.update({"before": drafting_snapshot_schema(), "after": drafting_snapshot_schema(),
            "final": drafting_snapshot_schema(), "observed_defaults_changed": {"type": "boolean"},
            "changed": {"type": "boolean"}, "mutation": _mutation_schema()})
        return fields, ("standard", "observed_defaults", "before", "changed", "mutation")
    return fields, ("standard", "observed_defaults")


def _mutation_schema():
    return _object({"attempted": {"type": "boolean"}, "may_have_changed": {"type": "boolean"}})


def _finite(value):
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def validate_preference_schema(value, schema):
    """Strict backend supplement: reject non-finite numbers and float/bool ints.

    These JSON schemas remain portable. JSON Schema alone does not constrain
    Python's NaN or distinguish an integer from an integral Python float.
    """
    from jsonschema import Draft202012Validator, validators
    checker = Draft202012Validator.TYPE_CHECKER.redefine_many({
        "integer": lambda checker, item: type(item) is int,
        "number": lambda checker, item: _finite(item),
    })
    validator = validators.extend(Draft202012Validator, type_checker=checker)
    try:
        validator(schema).validate(value)
    except Exception as error:
        raise ValueError("document preference payload does not match its schema: " + str(error)) from error
    return value


def _font_pair(font, native):
    validate_annotation_font_snapshot(font)
    if annotation_font_snapshot(native) != font:
        raise ValueError("annotation font normalized/native values disagree")


def _scalar_values(options, catalog):
    for field, observation in options.items():
        spec = catalog[field]
        raw = observation["native_value"]
        if catalog is DISPLAY_FIELDS:
            expected = display_observation(field, raw)
        elif spec["kind"] == "Integer":
            expected = {"value": next((name for name, code in spec["values"].items() if code == raw), "other"),
                        "native_value": raw}
        else:
            expected = {"value": raw * 1000.0 if spec["kind"] == "Double" else raw,
                        "native_value": raw}
        if observation != expected:
            raise ValueError("document preference normalized/native scalar values disagree: " + field)


def validate_drafting_snapshot_values(snapshot):
    validate_preference_schema(snapshot, drafting_snapshot_schema())
    if snapshot["standard"] != drafting_standard_observation(snapshot["standard"]["native_value"]):
        raise ValueError("drafting standard normalized/native values disagree")
    observed = snapshot["observed_defaults"]
    _font_pair(observed["annotation_font"]["font"], observed["annotation_font"]["native_font"])
    _scalar_values(observed["annotations"], ANNOTATION_FIELDS)
    _scalar_values(observed["display"], DISPLAY_FIELDS)
    for value in observed["base_standards"].values():
        if value != drafting_standard_observation(value["native_value"]):
            raise ValueError("drafting base standard normalized/native values disagree")
    units = observed["length_units"]
    native = units["native_units"]
    unit = {0: "mm", 3: "inch"}.get(native["length_unit"], "other")
    if units["length_unit"] != unit or units["decimal_places"] != native["significant_digits"]:
        raise ValueError("length unit normalized/native values disagree")
    return snapshot


def validate_document_preference_request(operation, parameters):
    validate_preference_schema(parameters, document_preference_parameters(operation))
    if operation == "document.annotation-font-set":
        validate_annotation_font_value(parameters["field"], parameters["value"])
        validate_annotation_font_snapshot(parameters["expected_font"])
    elif operation == "document.display-option-set":
        validate_display_value(parameters["field"], parameters["value"])
        validate_display_value(parameters["field"], parameters["expected_value"], writable=False)
    elif operation == "document.drafting-standard-set":
        validate_drafting_standard(parameters["value"])
        validate_drafting_snapshot_values(parameters["expected_snapshot"])
    return parameters


def validate_document_preference_result_values(operation, result):
    """Validate owned fragments and cross-field semantics, not transport envelope."""
    fields, required = document_preference_result_fields(operation)
    owned = {key: value for key, value in result.items() if key in fields}
    validate_preference_schema(owned, _object(fields, required if result.get("ok") is True else ()))
    if operation.startswith("document.annotation-font"):
        for public, native in (("font", "native_font"), ("before", "native_before"),
                               ("observed_font", "observed_native_font")):
            if public in result and native in result:
                _font_pair(result[public], result[native])
        if operation.endswith("-set") and result.get("ok") is True:
            expected = annotation_font_native_normalizations(result["native_before"], result["native_font"],
                                                             ANNOTATION_FONT_MEMBERS[result["field"]])
            if result["native_normalizations"] != expected:
                raise ValueError("native font normalization evidence disagrees with raw snapshots")
    elif operation.startswith("document.display-"):
        for key in ("options", "before", "observed_options"):
            if key in result:
                _scalar_values(result[key], DISPLAY_FIELDS)
                kind = result.get("document", {}).get("type")
                if kind is not None:
                    validate_preference_schema(result[key], display_options_schema(kind))
    else:
        if "standard" in result and "observed_defaults" in result:
            validate_drafting_snapshot_values({key: result[key] for key in ("standard", "observed_defaults")})
            kind = result.get("document", {}).get("type")
            if kind is not None and kind != result["observed_defaults"]["document_type"]:
                raise ValueError("drafting profile document type disagrees with selected document")
        for key in ("before", "after", "final"):
            if key in result:
                validate_drafting_snapshot_values(result[key])
    return result
