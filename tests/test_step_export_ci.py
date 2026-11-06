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
    for profile in ("internal", "public"):
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
        self.assertEqual(full, step("Prepare property fixtures for public CLI verification"))
        self.assertEqual(full, step("Prepare annotation fixtures for public CLI verification"))
        scope = re.search(r'--host windows --scope.*?\$\{\{ (.*?) \}\}', job)[1]
        combinations = 0
        for event, ref, full_flag, internal_flag, public_flag, tag_policy, owner, test_result, package_result in product(
            ("push", "pull_request", "workflow_dispatch"),
            ("refs/heads/main", "refs/heads/codex/other", STEP_REF, "refs/tags/v0.0.0", "refs/tags/diagnostic", "refs/pull/1/merge"),
            (False, True), (False, True), (False, True), ("success", "failure", "skipped"),
            ("YJBeetle/SWCLI", "untrusted/fork"), ("success", "failure"), ("success", "failure"),
        ):
            combinations += 1
            values = {"github.repository": owner, "github.event_name": event, "github.ref": ref,
                      "needs.test.result": test_result, "needs.package.result": package_result,
                      "needs.tag-policy.result": tag_policy, "inputs.native_full": full_flag,
                      "inputs.native_step_targeted": internal_flag, "inputs.native_step_public_targeted": public_flag}
            mode = None
            if event == "push" and ref.startswith("refs/tags/v") and tag_policy == "success":
                mode = "full"
            elif event == "workflow_dispatch":
                if full_flag and not internal_flag and not public_flag:
                    mode = "full"
                elif not full_flag and internal_flag != public_flag and ref == STEP_REF:
                    mode = "internal" if internal_flag else "public"
            expected = (owner == "YJBeetle/SWCLI" and test_result == package_result == "success" and mode is not None)
            actual = bool(evaluate(guard, values))
            self.assertEqual(actual, expected, values)
            if actual:
                selected = [label for label, predicate in (("full", full), ("internal", internal), ("public", public))
                            if evaluate(predicate, values)]
                self.assertEqual(selected, [mode], values)  # No eligible empty-green or multiple-mode job.
                self.assertEqual(bool(evaluate(observer, values)), mode == "public", values)
                expected_name = {"full": "Complete SOLIDWORKS functional verification",
                                 "internal": "Internal STEP export calibration", "public": "Public STEP export acceptance"}[mode]
                self.assertEqual(evaluate(name, values), expected_name, values)
                expected_group = "swcli-hosted-windows-solidworks" if mode == "full" else "swcli-step-export-" + mode + "-" + ref
                self.assertEqual(evaluate(group, values), expected_group, values)
                expected_scope = {"full": "windows-installed-full", "internal": "windows-step-internal-calibration",
                                  "public": "windows-step-public-acceptance"}[mode]
                self.assertEqual(evaluate(scope, values), expected_scope, values)
        self.assertEqual(combinations, 3456)
        for key in ("native_step_targeted", "native_step_public_targeted"):
            self.assertIn("default: false", text.split("      " + key + ":", 1)[1].split("\npermissions:", 1)[0])
        self.assertIn("cancel-in-progress: false", job)
        self.assertNotIn("pull_request_target", text)
        self.assertIn("--export-report", job)

    def test_watchdogs_and_evidence_do_not_enable_public_revision_allowlist(self):
        script = (ROOT / "scripts/ci/verify-step-export-calibration.py").read_text()
        self.assertIn("time.monotonic() - started >= 1800", script)
        self.assertIn('time.time() - active["time"] >= 600', script)
        self.assertIn('"timeout.json"', script)
        self.assertIn('"public-fail-closed"', script)
        self.assertIn('"reopen-imported-native"', script)
        from swcli.hosts.windows_step_export import VALIDATED_REVISIONS
        self.assertEqual(VALIDATED_REVISIONS, frozenset())
