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
        inspect_active_windows_document.assert_called_once_with(
            detail="summary", max_features=500
        )

    @mock.patch("swcli.cli.inspect_active_windows_document")
    def test_document_inspect_structure(self, inspect_active_windows_document):
        inspect_active_windows_document.return_value = {
            "ok": True,
            "action": "document.inspect",
            "structure": {"features": {"count": 1}},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(
                [
                    "document",
                    "inspect",
                    "--detail",
                    "structure",
                    "--max-features",
                    "25",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        inspect_active_windows_document.assert_called_once_with(
            detail="structure", max_features=25
        )

    @mock.patch("swcli.cli.close_active_windows_document")
    def test_document_close_discard(self, close_active_windows_document):
        close_active_windows_document.return_value = {
            "ok": True,
            "action": "document.close",
            "closed": True,
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["document", "close", "--discard", "--json"])

        self.assertEqual(exit_code, 0)
        close_active_windows_document.assert_called_once_with(discard=True)

    @mock.patch("swcli.cli.diagnose_active_windows_document")
    def test_document_diagnose(self, diagnose_active_windows_document):
        diagnose_active_windows_document.return_value = {
            "ok": True,
            "action": "document.diagnose",
            "diagnostics": {"healthy": True},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(
                ["document", "diagnose", "--max-features", "25", "--json"]
            )

        self.assertEqual(exit_code, 0)
        diagnose_active_windows_document.assert_called_once_with(max_features=25)

    @mock.patch("swcli.cli.rebuild_active_windows_document")
    def test_document_force_rebuild(self, rebuild_active_windows_document):
        rebuild_active_windows_document.return_value = {
            "ok": True,
            "action": "document.rebuild",
            "rebuilt": True,
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(
                ["document", "rebuild", "--force", "--top-only", "--json"]
            )

        self.assertEqual(exit_code, 0)
        rebuild_active_windows_document.assert_called_once_with(
            force=True, top_only=True, max_features=500
        )

    @mock.patch("swcli.cli.render_active_windows_document")
    def test_document_render(self, render_active_windows_document):
        render_active_windows_document.return_value = {
            "ok": True,
            "action": "document.render",
            "artifact": {"path": "view.bmp"},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(
                [
                    "document",
                    "render",
                    "view.bmp",
                    "--width",
                    "800",
                    "--height",
                    "600",
                    "--view",
                    "isometric",
                    "--no-fit",
                    "--overwrite",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        render_active_windows_document.assert_called_once_with(
            "view.bmp",
            width=800,
            height=600,
            view="isometric",
            fit=False,
            overwrite=True,
        )

    @mock.patch("swcli.cli.create_box_part_windows")
    def test_part_create_box(self, create_box_part_windows):
        create_box_part_windows.return_value = {
            "ok": True,
            "action": "part.create-box",
            "saved": True,
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(
                [
                    "part",
                    "create-box",
                    "box.SLDPRT",
                    "--width-mm",
                    "100",
                    "--height-mm",
                    "50",
                    "--depth-mm",
                    "20",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        create_box_part_windows.assert_called_once_with(
            "box.SLDPRT",
            width_mm=100.0,
            height_mm=50.0,
            depth_mm=20.0,
            overwrite=False,
        )


if __name__ == "__main__":
    unittest.main()
