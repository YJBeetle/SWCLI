"""Narrow face-observation result contracts, separate from edit authority."""

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


def entity_result_fields():
    common = {
        "scope": {"const": "single-solid-part-faces"},
        "body_count": {"const": 1},
        "face_count": {"type": "integer", "minimum": 1, "maximum": 64},
        "observation": _OBSERVATION,
    }
    return deepcopy(
        {
            "entity.list": (
                {
                    **common,
                    "entities": {
                        "type": "array",
                        "items": _FACE,
                        "minItems": 1,
                        "maxItems": 64,
                    },
                },
                ("document", *common, "entities"),
            ),
            "entity.inspect": (
                {**common, "entity": _FACE},
                ("document", *common, "entity"),
            ),
        }
    )


def without_entity_ids(schema, name):
    """Make a copy for validating native evidence before handle registration."""
    schema = deepcopy(schema)
    face = (
        schema["properties"]["entities"]["items"]
        if name == "entity.list"
        else schema["properties"]["entity"]
    )
    for variant in face["oneOf"]:
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
                for key in ("entities", "entity", "face_count", "body_count")
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
    faces = result["entities"] if name == "entity.list" else [result["entity"]]
    if name == "entity.list":
        require(result["face_count"] == len(faces), "incomplete face enumeration")
        tokens = [face["entity_id"] for face in faces if "entity_id" in face]
        require(len(tokens) == len(set(tokens)), "duplicate entity handles")
    for face in faces:
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
