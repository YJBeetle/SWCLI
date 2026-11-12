"""The active integrated STEP workflow stays manual, bounded and non-publishing."""
import itertools
from pathlib import Path
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]

class StepPublicWorkflow(unittest.TestCase):
    def test_manual_job_has_two_actual_gates_no_release_and_no_private_pull_requests(self):
        w=yaml.safe_load((ROOT/'.github/workflows/step-export.yml').read_text())
        events=w.get('on',w.get(True));self.assertEqual(set(events),{'workflow_dispatch'})
        self.assertEqual(set(events['workflow_dispatch']['inputs']),{'media_path','assets_path','cleanup_profile','vfs_cache_gib'})
        self.assertEqual(set(w['jobs']),{'test','package','solidworks-e2e'})
        j=w['jobs']['solidworks-e2e'];self.assertEqual(j['needs'],['test','package'])
        self.assertEqual(j['concurrency'],{'group':'swcli-step-public-${{ github.ref }}','cancel-in-progress':False})
        self.assertIn("github.repository == 'YJBeetle/SWCLI'",j['if'])
        self.assertIn("github.event_name == 'workflow_dispatch'",j['if'])
        self.assertIn("github.ref == 'refs/heads/main' || github.ref == 'refs/heads/codex/swcli-step-export-options'",j['if'])
        self.assertIn("needs.test.result == 'success' && needs.package.result == 'success'",j['if'])
        self.assertEqual(j['timeout-minutes'],120)
        steps={s.get('id'):s for s in j['steps'] if s.get('id')}
        for k,script in [('step_public','verify-step-export-public.py'),('step_public_readback','verify-step-export-calibration.py')]:
            s=steps[k];self.assertNotIn('if',s);self.assertNotIn('continue-on-error',s)
            self.assertEqual(s['timeout-minutes'],31);self.assertEqual(s['run'].count(script),1)
            self.assertIn('if ($LASTEXITCODE -ne 0) { throw',s['run'])
        self.assertIn('--neutral-free-null-sketch-candidate',steps['step_public_readback']['run'])
        self.assertIn('--export-report',steps['step_public_readback']['run'])
        self.assertEqual(steps['native_cleanup']['if'],'always()')
        self.assertFalse({'step_calibration','step_original_preflight','native_tests'}&steps.keys())
        text=(ROOT/'.github/workflows/step-export.yml').read_text()
        self.assertNotIn('contents: write',text);self.assertNotIn('pull_request',text)
        self.assertNotIn('native_full',text);self.assertNotIn('native_step_targeted',text)
