import io
import json
import unittest
from unittest import mock

from swcli import PROTOCOL_VERSION
from swcli.daemon import client, operations, server


class DaemonProtocolTests(unittest.TestCase):
    def test_resident_lifetime_selects_official_background_control(self):
        hidden = mock.Mock()
        server.configure_resident_app(hidden, visible=False)
        self.assertTrue(hidden.UserControlBackground)
        self.assertFalse(hidden.Visible)

        visible = mock.Mock()
        server.configure_resident_app(visible, visible=True)
        self.assertTrue(visible.UserControl)
        self.assertTrue(visible.Visible)

    def test_endpoint_parser_validates_host_and_port(self):
        self.assertEqual(client.parse_endpoint("127.0.0.1:18495"), ("127.0.0.1", 18495))
        with self.assertRaisesRegex(ValueError, "HOST:PORT"):
            client.parse_endpoint("18495")
        with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
            client.parse_endpoint("127.0.0.1:70000")

    def test_client_sends_versioned_request_and_checks_request_id(self):
        response = {
            "api_version": PROTOCOL_VERSION,
            "request_id": "request-1",
            "success": True,
            "duration_ms": 1.0,
            "result": {"ok": True},
        }

        class Connection:
            def __init__(self):
                self.sent = b""

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def settimeout(self, timeout):
                self.timeout = timeout

            def sendall(self, value):
                self.sent += value

            def makefile(self, mode):
                return io.BytesIO(json.dumps(response).encode("utf-8") + b"\n")

        connection = Connection()
        with mock.patch.object(
            client.socket, "create_connection", return_value=connection
        ):
            actual = client.call_daemon(
                "daemon.health",
                endpoint="127.0.0.1:18495",
                timeout_seconds=2.0,
                request_id="request-1",
            )

        request = json.loads(connection.sent.decode("utf-8"))
        self.assertEqual(request["api_version"], PROTOCOL_VERSION)
        self.assertEqual(request["operation"], "daemon.health")
        self.assertEqual(request["timeout_ms"], 2000)
        self.assertEqual(actual, response)

    def test_request_validation_rejects_unknown_protocol(self):
        with self.assertRaisesRegex(ValueError, "unsupported api_version"):
            server.validate_request(
                {
                    "api_version": "swcli/v2",
                    "request_id": "request-1",
                    "operation": "daemon.health",
                    "parameters": {},
                }
            )

    @mock.patch("swcli.daemon.operations.batch_export_windows")
    def test_batch_operation_reuses_worker_owned_app(self, batch_export_windows):
        app = object()
        batch_export_windows.return_value = {"ok": True}

        result = operations.execute_operation(
            app,
            "batch.export",
            {
                "manifest": "C:\\list.txt",
                "workspace": "C:\\",
                "outdir": "Z:\\output",
                "overwrite": True,
            },
        )

        self.assertEqual(result, {"ok": True})
        batch_export_windows.assert_called_once_with(
            "C:\\list.txt",
            workspace="C:\\",
            outdir="Z:\\output",
            overwrite=True,
            app=app,
        )

    @mock.patch("swcli.daemon.operations.open_windows_document")
    def test_document_operation_reuses_worker_owned_app(self, open_document):
        app = object()
        open_document.return_value = {"ok": True}

        result = operations.execute_operation(
            app,
            "document.open",
            {
                "path": "C:\\part.SLDPRT",
                "read_only": True,
                "configuration": "Default",
            },
        )

        self.assertEqual(result, {"ok": True})
        open_document.assert_called_once_with(
            "C:\\part.SLDPRT",
            read_only=True,
            configuration="Default",
            app=app,
        )


if __name__ == "__main__":
    unittest.main()
