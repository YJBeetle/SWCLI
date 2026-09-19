import contextlib
import io
import unittest
from unittest import mock

from swcli.utils import export


class ExportCliTests(unittest.TestCase):
    @mock.patch("swcli.daemon.client.call_daemon")
    def test_utility_entry_point_uses_resident_daemon(self, call_daemon):
        call_daemon.return_value = {
            "success": True,
            "result": {
                "ok": True,
                "action": "batch.export",
                "artifacts": [],
                "ok_count": 1,
                "failed_count": 0,
            },
        }

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = export.main(
                [
                    "--list",
                    "files.txt",
                    "--workspace",
                    "workspace",
                    "--endpoint",
                    "127.0.0.1:19000",
                ]
            )

        self.assertEqual(exit_code, 0)
        call_daemon.assert_called_once_with(
            "batch.export",
            {
                "manifest": "files.txt",
                "workspace": "workspace",
                "outdir": None,
                "overwrite": False,
            },
            endpoint="127.0.0.1:19000",
            timeout_seconds=600.0,
        )
        self.assertIn("success: 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
