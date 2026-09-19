import contextlib
import io
import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
