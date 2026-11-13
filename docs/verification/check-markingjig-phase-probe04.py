"""Offline only: package/import guards, stale/absent authority, exact-finally fault injection."""
import ast
import contextlib
import copy
import ctypes
import os
import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile

SHARE = Path('/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-a7ecb97-04')
SPEC = importlib.util.spec_from_file_location('probe04_review', SHARE/'launch-probe.py')
l = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(l)
CTX, INV = l.checked_package(SHARE)


class Preparation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.share = Path(self.tmp.name)/'package'; self.share.mkdir()
        # Only fixed preparation files enter a test fixture. Later native evidence
        # in SHARE must never be copied or mistaken for test execution receipts.
        for name in (*CTX['preparation_files_sha256'], 'proposal.json',
                     'markingjig-code-a7ecb97.zip', 'coordinator-cad-grant.example.json'):
            shutil.copy2(SHARE/name,self.share/name)
    def proposal(self, change):
        ctx = copy.deepcopy(CTX); change(ctx)
        (self.share/'proposal.json').write_text(json.dumps(ctx))
    def test_default_check_is_zero_native_and_writes_no_receipts(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(self.share/'launch-probe.py')], capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['native_operations'], 0)
        self.assertFalse((self.share/'launcher-context.json').exists())
        self.assertFalse((self.share/'entry-arrived.json').exists())
        self.assertFalse((self.share/'__pycache__').exists())
    def test_missing_helper_rejected(self):
        (self.share/'launcher_receipts.py').unlink()
        with self.assertRaises(FileNotFoundError): l.checked_package(self.share)
    def test_altered_standalone_helper_rejected(self):
        (self.share/'launcher_receipts.py').write_text('raise RuntimeError("injected")')
        with self.assertRaisesRegex(RuntimeError, 'preparation file differs'): l.checked_package(self.share)
    def test_altered_zip_hash_rejected(self):
        with (self.share/'markingjig-code-a7ecb97.zip').open('ab') as stream: stream.write(b'bad')
        with self.assertRaisesRegex(RuntimeError, 'ZIP differs'): l.checked_package(self.share)
    def test_duplicate_zip_member_rejected_even_with_new_zip_pin(self):
        path = self.share/'markingjig-code-a7ecb97.zip'
        with zipfile.ZipFile(path, 'a') as packed:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore'); packed.writestr(l.MEMBERS[0], b'# duplicate')
        self.proposal(lambda ctx: ctx.update(package_sha256=l.digest(path)))
        with self.assertRaisesRegex(RuntimeError, 'duplicate'): l.checked_package(self.share)
    def test_missing_packaged_receipts_rejected_even_with_updated_manifest(self):
        path = self.share/'markingjig-code-a7ecb97.zip'
        with zipfile.ZipFile(path) as old: data = {n:old.read(n) for n in old.namelist() if not n.endswith('/launcher_receipts.py')}
        path.unlink()
        with zipfile.ZipFile(path, 'w') as packed:
            for n, value in data.items(): packed.writestr(n, value)
        self.proposal(lambda ctx: (ctx.update(package_sha256=l.digest(path)), ctx['code_files_sha256'].pop(l.CONTROL+'launcher_receipts.py')))
        with self.assertRaisesRegex(RuntimeError, 'member list differs'): l.checked_package(self.share)
    def test_old_paths_rejected(self):
        self.proposal(lambda ctx: ctx.update(guest_base='C:\\Workspace\\old-attempt'))
        with self.assertRaisesRegex(RuntimeError, 'fresh layout differs'): l.checked_package(self.share)
    def test_invoke_rejected(self):
        self.proposal(lambda ctx: ctx.update(mode='invoke'))
        with self.assertRaisesRegex(RuntimeError, 'zero-export'): l.checked_package(self.share)
    def test_proposal_cannot_authorize_cad(self):
        self.proposal(lambda ctx: ctx.update(authorized_for_CAD=True))
        with self.assertRaisesRegex(RuntimeError, 'proposal identity'): l.checked_package(self.share)
    def test_execute_without_grant_records_entry_then_rejects_before_native(self):
        arrived=[]
        with mock.patch.object(l,'__file__',str(self.share/'launch-probe.py')), \
             mock.patch.object(l,'write_entry_arrival',lambda share:arrived.append(share)):
            with self.assertRaises(FileNotFoundError): l.main(['--execute'])
        self.assertEqual(arrived,[self.share.resolve()])
        self.assertFalse((self.share/'native-launch-started.json').exists())
        self.assertFalse((self.share/'launcher-context.partial.json').exists())
    def test_example_is_not_a_grant(self):
        grant = json.loads((self.share/'coordinator-cad-grant.example.json').read_text())
        with self.assertRaisesRegex(RuntimeError, 'CAD grant required'): l.checked_grant(self.share, CTX, grant)
    def test_grant_expiry_and_source_binding(self):
        time = dt.datetime(2026,11,13,10,tzinfo=dt.timezone.utc)
        grant = dict(schema='swcli.markingjig-cad-grant.v1', authorized_for_CAD=True,
                     allocation_id='VM-20261113-MARKINGJIG-PHASE-PROBE-04', reviewer_thread_id='01a0bfca-5e87-7e61-ab5f-0ef249443bab',
                     proposal_sha256=l.digest(self.share/'proposal.json'), launcher_sha256=l.digest(self.share/'launch-probe.py'),
                     package_sha256=CTX['package_sha256'], launcher_receipts_sha256=l.HELPER_SHA,
                     mode='probe',phase_policy='opening-transition-probe',component_context_policy=l.COMPONENT_POLICY,export_permitted=False,
                     issued_utc=(time-dt.timedelta(minutes=20)).isoformat(), expires_utc=time.isoformat())
        with self.assertRaisesRegex(RuntimeError, 'not fresh'): l.checked_grant(self.share, CTX, grant, time)
        grant['proposal_sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError, 'does not bind'): l.checked_grant(self.share, CTX, grant, time)
    def fresh_fixture_grant(self):
        time=dt.datetime(2026,11,13,10,tzinfo=dt.timezone.utc)
        proof=dict(success=True,phase='before',errors=[],finished_utc=time.isoformat(),
                   proposal_sha256=l.digest(self.share/'proposal.json'),
                   files={name:{'synthetic_test_only':True} for name in [*CTX['selected'],'MarkingJig.REND.GLB']})
        path=self.share/'host-originals-before.json';path.write_text(json.dumps(proof))
        grant=dict(schema='swcli.markingjig-cad-grant.v1',authorized_for_CAD=True,
                   allocation_id='VM-20261113-MARKINGJIG-PHASE-PROBE-04',
                   reviewer_thread_id='01a0bfca-5e87-7e61-ab5f-0ef249443bab',
                   proposal_sha256=l.digest(self.share/'proposal.json'),launcher_sha256=l.digest(self.share/'launch-probe.py'),
                   package_sha256=CTX['package_sha256'],launcher_receipts_sha256=l.HELPER_SHA,
                   mode='probe',phase_policy='opening-transition-probe',component_context_policy=l.COMPONENT_POLICY,export_permitted=False,
                   issued_utc=time.isoformat(),expires_utc=(time+dt.timedelta(seconds=60)).isoformat(),
                   expected_session_id=1,expected_user='synthetic-test-only',expected_sid='S-1-5-21-1',
                   root_idle_confirmed=True,host_originals_before_sha256=l.digest(path))
        return time,grant
    def test_proposal_component_policy_is_mandatory_and_exact(self):
        for value in (None,'strict-model-configuration','invoke',False):
            with self.subTest(value=value):
                self.proposal(lambda ctx:ctx.update(component_context_policy=value))
                with self.assertRaisesRegex(RuntimeError,'zero-export component phase'):l.checked_package(self.share)
    def test_fresh_synthetic_grant_binds_all_three_policies_without_native_entry(self):
        time,grant=self.fresh_fixture_grant()
        proof=l.checked_grant(self.share,CTX,grant,time)
        self.assertEqual(len(proof['files']),11)
        self.assertFalse((self.share/'entry-arrived.json').exists())
        self.assertFalse((self.share/'native-launch-started.json').exists())
    def test_grant_cannot_omit_component_policy_or_authorize_invoke(self):
        time,base=self.fresh_fixture_grant()
        for field,value in (('component_context_policy',None),('component_context_policy','strict-model-configuration'),
                            ('mode','invoke'),('phase_policy','strict'),('export_permitted',True)):
            with self.subTest(field=field,value=value):
                grant=copy.deepcopy(base)
                if value is None:grant.pop(field)
                else:grant[field]=value
                with self.assertRaisesRegex(RuntimeError,'grant zero-export component policy'):l.checked_grant(self.share,CTX,grant,time)
        self.assertFalse((self.share/'native-launch-started.json').exists())
    def test_exact_candidate_argv_contains_zero_export_component_policy_once(self):
        tree=ast.parse((self.share/'launch-probe.py').read_bytes())
        execute=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        candidates=[n for n in ast.walk(execute) if isinstance(n,ast.Assign) and
                    any(isinstance(t,ast.Name) and t.id=='argv' for t in n.targets) and isinstance(n.value,ast.List) and
                    any(isinstance(v,ast.Constant) and v.value=='--component-context-policy' for v in n.value.elts)]
        self.assertEqual(len(candidates),1)
        node=candidates[0]
        env=dict(sys=types.SimpleNamespace(executable=l.PYTHON),code=self.share/'code',inputs=self.share/'input',
                 output=self.share/'output',baseline=Path(l.DRIVER),CONTROL=l.CONTROL,INVENTORY=l.INVENTORY,
                 INVENTORY_SHA=l.INVENTORY_SHA,COMPONENT_POLICY=l.COMPONENT_POLICY)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'exact-candidate-argv','exec'),env)
        argv=env['argv']
        for flag,value in (('--mode','probe'),('--phase-policy','opening-transition-probe'),
                           ('--component-context-policy','component-bodies-probe')):
            self.assertEqual(argv.count(flag),1);self.assertEqual(argv[argv.index(flag)+1],value)
        self.assertNotIn('invoke',argv)

    def test_runtime_imports_resolve_to_payload_without_native_initialization(self):
        unpack = self.share/'import-check'; unpack.mkdir()
        with zipfile.ZipFile(self.share/'markingjig-code-a7ecb97.zip') as packed: packed.extractall(unpack)
        snippet = '''import sys,json,importlib.util,hashlib
from pathlib import Path
root=Path(sys.argv[1]);folder=root/'scripts/diagnostics/markingjig'
sys.path.insert(0,str(folder))
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
runner=module(folder/'run-markingjig-control.py','probe_import_only')
import file_forensics,opening_phases,launcher_receipts
assert Path(runner.receipts.__file__).resolve()==(folder/'launcher_receipts.py').resolve()
assert hashlib.sha256(Path(runner.receipts.__file__).read_bytes()).hexdigest()==sys.argv[2]
module(root/'scripts/diagnostics/typed_glb/run-typed-glb-control.py','typed_import_only')
assert not any(n.startswith(('pythoncom','win32com','swcli.')) for n in sys.modules)
print(json.dumps({'runtime_modules_imported':6,'packaged_receipts_resolved':True,'native_backend_initializations':0}))
'''
        result = subprocess.run([sys.executable,'-I','-B','-c',snippet,str(unpack),l.HELPER_SHA],capture_output=True,check=True)
        self.assertTrue(json.loads(result.stdout)['packaged_receipts_resolved'])
    def test_launcher_own_session_query_preserves_raw_success_and_failures(self):
        tree=ast.parse((self.share/'launch-probe.py').read_bytes())
        body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        body=next(n for n in body.body if isinstance(n,ast.Try)).body
        start=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='kernel')
        end=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Subscript) and isinstance(n.targets[0].slice,ast.Constant) and n.targets[0].slice.value=='native_pids_before')
        snippet=compile(ast.Module(body=body[start:end],type_ignores=[]),'actual-session-preflight','exec')
        class Query:
            def __init__(self,ok,value): self.ok,self.value=ok,value
            def __call__(self,pid,pointer):
                ctypes.cast(pointer,ctypes.POINTER(ctypes.c_ulong))[0]=self.value
                return self.ok
        for ok,value,error in ((1,1,0),(1,0,0),(0,0,87)):
            with self.subTest(ok=ok,session=value):
                query=Query(ok,value)
                fake=types.SimpleNamespace(WinDLL=lambda *a,**k:types.SimpleNamespace(ProcessIdToSessionId=query),
                                           c_ulong=ctypes.c_ulong,c_int=ctypes.c_int,POINTER=ctypes.POINTER,
                                           byref=ctypes.byref,set_last_error=lambda n:None,get_last_error=lambda:error)
                record={};namespace=dict(ctypes=fake,os=os,record=record,grant={'expected_session_id':1},save=lambda:None,require=l.require)
                if ok and value==1: exec(snippet,namespace)
                else:
                    with self.assertRaisesRegex(RuntimeError,'actual launcher SessionId'): exec(snippet,namespace)
                self.assertEqual(record['launcher_session_query'],dict(pid=os.getpid(),ok=bool(ok),last_error=error,session=value if ok else None))
                self.assertEqual(query.restype,ctypes.c_int)

    def test_entry_marker_precedes_even_proposal_read_failure(self):
        calls=[]
        def bad_package(share): calls.append('proposal'); raise OSError('injected proposal read failure')
        with mock.patch.object(l,'write_entry_arrival',lambda share:calls.append('entry')), \
             mock.patch.object(l,'checked_package',bad_package):
            with self.assertRaisesRegex(OSError,'injected proposal'): l.main(['--execute'])
        self.assertEqual(calls,['entry','proposal'])
    def test_entry_raw_session_failure_and_exclusive_marker(self):
        class Query:
            def __call__(self,pid,pointer): return 0
        query=Query()
        fake=types.SimpleNamespace(WinDLL=lambda *a,**k:types.SimpleNamespace(ProcessIdToSessionId=query),
             c_ulong=ctypes.c_ulong,c_int=ctypes.c_int,POINTER=ctypes.POINTER,byref=ctypes.byref,
             set_last_error=lambda n:None,get_last_error=lambda:87)
        with mock.patch.object(l.sys,'platform','win32'), mock.patch.object(l,'ctypes',fake), \
             mock.patch.object(l.sys,'argv',[str(self.share/'launch-probe.py'),'--execute']):
            l.write_entry_arrival(self.share)
            original=(self.share/'entry-arrived.json').read_bytes()
            row=json.loads(original)
            self.assertEqual(row['pid'],os.getpid())
            self.assertEqual(row['session_query'],dict(ok=False,last_error=87,session=None))
            self.assertEqual(row['argv'],[str(self.share/'launch-probe.py'),'--execute'])
            self.assertEqual(row['entry_source_sha256'],l.digest(SHARE/'launch-probe.py'))
            with self.assertRaises(FileExistsError): l.write_entry_arrival(self.share)
            self.assertEqual((self.share/'entry-arrived.json').read_bytes(),original)
    def test_entry_marker_retains_query_api_exception_without_grant_or_cad(self):
        def bad_kernel(*args,**kwargs): raise OSError('injected OS API error')
        with mock.patch.object(l.sys,'platform','win32'), \
             mock.patch.object(l,'ctypes',types.SimpleNamespace(WinDLL=bad_kernel)):
            l.write_entry_arrival(self.share)
        row=json.loads((self.share/'entry-arrived.json').read_bytes())
        self.assertEqual(row['session_query'],dict(ok=False,type='OSError',error='injected OS API error'))
        self.assertFalse((self.share/'native-launch-started.json').exists())

    def test_full_launcher_finally_preserves_empty_case_first_failure_and_all_hashes(self):
        code, inputs, output = self.share/'code', self.share/'input', self.share/'output'
        code.mkdir(); inputs.mkdir(); output.mkdir()
        with zipfile.ZipFile(self.share/'markingjig-code-a7ecb97.zip') as packed: packed.extractall(code)
        copies=[]
        for name in CTX['selected']:
            path=inputs/name; path.write_bytes(b'fake input solely in test temp')
            copies.append(dict(name=name,destination=str(path),sha256=l.digest(path),size_bytes=path.stat().st_size))
        fatal=dict(type='com_error',message='original Server execution failed',hresult=-2146959355)
        (output/'report.json').write_text(json.dumps(dict(success=False,cases=[],failure=fatal,cleanup_errors=[])))
        record=dict(candidate_launch_attempts=1,candidate_exit=1,copies=copies,first_error=None,cleanup_errors=[])
        receipts=l.load_module(self.share/'launcher_receipts.py','test_receipts_exact')
        def bad_capture(*args): raise OSError('injected raw capture failure')
        phases=types.SimpleNamespace(capture_frame=bad_capture)
        tree=ast.parse((self.share/'launch-probe.py').read_bytes())
        execute=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        final=next(n for n in execute.body if isinstance(n,ast.Try)).finalbody
        namespace=dict(record=record,ctx=CTX,code=code,inputs=inputs,output=output,share=self.share,
                       receipts=receipts,working=object(),phases=phases,digest=l.digest,require=l.require,
                       context=lambda label:[],save=lambda *args:None,shutil=shutil,now=l.now,json=json)
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(ast.Module(body=final,type_ignores=[]),'exact-new-launcher-finally','exec'),namespace)
        self.assertEqual(record['primary_failure'],fatal)
        self.assertIsNone(record['first_error'])
        self.assertEqual(record['native_report_case_count'],0)
        self.assertEqual(record['code_hashes_after'],CTX['code_files_sha256'])
        self.assertTrue(record['copy_hash_postcheck_complete'])
        self.assertTrue(record['preparation_source_postcheck']['code_hash_postcheck_complete'])
        self.assertEqual(record['native_pids_after_postcleanup_OS'],[])
        self.assertEqual([e['stage'] for e in record['secondary_errors']],
                         ['OS-post-candidate-input-capture','OS-post-candidate-input-comparison'])
        self.assertFalse(receipts.launcher_success(record))
        self.assertTrue((self.share/'native-output/report.json').exists())


if __name__ == '__main__': unittest.main(verbosity=2)
