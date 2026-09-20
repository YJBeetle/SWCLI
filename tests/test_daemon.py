import io
import json
import os
import tempfile
import unittest
from unittest import mock

from swcli import PROTOCOL_VERSION
from swcli.daemon import client, operations, server
from swcli.daemon.main import start_daemon


class DaemonProtocolTests(unittest.TestCase):
    @mock.patch("swcli.daemon.main.call_daemon")
    def test_background_start_is_idempotent(self, call_daemon):
        call_daemon.return_value = {
            "success": True,
            "result": {"worker_alive": True},
        }

        with mock.patch("swcli.daemon.main.sys.platform", "win32"):
            result = start_daemon(endpoint="127.0.0.1:18495")

        self.assertTrue(result["success"])
        self.assertTrue(result["result"]["already_running"])
        self.assertFalse(result["result"]["started"])

    @mock.patch("swcli.daemon.main.subprocess.Popen")
    @mock.patch("swcli.daemon.main.call_daemon")
    def test_background_start_launches_serve_and_waits_for_health(
        self, call_daemon, popen
    ):
        call_daemon.side_effect = [
            ConnectionRefusedError("offline"),
            {"success": True, "result": {"worker_alive": True}},
        ]
        process = popen.return_value
        process.pid = 4321
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"LOCALAPPDATA": directory}
        ), mock.patch("swcli.daemon.main.sys.platform", "win32"):
            result = start_daemon(
                endpoint="127.0.0.1:19000", startup_timeout_seconds=5.0
            )

        self.assertTrue(result["success"])
        self.assertTrue(result["result"]["started"])
        command = popen.call_args.args[0]
        self.assertEqual(command[:4], [mock.ANY, "-m", "swcli", "daemon"])
        self.assertIn("serve", command)
        self.assertIn("19000", command)

    @mock.patch("swcli.daemon.main.subprocess.Popen")
    @mock.patch("swcli.daemon.main.call_daemon")
    def test_background_start_treats_local_connect_timeout_as_offline(
        self, call_daemon, popen
    ):
        call_daemon.side_effect = [
            TimeoutError("timed out"),
            {"success": True, "result": {"worker_alive": True}},
        ]
        process = popen.return_value
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"LOCALAPPDATA": directory}
        ), mock.patch("swcli.daemon.main.sys.platform", "win32"):
            result = start_daemon(
                endpoint="127.0.0.1:19000", startup_timeout_seconds=5.0
            )

        self.assertTrue(result["success"])
        self.assertTrue(result["result"]["started"])
        popen.assert_called_once()

    def test_resident_lifetime_selects_official_background_control(self):
        hidden = mock.Mock()
        server.configure_resident_app(hidden, visible=False)
        self.assertTrue(hidden.UserControlBackground)
        self.assertFalse(hidden.Visible)

        visible = mock.Mock()
        server.configure_resident_app(visible, visible=True)
        self.assertTrue(visible.UserControl)
        self.assertTrue(visible.Visible)

    @mock.patch("swcli.daemon.server.configure_resident_app")
    def test_resident_app_preserves_existing_user_instance(self, configure):
        app = object()
        com_client = mock.Mock()
        com_client.GetActiveObject.return_value = app

        actual, owned_by_daemon = server.acquire_resident_app(
            com_client, visible=False
        )

        self.assertIs(actual, app)
        self.assertFalse(owned_by_daemon)
        com_client.DispatchEx.assert_not_called()
        configure.assert_not_called()

    @mock.patch("swcli.daemon.server.configure_resident_app")
    def test_resident_app_configures_new_daemon_instance(self, configure):
        app = object()
        com_client = mock.Mock()
        com_client.GetActiveObject.side_effect = RuntimeError("not running")
        com_client.DispatchEx.return_value = app

        actual, owned_by_daemon = server.acquire_resident_app(
            com_client, visible=False
        )

        self.assertIs(actual, app)
        self.assertTrue(owned_by_daemon)
        com_client.DispatchEx.assert_called_once_with(server.PROG_ID)
        configure.assert_called_once_with(app, visible=False)

    @mock.patch("swcli.daemon.server.subprocess.run")
    def test_worker_termination_does_not_kill_attached_user_instance(self, run):
        manager = object.__new__(server.WorkerManager)
        process = mock.Mock()
        process.is_alive.side_effect = [True, False]
        manager._process = process
        manager.host = {"process_id": 1234, "owned_by_daemon": False}

        manager._terminate_worker()

        process.terminate.assert_called_once()
        run.assert_not_called()

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
        ) as create_connection:
            actual = client.call_daemon(
                "daemon.health",
                endpoint="127.0.0.1:18495",
                timeout_seconds=2.0,
                connect_timeout_seconds=0.5,
                request_id="request-1",
            )

        request = json.loads(connection.sent.decode("utf-8"))
        self.assertEqual(request["api_version"], PROTOCOL_VERSION)
        self.assertEqual(request["operation"], "daemon.health")
        self.assertEqual(request["timeout_ms"], 2000)
        create_connection.assert_called_once_with(
            ("127.0.0.1", 18495), timeout=0.5
        )
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

    @mock.patch("swcli.daemon.operations.export_active_windows_document")
    def test_export_can_require_strict_source_state(self, export_document):
        app = object()
        export_document.return_value = {"ok": True}

        result = operations.execute_operation(
            app,
            "document.export",
            {
                "output": "C:\\drawing.DWG",
                "overwrite": True,
                "strict": True,
            },
        )

        self.assertEqual(result, {"ok": True})
        export_document.assert_called_once_with(
            "C:\\drawing.DWG",
            overwrite=True,
            strict=True,
            app=app,
        )

    @mock.patch("swcli.daemon.operations.save_active_windows_document")
    def test_document_save_reuses_worker_owned_app(self, save_document):
        app = object()
        save_document.return_value = {"ok": True}

        result = operations.execute_operation(app, "document.save", {})

        self.assertEqual(result, {"ok": True})
        save_document.assert_called_once_with(app=app)


if __name__ == "__main__":
    unittest.main()
