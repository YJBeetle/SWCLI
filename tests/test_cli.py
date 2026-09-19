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

    def test_host_probe_remains_an_explicit_local_diagnostic(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["host", "probe", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("supported", payload)
        self.assertIn("host", payload)

    @mock.patch("swcli.cli.start_windows_host")
    def test_host_start_remains_an_explicit_local_diagnostic(self, start_windows_host):
        start_windows_host.return_value = {
            "ok": True,
            "action": "start",
            "started": True,
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["host", "start", "--json"])
        self.assertEqual(exit_code, 0)
        start_windows_host.assert_called_once_with(visible=True, timeout_seconds=60.0)

    @mock.patch("swcli.cli.stop_windows_host")
    def test_host_stop_failure_returns_nonzero(self, stop_windows_host):
        stop_windows_host.return_value = {
            "ok": False,
            "action": "stop",
            "error": {"type": "OpenDocument", "message": "document is open"},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["host", "stop", "--json"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            json.loads(output.getvalue())["error"]["type"], "OpenDocument"
        )

    def test_all_typed_commands_map_to_daemon_operations(self):
        cases = (
            (
                ["document", "open", "part.SLDPRT", "--read-only", "--json"],
                "document.open",
                {"path": "part.SLDPRT", "read_only": True, "configuration": ""},
            ),
            (
                ["document", "inspect", "--detail", "structure", "--json"],
                "document.inspect",
                {"detail": "structure", "max_features": 500},
            ),
            (
                ["document", "close", "--discard", "--json"],
                "document.close",
                {"discard": True},
            ),
            (
                ["document", "diagnose", "--max-features", "25", "--json"],
                "document.diagnose",
                {"max_features": 25},
            ),
            (
                ["document", "rebuild", "--force", "--top-only", "--json"],
                "document.rebuild",
                {"force": True, "top_only": True, "max_features": 500},
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
            ),
            (
                [
                    "document", "export", "part.STEP", "--overwrite",
                    "--allow-source-modification", "--json",
                ],
                "document.export",
                {
                    "output": "part.STEP",
                    "overwrite": True,
                    "allow_source_modification": True,
                },
            ),
            (
                [
                    "part", "create-box", "box.SLDPRT", "--width-mm", "100",
                    "--height-mm", "50", "--depth-mm", "20", "--json",
                ],
                "part.create-box",
                {
                    "output": "box.SLDPRT", "width_mm": 100.0,
                    "height_mm": 50.0, "depth_mm": 20.0, "overwrite": False,
                },
            ),
        )
        parser = build_parser()
        for arguments, operation, parameters in cases:
            with self.subTest(operation=operation):
                self.assertEqual(
                    _typed_operation(parser.parse_args(arguments)),
                    (operation, parameters, True),
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
        )

    @mock.patch("swcli.cli.call_daemon")
    def test_daemon_connection_failure_does_not_fall_back_to_com(self, call_daemon):
        call_daemon.side_effect = ConnectionRefusedError("daemon unavailable")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["document", "inspect", "--json"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            json.loads(output.getvalue())["error"]["type"],
            "ConnectionRefusedError",
        )


if __name__ == "__main__":
    unittest.main()
