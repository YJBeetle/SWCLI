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
    def test_all_event_ref_scope_combinations(self):
        refs = ["refs/heads/main", "refs/heads/other", "refs/tags/v0.2.4", *set(PROFILE.FEATURE_REFS.values())]
        for event, ref, bits in itertools.product(("push", "workflow_dispatch", "pull_request"), refs,
                                                  itertools.product((False, True), repeat=len(PROFILE.FLAGS))):
            inputs = dict(zip(PROFILE.FLAGS, bits))
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
