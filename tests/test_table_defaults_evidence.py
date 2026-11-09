"""Independent proof-audit refusals; generated portable fixtures are not CAD proof."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from swcli.document_tables import TABLE_FIELDS
from tests import test_document_tables as fakes

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('table_internal_audit_test', ROOT / 'scripts/ci/gate_support/table_defaults_evidence.py')
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


class TableEvidenceTests(unittest.TestCase):
    def fixture(self, directory, document_types=(1, 2, 3)):
        report = dict(success=True, cleanup_errors=[], diagnostic_case='document-table-defaults-internal',
                      full_acceptance_eligible=False, host=dict(revision='33.5.0', process_id=123), requested_document_types=list(document_types), cases=[])
        methods = ["GetExecutablePath"]
        for kind, suffix in enumerate(('SLDPRT', 'SLDASM', 'SLDDRW'), 1):
            if kind not in document_types: continue
            fake = fakes.DocumentTableTests()
            fake.setUp()
            self.addCleanup(fake.doCleanups)
            fake.kind = kind
            if kind == 3: fake.drawing()
            else: fake.register()
            original = fake.read()
            case = dict(document_type=kind, success=True, internal_calibration_only=True, preparation_only=False,
                        original=original, writes=[], noops=[], conflicts=[], public_write_gate=fake.edit(calibrated=False))
            cycle = ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in TABLE_FIELDS.values() if kind in spec['types']]
            methods += cycle
            for field, spec in TABLE_FIELDS.items():
                if kind not in spec['types']: continue
                value = not fake.native[fake.constants[spec['symbol']]] if spec['kind'] == 'Toggle' else 'thick'
                before = deepcopy(fake.read()['options'])
                changed = fake.edit(field, value)
                case['writes'].append(changed)
                case['noops'].append(fake.edit(field, value))
                case['conflicts'].append(fake.edit(field, value, expected=before))
                methods += cycle + ['IModelDocExtension.SetUserPreference' + spec['kind']] + cycle * 4
            if kind == 1:
                case['geometry_reopened'] = dict(solid_body_count=1, volume_mm3=12000.0, surface_area_mm2=3800.0, centroid_mm=dict(x=0.0, y=0.0, z=5.0))
                case['geometry'] = deepcopy(case['geometry_reopened'])
                case['geometry_before_table_write_measurement'] = dict(ok=True, metrics=deepcopy(case['geometry_reopened']))
                case['geometry_before_table_write_context_unchanged'] = True
                fields = [field for field, spec in TABLE_FIELDS.items() if kind in spec['types']]
                case['geometry_checks'] = [dict(field=field, before=deepcopy(case['geometry_reopened']), after=deepcopy(case['geometry_reopened']), **auditor.geometry.compare_table_geometry(case['geometry_reopened'], case['geometry_reopened'])) for field in ['fixture-readonly-reopen', 'before-first-table-write'] + fields + ['saved-reopen']]
            case['final_options'] = fake.read()['options']
            case['persisted'] = fake.read()
            case['readonly_rejection'] = dict(ok=False, mutation=dict(attempted=False, may_have_changed=False))
            case['save_defaults'] = dict(ok=True, api_saved=True, save_errors=0, save_warnings=None)
            methods += cycle
            for filename, key in (('annotations.' + suffix, 'file_sha256'), ('table-defaults.' + suffix, 'persisted_sha256')):
                path = directory / filename
                path.write_bytes(bytes(kind + 511))
                case[key] = auditor.sha256(path)
            report['cases'].append(case)
        stages = []
        for number, name in enumerate(('acquire-owned-host', 'ExitApp', 'WaitForOwnedProcess')):
            stages += [dict(call=name, phase=phase, time=number + index / 10) for index, phase in enumerate(('begin', 'end'))]
        (directory / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in stages))
        base = dict(event='swcli.native-call', request_id='table-defaults-calibration', operation='internal.table-defaults', worker_pid=42)
        rows = [dict(base, sequence=0, call='internal.table-defaults', phase='begin')]
        for number, method in enumerate(methods, 1):
            rows += [dict(base, sequence=number, call=method, phase=phase) for phase in ('begin', 'end')]
        rows += [dict(base, sequence=0, call='internal.table-defaults', phase='end')]
        native = directory / 'native.jsonl'
        native.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return report, native

    def test_audits_only_proven_raw_transitions_and_refuses_corrupt_originals_or_receipts(self):
        for defect in (None, 'saved-file', 'report-digest', 'partial', 'noop', 'persistence', 'trace', 'prewrite-context', 'prewrite-metrics'):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                report, native = self.fixture(directory)
                if defect == 'saved-file': (directory / 'table-defaults.SLDPRT').write_bytes(b'changed')
                if defect == 'partial': report['cases'][0]['writes'][0]['ok'] = False
                if defect == 'noop': report['cases'][0]['noops'][0]['mutation']['attempted'] = True
                if defect == 'persistence': report['cases'][0]['persisted']['options']['bom.box_border'] = dict(value='normal', native_value=1)
                if defect == 'trace': native.write_text(native.read_text().replace('"phase": "end"', '"phase": "error"', 1))
                if defect == 'prewrite-context': report['cases'][0]['geometry_before_table_write_context_unchanged'] = False
                if defect == 'prewrite-metrics': report['cases'][0]['geometry_before_table_write_measurement']['metrics']['centroid_mm']['y'] = 1e-20
                path = directory / 'report.json'
                path.write_text(json.dumps(report))
                digest = '0' * 64 if defect == 'report-digest' else auditor.sha256(path)
                if defect:
                    with self.assertRaises((ValueError, RuntimeError)):
                        auditor.audit(directory, native, report_sha256=digest)
                else:
                    result = auditor.audit(directory, native, report_sha256=digest)
                    self.assertEqual(result['native_setter_calls'], 11)
                    self.assertEqual(result['native_getter_calls'], 237)
                    self.assertEqual(result['profiles']['1']['bom.box_border'], [[1, 2], [2, 2]])
                    self.assertFalse(result['full_acceptance_eligible'])

    def test_explicit_bounded_scope_is_complete_and_cannot_hide_an_incomplete_full_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report, native = self.fixture(directory, document_types=(2, 3))
            path = directory / 'report.json'
            path.write_text(json.dumps(report))
            result = auditor.audit(directory, native, report_sha256=auditor.sha256(path))
            self.assertEqual(result['document_types'], [2, 3])
            self.assertEqual(set(result['profiles']), {'2', '3'})
            self.assertEqual((result['native_setter_calls'], result['native_getter_calls']), (8, 186))
            report['requested_document_types'] = [1, 2, 3]
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'document-type plan incomplete'):
                auditor.audit(directory, native, report_sha256=auditor.sha256(path))

    def test_scope_without_analytic_part_refuses_global_fixture_setters(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report, native = self.fixture(directory, document_types=(2, 3))
            path = directory / 'report.json'
            path.write_text(json.dumps(report))
            rows = [json.loads(line) for line in native.read_text().splitlines()]
            extra = []
            for number in (1, 2):
                extra += [dict(rows[0], sequence=number, call='SldWorks.SetUserPreferenceToggle(swSketchInference)', phase=phase)
                          for phase in ('begin', 'end')]
            for row in rows[1:-1]: row['sequence'] += 2
            rows[1:1] = extra
            native.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'global preference setter'):
                auditor.audit(directory, native, report_sha256=auditor.sha256(path))
