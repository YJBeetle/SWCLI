import contextlib
import io
import json
import unittest
from unittest import mock

from swcli.cli import _typed_operation, build_parser, main


class CliTests(unittest.TestCase):
    def test_version_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["version", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["name"], "SWCLI")
        self.assertEqual(payload["protocol_version"], "swcli/v1")

    def test_protocol_show(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["protocol", "show", "request"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["title"], "SWCLI Request")

    def test_daemon_lifecycle_commands_share_the_main_parser(self):
        parser = build_parser()
        for command in ("serve", "start", "status", "stop"):
            with self.subTest(command=command):
                args = parser.parse_args(["daemon", command])
                self.assertEqual(args.command, "daemon")
                self.assertEqual(args.daemon_command, command)

    def test_daemon_attach_existing_is_explicit(self):
        parser = build_parser()

        default = parser.parse_args(["daemon", "start"])
        attached_start = parser.parse_args(
            ["daemon", "start", "--attach-existing"]
        )
        attached_serve = parser.parse_args(
            ["daemon", "serve", "--attach-existing"]
        )

        self.assertFalse(default.attach_existing)
        self.assertTrue(attached_start.attach_existing)
        self.assertTrue(attached_serve.attach_existing)

    @mock.patch("swcli.cli.call_daemon")
    @mock.patch("swcli.cli.doctor_windows_host")
    def test_doctor_combines_host_and_daemon_diagnostics(
        self, doctor_windows_host, call_daemon
    ):
        doctor_windows_host.return_value = {
            "supported": True,
            "host": {"platform": "win32", "machine": "AMD64"},
            "registration": {},
            "com": {},
        }
        call_daemon.return_value = {
            "success": True,
            "result": {"worker_alive": True},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["doctor", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["daemon"]["reachable"])
        self.assertTrue(payload["daemon"]["health"]["worker_alive"])
        call_daemon.assert_called_once_with(
            "daemon.health",
            endpoint="127.0.0.1:18495",
            timeout_seconds=10.0,
            connect_timeout_seconds=3.0,
        )

    @mock.patch("swcli.cli.call_daemon", side_effect=ConnectionRefusedError("offline"))
    @mock.patch("swcli.cli.doctor_windows_host")
    def test_doctor_reports_unreachable_daemon_without_failing(
        self, doctor_windows_host, call_daemon
    ):
        doctor_windows_host.return_value = {
            "supported": False,
            "host": {"platform": "linux", "machine": "x86_64"},
            "registration": None,
            "com": None,
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["doctor", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertFalse(payload["daemon"]["reachable"])
        self.assertEqual(payload["daemon"]["error"]["type"], "ConnectionRefusedError")

    def test_all_typed_commands_map_to_daemon_operations(self):
        cases = (
            (
                ["document", "open", "part.SLDPRT", "--read-only", "--json"],
                "document.open",
                {"path": "part.SLDPRT", "read_only": True, "configuration": ""},
                None,
            ),
            (
                ["document", "list", "--json"],
                "document.list",
                {},
                None,
            ),
            (
                ["document", "use", "d-k7m2q9", "--json"],
                "document.use",
                {},
                "d-k7m2q9",
            ),
            (
                ["document", "inspect", "--detail", "structure", "--json"],
                "document.inspect",
                {"detail": "structure", "max_features": 500},
                None,
            ),
            (
                ["document", "close", "--discard", "--json"],
                "document.close",
                {"discard": True},
                None,
            ),
            (
                ["document", "save", "--json"],
                "document.save",
                {},
                None,
            ),
            (
                ["document", "diagnose", "--max-features", "25", "--json"],
                "document.diagnose",
                {"max_features": 25},
                None,
            ),
            (
                ["document", "rebuild", "--force", "--top-only", "--json"],
                "document.rebuild",
                {"force": True, "top_only": True, "max_features": 500},
                None,
            ),
            (
                [
                    "document", "render", "view.bmp", "--width", "800",
                    "--height", "600", "--view", "isometric", "--no-fit",
                    "--overwrite", "--json",
                ],
                "document.render",
                {
                    "output": "view.bmp", "width": 800, "height": 600,
                    "view": "isometric", "fit": False, "overwrite": True,
                },
                None,
            ),
            (
                [
                    "document", "export", "part.STEP", "--overwrite",
                    "--strict", "--json",
                ],
                "document.export",
                {
                    "output": "part.STEP",
                    "overwrite": True,
                    "strict": True,
                },
                None,
            ),
            (
                [
                    "part", "create-box", "box.SLDPRT", "--width-mm", "100",
                    "--height-mm", "50", "--depth-mm", "20",
                    "--template", "Part.prtdot", "--json",
                ],
                "part.create-box",
                {
                    "output": "box.SLDPRT", "width_mm": 100.0,
                    "height_mm": 50.0, "depth_mm": 20.0,
                    "template": "Part.prtdot", "overwrite": False,
                },
                None,
            ),
        )
        parser = build_parser()
        for arguments, operation, parameters, document_id in cases:
            with self.subTest(operation=operation):
                self.assertEqual(
                    _typed_operation(parser.parse_args(arguments)),
                    (operation, parameters, True, document_id),
                )

    def test_document_selector_and_session_are_mapped_separately(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "--session",
                "agent-a",
                "document",
                "inspect",
                "--document",
                "active",
                "--json",
            ]
        )

        self.assertEqual(args.session, "agent-a")
        self.assertEqual(
            _typed_operation(args),
            (
                "document.inspect",
                {"detail": "summary", "max_features": 500},
                True,
                "active",
            ),
        )

    @mock.patch("swcli.cli.call_daemon")
    def test_typed_command_uses_default_daemon_endpoint(self, call_daemon):
        call_daemon.return_value = {
            "success": True,
            "result": {
                "ok": True,
                "action": "document.open",
                "document": {"title": "sample.SLDPRT"},
            },
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(
                ["document", "open", "sample.SLDPRT", "--read-only", "--json"]
            )
        self.assertEqual(exit_code, 0)
        call_daemon.assert_called_once_with(
            "document.open",
            {"path": "sample.SLDPRT", "read_only": True, "configuration": ""},
            endpoint="127.0.0.1:18495",
            timeout_seconds=600.0,
            connect_timeout_seconds=3.0,
            session_id=None,
            document_id=None,
        )

    @mock.patch("swcli.cli.call_daemon")
    def test_daemon_connection_failure_does_not_fall_back_to_com(self, call_daemon):
        call_daemon.side_effect = ConnectionRefusedError("daemon unavailable")
        output = io.StringIO()
        with mock.patch("swcli.cli.sys.platform", "linux"), contextlib.redirect_stdout(output):
            exit_code = main(["document", "inspect", "--json"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            json.loads(output.getvalue())["error"]["type"],
            "ConnectionRefusedError",
        )

    @mock.patch("swcli.cli.start_daemon")
    @mock.patch("swcli.cli.call_daemon")
    def test_native_windows_typed_command_autostarts_and_retries(
        self, call_daemon, start_daemon
    ):
        call_daemon.side_effect = [
            ConnectionRefusedError("daemon unavailable"),
            {
                "success": True,
                "result": {
                    "ok": True,
                    "action": "document.inspect",
                    "document": {"title": "sample.SLDPRT"},
                },
            },
        ]
        start_daemon.return_value = {
            "success": True,
            "result": {"started": True},
        }
        output = io.StringIO()
        with mock.patch("swcli.cli.sys.platform", "win32"), contextlib.redirect_stdout(
            output
        ):
            exit_code = main(["document", "inspect", "--json"])

        self.assertEqual(exit_code, 0)
        start_daemon.assert_called_once_with(endpoint="127.0.0.1:18495")
        self.assertEqual(call_daemon.call_count, 2)
        self.assertTrue(json.loads(output.getvalue())["ok"])

    @mock.patch("swcli.cli.start_daemon")
    @mock.patch("swcli.cli.call_daemon")
    def test_native_windows_typed_command_autostarts_after_connect_timeout(
        self, call_daemon, start_daemon
    ):
        call_daemon.side_effect = [
            TimeoutError("timed out"),
            {
                "success": True,
                "result": {
                    "ok": True,
                    "action": "document.inspect",
                    "document": {"title": "sample.SLDPRT"},
                },
            },
        ]
        start_daemon.return_value = {
            "success": True,
            "result": {"started": True},
        }
        output = io.StringIO()
        with mock.patch("swcli.cli.sys.platform", "win32"), contextlib.redirect_stdout(
            output
        ):
            exit_code = main(["document", "inspect", "--json"])

        self.assertEqual(exit_code, 0)
        start_daemon.assert_called_once_with(endpoint="127.0.0.1:18495")
        self.assertEqual(call_daemon.call_count, 2)
        self.assertTrue(json.loads(output.getvalue())["ok"])

    @mock.patch("swcli.cli.start_daemon")
    @mock.patch("swcli.cli.call_daemon", side_effect=ConnectionRefusedError("offline"))
    def test_native_windows_remote_endpoint_never_autostarts(
        self, call_daemon, start_daemon
    ):
        output = io.StringIO()
        with mock.patch("swcli.cli.sys.platform", "win32"), contextlib.redirect_stdout(
            output
        ):
            exit_code = main(
                [
                    "--endpoint",
                    "192.0.2.10:18495",
                    "document",
                    "inspect",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 1)
        start_daemon.assert_not_called()
        self.assertEqual(
            json.loads(output.getvalue())["error"]["type"],
            "ConnectionRefusedError",
        )


if __name__ == "__main__":
    unittest.main()
