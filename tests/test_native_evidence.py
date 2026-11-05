"""Exercise native evidence reuse without querying Actions or invoking CAD."""

import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/native-evidence.py"
spec = importlib.util.spec_from_file_location("native_evidence", SCRIPT)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

REPO = "YJBeetle/SWCLI"
COMMIT = "1" * 40


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        host = {"platform": "windows", "visible": True, "owned_by_daemon": True}
        boundary = {"verified": True, "native_process_ids": []}
        self.full = {
            "completed": True, "success": True, "suite": "full", "coverage_scope": "full-plan",
            "diagnostic_set": None, "cleanup_errors": [], "expected_sets": ["model"],
            "sets": [{"name": "model", "success": True, "cleanup_errors": [], "server_exit_code": 0,
                      "host": host, "steps": [{"success": True}],
                      "before_start": boundary, "after_stop": boundary}],
        }
        self.visible = {
            "state": "completed", "success": True, "cleanup_errors": [], "host": host,
            "host_after": dict(host),
        }
        self.run = {
            "id": 123, "head_sha": COMMIT, "path": ".github/workflows/ci.yml@codex/example",
            "event": "workflow_dispatch", "status": "completed", "conclusion": "success",
            "head_repository": {"full_name": REPO}, "run_attempt": 2,
        }
        self.manifest = native.identity(REPO, COMMIT, 123, 2)

    def bundle(self, reports=None):
        reports = reports or dict(zip(native.REPORTS, (self.full, self.visible)))
        payloads = {key: json.dumps(value).encode() for key, value in reports.items()}
        stamp = {**self.manifest, "report_digests": {key: native.sha(value) for key, value in payloads.items()}}
        stream = io.BytesIO()
        with ZipFile(stream, "w") as archive:
            for key, value in payloads.items():
                archive.writestr(native.ROOT + key, value)
            archive.writestr(native.ROOT + native.STAMP, json.dumps(stamp))
        payload = stream.getvalue()
        artifact = {"id": 99, "name": "swcli-windows-hosted-123-2", "expired": False,
                    "size_in_bytes": len(payload), "digest": native.sha(payload)}
        return payload, artifact

    def lookup(self, payload, artifact):
        api_values = [json.dumps({"workflow_runs": [self.run]}).encode(),
                      json.dumps({"artifacts": [artifact, {"name": "swcli-dist", "expired": False}]}).encode(),
                      payload]
        with patch.object(native, "api", side_effect=api_values) as api:
            return native.find(REPO, COMMIT), api.call_count

    def test_reuses_exact_commit_with_complete_original_reports(self):
        result, calls = self.lookup(*self.bundle())
        self.assertEqual((result, calls), ((123, 99), 3))

    def test_different_commit_repository_or_failed_run_never_downloads(self):
        for change in ({"head_sha": "2" * 40}, {"conclusion": "failure"},
                       {"head_repository": {"full_name": "fork/SWCLI"}}):
            with self.subTest(change=change), patch.dict(self.run, change):
                self.assertEqual(self.lookup(*self.bundle()), (None, 1))

    def test_corrupt_expired_or_wrong_attempt_evidence_falls_back(self):
        payload, artifact = self.bundle()
        for change in ({"digest": "sha256:" + "0" * 64}, {"expired": True},
                       {"name": "swcli-windows-hosted-123-1"}):
            with self.subTest(change=change):
                self.assertIsNone(self.lookup(payload, {**artifact, **change})[0])

    def test_nonfull_or_unverified_native_results_are_not_reusable(self):
        for change in ({"coverage_scope": "diagnostic"}, {"cleanup_errors": ["failed to close"]},
                       {"sets": [{**self.full["sets"][0], "server_exit_code": 1}]}):
            with self.subTest(change=change), patch.dict(self.full, change):
                self.assertIsNone(self.lookup(*self.bundle())[0])
