"""Explicit lifecycle, protocol preservation and official-SDK stdio interoperability."""

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
from swcli.mcp import DaemonBridge, tool_definitions, STARTUP_MESSAGE
from swcli.protocol import load_schema
from swcli.runtime_state import snapshot

SDK_AVAILABLE = sys.version_info >= (3, 10) and importlib.util.find_spec("mcp") is not None


def response(request_id="request-1", **fields):
    return {"api_version": PROTOCOL_VERSION, "request_id": request_id, "success": True,
            "duration_ms": 0, "result": {"ok": True}, **fields}


def health():
    return {"worker_alive": True, "host_connected": True,
            "host": {"process_id": 10, "owned_by_daemon": True, "visible": False}}


class MCPBridgeTests(unittest.TestCase):
    def setUp(self):
        env=mock.patch.dict(os.environ,{},clear=True);env.start();self.addCleanup(env.stop)
        self.manager=mock.Mock()
        self.manager.status.return_value={"success":True,"result":snapshot(daemon_running=False,reachable=False)}
        self.manager.start.return_value={"success":True,"result":{"started":True}}
        self.manager.stop.return_value={"success":True,"result":{"stopping":True}}
        manager=mock.patch("swcli.mcp.DaemonManager",return_value=self.manager);manager.start();self.addCleanup(manager.stop)
        self.bridge=DaemonBridge(session_id="agent-1")
        transport=mock.patch("swcli.mcp.call_daemon",return_value=response());self.call=transport.start();self.addCleanup(transport.stop)

    def test_small_stable_tool_contract_and_shared_context(self):
        tools=tool_definitions()
        self.assertEqual([t["name"] for t in tools],["status","daemon_start","daemon_stop","capabilities","execute"])
        self.assertLess(len(json.dumps(tools)),7500)
        for name,field in tools[-1]["inputSchema"]["properties"].items():
            self.assertEqual(field,load_schema("request")["properties"][name])
        self.assertTrue(tools[0]["annotations"]["readOnlyHint"])
        self.assertFalse(tools[1]["annotations"]["readOnlyHint"])
        self.assertIn(STARTUP_MESSAGE,tools[1]["description"])
        tools[-1]["inputSchema"]["properties"].clear()
        self.assertIn("document_id",tool_definitions()[-1]["inputSchema"]["properties"])

    def test_only_short_tool_names_dispatch_and_old_names_have_no_side_effects(self):
        for name in ("status", "daemon_start", "daemon_stop", "capabilities", "execute"):
            self.assertFalse(self.bridge.call("swcli_" + name, {})["success"])
        self.call.assert_not_called()
        self.manager.start.assert_not_called(); self.manager.stop.assert_not_called()
        self.manager.status.assert_not_called()

    def test_document_units_and_annotations_preserve_native_operation_context(self):
        from swcli.operation_schemas import validate_operation_request
        cases = (
            ("document.units", {}),
            ("document.units-set", {"length_unit": "inch", "expected_length_unit": "mm"}),
            ("document.annotation-options", {}),
            ("document.annotation-option-set", {"field": "arrow.edge_vertex", "value": "dot", "expected_value": "closed"}),
        )
        for operation, parameters in cases:
            with self.subTest(operation=operation):
                validate_operation_request(operation, parameters)
                arguments = {"operation": operation, "parameters": parameters,
                             "session_id": "options", "document_id": "d-ab12cd",
                             "expected_update_stamp": 0, "lease_id": "l-ab12cd34ef56"}
                self.assertTrue(self.bridge.call("execute", arguments)["success"])
                self.assertEqual(self.call.call_args.args, (operation, parameters))
                self.assertEqual(self.call.call_args.kwargs["session_id"], "options")
                self.assertEqual(self.call.call_args.kwargs["document_id"], "d-ab12cd")
                self.assertEqual(self.call.call_args.kwargs["expected_update_stamp"], 0)
                self.assertEqual(self.call.call_args.kwargs["lease_id"], "l-ab12cd34ef56")
        self.manager.start.assert_not_called()

    def test_status_capability_and_cad_calls_never_start_a_host(self):
        self.assertFalse(self.bridge.call("status",{})["result"]["daemon_running"])
        self.manager.status.assert_called_once_with()
        self.bridge.call("capabilities",{"operation":"document.properties"})
        self.assertEqual(self.call.call_args.args,("daemon.capabilities",{"include_schemas":False,"operation":"document.properties"}))
        self.bridge.call("execute",{"operation":"document.list","parameters":{}})
        self.manager.start.assert_not_called()

    def test_start_is_explicit_with_runtime_selection_and_budget(self):
        result=self.bridge.call("daemon_start",{"visible":True,"attach_existing":True,"startup_timeout_seconds":600})
        self.assertTrue(result["success"])
        self.manager.start.assert_called_once_with(visible=True,attach_existing=True,startup_timeout_seconds=600)
        self.call.assert_not_called()

    def test_stop_is_explicit_and_preserves_refusal_without_restart(self):
        refused={"success":False,"error":{"code":"ActiveDocument","message":"close explicitly"}}
        self.manager.stop.return_value=refused
        result=self.bridge.call("daemon_stop",{"request_id":"stop-once"})
        self.assertEqual(result["error"],refused["error"])
        self.manager.stop.assert_called_once_with(request_id="stop-once",timeout_seconds=600)
        self.manager.start.assert_not_called()

    def test_execute_preserves_zero_cas_session_lease_and_request_identity(self):
        result=self.bridge.call("execute",{"operation":"document.summary.set","parameters":{"author":"中文"},"document_id":"d-ab12cd","expected_update_stamp":0,"lease_id":"l-ab12cd34ef56","session_id":"writer","request_id":"request-1"})
        self.assertTrue(result["success"])
        self.call.assert_called_once_with("document.summary.set",{"author":"中文"},endpoint="127.0.0.1:18495",timeout_seconds=600,connect_timeout_seconds=3,request_id="request-1",session_id="writer",document_id="d-ab12cd",expected_update_stamp=0,lease_id="l-ab12cd34ef56")

    def test_process_default_sessions_differ_and_explicit_shared_session_is_preserved(self):
        one,two=DaemonBridge(),DaemonBridge()
        self.assertNotEqual(one.session_id,two.session_id)
        with mock.patch.dict(os.environ,{"SWCLI_SESSION_ID":"shared"}):
            self.assertEqual(DaemonBridge().session_id,"shared")

    def test_paths_reuse_existing_mapper_without_mutating_input(self):
        args={"operation":"document.open","parameters":{"path":"/workspace/中文 零件.SLDPRT"}}
        with mock.patch.dict(os.environ,{"SWCLI_PATH_TRANSLATE_CMD":"wine-path"}),mock.patch("swcli.cli.subprocess.check_output",return_value="Z:\\workspace\\中文 零件.SLDPRT\n") as mapper:
            self.bridge.call("execute",args)
        mapper.assert_called_once_with(["wine-path",args["parameters"]["path"]],text=True)
        self.assertEqual(self.call.call_args.args[1],{"path":"Z:\\workspace\\中文 零件.SLDPRT"})

    def test_invalid_inputs_never_reach_native_transport_or_manager(self):
        for name,args in (("wrong",{}),("execute",{"operation":"document.list"}),("execute",{"operation":"daemon.shutdown","parameters":{}}),("daemon_start",{"startup_timeout_seconds":601}),("daemon_start",{"host_launcher":"/arbitrary"}),("execute",{"operation":"document.list","parameters":{},"expected_update_stamp":True})):
            with self.subTest(name=name,args=args):
                self.assertFalse(self.bridge.call(name,args)["success"])
        self.call.assert_not_called();self.manager.start.assert_not_called();self.manager.stop.assert_not_called()

    def test_future_daemon_operation_is_not_blocked_by_client_catalog(self):
        self.bridge.call("execute",{"operation":"future.operation","parameters":{"x":1}})
        self.assertEqual(self.call.call_args.args,("future.operation",{"x":1}))

    def test_native_refusal_details_are_preserved_and_never_retried(self):
        refused=response(success=False,result=None,error={"code":"DocumentLeaseConflict","message":"held","details":{"partial":True}})
        self.call.return_value=refused
        self.assertEqual(self.bridge.call("execute",{"operation":"document.save","parameters":{}}),refused)
        self.call.assert_called_once()

    def test_lost_mutation_reply_is_unknown_with_stable_id(self):
        self.call.side_effect=TimeoutError("lost reply")
        result=self.bridge.call("execute",{"operation":"document.save","parameters":{},"request_id":"once"})
        self.assertEqual(result["request_id"],"once");self.assertTrue(result["outcome_unknown"]);self.call.assert_called_once()
        self.manager.start.assert_not_called()

    def test_connect_failure_never_tries_start(self):
        error=ConnectionRefusedError("offline");error._swcli_transport_phase="connect";self.call.side_effect=error
        result=self.bridge.call("capabilities",{})
        self.assertFalse(result["outcome_unknown"]);self.manager.start.assert_not_called()

    def test_malformed_or_incompatible_native_response_fails_closed(self):
        for value in ({},response(api_version="other/v1"),response(success="yes")):
            self.call.return_value=value
            self.assertFalse(self.bridge.call("execute",{"operation":"document.list","parameters":{}})["success"])

    def test_missing_extra_error_uses_stderr_only(self):
        from swcli import mcp as adapter
        output,error=io.StringIO(),io.StringIO()
        with mock.patch.object(adapter,"serve",side_effect=ModuleNotFoundError(name="mcp")),contextlib.redirect_stdout(output),contextlib.redirect_stderr(error):
            self.assertEqual(adapter.run(build_parser().parse_args(["mcp","serve"])),2)
        self.assertEqual(output.getvalue(),"");self.assertIn("swcli[mcp]",error.getvalue())


@unittest.skipUnless(SDK_AVAILABLE,"optional official MCP SDK requires Python 3.10+")
class MCPStdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def fake_daemon(self):
        captured=[]
        state={"running":True}
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request=json.loads(self.rfile.readline());captured.append(request)
                operation=request["operation"]
                if operation=="daemon.runtime-status":
                    value=snapshot(health() if state["running"] else None,daemon_running=state["running"])
                    payload=response(request["request_id"],result=value)
                elif operation=="daemon.health":
                    payload=response(request["request_id"],result=health())
                elif operation=="daemon.shutdown":
                    state["running"]=False;payload=response(request["request_id"],result={"stopping":True})
                elif operation=="document.save":
                    payload=response(request["request_id"],success=False,result=None,error={"code":"UpdateStampConflict","message":"changed"})
                else:
                    payload=response(request["request_id"],result={"echo":request})
                self.wfile.write(json.dumps(payload,ensure_ascii=False).encode("utf-8")+b"\n")
        daemon=socketserver.ThreadingTCPServer(("127.0.0.1",0),Handler)
        threading.Thread(target=daemon.serve_forever,daemon=True).start()
        self.addCleanup(daemon.server_close);self.addCleanup(daemon.shutdown)
        return daemon,captured

    def parameters(self,daemon):
        from mcp import StdioServerParameters
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/"src"))
        for key in ("SWCLI_SESSION_ID","SWCLI_DAEMON_UTILS","SWCLI_DAEMON_UTILS_ACTIVE","SWCLI_PATH_TRANSLATE_CMD"):
            env.pop(key,None)
        return StdioServerParameters(command=sys.executable,args=["-m","swcli","--endpoint",f"127.0.0.1:{daemon.server_address[1]}","mcp","serve"],env=env)

    async def test_official_sdk_discovery_lifecycle_progress_errors_and_eof(self):
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        daemon,captured=self.fake_daemon()
        messages=[]
        async def progress(value,total,message):messages.append(message)
        with tempfile.TemporaryFile(mode="w+",encoding="utf-8") as errors:
            async with stdio_client(self.parameters(daemon),errlog=errors) as streams:
                async with ClientSession(*streams,read_timeout_seconds=timedelta(seconds=15)) as session:
                    initialized=await session.initialize();self.assertEqual(initialized.serverInfo.name,"swcli")
                    self.assertEqual([tool.name for tool in (await session.list_tools()).tools],
                                     ["status", "daemon_start", "daemon_stop", "capabilities", "execute"])
                    self.assertNotIn("swcli_", initialized.instructions)
                    self.assertEqual(captured,[])
                    status=await session.call_tool("status",{});self.assertFalse(status.isError)
                    started=await session.call_tool("daemon_start",{},progress_callback=progress)
                    self.assertTrue(started.structuredContent["result"]["already_running"])
                    self.assertTrue(any(message and "SOLIDWORKS" in message for message in messages))
                    capabilities=await session.call_tool("capabilities",{"operation":"document.summary"})
                    self.assertEqual(capabilities.structuredContent["result"]["echo"]["parameters"],{"include_schemas":False,"operation":"document.summary"})
                    result=await session.call_tool("execute",{"operation":"document.list","parameters":{},"request_id":"once"})
                    self.assertEqual(result.structuredContent["request_id"],"once")
                    self.assertEqual(json.loads(result.content[0].text),result.structuredContent)
                    refused=await session.call_tool("execute",{"operation":"document.save","parameters":{}})
                    self.assertTrue(refused.isError)
                    before=len(captured)
                    self.assertTrue((await session.call_tool("execute",{"operation":"document.list"})).isError)
                    self.assertEqual(len(captured),before)
                    stopped=await session.call_tool("daemon_stop",{})
                    self.assertFalse(stopped.isError)
                    observed=await session.call_tool("status",{})
                    self.assertFalse(observed.structuredContent["result"]["daemon_running"])
                    await session.send_ping()
        self.assertEqual([r["operation"] for r in captured].count("daemon.shutdown"),1)

    async def test_two_mcp_clients_have_distinct_sessions_and_disconnect_does_not_stop_daemon(self):
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        daemon,captured=self.fake_daemon();parameters=self.parameters(daemon)
        async with stdio_client(parameters) as second_streams:
            async with ClientSession(*second_streams,read_timeout_seconds=timedelta(seconds=15)) as second:
                await second.initialize()
                async with stdio_client(parameters) as first_streams:
                    async with ClientSession(*first_streams,read_timeout_seconds=timedelta(seconds=15)) as first:
                        await first.initialize()
                        one=await first.call_tool("execute",{"operation":"document.list","parameters":{}})
                        two=await second.call_tool("execute",{"operation":"document.list","parameters":{}})
                        self.assertNotEqual(one.structuredContent["result"]["echo"]["session_id"],two.structuredContent["result"]["echo"]["session_id"])
                self.assertFalse((await second.call_tool("status",{})).isError)
        self.assertNotIn("daemon.shutdown",[r["operation"] for r in captured])
