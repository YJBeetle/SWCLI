"""One owned public-CLI host with 1800s group and 600s request budgets."""
import argparse
import importlib.util
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


def group_expired(started,now):return now-started>1800


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
    started=time.monotonic();daemon=worker=None;ready=False
    failure=None
    with (output/'daemon.stdout').open('wb') as stdout,(output/'daemon.stderr').open('wb') as stderr:
        try:
            command=[sys.executable,'-I','-m','swcli','daemon','serve','--host','127.0.0.1','--port',str(port),'--startup-timeout','120','--tray','off']
            report['daemon_command']=command;save()
            daemon=subprocess.Popen(command,stdout=stdout,stderr=stderr,env={**os.environ,'SWCLI_TRACE_NATIVE_CALLS':'1'})
            report['daemon_pid']=daemon.pid;save()
            while time.monotonic()-started<=180:
                evidence.require(daemon.poll() is None,'owned daemon exited during startup; no replacement')
                if '"action": "daemon.serve"' in (output/'daemon.stdout').read_text(encoding='utf-8',errors='replace'):
                    ready=True;break
                time.sleep(1)
            evidence.require(ready,'owned daemon readiness deadline exceeded')
            command=[sys.executable,'-I',str(Path(__file__).with_name('verify-document-unit-profile.py')),'--output-dir',str(output/'cli'),'--fixture-dir',str(args.fixture_dir.resolve()),'--endpoint',endpoint,'--prior-pids',str(output/'prior-pids.json')]
            report['public_command']=command;save()
            with (output/'public.stdout').open('wb') as public_stdout,(output/'public.stderr').open('wb') as public_stderr:
                worker=subprocess.Popen(command,stdout=public_stdout,stderr=public_stderr)
                while worker.poll() is None:
                    evidence.require(not group_expired(started,time.monotonic()),'public group exceeded 1800s')
                    time.sleep(1)
                evidence.require(not group_expired(started,time.monotonic()),'public group exceeded 1800s')
                report['public_exit_code']=worker.returncode;save()
                evidence.require(worker.returncode==0,'public CLI acceptance failed; see original records')
            report['success']=True
        except BaseException as error:
            failure=error;report['failure']=dict(type=type(error).__name__,message=str(error))
            try:save()
            except BaseException as evidence_error:report['evidence_error']=str(evidence_error)
        finally:
            if worker is not None and worker.poll() is None:worker.kill();worker.wait()
            if daemon is not None and ready and daemon.poll() is None:
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
                    after=report['pids_after']=solidworks_process_ids()
                    evidence.require(sorted(after)==sorted(before),'owned public host leaked or changed preexisting PID inventory')
                except BaseException as error:
                    report['cleanup_errors'].append(dict(type=type(error).__name__,message=str(error)))
                    if failure is None:failure=error
            if daemon is not None and daemon.poll() is None:
                # Only our retained Python process; never send stop to an
                # unproven endpoint after startup failure. Native leftovers fail.
                daemon.terminate()
                try:daemon.wait(timeout=30)
                except BaseException as error:report['cleanup_errors'].append(dict(stage='owned-daemon-exit',message=str(error)))
                report['cleanup_errors'].append(dict(stage='owned-daemon-termination',message='graceful shutdown was not confirmed'))
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
    execute(parser.parse_args())

if __name__=='__main__':main()
