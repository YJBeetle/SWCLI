import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

import opening_phases as p
import test_file_forensics as f
import test_markingjig_control as existing


def stable(name, ino=1):
    path=copy.deepcopy(f.PYROW)
    path['st_ino']=ino
    path={k:v for k,v in path.items() if k not in ('st_atime_ns','st_reparse_tag')}
    held=dict(path,st_ctime_ns=44)
    return dict(path='/private/tmp/copy/'+name,size_bytes=len(f.DATA),sha256=f.SHA,
                path_before=path,handle_before=held,handle_after=copy.deepcopy(held),path_after=copy.deepcopy(path))


def frame_for(rows):
    raw={}
    for name,row in rows.items():
        rounds=[]
        for label in ('before-read','after-read'):
            native=copy.deepcopy(f.NATIVE)
            native['id_before']=native['id_after']=dict(VolumeSerialNumber=row['path_before']['st_dev'],
                FileId128_bytes_hex=row['path_before']['st_ino'].to_bytes(16,'little').hex())
            rounds.append(dict(label=label,python_path=dict(row['path_before'],st_atime_ns=11,st_reparse_tag=0),
                python_held=dict(row['handle_before'],st_atime_ns=11,st_reparse_tag=0),
                win32_held=native,win32_path_reopen=copy.deepcopy(native),physical_identity_proven=True,
                raw_python_cross_channel_differences={'st_ctime_ns':dict(path=row['path_before']['st_ctime_ns'],held=row['handle_before']['st_ctime_ns'])}))
        for snap in rounds:
            a,b=snap['python_path'],snap['python_held']
            snap['raw_python_cross_channel_differences']={k:dict(path=a[k],held=b[k]) for k in f.m.FIELDS if a[k]!=b[k]}
        raw[name]=rounds
    return dict(stable=copy.deepcopy(rows),raw=raw)


class Source:
    def __init__(self, rows):
        self.current=frame_for(rows)
        self.fail=None
    def capture(self, working, label, frame):
        frame.update(copy.deepcopy(self.current),label=label,complete=False)
        if self.fail:raise self.fail
        frame['complete']=True
    def transition(self, name=p.TOP):
        row=self.current['stable'][name]
        for channel in ('handle_before','handle_after'):row[channel]['st_ctime_ns']+=10
        for snap in self.current['raw'][name]:
            snap['python_held']['st_ctime_ns']+=10
            # Derived differences also retain the raw new values. They are deliberately
            # not used as a second independently sampled metadata field.
            a,b=snap['python_path'],snap['python_held']
            snap['raw_python_cross_channel_differences']={k:dict(path=a[k],held=b[k]) for k in f.m.FIELDS if a[k]!=b[k]}
            for channel in ('win32_held','win32_path_reopen'):snap[channel]['basic']['ChangeTime']+=10


class Working:
    def __init__(self):
        self.root=Path('/private/tmp/copy')
        self.before={p.TOP:stable(p.TOP),'Spirit_Level.SLDPRT':stable('Spirit_Level.SLDPRT',2)}
        self.files={name:dict(sha256=f.SHA,size_bytes=len(f.DATA)) for name in self.before}
    def snapshot(self):return copy.deepcopy(self.before)
    def unchanged(self):return self.snapshot()
    def external(self,path):return Path(path).name


MODEL=dict(complete=True,top=dict(type=2,readonly=True,modified=False,viewonly=False))


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.working=Working();self.source=Source(self.working.before);self.report={}
        self.guard=p.PhaseGuard(self.working,self.report,self.source.capture)
    def opened(self, transition=True):
        self.guard.before_open()
        if transition:self.source.transition()
        self.guard.after_open()
    def test_top_transition_raw_and_origin_retained_not_yet_admitted(self):
        origin=copy.deepcopy(self.working.before);self.opened()
        self.assertEqual(self.guard.record['opening_classification'],'opening-metadata-transition')
        self.assertEqual(self.guard.state,'opened-not-admitted')
        self.assertFalse(self.guard.record['loaded_baseline_sealed'])
        self.assertEqual(self.working.before,origin)
        self.assertEqual(len(self.guard.record['opening_changes']),10)
        self.assertFalse(self.guard.record['export_permitted'])
    def test_initial_equal_ctimes_can_become_split_without_rewriting_raw_fields(self):
        for channel in ('handle_before','handle_after'):
            self.working.before[p.TOP][channel]['st_ctime_ns']=self.working.before[p.TOP]['path_before']['st_ctime_ns']
        self.source=Source(self.working.before);self.guard=p.PhaseGuard(self.working,self.report,self.source.capture)
        self.opened()
        before=self.guard.before_open_frame['raw'][p.TOP][0]
        after=self.guard.opened_frame['raw'][p.TOP][0]
        self.assertEqual(before['raw_python_cross_channel_differences'],{})
        self.assertIn('st_ctime_ns',after['raw_python_cross_channel_differences'])
    def test_no_transition_still_requires_full_model_gate(self):
        self.opened(False)
        self.assertEqual(self.guard.record['opening_classification'],'opening-metadata-unchanged')
        with self.assertRaisesRegex(RuntimeError,'incomplete'):self.guard.seal_loaded(dict(complete=False))
        self.assertFalse(self.guard.record['loaded_baseline_sealed'])
    def test_only_complete_clean_readonly_full_model_can_seal(self):
        self.opened()
        for key,value in (('readonly',False),('modified',True),('viewonly',True),('type',1)):
            row=copy.deepcopy(MODEL);row['top'][key]=value
            with self.subTest(field=key),self.assertRaises(RuntimeError):self.guard.seal_loaded(row)
        self.guard.seal_loaded(MODEL)
        self.assertTrue(self.guard.record['loaded_baseline_sealed'])
        self.guard.unchanged();self.guard.postcheck()
        with self.assertRaisesRegex(RuntimeError,'resealed'):self.guard.seal_loaded(MODEL)
    def test_every_original_stable_field_other_than_top_held_ctime_fails(self):
        for name in self.working.before:
            for channel in ('path_before','path_after','handle_before','handle_after'):
                for key in self.working.before[name][channel]:
                    if name==p.TOP and channel.startswith('handle') and key=='st_ctime_ns':continue
                    with self.subTest(file=name,channel=channel,field=key):
                        self.setUp();self.guard.before_open()
                        self.source.current['stable'][name][channel][key]+=1
                        with self.assertRaises(RuntimeError):self.guard.after_open()
                        self.assertFalse(self.guard.record['loaded_baseline_sealed'])
    def test_non_top_even_matching_ctime_transition_fails(self):
        self.guard.before_open();self.source.transition('Spirit_Level.SLDPRT')
        with self.assertRaisesRegex(RuntimeError,'outside top'):self.guard.after_open()
    def test_content_and_identity_never_reset(self):
        for key,value in (('sha256','ff'*32),('size_bytes',99)):
            with self.subTest(key=key):
                self.setUp();self.guard.before_open();self.source.current['stable'][p.TOP][key]=value
                with self.assertRaisesRegex(RuntimeError,'content changed'):self.guard.after_open()
    def test_all_native_fields_and_raw_access_times_are_strict(self):
        fields=(('basic','CreationTime'),('basic','LastAccessTime'),('basic','LastWriteTime'),
                ('basic','FileAttributes'),('standard','AllocationSize'),('standard','EndOfFile'),
                ('standard','NumberOfLinks'),('standard','Directory'),('standard','DeletePending'))
        for name in self.working.before:
            for channel in ('win32_held','win32_path_reopen'):
                for group,key in fields:
                    with self.subTest(name=name,channel=channel,field=key):
                        self.setUp();self.guard.before_open()
                        self.source.current['raw'][name][0][channel][group][key]+=1
                        with self.assertRaisesRegex(RuntimeError,'outside top'):self.guard.after_open()
            for channel in ('python_path','python_held'):
                self.setUp();self.guard.before_open();self.source.current['raw'][name][0][channel]['st_atime_ns']+=1
                with self.assertRaises(RuntimeError):self.guard.after_open()
    def test_partial_transition_or_added_unknown_field_cannot_pass(self):
        self.guard.before_open();self.source.current['stable'][p.TOP]['handle_before']['st_ctime_ns']+=1
        with self.assertRaisesRegex(RuntimeError,'incomplete top'):self.guard.after_open()
        self.setUp();self.guard.before_open();self.source.current['raw'][p.TOP][0]['new_field']=123
        with self.assertRaisesRegex(RuntimeError,'schema changed'):self.guard.after_open()
    def test_full_id_high_bytes_and_opened_path_never_ignored(self):
        for key,value in (('opened_path','different raw path'),('id_after',dict(VolumeSerialNumber=42,FileId128_bytes_hex='01'*16))):
            with self.subTest(key=key):
                self.setUp();self.guard.before_open();self.source.current['raw'][p.TOP][0]['win32_held'][key]=value
                with self.assertRaises(RuntimeError):self.guard.after_open()
    def test_drift_during_gate_or_loaded_stage_cannot_rebaseline(self):
        self.opened();self.source.transition()
        with self.assertRaisesRegex(RuntimeError,'during complete admission'):self.guard.seal_loaded(MODEL)
        self.assertFalse(self.guard.record['loaded_baseline_sealed'])
        self.setUp();self.opened();self.guard.seal_loaded(MODEL);self.source.transition()
        with self.assertRaisesRegex(RuntimeError,'same-channel'):self.guard.unchanged()
        with self.assertRaisesRegex(RuntimeError,'same-channel'):self.guard.postcheck()
    def test_opening_and_loaded_seal_are_single_use(self):
        self.guard.before_open()
        with self.assertRaisesRegex(RuntimeError,'cannot repeat'):self.guard.before_open()
        with self.assertRaises(RuntimeError):self.guard.seal_loaded(MODEL)
    def test_partial_capture_is_retained_and_no_baseline_created(self):
        self.source.fail=OSError('original raw sample failed')
        with self.assertRaises(OSError):self.guard.before_open()
        frame=self.guard.record['frames'][0]
        self.assertFalse(frame['complete']);self.assertEqual(frame['phase_error']['type'],'OSError')
        self.assertFalse(self.guard.record['loaded_baseline_sealed'])
    def test_complete_three_channel_capture_reuses_existing_collector(self):
        w=Working();w.before={p.TOP:stable(p.TOP,f.PYROW['st_ino'])};w.files={p.TOP:dict(sha256=f.SHA,size_bytes=len(f.DATA))}
        backend=f.Fake();frame={}
        with mock.patch.object(p.forensic,'NativeBackend',return_value=backend):p.capture_frame(w,'test',frame)
        self.assertTrue(frame['complete'])
        self.assertEqual(frame['captures'][p.TOP]['hash']['sha256'],f.SHA)
        self.assertEqual(len(frame['raw'][p.TOP]),2)
        self.assertCountEqual(backend.closed,backend.opened)
    def test_loaded_stage_compares_every_existing_stable_field(self):
        for name in self.working.before:
            for channel in ('path_before','handle_before','handle_after','path_after'):
                for key in self.working.before[name][channel]:
                    with self.subTest(file=name,channel=channel,field=key):
                        self.setUp();self.opened();self.guard.seal_loaded(MODEL)
                        self.source.current['stable'][name][channel][key]+=1
                        with self.assertRaises(RuntimeError):self.guard.unchanged()
    def test_native_only_change_is_incomplete_transition(self):
        self.guard.before_open()
        for snapshot in self.source.current['raw'][p.TOP]:
            for channel in ('win32_held','win32_path_reopen'):snapshot[channel]['basic']['ChangeTime']+=1
        with self.assertRaisesRegex(RuntimeError,'incomplete top'):self.guard.after_open()
    def test_original_collector_unchanged_atime_failure_retains_raw_values(self):
        w=Working();w.before={p.TOP:stable(p.TOP,f.PYROW['st_ino'])};w.files={p.TOP:dict(sha256=f.SHA,size_bytes=len(f.DATA))}
        backend=f.Fake()
        backend.py_change=lambda row,channel:row.update(st_atime_ns=12) if backend.offset else None
        backend.native_change=lambda row,fd:row['basic'].update(LastAccessTime=999) if backend.offset else None
        frame={}
        with mock.patch.object(p.forensic,'NativeBackend',return_value=backend),self.assertRaisesRegex(RuntimeError,'raw capture failed'):
            p.capture_frame(w,'test',frame)
        self.assertFalse(frame['complete'])
        raw=frame['captures'][p.TOP]
        self.assertEqual(raw['snapshots'][1]['python_held']['st_atime_ns'],12)
        self.assertEqual(raw['snapshots'][1]['win32_held']['basic']['LastAccessTime'],999)
        self.assertCountEqual(backend.closed,backend.opened)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.case=existing.Case('test_probe_has_zero_save');self.case.setUp()
        self.source=Source(self.case.copy.before)
        self.guard=p.PhaseGuard(self.case.copy,self.case.report,self.source.capture)
        original=self.case.app.OpenDoc7
        def opening(spec):self.source.transition();return original(spec)
        self.case.app.OpenDoc7=opening
    def tearDown(self):self.case.tearDown()
    def run_case(self,mode='probe'):
        c=self.case
        existing.m.one_case(c.app,c.copy,mode,c.root/'new-output',existing.value,c.call,c.live,c.report,c.constants,
                            17,c.export,lambda pid:dict(created_filetime=123,exe_path='raw',exe_sha256='fixed'),phase_guard=self.guard)
    def test_zero_export_probe_seals_only_after_complete_gate_and_observes_again(self):
        original=copy.deepcopy(self.case.copy.before);self.run_case()
        self.assertEqual(len(self.case.opens),1);self.assertFalse(self.case.exports)
        self.assertEqual(self.case.report['export_attempts'],0);self.assertTrue(self.case.report['probe_success'])
        self.assertEqual(len(self.case.report['observations']),2)
        self.assertTrue(all(row['complete'] for row in self.case.report['observations']))
        self.assertEqual(self.case.copy.before,original);self.assertEqual(self.guard.state,'loaded')
    def test_invoke_is_rejected_before_open_and_export(self):
        with self.assertRaisesRegex(RuntimeError,'zero-export'):self.run_case('invoke')
        self.assertFalse(self.case.opens);self.assertFalse(self.case.exports)
    def test_failed_complete_model_gate_does_not_seal(self):
        self.case.top.modified=True
        with self.assertRaisesRegex(RuntimeError,'dirty'):self.run_case()
        self.assertFalse(self.guard.record['loaded_baseline_sealed']);self.assertFalse(self.case.exports)
    def test_unknown_warning_keeps_original_failure_and_no_loaded_baseline(self):
        self.case.spec.Warning=6
        with self.assertRaisesRegex(RuntimeError,'unexpected warning'):self.run_case()
        self.assertEqual(self.guard.state,'opened-not-admitted');self.assertFalse(self.guard.record['loaded_baseline_sealed'])
    def test_original_open_error_is_not_replaced_by_metadata_failure(self):
        def failed(spec):
            self.source.fail=OSError('secondary phase capture failure')
            raise ValueError('first native opening failure')
        self.case.app.OpenDoc7=failed
        with self.assertRaisesRegex(ValueError,'first native opening failure'):self.run_case()
        self.assertEqual(self.case.report['failed_open_phase_capture_error']['type'],'OSError')
        self.assertFalse(self.guard.record['loaded_baseline_sealed'])
    def test_open_error_return_captured_without_admission(self):
        self.case.spec.Error=1
        with self.assertRaisesRegex(RuntimeError,'OpenDoc7 failed'):self.run_case()
        self.assertEqual(len(self.guard.record['frames']),2);self.assertFalse(self.case.exports)
    def test_loaded_stage_ctime_drift_stops_zero_export(self):
        original=self.guard.seal_loaded
        def seal(model):original(model);self.source.transition()
        self.guard.seal_loaded=seal
        with self.assertRaisesRegex(RuntimeError,'same-channel metadata changed'):self.run_case()
        self.assertFalse(self.case.exports);self.assertNotIn('probe_success',self.case.report)
    def test_receipt_cannot_accept_unsealed_or_incomplete_phase_evidence(self):
        import json
        import tempfile
        spec=importlib.util.spec_from_file_location('phase_audit_test',Path(__file__).with_name('run-markingjig-control.py'))
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        phases=dict(state='loaded',loaded_baseline_sealed=True,raw_access_times_strict=True,
                    export_permitted=False,opening_classification='opening-metadata-transition',frames=[dict(complete=True)])
        case=dict(probe_success=True,export_attempts=0,phase_policy='opening-transition-probe',
                  observations=[dict(complete=True),dict(complete=True)],file_phases=phases)
        report=dict(success=True,cleanup_errors=[],cases=[case])
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);(out/'worker.stderr.log').write_text('')
            def check(value):
                (out/'report.json').write_text(json.dumps(value))
                return runner.audit(out,'probe','opening-transition-probe')['success']
            self.assertTrue(check(report))
            for mutate in (lambda r:r['cases'][0]['file_phases'].update(loaded_baseline_sealed=False),
                           lambda r:r['cases'][0]['observations'][1].update(complete=False),
                           lambda r:r['cases'][0]['file_phases']['frames'][0].update(complete=False),
                           lambda r:r['cases'][0]['file_phases'].update(raw_access_times_strict=False),
                           lambda r:r['cases'][0]['file_phases'].update(export_permitted=True)):
                altered=copy.deepcopy(report);mutate(altered);self.assertFalse(check(altered))
            (out/'worker.stderr.log').write_text(json.dumps(dict(event='swcli.native-call',phase='begin',call='IModelDocExtension.SaveAs3'))+'\n')
            self.assertFalse(check(report))
    def test_cli_new_policy_invoke_rejected_before_any_native_loader(self):
        spec=importlib.util.spec_from_file_location('phase_runner_test',Path(__file__).with_name('run-markingjig-control.py'))
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        args=['runner','--baseline','unused','--inventory','unused','--inventory-sha256','00'*32,
              '--copy-root','unused','--selected',p.TOP,'--output','unused','--mode','invoke',
              '--phase-policy','opening-transition-probe']
        with mock.patch.object(sys,'argv',args),mock.patch.object(runner,'pinned') as loader:
            with self.assertRaisesRegex(RuntimeError,'zero-export'):runner.main()
            loader.assert_not_called()


if __name__=='__main__':unittest.main()
