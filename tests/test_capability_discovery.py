"""Cheap discovery is a supervisor query, not COM work or a hidden full catalog."""

import contextlib
import copy
import io
import json
import unittest
from unittest import mock

from swcli import PROTOCOL_VERSION
from swcli.cli import _capabilities_mismatch, build_parser, main
from swcli.daemon import server
from swcli.hosts.windows_documents import supported_export_formats
from swcli.operation_schemas import OPERATIONS, validate_operation_request
from swcli.result_schemas import validate_operation_result


class CapabilityDiscoveryTests(unittest.TestCase):
    def setUp(self):
        startup = mock.patch.object(server.WorkerManager, "_start_worker")
        self.addCleanup(startup.stop)
        self.start = startup.start()
        self.manager = server.WorkerManager()
        self.start.reset_mock()

    def cli(self, arguments, payload):
        output = io.StringIO()
        with mock.patch("swcli.cli.call_daemon", return_value={
            "success": True, "result": payload,
        }) as call, contextlib.redirect_stdout(output):
            code = main(["capabilities", *arguments, "--json"])
        return code, json.loads(output.getvalue()), call

    def test_health_is_small_and_does_not_publish_or_build_catalogs(self):
        with mock.patch("swcli.operation_schemas.operation_schemas", side_effect=AssertionError), \
                mock.patch("swcli.operation_schemas.operation_result_schemas", side_effect=AssertionError):
            health = self.manager.health()
        validate_operation_result("daemon.health", health)
        self.assertLess(len(json.dumps(health)), 4096)
        for key in ("operations", "operation_schemas", "operation_result_schemas", "export_formats"):
            self.assertNotIn(key, health)
        self.assertFalse(health["host_connected"])
        self.assertIsNone(health["host"])
        self.start.assert_not_called()

    def test_summary_advertises_adapter_extensions_without_schemas(self):
        summary = self.manager.capabilities()
        validate_operation_result("daemon.capabilities", summary)
        self.assertIsNone(_capabilities_mismatch(summary, include_schemas=False))
        self.assertLess(len(json.dumps(summary)), 8192)
        self.assertEqual(summary["operations"], list(OPERATIONS))
        self.assertEqual(summary["export_formats"], supported_export_formats())
        self.assertIn(".glb", summary["export_formats"]["part"])
        self.assertNotIn(".obj", summary["export_formats"]["part"])
        self.assertNotIn("operation_schemas", summary)
        self.assertNotIn("operation_result_schemas", summary)
        self.start.assert_not_called()

    def test_selected_query_returns_only_requested_schema_and_independent_copies(self):
        selected = self.manager.capabilities(operation="document.export")
        validate_operation_result("daemon.capabilities", selected)
        self.assertIsNone(_capabilities_mismatch(selected))
        self.assertEqual(selected["operations"], ["document.export"])
        self.assertEqual(set(selected["operation_schemas"]), {"document.export"})
        self.assertEqual(set(selected["operation_result_schemas"]), {"document.export"})
        self.assertLess(len(json.dumps(selected)), 32768)
        selected["operation_schemas"]["document.export"]["properties"].clear()
        self.assertIn("output", self.manager.capabilities(operation="document.export")
                      ["operation_schemas"]["document.export"]["properties"])
        self.start.assert_not_called()

    def test_full_catalog_still_has_all_request_and_result_contracts(self):
        full = self.manager.capabilities(include_schemas=True)
        validate_operation_result("daemon.capabilities", full)
        self.assertIsNone(_capabilities_mismatch(full))
        self.assertEqual(set(full["operation_schemas"]), set(OPERATIONS))
        self.assertEqual(set(full["operation_result_schemas"]), set(OPERATIONS))

    def test_cli_summary_full_and_selected_request_the_right_wire_view(self):
        for arguments, parameters, payload in (
            ([], {"include_schemas": False}, self.manager.capabilities()),
            (["--full"], {"include_schemas": True}, self.manager.capabilities(include_schemas=True)),
            (["--operation", "document.export"],
             {"include_schemas": False, "operation": "document.export"},
             self.manager.capabilities(operation="document.export")),
        ):
            with self.subTest(arguments=arguments):
                code, output, call = self.cli(arguments, payload)
                self.assertEqual(code, 0, output)
                self.assertEqual(output, payload)
                call.assert_called_once_with(
                    "daemon.capabilities", parameters, endpoint="127.0.0.1:18495",
                    timeout_seconds=10.0, connect_timeout_seconds=3.0,
                )

    def test_missing_extra_mismatched_and_incomplete_discovery_fail_closed(self):
        summary = self.manager.capabilities()
        invalid = copy.deepcopy(summary)
        invalid["export_formats"]["drawing"] = ["not-an-extension"]
        missing = copy.deepcopy(summary)
        del missing["export_formats"]
        incomplete = self.manager.capabilities(include_schemas=True)
        del incomplete["operation_result_schemas"]["document.export"]
        for arguments, payload in (([], invalid), ([], missing),
                                   ([], self.manager.capabilities(include_schemas=True)),
                                   (["--full"], incomplete),
                                   (["--operation", "document.export"],
                                    self.manager.capabilities(operation="document.open"))):
            with self.subTest(arguments=arguments):
                code, result, _ = self.cli(arguments, payload)
                self.assertEqual(code, 1)
                self.assertEqual(result["error"]["type"], "CapabilitiesMismatch")

    def test_request_schema_rejects_ambiguous_types_and_document_context(self):
        for parameters in ({"include_schemas": 1}, {"operation": ""}, {"operation": None},
                           {"operation": []}, {"unknown": True}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                validate_operation_request("daemon.capabilities", parameters)
        with self.assertRaises(ValueError):
            validate_operation_request("daemon.capabilities", {}, document_id="d-ab12cd")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["capabilities", "--full", "--operation", "document.open"])

    def test_supervisor_wire_queries_do_not_dispatch_business_operations(self):
        for operation, parameters in (("daemon.health", {}), ("daemon.capabilities", {}),
                                      ("daemon.capabilities", {"operation": "document.export"})):
            request = {"api_version": PROTOCOL_VERSION, "request_id": "discovery",
                       "operation": operation, "parameters": parameters}
            handler = object.__new__(server.SwclidRequestHandler)
            handler.rfile = io.BytesIO(json.dumps(request).encode() + b"\n")
            handler.wfile = io.BytesIO()
            handler.server = mock.Mock(manager=self.manager)
            with mock.patch.object(self.manager, "call", side_effect=AssertionError):
                handler.handle()
            response = json.loads(handler.wfile.getvalue())
            self.assertTrue(response["success"], response)
            validate_operation_result(operation, response["result"])
        with self.assertRaisesRegex(ValueError, "unknown operation"):
            self.manager.capabilities(operation="imagined.operation")
        self.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
