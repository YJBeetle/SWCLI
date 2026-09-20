import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from swcli import PROTOCOL_VERSION
from swcli.daemon import client, operations, server
from swcli.daemon.documents import (
    DocumentRegistry,
    NoCurrentDocument,
)
from swcli.daemon.main import _read_startup_failure, start_daemon


class DaemonProtocolTests(unittest.TestCase):
    class FakeDocument:
        def __init__(self, title, path, document_type=1):
            self.title = title
            self.path = path
            self.document_type = document_type

        def GetTitle(self):
            return self.title

        def GetPathName(self):
            return self.path

        def GetType(self):
            return self.document_type

        def GetSaveFlag(self):
            return False

    class FakeApp:
        def __init__(self, documents=(), active=None):
            self.documents = list(documents)
            self.ActiveDoc = active

        def GetDocuments(self):
            return tuple(self.documents)

        def GetOpenDocumentByName(self, path):
            return next(
                (document for document in self.documents if document.path == path),
                None,
            )

    def test_host_description_reports_solidworks_language(self):
        class App:
            RevisionNumber = "33.5.0"
            Visible = False

            @staticmethod
            def GetCurrentLanguage():
                return "chinese-simplified"

            @staticmethod
            def GetProcessID():
                return 1234

        app = App()

        description = server._describe_app(
            app, 0.5, owned_by_daemon=True
        )

        self.assertEqual("33.5.0", description["solidworks_revision"])
        self.assertEqual("chinese-simplified", description["language"])

    def test_document_registry_uses_short_ids_and_session_current(self):
        first = self.FakeDocument("first.SLDPRT", "C:\\first.SLDPRT")
        second = self.FakeDocument("second.SLDPRT", "C:\\second.SLDPRT")
        app = self.FakeApp([first, second], active=second)
        registry = DocumentRegistry(app)

        first_entry = registry.register(first)
        second_entry = registry.register(second)
        registry.set_current(first_entry, session_id="agent-a")
        registry.set_current(second_entry, session_id="agent-b")

        self.assertRegex(first_entry.document_id, r"^d-[0-9a-hjkmnp-tv-z]{6}$")
        self.assertNotEqual(first_entry.document_id, second_entry.document_id)
        self.assertIs(
            registry.resolve(None, session_id="agent-a").document, first
        )
        self.assertIs(
            registry.resolve(None, session_id="agent-b").document, second
        )

    def test_active_selector_is_one_shot_and_does_not_change_current(self):
        first = self.FakeDocument("first.SLDPRT", "C:\\first.SLDPRT")
        second = self.FakeDocument("second.SLDPRT", "C:\\second.SLDPRT")
        app = self.FakeApp([first, second], active=second)
        registry = DocumentRegistry(app)
        first_entry = registry.register(first)
        registry.set_current(first_entry, session_id="default")

        active_entry = registry.resolve("active", session_id="default")

        self.assertIs(active_entry.document, second)
        self.assertIs(
            registry.resolve(None, session_id="default").document, first
        )

    def test_closing_current_document_clears_only_matching_sessions(self):
        first = self.FakeDocument("first.SLDPRT", "C:\\first.SLDPRT")
        app = self.FakeApp([first], active=first)
        registry = DocumentRegistry(app)
        entry = registry.register(first)
        registry.set_current(entry, session_id="agent-a")
        registry.forget(entry.document_id)

        with self.assertRaises(NoCurrentDocument):
            registry.resolve(None, session_id="agent-a")

    @mock.patch("swcli.daemon.operations.close_active_windows_document")
    def test_close_uses_pre_close_descriptor_and_forgets_handle(self, close_document):
        document = self.FakeDocument("part.SLDPRT", "C:\\part.SLDPRT")
        app = self.FakeApp([document], active=document)
        registry = DocumentRegistry(app)
        entry = registry.register(document)
        registry.set_current(entry, session_id="default")

        def close(**kwargs):
            app.documents.clear()
            app.ActiveDoc = None
            return {
                "ok": True,
                "action": "document.close",
                "document": {
                    "title": document.title,
                    "path": document.path,
                    "type": document.document_type,
                    "modified": False,
                },
                "closed": True,
            }

        close_document.side_effect = close
        result = operations.execute_operation(
            app,
            "document.close",
            {"discard": False},
            documents=registry,
            document_id=entry.document_id,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["document"]["document_id"], entry.document_id)
        with self.assertRaises(NoCurrentDocument):
            registry.resolve(None, session_id="default")

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
        self.assertNotIn("--attach-existing", command)

    @mock.patch("swcli.daemon.main.subprocess.Popen")
    @mock.patch("swcli.daemon.main.call_daemon")
    def test_background_start_forwards_explicit_attach(self, call_daemon, popen):
        call_daemon.side_effect = [
            ConnectionRefusedError("offline"),
            {"success": True, "result": {"worker_alive": True}},
        ]
        process = popen.return_value
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"LOCALAPPDATA": directory}
        ), mock.patch("swcli.daemon.main.sys.platform", "win32"):
            result = start_daemon(
                endpoint="127.0.0.1:19000",
                startup_timeout_seconds=5.0,
                attach_existing=True,
            )

        self.assertTrue(result["success"])
        self.assertIn("--attach-existing", popen.call_args.args[0])

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
    def test_resident_app_requires_explicit_attach_for_user_instance(self, configure):
        app = object()
        com_client = mock.Mock()
        com_client.GetActiveObject.return_value = app

        with self.assertRaises(server.ExistingHostRequiresAttach):
            server.acquire_resident_app(com_client, visible=False)

        com_client.DispatchEx.assert_not_called()
        configure.assert_not_called()

    @mock.patch("swcli.daemon.server.configure_resident_app")
    def test_resident_app_preserves_explicitly_attached_user_instance(self, configure):
        app = object()
        com_client = mock.Mock()
        com_client.GetActiveObject.return_value = app

        actual, owned_by_daemon = server.acquire_resident_app(
            com_client, visible=False, attach_existing=True
        )

        self.assertIs(actual, app)
        self.assertFalse(owned_by_daemon)
        com_client.DispatchEx.assert_not_called()
        configure.assert_not_called()

    def test_structured_startup_failure_can_be_recovered_from_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = os.path.join(directory, "daemon.log")
            with open(log_path, "w", encoding="utf-8") as log:
                log.write("older diagnostic\n")
                current_launch_offset = log.tell()
                log.write(
                    json.dumps(
                        {
                            "ok": False,
                            "action": "daemon.serve",
                            "error": {
                                "code": "ExistingHostRequiresAttach",
                                "message": "explicit attach required",
                            },
                        }
                    )
                    + "\n"
                )

            self.assertEqual(
                _read_startup_failure(
                    Path(log_path), start_offset=current_launch_offset
                ),
                {
                    "code": "ExistingHostRequiresAttach",
                    "message": "explicit attach required",
                },
            )

            self.assertIsNone(
                _read_startup_failure(
                    Path(log_path), start_offset=os.path.getsize(log_path)
                )
            )

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

    def test_client_sends_document_and_session_context(self):
        response = {
            "api_version": PROTOCOL_VERSION,
            "request_id": "request-2",
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
                pass

            def sendall(self, value):
                self.sent += value

            def makefile(self, mode):
                return io.BytesIO(json.dumps(response).encode("utf-8") + b"\n")

        connection = Connection()
        with mock.patch.object(
            client.socket, "create_connection", return_value=connection
        ):
            client.call_daemon(
                "document.inspect",
                request_id="request-2",
                session_id="agent-a",
                document_id="d-k7m2q9",
            )

        request = json.loads(connection.sent.decode("utf-8"))
        self.assertEqual(request["session_id"], "agent-a")
        self.assertEqual(request["document_id"], "d-k7m2q9")

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
            document=None,
        )

    @mock.patch("swcli.daemon.operations.save_active_windows_document")
    def test_document_save_reuses_worker_owned_app(self, save_document):
        app = object()
        save_document.return_value = {"ok": True}

        result = operations.execute_operation(app, "document.save", {})

        self.assertEqual(result, {"ok": True})
        save_document.assert_called_once_with(app=app, document=None)


if __name__ == "__main__":
    unittest.main()
