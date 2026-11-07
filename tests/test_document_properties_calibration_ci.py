"""Portable hosted-wiring checks. Never acquires or controls a native host."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('docprops_owned_ci', ROOT / 'scripts/ci/verify-document-properties-calibration.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class BranchContext(unittest.TestCase):
    def setUp(self):
        self.head = 'a' * 40
        self.env = {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REPOSITORY': 'YJBeetle/SWCLI',
                    'GITHUB_REF': ci.BRANCH_REF, 'GITHUB_SHA': self.head, 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}

    def test_exact_manual_branch_context_is_internal_with_fixed_budgets(self):
        result = ci.source_context(self.head, self.env, self.head)
        self.assertEqual(result['source_head'], self.head)
        self.assertFalse(result['full_acceptance_eligible'])
        self.assertEqual((result['native_timeout_seconds'], result['group_timeout_seconds']), (600, 1800))

    def test_pr_other_repo_ref_or_head_never_enters_calibration(self):
        for key, value in [('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_EVENT_NAME', 'pull_request_target'),
                           ('GITHUB_EVENT_NAME', 'push'), ('GITHUB_REPOSITORY', 'fork/SWCLI'),
                           ('GITHUB_REF', 'refs/heads/main'), ('GITHUB_SHA', 'b' * 40)]:
            env = {**self.env, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                ci.source_context(self.head, env, self.head)
        for expected, actual in [('', self.head), ('main', self.head), (self.head, 'b' * 40)]:
            with self.subTest(expected=expected, actual=actual), self.assertRaises(RuntimeError):
                ci.source_context(expected, self.env, actual)

    def test_main_rejects_context_before_importing_com_or_starting_host(self):
        with patch.object(ci, 'source_context', side_effect=RuntimeError('rejected')), patch.object(ci, 'run_owned') as run:
            with self.assertRaisesRegex(RuntimeError, 'rejected'):
                ci.main(['--expected-head', self.head])
            run.assert_not_called()


class OwnedPump(unittest.TestCase):
    def test_driver_runs_once_in_worker_and_owner_pumps_on_original_sta(self):
        from types import SimpleNamespace
        owner = threading.get_ident()
        ready = threading.Event()
        calls = []
        def run(args):
            calls.append(threading.get_ident())
            if not ready.wait(3):
                raise RuntimeError('owner did not pump')
            return 17
        def pump():
            self.assertEqual(threading.get_ident(), owner)
            ready.set()
        self.assertEqual(ci.run_driver_with_pump(SimpleNamespace(run=run), None, pump), 17)
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(calls[0], owner)

    def test_driver_failure_propagates_without_second_run(self):
        from types import SimpleNamespace
        calls = []
        def run(args):
            calls.append(True)
            raise ValueError('first driver failure')
        with self.assertRaisesRegex(ValueError, 'first driver failure'):
            ci.run_driver_with_pump(SimpleNamespace(run=run), None, lambda: None)
        self.assertEqual(calls, [True])


class CompleteInternalEvidence(unittest.TestCase):
    def reports(self):
        row = {'success': True, 'plan_index': 1, 'native_setter_calls': 1, 'native_return': True,
               'saved': {'path': 'fixture.SLDPRT', 'sha256': 'abc'},
               'final': {'typed': False}, 'saved_profile': {'typed': False}, 'readonly_profile': {'typed': False}}
        report = {'owned_interface_binding': {'source': 'parent-owned-COM-marshal', 'unmarshal_attempted': True, 'identity_verified': True},
                  'success': True, 'cleanup_errors': [], 'remaining_registered_test_documents': [],
                  'actual_attach_pid': 3140, 'manual_host_still_running': True, 'stage': 'standards',
                  'full_acceptance_eligible': False, 'native_timeout_seconds': 600, 'group_timeout_seconds': 1800,
                  'cases': []}
        for kind in ('part', 'assembly', 'drawing'):
            writes = [{**copy.deepcopy(row), 'plan_index': index} for index in range(1, 13)]
            report['cases'].append({'kind': kind, 'success': True, 'successful_planned_transitions': 12, 'writes': writes})
        driver = {'owned_interface_transfer_completed': True, 'success': True, 'worker_authorized': True, 'attach_pid': 3140,
                  'host_termination_attempted': False, 'automatic_retry': False, 'automatic_rollback': False,
                  'native_timeout_seconds': 600, 'group_timeout_seconds': 1800}
        return report, driver

    def test_36_complete_transitions_are_still_only_internal(self):
        report, driver = self.reports()
        self.assertEqual(ci.verify_complete_report(report, driver, 3140), 36)
        self.assertFalse(report['full_acceptance_eligible'])

    def test_r4_shaped_partial_report_never_becomes_complete(self):
        for mode in ('30-setters', '29-roundtrips', 'profile-drift', 'bool-int-drift', 'no-profiles', 'repeated-setter', 'false-return', 'wrong-pid', 'cleanup-failure', 'changed-budget'):
            with self.subTest(mode=mode):
                report, driver = self.reports()
                row = report['cases'][-1]['writes'][-1]
                if mode == '30-setters':
                    report['cases'][-1]['writes'] = report['cases'][-1]['writes'][:6]
                elif mode == '29-roundtrips':
                    del report['cases'][-1]['writes'][5]['readonly_profile']
                elif mode == 'profile-drift':
                    row['readonly_profile']['extra'] = True
                elif mode == 'bool-int-drift':
                    row['readonly_profile']['typed'] = 0
                elif mode == 'no-profiles':
                    for key in ('final', 'saved_profile', 'readonly_profile'):
                        row.pop(key)
                elif mode == 'repeated-setter':
                    row['native_setter_calls'] = 2
                elif mode == 'false-return':
                    row['native_return'] = False
                elif mode == 'wrong-pid':
                    report['actual_attach_pid'] = 3141
                elif mode == 'cleanup-failure':
                    report['cleanup_errors'].append({'error': 'fixture left'})
                elif mode == 'changed-budget':
                    driver['group_timeout_seconds'] = 3600
                with self.assertRaises(RuntimeError):
                    ci.verify_complete_report(report, driver, 3140)

    def test_manifest_retains_source_head_and_every_original_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            (output / 'report.json').write_text('{"success": false}')
            (output / 'nested').mkdir()
            (output / 'nested/driver.json').write_text('{}')
            ci.manifest(output, {'source_head': 'a' * 40, 'full_acceptance_eligible': False})
            result = json.loads((output / 'manifest.json').read_text())
            self.assertEqual([r['path'] for r in result['files']], ['nested/driver.json', 'report.json'])
            self.assertEqual(len(result['sources']), 4)
            self.assertTrue(all(len(row['sha256']) == 64 for row in result['files']))
            self.assertFalse(result['full_acceptance_eligible'])


class DedicatedWorkflow(unittest.TestCase):
    def test_only_explicit_exact_head_manual_opt_in_can_reach_private_inputs(self):
        workflow = (ROOT / '.github/workflows/document-preferences.yml').read_text()
        job = workflow.split('  docprops-calibration:\n', 1)[1].split('\n\n  release:', 1)[0]
        guard = job.split('    runs-on:', 1)[0]
        for term in ("github.event_name == 'workflow_dispatch'", "github.repository == 'YJBeetle/SWCLI'",
                     "github.ref == '" + ci.BRANCH_REF + "'", 'inputs.docprops_calibration',
                     'inputs.docprops_calibration != inputs.docprops_public', '!inputs.native_full', 'inputs.docprops_expected_head == github.sha'):
            self.assertIn(term, guard)
        self.assertIn('persist-credentials: false', job)
        self.assertIn('actions: read', job)
        self.assertIn('if: ${{ !inputs.docprops_public }}', job)
        self.assertIn('if: ${{ inputs.docprops_public }}', job)
        self.assertIn('digest-mismatch: error', job)
        self.assertLess(job.index('--check-dependency'), job.index('secrets.'))
        self.assertIn('ref: ${{ github.sha }}', job)
        self.assertLess(job.index('--check-context'), job.index('secrets.'))
        self.assertIn('default: false\n        type: boolean\n      docprops_public_scope:', workflow)
        self.assertNotIn('pull_request_target:', workflow)
        self.assertNotIn('smoke-solidworks.ps1', job)
        self.assertNotIn('Upload private installer logs', job)
        self.assertIn('group: swcli-docprops-performance-windows-${{ github.ref }}', job)
        self.assertNotIn('group: swcli-hosted-windows-solidworks', job)
        self.assertIn('cancel-in-progress: false', job)
        self.assertIn('if: always()\n        shell: powershell\n        run: scripts/ci/windows/cleanup-hosted-solidworks.ps1', job)
        self.assertIn('C:\\Workspace\\swcli-docprops-${{ github.run_id }}-${{ github.run_attempt }}', job)
        self.assertIn('--prepare-gb-inputs', job)
        self.assertIn('--drawing-template $drawingTemplate', job)
        self.assertIn('gate_support/drawing_template.py', job)
        self.assertIn('timeout-minutes: 65', job)
        self.assertIn('-ProbeRoot $env:PROBE_ROOT -PrivateInputsOnly', job)
        cleanup = (ROOT / 'scripts/ci/windows/cleanup-hosted-solidworks.ps1').read_text()
        private_only = cleanup.split('if (-not $PrivateInputsOnly) {', 1)[1].split('$lmgrdPidPath', 1)[0]
        self.assertIn('Get-Process -Name SLDWORKS', private_only)
        self.assertNotIn('Get-Process -Name SLDWORKS', cleanup.split('$lmgrdPidPath', 1)[1])
        self.assertIn('-InventoryPath "$env:PROBE_ROOT\\vba-runtime.json"', job)
        self.assertNotIn('  push:', workflow)
        self.assertNotIn('  pull_request:', workflow)
        primary = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertNotIn('  docprops-calibration:', primary)
        self.assertIn('  package:', primary)
        self.assertIn('  test:', primary)

    def test_independent_workflow_stays_within_dispatch_input_limit(self):
        import yaml
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            data = yaml.safe_load(path.read_text())
            trigger = data.get(True, data.get('on', {}))
            dispatch = trigger.get('workflow_dispatch') if isinstance(trigger, dict) else None
            if isinstance(dispatch, dict):
                self.assertLessEqual(len(dispatch.get('inputs', {})), 25, path.name)
        data = yaml.safe_load((ROOT / '.github/workflows/document-preferences.yml').read_text())
        self.assertEqual(set(data.get(True, data.get('on'))), {'workflow_dispatch'})
        self.assertEqual(data['permissions'], {'contents': 'read'})

    def test_owned_harness_remains_exclusive_and_scope_is_finite(self):
        harness = (ROOT / 'scripts/ci/verify-through-all-calibration.py').read_text()
        self.assertIn('checked(owned, "calibration must never attach to an existing host")', harness)
        self.assertIn('"ExitApp", lambda: _com_value(app, "ExitApp"), owned', harness)
        wrapper = (ROOT / 'scripts/ci/verify-document-properties-calibration.py').read_text()
        self.assertNotIn('GetActiveObject', wrapper)
        self.assertNotIn('DispatchEx', wrapper)
        self.assertNotIn('taskkill', wrapper)
        from swcli.document_drafting_standard import CALIBRATED_DRAFTING_TRANSITIONS
        self.assertEqual(len(CALIBRATED_DRAFTING_TRANSITIONS), 36)
