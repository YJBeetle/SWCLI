"""Portable shared visible smoke guards, not real Windows/Wine proof."""
import importlib.util
import json
from pathlib import Path
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
