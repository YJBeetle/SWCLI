"""MCP adapter contract plus an independent official-SDK stdio round trip."""

import contextlib
from datetime import timedelta
import importlib.util
import io
import json
import os
from pathlib import Path
import socketserver
import sys
import tempfile
import threading
import unittest
from unittest import mock

from swcli import PROTOCOL_VERSION
from swcli.cli import build_parser, main
from swcli.mcp import DaemonBridge, tool_definitions
from swcli.protocol import load_schema

SDK_AVAILABLE = sys.version_info >= (3, 10) and importlib.util.find_spec("mcp") is not None


def response(request_id="request-1", **fields):
    return {"api_version": PROTOCOL_VERSION, "request_id": request_id,
            "success": True, "duration_ms": 0, "result": {"ok": True}, **fields}


class MCPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.environment = mock.patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.bridge = DaemonBridge(session_id="agent-1", auto_start=False)
        self.transport = mock.patch("swcli.mcp.call_daemon", return_value=response())
        self.call = self.transport.start()
        self.addCleanup(self.transport.stop)
        startup_transport = mock.patch("swcli.client_startup.call_daemon", self.call)
        startup_transport.start()
        self.addCleanup(startup_transport.stop)
        job = mock.patch("swcli.client_startup.in_client_job", return_value=False)
        job.start()
        self.addCleanup(job.stop)

    def test_small_discovery_and_wire_context_schema_are_reused(self):
        tools = tool_definitions()
        self.assertEqual([t["name"] for t in tools], ["swcli_status", "swcli_capabilities", "swcli_execute"])
        self.assertLess(len(json.dumps(tools)), 5500)
        fields = tools[-1]["inputSchema"]["properties"]
        for name, field in fields.items():
            self.assertEqual(field, load_schema("request")["properties"][name])
        self.assertFalse(tools[0]["annotations"]["readOnlyHint"])
        self.assertTrue(tool_definitions(auto_start=False)[0]["annotations"]["readOnlyHint"])
        self.assertFalse(tools[-1]["annotations"]["readOnlyHint"])
        tools[-1]["inputSchema"]["properties"].clear()
        self.assertIn("document_id", tool_definitions()[-1]["inputSchema"]["properties"])

    def test_status_and_selected_capabilities_are_cheap_live_daemon_queries(self):
        self.bridge.call("swcli_status", {})
        self.assertEqual(self.call.call_args.args, ("daemon.health", {}))
        self.assertEqual(self.call.call_args.kwargs["timeout_seconds"], 10)
        self.bridge.call("swcli_capabilities", {})
        self.assertEqual(self.call.call_args.args, ("daemon.capabilities", {"include_schemas": False}))
        self.bridge.call("swcli_capabilities", {"operation": "document.summary"})
        self.assertEqual(self.call.call_args.args, ("daemon.capabilities", {"include_schemas": False, "operation": "document.summary"}))

    def test_execute_preserves_zero_stamp_explicit_session_lease_and_request_id(self):
        expected = response()
        self.call.return_value = expected
        arguments = {"operation": "document.summary.set", "parameters": {"author": "中文"},
                     "document_id": "d-ab12cd", "expected_update_stamp": 0,
                     "lease_id": "l-ab12cd34ef56", "session_id": "writer", "request_id": "request-1"}
        self.assertEqual(self.bridge.call("swcli_execute", arguments), expected)
        self.call.assert_called_once_with(
            "document.summary.set", {"author": "中文"}, endpoint="127.0.0.1:18495",
            timeout_seconds=600, connect_timeout_seconds=3, request_id="request-1",
            session_id="writer", document_id="d-ab12cd", expected_update_stamp=0, lease_id="l-ab12cd34ef56",
        )
        self.assertIn("operation", arguments)

    def test_new_mcp_processes_have_distinct_stable_default_sessions(self):
        first, second = DaemonBridge(auto_start=False), DaemonBridge(auto_start=False)
        self.assertNotEqual(first.session_id, second.session_id)
        first.call("swcli_status", {})
        one = self.call.call_args.kwargs["session_id"]
        first.call("swcli_execute", {"operation": "document.list", "parameters": {}})
        self.assertEqual(one, self.call.call_args.kwargs["session_id"])

    def test_environment_and_explicit_connection_selection(self):
        with mock.patch.dict(os.environ, {"SWCLI_ENDPOINT": "localhost:19100", "SWCLI_SESSION_ID": "explicit-shared"}):
            bridge = DaemonBridge()
            self.assertEqual(bridge.endpoint, "localhost:19100")
            self.assertEqual(bridge.session_id, "explicit-shared")
            self.assertEqual(DaemonBridge(endpoint="127.0.0.1:19200", session_id="own").session_id, "own")

    def test_host_paths_use_existing_cli_mapper_without_modifying_caller_arguments(self):
        arguments = {"operation": "document.open", "parameters": {"path": "/workspace/中文 零件.SLDPRT"}}
        with mock.patch.dict(os.environ, {"SWCLI_PATH_TRANSLATE_CMD": "wine-path"}), \
                mock.patch("swcli.cli.subprocess.check_output", return_value="Z:\\workspace\\中文 零件.SLDPRT\n") as mapper:
            self.bridge.call("swcli_execute", arguments)
        mapper.assert_called_once_with(["wine-path", "/workspace/中文 零件.SLDPRT"], text=True)
        self.assertEqual(self.call.call_args.args[1], {"path": "Z:\\workspace\\中文 零件.SLDPRT"})
        self.assertEqual(arguments["parameters"]["path"], "/workspace/中文 零件.SLDPRT")

    def test_invalid_inputs_and_daemon_shutdown_never_reach_transport(self):
        for name, arguments in (
            ("not-a-tool", {}), ("swcli_status", {"start": True}),
            ("swcli_capabilities", {"operation": ""}),
            ("swcli_execute", {"operation": "document.list"}),
            ("swcli_execute", {"operation": "document.list", "parameters": {}, "document_id": "wrong"}),
            ("swcli_execute", {"operation": "document.list", "parameters": {}, "expected_update_stamp": True}),
            ("swcli_execute", {"operation": "daemon.shutdown", "parameters": {}}),
        ):
            with self.subTest(name=name, arguments=arguments):
                result = self.bridge.call(name, arguments)
                self.assertFalse(result["success"])
                self.assertFalse(result["outcome_unknown"])
        self.call.assert_not_called()

    def test_daemon_validation_is_authoritative_including_new_operations(self):
        # Do not constrain an independently upgraded daemon to this client's catalog.
        self.bridge.call("swcli_execute", {"operation": "future.operation", "parameters": {"value": 1}})
        self.assertEqual(self.call.call_args.args, ("future.operation", {"value": 1}))

    def test_native_refusal_is_returned_without_rewriting_details_or_retry(self):
        refused = response(success=False, result=None, error={"code": "DocumentLeaseConflict", "message": "held", "details": {"partial": True}})
        # A real error envelope may contain result diagnostics as well.
        self.call.return_value = refused
        self.assertEqual(self.bridge.call("swcli_execute", {"operation": "document.save", "parameters": {}}), refused)
        self.call.assert_called_once()

    def test_read_timeout_preserves_request_id_and_marks_unknown_without_retry(self):
        self.call.side_effect = TimeoutError("reply timed out")
        result = self.bridge.call("swcli_execute", {"operation": "document.save", "parameters": {}, "request_id": "save-once"})
        self.assertEqual(result["request_id"], "save-once")
        self.assertTrue(result["outcome_unknown"])
        self.call.assert_called_once()

    def test_connect_failure_is_not_an_unknown_mutation(self):
        exc = ConnectionRefusedError("offline")
        exc._swcli_transport_phase = "connect"
        self.call.side_effect = exc
        result = self.bridge.call("swcli_status", {})
        self.assertFalse(result["outcome_unknown"])
        self.assertEqual(result["error"]["code"], "ConnectionRefusedError")
        self.call.assert_called_once()

    def test_incompatible_or_malformed_daemon_response_fails_closed(self):
        for payload in (response(api_version="other/v1"), {}, response(success="yes")):
            self.call.return_value = payload
            result = self.bridge.call("swcli_status", {})
            self.assertFalse(result["success"])
            self.assertTrue(result["outcome_unknown"])

    def test_invalid_timeouts_and_endpoints_fail_before_connect(self):
        for options in ({"timeout_seconds": float('nan')}, {"connect_timeout_seconds": 0}, {"endpoint": "bad"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                DaemonBridge(**options)
        self.call.assert_not_called()

    def test_lazy_start_happens_only_after_first_valid_tool_call_and_only_once(self):
        bridge = DaemonBridge(session_id="lazy")
        self.call.assert_not_called()
        offline = ConnectionRefusedError("offline")
        offline._swcli_transport_phase = "connect"
        self.call.side_effect = [offline, response(), response()]
        with mock.patch("swcli.daemon.main.start_daemon", return_value={"success": True}) as start:
            result = bridge.call("swcli_execute", {"operation": "document.list", "parameters": {}})
            bridge.call("swcli_status", {})
        self.assertTrue(result["success"])
        start.assert_called_once_with(endpoint="127.0.0.1:18495", startup_timeout_seconds=120)
        self.assertEqual([c.args[0] for c in self.call.call_args_list], ["daemon.health", "document.list", "daemon.health"])

    def test_existing_daemon_is_reused_without_start_or_restart(self):
        bridge = DaemonBridge()
        with mock.patch("swcli.daemon.main.start_daemon") as start:
            bridge.call("swcli_status", {})
            bridge.call("swcli_status", {})
        start.assert_not_called()
        self.assertEqual(self.call.call_count, 3)  # one preflight, two calls

    def test_remote_or_connect_only_never_tries_start(self):
        offline = ConnectionRefusedError("offline")
        offline._swcli_transport_phase = "connect"
        self.call.side_effect = offline
        with mock.patch("swcli.daemon.main.start_daemon") as start:
            for bridge in (DaemonBridge(endpoint="192.0.2.1:18495"), DaemonBridge(auto_start=False)):
                self.assertFalse(bridge.call("swcli_status", {})["success"])
        start.assert_not_called()
        self.assertEqual(self.call.call_count, 2)

    def test_failed_lazy_start_is_reported_once_and_never_repeated_on_tool_calls(self):
        bridge = DaemonBridge()
        offline = ConnectionRefusedError("offline")
        offline._swcli_transport_phase = "connect"
        self.call.side_effect = offline
        with mock.patch("swcli.daemon.main.start_daemon", return_value={"success": False, "error": {"code": "ExistingHostRequiresAttach", "message": "explicit attach required"}}) as start:
            first = bridge.call("swcli_status", {})
            second = bridge.call("swcli_status", {})
        self.assertIn("ExistingHostRequiresAttach", first["error"]["message"])
        self.assertFalse(first["outcome_unknown"])
        self.assertFalse(second["success"])
        start.assert_called_once()
        self.call.assert_called_once()

    def test_health_read_failure_or_existing_host_error_never_launches_another_host(self):
        with mock.patch("swcli.daemon.main.start_daemon") as start:
            self.call.side_effect = TimeoutError("reply lost")
            self.assertFalse(DaemonBridge().call("swcli_status", {})["success"])
            self.call.side_effect = None
            self.call.return_value = response(success=False, result=None, error={"code": "HostDisconnected", "message": "recover explicitly"})
            self.assertFalse(DaemonBridge().call("swcli_status", {})["success"])
        start.assert_not_called()

    def test_windows_client_job_uses_independent_same_user_launcher(self):
        offline = ConnectionRefusedError("offline")
        offline._swcli_transport_phase = "connect"
        self.call.side_effect = [offline, response()]
        with mock.patch("swcli.client_startup.in_client_job", return_value=True), \
                mock.patch("swcli.client_startup.start_resident_daemon", return_value={"success": True}) as broker, \
                mock.patch("swcli.daemon.main.start_daemon") as direct:
            self.assertTrue(DaemonBridge().call("swcli_status", {})["success"])
        broker.assert_called_once_with(endpoint="127.0.0.1:18495", startup_timeout_seconds=120)
        direct.assert_not_called()

    def test_permission_denied_at_connect_never_starts_a_host(self):
        error = PermissionError("blocked by policy")
        error._swcli_transport_phase = "connect"
        self.call.side_effect = error
        with mock.patch("swcli.daemon.main.start_daemon") as start:
            self.assertFalse(DaemonBridge().call("swcli_status", {})["success"])
        start.assert_not_called()

    def test_cli_dispatch_and_missing_extra_diagnostic_keep_stdout_clean(self):
        with mock.patch("swcli.mcp.run", return_value=0) as run:
            self.assertEqual(main(["--endpoint", "localhost:19100", "mcp", "serve"]), 0)
            self.assertEqual(run.call_args.args[0].endpoint, "localhost:19100")
        from swcli import mcp as adapter
        error = io.StringIO()
        output = io.StringIO()
        with mock.patch.object(adapter, "serve", side_effect=ModuleNotFoundError(name="mcp")), \
                contextlib.redirect_stderr(error), contextlib.redirect_stdout(output):
            self.assertEqual(adapter.run(build_parser().parse_args(["mcp", "serve"])), 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn('swcli[mcp]', error.getvalue())


@unittest.skipUnless(SDK_AVAILABLE, "optional official MCP SDK requires Python 3.10+")
class MCPStdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_sdk_handshake_discovery_execute_error_and_disconnect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        captured = []

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request = json.loads(self.rfile.readline())
                captured.append(request)
                if request["operation"] == "document.save":
                    payload = response(request["request_id"], success=False, result=None,
                                       error={"code": "UpdateStampConflict", "message": "changed"})
                else:
                    payload = response(request["request_id"], result={"echo": request})
                self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")

        with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as daemon:
            thread = threading.Thread(target=daemon.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(daemon.shutdown)
            endpoint = f"127.0.0.1:{daemon.server_address[1]}"
            environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
            environment.pop("SWCLI_PATH_TRANSLATE_CMD", None)
            arguments = ["-m", "swcli", "--endpoint", endpoint, "mcp", "serve", "--connect-only"]
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
                async with stdio_client(StdioServerParameters(command=sys.executable, args=arguments, env=environment), errlog=errors) as streams:
                    async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=15)) as session:
                        initialized = await session.initialize()
                        self.assertEqual(initialized.serverInfo.name, "swcli")
                        tools = await session.list_tools()
                        self.assertEqual(len(tools.tools), 3)
                        # Initialization/discovery do not connect to swclid or launch SW.
                        self.assertEqual(captured, [])
                        await session.send_ping()
                        status = await session.call_tool("swcli_status", {})
                        self.assertFalse(status.isError)
                        capabilities = await session.call_tool("swcli_capabilities", {"operation": "document.summary"})
                        self.assertEqual(capabilities.structuredContent["result"]["echo"]["parameters"], {"include_schemas": False, "operation": "document.summary"})
                        result = await session.call_tool("swcli_execute", {"operation": "document.list", "parameters": {}, "request_id": "once"})
                        self.assertEqual(result.structuredContent["request_id"], "once")
                        self.assertEqual(json.loads(result.content[0].text), result.structuredContent)
                        refused = await session.call_tool("swcli_execute", {"operation": "document.save", "parameters": {}, "expected_update_stamp": 0})
                        self.assertTrue(refused.isError)
                        self.assertEqual(refused.structuredContent["error"]["code"], "UpdateStampConflict")
                        before = len(captured)
                        invalid = await session.call_tool("swcli_execute", {"operation": "document.list"})
                        self.assertTrue(invalid.isError)
                        self.assertEqual(len(captured), before)
                self.assertEqual(len(captured), 4)
                self.assertEqual(len({r["session_id"] for r in captured}), 1)
                self.assertNotIn("daemon.shutdown", [r["operation"] for r in captured])
                # MCP EOF leaves the daemon available to other clients.
                self.assertTrue(thread.is_alive())

    async def test_two_mcp_processes_share_daemon_without_sharing_default_session(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        captured = []

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request = json.loads(self.rfile.readline())
                captured.append(request)
                self.wfile.write(json.dumps(response(request["request_id"], result={"session_id": request["session_id"]})).encode() + b"\n")

        with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as daemon:
            threading.Thread(target=daemon.serve_forever, daemon=True).start()
            self.addCleanup(daemon.shutdown)
            endpoint = f"127.0.0.1:{daemon.server_address[1]}"
            environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
            environment.pop("SWCLI_SESSION_ID", None)
            parameters = StdioServerParameters(command=sys.executable, args=["-m", "swcli", "--endpoint", endpoint, "mcp", "serve", "--connect-only"], env=environment)
            async with stdio_client(parameters) as second_streams:
                async with ClientSession(*second_streams, read_timeout_seconds=timedelta(seconds=15)) as second:
                    await second.initialize()
                    async with stdio_client(parameters) as first_streams:
                        async with ClientSession(*first_streams, read_timeout_seconds=timedelta(seconds=15)) as first:
                            await first.initialize()
                            one = await first.call_tool("swcli_execute", {"operation": "document.list", "parameters": {}})
                            two = await second.call_tool("swcli_execute", {"operation": "document.list", "parameters": {}})
                            self.assertNotEqual(one.structuredContent["result"]["session_id"], two.structuredContent["result"]["session_id"])
                    still_live = await second.call_tool("swcli_status", {})
                    self.assertFalse(still_live.isError)
                    self.assertEqual(still_live.structuredContent["result"]["session_id"], two.structuredContent["result"]["session_id"])
            self.assertEqual(len(captured), 3)
            self.assertNotIn("daemon.shutdown", [item["operation"] for item in captured])
