import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest import mock

script = Path(__file__).resolve().parents[1] / "scripts/ci/verify-invalid-requests.py"
spec = importlib.util.spec_from_file_location("wire_smoke", script)
wire_smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire_smoke)


class InvalidWireSmokeTests(unittest.TestCase):
    def run_smoke(self, *, response=None, after_pid=123, after_documents=None):
        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def settimeout(self, value):
                pass

            def sendall(self, value):
                pass

            def makefile(self, mode):
                payload = response or {
                    "request_id": "invalid-wire-smoke",
                    "success": False,
                    "error": {"code": "ValueError"},
                }
                return io.BytesIO(json.dumps(payload).encode("utf-8") + b"\n")

        def result(value):
            return {"success": True, "result": value}

        health = {"host_connected": True, "host": {"process_id": 123}}
        documents = {"documents": []}
        with (
            mock.patch.object(
                wire_smoke,
                "call_daemon",
                side_effect=[
                    result(health),
                    result(documents),
                    result({**health, "host": {"process_id": after_pid}}),
                    result(documents if after_documents is None else after_documents),
                ],
            ),
            mock.patch.object(
                wire_smoke.socket, "create_connection", return_value=Connection()
            ) as connect,
            mock.patch("sys.stdout", new_callable=io.StringIO),
        ):
            wire_smoke.main()
            self.assertEqual(connect.call_count, 5)

    def test_valid_errors_and_unchanged_host_pass(self):
        self.run_smoke()

    def test_accidental_success_fails(self):
        with self.assertRaisesRegex(RuntimeError, "reached execution"):
            self.run_smoke(response={"success": True})

    def test_replaced_host_fails(self):
        with self.assertRaisesRegex(RuntimeError, "changed the running host"):
            self.run_smoke(after_pid=124)

    def test_new_document_fails(self):
        with self.assertRaisesRegex(RuntimeError, "document state"):
            self.run_smoke(after_documents={"documents": [{"document_id": "d-ab12cd"}]})
