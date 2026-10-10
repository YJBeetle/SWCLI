"""Contracts for operation results, distinct from transport error envelopes."""

from copy import deepcopy
from functools import lru_cache
import json
from math import isclose
from typing import Any, Dict

from .protocol import load_schema
from .entity_contracts import (
    entity_result_fields, entity_success_conditions, without_entity_ids, validate_entity_semantics,
)


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
            "feature": _object(
                {
                    "name": STRING,
                    "type": STRING,
                    "feature_id": {"type": "string", "pattern": "^f-[a-z0-9]{6}$"},
                },
                ("name", "type"),
            ),
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
                    "format": {"enum": ["SLDPRT", "SLDASM"]},
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
_RESULT_FIELDS["sketch.list"] = (
    {
        "sketches": {
            "type": "array",
            "items": deepcopy(_RESULT_FIELDS["sketch.inspect"][0]["sketch"]),
        },
        "count": {"type": "integer", "minimum": 0},
    },
    ("document", "sketches", "count"),
)

_FEATURE_DESCRIPTOR = _object(
    {
        "feature_id": {"type": "string", "pattern": "^f-[a-z0-9]{6}$"},
        "name": {"type": "string", "minLength": 1},
        "type": {"type": "string", "minLength": 1},
        "native_type": {"enum": ["Boss", "Extrusion", "BaseBody", "Cut"]},
        "kind": {"enum": ["boss-extrude", "cut-extrude"]},
    },
    ("feature_id", "name", "type", "native_type", "kind"),
)
_FEATURE_STATE = _object(
    {
        "configuration": {"type": "string", "minLength": 1},
        "update_stamp": INTEGER,
        "modified": BOOL,
        "editing": BOOL,
        "foreground_present": BOOL,
    },
    ("configuration", "update_stamp", "modified", "editing", "foreground_present"),
)
_FEATURE_OBSERVATION = _object(
    {"before": _FEATURE_STATE, "after": _FEATURE_STATE, "unchanged": BOOL},
    ("before", "unchanged"),
)
_FEATURE_DEFINITION_FIELDS = {
    "depth_mm": {"type": "number", "minimum": 0},
    "end_condition": INTEGER,
    "reverse_direction": BOOL,
    "both_directions": BOOL,
    "thin": BOOL,
    "from_type": INTEGER,
    "forward_draft": BOOL,
    "reverse_draft": BOOL,
}
_RESULT_FIELDS["feature.list"] = (
    {
        "scope": {"const": "part-extrusions"},
        "features": {"type": "array", "items": _FEATURE_DESCRIPTOR},
        "count": {"type": "integer", "minimum": 0},
        "observation": _FEATURE_OBSERVATION,
    },
    ("document", "scope", "features", "count", "observation"),
)
_RESULT_FIELDS["feature.inspect"] = (
    {
        "feature": _FEATURE_DESCRIPTOR,
        "definition": {
            "oneOf": [
                _object(
                    {**_FEATURE_DEFINITION_FIELDS, branch: BOOL},
                    (*_FEATURE_DEFINITION_FIELDS, branch),
                )
                for branch in ("merge", "feature_scope")
            ]
        },
        "observation": _FEATURE_OBSERVATION,
    },
    ("document", "feature", "definition", "observation"),
)

_FEATURE_SELECTION_ACCESS = _object(
    {
        key: BOOL
        for key in (
            "attempted",
            "acquired",
            "release_attempted",
            "released",
            "state_restored",
        )
    },
    ("attempted", "acquired", "release_attempted", "released", "state_restored"),
)
_FEATURE_SELECTION_CHECK = {
    **_object(
        {
            "ok": BOOL,
            "selection_access": _FEATURE_SELECTION_ACCESS,
            "observation": _object(
                {
                    "before": _FEATURE_STATE,
                    "after": _FEATURE_STATE,
                    "update_stamp_changed": BOOL,
                },
                ("before",),
            ),
            "error": ERROR,
            "warnings": WARNINGS,
        },
        ("ok", "selection_access"),
    ),
    "if": {"properties": {"ok": {"const": True}}},
    "then": {
        "required": ["observation"],
        "properties": {
            "selection_access": {
                "properties": {
                    key: {"const": True}
                    for key in (
                        "attempted",
                        "acquired",
                        "release_attempted",
                        "released",
                        "state_restored",
                    )
                }
            },
            "observation": {"required": ["after", "update_stamp_changed"]},
        },
        "not": {"required": ["error"]},
    },
    "else": {"required": ["error"]},
}
_FEATURE_DEPTH_MUTATION = _object(
    {
        key: BOOL
        for key in (
            "staging_attempted",
            "configuration_scope_applied",
            "commit_attempted",
            "committed",
        )
    },
    (
        "staging_attempted",
        "configuration_scope_applied",
        "commit_attempted",
        "committed",
    ),
)
_FEATURE_DEPTH_METRICS = _object(
    {
        "solid_body_count": {"const": 1},
        "volume_mm3": {"type": "number", "exclusiveMinimum": 0},
        "surface_area_mm2": {"type": "number", "exclusiveMinimum": 0},
        "centroid_mm": VECTOR,
    },
    ("solid_body_count", "volume_mm3", "surface_area_mm2", "centroid_mm"),
)
_RESULT_FIELDS["feature.set-depth"] = (
    {
        "feature_id": _FEATURE_DESCRIPTOR["properties"]["feature_id"],
        "feature": _FEATURE_DESCRIPTOR,
        "mutation": _FEATURE_DEPTH_MUTATION,
        "requested_depth_mm": {"type": "number", "exclusiveMinimum": 0},
        "before_depth_mm": {"type": "number", "exclusiveMinimum": 0},
        "depth_changed": {"type": ["boolean", "null"]},
        "modification_may_have_happened": BOOL,
        "definition_after": _RESULT_FIELDS["feature.inspect"][0]["definition"],
        "measurement_before": _FEATURE_DEPTH_METRICS,
        "measurement_after": _FEATURE_DEPTH_METRICS,
        "final_state": _FEATURE_STATE,
        "rebuilt": BOOL,
        "verification": _object(
            {
                "passed": BOOL,
                "method": {
                    "enum": [
                        "guarded-equal-depth",
                        "native-blind-depth-preserved-profile-and-scope",
                    ]
                },
                "absolute_tolerance_mm": {"const": 1e-6},
            },
            ("passed", "method", "absolute_tolerance_mm"),
        ),
        "selection_checks": _object(
            {
                "preflight": _FEATURE_SELECTION_CHECK,
                "postflight": _FEATURE_SELECTION_CHECK,
            },
        ),
    },
    (
        "document",
        "feature_id",
        "feature",
        "mutation",
        "requested_depth_mm",
        "before_depth_mm",
        "depth_changed",
        "definition_after",
        "measurement_before",
        "measurement_after",
        "final_state",
        "verification",
        "selection_checks",
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


_RECTANGLE_GEOMETRY = _object(
    {
        "width_mm": {"type": "number", "exclusiveMinimum": 0},
        "height_mm": {"type": "number", "exclusiveMinimum": 0},
        "center_mm": VECTOR,
        "bounds_mm": {"type": "array", "items": NUMBER, "minItems": 4, "maxItems": 4},
        "profile_segment_count": {"const": 4},
        "construction_segment_count": {"const": 2},
        "max_abs_z_mm": {"type": "number", "minimum": 0},
    },
    (
        "width_mm",
        "height_mm",
        "center_mm",
        "bounds_mm",
        "profile_segment_count",
        "construction_segment_count",
        "max_abs_z_mm",
    ),
)
_SKETCH_ENTITY_SNAPSHOT_KEY = {
    "type": "array",
    "items": {"type": "integer", "minimum": -(2**31), "maximum": 2**31 - 1},
    "minItems": 2,
    "maxItems": 2,
}
_RECTANGLE_CENTER = _object(
    {
        "method": {"const": "sketch-local-center-relations"},
        "attached_to_both_diagonals": {"const": True},
        "fixed": BOOL,
        "native_point_id": _SKETCH_ENTITY_SNAPSHOT_KEY,
        "native_diagonal_ids": {
            "type": "array",
            "items": _SKETCH_ENTITY_SNAPSHOT_KEY,
            "minItems": 2,
            "maxItems": 2,
            "uniqueItems": True,
        },
        "identity_scope": {"const": "exact-sketch-and-entity-kind-snapshot"},
        "geometry": _RECTANGLE_GEOMETRY,
    },
    (
        "method",
        "attached_to_both_diagonals",
        "fixed",
        "native_point_id",
        "native_diagonal_ids",
        "identity_scope",
        "geometry",
    ),
)
_RESULT_FIELDS["sketch.fix-center"] = (
    {
        "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
        "created": BOOL,
        "center_before": _RECTANGLE_CENTER,
        "center_in_edit": _RECTANGLE_CENTER,
        "center": _RECTANGLE_CENTER,
        "constraint_status_before": {"type": "integer", "enum": [2, 3]},
        "constraint_status": {"type": "integer", "enum": [2, 3]},
        "editing": BOOL,
        "modification_may_have_happened": {"const": True},
        "geometry_verification": _object(
            {
                "method": {"const": "sketch-local-rectangle"},
                "passed": BOOL,
                "size_matched": BOOL,
                "center_preserved": BOOL,
                "expected_width_mm": {"type": "number", "exclusiveMinimum": 0},
                "expected_height_mm": {"type": "number", "exclusiveMinimum": 0},
                "expected_center_mm": VECTOR,
                "actual": _RECTANGLE_GEOMETRY,
                "absolute_tolerance_mm": {"const": 1e-6},
            },
            (
                "method",
                "passed",
                "size_matched",
                "center_preserved",
                "expected_width_mm",
                "expected_height_mm",
                "expected_center_mm",
                "actual",
                "absolute_tolerance_mm",
            ),
        ),
    },
    (
        "document",
        "sketch_id",
        "created",
        "center_before",
        "center",
        "constraint_status_before",
        "constraint_status",
        "editing",
        "geometry_verification",
    ),
)


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


def _linear_dimension(kind):
    schema = deepcopy(_DIMENSION)
    schema["properties"]["kind"] = {"const": kind}
    return schema


# Size operations also accept rectangles without the two center diagonals.
# Requiring those belongs to explicit center fixing, not size control.
_RECTANGLE_SIZE_GEOMETRY = deepcopy(_RECTANGLE_GEOMETRY)
_RECTANGLE_SIZE_GEOMETRY["properties"]["construction_segment_count"] = {
    "type": "integer",
    "minimum": 0,
}
_RECTANGLE_SIZE_VERIFICATION = deepcopy(
    _RESULT_FIELDS["sketch.fix-center"][0]["geometry_verification"]
)
_RECTANGLE_SIZE_VERIFICATION["properties"]["actual"] = _RECTANGLE_SIZE_GEOMETRY
_LINEAR_PAIR = _object({kind: _linear_dimension(kind) for kind in ("width", "height")})
_RESULT_FIELDS["sketch.dimension-rectangle"] = (
    {
        "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
        "dimensions": _LINEAR_PAIR,
        "native_status": _object({"width": INTEGER, "height": INTEGER}),
        "geometry_before": _RECTANGLE_SIZE_GEOMETRY,
        "steps": _object(
            {kind: _RECTANGLE_SIZE_VERIFICATION for kind in ("width", "height")}
        ),
        "geometry_verification": _RECTANGLE_SIZE_VERIFICATION,
        "constraint_status": INTEGER,
        "editing": BOOL,
        "modification_may_have_happened": {"const": True},
    },
    (
        "document",
        "sketch_id",
        "dimensions",
        "native_status",
        "geometry_before",
        "steps",
        "geometry_verification",
        "constraint_status",
        "editing",
    ),
)
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
_DIMENSION_DISCOVERY_STATE = _object(
    {
        "update_stamp": INTEGER,
        "configuration": {"type": "string", "minLength": 1, "pattern": r"\S"},
        "editing": BOOL,
    },
    ("update_stamp", "configuration", "editing"),
)
_LINEAR_INSPECT_GEOMETRY = _object(
    {
        "method": {"const": "sketch-local-rectangle"},
        "passed": BOOL,
        "dimension_kind": {"enum": ["width", "height"]},
        "expected_value_mm": {"type": "number", "exclusiveMinimum": 0},
        "actual_width_mm": {"type": "number", "exclusiveMinimum": 0},
        "actual_height_mm": {"type": "number", "exclusiveMinimum": 0},
        "actual_center_mm": VECTOR,
        "bounds_mm": _RECTANGLE_SIZE_GEOMETRY["properties"]["bounds_mm"],
        "profile_segment_count": {"const": 4},
        "construction_segment_count": {"type": "integer", "minimum": 0},
        "max_abs_z_mm": {"type": "number", "minimum": 0},
        "absolute_tolerance_mm": {"const": 1e-6},
    },
    (
        "method",
        "passed",
        "dimension_kind",
        "expected_value_mm",
        "actual_width_mm",
        "actual_height_mm",
        "actual_center_mm",
        "bounds_mm",
        "profile_segment_count",
        "construction_segment_count",
        "max_abs_z_mm",
        "absolute_tolerance_mm",
    ),
)
_LINEAR_OBSERVATION = _object(
    {
        "before": _DIMENSION_DISCOVERY_STATE,
        "after": _DIMENSION_DISCOVERY_STATE,
        "configuration_matched": BOOL,
        "unchanged": BOOL,
    }
)
_RESULT_FIELDS["dimension.discover-diameter"] = (
    {
        **deepcopy(_RESULT_FIELDS["dimension.inspect"][0]),
        "observation": _object(
            {
                "before": _DIMENSION_DISCOVERY_STATE,
                "after": _DIMENSION_DISCOVERY_STATE,
                "configuration_matched": BOOL,
                "unchanged": BOOL,
            }
        ),
    },
    _RESULT_FIELDS["dimension.inspect"][1] + ("sketch_id", "observation"),
)
_RESULT_FIELDS["dimension.discover-rectangle"] = (
    {
        "sketch_id": {"type": "string", "pattern": "^s-[a-z0-9]{6}$"},
        "dimensions": _LINEAR_PAIR,
        "geometry_verification": _RECTANGLE_SIZE_VERIFICATION,
        "constraint_status": INTEGER,
        "editing": BOOL,
        "observation": _LINEAR_OBSERVATION,
    },
    (
        "document",
        "sketch_id",
        "dimensions",
        "geometry_verification",
        "constraint_status",
        "editing",
        "observation",
        "inspections",
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


_RESULT_FIELDS.update(entity_result_fields())


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
            "document": {"properties": {"modified": {"const": False}, "type": {"enum": [1, 2]}}},
            "file_verification": {
                "properties": {
                    "non_empty": {"const": True},
                    "minimum_size_valid": {"const": True},
                }
            },
        }
        schema["then"]["allOf"] = [
            {
                "if": {"properties": {"document": {"properties": {"type": {"const": kind}}}}},
                "then": {"properties": {"artifact": {"properties": {"format": {"const": file_format}}}}},
            }
            for kind, file_format in ((1, "SLDPRT"), (2, "SLDASM"))
        ]
    if name in ("feature.list", "feature.inspect", "entity.list", "entity.inspect"):
        schema["then"]["properties"] = {
            "observation": {
                "required": ["after"],
                "properties": {"unchanged": {"const": True}},
            }
        }
    if name in ("entity.list", "entity.inspect"):
        schema["then"]["allOf"] = entity_success_conditions(name)
    if name == "feature.set-depth":
        schema["required"].extend(["feature_id", "mutation"])
        schema["then"]["properties"] = {
            "depth_changed": BOOL,
            "verification": {"properties": {"passed": {"const": True}}},
            "final_state": {
                "properties": {
                    "editing": {"const": False},
                    "foreground_present": {"const": True},
                }
            },
            "selection_checks": {
                "required": ["preflight"],
                "properties": {"preflight": {"properties": {"ok": {"const": True}}}},
            },
        }
    if name in ("feature.extrude", "feature.cut-extrude"):
        schema["then"]["properties"] = {
            "feature": {"required": ["feature_id"]},
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
    if name == "sketch.fix-center":
        schema["then"].update(
            properties={
                "editing": {"const": False},
                "center": {"properties": {"fixed": {"const": True}}},
                "center_in_edit": {"properties": {"fixed": {"const": True}}},
                "geometry_verification": {
                    "properties": {
                        field: {"const": True}
                        for field in ("passed", "size_matched", "center_preserved")
                    }
                },
            },
            allOf=[
                {
                    "if": {"properties": {"created": {"const": True}}},
                    "then": {
                        "required": ["center_in_edit"],
                        "properties": {
                            "constraint_status_before": {"const": 2},
                            "center_before": {
                                "properties": {"fixed": {"const": False}}
                            },
                        },
                    },
                    "else": {
                        "properties": {
                            "center_before": {"properties": {"fixed": {"const": True}}},
                        },
                    },
                }
            ],
            **{
                "not": {
                    "anyOf": [
                        {"required": ["error"]},
                        {"required": ["modification_may_have_happened"]},
                    ]
                }
            },
        )
    if name == "sketch.dimension-rectangle":
        verified = {
            "properties": {
                field: {"const": True}
                for field in ("passed", "size_matched", "center_preserved")
            }
        }
        schema["then"]["properties"] = {
            "editing": {"const": False},
            "dimensions": {
                "required": ["width", "height"],
                "properties": {
                    kind: {
                        "required": list(_DIMENSION["properties"]),
                        "properties": {
                            "value": {"type": "number", "exclusiveMinimum": 0},
                            "driven_state": {"const": 2},
                            "read_only": {"const": False},
                        },
                    }
                    for kind in ("width", "height")
                },
            },
            "native_status": {
                "required": ["width", "height"],
                "properties": {kind: {"const": 0} for kind in ("width", "height")},
            },
            "steps": {
                "required": ["width", "height"],
                "properties": {kind: verified for kind in ("width", "height")},
            },
            "geometry_verification": verified,
        }
        schema["then"]["not"] = {
            "anyOf": [
                {"required": ["error"]},
                {"required": ["modification_may_have_happened"]},
            ]
        }
        schema["else"]["properties"] = {
            "dimensions": {
                "properties": {
                    kind: {"not": {"required": ["dimension_id"]}}
                    for kind in ("width", "height")
                }
            }
        }
    if name in (
        "sketch.dimension-diameter",
        "dimension.discover-diameter",
        "dimension.inspect",
        "dimension.set",
    ):
        schema["then"]["properties"] = {
            "dimension": {
                "required": list(_DIMENSION["properties"]),
                "properties": {"value": {"type": "number", "exclusiveMinimum": 0}},
            }
        }
        if name not in ("dimension.inspect", "dimension.discover-diameter"):
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
        if name == "dimension.discover-diameter":
            schema["then"]["properties"].update(
                {
                    "document": {"properties": {"update_stamp": INTEGER}},
                    "observation": {
                        "required": [
                            "before",
                            "after",
                            "configuration_matched",
                            "unchanged",
                        ],
                        "properties": {
                            "configuration_matched": {"const": True},
                            "unchanged": {"const": True},
                        },
                    },
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
                {
                    "driven_state": {"type": "integer", "enum": [0, 1, 2]},
                    "configuration": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                    "native_name": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                }
            )
            # A failed read must not claim that a native handle was recovered.
            schema["else"]["properties"] = {
                "dimension": {"not": {"required": ["dimension_id"]}}
            }
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
    if name in ("dimension.inspect", "dimension.set"):
        schema = _extend_linear_result_schema(name, schema)
    if name == "dimension.discover-rectangle":
        schema["properties"]["inspections"] = _object(
            {
                kind: _native_linear_inspection_schema(kind)
                for kind in ("width", "height")
            }
        )
        schema["then"]["properties"] = {
            "document": {"properties": {"update_stamp": INTEGER}},
            "dimensions": {
                "required": ["width", "height"],
                "properties": {
                    kind: {"required": list(_DIMENSION["properties"])}
                    for kind in ("width", "height")
                },
            },
            "inspections": {
                "required": ["width", "height"],
                "properties": {
                    kind: {
                        "properties": {
                            "ok": {"const": True},
                            "geometry_verification": {
                                "properties": {"passed": {"const": True}}
                            },
                        }
                    }
                    for kind in ("width", "height")
                },
            },
            "observation": {
                "required": ["before", "after", "configuration_matched", "unchanged"],
                "properties": {
                    field: {"const": True}
                    for field in ("configuration_matched", "unchanged")
                },
            },
            "geometry_verification": {
                "properties": {
                    field: {"const": True}
                    for field in ("passed", "size_matched", "center_preserved")
                }
            },
        }
        schema["else"]["properties"] = {
            "dimensions": {
                "properties": {
                    kind: {"not": {"required": ["dimension_id"]}}
                    for kind in ("width", "height")
                }
            }
        }
    return deepcopy(schema)


def _linear_result_schema(name, diameter_schema):
    """Rectangle role contracts, also used for native readback snapshots."""
    linear = deepcopy(diameter_schema)
    linear["properties"]["dimension"] = _linear_dimension("width")
    linear["properties"]["dimension"]["properties"]["kind"] = {
        "enum": ["width", "height"]
    }
    linear["properties"]["modification_may_have_happened"] = {"const": True}
    linear["then"]["properties"]["dimension"]["properties"].update(
        driven_state={"enum": [0, 1, 2]},
        configuration={"type": "string", "minLength": 1, "pattern": r"\S"},
        native_name={"type": "string", "minLength": 1, "pattern": r"\S"},
    )
    if name == "dimension.inspect":
        linear["properties"].update(
            geometry_verification=_LINEAR_INSPECT_GEOMETRY,
            observation=_LINEAR_OBSERVATION,
        )
        linear["then"]["required"].append("observation")
        linear["then"]["properties"]["observation"] = {
            "required": ["before", "after", "configuration_matched", "unchanged"],
            "properties": {
                field: {"const": True}
                for field in ("configuration_matched", "unchanged")
            },
        }
        linear["then"]["not"] = {
            "anyOf": [
                {"required": ["error"]},
                {"required": ["modification_may_have_happened"]},
            ]
        }
    else:
        # These two are native readback snapshots, before wire IDs/document
        # context are added. They are not nested transport responses.
        observation = _linear_result_schema(
            "dimension.inspect", _diameter_inspect_schema()
        )
        for field in ("document", "dimension_id", "sketch_id"):
            if field in observation["then"]["required"]:
                observation["then"]["required"].remove(field)
        for field in ("dimension_id", "sketch_id"):
            observation["then"]["properties"]["dimension"]["required"].remove(field)
        linear["properties"].update(
            geometry_verification=_RECTANGLE_SIZE_VERIFICATION,
            before=observation,
            after=observation,
            final_state=_DIMENSION_DISCOVERY_STATE,
        )
        linear["then"]["required"].extend(["before", "after", "final_state"])
        linear["then"]["properties"]["dimension"]["properties"]["driven_state"] = {
            "const": 2
        }
        linear["then"]["properties"]["geometry_verification"] = {
            "properties": {
                field: {"const": True}
                for field in ("passed", "size_matched", "center_preserved")
            }
        }
        linear["then"]["properties"].update(
            {
                field: {
                    "properties": {
                        "ok": {"const": True},
                        "geometry_verification": {
                            "properties": {"passed": {"const": True}}
                        },
                    }
                }
                for field in ("before", "after")
            }
        )
        linear["then"]["not"] = {
            "anyOf": [
                {"required": ["error"]},
                {"required": ["modification_may_have_happened"]},
            ]
        }
    return linear


def _native_linear_inspection_schema(kind):
    schema = _linear_result_schema("dimension.inspect", _diameter_inspect_schema())
    schema["then"]["required"].remove("document")
    descriptor = schema["properties"]["dimension"]["properties"]
    descriptor["kind"] = {"const": kind}
    for field in ("dimension_id", "sketch_id"):
        del descriptor[field]
        schema["then"]["properties"]["dimension"]["required"].remove(field)
    return schema


def _diameter_inspect_schema():
    # Build the narrow original read shape directly to avoid recursive catalog
    # expansion while embedding native linear readback in a set result.
    fields, required = _RESULT_FIELDS["dimension.inspect"]
    return {
        **_object(
            {
                "ok": BOOL,
                "action": {"const": "dimension.inspect"},
                "document": DOCUMENT,
                "session_id": STRING,
                "warnings": WARNINGS,
                "error": ERROR,
                **deepcopy(fields),
            },
            ("ok", "action"),
        ),
        "if": {"properties": {"ok": {"const": True}}},
        "then": {
            "required": list(required),
            "not": {"required": ["error"]},
            "properties": {
                "dimension": {
                    "required": list(_DIMENSION["properties"]),
                    "properties": {"value": {"type": "number", "exclusiveMinimum": 0}},
                }
            },
        },
        "else": {"required": ["error"]},
    }


def _extend_linear_result_schema(name, diameter_schema):
    """Discriminated union: adding rectangle roles never weakens diameters."""
    linear = _linear_result_schema(name, diameter_schema)
    schema = deepcopy(diameter_schema)
    for key in ("if", "then", "else"):
        schema.pop(key)
    schema["properties"].update(deepcopy(linear["properties"]))
    schema["properties"]["dimension"]["properties"]["kind"] = {
        "enum": ["diameter", "width", "height"]
    }
    schema["properties"]["geometry_verification"] = {
        "oneOf": [
            diameter_schema["properties"]["geometry_verification"],
            linear["properties"]["geometry_verification"],
        ]
    }
    for branch in (diameter_schema, linear):
        for key in ("$id", "$schema", "title"):
            branch.pop(key, None)
    schema["allOf"] = [
        {
            "if": {
                "required": ["dimension"],
                "properties": {
                    "dimension": {
                        "required": ["kind"],
                        "properties": {"kind": {"enum": ["width", "height"]}},
                    }
                },
            },
            "then": linear,
            "else": diameter_schema,
        }
    ]
    return schema


@lru_cache(maxsize=32)
def _validator(name: str):
    # Lazy import keeps help/version independent of validator import costs.
    from jsonschema import Draft202012Validator
    from .operation_schemas import OPERATION_CATALOG

    return Draft202012Validator(OPERATION_CATALOG[name].result)


class OperationResultInvalid(RuntimeError):
    """An adapter returned a result outside its advertised contract."""


def _validate_result(name: str, result: Any, validator: Any) -> None:
    # jsonschema accepts Python NaN/Infinity as numbers; wire JSON does not.
    # Check the actual UTF-8 encoding too, so malformed native text cannot make
    # a later socket write fail instead of returning a structured adapter error.
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise OperationResultInvalid(
            f"{name}: result is not finite UTF-8 JSON: {exc}"
        ) from exc
    error = next(validator.iter_errors(result), None)
    if error is not None:
        path = ".".join(str(item) for item in error.absolute_path) or "result"
        raise OperationResultInvalid(f"{name}: {path}: {error.message}")


def _validate_dimension_discovery_state(result: Dict[str, Any]) -> None:
    if result["ok"] is not True:
        return
    observation = result["observation"]
    before, after = observation["before"], observation["after"]
    dimension = result["dimension"]
    if (
        before != after
        or dimension["configuration"] != before["configuration"]
        or result["editing"] != before["editing"]
        or result["document"]["update_stamp"] != after["update_stamp"]
        or ("sketch_id" in dimension and dimension["sketch_id"] != result["sketch_id"])
    ):
        raise OperationResultInvalid(
            "dimension.discover-diameter: inconsistent read-only observation state"
        )


@lru_cache(maxsize=1)
def _dimension_discovery_observation_validator():
    from jsonschema import Draft202012Validator

    schema = operation_result_schema("dimension.discover-diameter")
    # Native observations have no wire handles yet. Validate every other
    # success field before allowing registration to create/reuse an m-ID.
    required = schema["then"]["properties"]["dimension"]["required"]
    required.remove("dimension_id")
    required.remove("sketch_id")
    return Draft202012Validator(schema)


def validate_dimension_discovery_observation(result: Dict[str, Any]) -> None:
    _validate_result(
        "dimension.discover-diameter",
        result,
        _dimension_discovery_observation_validator(),
    )
    _validate_dimension_discovery_state(result)


def _validate_rectangle_creation(result: Dict[str, Any]) -> None:
    if result["ok"] is not True:
        return
    verification = result["geometry_verification"]
    before = result["geometry_before"]
    for phase, evidence in (
        ("width", result["steps"]["width"]),
        ("height", result["steps"]["height"]),
        ("final", verification),
    ):
        actual = evidence["actual"]
        expected_height = (
            before["height_mm"]
            if phase == "width"
            else verification["expected_height_mm"]
        )
        if (
            evidence["expected_width_mm"] != verification["expected_width_mm"]
            or evidence["expected_height_mm"] != expected_height
            or evidence["expected_center_mm"] != before["center_mm"]
            or any(
                not isclose(value, expected, rel_tol=0, abs_tol=1e-6)
                for value, expected in (
                    (actual["width_mm"], evidence["expected_width_mm"]),
                    (actual["height_mm"], expected_height),
                    *[
                        (actual["center_mm"][axis], before["center_mm"][axis])
                        for axis in ("x", "y", "z")
                    ],
                )
            )
        ):
            raise OperationResultInvalid(
                "sketch.dimension-rectangle: inconsistent native size/center evidence"
            )
    if (
        any(
            not isclose(
                result["dimensions"][kind]["value"],
                verification[f"expected_{kind}_mm"],
                rel_tol=0,
                abs_tol=1e-6,
            )
            or (
                "sketch_id" in result["dimensions"][kind]
                and result["dimensions"][kind]["sketch_id"] != result["sketch_id"]
            )
            for kind in ("width", "height")
        )
        or result["dimensions"]["width"]["configuration"]
        != result["dimensions"]["height"]["configuration"]
    ):
        raise OperationResultInvalid(
            "sketch.dimension-rectangle: inconsistent dimension bindings"
        )


@lru_cache(maxsize=1)
def _rectangle_creation_observation_validator():
    from jsonschema import Draft202012Validator

    schema = operation_result_schema("sketch.dimension-rectangle")
    for kind in ("width", "height"):
        required = schema["then"]["properties"]["dimensions"]["properties"][kind][
            "required"
        ]
        required.remove("dimension_id")
        required.remove("sketch_id")
    return Draft202012Validator(schema)


def validate_rectangle_creation_observation(result: Dict[str, Any]) -> None:
    _validate_result(
        "sketch.dimension-rectangle",
        result,
        _rectangle_creation_observation_validator(),
    )
    _validate_rectangle_creation(result)


def _validate_rectangle_discovery(result):
    if result["ok"] is not True:
        return
    observation, geometry = result["observation"], result["geometry_verification"]
    before, after = observation["before"], observation["after"]
    actual = geometry["actual"]
    if (
        before != after
        or result["document"]["update_stamp"] != after["update_stamp"]
        or result["editing"] != after["editing"]
    ):
        raise OperationResultInvalid(
            "dimension.discover-rectangle: inconsistent read-only state"
        )
    tokens = []
    for kind in ("width", "height"):
        descriptor = result["dimensions"][kind]
        native = result["inspections"][kind]
        _validate_linear_inspection(native)
        snapshot = native["geometry_verification"]
        if "dimension_id" in descriptor:
            tokens.append(descriptor["dimension_id"])
        if (
            native["observation"]["before"] != before
            or native["dimension"]
            != {
                key: value
                for key, value in descriptor.items()
                if key not in ("dimension_id", "sketch_id")
            }
            or descriptor["configuration"] != before["configuration"]
            or native["constraint_status"] != result["constraint_status"]
            or (
                "sketch_id" in descriptor
                and descriptor["sketch_id"] != result["sketch_id"]
            )
            or any(
                not isclose(value, expected, rel_tol=0, abs_tol=1e-6)
                for value, expected in (
                    (descriptor["value"], geometry[f"expected_{kind}_mm"]),
                    *[
                        (actual[f"{axis}_mm"], geometry[f"expected_{axis}_mm"])
                        for axis in ("width", "height")
                    ],
                    *[
                        (snapshot[f"actual_{axis}_mm"], actual[f"{axis}_mm"])
                        for axis in ("width", "height")
                    ],
                    *[
                        (snapshot["actual_center_mm"][axis], actual["center_mm"][axis])
                        for axis in ("x", "y", "z")
                    ],
                    *[
                        (
                            actual["center_mm"][axis],
                            geometry["expected_center_mm"][axis],
                        )
                        for axis in ("x", "y", "z")
                    ],
                )
            )
        ):
            raise OperationResultInvalid(
                "dimension.discover-rectangle: inconsistent native pair/geometry"
            )
    if len(tokens) == 2 and tokens[0] == tokens[1]:
        raise OperationResultInvalid(
            "dimension.discover-rectangle: two roles share a live ID"
        )


@lru_cache(maxsize=1)
def _rectangle_discovery_observation_validator():
    from jsonschema import Draft202012Validator

    schema = operation_result_schema("dimension.discover-rectangle")
    for kind in ("width", "height"):
        required = schema["then"]["properties"]["dimensions"]["properties"][kind][
            "required"
        ]
        required.remove("dimension_id")
        required.remove("sketch_id")
    return Draft202012Validator(schema)


def validate_rectangle_discovery_observation(result):
    _validate_result(
        "dimension.discover-rectangle",
        result,
        _rectangle_discovery_observation_validator(),
    )
    _validate_rectangle_discovery(result)


def _validate_linear_inspection(result):
    if result["ok"] is not True:
        return
    dimension, observation = result["dimension"], result["observation"]
    geometry = result["geometry_verification"]
    state = observation["after"]
    matches = isclose(
        dimension["value"],
        geometry[f"actual_{dimension['kind']}_mm"],
        rel_tol=0,
        abs_tol=1e-6,
    )
    if (
        observation["before"] != state
        or dimension["configuration"] != state["configuration"]
        or result["editing"] != state["editing"]
        or geometry["dimension_kind"] != dimension["kind"]
        or geometry["expected_value_mm"] != dimension["value"]
        or geometry["passed"] != matches
        or (
            "document" in result
            and result["document"]["update_stamp"] != state["update_stamp"]
        )
        or ("sketch_id" in result and dimension.get("sketch_id") != result["sketch_id"])
    ):
        raise OperationResultInvalid(
            "dimension.inspect: inconsistent native rectangle observation"
        )


def _validate_linear_set(result):
    before, after = result["before"], result["after"]
    _validate_linear_inspection(before)
    _validate_linear_inspection(after)
    dimension = result["dimension"]
    kind = dimension["kind"]
    other = "height" if kind == "width" else "width"
    geometry = result["geometry_verification"]
    previous = before["geometry_verification"]
    current = after["geometry_verification"]
    if (
        any(read["dimension"]["kind"] != kind for read in (before, after))
        or any(
            dimension[field] != after["dimension"][field]
            for field in after["dimension"]
        )
        or before["dimension"]["configuration"] != dimension["configuration"]
        or result["before_value_mm"] != before["dimension"]["value"]
        or result["final_state"] != after["observation"]["after"]
        or geometry["expected_center_mm"] != previous["actual_center_mm"]
        or geometry[f"expected_{kind}_mm"] != result["value_mm"]
        or geometry[f"expected_{other}_mm"] != previous[f"actual_{other}_mm"]
        or ("sketch_id" in result and dimension.get("sketch_id") != result["sketch_id"])
        or any(
            not isclose(value, expected, rel_tol=0, abs_tol=1e-6)
            for value, expected in (
                (dimension["value"], result["value_mm"]),
                *[
                    (geometry["actual"][f"{axis}_mm"], geometry[f"expected_{axis}_mm"])
                    for axis in ("width", "height")
                ],
                *[
                    (geometry["actual"][f"{axis}_mm"], current[f"actual_{axis}_mm"])
                    for axis in ("width", "height")
                ],
                *[
                    (
                        geometry["actual"]["center_mm"][axis],
                        previous["actual_center_mm"][axis],
                    )
                    for axis in ("x", "y", "z")
                ],
                *[
                    (
                        geometry["actual"]["center_mm"][axis],
                        current["actual_center_mm"][axis],
                    )
                    for axis in ("x", "y", "z")
                ],
            )
        )
    ):
        raise OperationResultInvalid(
            "dimension.set: inconsistent native size/center readback"
        )


def _validate_feature_state(name: str, result: Dict[str, Any]) -> None:
    if result["ok"] is not True:
        # Native failed reads publish state/error evidence only, not a usable
        # partial feature list or definition.
        if any(field in result for field in ("features", "feature", "definition")):
            raise OperationResultInvalid(
                f"{name}: failed observation published handles"
            )
        return
    observation = result["observation"]
    before, after = observation["before"], observation["after"]
    document = result["document"]
    if (
        before != after
        or not before["configuration"].strip()
        or document["type"] != 1
        or document["modified"] != after["modified"]
        or document["update_stamp"] != after["update_stamp"]
    ):
        raise OperationResultInvalid(f"{name}: inconsistent native observation state")
    features = result["features"] if name == "feature.list" else [result["feature"]]
    for feature in features:
        is_cut = feature["native_type"] == "Cut"
        if (
            feature["kind"] != ("cut-extrude" if is_cut else "boss-extrude")
            or feature["type"] not in ("ICE", feature["native_type"])
            or not feature["name"].strip()
            or (
                name == "feature.inspect"
                and (("feature_scope" in result["definition"]) != is_cut)
            )
        ):
            raise OperationResultInvalid(
                f"{name}: inconsistent native feature semantics"
            )
    if name == "feature.list":
        if result["count"] != len(features):
            raise OperationResultInvalid(
                f"{name}: feature count differs from observations"
            )
        ids = [feature["feature_id"] for feature in features if "feature_id" in feature]
        if len(ids) != len(set(ids)):
            raise OperationResultInvalid(f"{name}: duplicate feature handles")


@lru_cache(maxsize=2)
def _feature_observation_validator(name: str):
    from jsonschema import Draft202012Validator

    schema = operation_result_schema(name)
    descriptor = (
        schema["properties"]["features"]["items"]
        if name == "feature.list"
        else schema["properties"]["feature"]
    )
    descriptor["required"].remove("feature_id")
    del descriptor["properties"]["feature_id"]
    return Draft202012Validator(schema)


def validate_feature_observation(name: str, result: Dict[str, Any]) -> None:
    """Validate complete native reads before exposing or registering wire handles."""
    _validate_result(name, result, _feature_observation_validator(name))
    _validate_feature_state(name, result)


def _validate_entity_semantics(name: str, result: Dict[str, Any]) -> None:
    try:
        validate_entity_semantics(name, result)
    except (ValueError, OverflowError) as exc:
        raise OperationResultInvalid(str(exc)) from exc


@lru_cache(maxsize=2)
def _entity_observation_validator(name: str):
    from jsonschema import Draft202012Validator

    return Draft202012Validator(without_entity_ids(operation_result_schema(name), name))


def validate_entity_observation(name: str, result: Dict[str, Any]) -> None:
    """Validate complete private observations before registering short IDs."""
    _validate_result(name, result, _entity_observation_validator(name))
    _validate_entity_semantics(name, result)


@lru_cache(maxsize=2)
def _entity_result_validator(name: str):
    from jsonschema import Draft202012Validator

    return Draft202012Validator(operation_result_schema(name))


def validate_entity_result(name: str, result: Dict[str, Any]) -> None:
    """Check prepared entity contracts independently of operation advertisement."""
    _validate_result(name, result, _entity_result_validator(name))
    _validate_entity_semantics(name, result)


def _validate_feature_depth_result(result: Dict[str, Any]) -> None:
    def require(condition, message):
        if not condition:
            raise OperationResultInvalid("feature.set-depth: " + message)

    mutation = result["mutation"]
    flags = [
        mutation[key]
        for key in (
            "staging_attempted",
            "configuration_scope_applied",
            "commit_attempted",
            "committed",
        )
    ]
    require(
        all(not later or earlier for earlier, later in zip(flags, flags[1:])),
        "inconsistent mutation lifecycle",
    )
    if "modification_may_have_happened" in result:
        require(
            result["modification_may_have_happened"] == flags[0],
            "inconsistent possible mutation flag",
        )
    for check in result.get("selection_checks", {}).values():
        lifecycle = check["selection_access"]
        require(
            not lifecycle["acquired"] or lifecycle["attempted"],
            "access acquired without attempt",
        )
        require(
            not lifecycle["release_attempted"] or lifecycle["attempted"],
            "release without owned access",
        )
        require(
            not lifecycle["released"] or lifecycle["release_attempted"],
            "release succeeded without attempt",
        )
        require(
            not lifecycle["state_restored"] or lifecycle["released"],
            "restored without releasing access",
        )
        observation = check.get("observation", {})
        if "after" in observation:
            before, after = observation["before"], observation["after"]
            require(
                "update_stamp_changed" in observation,
                "missing selection stamp-change report",
            )
            require(
                observation["update_stamp_changed"]
                == (before["update_stamp"] != after["update_stamp"]),
                "incorrect selection stamp-change report",
            )
            if check["ok"]:
                require(
                    all(
                        before[key] == after[key]
                        for key in (
                            "configuration",
                            "modified",
                            "editing",
                            "foreground_present",
                        )
                    ),
                    "successful selection access did not restore native state",
                )
    if not result["ok"]:
        return
    require(
        result["feature_id"] == result["feature"]["feature_id"],
        "feature target mismatch",
    )
    definition = result["definition_after"]
    kind = result["feature"]["kind"]
    feature = result["feature"]
    require(
        kind == ("cut-extrude" if feature["native_type"] == "Cut" else "boss-extrude")
        and feature["type"] in ("ICE", feature["native_type"])
        and bool(feature["name"].strip()),
        "inconsistent native feature semantics",
    )
    require(
        (kind == "boss-extrude") == ("merge" in definition),
        "feature/definition kind mismatch",
    )
    require(
        definition["end_condition"] == 0
        and definition["from_type"] == 0
        and not any(
            definition[key]
            for key in ("both_directions", "thin", "forward_draft", "reverse_draft")
        )
        and (kind != "boss-extrude" or definition["merge"]),
        "unsupported successful depth definition",
    )
    require(
        isclose(
            definition["depth_mm"],
            result["requested_depth_mm"],
            rel_tol=0,
            abs_tol=1e-6,
        ),
        "native depth differs from request",
    )
    checks = result["selection_checks"]
    final_check = checks["preflight"]
    if result["depth_changed"]:
        require(
            all(flags) and result.get("rebuilt") is True,
            "uncommitted/unrebuilt depth change",
        )
        require(
            "postflight" in checks and checks["postflight"]["ok"],
            "missing successful postflight",
        )
        require(
            result["verification"]["method"]
            == "native-blind-depth-preserved-profile-and-scope",
            "wrong write verification method",
        )
        require(
            not isclose(
                result["before_depth_mm"],
                result["requested_depth_mm"],
                rel_tol=0,
                abs_tol=1e-6,
            ),
            "equal depth reported as changed",
        )
        final_check = checks["postflight"]
    else:
        require(
            not any(flags) and "rebuilt" not in result and "postflight" not in checks,
            "equal-depth call mutated/rebuilt",
        )
        require(
            result["verification"]["method"] == "guarded-equal-depth",
            "wrong equal-depth verification method",
        )
        require(
            isclose(
                result["before_depth_mm"],
                result["requested_depth_mm"],
                rel_tol=0,
                abs_tol=1e-6,
            ),
            "unequal depth reported unchanged",
        )
        require(
            result["measurement_before"] == result["measurement_after"],
            "equal-depth geometry changed",
        )
    require(
        result["final_state"] == final_check["observation"]["after"],
        "final native state drift",
    )
    require(
        result["document"]["modified"] == result["final_state"]["modified"]
        and result["document"]["update_stamp"] == result["final_state"]["update_stamp"],
        "document differs from verified final state",
    )


def validate_operation_result(name: str, result: Any) -> None:
    _validate_result(name, result, _validator(name))
    if name in ("entity.list", "entity.inspect"):
        _validate_entity_semantics(name, result)
    if name in ("feature.list", "feature.inspect"):
        _validate_feature_state(name, result)
    if name == "feature.set-depth":
        _validate_feature_depth_result(result)
    if name == "dimension.discover-diameter":
        _validate_dimension_discovery_state(result)
    if name == "sketch.dimension-rectangle":
        _validate_rectangle_creation(result)
    if name == "dimension.discover-rectangle":
        _validate_rectangle_discovery(result)
    if result.get("ok") is True and result.get("dimension", {}).get("kind") in (
        "width",
        "height",
    ):
        if name == "dimension.inspect":
            _validate_linear_inspection(result)
        elif name == "dimension.set":
            _validate_linear_set(result)
    if name == "sketch.fix-center" and result["ok"] is True:
        before, after = result["center_before"], result["center"]
        verification = result["geometry_verification"]
        expected = before["geometry"]
        observations = [after]
        if result["created"]:
            observations.append(result["center_in_edit"])
        if (
            any(
                before[field] != observation[field]
                for observation in observations
                for field in (
                    "native_point_id",
                    "native_diagonal_ids",
                    "identity_scope",
                )
            )
            or verification["actual"] != after["geometry"]
            or verification["expected_width_mm"] != expected["width_mm"]
            or verification["expected_height_mm"] != expected["height_mm"]
            or verification["expected_center_mm"] != expected["center_mm"]
            or any(
                not isclose(value, reference, rel_tol=0, abs_tol=1e-6)
                for observation in observations
                for value, reference in (
                    (observation["geometry"]["width_mm"], expected["width_mm"]),
                    (observation["geometry"]["height_mm"], expected["height_mm"]),
                    *[
                        (
                            observation["geometry"]["center_mm"][axis],
                            expected["center_mm"][axis],
                        )
                        for axis in ("x", "y", "z")
                    ],
                    *zip(observation["geometry"]["bounds_mm"], expected["bounds_mm"]),
                )
            )
        ):
            raise OperationResultInvalid(
                "sketch.fix-center: inconsistent native center/geometry evidence"
            )
