import copy
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.daemon.server import WorkerManager
from swcli.operation_schemas import OPERATIONS, operation_result_schemas
from swcli.protocol import load_schema
from swcli.result_schemas import OperationResultInvalid, validate_operation_result

DOCUMENT = {
    "title": "part.SLDPRT",
    "path": "C:\\part.SLDPRT",
    "type": 1,
    "modified": False,
    "update_stamp": 0,
    "document_id": "d-ab12cd",
    "current": True,
    "active": False,
}
DIMENSION = {
    "dimension_id": "m-ab12cd",
    "sketch_id": "s-ab12cd",
    "kind": "diameter",
    "unit": "millimeter",
    "value": 16,
    "driven_state": 2,
    "read_only": False,
    "configuration": "默认",
    "native_name": "D1@草图1",
}
CIRCLE_VERIFICATION = {
    "passed": True,
    "method": "sketch-local-circle",
    "segment_count": 1,
    "profile_segment_count": 1,
    "complete_circle": True,
    "actual_radius_mm": 8,
    "actual_center_mm": {"x": 3, "y": 4, "z": 0},
    "absolute_tolerance_mm": 1e-6,
}


def diameter_result(action):
    return {
        "ok": True,
        "action": action,
        "document": DOCUMENT,
        "sketch_id": "s-ab12cd",
        "dimension": copy.deepcopy(DIMENSION),
        "geometry_verification": copy.deepcopy(CIRCLE_VERIFICATION),
        "constraint_status": 2,
        "editing": False,
    }


class ResultSchemaTests(unittest.TestCase):
    def test_diameter_creation_success_requires_native_and_geometric_evidence(self):
        result = {**diameter_result("sketch.dimension-diameter"), "native_status": 0}
        validate_operation_result("sketch.dimension-diameter", result)
        for field, value in (
            ("value", None),
            ("value", 0),
            ("driven_state", 1),
            ("read_only", True),
            ("dimension_id", "D1@Sketch1"),
        ):
            invalid = copy.deepcopy(result)
            invalid["dimension"][field] = value
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("sketch.dimension-diameter", invalid)
        for field, value in (("native_status", 1), ("editing", True)):
            with self.subTest(field=field), self.assertRaises(OperationResultInvalid):
                validate_operation_result(
                    "sketch.dimension-diameter", {**result, field: value}
                )
        invalid = copy.deepcopy(result)
        invalid["geometry_verification"]["passed"] = False
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.dimension-diameter", invalid)
        invalid = copy.deepcopy(result)
        del invalid["dimension"]["native_name"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.dimension-diameter", invalid)

    def test_diameter_failure_preserves_a_partially_created_handle(self):
        result = {
            "ok": False,
            "action": "sketch.dimension-diameter",
            "document": DOCUMENT,
            "sketch_id": "s-ab12cd",
            "dimension": {"dimension_id": "m-ab12cd", "sketch_id": "s-ab12cd"},
            "native_status": 1,
            "editing": True,
            "error": {"type": "DimensionSetFailed", "message": "native rejection"},
        }
        validate_operation_result("sketch.dimension-diameter", result)
        result["ok"] = True
        del result["error"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.dimension-diameter", result)

    def test_dimension_inspect_observes_controls_and_editing_without_mutation_claims(
        self,
    ):
        result = {
            **diameter_result("dimension.inspect"),
            "equation_control": {"controlled": True, "equation_indices": [0]},
            "design_table_controlled": True,
            "editing": True,
        }
        result["dimension"].update(driven_state=1, read_only=True)
        result["geometry_verification"]["passed"] = False
        validate_operation_result("dimension.inspect", result)
        invalid = copy.deepcopy(result)
        del invalid["equation_control"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.inspect", invalid)
        invalid = copy.deepcopy(result)
        invalid["equation_control"]["equation_indices"] = [-1]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.inspect", invalid)

    def test_dimension_set_success_requires_rebuild_and_controlled_downstream_evidence(
        self,
    ):
        result = {
            **diameter_result("dimension.set"),
            "value_mm": 16,
            "before_value_mm": 10,
            "native_status": 0,
            "rebuilt": True,
            "needs_rebuild": 0,
            "equation_control": {"controlled": False, "equation_indices": []},
            "design_table_controlled": False,
            "diagnostics": {
                "healthy": True,
                "issues": [],
                "issue_count": 0,
                "scanned_feature_count": 5,
                "truncated": False,
                "limit": 500,
            },
            "downstream": {
                "applicable": False,
                "measurement_before": None,
                "measurement_after": None,
            },
        }
        validate_operation_result("dimension.set", result)
        for field, value in (
            ("rebuilt", False),
            ("needs_rebuild", 1),
            ("before_value_mm", None),
        ):
            with self.subTest(field=field), self.assertRaises(OperationResultInvalid):
                validate_operation_result("dimension.set", {**result, field: value})
        invalid = copy.deepcopy(result)
        invalid["downstream"]["applicable"] = True
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.set", invalid)
        invalid = copy.deepcopy(result)
        invalid["design_table_controlled"] = True
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.set", invalid)
        invalid = copy.deepcopy(result)
        invalid["equation_control"].update(controlled=True, equation_indices=[0])
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.set", invalid)
        invalid["ok"] = False
        invalid["error"] = {"type": "DimensionEquationControlled", "message": "native equation"}
        validate_operation_result("dimension.set", invalid)
        invalid = copy.deepcopy(result)
        invalid["diagnostics"]["healthy"] = False
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.set", invalid)
        invalid["ok"] = False
        invalid["error"] = {
            "type": "DimensionVerificationFailed",
            "message": "rebuild unhealthy",
        }
        validate_operation_result("dimension.set", invalid)

    def test_result_validation_rejects_nonfinite_json_even_in_partial_measurement(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            result = {
                "ok": False,
                "action": "document.measure",
                "error": {
                    "type": "MeasurementUnavailable",
                    "message": "partial geometry",
                },
                "metrics": {
                    "solid_body_count": 1,
                    "volume_mm3": value,
                    "surface_area_mm2": 1,
                    "centroid_mm": {"x": 0, "y": 0, "z": 0},
                },
            }
            with self.subTest(value=value), self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.measure", result)

    def test_transport_envelope_distinguishes_success_from_failure(self):
        validator = Draft202012Validator(load_schema("response"))
        base = {"api_version": "swcli/v1", "request_id": "test", "duration_ms": 0}
        validator.validate({**base, "success": True, "result": {"stopping": True}})
        validator.validate(
            {
                **base,
                "success": False,
                "error": {"code": "InvalidArgument", "message": "invalid"},
            }
        )
        self.assertFalse(validator.is_valid({**base, "success": True}))
        self.assertFalse(validator.is_valid({**base, "success": False}))
        self.assertFalse(
            validator.is_valid(
                {
                    **base,
                    "success": True,
                    "result": {},
                    "error": {"code": "mixed", "message": "mixed"},
                }
            )
        )

    def test_every_operation_publishes_a_valid_isolated_result_contract(self):
        schemas = operation_result_schemas()
        self.assertEqual(tuple(schemas), OPERATIONS)
        self.assertEqual(len({s["$id"] for s in schemas.values()}), len(schemas))
        for name, schema in schemas.items():
            with self.subTest(name=name):
                Draft202012Validator.check_schema(schema)
        schemas["document.inspect"]["properties"].clear()
        self.assertIn(
            "document", operation_result_schemas()["document.inspect"]["properties"]
        )

    def test_health_result_matches_its_published_contract(self):
        with mock.patch.object(WorkerManager, "_start_worker"):
            validate_operation_result("daemon.health", WorkerManager().health())

    def test_inspect_accepts_native_zero_stamp_and_rejects_wrong_types(self):
        result = {
            "ok": True,
            "action": "document.inspect",
            "document": DOCUMENT,
            "needs_rebuild": 0,
        }
        validate_operation_result("document.inspect", result)
        invalid = copy.deepcopy(result)
        invalid["document"]["modified"] = "false"
        with self.assertRaisesRegex(OperationResultInvalid, "document.modified"):
            validate_operation_result("document.inspect", invalid)
        invalid = copy.deepcopy(result)
        del invalid["needs_rebuild"]
        with self.assertRaisesRegex(OperationResultInvalid, "needs_rebuild"):
            validate_operation_result("document.inspect", invalid)

    def test_unserializable_cyclic_and_unencodable_native_results_fail_structurally(self):
        cyclic = []
        cyclic.append(cyclic)
        for title in (b"binary", object(), cyclic, "bad\ud800title"):
            result = {
                "ok": True,
                "action": "document.inspect",
                "document": {**DOCUMENT, "title": title},
                "needs_rebuild": 0,
            }
            with (
                self.subTest(kind=type(title).__name__),
                self.assertRaisesRegex(OperationResultInvalid, "UTF-8 JSON"),
            ):
                validate_operation_result("document.inspect", result)

    def test_failure_can_have_partial_result_but_requires_error(self):
        result = {
            "ok": False,
            "action": "document.export",
            "error": {
                "type": "SourceNotClean",
                "message": "needs saving",
                "violations": [{"code": "source-modified", "message": "modified"}],
            },
        }
        validate_operation_result("document.export", result)
        del result["error"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.export", result)

    def test_export_contract_rejects_empty_artifact_and_unknown_fields(self):
        result = {
            "ok": True,
            "action": "document.export",
            "output": "part.STEP",
            "artifact": {
                "kind": "cad-export",
                "path": "part.STEP",
                "format": "STEP",
                "size_bytes": 16,
            },
        }
        validate_operation_result("document.export", result)
        result["artifact"]["size_bytes"] = 0
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.export", result)
        result["artifact"]["size_bytes"] = 16
        result["unexpected"] = True
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.export", result)

    def test_foreign_lease_status_can_hide_the_token(self):
        result = {
            "ok": True,
            "action": "document.lease.status",
            "session_id": "observer",
            "document": DOCUMENT,
            "leased": True,
            "owned_by_session": False,
            "lease": {
                "document_id": "d-ab12cd",
                "session_id": "owner",
                "expires_in_seconds": 59,
            },
        }
        validate_operation_result("document.lease.status", result)
        result["action"] = "document.lease.acquire"
        del result["leased"]
        del result["owned_by_session"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.lease.acquire", result)

    def test_shutdown_handles_both_connected_and_disconnected_hosts(self):
        validate_operation_result("daemon.shutdown", {"stopping": True})
        validate_operation_result(
            "daemon.shutdown", {"stopping": True, "host_already_disconnected": True}
        )


if __name__ == "__main__":
    unittest.main()
