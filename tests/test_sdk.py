"""SDK contracts: typed wrappers, actual TCP/TLS, CAS and failure boundaries."""

import base64
from copy import deepcopy
import importlib.util
import inspect
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from swcli.operation_schemas import OPERATION_CATALOG
from swcli.sdk import Client, ProtocolError, RemoteError, Response, TLSConfig, TransportError, UNSET
from swcli.sdk.runtime import Error

ROOT = Path(__file__).resolve().parents[1]


def envelope(result=None, *, success=True, request_id="request", error=None):
    value = {"api_version": "swcli/v1", "success": success, "request_id": request_id, "duration_ms": 1.25}
    value["result" if success else "error"] = result if success else error
    return value


def document(stamp=0):
    return {"title": "part", "path": "", "type": 1, "modified": False,
            "update_stamp": stamp, "document_id": "d-ab12cd", "current": True, "active": True}


def inspected():
    return {"ok": True, "action": "document.inspect", "document": document(),
            "needs_rebuild": 0}


class GeneratedSDKTests(unittest.TestCase):
    def test_generator_reproduces_models_and_methods_for_every_operation(self):
        spec = importlib.util.spec_from_file_location("sdk_generator", ROOT / "scripts/dev/generate-sdk.py")
        generator = importlib.util.module_from_spec(spec); spec.loader.exec_module(generator)
        for name, text in generator.render().items():
            self.assertEqual((ROOT / "src/swcli/sdk" / name).read_text(encoding="utf-8"), text)
        client = Client()
        operations = []
        for operation, schema in OPERATION_CATALOG.items():
            method = client
            for part in operation.split("."):
                method = getattr(method, part.replace("-", "_"))
            signature = inspect.signature(method)
            self.assertIn("request_id", signature.parameters)
            self.assertEqual(set(signature.parameters) - {"request_id"},
                set(schema.parameters["properties"]) | {key for key, mode in schema.parameters["x-swcli-context"].items() if mode != "forbidden"})
            operations.append(operation)
        self.assertEqual(len(operations), len(OPERATION_CATALOG))

    def test_constructing_and_discovering_namespaces_does_not_connect_or_start(self):
        with patch("swcli.sdk.client.call_daemon") as wire, patch("socket.create_connection") as connect:
            first, second = Client(), Client()
            self.assertNotEqual(first.session_id, second.session_id)
            self.assertTrue(callable(first.document.lease.acquire))
            wire.assert_not_called(); connect.assert_not_called()

    def test_omission_false_zero_and_empty_strings_are_distinct_on_wire(self):
        client = Client(session_id="chosen")
        def call(operation, parameters, **kw):
            return envelope({"stopping": True}, request_id=kw["request_id"])
        with patch("swcli.sdk.client.call_daemon", side_effect=call) as wire, \
                patch("swcli.sdk.client.validate_operation_result"):
            client.document.open(path="C:\\Workspace\\part.SLDPRT", read_only=False, configuration="", request_id="one")
            self.assertEqual(wire.call_args.args[1], {"path": "C:\\Workspace\\part.SLDPRT", "read_only": False, "configuration": ""})
            client.document.open(path="part.SLDPRT", read_only=UNSET)
            self.assertEqual(wire.call_args.args[1], {"path": "part.SLDPRT"})
            client.document.property_set(name="empty", value="", expected_value="", document_id="d-ab12cd",
                expected_update_stamp=0, lease_id="l-ab12cd34ef56", request_id="write-once")
            self.assertEqual(wire.call_args.kwargs["expected_update_stamp"], 0)
            self.assertEqual(wire.call_args.kwargs["session_id"], "chosen")
            self.assertEqual(wire.call_args.kwargs["lease_id"], "l-ab12cd34ef56")
            self.assertEqual(wire.call_args.kwargs["request_id"], "write-once")

    def test_bad_bounds_context_unknown_fields_and_nonfinite_values_fail_before_io(self):
        client = Client()
        calls = [lambda: client.document.units_set(decimal_places=-1),
                 lambda: client.document.open(path="x", read_only=None),
                 lambda: client.execute("document.open", {"path": "x", "bogus": True}),
                 lambda: client.execute("document.open", {"path": "x"}, document_id="active"),
                 lambda: client.feature.extrude(sketch_id="s-ab12cd", depth_mm=float("nan")),
                 lambda: client.document.units_set(),
                 lambda: client.document.lease.renew(lease_id="bad"),
                 lambda: client.execute("unknown.operation", {}),
                 lambda: client.document.list(request_id="")]
        with patch("swcli.sdk.client.call_daemon") as wire:
            for call in calls:
                with self.subTest(call=call), self.assertRaises(Exception):
                    call()
            wire.assert_not_called()

    def test_result_fields_and_original_error_and_partial_state_are_preserved(self):
        client = Client()
        failure = {"ok": False, "action": "document.inspect", "error": {"type": "NativeRefusal", "message": "partial", "details": {"stage": "setter", "mutation": {"attempted": True, "may_have_changed": True}}}}
        # Native partial payloads are exposed, not replaced with an empty success.
        raw = envelope(failure, request_id="partial")
        with patch("swcli.sdk.client.call_daemon", return_value=raw):
            response = client.document.inspect(request_id="partial")
        self.assertTrue(response.success); self.assertFalse(response.ok)
        self.assertEqual(response.error, Error("NativeRefusal", "partial", {"stage": "setter", "mutation": {"attempted": True, "may_have_changed": True}}))
        with self.assertRaises(RemoteError) as caught:
            response.require_result()
        self.assertIs(caught.exception.response, response)
        self.assertEqual(caught.exception.response.raw["result"]["error"]["details"], failure["error"]["details"])
        self.assertFalse(caught.exception.outcome_unknown)
        refused = envelope(success=False, request_id="cas", error={"code": "DocumentUpdateConflict", "message": "changed", "details": {"expected": 0}})
        with patch("swcli.sdk.client.call_daemon", return_value=refused) as wire:
            result = client.document.inspect(expected_update_stamp=0, request_id="cas")
        self.assertFalse(result.ok); self.assertEqual(result.error.code, "DocumentUpdateConflict")
        self.assertEqual(wire.call_count, 1)

    def test_transport_errors_keep_request_id_and_never_retry(self):
        for phase, unknown in (("connect", False), ("tls", False), ("authenticate", False), (None, True)):
            error = ConnectionError("connection ended")
            if phase:
                error._swcli_transport_phase = phase
            with self.subTest(phase=phase), patch("swcli.sdk.client.call_daemon", side_effect=error) as wire:
                with self.assertRaises(TransportError) as caught:
                    Client().document.save(document_id="d-ab12cd", request_id="keep-this-id")
                self.assertEqual(caught.exception.request_id, "keep-this-id")
                self.assertEqual(caught.exception.outcome_unknown, unknown)
                self.assertIs(caught.exception.__cause__, error)
                wire.assert_called_once()

    def test_invalid_response_summary_does_not_repeat_large_binary_payload(self):
        raw = envelope(inspected(), request_id="large-invalid")
        raw["unexpected"] = "private-binary-payload" * 10000
        with patch("swcli.sdk.client.call_daemon", return_value=raw):
            with self.assertRaises(ProtocolError) as caught:
                Client().document.inspect(request_id="large-invalid")
        self.assertNotIn("private-binary-payload", str(caught.exception))
        self.assertLess(len(str(caught.exception)), 1200)
        self.assertEqual(caught.exception.raw, raw)
        self.assertIsNotNone(caught.exception.__cause__)

    def test_response_envelope_and_operation_schema_are_validated(self):
        for raw in (envelope({"stopping": True}, request_id="wrong"),
                    envelope({}, request_id="same"), {"success": True, "request_id": "same"}):
            with self.subTest(raw=raw), patch("swcli.sdk.client.call_daemon", return_value=raw):
                with self.assertRaises(ProtocolError) as caught:
                    Client().document.inspect(request_id="same")
                self.assertEqual(caught.exception.raw, raw)
                self.assertTrue(caught.exception.outcome_unknown)


class SDKSocketTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        requests = self.requests
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request = json.loads(self.rfile.readline()); requests.append(request)
                if request["operation"] == "document.inspect":
                    result = inspected()
                elif request["operation"] == "document.lease.release":
                    result = {"ok": True, "action": "document.lease.release", "released": True}
                else:
                    result = {"ok": True, "action": "document.list", "documents": [], "count": 0, "current_document_id": None, "session_id": request["session_id"]}
                reply = envelope(result, request_id=request["request_id"])
                self.wfile.write(json.dumps(reply).encode() + b"\n")
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.client = Client(endpoint="127.0.0.1:" + str(self.server.server_address[1]), session_id="reader")

    def test_actual_tcp_typed_result_cas_and_session_match_protocol(self):
        response = self.client.document.inspect(document_id="d-ab12cd", expected_update_stamp=0, request_id="inspect-once")
        self.assertTrue(response.ok); self.assertFalse(response.replayed)
        self.assertEqual(response.require_result()["document"]["update_stamp"], 0)
        self.assertEqual(response.duration_ms, 1.25)
        self.assertEqual(self.requests[0]["document_id"], "d-ab12cd")
        self.assertEqual(self.requests[0]["session_id"], "reader")
        self.assertEqual(self.requests[0]["expected_update_stamp"], 0)
        self.assertEqual(self.requests[0]["request_id"], "inspect-once")
        self.assertNotIn("lease_id", self.requests[0])

    def test_different_clients_do_not_share_a_default_session(self):
        one, two = Client(endpoint=self.client.endpoint), Client(endpoint=self.client.endpoint)
        a = one.document.list().require_result(); b = two.document.list().require_result()
        self.assertNotEqual(a["session_id"], b["session_id"])


class SDKTLSTransferTests(unittest.TestCase):
    def test_per_client_tls_and_large_files_do_not_mutate_process_environment(self):
        from tests.test_secure_transport import certificate
        from swcli.daemon.server import SwclidServer
        from swcli.secure_transport import ServerSecurity
        from swcli.workspace import WorkspaceStore
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); cert, key = certificate(root / "tls")
            token = root / "token"; token.write_text("sdk-test-token-" + "a" * 32)
            local, host = root / "client", root / "host"; local.mkdir(); host.mkdir()
            store = WorkspaceStore(host)
            server = SwclidServer(("127.0.0.1", 0), None, workspace=store,
                security=ServerSecurity.load(str(cert), str(key), str(token)))
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
            try:
                before = {k:v for k,v in os.environ.items() if k.startswith("SWCLI_")}
                tls = TLSConfig(ca_file=cert, token_file=token, server_name="localhost")
                client = Client(endpoint="127.0.0.1:" + str(server.server_address[1]), tls=tls, client_workspace=local)
                data = b"sdk-bytes" * (1024 * 1024 + 1)
                (local / "source.bin").write_bytes(data)
                upload = client.files.upload("source.bin", "received.bin")
                self.assertGreater(upload["size_bytes"], 8 * 1024 * 1024)
                download = client.files.download("received.bin", "result.bin")
                self.assertEqual((local / "result.bin").read_bytes(), data)
                self.assertEqual(upload["sha256"], download["sha256"])
                reply = client.workspace.download_begin(path="received.bin").require_result()
                self.assertEqual(reply["sha256"], upload["sha256"])
                client.workspace.download_end(transfer_id=reply["transfer_id"]).require_result()
                self.assertEqual({k:v for k,v in os.environ.items() if k.startswith("SWCLI_")}, before)
            finally:
                server.shutdown(); server.server_close()
