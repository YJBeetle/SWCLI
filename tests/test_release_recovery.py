"""Only a completed, trusted tag run with original passing artifacts can recover."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("recovery", ROOT / "scripts/ci/recover-release.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.run = {"id": 123, "repository": {"full_name": recovery.REPOSITORY}, "event": "push",
                    "path": ".github/workflows/ci.yml", "status": "completed", "conclusion": "cancelled",
                    "head_branch": "v0.2.1", "head_sha": "a" * 40, "run_attempt": 1}
        self.jobs = [{"name": name, "conclusion": "success"} for name in recovery.JOBS]
        self.rows = [{"id": n, "name": name, "digest": "sha256:" + "b" * 64,
                      "expired": False, "size_in_bytes": 1234, "workflow_run": {"head_sha": "a" * 40}}
                     for n, name in ((1, "swcli-dist"), (2, "swcli-windows-hosted-123-1"))]
        self.api = Mock()
        self.api.api.side_effect = lambda path: ({"jobs": self.jobs} if "/jobs?" in path
            else {"artifacts": self.rows} if "/artifacts?" in path else self.run)

    def test_cancelled_publication_uses_passing_original_native_attempt(self):
        context = recovery.source_context(self.api, "123")
        self.assertEqual(context["run_attempt"], 1)
        self.assertEqual(context["artifacts"]["native"]["name"], "swcli-windows-hosted-123-1")
        self.assertEqual(context["commit"], "a" * 40)

    def test_in_progress_or_wrong_workflow_never_recovers(self):
        for field, value in (("status", "in_progress"), ("event", "workflow_dispatch"),
                             ("head_branch", "main"), ("path", ".github/workflows/untrusted.yml"),
                             ("head_sha", "not-a-sha")):
            with self.subTest(field=field):
                original = self.run[field]; self.run[field] = value
                with self.assertRaises(RuntimeError): recovery.source_context(self.api, "123")
                self.run[field] = original

    def test_missing_failed_or_repeated_native_gate_cannot_publish(self):
        for conclusion in ("failure", "cancelled", "skipped"):
            self.jobs[-1]["conclusion"] = conclusion
            with self.assertRaises(RuntimeError): recovery.source_context(self.api, "123")
        self.jobs[-1]["conclusion"] = "success"
        self.jobs.append(copy.deepcopy(self.jobs[-1]))
        with self.assertRaises(RuntimeError): recovery.source_context(self.api, "123")

    def test_foreign_expired_or_ambiguous_artifact_cannot_publish(self):
        for field, value in (("expired", True), ("digest", "missing"),
                             ("workflow_run", {"head_sha": "f" * 40})):
            row = self.rows[-1]; original = row[field]; row[field] = value
            with self.assertRaises(RuntimeError): recovery.source_context(self.api, "123")
            row[field] = original
        self.rows.append(copy.deepcopy(self.rows[-1]))
        with self.assertRaises(RuntimeError): recovery.source_context(self.api, "123")

    def test_recovery_rejects_untrusted_publisher_before_any_mutation(self):
        with self.assertRaisesRegex(RuntimeError, "trusted main"):
            recovery.publish_original({}, "unused", "unused", "unused", "unused", self.api, {})

    def test_publication_records_real_recovery_identity_separate_from_source(self):
        context = recovery.source_context(self.api, "123")
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": recovery.REPOSITORY,
               "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
               "GITHUB_RUN_ID": "999", "GITHUB_SHA": "c" * 40}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src/swcli").mkdir(parents=True); (root / "src/swcli/__init__.py").write_text('version="0.2.1"')
            (root / "docs/releases").mkdir(parents=True); (root / "docs/releases/v0.2.1.md").write_text("Original notes")
            package = root / "original.whl"; package.write_bytes(b"original bytes")
            publisher = Mock()
            publisher.source_version.return_value = "0.2.1"
            publisher.verify_packages.return_value = [package]
            publisher.verify_native.return_value = {"full.json": "hash"}
            publisher.sha256.return_value = "d" * 64
            publisher.publish.return_value = {"tag": "v0.2.1"}
            out = root / "assets"
            with patch.object(recovery, "load_publisher", return_value=publisher), patch.object(recovery.subprocess, "check_output", return_value="a" * 40), patch.object(recovery.subprocess, "run"):
                recovery.publish_original(context, root, root, root, out, self.api, env)
            proof = json.loads((out / "provenance.json").read_text())
            self.assertEqual(proof["run_id"], "123")
            self.assertEqual(proof["publication"]["run_id"], "999")
            self.assertTrue(proof["publication"]["recovery"])
            self.assertEqual((out / package.name).read_bytes(), b"original bytes")
            publisher.publish.assert_called_once_with(out, self.api)
