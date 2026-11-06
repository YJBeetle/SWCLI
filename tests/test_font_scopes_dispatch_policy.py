"""Illegal manual selectors must fail, never become a zero-validation green run."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_font_dispatch_policy', ROOT / 'scripts/ci/validate-ci-dispatch.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class FontDispatchPolicyTests(unittest.TestCase):
    def select(self, *, event='workflow_dispatch', repository='YJBeetle/SWCLI',
               ref='refs/heads/main', fonts=False, native_full=False, font_profile='internal'):
        return policy.select_profile(event=event, repository=repository, ref=ref,
                                     fonts=fonts, native_full=native_full, font_profile=font_profile)

    def test_standard_push_manual_full_and_font_routes_are_exclusive(self):
        self.assertEqual(self.select(event='push'), 'standard')
        self.assertEqual(self.select(event='push', ref='refs/tags/v0.2.4'), 'standard')
        self.assertEqual(self.select(), 'standard')
        self.assertEqual(self.select(native_full=True), 'standard')
        for profile in ('internal', 'public-notes'):
            self.assertEqual(self.select(ref=policy.FONT_REF, fonts=True, font_profile=profile), 'font-scopes')

    def test_wrong_ref_full_plus_font_and_unselected_public_profile_fail(self):
        cases = [dict(fonts=True), dict(fonts=True, native_full=True),
                 dict(ref=policy.FONT_REF, fonts=True, native_full=True),
                 dict(ref='refs/heads/other', fonts=True), dict(font_profile='public-notes'),
                 dict(ref=policy.FONT_REF, fonts=True, repository='someone/SWCLI'),
                 dict(native_full=True, repository='someone/SWCLI'),
                 dict(ref=policy.FONT_REF, fonts=True, font_profile='unknown'),
                 dict(event='pull_request', ref=policy.FONT_REF, fonts=True), dict(fonts=1)]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.select(**case)

    def test_all_manual_flag_ref_combinations_have_one_route_or_fail(self):
        for ref in ('refs/heads/main', policy.FONT_REF, 'refs/heads/other'):
            for fonts in (False, True):
                for full in (False, True):
                    for profile in ('internal', 'public-notes'):
                        invalid = fonts and (full or ref != policy.FONT_REF) or not fonts and profile != 'internal'
                        args = dict(ref=ref, fonts=fonts, native_full=full, font_profile=profile)
                        if invalid:
                            with self.assertRaises(ValueError): self.select(**args)
                        else:
                            self.assertEqual(self.select(**args), 'font-scopes' if fonts else 'standard')

    def test_routing_jobs_depend_on_portable_policy_and_do_not_use_raw_skip_flags(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        for name, selected in (('test', 'standard'), ('package', 'standard'), ('font-scopes-calibration', 'font-scopes')):
            import re
            section = re.split(r'\n  [a-z][a-z0-9-]*:', text.split('  ' + name + ':', 1)[1], maxsplit=1)[0]
            self.assertIn('needs: [native-profile, dispatch-policy]', section)
            self.assertIn("needs.dispatch-policy.outputs.validation_profile == '" + selected + "'", section)
        policy_job = text.split('  dispatch-policy:', 1)[1].split('  tag-policy:', 1)[0]
        self.assertIn('validate-ci-dispatch.py', policy_job)
        self.assertNotIn('secrets.', policy_job)
        self.assertNotIn('continue-on-error', policy_job)


if __name__ == '__main__':
    unittest.main()
