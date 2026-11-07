"""Synthetic evidence faults; never native acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import test_document_properties_calibration_ci as ci_tests

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('docprops_audit', ROOT / 'scripts/dev/audit-document-properties-calibration.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class OfflineEvidenceAudit(unittest.TestCase):
    def fixture(self, root, partial=False):
        report, driver = ci_tests.CompleteInternalEvidence().reports()
        driver['elapsed_seconds'] = 100
        driver.update(child_python_pid=3141, worker_identity={'pid': 3141})
        report.update(python_process_id=3141, script_sha256=hashlib.sha256((ROOT / audit.SOURCES[0]).read_bytes()).hexdigest())
        context = {'source_head': 'a' * 40, 'run_id': '123', 'run_attempt': '1', 'full_acceptance_eligible': False,
                   'native_timeout_seconds': 600, 'group_timeout_seconds': 1800}
        if partial:
            report['success'] = False
            report['cases'][-1]['writes'] = report['cases'][-1]['writes'][:6]
            report['cases'][-1]['writes'][-1].pop('readonly_profile')
            report['cases'][-1]['writes'][-1]['success'] = False
            report['failure'] = {'message': 'first real native failure'}
            driver['success'] = False
        files = {'context.json': context, 'report.json': {'success': not partial, 'cleanup_errors': [],
                 'host': {'process_id': 3140}, 'cases': [{'owned_interface': {'marshaled': True, 'released': True}}]}, 'standards-36/report.json': report,
                 'standards-36-driver/driver.json': driver}
        for relative, value in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        trace = root / 'standards-36/trace.jsonl'
        records = []
        labels = ['ISldWorks.IsSame'] + [f'part.standard-{i}.SetUserPreferenceInteger.once' for i in range(36)]
        labels += [f'profile-{i}.fixed-observed-defaults-reader' for i in range(216)]
        for label in labels:
            records.extend([{'call': label, 'phase': 'begin'},
                {'call': label, 'phase': 'end', 'elapsed_seconds': 3,
                 'begin_trace_seconds': 1, 'checkpoint_seconds': 1, 'native_seconds': 1,
                 'native_started': True, 'native_completed': True}])
        trace.write_text('\n'.join(json.dumps(row) for row in records)+'\n')
        (root / 'trace.jsonl').write_text('\n'.join(json.dumps({'call': label, 'phase': phase})
            for label in ('owned-interface.CoReleaseMarshalData', 'ExitApp', 'WaitForOwnedProcess', 'CloseProcessHandle', 'CoUninitialize')
            for phase in ('begin', 'end'))+'\n')
        self.sdk_trace(root, report)
        self.remanifest(root, context)
        return context

    def sdk_trace(self, root, report, group="standards-36", counts=None):
        report['prefix'] = 'portable-fake-sdk'
        report['standard_reads'] = {}
        expected = []
        for kind_index, case in enumerate(report['cases'], 1):
            for index in range(72 if counts is None else counts[case["kind"]]):
                label = case['kind'] + '.profile-' + str(index)
                report['standard_reads'][label] = {'snapshot': {'observed_defaults': {'document_type': kind_index}}}
                expected.append((report['prefix'] + '-' + label, 'diagnostic.document-drafting-standard-snapshot',
                                 audit.fixed_reader_cycle(kind_index)))
            for row in case['writes']:
                if row.get('native_setter_calls') == 0:
                    continue
                if group == 'standards-36':
                    row['source_name'], row['target_name'] = ('gb', 'ansi') if row['plan_index'] % 2 else ('ansi', 'gb')
                label = case['kind'] + '.standard-' + str(row['plan_index']) + '-' + row['source_name'] + '-to-' + row['target_name']
                expected.append((report['prefix'] + '-' + label, 'diagnostic.document-drafting-standard-set',
                                 ['IModelDocExtension.SetUserPreferenceInteger']))
        (root / group / 'report.json').write_text(json.dumps(report))
        with (root / (group + '-driver') / 'stderr.log').open('w') as stream:
            for request, operation, cycle in expected:
                base = {'event': 'swcli.native-call', 'worker_pid': 3141, 'request_id': request, 'operation': operation}
                stream.write(json.dumps({**base, 'sequence': 0, 'phase': 'begin', 'call': operation})+'\n')
                for sequence, method in enumerate(cycle, 1):
                    for phase in ('begin', 'end'):
                        stream.write(json.dumps({**base, 'sequence': sequence, 'phase': phase, 'call': method, 'duration_ms': 1})+'\n')
                stream.write(json.dumps({**base, 'sequence': 0, 'phase': 'end', 'call': operation, 'duration_ms': 2})+'\n')

    def remanifest(self, root, context):
        manifest = {**context, 'sources': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in audit.SOURCES},
                    'files': [{'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                              for path in sorted(root.rglob('*')) if path.is_file() and path.name != 'manifest.json']}
        (root / 'manifest.json').write_text(json.dumps(manifest))

    def test_complete_internal_coverage_and_split_totals_still_never_public_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            result = audit.audit(root, 'a' * 40, ROOT)
            self.assertTrue(result['native_group_complete'])
            self.assertEqual(result['completed_transitions'], 36)
            self.assertEqual(result['trace']['categories']['identity']['wrapper_seconds'], 3)
            self.assertEqual(result['trace']['categories']['identity']['function_body_seconds'], 1)
            self.assertFalse(result['full_acceptance_eligible'])
            self.assertEqual(result['public_whitelist_updates'], [])

    def test_partial_native_evidence_retains_first_cause_without_promoting_29_roundtrips(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root, partial=True)
            result = audit.audit(root, 'a' * 40, ROOT)
            self.assertTrue(result['all_original_hashes_verified'])
            self.assertFalse(result['native_group_complete'])
            self.assertEqual(result['per_kind']['drawing']['strict_true_returns'], 6)
            self.assertEqual(result['per_kind']['drawing']['complete_saved_readonly_transitions'], 5)
            self.assertEqual(result['first_failure']['message'], 'first real native failure')

    def test_tampered_bytes_head_and_unlisted_file_are_rejected(self):
        for fault in ('bytes', 'head', 'unlisted'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.fixture(root)
                if fault == 'bytes':
                    (root / 'standards-36/report.json').write_text('{}')
                elif fault == 'unlisted':
                    (root / 'unexpected.json').write_text('{}')
                with self.assertRaises(ValueError):
                    audit.audit(root, ('b' if fault == 'head' else 'a') * 40)

    def test_incomplete_trace_is_reported_and_overlapping_trace_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            context = self.fixture(root)
            with (root / 'standards-36/trace.jsonl').open('a') as stream:
                stream.write(json.dumps({'call': 'setter', 'phase': 'begin'})+'\n')
            self.remanifest(root, context)
            result = audit.audit(root, 'a' * 40)
            self.assertFalse(result['native_group_complete'])
            self.assertEqual(result['trace']['unfinished_call'], 'setter')
            with (root / 'standards-36/trace.jsonl').open('a') as stream:
                stream.write(json.dumps({'call': 'another', 'phase': 'begin'})+'\n')
            self.remanifest(root, context)
            result = audit.audit(root, 'a' * 40)
            self.assertFalse(result['native_group_complete'])
            self.assertIn('overlapping', result['coverage_error'])

    def test_windows_crlf_checkout_source_is_explicitly_hashed_but_code_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            path = root / 'manifest.json'
            manifest = json.loads(path.read_text())
            relative = audit.SOURCES[0]
            crlf = (ROOT / relative).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
            source_hash = hashlib.sha256(crlf).hexdigest()
            report_path = root / 'standards-36/report.json'
            report = json.loads(report_path.read_text())
            report['script_sha256'] = source_hash
            report_path.write_text(json.dumps(report))
            self.remanifest(root, json.loads((root / 'context.json').read_text()))
            manifest = json.loads(path.read_text())
            manifest['sources'][relative] = source_hash
            path.write_text(json.dumps(manifest))
            result = audit.audit(root, 'a' * 40, ROOT)
            self.assertEqual(result['source_byte_forms_verified_locally'][relative], 'git-CRLF')
            manifest['sources'][relative] = hashlib.sha256(b'different code').hexdigest()
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'source bytes differ'):
                audit.audit(root, 'a' * 40, ROOT)

    def test_sdk_repeated_setter_cannot_pass_a_complete_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            context = self.fixture(root)
            path = root / 'standards-36-driver/stderr.log'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            index = next(i for i, row in enumerate(rows) if row['call'] == 'IModelDocExtension.SetUserPreferenceInteger' and row['phase'] == 'end')
            second = [{**rows[index-1], 'sequence': 2}, {**rows[index], 'sequence': 2}]
            rows[index+1:index+1] = second
            path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
            self.remanifest(root, context)
            result = audit.audit(root, 'a' * 40)
            self.assertFalse(result['native_group_complete'])
            self.assertIn('single setter', result['coverage_error'])

    def test_sdk_missing_fixed_getter_cannot_pass_a_complete_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); context = self.fixture(root)
            path = root / 'standards-36-driver/stderr.log'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows.pop(2)
            path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
            self.remanifest(root, context)
            result = audit.audit(root, 'a' * 40)
            self.assertFalse(result['native_group_complete'])
            self.assertIn('SDK', result['coverage_error'])


    def preparation_fixture(self, root):
        from test_document_properties_calibration_preparation import PreparationReceipt
        context = self.fixture(root)
        context['fixture_preparation_required'] = True
        (root / 'context.json').write_text(json.dumps(context))
        report, driver = PreparationReceipt().fixture()
        report.update(python_process_id=3141, script_sha256=hashlib.sha256((ROOT / audit.SOURCES[0]).read_bytes()).hexdigest())
        driver.update(elapsed_seconds=50, child_python_pid=3141, worker_identity={'pid': 3141}, output=r'C:\Workspace\prep')
        prep = root / 'standards-prepare'; prep.mkdir()
        sibling = root / 'standards-prepare-driver'; sibling.mkdir()
        (sibling / 'driver.json').write_text(json.dumps(driver))
        for kind, item in report['prepared_native_inputs'].items():
            path = prep / (kind + '.native')
            path.write_bytes(kind.encode())
            item.update(path=driver['output'] + '\\' + path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            row = next(case for case in report['cases'] if case['kind'] == kind)['writes'][0]
            row['saved'] = {'path': item['path'], 'sha256': item['sha256']}
        (root / 'prepared-inputs.json').write_text(json.dumps({'format': 'owned-prepared-gb-v1', 'attach_pid': 3140,
            'script_sha256': report['script_sha256'], 'inputs': report['prepared_native_inputs']}))
        records = []
        labels = ['prep.SetUserPreferenceInteger.once'] * 2 + ['prep.fixed-observed-defaults-reader'] * 15
        for label in labels:
            records.extend([{'call': label, 'phase': 'begin'}, {'call': label, 'phase': 'end', 'elapsed_seconds': 3,
                'begin_trace_seconds': 1, 'checkpoint_seconds': 1, 'native_seconds': 1,
                'native_started': True, 'native_completed': True}])
        (prep / 'trace.jsonl').write_text('\n'.join(json.dumps(row) for row in records)+'\n')
        self.sdk_trace(root, report, 'standards-prepare', {'part': 6, 'assembly': 6, 'drawing': 3})
        native_path = root / 'standards-36/report.json'
        native = json.loads(native_path.read_text())
        for case in native['cases']:
            item = report['prepared_native_inputs'][case['kind']]
            case.update(prepared_input=item, standard_initial=item['profile'])
        native_path.write_text(json.dumps(native))
        self.remanifest(root, context)
        return context

    def test_independent_preparation_and_original_36_are_both_audited(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.preparation_fixture(root)
            result = audit.audit(root, 'a' * 40)
            self.assertTrue(result['native_group_complete'], result['coverage_error'])
            self.assertEqual(result['completed_transitions'], 36)
            self.assertEqual(result['fixture_preparation']['setter_requests'], 2)
            self.assertEqual(result['fixture_preparation']['profile_reads'], 15)
            self.assertFalse(result['full_acceptance_eligible'])

    def test_failed_preparation_retains_first_cause_without_requiring_main_files(self):
        with tempfile.TemporaryDirectory() as folder:
            import shutil
            root = Path(folder); context = self.preparation_fixture(root)
            path = root / 'standards-prepare/report.json'
            report = json.loads(path.read_text())
            report.update(success=False, first_call_failure={'message': 'first seed setter failed'})
            path.write_text(json.dumps(report))
            shutil.rmtree(root / 'standards-36')
            shutil.rmtree(root / 'standards-36-driver')
            self.remanifest(root, context)
            result = audit.audit(root, 'a' * 40)
            self.assertTrue(result['all_original_hashes_verified'])
            self.assertFalse(result['native_group_complete'])
            self.assertEqual(result['active_group_at_conclusion'], 'standards-prepare')
            self.assertEqual(result['first_failure']['message'], 'first seed setter failed')

    def test_prepared_lineage_or_native_bytes_cannot_be_substituted(self):
        for fault in ('lineage', 'bytes'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); context = self.preparation_fixture(root)
                if fault == 'bytes': (root / 'standards-prepare/part.native').write_bytes(b'substitute')
                else:
                    path = root / 'standards-36/report.json'
                    report = json.loads(path.read_text())
                    report['cases'][0]['prepared_input']['sha256'] = '0' * 64
                    path.write_text(json.dumps(report))
                self.remanifest(root, context)
                result = audit.audit(root, 'a' * 40)
                self.assertFalse(result['native_group_complete'])
                self.assertIn('prepared', result['coverage_error'])
