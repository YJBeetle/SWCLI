"""Native routing policy: exhaustive flags, wrong branches, full and tag defaults."""
import importlib.util
from itertools import product
from pathlib import Path
import unittest
import json
import os
import subprocess
import sys

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("_line_font_route", ROOT / "scripts/ci/validate-line-font-route.py")
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


class LineFontRouteTests(unittest.TestCase):
    def test_all_manual_flags_across_allowed_and_wrong_branches(self):
        for flags in product((False, True), repeat=3):
            for ref in (route.BRANCH, "refs/heads/main", "refs/heads/codex/other", "refs/tags/v0.1.0"):
                full, internal, public = flags
                with self.subTest(flags=flags, ref=ref):
                    valid = sum(flags) <= 1 and (not (internal or public) or ref == route.BRANCH)
                    if not valid:
                        with self.assertRaises(ValueError):
                            route.validate_route(event="workflow_dispatch", ref=ref, native_full=full, internal=internal, public=public)
                    else:
                        expected = ("full" if full else "line-font-internal" if internal else
                                    "line-font-public" if public else "portable")
                        self.assertEqual(route.validate_route(event="workflow_dispatch", ref=ref,
                            native_full=full, internal=internal, public=public), expected)

    def test_tag_and_default_push_do_not_accept_manual_inputs(self):
        for event, ref in (("push", "refs/tags/v0.1.0"), ("push", "refs/heads/main"),
                           ("pull_request", route.BRANCH)):
            for full, internal, public in product((False, True), repeat=3):
                with self.subTest(event=event, ref=ref, full=full, internal=internal, public=public):
                    if full or internal or public:
                        with self.assertRaises(ValueError):
                            route.validate_route(event=event, ref=ref, native_full=full, internal=internal, public=public)
                    else:
                        expected = "tag-policy-controls-full" if ref.startswith("refs/tags/v") else "portable"
                        self.assertEqual(route.validate_route(event=event, ref=ref), expected)

    def test_cli_decodes_false_flags_and_rejects_invalid_combinations(self):
        script = ROOT / "scripts/ci/validate-line-font-route.py"
        base = {**os.environ, "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": route.BRANCH,
                "SWCLI_ROUTE_FULL": "false", "SWCLI_ROUTE_LINE_FONT_INTERNAL": "false", "SWCLI_ROUTE_LINE_FONT_PUBLIC": "true"}
        accepted = subprocess.run([sys.executable, str(script)], env=base, capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["validated_native_route"], "line-font-public")
        for invalid in ({"SWCLI_ROUTE_FULL": "true"}, {"GITHUB_REF": "refs/heads/main"}):
            rejected = subprocess.run([sys.executable, str(script)], env={**base, **invalid}, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertNotIn("validated_native_route", rejected.stdout)

    def test_workflow_checks_route_before_install_and_blocks_native_on_test_failure(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        portable = text.split("  test:", 1)[1].split("  package:", 1)[0]
        self.assertLess(portable.index("validate-line-font-route.py"), portable.index("- name: Install SWCLI"))
        for name in ("inputs.native_full", "inputs.line_font_calibration", "inputs.line_font_public"):
            self.assertIn(name + " || false", portable)
        guard = text.split("  solidworks-e2e:", 1)[1].split("runs-on:", 1)[0]
        self.assertIn("needs.test.result == 'success'", guard)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.native_full", guard)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", guard)
        self.assertIn("needs.tag-policy.result == 'success'", guard)
        full_step = text.split("- name: Run real SOLIDWORKS modeling and export smoke test", 1)[1].split("- name:", 1)[0]
        self.assertIn("!inputs.line_font_calibration && !inputs.line_font_public", full_step)
