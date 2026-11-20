"""Private fixed readonly census transport; no public routes or execution grant.

Selected Journal/watchdog/mirror primitives derive from b2e7e4b. No old mate
reader/product modules are imported. manager/supervisor never initialize COM;
only the single parent STA acquires a host and invokes the new census once.
"""
import argparse
import gc
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SPEC=importlib.util.spec_from_file_location('active_census_reader',HERE/'observe-active-assembly-target-census.py')
reader=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(reader)
require,digest=reader.require,reader.digest
NATIVE_SECONDS,GROUP_SECONDS,OUTER_SECONDS=600,1800,1840

def is_link(path):
    return path.is_symlink() or getattr(path,'is_junction',lambda:False)()

def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def failure(error):
    return dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())


class Journal:
    def __init__(self, path, stop_path=None, *, deadline=None, clock=time.monotonic):
        self.path = path
        self.stop_path = stop_path
        self.sequence = 0
        self.deadline,self.clock=deadline,clock
        self.secondary_errors=[]

    def call(self, label, function):
        if self.stop_path is not None and self.stop_path.exists():
            raise TimeoutError('supervisor stop before another parent call')
        if self.deadline is not None and self.clock()>=self.deadline:
            raise TimeoutError('group deadline before another parent call')
        self.sequence += 1
        sequence = self.sequence
        def emit(phase, **facts):
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(event='owner-parent-call', call=label, sequence=sequence,
                    phase=phase, monotonic_seconds=time.monotonic(), **facts))+'\n')
                stream.flush(); os.fsync(stream.fileno())
        emit('begin')
        try:
            value = function()
        except BaseException as error:
            try: emit('error', error=failure(error))
            except Exception as io_error:
                self.secondary_errors.append(failure(io_error))
                try:
                    sys.stderr.write(json.dumps(dict(event='parent-trace-secondary-error',error=failure(io_error)))+'\n')
                    sys.stderr.flush()
                except Exception as stderr_error:self.secondary_errors.append(failure(stderr_error))
            raise
        emit('end')
        return value


def readonly_open(app, path, document_type, journal, report):
    """Exactly one OpenDoc7. Output flags/errors remain evidence even on refusal."""
    path=path.resolve()
    row=dict(path=str(path), expected_type=document_type, flags_requested=dict(
        DocumentType=document_type, ReadOnly=True, Silent=True, UseLightWeightDefault=False, LightWeight=False))
    report.setdefault('opens',[]).append(row)
    spec=journal.call('GetOpenDocSpec-'+path.suffix,lambda:app.GetOpenDocSpec(str(path)))
    require(spec is not None, 'OpenDocSpec returned null')
    for name, value in row['flags_requested'].items():
        journal.call('open-flag-'+name,lambda name=name,value=value:setattr(spec,name,value))
    row['flags_actual']={}
    for name,value in row['flags_requested'].items():
        actual=journal.call('read-open-flag-'+name,lambda name=name:reader._com_value(spec,name))
        row['flags_actual'][name]=actual
        require(type(actual) is type(value) and actual==value, 'opening flag type/value differs: '+name)
    document=journal.call('OpenDoc7-'+path.suffix,lambda:app.OpenDoc7(spec))
    row['returned_null']=document is None
    # Official out fields are retrieved once immediately after the return;
    # no document observation or fallback follows an opening refusal.
    row['api_error']=journal.call('OpenDoc7-error',lambda:reader._com_value(spec,'Error'))
    row['api_warning']=journal.call('OpenDoc7-warning',lambda:reader._com_value(spec,'Warning'))
    require(type(row['api_error']) is int and row['api_error']==0, 'OpenDoc7 error or unknown type')
    require(type(row['api_warning']) is int and row['api_warning'] in (0,2), 'OpenDoc7 warning outside exact 0/2')
    require(document is not None, 'OpenDoc7 returned null')
    row['document']={}
    for field in ('GetType','GetPathName','GetSaveFlag','IsOpenedReadOnly','IsOpenedViewOnly'):
        row['document'][field]=journal.call('opened-'+field,lambda field=field:reader._com_value(document,field))
    facts=row['document']
    require(type(facts['GetType']) is int and facts['GetType']==document_type,'opened type differs')
    require(type(facts['GetPathName']) is str and facts['GetPathName'].casefold()==str(path.resolve()).casefold(),'opened path differs')
    require(facts['GetSaveFlag'] is False and facts['IsOpenedReadOnly'] is True and facts['IsOpenedViewOnly'] is False,
            'opened document dirty, writable, view-only or unknown')
    return document


def python_identity(handle):
    import win32process
    path=Path(win32process.GetModuleFileNameEx(handle,0))
    return dict(pid=win32process.GetProcessId(handle),path=str(path),created=win32process.GetProcessTimes(handle)['CreationTime'].timestamp(),sha256=digest(path))


def child_environment():
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT/'src');env['PYTHONDONTWRITEBYTECODE']='1';env['SWCLI_TRACE_NATIVE_CALLS']='1'
    return env


class PendingCalls(dict):
    def __init__(self):
        super().__init__();self.completed=[]


def pending_calls(paths):
    active=PendingCalls()
    for path in paths:
        if not path.exists():continue
        for line in path.read_text(encoding='utf-8',errors='replace').splitlines(keepends=True):
            if not line.endswith('\n'):break
            try:item=json.loads(line)
            except ValueError:continue  # An incomplete final line is not an end.
            if item.get('event') not in ('owner-parent-call','swcli.native-call'):continue
            key=(str(path),item.get('request_id'),item.get('sequence'),item.get('stage'),item.get('call'))
            require(type(item.get('sequence')) is int and item['sequence']>=0,'invalid trace sequence')
            if item.get('phase')=='begin':
                require(key not in active,'duplicate pending native begin')
                active[key]=item.get('monotonic_seconds')
            elif item.get('phase') in ('end','error'):
                require(key in active,'native end without recorded begin')
                active.completed.append((key,active.pop(key),item.get('monotonic_seconds')))
            else:raise RuntimeError('unknown native phase')
    return active


def budget_failure(now,started,active):
    require(type(now) in (int,float) and type(started) in (int,float) and math.isfinite(now) and math.isfinite(started) and 0<=started<=now,'unknown group clock')
    if now-started>=GROUP_SECONDS:return 'group-budget-1800'
    for started_call in active.values():
        require(type(started_call) in (int,float) and math.isfinite(started_call) and started_call<=now,'unknown native trace timestamp')
        if now-started_call>=NATIVE_SECONDS:return 'native-budget-600'
    for key,began,ended in getattr(active,'completed',[]):
        require(type(began) in (int,float) and type(ended) in (int,float) and math.isfinite(began) and math.isfinite(ended)
                and began<=ended<=now,'unknown completed native trace timestamp')
        if ended-began>=NATIVE_SECONDS:return 'native-budget-600'
    return None


def budget_sample_snapshot(now,started,active):
    def scalar(value):
        if type(value) is float and not math.isfinite(value):
            return dict(value_type='float',value_repr=repr(value))
        return value
    rows=[]
    for (path,request_id,sequence,stage,call),value in active.items():
        age=now-value if type(now) in (int,float) and type(value) in (int,float) and math.isfinite(now) and math.isfinite(value) else None
        rows.append(dict(trace_path=path,request_id=request_id,sequence=sequence,stage=stage,call=call,
                         monotonic_seconds=scalar(value),value_type=type(value).__name__,age_seconds=age))
    completed=[dict(trace_path=key[0],request_id=key[1],sequence=key[2],stage=key[3],call=key[4],
                    began=scalar(began),ended=scalar(ended)) for key,began,ended in getattr(active,'completed',[])]
    return dict(now=scalar(now),group_started=scalar(started),active=rows,completed=completed,
                clock_sampled_after_pending_read=True)


def mirror(run_root,artifact):
    for path in run_root.rglob('*'):
        require(not is_link(path),'execution output link refused')
        if not path.is_file() or path.suffix=='.tmp':continue
        relative=path.relative_to(run_root)
        destination=artifact/relative
        require(destination.resolve().is_relative_to(artifact.resolve()),'persistent output escapes artifact')
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_suffix(destination.suffix+'.tmp')
        shutil.copyfile(path,temporary);os.replace(temporary,destination)


class MirrorWorker:
    def __init__(self,root,artifact):
        self.root,self.artifact=root,artifact
        self.thread=None;self.error=None

    def tick(self):
        if self.error is not None:raise self.error
        if self.thread is not None and self.thread.is_alive():return
        def copy():
            try:mirror(self.root,self.artifact)
            except Exception as error:self.error=error
        self.thread=threading.Thread(target=copy,daemon=True)
        self.thread.start()

    def finish(self,timeout=5):
        if self.thread is not None:
            self.thread.join(timeout)
            require(not self.thread.is_alive(),'persistent artifact mirror unconfirmed')
        self.tick()
        self.thread.join(timeout)
        require(not self.thread.is_alive(),'final artifact mirror unconfirmed')
        if self.error is not None:raise self.error


def verify_options(options):
    manifest=reader.verify_candidate(options)
    require(os.path.samefile(options.expected_host_image,options.host_executable), 'approved host path/file identity differs')
    require(digest(options.expected_host_image)==manifest['pins']['host_executable'], 'expected host image digest differs')
    return manifest


def prepare_copies(options):
    directory=options.run_root/'fixtures';directory.mkdir(exist_ok=False)
    prefix='swcli-native-smoke/assembly-mates-calibration/native/'
    with ZipFile(options.internal_zip) as archive:
        names=archive.namelist();require(len(names)==len(set(names)), 'duplicate ZIP names')
        for name in names:
            path=PurePosixPath(name)
            require(not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name,'unsafe ZIP path')
        for name,sha in reader.FILES.items():
            key=prefix+name;require(names.count(key)==1,'fixed fixture entry absent or repeated')
            blob=archive.read(key)
            import hashlib
            require(hashlib.sha256(blob).hexdigest()==sha,'fixed sample digest differs')
            destination=directory/name
            with destination.open('xb') as stream:stream.write(blob)
            destination.chmod(0o444)
    return reader.verify_files(directory)


class WindowsBackend:
    def __init__(self,options):
        import pythoncom,win32com.client,win32api,win32con,win32event
        from swcli.host_processes import solidworks_process_ids
        spec=importlib.util.spec_from_file_location('main_owned_native',ROOT/'scripts/ci/gate_support/unit_owned_native.py')
        self.native=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.native)
        self.com,self.client,self.api,self.con,self.events=pythoncom,win32com.client,win32api,win32con,win32event
        self.options=options;self.inventory=solidworks_process_ids
        self.expected_image_sha=json.loads(options.source_manifest.read_text())['pins']['host_executable']
        self.app=self.handle=self.pid=self.identity_record=None
        self.initialized=self.ownership_verified=False
        self.identity_observations=[];self.on_identity=lambda observation:None
        self.thread_id=None

    def initialize(self):
        require(self.inventory()==[], 'preexisting or unknown CAD occupancy')
        import ctypes
        from ctypes import wintypes
        import win32security
        session=wintypes.DWORD();function=ctypes.WinDLL('kernel32',use_last_error=True).ProcessIdToSessionId
        function.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)];function.restype=wintypes.BOOL
        require(bool(function(os.getpid(),ctypes.byref(session))) and session.value==1,'reserved interactive session 1 required')
        token=win32security.OpenProcessToken(self.api.GetCurrentProcess(),self.con.TOKEN_QUERY)
        try:require(win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token,win32security.TokenUser)[0])!='S-1-5-18','SYSTEM refused')
        finally:token.Close()
        self.com.CoInitialize();self.initialized=True;self.thread_id=threading.get_ident()

    def acquire(self):
        from swcli.daemon.server import acquire_resident_app
        require(self.inventory()==[], 'CAD occupancy changed')
        launched=time.time();self.app,owned=acquire_resident_app(self.client,visible=False,attach_existing=False)
        require(owned is True,'existing host attachment refused')
        self.pid=reader._com_value(self.app,'GetProcessID');require(type(self.pid) is int and self.pid>0,'invalid owned PID')
        def record(observation):self.identity_observations.append(observation);self.on_identity(observation)
        self.handle,self.identity_record=self.native.capture(self.pid,launched,expected_image=str(self.options.expected_host_image),terminate_right=False,observe=record)
        require(self.identity()=='running','owned host not live')
        require(reader._com_value(self.app,'RevisionNumber')=='33.5.0','native revision differs')
        count=reader._com_value(self.app,'GetDocumentCount');require(type(count) is int and count==0,'owned host not empty')
        self.ownership_verified=True
        return dict(process_id=self.pid,identity=self.identity_record,owned=True)

    def exit_state(self):
        status=self.events.WaitForSingleObject(self.handle,0)
        require(status in (self.events.WAIT_TIMEOUT,self.events.WAIT_OBJECT_0),'unknown held process state')
        return status==self.events.WAIT_OBJECT_0

    def identity(self):
        require(self.handle is not None,'held handle absent')
        require(set(self.inventory())<={self.pid},'foreign CAD occupancy')
        if self.exit_state():return 'exited'
        require(self.native.process_identity(self.handle)==self.identity_record,'held process identity changed')
        require(digest(Path(self.identity_record['image']))==self.expected_image_sha,'held image digest changed')
        return 'running'

    def exit_code(self):
        import ctypes
        from ctypes import wintypes
        function=ctypes.WinDLL('kernel32',use_last_error=True).GetExitCodeProcess
        function.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];function.restype=wintypes.BOOL
        code=wintypes.DWORD();require(bool(function(int(self.handle),ctypes.byref(code))),'GetExitCodeProcess failed')
        return int(code.value)

    def cleanup(self,journal,state,uncertain,deadline,clock=time.monotonic):
        if self.handle is None or not self.ownership_verified:
            state['host_identity_unknown']=True;return
        if uncertain or clock()>=deadline or (self.options.run_root/'stop.json').exists():
            state['host_preserved_due_to_uncertainty']=True
            if journal.call('cleanup-OS-exit-state',self.exit_state):
                state['host_exit_confirmed']=True
                code=journal.call('GetExitCodeProcess',self.exit_code)
                require(type(code) is int,'raw host code is not strict integer');state['host_exit_code']=code
            return
        if journal.call('cleanup-OS-identity',self.identity)=='running':
            require(clock()<deadline and not (self.options.run_root/'stop.json').exists(),'stop/group exhausted before ExitApp')
            state['ExitApp_attempted']=True
            journal.call('ExitApp',lambda:reader._com_value(self.app,'ExitApp'))
        remaining=max(0,min(10,deadline-clock()))
        status=journal.call('WaitForOwnedProcess',lambda:self.events.WaitForSingleObject(self.handle,int(remaining*1000)))
        require(status==self.events.WAIT_OBJECT_0,'held host exit unconfirmed')
        state['host_exit_confirmed']=True
        code=journal.call('GetExitCodeProcess',self.exit_code)
        require(type(code) is int,'raw host code is not strict integer');state['host_exit_code']=code

    def release(self):
        self.app=None;gc.collect();first=None;self.release_secondary_errors=[]
        for name,function,needed in (('CoUninitialize',self.com.CoUninitialize,self.initialized),
                                     ('CloseProcessHandle',lambda:self.handle.Close(),self.handle is not None)):
            if needed:
                try:function()
                except Exception as error:
                    if first is None:first=error
                    else:self.release_secondary_errors.append(dict(stage=name,error=failure(error)))
        self.initialized=False;self.handle=None
        if first is not None:raise first


def parent(options,backend,clock=time.monotonic):
    require(type(options.group_started) in (int,float) and math.isfinite(options.group_started) and 0<=options.group_started<=clock(),'invalid parent group clock')
    deadline=options.group_started+GROUP_SECONDS
    report=dict(role='census-parent',success=False,public_acceptance=False,resource_released=False,
        parent_process_id=os.getpid(),parent_thread_id=threading.get_ident(),cleanup_errors=[],source_manifest_sha256=options.source_manifest_sha,
        cleanup=dict(resource_released=False,host_exit_code=None,host_exit_confirmed=False),
        identity_observations=getattr(backend,'identity_observations',[]))
    persist=lambda:atomic_json(options.run_root/'parent-report.json',report)
    journal=Journal(options.run_root/'parent-trace.jsonl',options.run_root/'stop.json',deadline=deadline,clock=clock)
    part=assembly=target=None
    try:
        backend.on_identity=lambda observation:persist()
        journal.call('prepare-fixed-readonly-copies',lambda:prepare_copies(options));persist()
        journal.call('initialize-owned-STA',backend.initialize)
        report['host']=journal.call('acquire-owned-empty-host',backend.acquire);persist()
        require(backend.initialized is True and backend.ownership_verified is True and backend.pid==report['host']['process_id']
                and backend.thread_id==threading.get_ident(),'verified same owning STA before opening required')
        part=readonly_open(backend.app,options.run_root/'fixtures/concentric-aligned-component.SLDPRT',1,journal,report);persist()
        assembly=readonly_open(backend.app,options.run_root/'fixtures/coincident-aligned.SLDASM',2,journal,report);persist()
        target=journal.call('prepared-catalog',lambda:reader.preflight(backend.app,backend.pid,options.run_root/'fixtures'))
        require(journal.call('prepared-ASM-IsSame',lambda:reader._same(backend.app,target,assembly)),'prepared ASM identity differs')
        require(journal.call('prepared-ActiveDoc-IsSame',lambda:reader._same(backend.app,reader._com_value(backend.app,'ActiveDoc'),assembly)),'ASM did not naturally become active')
        require(backend.initialized is True and backend.ownership_verified is True and backend.pid==report['host']['process_id']
                and backend.thread_id==threading.get_ident(),'same owning STA/host required')
        require(journal.call('owned-host-before-census',backend.identity)=='running','host not live')
        options.fixture_dir=options.run_root/'fixtures';options.expected_pid=backend.pid
        observation=dict(request_id=str(uuid.uuid4()),executing_process_id=os.getpid(),executing_thread_id=threading.get_ident())
        report['observer_report']=observation
        try:journal.call('whole-census-on-owned-STA',lambda:reader.run(backend.app,options,observation))
        finally:
            first=sys.exc_info()[1]
            try:atomic_json(options.run_root/'observer-report.json',observation)
            except Exception as error:
                report['observer_report_io_error']=failure(error)
                try:sys.stderr.write(json.dumps(dict(observation=observation,observer_report_io_error=report['observer_report_io_error']))+'\n');sys.stderr.flush()
                except Exception:pass
                if first is None:raise
            finally:first=None  # Do not retain census traceback/native proxies through COM release.
        require(observation.get('success') is True,'readonly census failed')
        report['success']=True
    except BaseException as error:
        report['first_error']=failure(error);report['success']=False
    finally:
        uncertain=(options.run_root/'stop.json').exists() or clock()>=deadline
        if uncertain:report['success']=False
        cleanup=Journal(options.run_root/'cleanup-trace.jsonl')
        try:
            backend.cleanup(cleanup,report['cleanup'],uncertain,deadline,clock)
            if report['success']:
                state=report['cleanup']
                require(state.get('host_exit_confirmed') is True and type(state.get('host_exit_code')) is int and state['host_exit_code']==0,'strict held host exit zero required')
        except BaseException as error:
            report['success']=False;report['cleanup_errors'].append(failure(error));report.setdefault('first_error',failure(error))
        part=assembly=target=None
        release_attempted=False
        def release_once():
            nonlocal release_attempted
            release_attempted=True;backend.release()
        try:cleanup.call('release-parent-proxies-and-COM',release_once)
        except BaseException as error:
            report['success']=False;report['cleanup_errors'].append(failure(error));report.setdefault('first_error',failure(error))
            if not release_attempted:
                try:release_once()
                except BaseException as secondary:report['cleanup_errors'].append(failure(secondary))
        report['trace_secondary_errors']=journal.secondary_errors+cleanup.secondary_errors
        if report['trace_secondary_errors']:report['success']=False
        report['cleanup_errors'].extend(getattr(backend,'release_secondary_errors',[]))
        if report['cleanup_errors']:report['success']=False
        try:report['files_after']=reader.verify_files(options.run_root/'fixtures')
        except BaseException as error:report['success']=False;report['filesystem_error']=failure(error)
        try:persist()
        except BaseException as error:
            report['success']=False;report['parent_report_io_error']=failure(error)
            try:sys.stderr.write(json.dumps(report)+'\n');sys.stderr.flush()
            except Exception:pass
    return 0 if report['success'] else 1


def role_argv(options,role):
    args=[sys.executable,'-B',str(Path(__file__).resolve()),'--role',role,'--ticket',options.ticket]
    for name in ('run_root','artifact_dir','source_manifest','source_manifest_sha','internal_zip','public_zip','host_executable','host_type_library','expected_host_image'):
        args+=['--'+name.replace('_','-'),str(getattr(options,name))]
    if role=='parent':args+=['--group-started',str(options.group_started)]
    return args


def stop_python(process,state,remaining):
    if process.poll() is None:process.terminate()  # Original Popen handle only, never a CAD PID.
    state['parent_exit_code']=process.poll()
    if state['parent_exit_code'] is None and remaining<=0:state['parent_exit_unconfirmed']=True
    if state['parent_exit_code'] is None and remaining>0:
        try:state['parent_exit_code']=process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:state['parent_exit_unconfirmed']=True


def supervisor(options,popen=subprocess.Popen,clock=time.monotonic,sleep=time.sleep):
    started=options.group_started=clock()
    require(not options.run_root.exists() and not options.artifact_dir.exists(),'new run/artifact directories required')
    require(not options.artifact_dir.resolve().is_relative_to(options.run_root.resolve())
            and not options.run_root.resolve().is_relative_to(options.artifact_dir.resolve()),'run/artifact must be disjoint')
    manifest=verify_options(options)
    options.run_root.mkdir(parents=True,exist_ok=False);options.artifact_dir.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(options.source_manifest,options.artifact_dir/'source-manifest.json')
    require(clock()-started<GROUP_SECONDS,'group exhausted during preflight')
    state=dict(role='census-supervisor',success=False,public_acceptance=False,resource_released=False,
               native_seconds=600,group_seconds=1800,outer_seconds=1840,parent_exit_code=None,host_exit_code=None,
               source_manifest_sha256=options.source_manifest_sha,verified_source_count=len(manifest['source_files']))
    mirror_worker=MirrorWorker(options.run_root,options.artifact_dir);process=None
    remaining=lambda:max(0,min(10,GROUP_SECONDS-(clock()-started)))
    try:
        with (options.run_root/'parent-stdout.log').open('xb') as stdout,(options.run_root/'parent-stderr.log').open('xb') as stderr:
            launched=time.time()
            process=popen(role_argv(options,'parent'),stdout=stdout,stderr=stderr,cwd=ROOT,env=child_environment())
            state['parent_pid']=process.pid;state['parent_python_identity']=python_identity(process._handle)
            require(state['parent_python_identity']['sha256']==reader.PYTHON_SHA and state['parent_python_identity']['pid']==process.pid
                    and launched<=state['parent_python_identity']['created']<=time.time(),'parent Python binary/PID/creation differs')
            atomic_json(options.run_root/'supervisor-report.json',state)
            while process.poll() is None:
                active=pending_calls([options.run_root/name for name in ('parent-trace.jsonl','cleanup-trace.jsonl','parent-stderr.log')])
                now=clock();state['budget_sample']=budget_sample_snapshot(now,started,active)
                reason=budget_failure(now,started,active);mirror_worker.tick()
                if reason:
                    state['first_error']=dict(type='TimeoutError',message=reason)
                    atomic_json(options.run_root/'stop.json',state['first_error']);stop_python(process,state,remaining());break
                sleep(.1)
            state['parent_exit_code']=process.poll()
        path=options.run_root/'parent-report.json'
        if path.exists():
            parent_report=json.loads(path.read_text());state['host_exit_code']=parent_report.get('cleanup',{}).get('host_exit_code')
            cleanup=parent_report.get('cleanup',{})
            state['parent_report_success']=(parent_report.get('success') is True and parent_report.get('parent_process_id')==process.pid
                and cleanup.get('host_exit_confirmed') is True and type(cleanup.get('host_exit_code')) is int and cleanup['host_exit_code']==0
                and parent_report.get('cleanup_errors')==[])
        final_active=pending_calls([options.run_root/name for name in ('parent-trace.jsonl','cleanup-trace.jsonl','parent-stderr.log')])
        final_now=clock();state['final_budget_sample']=budget_sample_snapshot(final_now,started,final_active)
        final_reason=budget_failure(final_now,started,final_active)
        if final_reason:state.setdefault('first_error',dict(type='TimeoutError',message=final_reason))
        if final_active:state.setdefault('first_error',dict(type='RuntimeError',message='terminal native trace still pending'))
        state['success']=type(state['parent_exit_code']) is int and state['parent_exit_code']==0 and state.get('parent_report_success') is True and 'first_error' not in state
    except BaseException as error:
        state['success']=False;state.setdefault('first_error',failure(error))
        atomic_json(options.run_root/'stop.json',state['first_error'])
        if process is not None:stop_python(process,state,remaining())
    finally:
        atomic_json(options.run_root/'supervisor-report.json',state)
        try:
            require(remaining()>0,'group exhausted; final mirror unconfirmed')
            mirror_worker.finish(timeout=min(5,remaining()/2))
            hashes={}
            for path in options.run_root.rglob('*'):
                if path.is_file() and path.suffix!='.tmp':
                    relative=path.relative_to(options.run_root).as_posix();sha=digest(path)
                    require(digest(options.artifact_dir/relative)==sha,'persistent copy digest differs: '+relative);hashes[relative]=sha
            atomic_json(options.artifact_dir/'transfer-receipt.json',dict(source_manifest_sha256=options.source_manifest_sha,files=hashes))
        except BaseException as error:
            state['success']=False;state['mirror_error']=failure(error)
            atomic_json(options.run_root/'supervisor-report.json',state)
            sys.stderr.write(json.dumps(state)+'\n');sys.stderr.flush()
    return 0 if state['success'] else 1


class OwnedPythonHandle:
    """Outer manager can retain only the exact supervisor-reported Python child."""
    def __init__(self,pid,identity):
        import win32api,win32con,win32event
        self.api,self.events=win32api,win32event
        require(type(pid) is int and pid>0,'reported Python PID must be a positive integer')
        self.handle=win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION|win32con.PROCESS_VM_READ|win32con.SYNCHRONIZE|win32con.PROCESS_TERMINATE,False,pid)
        try:require(identity.get('pid')==pid and identity['sha256']==reader.PYTHON_SHA and python_identity(self.handle)==identity,'reported Python identity differs')
        except BaseException:self.handle.Close();raise
    def stop(self):
        status=self.events.WaitForSingleObject(self.handle,0)
        if status==self.events.WAIT_OBJECT_0:return
        require(status==self.events.WAIT_TIMEOUT,'Python wait state unknown')
        self.api.TerminateProcess(self.handle,124)
    def close(self):self.handle.Close()


def manager(options,popen=subprocess.Popen,clock=time.monotonic,sleep=time.sleep,handle_factory=OwnedPythonHandle):
    started=clock()
    require(not options.run_root.exists() and not options.artifact_dir.exists(),'new output paths required')
    verify_options(options)
    require(clock()-started<OUTER_SECONDS,'outer budget exhausted during preflight')
    process=handle=None
    state=dict(role='census-manager',success=False,public_acceptance=False,resource_released=False,outer_seconds=1840,source_manifest_sha256=options.source_manifest_sha)
    output=options.run_root.parent/(options.run_root.name+'-manager');output.mkdir(parents=True,exist_ok=False)
    manager_mirror=MirrorWorker(output,options.artifact_dir/'manager')
    def stop_parent_once():
        if handle is not None and not state.get('parent_stop_attempted'):
            state['parent_stop_attempted']=True
            try:handle.stop()
            except BaseException as error:state['parent_stop_error']=failure(error)
    try:
        with (output/'stdout.log').open('xb') as stdout,(output/'stderr.log').open('xb') as stderr:
            launched=time.time()
            process=popen(role_argv(options,'supervisor'),stdout=stdout,stderr=stderr,cwd=ROOT,env=child_environment())
            state['supervisor_pid']=process.pid
            state['supervisor_python_identity']=python_identity(process._handle)
            require(state['supervisor_python_identity']['sha256']==reader.PYTHON_SHA and state['supervisor_python_identity']['pid']==process.pid
                    and launched<=state['supervisor_python_identity']['created']<=time.time(),'supervisor Python binary/PID/creation differs')
            while process.poll() is None:
                path=options.run_root/'supervisor-report.json'
                if handle is None and path.exists():
                    report=json.loads(path.read_text())
                    if 'parent_python_identity' in report:handle=handle_factory(report['parent_pid'],report['parent_python_identity'])
                if options.artifact_dir.is_dir():manager_mirror.tick()
                if clock()-started>=OUTER_SECONDS:
                    state['first_error']=dict(type='TimeoutError',message='outer-budget-1840')
                    if options.run_root.is_dir():atomic_json(options.run_root/'stop.json',state['first_error'])
                    stop_parent_once()
                    if process.poll() is None:process.terminate()
                    break
                sleep(.1)
            state['supervisor_exit_code']=process.poll()
            path=options.run_root/'supervisor-report.json'
            verified=json.loads(path.read_text()) if path.exists() else {}
            state['success']=type(state['supervisor_exit_code']) is int and state['supervisor_exit_code']==0 and 'first_error' not in state
            state['success']=state['success'] and verified.get('success') is True and verified.get('source_manifest_sha256')==options.source_manifest_sha
    except BaseException as error:
        state.setdefault('first_error',failure(error))
        if options.run_root.is_dir():atomic_json(options.run_root/'stop.json',state['first_error'])
        stop_parent_once()
        if process is not None and process.poll() is None:process.terminate()
    finally:
        if handle is not None:
            if not state['success']:stop_parent_once()
            try:handle.close()
            except BaseException as error:state['success']=False;state['handle_close_error']=failure(error)
        atomic_json(output/'manager-report.json',state)
        try:
            remaining=max(0,OUTER_SECONDS-(clock()-started))
            require(remaining>0 and options.artifact_dir.is_dir(),'outer budget/artifact unavailable; manager copy unconfirmed')
            manager_mirror.finish(timeout=min(5,remaining/2))
            hashes={}
            for path in output.iterdir():
                if path.is_file() and path.suffix!='.tmp':
                    sha=digest(path);require(digest(options.artifact_dir/'manager'/path.name)==sha,'manager copy digest differs')
                    hashes[path.name]=sha
            atomic_json(options.artifact_dir/'manager-transfer-receipt.json',dict(source_manifest_sha256=options.source_manifest_sha,files=hashes))
        except BaseException as error:
            state['success']=False;state['manager_persist_error']=failure(error)
            atomic_json(output/'manager-report.json',state)
    return 0 if state['success'] else 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=('manager','supervisor','parent'),required=True);parser.add_argument('--ticket',required=True)
    for name in ('run-root','artifact-dir','source-manifest','internal-zip','public-zip','host-executable','host-type-library','expected-host-image'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--source-manifest-sha',required=True);parser.add_argument('--group-started',type=float)
    options=parser.parse_args(argv)
    for name in ('run_root','artifact_dir','source_manifest','internal_zip','public_zip','host_executable','host_type_library','expected_host_image'):
        setattr(options,name,getattr(options,name).resolve())
    require(sys.platform=='win32','Windows execution only; no portable native execution')
    workspace=Path('C:/Workspace').resolve()
    require(options.run_root.resolve()!=workspace and options.run_root.resolve().is_relative_to(workspace),'run root must be a new child of C:/Workspace')
    if options.role=='manager':return manager(options)
    if options.role=='supervisor':return supervisor(options)
    require(type(options.group_started) is float and math.isfinite(options.group_started),'explicit parent group clock required')
    verify_options(options)
    return parent(options,WindowsBackend(options))


if __name__=='__main__':raise SystemExit(main())
