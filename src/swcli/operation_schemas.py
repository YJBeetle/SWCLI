"""Machine-readable schemas for every public SWCLI protocol operation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from re import search
from typing import Any, Dict, Optional

from .hosts.windows_documents import RENDER_VIEWS
from .hosts.windows_sketches import STANDARD_PLANES
from .result_schemas import operation_result_schema

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
CONTEXT_FIELDS = ("document_id", "expected_update_stamp", "lease_id")


@dataclass(frozen=True)
class OperationSpec:
    """One declaration for request contract and execution policy."""

    parameters: Dict[str, Any]
    handler: Optional[str]
    selected_document: bool
    lease_guarded: bool
    temporary_activation: bool
    result: Dict[str, Any]


def _string(**keywords: Any) -> Dict[str, Any]:
    return {"type": "string", **keywords}


def _boolean() -> Dict[str, Any]:
    return {"type": "boolean"}


def _integer(**keywords: Any) -> Dict[str, Any]:
    return {"type": "integer", **keywords}


def _number(**keywords: Any) -> Dict[str, Any]:
    return {"type": "number", **keywords}


def _operation(
    name: str,
    properties: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    required: tuple[str, ...] = (),
    document_id: str = "forbidden",
    expected_update_stamp: str = "forbidden",
    lease_id: str = "forbidden",
    selected_document: Optional[bool] = None,
    temporary_activation: bool = False,
) -> OperationSpec:
    schema = {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"https://swcli.dev/schema/v1/operations/{name}.schema.json",
        "title": f"SWCLI {name} parameters",
        "type": "object",
        "additionalProperties": False,
        "properties": properties or {},
        "required": list(required),
        "x-swcli-context": {
            "document_id": document_id,
            "expected_update_stamp": expected_update_stamp,
            "lease_id": lease_id,
        },
    }
    return OperationSpec(
        parameters=schema,
        handler=(
            None
            if name.startswith("daemon.")
            else name.replace(".", "_").replace("-", "_")
        ),
        selected_document=(
            (document_id != "forbidden")
            if selected_document is None
            else selected_document
        ),
        lease_guarded=lease_id == "optional",
        temporary_activation=temporary_activation,
        result=operation_result_schema(name),
    )


_DOCUMENT_READ_CONTEXT = {
    "document_id": "optional",
    "expected_update_stamp": "optional",
}
_DOCUMENT_WRITE_CONTEXT = {
    **_DOCUMENT_READ_CONTEXT,
    "lease_id": "optional",
}


OPERATION_CATALOG: Dict[str, OperationSpec] = {
    "daemon.health": _operation("daemon.health"),
    "daemon.shutdown": _operation("daemon.shutdown"),
    "document.create": _operation(
        "document.create",
        {"type": _string(enum=["part"]), "template": _string(minLength=1)},
    ),
    "document.open": _operation(
        "document.open",
        {
            "path": _string(minLength=1),
            "read_only": _boolean(),
            "configuration": _string(),
        },
        required=("path",),
    ),
    "document.list": _operation("document.list"),
    "document.use": _operation(
        "document.use",
        document_id="required",
        selected_document=False,
    ),
    "document.lease.acquire": _operation(
        "document.lease.acquire",
        {"ttl_seconds": _number(minimum=1, maximum=3600)},
        document_id="optional",
    ),
    "document.lease.status": _operation(
        "document.lease.status",
        document_id="optional",
    ),
    "document.lease.renew": _operation(
        "document.lease.renew",
        {"ttl_seconds": _number(minimum=1, maximum=3600)},
        lease_id="required",
    ),
    "document.lease.release": _operation(
        "document.lease.release",
        lease_id="required",
    ),
    "document.inspect": _operation(
        "document.inspect",
        {
            "detail": _string(enum=["summary", "structure"]),
            "max_features": _integer(minimum=1),
        },
        **_DOCUMENT_READ_CONTEXT,
    ),
    "document.close": _operation(
        "document.close",
        {"discard": _boolean()},
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "document.measure": _operation(
        "document.measure",
        {"max_bodies": _integer(minimum=1)},
        **_DOCUMENT_READ_CONTEXT,
    ),
    "document.save": _operation(
        "document.save",
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "document.save-as": _operation(
        "document.save-as",
        {"output": _string(minLength=1)},
        required=("output",),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "document.diagnose": _operation(
        "document.diagnose",
        {"max_features": _integer(minimum=1)},
        **_DOCUMENT_READ_CONTEXT,
    ),
    "document.rebuild": _operation(
        "document.rebuild",
        {
            "force": _boolean(),
            "top_only": _boolean(),
            "max_features": _integer(minimum=1),
        },
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "document.render": _operation(
        "document.render",
        {
            "output": _string(minLength=1),
            "width": _integer(minimum=1),
            "height": _integer(minimum=1),
            "view": _string(enum=list(RENDER_VIEWS)),
            "fit": _boolean(),
            "overwrite": _boolean(),
        },
        required=("output",),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "document.export": _operation(
        "document.export",
        {
            "output": _string(minLength=1),
            "overwrite": _boolean(),
            "strict": _boolean(),
        },
        required=("output",),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "sketch.inspect": _operation(
        "sketch.inspect",
        {
            "sketch_id": _string(pattern="^s-[a-z0-9]{6}$"),
            "max_segments": _integer(minimum=1),
        },
        required=("sketch_id",),
        **_DOCUMENT_READ_CONTEXT,
    ),
    "sketch.rectangle": _operation(
        "sketch.rectangle",
        {
            "plane": _string(enum=list(STANDARD_PLANES)),
            "width_mm": _number(exclusiveMinimum=0),
            "height_mm": _number(exclusiveMinimum=0),
            "center_x_mm": _number(),
            "center_y_mm": _number(),
        },
        required=("plane", "width_mm", "height_mm"),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "sketch.circle": _operation(
        "sketch.circle",
        {
            "plane": _string(enum=list(STANDARD_PLANES)),
            "radius_mm": _number(exclusiveMinimum=0),
            "center_x_mm": _number(),
            "center_y_mm": _number(),
        },
        required=("plane", "radius_mm"),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "sketch.dimension-diameter": _operation(
        "sketch.dimension-diameter",
        {
            "sketch_id": _string(pattern="^s-[a-z0-9]{6}$"),
            "diameter_mm": _number(exclusiveMinimum=0),
        },
        required=("sketch_id", "diameter_mm"),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "dimension.inspect": _operation(
        "dimension.inspect",
        {"dimension_id": _string(pattern="^m-[a-z0-9]{6}$")},
        required=("dimension_id",),
        **_DOCUMENT_READ_CONTEXT,
    ),
    "dimension.set": _operation(
        "dimension.set",
        {
            "dimension_id": _string(pattern="^m-[a-z0-9]{6}$"),
            "value_mm": _number(exclusiveMinimum=0),
        },
        required=("dimension_id", "value_mm"),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "feature.extrude": _operation(
        "feature.extrude",
        {
            "sketch_id": _string(pattern="^s-[a-z0-9]{6}$"),
            "depth_mm": _number(exclusiveMinimum=0),
            "reverse": _boolean(),
            "merge": _boolean(),
        },
        required=("sketch_id", "depth_mm"),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "feature.cut-extrude": _operation(
        "feature.cut-extrude",
        {
            "sketch_id": _string(pattern="^s-[a-z0-9]{6}$"),
            "depth_mm": _number(exclusiveMinimum=0),
            "reverse": _boolean(),
        },
        required=("sketch_id", "depth_mm"),
        temporary_activation=True,
        **_DOCUMENT_WRITE_CONTEXT,
    ),
    "part.create-box": _operation(
        "part.create-box",
        {
            "output": _string(minLength=1),
            "width_mm": _number(exclusiveMinimum=0),
            "height_mm": _number(exclusiveMinimum=0),
            "depth_mm": _number(exclusiveMinimum=0),
            "template": _string(minLength=1),
            "overwrite": _boolean(),
        },
        required=("output", "width_mm", "height_mm", "depth_mm"),
    ),
}


OPERATION_SCHEMAS = {name: spec.parameters for name, spec in OPERATION_CATALOG.items()}
OPERATIONS = tuple(OPERATION_CATALOG)


def operation_schemas() -> Dict[str, Dict[str, Any]]:
    """Return an isolated protocol-safe operation schema catalog."""

    return deepcopy(OPERATION_SCHEMAS)


def operation_result_schemas() -> Dict[str, Dict[str, Any]]:
    return {name: deepcopy(spec.result) for name, spec in OPERATION_CATALOG.items()}


def _validate_parameter(name: str, value: Any, schema: Dict[str, Any]) -> None:
    expected = schema["type"]
    if expected == "string":
        valid = isinstance(value, str)
    elif expected == "boolean":
        valid = isinstance(value, bool)
    elif expected == "integer":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    else:  # pragma: no cover - operation schemas only use the types above
        raise RuntimeError(f"unsupported operation schema type: {expected}")
    if not valid:
        article = "an" if expected == "integer" else "a"
        raise ValueError(f"{name} must be {article} {expected}")
    if expected == "number" and not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    if "minLength" in schema and len(value) < schema["minLength"]:
        raise ValueError(f"{name} must not be empty")
    if "pattern" in schema and search(schema["pattern"], value) is None:
        raise ValueError(f"{name} must match {schema['pattern']}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{name} must be one of {', '.join(schema['enum'])}")
    if "minimum" in schema and value < schema["minimum"]:
        raise ValueError(f"{name} must be at least {schema['minimum']}")
    if "maximum" in schema and value > schema["maximum"]:
        raise ValueError(f"{name} must be at most {schema['maximum']}")
    if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
        raise ValueError(f"{name} must be greater than {schema['exclusiveMinimum']}")


def validate_operation_request(
    operation: str,
    parameters: Dict[str, Any],
    *,
    document_id: Optional[str] = None,
    expected_update_stamp: Optional[int] = None,
    lease_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate one request against the same schemas published by swclid."""

    schema = OPERATION_SCHEMAS.get(operation)
    if schema is None:
        raise ValueError(f"unsupported operation: {operation}")
    properties = schema["properties"]
    unexpected = sorted(set(parameters) - set(properties))
    if unexpected:
        raise ValueError(f"unsupported {operation} parameters: {', '.join(unexpected)}")
    missing = sorted(
        name for name in schema["required"] if parameters.get(name) is None
    )
    if missing:
        raise ValueError(f"{operation} requires {', '.join(missing)}")
    for name, value in parameters.items():
        _validate_parameter(name, value, properties[name])

    context_values = {
        "document_id": document_id,
        "expected_update_stamp": expected_update_stamp,
        "lease_id": lease_id,
    }
    for name in CONTEXT_FIELDS:
        mode = schema["x-swcli-context"][name]
        value = context_values[name]
        if mode == "required" and value is None:
            raise ValueError(f"{operation} requires {name}")
        if mode == "forbidden" and value is not None:
            raise ValueError(f"{name} is not supported for {operation}")
    return parameters
