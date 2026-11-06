"""Portable orchestration proof; these fakes are not native acceptance evidence."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests import test_document_tables as table_tests
from swcli.hosts import windows_document_tables as adapter
from swcli.daemon import operations

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("table_defaults_calibration_tests", ROOT / "scripts/ci/verify-table-defaults-calibration.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class TableCalibrationTests(unittest.TestCase):
    def test_dedicated_dispatch_is_default_off_exact_branch_head_and_keeps_secrets_out_of_prs(self):
        source = (ROOT / ".github/workflows/ci.yml").read_text()
        entry = source.split('      table_defaults_calibration:', 1)[1].split('      table_defaults_head:', 1)[0]
        self.assertIn('default: false', entry)
        job = source.split('  table-defaults-calibration:', 1)[1]
        for guard in ("github.event_name == 'workflow_dispatch'", "refs/heads/codex/docprops-table-defaults",
                      'inputs.table_defaults_calibration', 'inputs.table_defaults_head == github.sha'):
            self.assertIn(guard, job)
        self.assertNotIn('pull_request:', source)
        self.assertNotIn('smoke-solidworks.ps1', job)
        self.assertNotIn('verify-properties-calibration.py', job)
        self.assertIn('calibrate-table-defaults.ps1', job)
        self.assertIn('if: always()', job)
        self.assertIn('path: ${{ runner.temp }}/swcli-native-smoke/table-defaults/', job)
        upload = job.split('      - name: Upload original calibration evidence', 1)[1].split('  release:', 1)[0]
        for private in ('PRIVATE_ROOT', 'PROBE_ROOT', 'rclone', 'install-logs', 'vba-runtime'):
            self.assertNotIn(private, upload)
        self.assertIn('ref: ${{ inputs.table_defaults_head }}', job)
        for job_name in ('test', 'package'):
            self.assertIn("if: ${{ !(github.event_name == 'workflow_dispatch' && inputs.table_defaults_calibration) }}",
                          source.split('  ' + job_name + ':', 1)[1].split('    steps:', 1)[0])

    def test_wrapper_has_native_and_group_limits_and_one_process_start(self):
        source = (ROOT / 'scripts/ci/windows/calibrate-table-defaults.ps1').read_text()
        self.assertEqual(source.count('Start-Process '), 1)
        self.assertIn('-ge 600', source)
        self.assertIn('-ge 1800', source)
        self.assertIn('watchdog-failure.json', source)
        self.assertIn('$env:SWCLI_TRACE_NATIVE_CALLS = $previousTrace', source)
        self.assertNotIn('restart', source.lower())
        self.assertNotIn('retry', source.lower())

    def run_case(self, output, *, fail=False):
        fake = table_tests.DocumentTableTests()
        fake.setUp()
        self.addCleanup(fake.doCleanups)
        fake.kind = 2
        fake.register()
        docs = [fake.document, fake.foreground]
        fake.app.GetDocuments = lambda: tuple(docs)
        fake.app.GetDocumentCount = lambda: len(docs)
        fake.app.GetProcessID = lambda: 123
        target = output / 'annotations.SLDASM'
        target.write_bytes(b'a' * 512)
        readonly = [False]
        fake.document.IsOpenedReadOnly = lambda: readonly[0]

        def close(title):
            for document in list(docs):
                if document.GetTitle() == title:
                    docs.remove(document)
            fake.app.ActiveDoc = docs[0] if docs else None
        fake.app.CloseDoc = close

        def prepare(*args, **kwargs):
            args[6].update(path=str(target), kind='assembly', success=True)

        def opened(path, **kwargs):
            readonly[0] = kwargs.get('read_only', False)
            if fake.document not in docs:
                docs.append(fake.document)
                fake.app.ActiveDoc = fake.document
            return dict(ok=True, api_errors=0, api_warnings=0, read_only=readonly[0]), fake.document

        def save(path, **kwargs):
            Path(path).write_bytes(b'b' * 512)
            fake.modified = False
            return dict(ok=True, api_saved=True, save_errors=0, save_warnings=None)

        case, calls = {}, []
        def call(name, function):
            calls.append(name)
            return function()
        original_handler = operations.set_document_table_option_windows
        if fail:
            fake.extension.SetUserPreferenceInteger.side_effect = RuntimeError('first real setter failure')
        with mock.patch.object(gate.fixtures, 'prepare_case', side_effect=prepare), \
             mock.patch.object(gate.adapter, '_read_constants', return_value=fake.constants), \
             mock.patch.object(gate, 'open_windows_document_with_handle', side_effect=opened), \
             mock.patch.object(gate, 'create_part_windows_with_handle', return_value=(dict(ok=True), fake.foreground)), \
             mock.patch.object(gate, '_diagnose_features', return_value=dict(healthy=True, truncated=False, scanned_feature_count=2)), \
             mock.patch.object(gate, 'save_as_native_windows', side_effect=save):
            if fail:
                with self.assertRaisesRegex(RuntimeError, 'table scalar write failed'):
                    gate.calibrate_case(fake.app, output, {}, 'front', False, call, case,
                        {'host': {'process_id': 123}}, {'document': None}, profile_kind='assembly',
                        drawing_template=output / 'base.drwdot', swconst=output / 'swconst.tlb')
            else:
                gate.calibrate_case(fake.app, output, {}, 'front', False, call, case,
                    {'host': {'process_id': 123}}, {'document': None}, profile_kind='assembly',
                    drawing_template=output / 'base.drwdot', swconst=output / 'swconst.tlb')
        self.assertIs(operations.set_document_table_option_windows, original_handler)
        return fake, case, calls

    def test_fake_assembly_checks_cas_noop_readonly_persistence_and_new_save_target(self):
        with tempfile.TemporaryDirectory() as directory:
            fake, case, calls = self.run_case(Path(directory))
            self.assertTrue(case['success'])
            self.assertTrue(case['internal_calibration_only'])
            self.assertEqual(len(case['writes']), 3)
            self.assertTrue(all(not item['ok'] for item in case['conflicts']))
            self.assertEqual(case['persisted']['options'], case['final_options'])
            self.assertEqual((Path(directory) / 'annotations.SLDASM').read_bytes(), b'a' * 512)
            self.assertIn('reopen-table-defaults-readonly', calls)
            self.assertEqual(fake.extension.SetUserPreferenceInteger.call_count, 2)
            fake.app.ActivateDoc3.assert_not_called()

    def test_fake_native_failure_stops_first_setter_without_retry_rollback_or_save(self):
        with tempfile.TemporaryDirectory() as directory:
            fake, case, calls = self.run_case(Path(directory), fail=True)
            self.assertFalse(case['success'])
            self.assertEqual(fake.extension.SetUserPreferenceInteger.call_count, 1)
            self.assertNotIn('internal-table-write:bom.grid_border', calls)
            self.assertNotIn('save-table-defaults', calls)
            self.assertIn('close-table-foreground-peer', calls)
            self.assertEqual(case['writes'][-1]['mutation'], dict(attempted=True, may_have_changed=True))


if __name__ == '__main__':
    unittest.main()
