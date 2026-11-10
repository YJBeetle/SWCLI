"""One owned public-CLI host with 1800s group and 600s request budgets."""
import argparse
from datetime import datetime,timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from swcli.host_processes import solidworks_process_ids

spec=importlib.util.spec_from_file_location('_unit_public_evidence',Path(__file__).with_name('calibrate-document-unit-profile.py'))
evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)
spec=importlib.util.spec_from_file_location('_units_owned_native',Path(__file__).parent/'gate_support/unit_owned_native.py')
owned_native=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned_native)


def group_expired(started,now):return now-started>1800


def capture_owned_native_process(pid):
    import win32api
    import win32con
    return win32api.OpenProcess(win32con.SYNCHRONIZE,False,pid)


def wait_owned_native_process(handle):
    import win32event
    status=win32event.WaitForSingleObject(handle,10000)
    evidence.require(status==win32event.WAIT_OBJECT_0,'owned native host exit was not confirmed within 10s')


def execute(args):
    fixture=json.loads((args.fixture_dir/'report.json').read_text())
    evidence.require(fixture.get('success') is True,'native calibration must succeed before starting public host')
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=False)
    report=dict(success=False,profile='units-public-host-v1',full_acceptance_eligible=False,cleanup_errors=[],source_commit=os.environ.get('GITHUB_SHA'))
    def save():evidence.durable(output/'host-report.json',report)
    before=report['pids_before']=solidworks_process_ids();evidence.durable(output/'prior-pids.json',before);save()
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    endpoint=f'127.0.0.1:{port}';report['endpoint']=endpoint;save()
    started=time.monotonic();daemon=worker=None;ready=False;native_process=None
    failure=None;enhanced=bool(getattr(args,'write_acceptance',False));native_capture_attempted=False;frontend_process=None;frontend_capture_attempted=False
    def observe_identity(role,value):
        report.setdefault('identity_observations',[]).append(dict(role=role,**value));save()
    def capture_identity(role,*arguments,**options):
        try:return owned_native.capture(*arguments,**options,observe=lambda value:observe_identity(role,value))
        except BaseException as error:
            report['identity_capture_failure']=dict(role=role,type=type(error).__name__,message=str(error),observation=getattr(error,'identity_observation',None),observation_error=getattr(error,'identity_observation_error',None),handle_close_error=getattr(error,'identity_handle_close_error',None))
            raise
    def capture_early(required=False):
        nonlocal native_process,native_capture_attempted
        if not enhanced or native_capture_attempted:return
        try:observed=json.loads((output/'cli/public-unit-profile.json').read_text())
        except (FileNotFoundError,json.JSONDecodeError):
            if required:raise RuntimeError('native ownership report unavailable')
            return
        if 'host' not in observed:
            if required:raise RuntimeError('native ownership is not yet proven')
            return
        native_capture_attempted=True;host=observed['host'];pid=host['process_id']
        evidence.require(type(pid) is int and pid>0 and pid not in before and host.get('owned_by_daemon') is True and host.get('visible') is False and host.get('shared_interactive') is False,'native process ownership is not proven')
        native_process,identity=capture_identity('native-host',pid,report['daemon_launch_utc_timestamp'])
        report.update(owned_native_pid=pid,owned_native_identity=identity,native_handle_captured_early=True);save()
    def capture_frontend_if_available():
        nonlocal frontend_process,frontend_capture_attempted
        if not enhanced or frontend_capture_attempted:return
        try:observed=json.loads((output/'cli/public-unit-profile.json').read_text())
        except (FileNotFoundError,json.JSONDecodeError):return
        frontend=observed.get('cli_frontend')
        if not frontend or 'ready' not in frontend:return
        frontend_capture_attempted=True
        helper=(Path(__file__).parent/'gate_support/unit_cli_worker.py').resolve()
        evidence.require(frontend['helper_path']==str(helper) and frontend['helper_sha256']==hashlib.sha256(helper.read_bytes()).hexdigest() and frontend['pid']==frontend['ready']['pid'] and frontend['command']==[sys.executable,'-I',str(helper)],'CLI frontend ownership metadata differs')
        if frontend.get('exit_confirmed') is True:
            report['cli_frontend_exit_confirmed_by_public']=frontend;save();return
        frontend_process,identity=capture_identity('cli-frontend',frontend['pid'],frontend['launch_utc_timestamp'],sys.executable,terminate_right=False)
        report['cli_frontend_retained_identity']=identity;save()
    with (output/'daemon.stdout').open('wb') as stdout,(output/'daemon.stderr').open('wb') as stderr:
        try:
            command=[sys.executable,'-I','-m','swcli','daemon','serve','--host','127.0.0.1','--port',str(port),'--startup-timeout','120','--tray','off']
            report['daemon_command']=command;save()
            report['daemon_launch_utc_timestamp']=datetime.now(timezone.utc).timestamp();save()
            daemon=subprocess.Popen(command,stdout=stdout,stderr=stderr,env={**os.environ,'SWCLI_TRACE_NATIVE_CALLS':'1'})
            report['daemon_pid']=daemon.pid;save()
            while time.monotonic()-started<=180:
                evidence.require(daemon.poll() is None,'owned daemon exited during startup; no replacement')
                if '"action": "daemon.serve"' in (output/'daemon.stdout').read_text(encoding='utf-8',errors='replace'):
                    ready=True;break
                time.sleep(1)
            evidence.require(ready,'owned daemon readiness deadline exceeded')
            public_script='verify-document-unit-writes.py' if getattr(args,'write_acceptance',False) else 'verify-document-unit-profile.py'
            command=[sys.executable,'-I',str(Path(__file__).with_name(public_script)),'--output-dir',str(output/'cli'),'--fixture-dir',str(args.fixture_dir.resolve()),'--endpoint',endpoint,'--prior-pids',str(output/'prior-pids.json')]
            report['public_command']=command;save()
            with (output/'public.stdout').open('wb') as public_stdout,(output/'public.stderr').open('wb') as public_stderr:
                worker=subprocess.Popen(command,stdout=public_stdout,stderr=public_stderr)
                while worker.poll() is None:
                    capture_early();capture_frontend_if_available()
                    evidence.require(not group_expired(started,time.monotonic()),'public group exceeded 1800s')
                    time.sleep(1)
                capture_early(required=True)
                evidence.require(not group_expired(started,time.monotonic()),'public group exceeded 1800s')
                report['public_exit_code']=worker.returncode;save()
                evidence.require(worker.returncode==0,'public CLI acceptance failed; see original records')
            report['success']=True
        except BaseException as error:
            failure=error;report['failure']=dict(type=type(error).__name__,message=str(error))
            try:save()
            except BaseException as evidence_error:report['evidence_error']=str(evidence_error)
        finally:
            if worker is not None and worker.poll() is None:
                try:worker.kill();worker.wait(timeout=10)
                except BaseException as error:
                    report['cleanup_errors'].append(dict(stage='owned-public-process-exit',type=type(error).__name__,message=str(error)))
                    if failure is None:failure=error
            if daemon is not None and ready and daemon.poll() is None:
                try:
                    if enhanced:evidence.require(native_process is not None,'no native handle retained before public exit; do not reopen PID')
                    else:
                        cli=json.loads((output/'cli/public-unit-profile.json').read_text())
                        host=cli['host'];pid=host['process_id']
                        evidence.require(type(pid) is int and pid>0 and pid not in before
                            and host.get('owned_by_daemon') is True and host.get('visible') is False
                            and host.get('shared_interactive') is False,'native process ownership is not proven')
                        report['owned_native_pid']=pid;save()
                        native_process=capture_owned_native_process(pid)
                except BaseException as error:
                    report['cleanup_errors'].append(dict(stage='capture-owned-native-process',type=type(error).__name__,message=str(error)))
                    if failure is None:failure=error
                try:
                    # Exactly one shutdown request, never restart/reattach/fallback.
                    stop=[sys.executable,'-I','-m','swcli','--endpoint',endpoint,'--request-timeout','10','daemon','stop','--json']
                    report['stop_command']=stop
                    try:save()
                    except BaseException as evidence_error:report['cleanup_errors'].append(dict(stage='persist-stop',message=str(evidence_error)))
                    result=subprocess.run(stop,capture_output=True,timeout=30)
                    (output/'stop.stdout').write_bytes(result.stdout);(output/'stop.stderr').write_bytes(result.stderr)
                    report['stop_exit_code']=result.returncode
                    evidence.require(result.returncode==0,'owned daemon shutdown failed')
                    evidence.require(daemon.wait(timeout=30)==0,'owned daemon exit failed')
                    evidence.require(native_process is not None,'owned native process handle unavailable')
                    wait_owned_native_process(native_process)
                    report['owned_native_exit_confirmed']=True;save()
                    after=report['pids_after']=solidworks_process_ids()
                    evidence.require(sorted(after)==sorted(before),'owned public host leaked or changed preexisting PID inventory')
                except BaseException as error:
                    report['cleanup_errors'].append(dict(type=type(error).__name__,message=str(error)))
                    if failure is None:failure=error
            if daemon is not None and daemon.poll() is None:
                # Only our retained Python process; never send stop to an
                # unproven endpoint after startup failure. Native leftovers fail.
                try:
                    daemon.terminate();daemon.wait(timeout=30)
                except BaseException as error:
                    report['cleanup_errors'].append(dict(stage='owned-daemon-exit',type=type(error).__name__,message=str(error)))
                    if failure is None:failure=error
                report['cleanup_errors'].append(dict(stage='owned-daemon-termination',message='graceful shutdown was not confirmed'))
            if enhanced and native_process is not None and not report.get('owned_native_exit_confirmed'):
                try:
                    if not owned_native.exited(native_process):
                        report['forced_native_termination_attempted']=True
                        report['cleanup_errors'].append(dict(stage='forced-native-termination',message='emergency termination of this retained owned host; acceptance remains failed'));save()
                        owned_native.terminate(native_process,report['owned_native_identity'])
                        report['forced_native_termination_returned']=True
                    wait_owned_native_process(native_process)
                    report['owned_native_exit_confirmed']=True
                    after=report['pids_after']=solidworks_process_ids()
                    evidence.require(sorted(after)==sorted(before),'owned native exit changed preexisting PID inventory')
                except BaseException as error:
                    report['cleanup_errors'].append(dict(stage='owned-native-emergency-exit',type=type(error).__name__,message=str(error)))
                    if failure is None:failure=error
            if frontend_process is not None:
                try:
                    # Read-only retained handle: EOF on public-parent exit must close it.
                    # No helper PID search, replacement, or extra termination rights.
                    wait_owned_native_process(frontend_process)
                    report['cli_frontend_exit_confirmed_by_wrapper']=True
                except BaseException as error:
                    report['cleanup_errors'].append(dict(stage='cli-frontend-exit',type=type(error).__name__,message=str(error)))
                    if failure is None:failure=error
                finally:
                    try:frontend_process.Close()
                    except BaseException as error:
                        report['cleanup_errors'].append(dict(stage='close-cli-frontend-handle',type=type(error).__name__,message=str(error)))
                        if failure is None:failure=error
            if native_process is not None:
                try:native_process.Close()
                except BaseException as error:
                    report['cleanup_errors'].append(dict(stage='close-native-process-handle',message=str(error)))
                    if failure is None:failure=error
            report['duration_seconds']=time.monotonic()-started
            if report['duration_seconds']>1800:
                report['cleanup_errors'].append(dict(stage='group-budget',message='public group exceeded 1800s including shutdown'))
            report['success']=report['success'] and not report['cleanup_errors']
            try:save()
            except BaseException as evidence_error:
                if failure is None:failure=evidence_error
    if failure is not None:raise failure
    evidence.require(report['success'],'public host lifecycle or evidence failed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--fixture-dir',type=Path,required=True)
    parser.add_argument('--write-acceptance',action='store_true',help='Verify only manually reviewed finite public write domains')
    execute(parser.parse_args())

if __name__=='__main__':main()
