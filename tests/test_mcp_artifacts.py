"""Bounded native-output capture and actual SDK/TCP/stdio artifact delivery."""

import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socketserver
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace, ModuleType
import unittest
from unittest import mock

from swcli.artifact_content import capture_content, MAX_ARTIFACT_BYTES
from swcli.mcp import DaemonBridge
from swcli.operation_schemas import validate_operation_request
from swcli.result_schemas import ARTIFACT_CONTENT
from jsonschema import Draft202012Validator

SDK = sys.version_info >= (3, 10) and importlib.util.find_spec("mcp") is not None
PIL = importlib.util.find_spec("PIL") is not None


def bitmap():
    pixels = b"\x00\x00\xff\x00\xff\x00\x00\x00" * 2
    return (struct.pack("<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
            + struct.pack("<IiiHHIIiiII", 40, 2, 2, 1, 24, 0, len(pixels), 0, 0, 0, 0) + pixels)


def ready(data):
    return {"status": "ready", "limit_bytes": MAX_ARTIFACT_BYTES,
            "sha256": hashlib.sha256(data).hexdigest(), "data_base64": base64.b64encode(data).decode()}


def response(result, request_id="test"):
    return {"api_version": "swcli/v1", "request_id": request_id,
            "duration_ms": 0, "success": True, "result": result}


def artifact(data, image=False):
    return {"kind": "image" if image else "cad-export", "size_bytes": len(data),
            "path": r"Z:\only-on-daemon\中文 图纸.bmp" if image else r"Z:\only-on-daemon\中文 图纸.pdf",
            **({"media_type": "image/bmp"} if image else {"format": "PDF"}), "content": ready(data)}


class CaptureTests(unittest.TestCase):
    def test_bytes_are_captured_with_hash_and_no_generic_read_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "temporary.pdf"
            data = b"%PDF-1.7\nverified output"
            p.write_bytes(data)
            result = capture_content(p, len(data))
            self.assertEqual(base64.b64decode(result["data_base64"]), data)
            self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
            Draft202012Validator(ARTIFACT_CONTENT).validate(result)
        for operation in ("document.render", "document.export"):
            self.assertEqual(validate_operation_request(operation, {"output": "out", "include_content": True}),
                             {"output": "out", "include_content": True})

    def test_too_large_never_opens_a_file_and_inexact_size_never_leaks_bytes(self):
        with mock.patch("swcli.artifact_content.os.open") as opened:
            result = capture_content("unused", MAX_ARTIFACT_BYTES + 1)
        self.assertEqual(result["status"], "too_large"); opened.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "output"; p.write_bytes(b"abc")
            result = capture_content(p, 2)
            self.assertEqual(result["status"], "unavailable")
            self.assertNotIn("data_base64", result)

    def test_symlink_is_not_followed_and_read_errors_remain_delivery_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "secret"; target.write_bytes(b"secret")
            link = Path(directory) / "link"
            try:
                link.symlink_to(target)
            except OSError:
                pass  # Windows user may not have symlink creation privilege.
            else:
                result = capture_content(link, 6)
                self.assertEqual(result["status"], "unavailable")
                self.assertNotIn("data_base64", result)
            with mock.patch("swcli.artifact_content.os.open", side_effect=PermissionError("denied")):
                result = capture_content(target, 6)
            self.assertEqual(result["error"]["code"], "PermissionError")

    def test_native_outputs_capture_only_their_verified_temporary_file(self):
        from tests.save_as_fixture import save_as_fixture
        from swcli.hosts import windows_documents as native
        data = b"%PDF-1.7\nverified output"
        class Document:
            Extension = SimpleNamespace(NeedsRebuild2=0)
            def ViewZoomtofit2(self): pass
            def ClearSelection2(self, _): pass
            def SaveBMP(self, path, width, height):
                Path(path).write_bytes(bitmap()); return True
            def SaveAs3(self, path, version, options, export_data, advanced_options, errors, warnings):
                Path(path).write_bytes(data)
                errors.value = 0
                warnings.value = 0
                return True
        document = Document()
        app = mock.Mock(ActiveDoc=document)
        pythoncom = ModuleType("pythoncom")
        win32com = ModuleType("win32com")
        win32com.client = ModuleType("win32com.client")
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, {"pythoncom": pythoncom, "win32com": win32com, "win32com.client": win32com.client}), mock.patch.object(native, "save_as3", side_effect=save_as_fixture), mock.patch.object(native.sys, "platform", "win32"), mock.patch.object(native, "_describe_document", return_value={"title": "drawing", "path": "source.SLDDRW", "type": 3, "modified": False}), mock.patch.object(native, "capture_content", wraps=capture_content) as capture:
            for image in (True, False):
                target = Path(directory) / ("view.bmp" if image else "view.pdf")
                result = (native.render_active_windows_document(str(target), width=2, height=2, app=app, include_content=True)
                          if image else native.export_active_windows_document(str(target), app=app, include_content=True))
                self.assertTrue(result["ok"], result)
                self.assertNotEqual(Path(capture.call_args.args[0]), target)
                self.assertEqual(base64.b64decode(result["artifact"]["content"]["data_base64"]), target.read_bytes())
                self.assertFalse(Path(capture.call_args.args[0]).exists())
            # A delivery failure does not erase a successful CAD export.
            capture.return_value = {"status": "unavailable", "limit_bytes": MAX_ARTIFACT_BYTES,
                                    "error": {"code": "PermissionError", "message": "denied"}}
            capture.side_effect = lambda *args: capture.return_value
            target = Path(directory) / "still-saved.pdf"
            result = native.export_active_windows_document(str(target), app=app, include_content=True)
            self.assertTrue(result["ok"]); self.assertTrue(target.is_file())
            self.assertEqual(result["artifact"]["content"]["status"], "unavailable")


class NegotiationTests(unittest.TestCase):
    def test_automatic_capture_is_negotiated_and_context_retained_once(self):
        capability = response({"operation_schemas": {"document.export": {"properties": {"include_content": {"type": "boolean"}}}}})
        args = {"operation": "document.export", "parameters": {"output": "file.pdf"},
                "request_id": "export-once", "session_id": "writer", "document_id": "d-ab12cd",
                "expected_update_stamp": 0, "lease_id": "l-ab12cd34ef56"}
        with mock.patch("swcli.mcp.call_daemon", side_effect=[capability, response({"ok": True})]) as transport:
            result = DaemonBridge().call("execute", args)
        self.assertTrue(result["success"])
        self.assertEqual([c.args[0] for c in transport.call_args_list], ["daemon.capabilities", "document.export"])
        call = transport.call_args
        self.assertTrue(call.args[1]["include_content"])
        for key in ("request_id", "session_id", "document_id", "expected_update_stamp", "lease_id"):
            self.assertEqual(call.kwargs[key], args[key])
        self.assertNotIn("include_content", args["parameters"])

    def test_old_daemon_gets_original_parameters_and_explicit_false_needs_no_probe(self):
        with mock.patch("swcli.mcp.call_daemon", side_effect=[response({}), response({"ok": True})]) as transport:
            self.assertTrue(DaemonBridge().call("execute", {"operation": "document.export", "parameters": {"output": "out.pdf"}})["success"])
            self.assertEqual(transport.call_args.args[1], {"output": "out.pdf"})
        with mock.patch("swcli.mcp.call_daemon", return_value=response({})) as transport:
            DaemonBridge().call("execute", {"operation": "document.render", "parameters": {"output": "out.bmp", "include_content": False}})
            transport.assert_called_once()


@unittest.skipUnless(SDK and PIL, "optional MCP + Pillow extras")
class PresentationTests(unittest.TestCase):
    def test_preview_is_png_and_file_is_exact_binary_without_reading_host_path(self):
        from swcli.mcp_artifacts import tool_result
        from PIL import Image
        raw = bitmap(); payload = response({"artifact": artifact(raw, image=True)})
        shown = tool_result(payload, "document.render")
        self.assertFalse(shown.isError)
        preview = shown.content[1]
        self.assertEqual(preview.mimeType, "image/png")
        with Image.open(io.BytesIO(base64.b64decode(preview.data))) as image:
            self.assertEqual(image.size, (2, 2))
        transfer = shown.structuredContent["result"]["artifact"]["content"]
        self.assertEqual(transfer["status"], "attached")
        self.assertEqual(transfer["preview_sha256"], hashlib.sha256(base64.b64decode(preview.data)).hexdigest())
        Draft202012Validator(ARTIFACT_CONTENT).validate(transfer)
        self.assertNotIn("data_base64", shown.content[0].text)
        self.assertIn("data_base64", payload["result"]["artifact"]["content"])
        raw = b"%PDF-1.7\noutput"; shown = tool_result(response({"artifact": artifact(raw)}), "document.export")
        resource = shown.content[1].resource
        self.assertEqual(base64.b64decode(resource.blob), raw)
        self.assertEqual(resource.mimeType, "application/pdf")
        self.assertTrue(str(resource.uri).startswith("swcli-artifact://"))
        self.assertNotIn("only-on-daemon", str(resource.uri))

    def test_failed_or_large_delivery_never_changes_cad_success_or_returns_binary(self):
        from swcli.mcp_artifacts import tool_result
        for failure in ({"status": "too_large", "limit_bytes": MAX_ARTIFACT_BYTES},
                        {**ready(b"abc"), "sha256": "0" * 64},
                        {**ready(b"abc"), "data_base64": "not base64"}):
            a = artifact(b"abc"); a["content"] = failure
            result = tool_result(response({"ok": True, "artifact": a}), "document.export")
            self.assertFalse(result.isError)
            self.assertTrue(result.structuredContent["success"])
            self.assertTrue(result.structuredContent["result"]["ok"])
            self.assertEqual(len(result.content), 1)
            self.assertNotIn("data_base64", result.content[0].text)


@unittest.skipUnless(SDK and PIL, "optional MCP + Pillow extras")
class SDKArtifactTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_sdk_receives_image_and_file_over_real_stdio_and_tcp(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        captured = []
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request = json.loads(self.rfile.readline()); captured.append(request)
                if request["operation"] == "daemon.capabilities":
                    op = request["parameters"]["operation"]
                    value = {"operation_schemas": {op: {"properties": {"include_content": {"type": "boolean"}}}}}
                else:
                    image = request["operation"] == "document.render"
                    value = {"ok": True, "artifact": artifact(bitmap() if image else b"%PDF-1.7\nfixture", image)}
                self.wfile.write(json.dumps(response(value, request["request_id"])).encode() + b"\n")
        daemon = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=daemon.serve_forever, daemon=True).start()
        self.addCleanup(daemon.server_close); self.addCleanup(daemon.shutdown)
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        env.pop("SWCLI_PATH_TRANSLATE_CMD", None)
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "swcli", "--endpoint", "127.0.0.1:" + str(daemon.server_address[1]), "mcp", "serve"], env=env)
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                for operation, output in (("document.render", "remote.bmp"), ("document.export", "remote.pdf")):
                    result = await session.call_tool("execute", {"operation": operation, "parameters": {"output": output}, "request_id": operation})
                    self.assertFalse(result.isError)
                    self.assertEqual(result.content[1].type, "image" if output.endswith("bmp") else "resource")
                    self.assertNotIn("data_base64", result.content[0].text)
                    self.assertEqual(result.structuredContent["result"]["artifact"]["content"]["status"], "attached")
        self.assertEqual([r["operation"] for r in captured], ["daemon.capabilities", "document.render", "daemon.capabilities", "document.export"])
        self.assertTrue(all(r["parameters"]["include_content"] for r in captured if r["operation"].startswith("document.")))
