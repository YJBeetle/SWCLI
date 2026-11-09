"""STEP selectors must preserve private/full gates and execute a CAD mode."""
from itertools import product
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
STEP_REF = "refs/heads/codex/swcli-step-export-options"


def expression(block, key="if"):
    return re.search(key + r": \$\{\{ (.*?) \}\}", block)[1]


def evaluate(source, values):
    rendered = source.replace("always()", "True")
    rendered = rendered.replace("startsWith(github.ref, 'refs/tags/v')", repr(values["github.ref"].startswith("refs/tags/v")))
    for profile in ("internal", "public", "diagnostic"):
        rendered = rendered.replace("format('swcli-step-export-" + profile + "-{0}', github.ref)",
                                    repr("swcli-step-export-" + profile + "-" + values["github.ref"]))
    for name in sorted(values, key=len, reverse=True):
        rendered = rendered.replace(name, repr(values[name]))
    rendered = rendered.replace("&&", " and ").replace("||", " or ")
    rendered = re.sub(r"!(?!=)", " not ", rendered)
    return eval(rendered.strip(), {"__builtins__": {}})


class StepWorkflowTests(unittest.TestCase):
    def test_private_job_all_flag_ref_event_and_tag_policy_combinations_have_one_cad_mode(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        job = text.split("  solidworks-e2e:\n", 1)[1].split("\n  release:", 1)[0]
        header = job.split("    runs-on:", 1)[0]
        guard, name, group = expression(header), expression(header, "name"), expression(job, "group")
        def step(label):
            return expression(job.split("      - name: " + label + "\n", 1)[1].split("      - name:", 1)[0])
        full = step("Run real SOLIDWORKS modeling and export smoke test")
        internal = step("Calibrate STEP protocol and geometry with save/reopen evidence")
        public = step("Accept public STEP CLI daemon SDK and MCP contracts")
        observer = step("Read back actual public STEP geometry and native save reopen")
        diagnostic = step("Diagnose original STEP imports once without exporting")
        self.assertEqual(diagnostic, step("Verify fixed original STEP source ZIP and all eight outputs"))
        self.assertEqual(full, step("Prepare property fixtures for public CLI verification"))
        self.assertEqual(full, step("Prepare annotation fixtures for public CLI verification"))
        scope = re.search(r'--host windows --scope.*?\$\{\{ (.*?) \}\}', job)[1]
        combinations = 0
        for event, ref, full_flag, internal_flag, public_flag, diagnostic_flag, head_matches, tag_policy, owner, test_result, package_result in product(
            ("push", "pull_request", "workflow_dispatch"),
            ("refs/heads/main", "refs/heads/codex/other", STEP_REF, "refs/tags/v0.0.0", "refs/tags/diagnostic", "refs/pull/1/merge"),
            (False, True), (False, True), (False, True), (False, True), (False, True), ("success", "failure", "skipped"),
            ("YJBeetle/SWCLI", "untrusted/fork"), ("success", "failure"), ("success", "failure"),
        ):
            combinations += 1
            values = {"github.repository": owner, "github.event_name": event, "github.ref": ref,
                      "needs.test.result": test_result, "needs.package.result": package_result,
                      "needs.tag-policy.result": tag_policy, "inputs.native_full": full_flag,
                      "inputs.native_step_targeted": internal_flag, "inputs.native_step_public_targeted": public_flag,
                      "inputs.native_step_import_diagnostic": diagnostic_flag, "github.sha": "a"*40,
                      "inputs.native_step_import_head": ("a" if head_matches else "b")*40}
            mode = None
            if event == "push" and ref.startswith("refs/tags/v") and tag_policy == "success":
                mode = "full"
            elif event == "workflow_dispatch":
                if full_flag and not internal_flag and not public_flag and not diagnostic_flag:
                    mode = "full"
                elif not full_flag and not diagnostic_flag and internal_flag != public_flag and ref == STEP_REF:
                    mode = "internal" if internal_flag else "public"
                elif diagnostic_flag and not (full_flag or internal_flag or public_flag) and ref == STEP_REF and head_matches:
                    mode = "diagnostic"
            expected = (owner == "YJBeetle/SWCLI" and test_result == package_result == "success" and mode is not None)
            actual = bool(evaluate(guard, values))
            self.assertEqual(actual, expected, values)
            if actual:
                selected = [label for label, predicate in (("full", full), ("internal", internal), ("public", public), ("diagnostic", diagnostic))
                            if evaluate(predicate, values)]
                self.assertEqual(selected, [mode], values)  # No eligible empty-green or multiple-mode job.
                self.assertEqual(bool(evaluate(observer, values)), mode == "public", values)
                expected_name = {"full": "Complete SOLIDWORKS functional verification",
                                 "internal": "Internal STEP export calibration", "public": "Public STEP export acceptance",
                                 "diagnostic": "Original STEP import diagnostic"}[mode]
                self.assertEqual(evaluate(name, values), expected_name, values)
                expected_group = "swcli-hosted-windows-solidworks" if mode == "full" else "swcli-step-export-" + mode + "-" + ref
                self.assertEqual(evaluate(group, values), expected_group, values)
                expected_scope = {"full": "windows-installed-full", "internal": "windows-step-internal-calibration",
                                  "public": "windows-step-public-acceptance", "diagnostic": "windows-step-original-import-diagnostic"}[mode]
                self.assertEqual(evaluate(scope, values), expected_scope, values)
        self.assertEqual(combinations, 13824)
        for key in ("native_step_targeted", "native_step_public_targeted", "native_step_import_diagnostic"):
            self.assertIn("default: false", text.split("      " + key + ":", 1)[1].split("\npermissions:", 1)[0])
        self.assertIn("cancel-in-progress: false", job)
        self.assertNotIn("pull_request_target", text)
        self.assertIn("--export-report", job)

    def test_watchdogs_and_exact_audited_revision_scope(self):
        script = (ROOT / "scripts/ci/verify-step-export-calibration.py").read_text()
        self.assertIn("time.monotonic() - started >= 1800", script)
        self.assertIn('time.time() - active["time"] >= 600', script)
        self.assertIn('"timeout.json"', script)
        self.assertIn('"public-fail-closed"', script)
        self.assertIn('"reopen-imported-native"', script)
        from swcli.hosts.windows_step_export import VALIDATED_REVISIONS
        self.assertEqual(VALIDATED_REVISIONS, frozenset({"33.5.0"}))

    def test_original_diagnostic_authenticates_before_private_inputs_and_runs_one_reader(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        job = text.split("  solidworks-e2e:\n", 1)[1].split("\n  release:", 1)[0]
        authenticate = job.index("- name: Verify fixed original STEP source ZIP and all eight outputs")
        for label in ("Initialize private paths", "Prepare protected Google Drive configuration",
                      "Stream Google Drive through WinFsp", "Fetch private smoke-test runtime", "Install native SOLIDWORKS"):
            self.assertLess(authenticate, job.index("- name: " + label))
        diagnostic = job.split("      - name: Diagnose original STEP imports once without exporting\n", 1)[1].split("      - name:", 1)[0]
        self.assertLess(diagnostic.index("prepare-step-import-original.py verify"), diagnostic.index("verify-step-export-calibration.py"))
        self.assertEqual(diagnostic.count("verify-step-export-calibration.py"), 1)
        self.assertIn("--export-report", diagnostic)
        self.assertNotIn("verify-step-export-public.py", diagnostic)
        self.assertNotIn("continue-on-error", diagnostic)
        self.assertIn("actions: read", job)
        self.assertIn("DIAGNOSTIC_WORKFLOW_SHA: ${{ github.workflow_sha }}", job)
        self.assertIn("swcli-step-original-import-diagnostic-${{ github.run_id }}-${{ github.run_attempt }}", job)
