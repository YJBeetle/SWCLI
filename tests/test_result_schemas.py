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


class ResultSchemaTests(unittest.TestCase):
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
