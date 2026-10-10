"""Narrow face/edge observation contracts, separate from edit authority."""

from copy import deepcopy
import math


def _object(fields):
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


_VECTOR = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
_STATE = _object(
    {
        "configuration": {"type": "string", "minLength": 1},
        "update_stamp": {"type": "integer"},
        "modified": {"type": "boolean"},
        "editing": {"type": "boolean"},
        "foreground_present": {"type": "boolean"},
    }
)
_OBSERVATION = {
    **_object({"before": _STATE, "after": _STATE, "unchanged": {"type": "boolean"}}),
    "required": ["before", "unchanged"],
}
_GEOMETRY_BASE = {
    "available": {"const": True},
    "coordinate_system": {"const": "part-model"},
    "boundary": {"const": "untrimmed-surface"},
    "face_normal_opposes_surface": {"type": "boolean"},
}
_GEOMETRIES = {
    "plane": _object(
        {
            **_GEOMETRY_BASE,
            "plane": _object(
                {
                    "point_mm": _VECTOR,
                    "surface_normal": _VECTOR,
                    "outward_normal": _VECTOR,
                }
            ),
        }
    ),
    "cylinder": _object(
        {
            **_GEOMETRY_BASE,
            "cylinder": _object(
                {
                    "axis_point_mm": _VECTOR,
                    "axis_direction": _VECTOR,
                    "radius_mm": {"type": "number", "exclusiveMinimum": 0},
                }
            ),
        }
    ),
    "unclassified": _object(
        {"available": {"const": False}, "reason": {"const": "unsupported-surface-kind"}}
    ),
}
_FACE = {
    "oneOf": [
        _object(
            {
                "entity_id": {"type": "string", "pattern": "^e-[a-z0-9]{6}$"},
                "kind": {"const": "face"},
                "surface_kind": {"const": kind},
                "area_mm2": {"type": "number", "exclusiveMinimum": 0},
                "area_accuracy": {"const": "approximate"},
                "surface_geometry": geometry,
            }
        )
        for kind, geometry in _GEOMETRIES.items()
    ]
}
_CURVE_TYPES = {"line": 3001, "circle": 3002}
_CURVE_BASE = {
    "available": {"const": True},
    "coordinate_system": {"const": "part-model"},
    "boundary": {"const": "untrimmed-curve"},
}
_CURVES = {
    "line": _object({**_CURVE_BASE, "line": _object({
        "root_point_mm": _VECTOR, "direction": _VECTOR,
    })}),
    "circle": _object({**_CURVE_BASE, "circle": _object({
        "center_mm": _VECTOR, "axis_direction": _VECTOR,
        "radius_mm": {"type": "number", "exclusiveMinimum": 0},
    })}),
    "unclassified": _object({
        "available": {"const": False}, "reason": {"const": "unsupported-curve-kind"},
    }),
}
_EDGE = {
    "oneOf": [
        _object({
            "entity_id": {"type": "string", "pattern": "^e-[a-z0-9]{6}$"},
            "kind": {"const": "edge"},
            "curve_kind": {"const": kind},
            "parameter_data": _object({
                "coordinate_system": {"const": "part-model"},
                "interpretation": {"const": "native-edge-parameter-data"},
                "start_point_mm": _VECTOR, "end_point_mm": _VECTOR,
                "u_min_native": {"type": "number"},
                "u_max_native": {"type": "number"},
                "curve_and_edge_same_direction": {"type": "boolean"},
                "curve_type": (
                    {"type": "integer", "const": _CURVE_TYPES[kind]}
                    if kind in _CURVE_TYPES else
                    {"type": "integer", "minimum": 1, "not": {"enum": list(_CURVE_TYPES.values())}}
                ),
            }),
            "curve_geometry": geometry,
        })
        for kind, geometry in _CURVES.items()
    ]
}
_ENTITY = {"oneOf": [*_FACE["oneOf"], *_EDGE["oneOf"]]}


def entity_result_fields():
    common = {
        "scope": {"enum": ["single-solid-part-faces", "single-solid-part-edges"]},
        "body_count": {"const": 1},
        "face_count": {"type": "integer", "minimum": 1, "maximum": 64},
        "edge_count": {"type": "integer", "minimum": 1, "maximum": 64},
        "observation": _OBSERVATION,
    }
    return deepcopy(
        {
            "entity.list": (
                {
                    **common,
                    "entities": {
                        "type": "array",
                        "items": _ENTITY,
                        "minItems": 1,
                        "maxItems": 64,
                    },
                },
                ("document", "scope", "body_count", "observation", "entities"),
            ),
            "entity.inspect": (
                {**common, "entity": _ENTITY},
                ("document", "scope", "body_count", "observation", "entity"),
            ),
        }
    )


def entity_success_conditions(name):
    """A success contains exactly one complete kind, never mixed/partial counts."""
    return [{
        "if": {"properties": {"scope": {"const": "single-solid-part-edges"}}},
        "then": _kind_success(name, "edge", "face"),
        "else": _kind_success(name, "face", "edge"),
    }]


def _kind_success(name, kind, other):
    descriptor = {"properties": {"kind": {"const": kind}}}
    return {
        "required": [f"{kind}_count"],
        "not": {"required": [f"{other}_count"]},
        "properties": (
            {"entities": {"items": descriptor}} if name == "entity.list"
            else {"entity": descriptor}
        ),
    }


def without_entity_ids(schema, name):
    """Make a copy for validating native evidence before handle registration."""
    schema = deepcopy(schema)
    entity = (
        schema["properties"]["entities"]["items"]
        if name == "entity.list"
        else schema["properties"]["entity"]
    )
    for variant in entity["oneOf"]:
        variant["required"].remove("entity_id")
        del variant["properties"]["entity_id"]
    return schema


def validate_entity_semantics(name, result):
    def require(condition, message):
        if not condition:
            raise ValueError(f"{name}: {message}")

    if result["ok"] is not True:
        require(
            not any(
                key in result
                for key in ("entities", "entity", "face_count", "edge_count", "body_count")
            ),
            "failed observation published partial geometry or handles",
        )
        return
    before, after = result["observation"]["before"], result["observation"]["after"]
    document = result["document"]
    require(
        before == after
        and before["configuration"].strip()
        and document["type"] == 1
        and document["modified"] == after["modified"]
        and document["update_stamp"] == after["update_stamp"],
        "inconsistent read-only observation state",
    )
    kind = "edge" if result["scope"] == "single-solid-part-edges" else "face"
    entities = result["entities"] if name == "entity.list" else [result["entity"]]
    if name == "entity.list":
        require(result[f"{kind}_count"] == len(entities), f"incomplete {kind} enumeration")
        tokens = [entity["entity_id"] for entity in entities if "entity_id" in entity]
        require(len(tokens) == len(set(tokens)), "duplicate entity handles")
    for entity in entities:
        require(entity["kind"] == kind, "entity kind disagrees with observation scope")
        if kind == "edge":
            parameters = entity["parameter_data"]
            require(parameters["u_min_native"] < parameters["u_max_native"],
                    "native curve parameter interval is empty or reversed")
            curve_kind = entity["curve_kind"]
            if curve_kind != "unclassified":
                geometry = entity["curve_geometry"][curve_kind]
                direction = geometry["direction" if curve_kind == "line" else "axis_direction"]
                require(math.isclose(math.hypot(*direction), 1, rel_tol=0, abs_tol=1e-9),
                        "non-unit analytic curve direction")
            continue
        face = entity
        geometry = face["surface_geometry"]
        kind = face["surface_kind"]
        if kind == "unclassified":
            continue
        directions = (
            [geometry["plane"]["surface_normal"], geometry["plane"]["outward_normal"]]
            if kind == "plane"
            else [geometry["cylinder"]["axis_direction"]]
        )
        require(
            all(
                math.isclose(math.hypot(*direction), 1, rel_tol=0, abs_tol=1e-9)
                for direction in directions
            ),
            "non-unit analytic direction",
        )
        if kind == "plane":
            expected = (
                [-item for item in directions[0]]
                if geometry["face_normal_opposes_surface"]
                else directions[0]
            )
            require(
                all(
                    math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
                    for a, b in zip(expected, directions[1])
                ),
                "outward face normal disagrees with surface sense",
            )
