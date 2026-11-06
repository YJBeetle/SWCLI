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
                 'host': {'process_id': 3140}}, 'standards-36/report.json': report,
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
        self.remanifest(root, context)
        return context

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
            with self.assertRaisesRegex(ValueError, 'overlapping'):
                audit.audit(root, 'a' * 40)

    def test_windows_crlf_checkout_source_is_explicitly_hashed_but_code_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            path = root / 'manifest.json'
            manifest = json.loads(path.read_text())
            relative = audit.SOURCES[0]
            crlf = (ROOT / relative).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
            manifest['sources'][relative] = hashlib.sha256(crlf).hexdigest()
            path.write_text(json.dumps(manifest))
            result = audit.audit(root, 'a' * 40, ROOT)
            self.assertEqual(result['source_byte_forms_verified_locally'][relative], 'git-CRLF')
            manifest['sources'][relative] = hashlib.sha256(b'different code').hexdigest()
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'source bytes differ'):
                audit.audit(root, 'a' * 40, ROOT)
