import ast
import copy
import datetime
import io
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest import mock

import launcher_receipts as receipts
import opening_phases as phases
from test_opening_phases import Source,Working

FAILURE=dict(type='com_error',message="(-2146959355, 'Server execution failed', None, None)",traceback='original acquire-owned-host traceback')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.code=self.root/'code';self.code.mkdir();self.inputs=self.root/'inputs';self.inputs.mkdir()
        self.copies=[];self.expected={}
        for name in ('first','second'):
            p=self.inputs/name;p.write_bytes(('source-'+name).encode());self.copies.append(dict(name=name,destination=str(p),sha256=digest(p),size_bytes=p.stat().st_size))
            q=self.code/(name+'.py');q.write_text('# fixed '+name);self.expected[q.name]=digest(q)
        self.path=self.root/'report.json';self.native=dict(success=False,cases=[],cleanup_errors=[],failure=copy.deepcopy(FAILURE))
        self.path.write_text(json.dumps(self.native))
        working=Working();pre=Source(working.before).current
        pre.update(label='pre-CAD',complete=True,access_time_policy='record-only')
        self.post=copy.deepcopy(pre);self.post['label']='after-worker-return'
        self.record=dict(first_error=None,cleanup_errors=[],copies=self.copies,private_source_before=working.before,
                         private_source_pre_CAD_frame=pre,candidate_exit=1)
        self.observed=[];self.context={}
    def read(self):self.observed.append('report');self.context['report']=receipts.read_native_report(self.record,self.path)
    def capture(self):self.observed.append('capture');self.record['private_source_after_owned_cleanup_frame']=copy.deepcopy(self.post)
    def compare(self):self.observed.append('compare');receipts.compare_post_inputs(self.record,self.context.get('report'),phases)
    def inputs_hash(self):self.observed.append('inputs');receipts.input_hash_postcheck(self.record,['first','second'],digest)
    def code_hash(self):self.observed.append('code');receipts.code_hash_postcheck(self.record,self.code,self.expected,digest)
    def jobs(self):
        return [('read-native-report',self.read),('capture-inputs',self.capture),('compare-inputs',self.compare),
                ('input-hash',self.inputs_hash),('code-hash',self.code_hash),('copy-original-evidence',lambda:self.observed.append('evidence'))]
    def test_acquire_failure_empty_case_retains_fatal_and_checks_real_files(self):
        original=self.path.read_bytes();self.assertTrue(receipts.postchecks(self.record,self.jobs()))
        self.assertEqual(self.record['primary_failure'],FAILURE);self.assertIsNone(self.record['first_error'])
        self.assertEqual(self.observed,['report','capture','compare','inputs','code','evidence'])
        self.assertEqual(self.record['code_hashes_after'],self.expected)
        self.assertTrue(self.record['copy_hash_postcheck_complete']);self.assertTrue(self.record['private_source_postcleanup_proof_complete'])
        self.assertEqual(self.record['postcleanup_comparison_baseline_label'],'pre-CAD')
        self.assertEqual(self.path.read_bytes(),original);self.assertEqual(self.native['cases'],[])
        self.assertNotIn('normal_SW_exit_proven',self.record);self.assertEqual(self.record['candidate_exit'],1);self.assertFalse(receipts.launcher_success(self.record))
    def test_compare_failure_cannot_skip_input_or_code_hash_or_replace_fatal(self):
        self.post['stable'][phases.TOP]['handle_after']['st_ctime_ns']+=1
        self.assertFalse(receipts.postchecks(self.record,self.jobs()))
        self.assertEqual(self.record['primary_failure'],FAILURE)
        self.assertEqual([e['stage'] for e in self.record['secondary_errors']],['compare-inputs'])
        self.assertTrue(self.record['copy_hash_postcheck_complete']);self.assertTrue(self.record['code_hash_postcheck_complete'])
        self.assertEqual(self.observed[-3:],['inputs','code','evidence'])
    def test_capture_and_report_read_failure_still_run_all_hash_checks(self):
        self.path.write_text('{invalid')
        def capture():self.observed.append('capture');self.record['partial_raw']={'one':'retained'};raise OSError('raw capture unavailable')
        jobs=self.jobs();jobs[1]=('capture-inputs',capture)
        self.assertFalse(receipts.postchecks(self.record,jobs))
        self.assertEqual(self.observed,['report','capture','compare','inputs','code','evidence'])
        self.assertIsNone(self.record['primary_failure']);self.assertEqual(self.record['partial_raw'],{'one':'retained'})
        self.assertTrue(self.record['copy_hash_postcheck_complete']);self.assertTrue(self.record['code_hash_postcheck_complete'])
        self.assertNotIn('candidate_failure',self.record)
    def test_each_input_and_code_file_is_attempted_after_one_read_fails(self):
        calls=[]
        def read(path):
            calls.append(path.name)
            if path.name in ('first','first.py'):raise OSError('injected inaccessible file')
            return digest(path)
        self.inputs_hash=lambda:receipts.input_hash_postcheck(self.record,['first','second'],read)
        self.code_hash=lambda:receipts.code_hash_postcheck(self.record,self.code,self.expected,read)
        self.assertFalse(receipts.postchecks(self.record,self.jobs()))
        self.assertEqual(calls,['first','second','first.py','second.py'])
        self.assertIn('second',self.record['copy_hashes_after']);self.assertIn('second.py',self.record['code_hashes_after'])
        self.assertFalse(self.record['copy_hash_postcheck_complete']);self.assertFalse(self.record['code_hash_postcheck_complete'])
        self.assertEqual(self.record['primary_failure'],FAILURE)
    def test_hash_mismatch_retains_actual_hashes_and_keeps_failure_separate(self):
        (self.inputs/'first').write_bytes(b'changed');(self.code/'first.py').write_text('# changed')
        self.assertFalse(receipts.postchecks(self.record,self.jobs()))
        self.assertEqual(self.record['copy_hash_mismatches'],['first']);self.assertEqual(self.record['code_hash_mismatches'],['first.py'])
        self.assertEqual(self.record['code_hashes_after']['first.py'],digest(self.code/'first.py'))
        self.assertEqual(self.record['primary_failure'],FAILURE)
    def test_persist_failure_does_not_skip_remaining_jobs(self):
        attempts=[]
        def persist(row):attempts.append(len(attempts));raise OSError('evidence disk unavailable')
        self.assertFalse(receipts.postchecks(self.record,self.jobs(),persist))
        self.assertEqual(len(attempts),6);self.assertEqual(self.observed[-1],'evidence')
        self.assertTrue(self.record['code_hash_postcheck_complete']);self.assertEqual(self.record['primary_failure'],FAILURE)
    def test_original_launcher_exception_retained_when_child_report_absent(self):
        self.path.unlink();self.record['first_error']=dict(type='TimeoutExpired',message='original launcher failure')
        receipts.postchecks(self.record,self.jobs())
        self.assertFalse(self.record['native_report_available'])
        self.assertEqual(self.record['primary_failure'],self.record['first_error'])
        self.assertNotIn('candidate_failure',self.record)
        self.assertTrue(self.record['code_hash_postcheck_complete'])
    def test_empty_case_cannot_become_success_even_with_contradictory_exit_zero(self):
        self.record['candidate_exit']=0;self.native['success']=True;self.native.pop('failure')
        self.path.write_text(json.dumps(self.native));receipts.postchecks(self.record,self.jobs())
        self.record.update(native_pids_after=[],native_pids_after_postcleanup_OS=[])
        self.assertEqual(self.record['native_report_case_count'],0)
        self.assertFalse(receipts.launcher_success(self.record));self.assertEqual(self.native['cases'],[])
    def test_actual_private_launcher_finally_handles_empty_acquire_case_and_comparison_failure(self):
        # Execute only the reviewed finally AST against temporary files and fake OS
        # callbacks. The original launch/preflight/CAD body is never executed.
        path=Path(__file__).resolve().parents[3]/'docs/verification/markingjig-private-launcher-review.py.txt'
        tree=ast.parse(path.read_text())
        final=next(n.finalbody for n in tree.body if isinstance(n,ast.Try) and n.finalbody)
        code=compile(ast.fix_missing_locations(ast.Module(body=final,type_ignores=[])),str(path),'exec')
        for drift in (False,True):
            with self.subTest(drift=drift):
                share=self.root/('share-drift' if drift else 'share-clean');share.mkdir()
                record=copy.deepcopy(self.record);record['candidate_launch_attempts']=1;post=copy.deepcopy(self.post)
                if drift:post['stable'][phases.TOP]['handle_after']['st_ctime_ns']+=1
                def capture(working,label,frame):frame.update(copy.deepcopy(post),label=label)
                fake=type('OSPhaseCallbacks',(),dict(capture_frame=staticmethod(capture),changes=staticmethod(phases.changes),PhaseGuard=phases.PhaseGuard))
                helper=Path(receipts.__file__)
                cfg=dict(selected=['first','second'],code_files_sha256=self.expected,launcher_receipts_sha256=digest(helper))
                def require(ok,message):
                    if not ok:raise RuntimeError(message)
                env=dict(record=record,receipts=receipts,output=self.root,share=share,inputs=self.inputs,code=self.code,
                         copy=object(),phases=fake,ctx=cfg,digest=digest,receipt_helper_path=helper,require=require,
                         inventory=lambda:[],save=lambda:None,datetime=datetime,json=json,shutil=shutil)
                # Keep evidence copy outside the source directory to avoid recursion.
                evidence=[];env['shutil']=type('EvidenceCopy',(),dict(copytree=staticmethod(lambda a,b:evidence.append((a,b)))))
                with mock.patch('sys.stdout',new=io.StringIO()):exec(code,env)
                saved=json.loads((share/'launcher-context.json').read_text())
                self.assertEqual(saved['primary_failure'],FAILURE);self.assertEqual(saved['candidate_exit'],1)
                self.assertEqual(saved['code_hashes_after'],self.expected)
                self.assertTrue(saved['copy_hash_postcheck_complete']);self.assertEqual(len(evidence),1)
                self.assertEqual(saved['launcher_receipts_sha256_after'],digest(helper))
                self.assertEqual(saved['native_report_case_count'],0)
                self.assertEqual(bool(saved['secondary_errors']),drift)
                self.assertFalse(receipts.launcher_success(saved))
    def test_no_working_copy_does_not_fabricate_raw_proof(self):
        record={}
        with self.assertRaisesRegex(RuntimeError,'not prepared'):receipts.capture_post_inputs(record,None,phases)
        self.assertNotIn('private_source_after_owned_cleanup_frame',record)
    def test_no_case_is_not_synthesized_and_bad_shape_still_rejected(self):
        self.assertIsNone(receipts.single_case(self.native));self.assertEqual(self.native['cases'],[])
        for value in (None,{},[{},{}],['bad']):
            with self.subTest(value=value),self.assertRaises(RuntimeError):receipts.single_case(dict(cases=value))
    def test_no_expected_code_or_sources_cannot_claim_hash_proof(self):
        with self.assertRaises(RuntimeError):receipts.code_hash_postcheck(self.record,self.code,{},digest)
        with self.assertRaises(RuntimeError):receipts.input_hash_postcheck(dict(copies=[]),[],digest)


class SupervisorAuditTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('receipt_supervisor',Path(__file__).with_name('run-markingjig-control.py'))
        self.runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.runner)
    def test_empty_acquire_report_returns_failed_audit_with_original_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);data=json.dumps(dict(success=False,cases=[],cleanup_errors=[],failure=FAILURE)).encode()
            (out/'report.json').write_bytes(data);(out/'worker.stderr.log').write_text('')
            for mode in ('probe','invoke'):
                for policy in ('strict','opening-transition-probe'):
                    row=self.runner.audit(out,mode,policy)
                    self.assertFalse(row['success']);self.assertEqual(row['case_count'],0)
                    self.assertEqual(row['native_failure'],FAILURE);self.assertEqual(row['modern_save_attempts'],0)
            self.assertEqual((out/'report.json').read_bytes(),data)
    def test_claimed_success_without_case_still_fails_and_no_fake_success_case(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);(out/'report.json').write_text(json.dumps(dict(success=True,cases=[],cleanup_errors=[])))
            (out/'worker.stderr.log').write_text('')
            row=self.runner.audit(out,'invoke');self.assertFalse(row['success']);self.assertEqual(row['case_count'],0)
