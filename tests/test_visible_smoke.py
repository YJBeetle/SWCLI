"""Portable shared visible smoke guards, not real Windows/Wine proof."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

path = Path(__file__).resolve().parents[1] / "scripts/ci/verify-visible.py"
spec = importlib.util.spec_from_file_location("visible_test", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class FakeSmoke:
    def __init__(self):
        self.record = {"cleanup_errors": []}
        self.calls = []
        self.host = {"process_id": 123, "visible": True, "owned_by_daemon": True, "shared_interactive": False}
        self.after = dict(self.host)
        self.opened = {"document": {"document_id": "d-one", "type": 1}, "read_only": True,
                       "api_errors": 0, "api_warnings": 0}
        self.inspected = {"document": {"document_id": "d-one", "type": 1}}
        self.health_reads = 0
        self.checkpoint_error = None

    def health(self):
        self.health_reads += 1
        return {"host": self.host if self.health_reads == 1 else self.after}

    def require_empty(self):
        self.calls.append("empty")

    def close(self, document):
        self.calls.append(("close", document))

    def command(self, *args, **kwargs):
        self.calls.append(args)
        if args[:2] == ("document", "open"):
            return self.opened
        if args[:2] == ("document", "inspect"):
            return self.inspected
        if args == ("daemon", "stop"):
            return {"result": {"stopping": True}}
        raise AssertionError(args)

    def cleanup(self):
        self.calls.append("cleanup")

    def checkpoint(self, stage):
        self.record_path.write_text(json.dumps(self.record))


class VisibleSmokeTests(unittest.TestCase):
    def test_request_timeout_reaches_cli_process_deadline_and_evidence(self):
        for options, expected in (([], 120), (["--request-timeout", "600"], 600)):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temp:
                completed = subprocess.CompletedProcess([], 0, stdout=b'{"ok":true}', stderr=b"")
                def observe(smoke, sample):
                    self.assertEqual(smoke.request_timeout_seconds, expected)
                    smoke.command("document", "list")
                with mock.patch.object(gate, "verify", side_effect=observe), \
                        mock.patch.object(gate.transport.subprocess, "run", return_value=completed) as run, \
                        contextlib.redirect_stdout(io.StringIO()):
                    gate.main(["--output-dir", temp, "--sample-part", r"C:\sample.SLDPRT", *options])
                command = run.call_args.args[0]
                self.assertEqual(float(command[command.index("--request-timeout") + 1]), expected)
                self.assertEqual(run.call_args.kwargs["timeout"], expected + 15)
                proof = json.loads((Path(temp) / "visible.json").read_text())
                self.assertTrue(proof["success"])
                self.assertEqual(proof["request_timeout_seconds"], expected)
                self.assertEqual(proof["cli_process_timeout_seconds"], expected + 15)
                self.assertEqual(proof["events"][0]["request_timeout_seconds"], expected)

    def test_invalid_request_deadline_is_rejected_before_creating_files_or_host(self):
        for value in ("0", "-1", "nan", "inf", "3601", "not-a-number"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "proof"
                with mock.patch.object(gate.transport, "ModelingSmoke") as smoke, \
                        contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        gate.main(["--output-dir", str(output), "--sample-part", r"C:\sample.SLDPRT",
                                   "--request-timeout", value])
                smoke.assert_not_called()
                self.assertFalse(output.exists())

    def test_timeout_still_fails_and_keeps_the_configured_budget_in_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            error = subprocess.TimeoutExpired(["fixture-cli"], 615)
            with mock.patch.object(gate, "verify", side_effect=error):
                with self.assertRaises(subprocess.TimeoutExpired) as caught:
                    gate.main(["--output-dir", temp, "--sample-part", r"C:\sample.SLDPRT",
                               "--request-timeout", "600"])
            self.assertIs(caught.exception, error)
            proof = json.loads((Path(temp) / "visible.json").read_text())
            self.assertFalse(proof["success"])
            self.assertEqual(proof["error"]["type"], "TimeoutExpired")
            self.assertEqual(proof["request_timeout_seconds"], 600)

    def test_only_opens_reads_closes_and_stops_the_same_visible_host(self):
        smoke = FakeSmoke()
        gate.verify(smoke, r"C:\samples\part.SLDPRT")
        self.assertEqual(smoke.calls, ["empty", ("document", "open", r"C:\samples\part.SLDPRT", "--read-only"),
                                      ("document", "inspect"), ("close", "d-one"), "empty", ("daemon", "stop")])
        self.assertEqual(smoke.record["profile"], "visible-open")
        self.assertEqual(smoke.record["host"], smoke.record["host_after"])

    def test_wrong_initial_visibility_or_ownership_never_opens_or_stops(self):
        for field, value in (("visible", False), ("owned_by_daemon", False), ("shared_interactive", True)):
            smoke = FakeSmoke()
            smoke.host[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                gate.verify(smoke, r"C:\samples\part.SLDPRT")
            self.assertEqual(smoke.calls, [])

    def test_open_errors_wrong_document_and_changed_host_do_not_pass(self):
        defects = [("read_only", False), ("api_errors", 2), ("api_warnings", 4)]
        for field, value in defects:
            smoke = FakeSmoke()
            smoke.opened[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                gate.verify(smoke, r"C:\samples\part.SLDPRT")
            self.assertNotIn(("daemon", "stop"), smoke.calls)
        for field, value in (("process_id", 999), ("visible", False), ("owned_by_daemon", False), ("shared_interactive", True)):
            smoke = FakeSmoke()
            smoke.after[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                gate.verify(smoke, r"C:\samples\part.SLDPRT")
            self.assertNotIn(("daemon", "stop"), smoke.calls)
        smoke = FakeSmoke()
        smoke.inspected["document"]["document_id"] = "d-other"
        with self.assertRaises(RuntimeError):
            gate.verify(smoke, r"C:\samples\part.SLDPRT")

    def test_failed_run_keeps_evidence_and_does_not_overwrite_previous_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            smoke = FakeSmoke()
            smoke.host["visible"] = False
            with mock.patch.object(gate.transport, "ModelingSmoke", return_value=smoke):
                with self.assertRaises(RuntimeError):
                    gate.main(["--output-dir", temp, "--sample-part", r"C:\sample.SLDPRT"])
                proof = Path(temp) / "visible.json"
                data = proof.read_bytes()
                self.assertFalse(json.loads(data)["success"])
                self.assertIn("cleanup", smoke.calls)
                with self.assertRaises(FileExistsError):
                    gate.main(["--output-dir", temp, "--sample-part", r"C:\sample.SLDPRT"])
                self.assertEqual(proof.read_bytes(), data)
