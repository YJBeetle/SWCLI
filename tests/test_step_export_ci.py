"""Targeted STEP wiring must never broaden private workflow authorization."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StepWorkflowTests(unittest.TestCase):
    def test_private_job_event_branch_and_opt_in_truth_table(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        block = text.split("  solidworks-e2e:\n", 1)[1].split("    runs-on:", 1)[0]
        expression = re.search(r"if: \$\{\{ (.*?) \}\}", block)[1]
        for event in ("push", "pull_request", "workflow_dispatch"):
            for ref in ("refs/heads/main", "refs/heads/codex/other", "refs/heads/codex/swcli-step-export-options", "refs/tags/v0.0.0"):
                for full in (False, True):
                    for targeted in (False, True):
                        values = {"github.repository": "YJBeetle/SWCLI", "github.event_name": event,
                                  "github.ref": ref, "needs.test.result": "success", "needs.package.result": "success",
                                  "needs.tag-policy.result": "success", "inputs.native_full": full,
                                  "inputs.native_step_targeted": targeted}
                        rendered = expression.replace("always()", "True")
                        rendered = rendered.replace("startsWith(github.ref, 'refs/tags/v')", repr(ref.startswith("refs/tags/v")))
                        for name in sorted(values, key=len, reverse=True):
                            rendered = rendered.replace(name, repr(values[name]))
                        actual = eval(rendered.replace("&&", " and ").replace("||", " or ").replace("!", " not "), {"__builtins__": {}})
                        expected = ((event == "push" and ref.startswith("refs/tags/v")) or
                                    (event == "workflow_dispatch" and ((full and not targeted) or
                                     (targeted and ref == "refs/heads/codex/swcli-step-export-options"))))
                        self.assertEqual(actual, expected, (event, ref, full, targeted))
        input_block = text.split("      native_step_targeted:", 1)[1].split("\npermissions:", 1)[0]
        self.assertIn("default: false", input_block)
        target = text.split("      - name: Calibrate STEP protocol", 1)[1].split("      - name:", 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'", target)
        self.assertIn("github.ref == 'refs/heads/codex/swcli-step-export-options'", target)
        self.assertIn("timeout-minutes: 31", target)
        self.assertNotIn("pull_request_target", text)
        self.assertIn("windows-step-internal-calibration", text)
        concurrency = text.split("  solidworks-e2e:", 1)[1].split("    env:", 1)[0]
        self.assertIn("format('swcli-step-export-{0}', github.ref)", concurrency)
        self.assertIn("|| 'swcli-hosted-windows-solidworks'", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)

    def test_watchdogs_and_evidence_do_not_enable_public_revision_allowlist(self):
        script = (ROOT / "scripts/ci/verify-step-export-calibration.py").read_text()
        self.assertIn("time.monotonic() - started >= 1800", script)
        self.assertIn('time.time() - active["time"] >= 600', script)
        self.assertIn('"timeout.json"', script)
        self.assertIn('"public-fail-closed"', script)
        self.assertIn('"reopen-imported-native"', script)
        from swcli.hosts.windows_step_export import VALIDATED_REVISIONS
        self.assertEqual(VALIDATED_REVISIONS, frozenset())
