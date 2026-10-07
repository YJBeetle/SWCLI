"""Contracts for operation results, distinct from transport error envelopes."""

from copy import deepcopy
from functools import lru_cache
import json
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
    "document.measure": (
        {
            "scope": {"const": "sum-of-solid-bodies"},
            "coordinate_system": {"const": "part-model"},
            "method": {"const": "native-body-mass-properties"},
            "metrics": _object(
                {
                    "solid_body_count": {"type": "integer", "minimum": 1},
                    "volume_mm3": {"type": "number", "exclusiveMinimum": 0},
                    "surface_area_mm2": {"type": "number", "exclusiveMinimum": 0},
                    "centroid_mm": VECTOR,
                },
                ("solid_body_count", "volume_mm3", "surface_area_mm2", "centroid_mm"),
            ),
            "bodies": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    {
                        "index": {"type": "integer", "minimum": 0},
                        "volume_mm3": {"type": "number", "exclusiveMinimum": 0},
                        "surface_area_mm2": {"type": "number", "exclusiveMinimum": 0},
                        "centroid_mm": VECTOR,
                    },
                    ("index", "volume_mm3", "surface_area_mm2", "centroid_mm"),
                ),
            },
        },
        ("document", "scope", "coordinate_system", "method", "metrics", "bodies"),
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
    "document.save-as": (
        {
            "output": STRING,
            "document_before": DOCUMENT,
            "api_saved": BOOL,
            "save_errors": INTEGER,
            "save_error_names": STRING_LIST,
            "save_warnings": {"type": "null"},
            "file_verification": _object(
                {"non_empty": BOOL, "minimum_size_valid": BOOL},
                ("non_empty", "minimum_size_valid"),
            ),
            "artifact": _object(
                {
                    "kind": {"const": "native-document"},
                    "format": {"const": "SLDPRT"},
                    "path": STRING,
                    "size_bytes": {"type": "integer", "minimum": 512},
                },
                ("kind", "format", "path", "size_bytes"),
            ),
        },
        (
            "output",
            "document_before",
            "document",
            "api_saved",
            "save_errors",
            "save_error_names",
            "save_warnings",
            "file_verification",
            "artifact",
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


_SKETCH_SEGMENT_GEOMETRY = {
    "oneOf": [
        {"type": "null"},
        _object(
            {"kind": {"const": "line"}, "start_mm": VECTOR, "end_mm": VECTOR},
            ("kind", "start_mm", "end_mm"),
        ),
        {
            **_object(
                {
                    "kind": {"const": "arc"},
                    "complete_circle": BOOL,
                    "radius_mm": {"type": "number", "exclusiveMinimum": 0},
                    "center_mm": VECTOR,
                    "start_mm": VECTOR,
                    "end_mm": VECTOR,
                },
                ("kind", "complete_circle", "radius_mm", "center_mm"),
            ),
            "if": {"properties": {"complete_circle": {"const": False}}},
            "then": {"required": ["start_mm", "end_mm"]},
        },
    ]
}
_RESULT_FIELDS["sketch.inspect"] = (
    {
        "sketch": _object(
            {
                "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
                "name": STRING,
                "type": {"const": "ProfileFeature"},
                "constraint_status": INTEGER,
                "absorbed": BOOL,
                "owner": {
                    "oneOf": [
                        {"type": "null"},
                        _object({"name": STRING, "type": STRING}, ("name", "type")),
                    ]
                },
            },
            ("sketch_id", "name", "type", "constraint_status", "absorbed", "owner"),
        ),
        "editing": BOOL,
        "coordinate_system": {"const": "sketch-local"},
        "unit": {"const": "millimeter"},
        "model_to_sketch_transform": {
            "type": "array",
            "items": NUMBER,
            "minItems": 16,
            "maxItems": 16,
        },
        "segments": {
            "type": "array",
            "items": _object(
                {
                    "index": {"type": "integer", "minimum": 0},
                    "type_code": INTEGER,
                    "construction": BOOL,
                    "geometry": _SKETCH_SEGMENT_GEOMETRY,
                },
                ("index", "type_code", "construction", "geometry"),
            ),
        },
        "segment_count": {"type": "integer", "minimum": 0},
        "profile_segment_count": {"type": "integer", "minimum": 0},
        "geometry_complete": BOOL,
    },
    (
        "document",
        "sketch",
        "editing",
        "coordinate_system",
        "unit",
        "model_to_sketch_transform",
        "segments",
        "segment_count",
        "profile_segment_count",
        "geometry_complete",
    ),
)


_CUT_FIELDS, _CUT_REQUIRED = deepcopy(_RESULT_FIELDS["feature.extrude"])
del _CUT_FIELDS["merge"]
_CUT_FIELDS["affected_scope"] = {"const": "all-solid-bodies"}
for _measurement_phase in ("measurement_before", "measurement_after"):
    _CUT_FIELDS[_measurement_phase] = deepcopy(
        _RESULT_FIELDS["document.measure"][0]["metrics"]
    )
_CUT_FIELDS["geometry_verification"] = _object(
    {
        "passed": BOOL,
        "method": {"const": "native-cut-definition-and-volume"},
        "actual_depth_mm": NUMBER,
        "actual_reverse": BOOL,
        "native_reverse_direction": BOOL,
        "end_condition": INTEGER,
        "both_directions": BOOL,
        "volume_removed_mm3": NUMBER,
        "minimum_volume_change_mm3": NUMBER,
        "absolute_depth_tolerance_mm": NUMBER,
    },
    (
        "passed",
        "method",
        "actual_depth_mm",
        "actual_reverse",
        "native_reverse_direction",
        "end_condition",
        "both_directions",
        "volume_removed_mm3",
        "minimum_volume_change_mm3",
        "absolute_depth_tolerance_mm",
    ),
)
_RESULT_FIELDS["feature.cut-extrude"] = (
    _CUT_FIELDS,
    tuple(key for key in _CUT_REQUIRED if key != "merge")
    + ("affected_scope", "measurement_before", "measurement_after"),
)


_CIRCLE_FIELDS, _CIRCLE_REQUIRED = deepcopy(_RESULT_FIELDS["sketch.rectangle"])
_CIRCLE_FIELDS["dimensions"] = _object(
    {
        "unit": {"const": "millimeter"},
        "radius": NUMBER,
        "center_x": NUMBER,
        "center_y": NUMBER,
    },
    ("unit", "radius", "center_x", "center_y"),
)
_CIRCLE_FIELDS["geometry_verification"] = _object(
    {
        "passed": BOOL,
        "method": {"const": "sketch-local-circle"},
        "segment_count": INTEGER,
        "profile_segment_count": INTEGER,
        "complete_circle": BOOL,
        "actual_radius_mm": {"type": ["number", "null"]},
        "actual_center_mm": {"anyOf": [VECTOR, {"type": "null"}]},
        "absolute_tolerance_mm": NUMBER,
    },
    (
        "passed",
        "method",
        "segment_count",
        "profile_segment_count",
        "complete_circle",
        "actual_radius_mm",
        "actual_center_mm",
        "absolute_tolerance_mm",
    ),
)
_RESULT_FIELDS["sketch.circle"] = (_CIRCLE_FIELDS, _CIRCLE_REQUIRED)


_DIMENSION = _object(
    {
        "dimension_id": {"type": "string", "pattern": "^m-[a-z0-9]{6}$"},
        "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
        "kind": {"const": "diameter"},
        "unit": {"const": "millimeter"},
        "value": {"type": ["number", "null"]},
        "driven_state": INTEGER,
        "read_only": BOOL,
        "configuration": STRING,
        "native_name": STRING,
    },
)
_DIMENSION_CONTROL_FIELDS = {
    "equation_control": _object(
        {
            "controlled": BOOL,
            "equation_indices": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0},
            },
        },
        ("controlled", "equation_indices"),
    ),
    "design_table_controlled": BOOL,
}
_RESULT_FIELDS["sketch.dimension-diameter"] = (
    {
        "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
        "diameter_mm": NUMBER,
        "dimension": _DIMENSION,
        "native_status": INTEGER,
        "geometry_verification": deepcopy(_CIRCLE_FIELDS["geometry_verification"]),
        "constraint_status": INTEGER,
        "editing": BOOL,
    },
    (
        "document",
        "sketch_id",
        "dimension",
        "native_status",
        "geometry_verification",
        "constraint_status",
        "editing",
    ),
)
_RESULT_FIELDS["dimension.inspect"] = (
    {
        "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
        "dimension": _DIMENSION,
        "geometry_verification": deepcopy(_CIRCLE_FIELDS["geometry_verification"]),
        "constraint_status": INTEGER,
        "editing": BOOL,
        **_DIMENSION_CONTROL_FIELDS,
    },
    (
        "document",
        "dimension",
        "geometry_verification",
        "constraint_status",
        "editing",
        "equation_control",
        "design_table_controlled",
    ),
)
_RESULT_FIELDS["dimension.set"] = (
    {
        "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
        "dimension": _DIMENSION,
        "value_mm": NUMBER,
        "before_value_mm": {"type": ["number", "null"]},
        "native_status": INTEGER,
        "geometry_verification": deepcopy(_CIRCLE_FIELDS["geometry_verification"]),
        "constraint_status": INTEGER,
        "editing": BOOL,
        "rebuilt": BOOL,
        "needs_rebuild": INTEGER,
        "diagnostics": DIAGNOSTICS,
        "downstream": _object(
            {
                "applicable": BOOL,
                **{
                    field: {
                        "anyOf": [
                            deepcopy(_RESULT_FIELDS["document.measure"][0]["metrics"]),
                            {"type": "null"},
                        ]
                    }
                    for field in ("measurement_before", "measurement_after")
                },
            },
            ("applicable", "measurement_before", "measurement_after"),
        ),
        **_DIMENSION_CONTROL_FIELDS,
    },
    (
        "document",
        "dimension",
        "value_mm",
        "before_value_mm",
        "native_status",
        "geometry_verification",
        "constraint_status",
        "editing",
        "rebuilt",
        "needs_rebuild",
        "diagnostics",
        "downstream",
        "equation_control",
        "design_table_controlled",
    ),
)


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
    if name == "document.save-as":
        schema["then"]["properties"] = {
            "api_saved": {"const": True},
            "save_errors": {"const": 0},
            "document": {"properties": {"modified": {"const": False}}},
            "file_verification": {
                "properties": {
                    "non_empty": {"const": True},
                    "minimum_size_valid": {"const": True},
                }
            },
        }
    if name in ("feature.extrude", "feature.cut-extrude"):
        schema["then"]["properties"] = {
            "rebuilt": {"const": True},
            "diagnostics": {"properties": {"healthy": {"const": True}}},
            "geometry_verification": {"properties": {"passed": {"const": True}}},
        }
        if name == "feature.cut-extrude":
            schema["then"]["properties"]["geometry_verification"]["properties"].update(
                {
                    "volume_removed_mm3": {"type": "number", "exclusiveMinimum": 0},
                    "end_condition": {"const": 0},
                    "both_directions": {"const": False},
                }
            )
    if name in ("sketch.rectangle", "sketch.circle"):
        schema["then"]["properties"] = {
            "editing": {"const": False},
            "sketch": {"required": ["sketch_id"]},
            "geometry_verification": {"properties": {"passed": {"const": True}}},
        }
        if name == "sketch.circle":
            schema["then"]["properties"]["geometry_verification"]["properties"].update(
                {
                    "complete_circle": {"const": True},
                    "profile_segment_count": {"const": 1},
                    "actual_radius_mm": {"type": "number", "exclusiveMinimum": 0},
                    "actual_center_mm": VECTOR,
                }
            )
    if name in ("sketch.dimension-diameter", "dimension.inspect", "dimension.set"):
        schema["then"]["properties"] = {
            "dimension": {
                "required": list(_DIMENSION["properties"]),
                "properties": {"value": {"type": "number", "exclusiveMinimum": 0}},
            }
        }
        if name != "dimension.inspect":
            schema["then"]["properties"].update(
                {
                    "native_status": {"const": 0},
                    "editing": {"const": False},
                    "geometry_verification": {
                        "properties": {
                            "passed": {"const": True},
                            "complete_circle": {"const": True},
                            "profile_segment_count": {"const": 1},
                            "actual_radius_mm": {
                                "type": "number",
                                "exclusiveMinimum": 0,
                            },
                            "actual_center_mm": VECTOR,
                        }
                    },
                }
            )
            schema["then"]["properties"]["dimension"]["properties"].update(
                {"driven_state": {"const": 2}, "read_only": {"const": False}}
            )
        if name == "dimension.set":
            schema["then"]["properties"].update(
                {
                    "value_mm": {"type": "number", "exclusiveMinimum": 0},
                    "before_value_mm": {"type": "number", "exclusiveMinimum": 0},
                    "rebuilt": {"const": True},
                    "needs_rebuild": {"const": 0},
                    "diagnostics": {
                        "properties": {
                            "healthy": {"const": True},
                            "truncated": {"const": False},
                        }
                    },
                    "equation_control": {
                        "properties": {
                            "controlled": {"const": False},
                            "equation_indices": {"maxItems": 0},
                        }
                    },
                    "design_table_controlled": {"const": False},
                    "downstream": {
                        "if": {"properties": {"applicable": {"const": True}}},
                        "then": {
                            "properties": {
                                field: {"type": "object"}
                                for field in (
                                    "measurement_before",
                                    "measurement_after",
                                )
                            }
                        },
                    },
                }
            )
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
    # jsonschema accepts Python NaN/Infinity as numbers; wire JSON does not.
    # Check the actual UTF-8 encoding too, so malformed native text cannot make
    # a later socket write fail instead of returning a structured adapter error.
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise OperationResultInvalid(
            f"{name}: result is not finite UTF-8 JSON: {exc}"
        ) from exc
    error = next(_validator(name).iter_errors(result), None)
    if error is not None:
        path = ".".join(str(item) for item in error.absolute_path) or "result"
        raise OperationResultInvalid(f"{name}: {path}: {error.message}")
