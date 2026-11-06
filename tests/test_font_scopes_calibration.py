"""Portable watchdog/wiring checks; does not create a COM host."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_font_scope_watchdog", ROOT / "scripts/ci/run-font-scopes-calibration.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FontScopeCalibrationTests(unittest.TestCase):
    def test_watchdog_has_fixed_hard_native_and_group_budgets(self):
        self.assertEqual(runner.NATIVE_TIMEOUT_SECONDS, 600)
        self.assertEqual(runner.GROUP_TIMEOUT_SECONDS, 1800)
        self.assertEqual(runner.timeout_reason(599, 599), None)
        self.assertEqual(runner.timeout_reason(600, 600), "native-call-timeout")
        self.assertEqual(runner.timeout_reason(1800, 10), "group-timeout")

    def test_native_timeout_kills_only_the_exact_child_once_and_preserves_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "native").mkdir()
            trace = output / "native/trace.jsonl"
            original = b'{"call":"native-property","phase":"begin"}\n'
            trace.write_bytes(original)
            now = [0.0]
            process = SimpleNamespace(pid=321, poll=lambda: None, kill=Mock(), wait=Mock())
            def sleep(seconds):
                now[0] += 300
            result = runner.monitor(process, output, clock=lambda: now[0], sleep=sleep)
            self.assertEqual(result["reason"], "native-call-timeout")
            self.assertEqual(result["terminated_pid"], 321)
            self.assertFalse(result["success"])
            process.kill.assert_called_once_with()
            process.wait.assert_called_once_with(timeout=10)
            self.assertEqual(trace.read_bytes(), original)

    def test_progress_does_not_reset_group_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "native").mkdir()
            trace = output / "native/trace.jsonl"
            now = [0.0]
            process = SimpleNamespace(pid=456, poll=lambda: None, kill=Mock(), wait=Mock())
            def sleep(seconds):
                now[0] += 300
                with trace.open("a") as stream:
                    stream.write(json.dumps(dict(phase="end", time=now[0])) + "\n")
            result = runner.monitor(process, output, clock=lambda: now[0], sleep=sleep)
            self.assertEqual(result["reason"], "group-timeout")
            process.kill.assert_called_once_with()
            self.assertEqual(len(trace.read_text().splitlines()), 6)

    def test_worker_report_is_required_and_original_first_failure_is_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "native").mkdir()
            report = output / "native/report.json"
            raw = json.dumps(dict(success=False, failure={"type": "NativeFirstFailure", "message": "first"}, cleanup_errors=[]))
            report.write_text(raw)
            process = SimpleNamespace(pid=789, returncode=1, poll=lambda: 1, kill=Mock())
            result = runner.monitor(process, output)
            self.assertFalse(result["success"])
            self.assertEqual(result["first_failure"]["type"], "NativeFirstFailure")
            self.assertEqual(report.read_text(), raw)
            process.kill.assert_not_called()
            process.returncode = 0
            process.poll = lambda: 0
            self.assertFalse(runner.monitor(process, output)["success"])
            report.write_text('{"success":true}')
            self.assertTrue(runner.monitor(process, output)["success"])

    def test_opt_in_workflow_never_exposes_private_runtime_to_pr_or_push(self):
        text = (ROOT / ".github/workflows/font-scopes-calibration.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("default: false", text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertIn("github.ref == 'refs/heads/codex/docprops-font-scopes'", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("pull_request_target:", text)
        self.assertNotIn("secrets: inherit", text)
        self.assertNotIn("native_full", text)
        self.assertNotIn("smoke-solidworks.ps1", text)
        self.assertIn("if: always()", text)
        self.assertIn("retention-days: 30", text)
        self.assertIn("group: swcli-font-scopes-${{ github.ref }}", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("group: swcli-hosted-windows-solidworks", text)

    def test_existing_dispatch_routes_only_font_calibration_with_one_named_secret(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        job = text.split("  font-scopes-calibration:", 1)[1].split("  release:", 1)[0]
        self.assertIn("inputs.calibrate_font_scopes", job)
        self.assertIn("github.ref == 'refs/heads/codex/docprops-font-scopes'", job)
        self.assertIn("uses: ./.github/workflows/font-scopes-calibration.yml", job)
        self.assertIn("RCLONE_CONFIG_B64: ${{ secrets.RCLONE_CONFIG_B64 }}", job)
        self.assertNotIn("secrets: inherit", job)
        self.assertEqual(job.count("secrets.RCLONE_CONFIG_B64"), 1)
        for name in ("test", "package"):
            block = text.split("  " + name + ":", 1)[1].split("    steps:", 1)[0]
            self.assertIn("!(github.event_name == 'workflow_dispatch' && inputs.calibrate_font_scopes)", block)

    def test_wrapper_is_limited_to_disposable_github_runner_and_exact_branch(self):
        text = (ROOT / "scripts/ci/windows/calibrate-font-scopes.ps1").read_text()
        for fragment in ('GITHUB_ACTIONS -ne "true"', 'GITHUB_EVENT_NAME -ne "workflow_dispatch"',
                         'GITHUB_REF -ne "refs/heads/codex/docprops-font-scopes"'):
            self.assertIn(fragment, text)
        self.assertEqual(text.count("run-font-scopes-calibration.py"), 1)
        self.assertNotIn("taskkill", text.lower())
        self.assertNotIn("retry", text.lower())

    def test_calibration_has_no_general_write_enable_switch(self):
        text = (ROOT / "src/swcli/hosts/windows_document_font_scopes.py").read_text()
        public = text.split("def set_document_font_scope_windows(", 1)[1].split("def _calibrate_set_document_font_scope(", 1)[0]
        self.assertIn("raise DocumentFontScopeNotCalibrated", public)
        self.assertNotIn("os.environ", public)
        self.assertNotIn("SetUserPreferenceTextFormat", public)
        self.assertNotIn("_calibrate_set_document_font_scope(", public)


if __name__ == "__main__":
    unittest.main()
