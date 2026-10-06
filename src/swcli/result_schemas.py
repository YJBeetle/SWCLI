"""Contracts for operation results, distinct from transport error envelopes."""

from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict

from .protocol import load_schema


def _object(properties, required=(), *, extensible=False):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": extensible,
    }


STRING = {"type": "string"}
BOOL = {"type": "boolean"}
INTEGER = {"type": "integer"}
NUMBER = {"type": "number"}
NULLABLE_STRING = {"type": ["string", "null"]}
STRING_LIST = {"type": "array", "items": STRING}
DOCUMENT = _object(
    {
        "title": STRING,
        "path": STRING,
        "type": INTEGER,
        "modified": BOOL,
        "update_stamp": {"type": ["integer", "null"]},
        "document_id": {"type": "string", "pattern": "^d-[a-z0-9]{6}$"},
        "current": BOOL,
        "active": BOOL,
    },
    ("title", "path", "type", "modified", "update_stamp"),
)
LEASE = _object(
    {
        "lease_id": {"type": "string", "pattern": "^l-[a-z0-9]{12}$"},
        "document_id": DOCUMENT["properties"]["document_id"],
        "session_id": STRING,
        "expires_in_seconds": {"type": "number", "minimum": 0},
    },
    ("document_id", "session_id", "expires_in_seconds"),
)
DIAGNOSTICS = _object(
    {
        "healthy": BOOL,
        "issues": {
            "type": "array",
            "items": _object(
                {
                    "index": INTEGER,
                    "name": STRING,
                    "type": STRING,
                    "code": INTEGER,
                    "severity": {"enum": ["error", "warning"]},
                },
                ("index", "name", "type", "code", "severity"),
            ),
        },
        "issue_count": INTEGER,
        "scanned_feature_count": INTEGER,
        "truncated": BOOL,
        "limit": INTEGER,
    },
    ("healthy", "issues", "issue_count", "scanned_feature_count", "truncated", "limit"),
)
PIXEL_SIZE = _object(
    {"width": INTEGER, "height": INTEGER, "unit": {"const": "pixel"}},
    ("width", "height", "unit"),
)
ARTIFACT = _object(
    {
        "kind": STRING,
        "path": STRING,
        "size_bytes": {"type": "integer", "minimum": 1},
        "format": {"enum": ["STEP", "GLB", "PDF", "DWG"]},
        "media_type": STRING,
    },
    ("kind", "path", "size_bytes"),
)

VECTOR = _object({"x": NUMBER, "y": NUMBER, "z": NUMBER}, ("x", "y", "z"))
BOUNDING_BOX = _object(
    {
        "coordinate_system": {"const": "model"},
        "unit": {"const": "meter"},
        "minimum": VECTOR,
        "maximum": VECTOR,
        "size_mm": VECTOR,
        "accuracy": {"const": "approximate"},
    },
    ("coordinate_system", "unit", "minimum", "maximum", "size_mm", "accuracy"),
)
CODE_NAME = _object({"code": INTEGER, "name": STRING}, ("code", "name"))
BODIES = _object(
    {
        "applicable": BOOL,
        "count": INTEGER,
        "items": {
            "type": "array",
            "items": _object(
                {
                    "name": STRING,
                    "type": CODE_NAME,
                    "visible": BOOL,
                    "face_count": INTEGER,
                    "edge_count": INTEGER,
                    "approximate_bounding_box": {
                        "anyOf": [BOUNDING_BOX, {"type": "null"}]
                    },
                },
                (
                    "name",
                    "type",
                    "visible",
                    "face_count",
                    "edge_count",
                    "approximate_bounding_box",
                ),
            ),
        },
    },
    ("applicable", "count", "items"),
)
STRUCTURE = _object(
    {
        "configurations": _object(
            {"active": NULLABLE_STRING, "names": STRING_LIST, "count": INTEGER},
            ("active", "names", "count"),
        ),
        "units": {
            "oneOf": [
                _object({"raw": {"type": "array", "items": NUMBER}}, ("raw",)),
                _object(
                    {
                        "length": CODE_NAME,
                        "fraction_base": INTEGER,
                        "fraction_value": INTEGER,
                        "significant_digits": INTEGER,
                        "round_to_fraction": BOOL,
                    },
                    (
                        "length",
                        "fraction_base",
                        "fraction_value",
                        "significant_digits",
                        "round_to_fraction",
                    ),
                ),
            ]
        },
        "features": _object(
            {
                "order": {"const": "model-definition"},
                "count": INTEGER,
                "truncated": BOOL,
                "limit": INTEGER,
                "items": {
                    "type": "array",
                    "items": _object(
                        {
                            "index": INTEGER,
                            "name": STRING,
                            "type": STRING,
                            "visibility": INTEGER,
                        },
                        ("index", "name", "type", "visibility"),
                    ),
                },
            },
            ("order", "count", "truncated", "limit", "items"),
        ),
        "bodies": BODIES,
    },
    ("configurations", "units", "features", "bodies"),
)
WARNINGS = {
    "type": "array",
    "items": _object(
        {
            "code": STRING,
            "message": STRING,
        },
        ("code", "message"),
        extensible=True,
    ),
}
ERROR = _object(
    {"type": STRING, "message": STRING}, ("type", "message"), extensible=True
)
PART_TEMPLATE = _object(
    {
        "ok": BOOL,
        "path": NULLABLE_STRING,
        "source": STRING,
        "configured_path": NULLABLE_STRING,
        "searched_roots": STRING_LIST,
    },
    ("ok", "path", "source"),
)


_RESULT_FIELDS = {
    "feature.extrude": (
        {
            "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
            "depth_mm": NUMBER,
            "reverse": BOOL,
            "merge": BOOL,
            "feature": _object({"name": STRING, "type": STRING}, ("name", "type")),
            "rebuilt": BOOL,
            "diagnostics": DIAGNOSTICS,
            "bodies": BODIES,
            "geometry_verification": _object(
                {
                    "passed": BOOL,
                    "method": {"const": "native-extrusion-definition"},
                    "actual_depth_mm": NUMBER,
                    "actual_reverse": BOOL,
                    "actual_merge": BOOL,
                    "end_condition": INTEGER,
                    "both_directions": BOOL,
                    "solid_body_count": INTEGER,
                    "absolute_tolerance_mm": NUMBER,
                },
                (
                    "passed",
                    "method",
                    "actual_depth_mm",
                    "actual_reverse",
                    "actual_merge",
                    "end_condition",
                    "both_directions",
                    "solid_body_count",
                    "absolute_tolerance_mm",
                ),
            ),
        },
        (
            "sketch_id",
            "depth_mm",
            "reverse",
            "merge",
            "feature",
            "rebuilt",
            "diagnostics",
            "bodies",
            "geometry_verification",
            "document",
        ),
    ),
    "sketch.rectangle": (
        {
            "plane": {"enum": ["front", "top", "right"]},
            "coordinate_system": {"const": "sketch-local"},
            "model_to_sketch_transform": {
                "type": "array",
                "items": NUMBER,
                "minItems": 16,
                "maxItems": 16,
            },
            "dimensions": _object(
                {
                    "unit": {"const": "millimeter"},
                    "width": NUMBER,
                    "height": NUMBER,
                    "center_x": NUMBER,
                    "center_y": NUMBER,
                },
                ("unit", "width", "height", "center_x", "center_y"),
            ),
            "sketch": _object(
                {
                    "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
                    "name": STRING,
                    "type": {"const": "ProfileFeature"},
                    "constraint_status": INTEGER,
                    "dimensions_created": {"const": False},
                },
                ("name", "type", "constraint_status", "dimensions_created"),
            ),
            "geometry_verification": _object(
                {
                    "passed": BOOL,
                    "method": {"const": "sketch-local-line-bounds"},
                    "segment_count": INTEGER,
                    "profile_segment_count": INTEGER,
                    "actual_bounds_mm": {
                        "anyOf": [
                            _object(
                                {
                                    k: NUMBER
                                    for k in ("min_x", "max_x", "min_y", "max_y")
                                },
                                ("min_x", "max_x", "min_y", "max_y"),
                            ),
                            {"type": "null"},
                        ]
                    },
                    "absolute_tolerance_mm": NUMBER,
                },
                (
                    "passed",
                    "method",
                    "segment_count",
                    "profile_segment_count",
                    "actual_bounds_mm",
                    "absolute_tolerance_mm",
                ),
            ),
            "editing": BOOL,
        },
        (
            "plane",
            "coordinate_system",
            "model_to_sketch_transform",
            "dimensions",
            "sketch",
            "geometry_verification",
            "editing",
            "document",
        ),
    ),
    "document.create": (
        {"created": {"const": True}, "template": PART_TEMPLATE},
        ("created", "template", "document"),
    ),
    "document.open": (
        {
            "path": STRING,
            "read_only": BOOL,
            "configuration": NULLABLE_STRING,
            "api_errors": INTEGER,
            "api_warnings": INTEGER,
        },
        (
            "document",
            "path",
            "read_only",
            "configuration",
            "api_errors",
            "api_warnings",
        ),
    ),
    "document.list": (
        {
            "current_document_id": NULLABLE_STRING,
            "documents": {"type": "array", "items": DOCUMENT},
            "count": INTEGER,
        },
        ("session_id", "current_document_id", "documents", "count"),
    ),
    "document.use": ({}, ("session_id", "document")),
    "document.lease.acquire": ({"lease": LEASE}, ("session_id", "document", "lease")),
    "document.lease.status": (
        {
            "lease": {"anyOf": [LEASE, {"type": "null"}]},
            "leased": BOOL,
            "owned_by_session": BOOL,
        },
        ("session_id", "document", "lease", "leased", "owned_by_session"),
    ),
    "document.lease.renew": ({"lease": LEASE}, ("session_id", "lease")),
    "document.lease.release": (
        {"lease": LEASE, "released": BOOL},
        ("session_id", "lease", "released"),
    ),
    "document.inspect": (
        {"needs_rebuild": INTEGER, "structure": STRUCTURE},
        ("document", "needs_rebuild"),
    ),
    "document.close": (
        {"discard": BOOL, "closed": BOOL},
        ("document", "discard", "closed"),
    ),
    "document.save": (
        {
            "api_saved": BOOL,
            "save_errors": INTEGER,
            "save_error_names": STRING_LIST,
            "save_warnings": INTEGER,
            "save_warning_names": STRING_LIST,
            "document_after": DOCUMENT,
        },
        (
            "document",
            "document_after",
            "api_saved",
            "save_errors",
            "save_error_names",
            "save_warnings",
            "save_warning_names",
        ),
    ),
    "document.diagnose": (
        {"needs_rebuild": INTEGER, "diagnostics": DIAGNOSTICS},
        ("document", "needs_rebuild", "diagnostics"),
    ),
    "document.rebuild": (
        {
            "force": BOOL,
            "top_only": BOOL,
            "rebuilt": BOOL,
            "needs_rebuild_before": INTEGER,
            "needs_rebuild_after": INTEGER,
            "diagnostics": DIAGNOSTICS,
        },
        (
            "document",
            "force",
            "top_only",
            "rebuilt",
            "needs_rebuild_before",
            "needs_rebuild_after",
            "diagnostics",
        ),
    ),
    "document.render": (
        {
            "output": STRING,
            "requested_size": _object(
                {
                    **PIXEL_SIZE["properties"],
                    "unit": {"const": "pixel"},
                },
                ("width", "height", "unit"),
            ),
            "view": _object(
                {"name": STRING, "standard_id": {"type": ["integer", "null"]}},
                ("name", "standard_id"),
            ),
            "fit": BOOL,
            "api_saved": BOOL,
            "actual_size": {"anyOf": [PIXEL_SIZE, {"type": "null"}]},
            "artifact": ARTIFACT,
        },
        (
            "document",
            "output",
            "requested_size",
            "view",
            "fit",
            "api_saved",
            "actual_size",
            "artifact",
        ),
    ),
    "document.export": (
        {"output": STRING, "artifact": ARTIFACT},
        ("output", "artifact"),
    ),
    "part.create-box": (
        {
            "output": STRING,
            "dimensions": _object(
                {
                    "unit": {"const": "millimeter"},
                    "width": NUMBER,
                    "height": NUMBER,
                    "depth": NUMBER,
                },
                ("unit", "width", "height", "depth"),
            ),
            "template": PART_TEMPLATE,
            "rebuilt": BOOL,
            "diagnostics": DIAGNOSTICS,
            "bodies": BODIES,
            "geometry_verification": _object(
                {
                    "passed": BOOL,
                    "method": STRING,
                    "expected_size_mm": VECTOR,
                    "actual_size_mm": {"anyOf": [VECTOR, {"type": "null"}]},
                    "absolute_tolerance_mm": NUMBER,
                    "note": STRING,
                },
                (
                    "passed",
                    "method",
                    "expected_size_mm",
                    "actual_size_mm",
                    "absolute_tolerance_mm",
                    "note",
                ),
            ),
            "save_errors": INTEGER,
            "save_warnings": {"type": ["integer", "null"]},
            "saved": BOOL,
            "feature": _object({"name": STRING, "type": STRING}, ("name", "type")),
        },
        (
            "output",
            "dimensions",
            "template",
            "rebuilt",
            "diagnostics",
            "bodies",
            "geometry_verification",
            "save_errors",
            "save_warnings",
            "saved",
            "document",
            "feature",
        ),
    ),
}


def operation_result_schema(name: str) -> Dict[str, Any]:
    """Describe response.result; dispatch failures can instead have no result."""

    if name == "daemon.health":
        return load_schema("capabilities")
    if name == "daemon.shutdown":
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://swcli.dev/schema/v1/results/daemon.shutdown.schema.json",
            **_object(
                {"stopping": {"const": True}, "host_already_disconnected": BOOL},
                ("stopping",),
            ),
        }
    fields, success_required = _RESULT_FIELDS[name]
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://swcli.dev/schema/v1/results/{name}.schema.json",
        "title": f"SWCLI {name} result",
        **_object(
            {
                "ok": BOOL,
                "action": {"const": name},
                "document": DOCUMENT,
                "session_id": STRING,
                "warnings": WARNINGS,
                "error": ERROR,
                **fields,
            },
            ("ok", "action"),
        ),
        "if": {"properties": {"ok": {"const": True}}},
        "then": {"required": list(success_required), "not": {"required": ["error"]}},
        "else": {"required": ["error"]},
    }
    if name in (
        "document.lease.acquire",
        "document.lease.renew",
        "document.lease.release",
    ):
        schema["then"]["properties"] = {"lease": {"required": ["lease_id"]}}
    if name == "feature.extrude":
        schema["then"]["properties"] = {
            "rebuilt": {"const": True},
            "diagnostics": {"properties": {"healthy": {"const": True}}},
            "geometry_verification": {"properties": {"passed": {"const": True}}},
        }
    if name == "sketch.rectangle":
        schema["then"]["properties"] = {
            "editing": {"const": False},
            "sketch": {"required": ["sketch_id"]},
            "geometry_verification": {"properties": {"passed": {"const": True}}},
        }
    if name in ("document.render", "document.export"):
        schema["properties"]["artifact"] = deepcopy(ARTIFACT)
        artifact = schema["properties"]["artifact"]
        if name == "document.render":
            artifact["properties"]["kind"] = {"const": "image"}
            artifact["properties"]["media_type"] = {"const": "image/bmp"}
            artifact["required"].append("media_type")
        else:
            artifact["properties"]["kind"] = {"const": "cad-export"}
            artifact["required"].append("format")
    return deepcopy(schema)


@lru_cache(maxsize=32)
def _validator(name: str):
    # Lazy import keeps help/version independent of validator import costs.
    from jsonschema import Draft202012Validator
    from .operation_schemas import OPERATION_CATALOG

    return Draft202012Validator(OPERATION_CATALOG[name].result)


class OperationResultInvalid(RuntimeError):
    """An adapter returned a result outside its advertised contract."""


def validate_operation_result(name: str, result: Any) -> None:
    error = next(_validator(name).iter_errors(result), None)
    if error is not None:
        path = ".".join(str(item) for item in error.absolute_path) or "result"
        raise OperationResultInvalid(f"{name}: {path}: {error.message}")
