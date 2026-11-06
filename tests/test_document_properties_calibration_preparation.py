"""Fixture preparation faults are portable control checks, never native evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from test_document_properties_calibration import Calibration, module, standard_fixture
from test_document_properties_calibration_ci import ci, CompleteInternalEvidence


class PreparationControl(unittest.TestCase):
    def prepare(self, source):
        c, doc, front = standard_fixture()
        doc.standard = source
        case = {'kind': 'assembly', 'writes': [], 'initial': {'standard': source}}
        c.report['cases'].append(case)
        roundtrips = []
        def roundtrip(document, kind, foreground, expected, state, context, row, label, continuation):
            self.assertFalse(continuation)
            roundtrips.append(copy.deepcopy(expected))
            row.update(saved={'path': 'prepared.SLDASM', 'sha256': 'a' * 64},
                       saved_profile=copy.deepcopy(expected), readonly_profile=copy.deepcopy(expected))
            return document
        c.standard_roundtrip = roundtrip
        return c, doc, front, case, roundtrips

    def test_known_named_source_prepares_once_and_preserves_full_fixed_profile(self):
        for source in range(1, 7):
            with self.subTest(source=source):
                c, doc, front, case, roundtrips = self.prepare(source)
                c.prepare_standards_stage(doc, 'assembly', front, case)
                self.assertEqual([e for e in doc.events if isinstance(e, tuple)], [('standard-set', 7)])
                self.assertEqual(len(roundtrips), 1)
                self.assertEqual(case['writes'][0]['native_setter_calls'], 1)
                self.assertEqual(c.report['prepared_native_inputs']['assembly']['profile'], roundtrips[0])
                self.assertNotIn('successful_planned_transitions', case)

    def test_already_gb_is_saved_and_reopened_with_zero_setters(self):
        c, doc, front, case, roundtrips = self.prepare(7)
        c.prepare_standards_stage(doc, 'assembly', front, case)
        self.assertEqual(len(roundtrips), 1)
        self.assertFalse(any(isinstance(e, tuple) for e in doc.events))
        self.assertEqual(case['writes'][0]['native_setter_calls'], 0)
        self.assertEqual(case['writes'][0]['mutation'], {'attempted': False, 'may_have_changed': False})

    def test_custom_unknown_bool_or_changed_source_refuses_before_setter(self):
        for source in (8, 999, True):
            with self.subTest(source=source):
                c, doc, front, case, roundtrips = self.prepare(source)
                with self.assertRaises((RuntimeError, ValueError)):
                    c.prepare_standards_stage(doc, 'assembly', front, case)
                self.assertEqual(roundtrips, [])
                self.assertFalse(any(isinstance(e, tuple) for e in doc.events))
        c, doc, front, case, _ = self.prepare(1)
        case['initial']['standard'] = 2
        with self.assertRaisesRegex(RuntimeError, 'unchanged known named source'):
            c.prepare_standards_stage(doc, 'assembly', front, case)
        self.assertEqual(case['writes'], [])

    def test_false_seed_stops_without_second_setter_or_prepared_manifest(self):
        c, doc, front, case, roundtrips = self.prepare(1)
        doc.extension.standard_return = False
        with self.assertRaisesRegex(RuntimeError, 'no retry'):
            c.prepare_standards_stage(doc, 'assembly', front, case)
        self.assertEqual([e for e in doc.events if isinstance(e, tuple)], [('standard-set', 7)])
        self.assertEqual(roundtrips, [])
        self.assertNotIn('prepared_native_inputs', c.report)
        self.assertTrue(case['writes'][0]['mutation']['may_have_changed'])

    def test_roundtrip_failure_does_not_emit_prepared_input(self):
        c, doc, front, case, _ = self.prepare(1)
        def fail(*args):
            raise RuntimeError('readonly profile mismatch')
        c.standard_roundtrip = fail
        with self.assertRaisesRegex(RuntimeError, 'readonly profile mismatch'):
            c.prepare_standards_stage(doc, 'assembly', front, case)
        self.assertNotIn('prepared_native_inputs', c.report)
        self.assertEqual(len([e for e in doc.events if isinstance(e, tuple)]), 1)

    def test_standard_group_rechecks_prepared_full_profile_before_any_setter(self):
        c, doc, front = standard_fixture()
        expected = c.standard_reader(doc, 2)
        expected['observed_defaults']['length_units']['decimal_places'] = 999
        c.prepared_inputs = {'assembly': {'profile': expected}}
        case = {'kind': 'assembly', 'writes': [], 'initial': {'standard': 7}}
        with self.assertRaisesRegex(RuntimeError, 'prepared GB profile changed'):
            c.standards_stage(doc, 'assembly', front, case)
        self.assertEqual(case['writes'], [])
        self.assertFalse(any(isinstance(e, tuple) for e in doc.events))


class PreparationReceipt(unittest.TestCase):
    def fixture(self):
        report, driver = CompleteInternalEvidence().reports()
        report['stage'] = 'standards-prepare'
        report['prepared_native_inputs'] = {}
        for index, case in enumerate(report['cases']):
            kind = case['kind']
            profile = {'standard': {'value': 'gb', 'native_value': 7}, 'observed_defaults': {'fake': True}}
            source = 7 if kind == 'drawing' else 1
            row = {'success': True, 'plan_index': 1, 'source': source, 'target': 7,
                   'source_name': 'gb' if source == 7 else 'ansi', 'target_name': 'gb',
                   'native_setter_calls': int(source != 7), 'native_return': True if source != 7 else None,
                   'mutation': {'attempted': source != 7, 'may_have_changed': source != 7},
                   'final': profile, 'saved_profile': copy.deepcopy(profile), 'readonly_profile': copy.deepcopy(profile),
                   'saved': {'path': 'fake.' + kind, 'sha256': 'a' * 64}}
            case['writes'] = [row]
            item = {'kind': kind, 'path': row['saved']['path'], 'sha256': row['saved']['sha256'], 'profile': profile}
            if kind == 'part':
                case['geometry_initial'] = item['geometry_initial'] = {'fake': 1}
                row['saved_geometry'] = row['reopened_geometry'] = {'fake': 1}
            report['prepared_native_inputs'][kind] = item
        return report, driver

    def test_two_seed_setters_and_one_noop_are_separate_from_standard_36(self):
        report, driver = self.fixture()
        inputs, count = ci.verify_prepared_report(report, driver, 3140)
        self.assertEqual(count, 2)
        self.assertEqual(set(inputs), {'part', 'assembly', 'drawing'})
        with self.assertRaises(RuntimeError):
            ci.verify_complete_report(report, driver, 3140)

    def test_wrong_pid_budget_false_duplicate_noop_or_profile_refused(self):
        for fault in ('pid', 'budget', 'false', 'duplicate', 'noop', 'profile', 'geometry', 'hash', 'partial'):
            with self.subTest(fault=fault):
                report, driver = self.fixture()
                row = report['cases'][0]['writes'][0]
                if fault == 'pid': report['actual_attach_pid'] += 1
                elif fault == 'budget': driver['group_timeout_seconds'] = 3600
                elif fault == 'false': row['native_return'] = False
                elif fault == 'duplicate': row['native_setter_calls'] = 2
                elif fault == 'noop': report['cases'][2]['writes'][0]['mutation']['attempted'] = True
                elif fault == 'profile': row['readonly_profile']['observed_defaults']['fake'] = 1
                elif fault == 'geometry': row.pop('reopened_geometry')
                elif fault == 'hash': report['prepared_native_inputs']['part']['sha256'] = 'bad'
                elif fault == 'partial': report['cases'].pop()
                with self.assertRaises(RuntimeError):
                    ci.verify_prepared_report(report, driver, 3140)

    def test_preparation_failure_starts_only_one_authorized_group(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            driver = SimpleNamespace(default_python=lambda: 'python')
            calls = []
            def run(_driver, args, pump):
                calls.append(args)
                path = output / 'standards-prepare-driver'
                path.mkdir()
                (path / 'driver.json').write_text(json.dumps({'success': False}))
                return 1
            with patch.object(ci, 'run_driver_with_pump', side_effect=run):
                with self.assertRaisesRegex(RuntimeError, 'standards-prepare failed'):
                    ci.run_groups(output, 'tlb', 'drawing', {}, 3140, b'private', driver, lambda: None,
                                  lambda label, func: func(), {}, part_template=None, assembly_template=None,
                                  prepare_gb_inputs=True)
            self.assertEqual([args.stage for args in calls], ['standards-prepare'])
            self.assertEqual(calls[0].attach_pid, 3140)
            self.assertFalse((output / 'prepared-inputs.json').exists())

    def test_two_workers_share_one_owned_pid_and_distinct_paths_without_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            prep, receipt = self.fixture()
            prep['script_sha256'] = 'f' * 64
            native, _ = CompleteInternalEvidence().reports()
            for kind, item in prep['prepared_native_inputs'].items():
                path = output / 'standards-prepare' / (kind + '.native')
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(kind.encode())
                item['path'] = str(path)
                item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                case = next(c for c in prep['cases'] if c['kind'] == kind)
                case['writes'][0]['saved'] = {'path': str(path), 'sha256': item['sha256']}
            calls = []
            def run(_driver, args, pump):
                calls.append(args)
                path = Path(args.output)
                path.mkdir(exist_ok=True)
                (path / 'report.json').write_text(json.dumps(prep if len(calls) == 1 else native))
                sibling = output / (path.name + '-driver')
                sibling.mkdir()
                (sibling / 'driver.json').write_text(json.dumps(receipt))
                return 0
            case = {}
            with patch.object(ci, 'run_driver_with_pump', side_effect=run):
                ci.run_groups(output, 'tlb', 'drawing', {}, 3140, b'private', SimpleNamespace(default_python=lambda:'python'),
                              lambda:None, lambda label, func:func(), case, part_template=None, assembly_template=None,
                              prepare_gb_inputs=True)
            self.assertEqual([args.stage for args in calls], ['standards-prepare', 'standards'])
            self.assertEqual([args.attach_pid for args in calls], [3140, 3140])
            self.assertEqual([args.owned_interface_data for args in calls], [b'private', b'private'])
            self.assertNotEqual(calls[0].output, calls[1].output)
            self.assertIsNone(calls[0].prepared_inputs)
            self.assertEqual(calls[1].prepared_inputs, str(output / 'prepared-inputs.json'))
            self.assertEqual(case['completed_transitions'], 36)
            self.assertEqual(case['fixture_preparation_setters'], 2)


class PreparedNativeFiles(unittest.TestCase):
    def test_copy_is_new_hash_equal_and_does_not_add_second_box(self):
        from test_document_properties_calibration import fixture, Doc
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'seed.SLDPRT'
            source.write_bytes(b'owned-generated-native')
            c = fixture()
            c.output, c.prefix = root, 'owned-test'
            c.args.stage = 'standards'
            geometry = {'solid_body_count': 1, 'volume_mm3': 12000, 'surface_area_mm2': 3800,
                        'centroid_mm': {'x': 20, 'y': 15, 'z': 5}}
            c.prepared_inputs = {'part': {'path': str(source), 'sha256': module.digest(source), 'geometry_initial': geometry}}
            c.report['cases'] = [{}]
            opened = []
            doc = Doc()
            c.open_native = lambda path, **kwargs: (opened.append((path, kwargs)) or ({'ok': True}, doc))
            c.register = lambda *args: None
            c.source_file = lambda *args: None
            c.rectangle = c.extrude = lambda **kwargs: self.fail('prepared box must not be recreated')
            c.measure = lambda **kwargs: {'ok': True, 'metrics': copy.deepcopy(geometry)}
            c.save_new = lambda *args: {'path': 'new-baseline'}
            c.create('part', 'part-target')
            copied = Path(opened[0][0])
            self.assertNotEqual(copied, source)
            self.assertEqual(copied.read_bytes(), source.read_bytes())
            self.assertIs(opened[0][1]['read_only'], False)
            self.assertEqual(c.report['cases'][0]['geometry_initial'], geometry)
            source.write_bytes(b'drift')
            with self.assertRaisesRegex(RuntimeError, 'prepared source changed'):
                c.create('part', 'part-target')
            self.assertEqual(len(opened), 1)

    def test_manifest_pid_script_hash_kind_or_profile_mismatch_refuses(self):
        for fault in (None, 'pid', 'script', 'bytes', 'kind', 'profile', 'outside'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                workspace = root / 'workspace'
                prep = workspace / 'standards-prepare'
                prep.mkdir(parents=True)
                inputs = {}
                for kind, suffix in module.SUFFIX.items():
                    path = prep / ('seed.' + suffix)
                    path.write_bytes(kind.encode())
                    inputs[kind] = {'kind': kind, 'path': str(path), 'sha256': module.digest(path),
                                    'profile': {'standard': {'value': 'gb', 'native_value': 7}}}
                data = {'format': 'owned-prepared-gb-v1', 'attach_pid': 2940,
                        'script_sha256': module.digest(Path(module.__file__)), 'inputs': inputs}
                if fault == 'pid': data['attach_pid'] += 1
                elif fault == 'script': data['script_sha256'] = '0' * 64
                elif fault == 'bytes': inputs['part']['sha256'] = '0' * 64
                elif fault == 'kind': inputs.pop('drawing')
                elif fault == 'profile': inputs['part']['profile']['standard']['native_value'] = 1
                elif fault == 'outside':
                    outside = root / 'outside.SLDPRT'
                    outside.write_bytes(b'part')
                    inputs['part']['path'] = str(outside)
                manifest = workspace / 'prepared-inputs.json'
                manifest.write_text(json.dumps(data))
                c, _, _ = standard_fixture()
                c.args.prepared_inputs = str(manifest)
                actual_path = Path
                def mapped_path(value):
                    return workspace if str(value) == r'C:\Workspace' else actual_path(value)
                with patch.object(module, 'Path', side_effect=mapped_path):
                    if fault is None:
                        c.load_prepared_inputs()
                        self.assertEqual(c.prepared_inputs, inputs)
                    else:
                        with self.assertRaises((RuntimeError, ValueError)):
                            c.load_prepared_inputs()
                        self.assertFalse(hasattr(c, 'prepared_inputs'))


class PreparedWorkerAuthorization(unittest.TestCase):
    def test_prepared_manifest_is_bound_to_exact_worker_argv(self):
        from test_document_properties_calibration_watchdog import driver
        args = SimpleNamespace(attach_pid=3140, stage='standards', output='owned-output', isolated_host=True,
            owned_interface_data=b'private', swconst='installed.tlb', drawing_template='gb.drwdot',
            prepared_inputs='owned-manifest.json', part_template=None, assembly_template=None, font_typeface=None)
        with patch.object(driver, 'driver_site_packages', return_value=['site']):
            config = driver.worker_config(args, Path('calibrator.py'), Path('src'), Path('driver'))
        index = config['script_args'].index('--prepared-inputs')
        self.assertEqual(config['script_args'][index+1], 'owned-manifest.json')
        expected = driver.expected_identity(config, 4321, 'python')
        changed = copy.deepcopy(expected)
        changed['script_args'][index+1] = 'foreign-manifest.json'
        self.assertFalse(driver.exact_json(expected, changed))
        self.assertNotIn('private', json.dumps(config))
