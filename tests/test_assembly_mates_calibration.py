"""Calibration wiring/budgets/content comparisons; no native CAD proof."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def load(filename):
    spec=importlib.util.spec_from_file_location(filename.replace('-','_').replace('.','_'), ROOT/'scripts/ci'/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class CalibrationTests(unittest.TestCase):
    def test_manual_branch_scoped_job_never_changes_default_native_gate_or_concurrency(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        job=workflow.split('  assembly-mates-calibration:\n',1)[1].split('\n\n  release:',1)[0]
        default=workflow.split('  solidworks-e2e:\n',1)[1].split('\n\n  assembly-mates-calibration:',1)[0]
        inputs=workflow.split('      assembly_mates_calibration:\n',1)[1].split('      native_full:',1)[0]
        self.assertIn('default: false',inputs)
        condition=next(line for line in job.splitlines() if line.startswith('    if:'))
        for part in ("github.event_name == 'workflow_dispatch'", "github.repository == 'YJBeetle/SWCLI'",
                     "github.ref == 'refs/heads/codex/swcli-assembly-mates'", 'inputs.assembly_mates_calibration'):
            self.assertIn(part,condition)
        self.assertNotIn('pull_request',condition)
        self.assertIn('group: swcli-assembly-mates-${{ github.ref }}',job)
        self.assertIn('cancel-in-progress: false',job)
        self.assertIn('group: swcli-hosted-windows-solidworks',default)
        self.assertNotIn('assembly_mates_calibration',default)
        self.assertIn('needs: [test, package]',job)
        self.assertIn('digest-mismatch: error',job)
        self.assertIn('timeout-minutes: 31',job)
        self.assertIn('run-assembly-mates-calibration.py',job)
        self.assertIn("inputs.assembly_mates_stage != 'public'",job)
        self.assertIn("inputs.assembly_mates_stage == 'public'",job)
        self.assertIn('--mode public',job)
        self.assertNotIn('smoke-solidworks.ps1',job)
        self.assertIn('if: always()',job)
        self.assertIn('${{ runner.temp }}\\swcli-native-smoke',job)
        self.assertIn('cleanup-hosted-solidworks.ps1',job)

    def test_external_watchdog_has_fixed_native_and_group_budgets_without_retry(self):
        watchdog=load('run-assembly-mates-calibration.py')
        self.assertEqual(watchdog.NATIVE_SECONDS,600)
        self.assertEqual(watchdog.GROUP_SECONDS,1800)
        self.assertIsNone(watchdog.budget_failure(599,0,0))
        self.assertEqual(watchdog.budget_failure(600,0,0),'native-call-budget-600-seconds')
        self.assertEqual(watchdog.budget_failure(1800,0,None),'group-budget-1800-seconds')
        self.assertIsNone(watchdog.budget_failure(1799,0,1700))
        source=(ROOT/'scripts/ci/run-assembly-mates-calibration.py').read_text()
        self.assertEqual(source.count('subprocess.Popen('),1)
        self.assertNotIn('taskkill',source)
        self.assertIn('TerminateProcess(host_handle,124)',source)
        self.assertIn('watchdog.json',source)
        self.assertIn('stdout.log',source)
        self.assertIn('stderr.log',source)

    def test_save_reopen_compares_content_and_uses_new_face_ownership_not_old_session_tokens(self):
        calibration=load('verify-assembly-mates-calibration.py')
        content=dict(title='before',path='old',update_stamp=3,modified=True,configuration='Default',
            components=[dict(name='a',source_update_stamp=1,faces=[dict(index=0,reference_sha256='aaa')]),
                        dict(name='b',source_update_stamp=2,faces=[dict(index=0,reference_sha256='bbb')])],
            mates=[dict(references=['aaa','bbb'],distance_mm=0)])
        expected=calibration.persistent_shape(content)
        reopened=copy.deepcopy(content)
        reopened.update(title='saved',path='saved.SLDASM',update_stamp=8,modified=False)
        reopened['components'][0]['source_update_stamp']=99
        reopened['components'][0]['faces'][0]['reference_sha256']='fresh'
        reopened['mates'][0]['references'][0]='fresh'
        self.assertTrue(calibration.equivalent(calibration.persistent_shape(reopened),expected))
        reopened['mates'][0]['distance_mm']=.001
        self.assertFalse(calibration.equivalent(calibration.persistent_shape(reopened),expected))
        source=(ROOT/'scripts/ci/verify-assembly-mates-calibration.py').read_text()
        self.assertIn('GetDocumentCount',source)
        self.assertIn('read_only=True',source)
        self.assertIn('not-run-production-write-fail-closed',source)
        self.assertIn('pythoncom.LoadTypeLib',source)
        self.assertIn('REQUIRED_MEMBERS',source)
        self.assertIn('part_hash',source)


if __name__=='__main__':unittest.main()
