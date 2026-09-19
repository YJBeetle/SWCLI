import contextlib
import io
import json
import unittest
from unittest import mock

from swcli.cli import main


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
        schema = json.loads(output.getvalue())
        self.assertEqual(schema["title"], "SWCLI Request")

    def test_host_probe_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["host", "probe", "--json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("supported", payload)
        self.assertIn("host", payload)

    @mock.patch("swcli.cli.start_windows_host")
    def test_host_start_json(self, start_windows_host):
        start_windows_host.return_value = {
            "ok": True,
            "action": "start",
            "started": True,
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["host", "start", "--json"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["started"])
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
        self.assertEqual(json.loads(output.getvalue())["error"]["type"], "OpenDocument")

    @mock.patch("swcli.cli.open_windows_document")
    def test_document_open_json(self, open_windows_document):
        open_windows_document.return_value = {
            "ok": True,
            "action": "document.open",
            "document": {"title": "sample.SLDPRT"},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(
                ["document", "open", "sample.SLDPRT", "--read-only", "--json"]
            )

        self.assertEqual(exit_code, 0)
        open_windows_document.assert_called_once_with(
            "sample.SLDPRT", read_only=True, configuration=""
        )

    @mock.patch("swcli.cli.inspect_active_windows_document")
    def test_document_inspect_failure(self, inspect_active_windows_document):
        inspect_active_windows_document.return_value = {
            "ok": False,
            "action": "document.inspect",
            "error": {"type": "NoActiveDocument", "message": "none"},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["document", "inspect", "--json"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            json.loads(output.getvalue())["error"]["type"], "NoActiveDocument"
        )


if __name__ == "__main__":
    unittest.main()
