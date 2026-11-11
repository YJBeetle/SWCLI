"""Bounded native write plan, pre-mutation durability, persistence and first-fail stops."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from swcli.document_unit_profile import FIELDS, SYSTEMS, target, observe
from test_unit_profile_public_gate import profile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('unit_write_test', ROOT/'scripts/ci/gate_support/unit_profile_writes.py')
write = importlib.util.module_from_spec(spec);spec.loader.exec_module(write)


class WritePlanTests(unittest.TestCase):
    def test_actual_tlb_targets_are_checked_before_native_write(self):
        report=json.loads((ROOT/'docs/evidence/units-profile/lease-exit-42361728509/report.json').read_text())
        enums=report['official_enums'];write.validate_native_targets(enums)
        for value in (999,True,None):
            broken=deepcopy(enums);broken['swUnitSystem_e']['swUnitSystem_CGS']=value
            with self.assertRaises(RuntimeError):write.validate_native_targets(broken)

    def test_all_eight_existing_candidate_domains_are_changed_not_noops(self):
        for field in FIELDS:
            if field == 'system':continue
            candidates = FIELDS[field].get('targets', tuple(range(9)))
            for source in [target(field, value) for value in candidates]+[999]:
                plan = write.scalar_targets(field, source)
                self.assertEqual(set(plan), set(candidates))
                for value in plan:
                    self.assertNotEqual(source, target(field, value))
                    source = target(field, value)

    def test_all_known_source_systems_use_exact_eight_directed_mmgs_spokes(self):
        expected = {(5, code) for code in (1, 2, 3, 4)} | {(code, 5) for code in (1, 2, 3, 4)}
        for source in SYSTEMS.values():
            edges = []
            for value in write.system_targets(source):
                code = target('system', value);edges.append((source, code));source = code
            self.assertEqual(len(edges), 8)
            self.assertEqual(set(edges), expected)
        self.assertEqual(write.custom_preparation(3), ('mmgs', 'custom'))
        self.assertEqual(write.custom_preparation(5), ('custom',))
        self.assertEqual(write.custom_preparation(4), ())
        for value in (True, 0, 999, '5'):
            with self.assertRaises(RuntimeError):write.system_targets(value)
            with self.assertRaises(RuntimeError):write.custom_preparation(value)


class NativeSimulation:
    def __init__(self, root, defect=None):
        self.root, self.defect = root, defect
        self.saved, self.calls, self.checkpoints = {}, [], []
        self.setter_count = 0
        self.initial_path = root/'original.SLDPRT'
        self.initial_path.write_bytes(b'original-native')
        self.document = self.doc(profile(1), self.initial_path)
        self.front = self.doc(profile(1), Path('foreground'))
        self.opened = [self.document, self.front]
        def same(a,b):
            if not all(any(obj is item for item in self.opened) for obj in (a,b)):
                raise RuntimeError('closed native handle must never be queried')
            return int(a is b)
        self.app = SimpleNamespace(ActiveDoc=self.front, GetDocuments=lambda:tuple(self.opened),
            GetDocumentCount=lambda:len(self.opened), IsSame=same, CloseDoc=self.close)
        self.case = {}
        self.cal = write.Calibration(app=self.app, document=self.document, front=self.front, case=self.case,
            output=root, suffix='SLDPRT', call=self.call, persist=self.persist, geometry=None, compare=None)

    def doc(self, snapshot, path, readonly=False):
        d = SimpleNamespace(snapshot=deepcopy(snapshot), path=path, modified=False, readonly=readonly)
        d.GetType=lambda:d.snapshot['document_type'];d.GetSaveFlag=lambda:d.modified
        d.GetUpdateStamp=lambda:7;d.GetActiveConfiguration=lambda:SimpleNamespace(Name='Default')
        d.GetTitle=lambda:str(d.path.name);d.GetPathName=lambda:str(d.path)
        d.IsOpenedReadOnly=lambda:d.readonly
        return d

    def call(self, name, function):
        self.calls.append(name);return function()

    def persist(self):self.checkpoints.append(deepcopy(self.case))

    def close(self, title):
        self.opened.remove(next(d for d in self.opened if d.GetTitle() == title))
        self.app.ActiveDoc=self.opened[-1] if self.opened else None

    def read(self, *, app, document):return dict(ok=True, unit_profile=deepcopy(document.snapshot))

    def edit(self, app=None, document=None, field=None, value=None, expected_snapshot=None):
        if document.readonly:return dict(ok=False, mutation=dict(attempted=False, may_have_changed=False), error=dict(type='ValueError'))
        self.setter_count += 1
        checkpoint=self.checkpoints[-1]['write_steps'][-1]
        assert checkpoint['before']==document.snapshot and 'result' not in checkpoint
        assert (self.root/checkpoint['source_file']).read_bytes()==b'original-native'
        before=deepcopy(document.snapshot)
        if self.defect=='false':return dict(ok=False, native_return_value=False, mutation=dict(attempted=True, may_have_changed=True), error=dict(type='RuntimeError', message='first native false'))
        document.snapshot['values'][field]=observe(field, target(field,value))
        if field=='linear.unit':document.snapshot['native_units']['length_unit']=target(field,value)
        document.modified=True
        return dict(ok=True, changed=True, before=before, unit_profile=deepcopy(document.snapshot), native_return_value=True, mutation=dict(attempted=True, may_have_changed=True))

    def save(self, path, *, document):
        path=Path(path);path.write_bytes(json.dumps(document.snapshot).encode())
        self.saved[str(path)]=deepcopy(document.snapshot);document.path=path;document.modified=False
        if self.defect=='source-overwrite':self.initial_path.write_bytes(b'overwritten')
        return dict(ok=True, save_errors=0, save_warnings=None)

    def reopen(self, path, *, app, read_only):
        self.document=self.doc(self.saved[path],Path(path),read_only)
        if self.defect=='readonly-drift' and read_only:self.document.snapshot['linkage']['swUnitsTimeUnits']+=1
        self.opened.append(self.document);app.ActiveDoc=self.document
        return dict(ok=True, api_errors=0, api_warnings=0),self.document

    def create(self, *, app):
        self.front=self.doc(profile(1),Path('next-foreground'));self.opened.append(self.front);app.ActiveDoc=self.front
        return dict(ok=True),self.front

    def execute(self):
        def private(app, document, field, value, expected):
            return self.edit(app,document,field,value,expected)
        with mock.patch.object(write.adapter,'read_document_unit_profile_windows',side_effect=self.read), \
             mock.patch.object(write.adapter,'_calibrate_unit_profile',side_effect=private), \
             mock.patch.object(write.adapter,'set_document_unit_profile_windows',side_effect=self.edit), \
             mock.patch.object(write,'save_as_native_windows',side_effect=self.save), \
             mock.patch.object(write,'open_windows_document_with_handle',side_effect=self.reopen), \
             mock.patch.object(write,'create_part_windows_with_handle',side_effect=self.create):
            self.cal.step('linear.unit','inch','scalar')


class WritePersistenceTests(unittest.TestCase):
    def test_changed_target_is_saved_reopened_and_sources_remain_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            native=NativeSimulation(Path(directory));native.execute()
            step=native.case['write_steps'][0]
            self.assertTrue(step['success'])
            self.assertEqual(step['before'],native.checkpoints[0]['write_steps'][0]['before'])
            self.assertEqual(step['readonly_profile'],step['after'])
            self.assertEqual(native.initial_path.read_bytes(),b'original-native')
            self.assertEqual(native.setter_count,1)
            self.assertLess(native.calls.index('private-single-unit-set'),native.calls.index('save-distinct-unit-target'))
            self.assertLess(native.calls.index('reopen_readonly'),native.calls.index('reopen_writable_for_next_case'))
            self.assertIsNot(native.cal.document,native.document if native.document is native.front else native.front)

    def test_first_native_false_preserved_without_save_reopen_retry_or_next_target(self):
        with tempfile.TemporaryDirectory() as directory:
            native=NativeSimulation(Path(directory),'false')
            with self.assertRaisesRegex(RuntimeError,'private changed write failed'):native.execute()
            step=native.checkpoints[-1]['write_steps'][0]
            self.assertIs(step['result']['native_return_value'],False)
            self.assertEqual(step['result']['error']['message'],'first native false')
            self.assertFalse(step['success'])
            self.assertEqual(native.setter_count,1)
            self.assertNotIn('save-distinct-unit-target',native.calls)
            self.assertNotIn('reopen_readonly',native.calls)

    def test_native_persistence_or_source_failure_stops_without_writable_reopen(self):
        for defect in ('readonly-drift','source-overwrite'):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                native=NativeSimulation(Path(directory),defect)
                with self.assertRaises(RuntimeError):native.execute()
                self.assertEqual(native.setter_count,1)
                self.assertNotIn('reopen_writable_for_next_case',native.calls)
                self.assertFalse(native.case['write_steps'][0]['success'])

    def test_failed_intent_checkpoint_prevents_set_and_save(self):
        with tempfile.TemporaryDirectory() as directory:
            native=NativeSimulation(Path(directory))
            def persist():
                if native.case['write_steps']:raise OSError('intent fsync failed')
            native.cal.persist=persist
            with self.assertRaisesRegex(OSError,'intent fsync failed'):native.execute()
            self.assertEqual(native.setter_count,0)
            self.assertNotIn('private-single-unit-set',native.calls)
            self.assertNotIn('save-distinct-unit-target',native.calls)

    def test_new_readback_and_target_hash_are_checkpointed_before_next_native_call(self):
        with tempfile.TemporaryDirectory() as directory:
            native=NativeSimulation(Path(directory));native.execute()
            saved=native.checkpoints
            self.assertTrue(any(s['write_steps'][-1].get('context_after') and 'save' not in s['write_steps'][-1] for s in saved))
            self.assertTrue(any('target_sha256' in s['write_steps'][-1] and 'readonly_profile' not in s['write_steps'][-1] for s in saved))
            self.assertTrue(any('readonly_profile' in s['write_steps'][-1] and 'readonly_refusal' not in s['write_steps'][-1] for s in saved))
