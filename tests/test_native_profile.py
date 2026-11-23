"""Merged feature profiles must not silently skip all validation."""
import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_profile", ROOT / "scripts/ci/validate-native-profile.py")
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


class NativeProfileTests(unittest.TestCase):
    def test_all_legal_scopes_and_pairwise_conflicts(self):
        refs = ["refs/heads/main", "refs/heads/other", "refs/tags/v0.2.4", *set(PROFILE.FEATURE_REFS.values())]
        selections = [(), *((name,) for name in PROFILE.FLAGS),
                      *itertools.combinations(PROFILE.FLAGS, 2), tuple(PROFILE.FLAGS)]
        for event, ref, selection in itertools.product(("push", "workflow_dispatch", "pull_request"), refs, selections):
            inputs = {name: name in selection for name in PROFILE.FLAGS}
            selected = [key for key, value in inputs.items() if value]
            valid = (not selected if event != "workflow_dispatch" else
                     len(selected) <= 1 and (not selected or selected[0] == "native_full"
                       or PROFILE.FEATURE_REFS[selected[0]] == ref))
            with self.subTest(event=event, ref=ref, inputs=inputs):
                if not valid:
                    with self.assertRaises(ValueError):
                        PROFILE.resolve(event, ref, inputs)
                else:
                    result = PROFILE.resolve(event, ref, inputs)
                    expected = (selected[0] if selected else "portable") if event == "workflow_dispatch" else (
                        "full" if event == "push" and ref.startswith("refs/tags/v") else "portable")
                    expected = {"native_full": "full", "calibrate_tolerances": "tolerances-calibration", "accept_tolerances": "tolerances-public"}.get(expected, expected)
                    self.assertEqual(result, expected)

    def test_drawing_lines_public_is_exclusive_and_keeps_legacy_routes(self):
        candidate = PROFILE.DETAILING_LINES_REF
        legacy = PROFILE.FEATURE_REFS["detailing_public_gate"]
        public = {"detailing_public_gate": True}
        self.assertEqual(PROFILE.resolve("workflow_dispatch", candidate, public), "detailing-lines-public")
        self.assertEqual(PROFILE.resolve("workflow_dispatch", legacy, public), "detailing_public_gate")
        self.assertEqual(PROFILE.resolve("workflow_dispatch", legacy, {"detailing_calibration": True}), "detailing_calibration")
        self.assertEqual(PROFILE.resolve("push", candidate, {}), "portable")
        invalid = [
            ("push", candidate, public),
            ("workflow_dispatch", "refs/heads/main", public),
            ("workflow_dispatch", "refs/heads/codex/other-detailing", public),
            ("workflow_dispatch", candidate, {"detailing_calibration": True}),
        ]
        invalid.extend(("workflow_dispatch", candidate, {**public, flag: True})
                       for flag in (*PROFILE.FLAGS, *PROFILE.UNITS_FLAGS) if flag not in public)
        for event, ref, inputs in invalid:
            with self.subTest(event=event, ref=ref, inputs=inputs), self.assertRaises(ValueError):
                PROFILE.resolve(event, ref, inputs)

    def test_drawing_lines_workflow_reuses_protected_job_with_exact_wheel(self):
        import yaml
        workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
        jobs = workflow["jobs"]
        self.assertNotIn("detailing_lines_public", workflow[True]["workflow_dispatch"]["inputs"])
        job = jobs["detailing-calibration"]
        self.assertIn("needs.native-profile.result == 'success'", job["if"])
        self.assertIn("github.event_name == 'workflow_dispatch'", job["if"])
        self.assertIn(PROFILE.DETAILING_LINES_REF, job["if"])
        self.assertIn("needs.native-profile.outputs.profile == 'detailing-lines-public'", job["if"])
        self.assertNotIn("detailing-lines-public", jobs["solidworks-e2e"]["if"])
        steps = job["steps"]
        public_steps = [step for step in steps if
                        "needs.native-profile.outputs.profile == 'detailing-lines-public'" in step.get("if", "")]
        self.assertEqual(len(public_steps), 3)
        install, gate, wheel_upload = public_steps
        self.assertIn("pip wheel --no-deps", install["run"])
        self.assertIn("pip install $wheel", install["run"])
        self.assertIn("verify-installed.py", install["run"])
        self.assertEqual(gate["timeout-minutes"], 31)
        self.assertIn("run-detailing-lines-calibration.py", gate["run"])
        self.assertIn("--source-head $env:GITHUB_SHA --wheel $env:SWCLI_DETAILING_LINES_WHEEL", gate["run"])
        self.assertIn("--public-gate --execute-owned-native", gate["run"])
        self.assertIn("always()", wheel_upload["if"])
        self.assertIn("swcli-detailing-lines-wheel", wheel_upload["with"]["path"])
        legacy_gate = next(step for step in steps if "run-detailing-calibration.py" in step.get("run", ""))
        self.assertIn("outputs.profile != 'detailing-lines-public'", legacy_gate["if"])
        upload = next(step for step in steps if step.get("name") == "Retain original detailing validation evidence")
        self.assertEqual(upload["if"], "always()")
        self.assertIn("swcli-native-smoke", upload["with"]["path"])

    def test_malformed_flags_fail_closed(self):
        for value in (None, 0, 1, [], {}, "True", "yes"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PROFILE.resolve("workflow_dispatch", "refs/heads/main", {"native_full": value})
        for value in (True, "true"):
            self.assertEqual(PROFILE.resolve("workflow_dispatch", "refs/heads/main", {"native_full": value}), "full")

    def test_cli_invalid_inputs_fail_and_valid_tag_keeps_full(self):
        for event, ref, inputs, success in (
            ("workflow_dispatch", "refs/heads/main", {"detailing_public_gate": True}, False),
            ("workflow_dispatch", PROFILE.FEATURE_REFS["native_revolve_public"],
             {"native_revolve_public": True, "native_full": True}, False),
            ("push", "refs/tags/v0.2.4", {}, True),
        ):
            env = dict(os.environ, GITHUB_EVENT_NAME=event, GITHUB_REF=ref, SWCLI_NATIVE_INPUTS=json.dumps(inputs))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/ci/validate-native-profile.py")],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, success, result.stderr)
            if success:
                self.assertIn("full", result.stdout)

    def test_jobs_wait_for_validation_before_private_access(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("workflow semantic checks require PyYAML")
        jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
        for name in ("test", "package", "solidworks-e2e", "detailing-calibration"):
            self.assertIn("native-profile", jobs[name]["needs"])
        self.assertIn("needs.native-profile.result == 'success'", jobs["solidworks-e2e"]["if"])
        preflight = jobs["native-profile"]
        self.assertNotIn("secrets", json.dumps(preflight))
        self.assertNotIn("if", preflight)
        self.assertEqual(preflight["steps"][-1]["run"], "python scripts/ci/validate-native-profile.py")


if __name__ == "__main__":
    unittest.main()
