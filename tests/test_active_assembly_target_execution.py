"""Private adapter boundaries only: no native imports, COM or CAD processes."""
import gc
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest import mock
import weakref
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('census_execution',ROOT/'scripts/diagnostics/run-active-assembly-target-census.py')
execution=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(execution)


class Process:
    pid=42
    _handle=object()
    def __init__(self):self.returncode=None;self.terminate=mock.Mock(side_effect=self.stop);self.wait=mock.Mock(side_effect=self.waiting)
    def poll(self):return self.returncode
    def stop(self):self.returncode=124
    def waiting(self,timeout):
        if self.returncode is None:raise subprocess.TimeoutExpired('owned Python',timeout)
        return self.returncode


class App:
    class Proxy:
        def __init__(self,**facts):self.__dict__.update(facts)
    def __init__(self,warning=0):
        self.warning=warning;self.references={};self.open_paths=[];self.active=None
        self.ActivateDoc3=mock.Mock(side_effect=AssertionError('no activation'))
    def GetOpenDocSpec(self,path):return NS(path=path,Error=0,Warning=self.warning)
    def OpenDoc7(self,spec):
        self.open_paths.append(spec.path)
        document=self.Proxy(token=spec.DocumentType,GetType=spec.DocumentType,GetPathName=spec.path,
            GetSaveFlag=False,IsOpenedReadOnly=True,IsOpenedViewOnly=False)
        self.references[spec.DocumentType]=weakref.ref(document);self.active=spec.DocumentType
        return document
    @property
    def ActiveDoc(self):return self.Proxy(token=self.active)
    def IsSame(self,a,b):return int(a.token==b.token)


class ExecutionTests(unittest.TestCase):
    def options(self,root):
        path=root/'source.json';path.write_text('{}')
        return NS(ticket='offline',run_root=root/'run',artifact_dir=root/'artifact',source_manifest=path,source_manifest_sha='known',
            internal_zip=root/'internal.zip',public_zip=root/'public.zip',host_executable=root/'SLDWORKS.exe',host_type_library=root/'sldworks.tlb',
            expected_host_image=root/'SLDWORKS.exe',group_started=0.)

    def backend(self,app,code=0):
        backend=NS(app=app,pid=7,initialized=True,ownership_verified=True,thread_id=threading.get_ident(),identity_observations=[])
        backend.initialize=mock.Mock();backend.acquire=mock.Mock(return_value=dict(process_id=7));backend.identity=mock.Mock(return_value='running')
        def cleanup(journal,state,uncertain,deadline,clock):
            self.assertTrue(all(ref() is not None for ref in app.references.values()))
            state.update(host_exit_confirmed=code is not None,host_exit_code=code)
        backend.cleanup=mock.Mock(side_effect=cleanup)
        def release():
            gc.collect();self.assertTrue(all(ref() is None for ref in app.references.values()))
        backend.release=mock.Mock(side_effect=release)
        return backend

    def parent_patches(self,app,read):
        return (mock.patch.object(execution,'prepare_copies',return_value={}),
                mock.patch.object(execution.reader,'verify_files',return_value={}),
                mock.patch.object(execution.reader,'preflight',side_effect=lambda *args:app.references[2]()),
                mock.patch.object(execution.reader,'run',side_effect=read))

    def test_parent_same_sta_natural_order_lifecycle_and_strict_exit(self):
        for code in (0,False,1,None):
            with self.subTest(code=repr(code)),tempfile.TemporaryDirectory() as temporary:
                options=self.options(Path(temporary));options.run_root.mkdir();app=App();backend=self.backend(app,code)
                def read(actual,args,report):
                    self.assertIs(actual,app);self.assertEqual(args.expected_pid,7)
                    self.assertTrue(all(ref() is not None for ref in app.references.values()));report['success']=True
                patches=self.parent_patches(app,read)
                with patches[0],patches[1],patches[2],patches[3] as observe:
                    self.assertEqual(execution.parent(options,backend,clock=lambda:1),0 if type(code) is int and code==0 else 1)
                self.assertEqual([Path(path).suffix for path in app.open_paths],['.SLDPRT','.SLDASM'])
                observe.assert_called_once();backend.cleanup.assert_called_once();backend.release.assert_called_once();app.ActivateDoc3.assert_not_called()

    def test_owner_failure_and_report_io_secondary_keep_first_no_business_postflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));options.run_root.mkdir();app=App();backend=self.backend(app)
            first=ValueError('original native owner error')
            def read(*args):raise first
            original=execution.atomic_json
            def persist(path,value):
                if path.name=='observer-report.json':raise OSError('secondary observer report error')
                return original(path,value)
            patches=self.parent_patches(app,read)
            with patches[0],patches[1],patches[2] as preflight,patches[3] as observe,mock.patch.object(execution,'atomic_json',side_effect=persist),mock.patch('sys.stderr',io.StringIO()):
                self.assertEqual(execution.parent(options,backend,clock=lambda:1),1)
            report=json.loads((options.run_root/'parent-report.json').read_text())
            self.assertEqual(report['first_error']['message'],str(first));self.assertEqual(report['observer_report_io_error']['message'],'secondary observer report error')
            observe.assert_called_once();preflight.assert_called_once();backend.release.assert_called_once()

    def test_census_exception_traceback_does_not_retain_document_proxies_through_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));options.run_root.mkdir();app=App();backend=self.backend(app)
            def read(app,args,report):
                held_assembly=app.references[2]();held_part=app.references[1]()
                self.assertIsNotNone(held_assembly);self.assertIsNotNone(held_part)
                raise ValueError('observer locals retain native proxies until traceback collection')
            patches=self.parent_patches(app,read)
            with patches[0],patches[1],patches[2],patches[3]:
                self.assertEqual(execution.parent(options,backend,clock=lambda:1),1)
            backend.release.assert_called_once()
            report=json.loads((options.run_root/'parent-report.json').read_text())
            self.assertEqual(report['cleanup_errors'],[])
            self.assertIn('observer locals',report['first_error']['message'])

    def test_wrong_thread_or_ownership_stops_before_opens(self):
        for field,value in (('thread_id',-1),('ownership_verified',False),('pid',8)):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temporary:
                options=self.options(Path(temporary));options.run_root.mkdir();app=App();backend=self.backend(app);setattr(backend,field,value)
                with mock.patch.object(execution,'prepare_copies',return_value={}),mock.patch.object(execution.reader,'verify_files',return_value={}),mock.patch.object(execution.reader,'run') as read:
                    self.assertEqual(execution.parent(options,backend,clock=lambda:1),1)
                self.assertEqual(app.open_paths,[]);read.assert_not_called();backend.release.assert_called_once()

    def test_first_open_warning_strict_and_no_second_open(self):
        for warning in (1,True,2.0):
            with self.subTest(warning=warning),tempfile.TemporaryDirectory() as temporary:
                options=self.options(Path(temporary));options.run_root.mkdir();app=App(warning);backend=self.backend(app)
                with mock.patch.object(execution,'prepare_copies',return_value={}),mock.patch.object(execution.reader,'verify_files',return_value={}),mock.patch.object(execution.reader,'run') as read:
                    self.assertEqual(execution.parent(options,backend,clock=lambda:1),1)
                self.assertEqual(len(app.open_paths),1);read.assert_not_called();backend.release.assert_called_once()
                report=json.loads((options.run_root/'parent-report.json').read_text());self.assertEqual(report['opens'][0]['api_warning'],warning)
                self.assertEqual(report['opens'][0]['flags_actual'],dict(DocumentType=1,ReadOnly=True,Silent=True,UseLightWeightDefault=False,LightWeight=False))

    def test_journal_stop_and_deadline_block_native_and_logging_cannot_replace_first(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);stop=root/'stop';function=mock.Mock()
            stop.write_text('stop')
            with self.assertRaises(TimeoutError):execution.Journal(root/'trace',stop).call('native',function)
            stop.unlink()
            with self.assertRaises(TimeoutError):execution.Journal(root/'trace',deadline=1800,clock=lambda:1800).call('native',function)
            function.assert_not_called()
            first=RuntimeError('first native error');journal=execution.Journal(root/'trace')
            original=Path.open;writes=[0]
            def open_path(path,*args,**kwargs):
                writes[0]+=1
                if writes[0]>1:raise OSError('trace disk failure')
                return original(path,*args,**kwargs)
            with mock.patch.object(Path,'open',open_path),mock.patch('sys.stderr',NS(write=mock.Mock(side_effect=OSError('stderr failed')))):
                with self.assertRaises(RuntimeError) as caught:journal.call('native',lambda:(_ for _ in ()).throw(first))
            self.assertIs(caught.exception,first);self.assertEqual(len(journal.secondary_errors),2)

    def test_nested_pending_partial_tail_exact_budgets_and_unknown_times(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'trace'
            def row(sequence,phase,time=10,call='outer'):
                return dict(event='swcli.native-call',request_id='r',sequence=sequence,stage='s',call=call,phase=phase,monotonic_seconds=time)
            records=[row(0,'begin'),row(1,'begin',11,'inner'),row(1,'end',12,'inner')]
            path.write_text('\n'.join(json.dumps(x) for x in records)+'\n'+json.dumps(row(0,'end',13)))
            active=execution.pending_calls([path]);self.assertEqual(len(active),1)
            self.assertIsNone(execution.budget_failure(609.999,0,active));self.assertEqual(execution.budget_failure(610,0,active),'native-budget-600')
            self.assertEqual(execution.budget_failure(1800,0,{}),'group-budget-1800')
            for invalid in (True,None,'10',float('nan'),float('inf'),611):
                with self.subTest(invalid=repr(invalid)),self.assertRaises(RuntimeError):execution.budget_failure(610,0,{('p','r',1,'s','c'):invalid})
            path.write_text(json.dumps(row(0,'begin'))+'\n'+json.dumps(row(0,'end',12,'different'))+'\n')
            with self.assertRaises(RuntimeError):execution.pending_calls([path])

    def test_completed_native_span_cannot_evade_600_budget_by_finishing_between_polls(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'trace'
            begin=dict(event='swcli.native-call',request_id='r',sequence=1,stage='s',call='native',phase='begin',monotonic_seconds=10)
            for ended,expected in ((609.999,None),(610,'native-budget-600')):
                path.write_text(json.dumps(begin)+'\n'+json.dumps(dict(begin,phase='end',monotonic_seconds=ended))+'\n')
                snapshot=execution.pending_calls([path]);self.assertFalse(snapshot)
                self.assertEqual(execution.budget_failure(611,0,snapshot),expected)
            for ended in (True,float('nan'),9,612):
                path.write_text(json.dumps(begin)+'\n'+json.dumps(dict(begin,phase='end',monotonic_seconds=ended))+'\n')
                with self.assertRaisesRegex(RuntimeError,'timestamp'):execution.budget_failure(611,0,execution.pending_calls([path]))

    def process_fixture(self,options,process):
        options.run_root.mkdir(exist_ok=True)
        (options.run_root/'parent-report.json').write_text(json.dumps(dict(success=True,parent_process_id=process.pid,
             cleanup=dict(host_exit_confirmed=True,host_exit_code=0),cleanup_errors=[])))
        return process

    def test_supervisor_reads_pending_before_clock_and_preserves_sample(self):
        for invalid in (False,True):
            with self.subTest(invalid=invalid),tempfile.TemporaryDirectory() as temporary:
                options=self.options(Path(temporary));process=Process();now=[1000.];reads=[0]
                def pending(paths):
                    reads[0]+=1;now[0]=1000.002
                    return {('trace','r',1,'s','native'):1000.003 if invalid else 1000.001} if reads[0]==1 else {}
                def sleep(seconds):process.returncode=0
                with mock.patch.object(execution,'verify_options',return_value=dict(source_files={})), \
                     mock.patch.object(execution,'python_identity',return_value=dict(pid=42,sha256=execution.reader.PYTHON_SHA,created=100)), \
                     mock.patch.object(execution.time,'time',return_value=100),mock.patch.object(execution,'pending_calls',side_effect=pending):
                    code=execution.supervisor(options,popen=lambda *a,**k:self.process_fixture(options,process),clock=lambda:now[0],sleep=sleep)
                state=json.loads((options.run_root/'supervisor-report.json').read_text());sample=state['budget_sample']
                self.assertTrue(sample['clock_sampled_after_pending_read']);self.assertEqual(sample['now'],1000.002)
                self.assertEqual(code,1 if invalid else 0)
                if invalid:self.assertIn('timestamp',state['first_error']['message']);process.terminate.assert_called_once()

    def test_group_deadline_stops_only_owned_python_without_extra_wait_or_host_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));process=Process();process.terminate.side_effect=lambda:None;now=[0.]
            def pending(paths):now[0]=1800.;return {}
            with mock.patch.object(execution,'verify_options',return_value=dict(source_files={})), \
                 mock.patch.object(execution,'python_identity',return_value=dict(pid=42,sha256=execution.reader.PYTHON_SHA,created=100)), \
                 mock.patch.object(execution.time,'time',return_value=100),mock.patch.object(execution,'pending_calls',side_effect=pending),mock.patch('sys.stderr',io.StringIO()):
                self.assertEqual(execution.supervisor(options,popen=lambda *a,**k:process,clock=lambda:now[0],sleep=lambda s:None),1)
            state=json.loads((options.run_root/'supervisor-report.json').read_text())
            self.assertEqual(state['first_error']['message'],'group-budget-1800');self.assertIsNone(state['host_exit_code'])
            self.assertTrue(state['parent_exit_unconfirmed']);process.wait.assert_not_called();process.terminate.assert_called_once()

    def test_outer_1840_stops_only_exact_python_handles_and_no_extra_wait(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));process=Process();now=[0.];handle=NS(stop=mock.Mock(),close=mock.Mock())
            def spawn(*args,**kwargs):
                options.run_root.mkdir();(options.run_root/'supervisor-report.json').write_text(json.dumps(dict(parent_pid=43,parent_python_identity=dict(pid=43,sha256=execution.reader.PYTHON_SHA,created=100))))
                now[0]=1840.;return process
            with mock.patch.object(execution,'verify_options'),mock.patch.object(execution.time,'time',return_value=100), \
                 mock.patch.object(execution,'python_identity',return_value=dict(pid=42,sha256=execution.reader.PYTHON_SHA,created=100)):
                self.assertEqual(execution.manager(options,popen=spawn,clock=lambda:now[0],sleep=lambda s:None,handle_factory=lambda pid,identity:handle),1)
            state=json.loads((options.run_root.parent/'run-manager/manager-report.json').read_text())
            self.assertEqual(state['first_error']['message'],'outer-budget-1840');handle.stop.assert_called_once();handle.close.assert_called_once()
            process.terminate.assert_called_once();process.wait.assert_not_called()

    def test_uncertain_cleanup_uses_only_os_state_and_preserves_unknown(self):
        for exited,code in ((False,None),(True,17),(True,0)):
            with self.subTest(exited=exited,code=code),tempfile.TemporaryDirectory() as temporary:
                backend=object.__new__(execution.WindowsBackend);backend.handle=object();backend.ownership_verified=True
                backend.options=NS(run_root=Path(temporary));backend.exit_state=mock.Mock(return_value=exited);backend.exit_code=mock.Mock(return_value=code)
                backend.identity=mock.Mock(side_effect=AssertionError('no uncertain identity/CAD access'));backend.app=NS(ExitApp=mock.Mock())
                state=dict(host_exit_code=None,host_exit_confirmed=False)
                backend.cleanup(execution.Journal(Path(temporary)/'cleanup'),state,True,1800,clock=lambda:1800)
                self.assertEqual(state['host_exit_code'],code);self.assertEqual(state['host_exit_confirmed'],exited)
                backend.identity.assert_not_called();backend.app.ExitApp.assert_not_called()

    def test_cleanup_normal_wait_is_capped_by_remaining_and_raw_code_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend=object.__new__(execution.WindowsBackend);backend.handle=object();backend.ownership_verified=True
            backend.options=NS(run_root=Path(temporary));backend.identity=mock.Mock(return_value='running');backend.exit_code=lambda:23
            backend.app=NS(ExitApp=lambda:None);wait=mock.Mock(return_value=0)
            backend.events=NS(WaitForSingleObject=wait,WAIT_OBJECT_0=0)
            state={};backend.cleanup(execution.Journal(Path(temporary)/'cleanup'),state,False,1800,clock=lambda:1799.5)
            wait.assert_called_once_with(backend.handle,500);self.assertEqual(state['host_exit_code'],23)

    def test_fixed_three_zip_copy_digests_and_readonly(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));options.run_root.mkdir();files={name:name.encode() for name in execution.reader.FILES}
            import hashlib
            expected={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
            with ZipFile(options.internal_zip,'w') as archive:
                for name,data in files.items():archive.writestr('swcli-native-smoke/assembly-mates-calibration/native/'+name,data)
            with mock.patch.dict(execution.reader.FILES,expected,clear=True):
                self.assertEqual(set(execution.prepare_copies(options)),set(files))
                with self.assertRaises(FileExistsError):execution.prepare_copies(options)
            for path in (options.run_root/'fixtures').iterdir():self.assertEqual(path.stat().st_mode&0o222,0)

    def test_uncertain_bool_raw_code_is_not_coerced_to_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend=object.__new__(execution.WindowsBackend);backend.handle=object();backend.ownership_verified=True
            backend.options=NS(run_root=Path(temporary));backend.exit_state=lambda:True;backend.exit_code=lambda:False
            state=dict(host_exit_code=None,host_exit_confirmed=False)
            with self.assertRaisesRegex(RuntimeError,'strict integer'):
                backend.cleanup(execution.Journal(Path(temporary)/'trace'),state,True,1800,clock=lambda:1800)
            self.assertIsNone(state['host_exit_code']);self.assertTrue(state['host_exit_confirmed'])

    def test_mirror_failure_rejects_success_and_root_manifest_parent_claim_is_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));process=Process()
            def spawn(*args,**kwargs):
                result=self.process_fixture(options,process);process.returncode=0;return result
            copier=NS(tick=mock.Mock(),finish=mock.Mock(side_effect=OSError('persistent copy failed')))
            with mock.patch.object(execution,'verify_options',return_value=dict(source_files={})), \
                 mock.patch.object(execution,'python_identity',return_value=dict(pid=42,sha256=execution.reader.PYTHON_SHA,created=100)), \
                 mock.patch.object(execution.time,'time',return_value=100),mock.patch.object(execution,'MirrorWorker',return_value=copier),mock.patch('sys.stderr',io.StringIO()):
                self.assertEqual(execution.supervisor(options,popen=spawn,clock=lambda:1,sleep=lambda s:None),1)
            state=json.loads((options.run_root/'supervisor-report.json').read_text())
            self.assertFalse(state['success']);self.assertIn('persistent copy',state['mirror_error']['message'])
            self.assertFalse((options.artifact_dir/'transfer-receipt.json').exists())

    def test_cleanup_trace_failure_still_releases_proxies_once_and_keeps_business_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));options.run_root.mkdir();app=App();backend=self.backend(app)
            first=ValueError('first census failure')
            def read(*args):raise first
            original=execution.Journal.call
            def call(journal,label,function):
                if label=='release-parent-proxies-and-COM':raise OSError('cleanup trace write failed')
                return original(journal,label,function)
            patches=self.parent_patches(app,read)
            with patches[0],patches[1],patches[2],patches[3],mock.patch.object(execution.Journal,'call',call):
                self.assertEqual(execution.parent(options,backend,clock=lambda:1),1)
            backend.release.assert_called_once()
            report=json.loads((options.run_root/'parent-report.json').read_text())
            self.assertEqual(report['first_error']['message'],str(first));self.assertTrue(report['cleanup_errors'])

    def test_acquire_uses_current_main_factory_and_readonly_owned_handle_capture(self):
        from swcli.daemon import server
        with tempfile.TemporaryDirectory() as temporary:
            backend=object.__new__(execution.WindowsBackend)
            backend.options=NS(expected_host_image=Path(temporary)/'SLDWORKS.exe')
            backend.inventory=lambda:[];backend.client=object();backend.identity_observations=[];backend.on_identity=mock.Mock()
            backend.identity=mock.Mock(return_value='running');backend.ownership_verified=False
            app=NS(GetProcessID=7,RevisionNumber='33.5.0',GetDocumentCount=0)
            def capture(pid,launched,**kwargs):
                self.assertEqual(pid,7);self.assertIs(kwargs['terminate_right'],False)
                kwargs['observe']({'raw':'identity retained before admission'})
                return object(),{'pid':7}
            backend.native=NS(capture=mock.Mock(side_effect=capture))
            with mock.patch.object(server,'acquire_resident_app',return_value=(app,True)) as acquire:
                result=backend.acquire()
            acquire.assert_called_once_with(backend.client,visible=False,attach_existing=False)
            backend.native.capture.assert_called_once();backend.on_identity.assert_called_once()
            self.assertTrue(backend.ownership_verified);self.assertTrue(result['owned'])
            backend.native.capture.reset_mock();backend.ownership_verified=False
            with mock.patch.object(server,'acquire_resident_app',return_value=(app,False)):
                with self.assertRaisesRegex(RuntimeError,'attachment refused'):backend.acquire()
            backend.native.capture.assert_not_called();self.assertFalse(backend.ownership_verified)

    def test_parent_bad_foreground_preflight_never_runs_reader_or_activates(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));options.run_root.mkdir();app=App();backend=self.backend(app)
            with mock.patch.object(execution,'prepare_copies',return_value={}),mock.patch.object(execution.reader,'verify_files',return_value={}), \
                 mock.patch.object(execution.reader,'preflight',side_effect=RuntimeError('target assembly inactive')), \
                 mock.patch.object(execution.reader,'run') as read:
                self.assertEqual(execution.parent(options,backend,clock=lambda:1),1)
            self.assertEqual(len(app.open_paths),2);read.assert_not_called();app.ActivateDoc3.assert_not_called()
            backend.release.assert_called_once()

    def test_manager_success_requires_and_hashes_persistent_manager_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));process=Process()
            def spawn(*args,**kwargs):
                options.run_root.mkdir();options.artifact_dir.mkdir()
                (options.run_root/'supervisor-report.json').write_text(json.dumps(dict(success=True,source_manifest_sha256=options.source_manifest_sha)))
                process.returncode=0;return process
            with mock.patch.object(execution,'verify_options'),mock.patch.object(execution.time,'time',return_value=100), \
                 mock.patch.object(execution,'python_identity',return_value=dict(pid=42,sha256=execution.reader.PYTHON_SHA,created=100)):
                self.assertEqual(execution.manager(options,popen=spawn,clock=lambda:1),0)
            receipt=json.loads((options.artifact_dir/'manager-transfer-receipt.json').read_text())
            self.assertEqual(receipt['source_manifest_sha256'],options.source_manifest_sha)
            for name,sha in receipt['files'].items():self.assertEqual(execution.digest(options.artifact_dir/'manager'/name),sha)

    def test_reported_python_pid_type_refused_before_opening_any_process_handle(self):
        open_process=mock.Mock(side_effect=AssertionError('unknown PID must not open a process'))
        modules={'win32api':NS(OpenProcess=open_process),'win32con':NS(),'win32event':NS()}
        with mock.patch.dict(sys.modules,modules):
            for pid in (True,0,-1,'42'):
                with self.subTest(pid=pid),self.assertRaisesRegex(RuntimeError,'positive integer'):
                    execution.OwnedPythonHandle(pid,dict(pid=pid,sha256=execution.reader.PYTHON_SHA))
        open_process.assert_not_called()

    def test_explicit_parent_argv_and_stage_only_new_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=self.options(Path(temporary));args=execution.role_argv(options,'parent')
            self.assertIn('--group-started',args);self.assertIn('--expected-host-image',args)
            self.assertNotIn('--observer-channel',args);self.assertNotIn('--attach-existing',args)
