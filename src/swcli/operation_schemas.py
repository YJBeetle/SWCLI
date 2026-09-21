"""Machine-readable schemas for every public SWCLI protocol operation."""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Dict, Optional

from .hosts.windows_documents import RENDER_VIEWS


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
CONTEXT_FIELDS = ("document_id", "expected_update_stamp", "lease_id")


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
) -> Dict[str, Any]:
    return {
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


_DOCUMENT_READ_CONTEXT = {
    "document_id": "optional",
    "expected_update_stamp": "optional",
}
_DOCUMENT_WRITE_CONTEXT = {
    **_DOCUMENT_READ_CONTEXT,
    "lease_id": "optional",
}


OPERATION_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "daemon.health": _operation("daemon.health"),
    "daemon.shutdown": _operation("daemon.shutdown"),
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
    "document.save": _operation(
        "document.save",
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


OPERATIONS = tuple(OPERATION_SCHEMAS)


def operation_schemas() -> Dict[str, Dict[str, Any]]:
    """Return an isolated protocol-safe operation schema catalog."""

    return deepcopy(OPERATION_SCHEMAS)


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
        raise ValueError(
            f"unsupported {operation} parameters: {', '.join(unexpected)}"
        )
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
