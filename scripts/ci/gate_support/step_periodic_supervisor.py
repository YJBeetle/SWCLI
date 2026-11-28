"""Durable evidence and 600/1800 supervision for the standalone periodic profile."""
import json
import math
import os
from pathlib import Path
import time

from .step_periodic_launch import verify_worker_receipt
from .step_periodic_evidence import PLAN, READER_SCOPE

NATIVE_SECONDS = 600
GROUP_SECONDS = 1800


def error(exc):
    row = dict(type=type(exc).__name__, message=str(exc))
    hresult = getattr(exc, 'hresult', None)
    if type(hresult) is int:row['hresult'] = hresult
    native = getattr(exc, 'native_error', None)
    if isinstance(native, dict):row['native_error'] = native
    return row


def durable_json(path, value):
    """Atomic report replacement in the new evidence directory, with flushed bytes."""
    temporary = path.with_name(path.name + '.writing')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():temporary.unlink()


class Recorder:
    def __init__(self, output, report):
        self.output, self.report, self.sequence = Path(output), report, 0
        self.cleanup_depth = 0
        self.calls = []
        self.trace = (self.output/'trace.jsonl').open('x', encoding='utf-8', buffering=1)

    def evidence_failure(self, stage, exc):
        self.report.setdefault('evidence_errors', []).append(dict(stage=stage, error=error(exc)))

    def persist(self):durable_json(self.output/'report.json', self.report)

    def safe_persist(self):
        try:self.persist()
        except Exception as exc:self.evidence_failure('persist', exc)

    def fail(self, stage, exc):
        # Preserve the first observed exception, but keep a validated business
        # error receipt primary when cleanup failed before that receipt returned.
        original=exc;seen=set()
        while id(original) not in seen:
            seen.add(id(original));restore=getattr(original,'restore_error',None)
            if restore is not None:
                row=dict(stage='CommandInProgress',error=error(restore))
                if row not in self.report.setdefault('cleanup_errors',[]):self.report['cleanup_errors'].append(row)
            previous=getattr(original,'operation_error',None)
            if previous is None:break
            original=previous
        row=dict(stage=stage,**error(original))
        if isinstance(getattr(original,'native_error',None),dict):
            if 'failure' in self.report and self.report['failure']!=row:self.report.setdefault('failure_before_business_receipt',self.report['failure'])
            self.report['failure']=row
        else:self.report.setdefault('failure',row)
        self.report['success']=False

    def event(self, identity, name, phase, started, exc=None):
        row = dict(id=identity, call=name, phase=phase, time=time.time(), started=started, clock='monotonic', observed=time.monotonic())
        if exc is not None:row['error'] = error(exc)
        self.trace.write(json.dumps(row, allow_nan=False)+'\n');self.trace.flush();os.fsync(self.trace.fileno())

    def call(self, name, function, *, cleanup=False):
        cleanup = cleanup or self.cleanup_depth > 0 or 'restore' in name.lower()
        if not cleanup and self.report.get('evidence_errors'):
            exc=RuntimeError('evidence unavailable; further business calls refused')
            self.fail(name,exc);raise exc
        self.sequence += 1;identity=self.sequence;started=time.monotonic();self.calls.append(name)
        try:
            self.event(identity,name,'begin',started)
            self.persist()
        except Exception as exc:
            self.evidence_failure('before:'+name,exc)
            if not cleanup:
                self.fail(name,exc);raise
        try:
            if cleanup:self.cleanup_depth += 1
            try:result=function()
            finally:
                if cleanup:self.cleanup_depth -= 1
        except BaseException as exc:
            self.report.setdefault('first_observed_exception',dict(stage=name,error=error(exc)))
            if cleanup:self.report.setdefault('cleanup_errors',[]).append(dict(stage=name,error=error(exc)))
            else:self.fail(name,exc)
            try:self.event(identity,name,'error',started,exc)
            except Exception as disk:self.evidence_failure('error:'+name,disk)
            self.safe_persist()
            raise
        try:self.event(identity,name,'end',started)
        except Exception as exc:
            self.evidence_failure('after:'+name,exc)
            if not cleanup:self.fail(name,exc);raise
        if not cleanup and self.report.get('evidence_errors'):
            exc=RuntimeError('evidence failed during operation; business calls closed')
            self.fail(name,exc);raise exc
        return result

    def close(self):
        try:self.trace.close()
        except Exception as exc:self.evidence_failure('close-trace',exc)


def trace_open_calls(raw):
    """Reject corrupted complete lines; only an incomplete last write may be ignored."""
    if len(raw)>32*1024*1024:raise ValueError('trace exceeds profile bound')
    lines=raw.splitlines(keepends=True);stack=[];seen=set()
    for index,line in enumerate(lines):
        if not line.endswith(b'\n') and index==len(lines)-1:break
        row=json.loads(line)
        if (type(row.get('id')) is not int or row['id']<=0 or not isinstance(row.get('call'),str)
                or type(row.get('started')) not in (int,float) or not math.isfinite(row['started']) or row.get('clock')!='monotonic'
                or type(row.get('observed')) not in (int,float) or not math.isfinite(row['observed'])
                or row['observed'] < row['started']):
            raise ValueError('invalid trace identity/clock')
        if row['phase']=='begin':
            if row['id'] in seen:raise ValueError('duplicate trace identity')
            seen.add(row['id']);stack.append(row)
        elif row['phase'] in ('end','error'):
            if not stack or stack[-1]['id']!=row['id'] or stack[-1]['call']!=row['call'] or stack[-1]['started']!=row['started']:raise ValueError('unpaired trace frame')
            stack.pop()
        else:raise ValueError('unknown trace phase')
    return stack


def timeout_reason(elapsed, stack, now):
    if elapsed>=GROUP_SECONDS:return 'group-1800s'
    if stack and now-min(row['started'] for row in stack)>=NATIVE_SECONDS:return 'native-600s'
    return None


def terminal_result(output, returncode, *, public_writer):
    import hashlib
    report_path=output/'report.json';trace_path=output/'trace.jsonl'
    report=json.loads(report_path.read_text(encoding='utf-8'))
    terminal=json.loads((output/'worker-finished.json').read_text(encoding='utf-8'))
    if terminal['report_sha256']!=hashlib.sha256(report_path.read_bytes()).hexdigest() or terminal['trace_sha256']!=hashlib.sha256(trace_path.read_bytes()).hexdigest():
        raise ValueError('terminal evidence digest differs')
    raw=trace_path.read_bytes();stack=trace_open_calls(raw)
    if not raw or not raw.endswith(b'\n') or stack:raise ValueError('trace empty or unfinished')
    if any(type(row['split_periodic_faces']) is not bool for row in report['cases']) or tuple(
        (row['protocol'], row['split_periodic_faces']) for row in report['cases']
    ) != PLAN:
        raise ValueError('four-case plan differs')
    if (report.get('diagnostic_case') != READER_SCOPE or report.get('public_writer') != public_writer
            or report.get('full_acceptance_eligible') is not False):
        raise ValueError('independent public writer input receipt differs')
    done = all(case.get('success') is True and case.get('export_complete') is True
               and case.get('import_started') is True for case in report['cases'])
    passed=(returncode==0 and terminal.get('returncode')==0 and report.get('complete') is True and report.get('success') is True
            and terminal.get('success') is True and report.get('owned_exit_confirmed') is True and not report.get('cleanup_errors') and not report.get('evidence_errors')
            and done)
    if passed:
        from collections import Counter
        rows = [json.loads(line) for line in raw.splitlines()]
        if any(row['phase'] != 'begin' and row['observed'] - row['started'] >= NATIVE_SECONDS
               for row in rows):
            raise ValueError('completed call exceeded native-600s')
        counts = Counter(row['call'] for row in rows if row['phase'] == 'begin')
        completed_language_check = any(row['call'] == 'verify-calibration-language' and row['phase'] == 'end'
                                       for row in rows)
        if (report.get('host', {}).get('language') != 'english'
                or counts['verify-calibration-language'] != 1 or not completed_language_check):
            raise ValueError('independent readback language receipt missing or different')
        if (report.get('public_writer_verified') is not True
                or report['public_writer_host_pid'] == report['host']['process_id']
                or any(case['export_started'] is not False for case in report['cases'])
                or counts['verify-terminal-public-writer'] != 1):
            raise ValueError('independent public readback host or writer evidence differs')
        required = {
            'LoadFile4': len(PLAN),
            'GetImportFileData': len(PLAN),
            'native:document-export:IModelDocExtension.SaveAs3': 0,
            'native:native-save-as:IModelDocExtension.SaveAs3': len(PLAN),
        }
        unexpected_saves = any('SaveAs' in name and name not in required for name in counts)
        if unexpected_saves or any(counts[name] != count for name, count in required.items()):
            raise ValueError('unique export/import and native save call counts differ')
    return passed,report



def early_worker_failure(output, process):
    failure_path = output / 'worker-startup-failure.json'
    try:
        startup = json.loads(failure_path.read_text(encoding='utf-8'))
        if (startup['stage'] == 'worker-startup' and startup['worker_pid'] == process.pid
                and isinstance(startup['error']['type'], str) and isinstance(startup['error']['message'], str)):
            return dict(stage=startup['stage'], **startup['error'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # The failure can precede all JSON writes. Keep stderr rather than replacing
    # the worker error with FileNotFoundError for its absent native report.
    try:
        with (output/'worker.stderr.log').open('rb') as stream:
            stream.seek(max(0, os.fstat(stream.fileno()).st_size - 4096))
            lines = stream.read().decode('utf-8', errors='replace').strip().splitlines()
    except OSError:
        lines = []
    return dict(stage='worker-startup', type='WorkerExitedBeforeReport',
                message=lines[-1] if lines else f'worker exited {process.returncode} before writing a native report')


def completed_worker(output, process, result, launch):
    if process.returncode != 0 and not (output/'report.json').is_file():
        result['failure'] = early_worker_failure(output, process)
        return False, {}
    if launch is not None and (process.returncode == 0 or (output/'worker-supervision.json').exists()):
        try:
            proof = json.loads((output/'worker-supervision.json').read_text(encoding='utf-8'))
            verify_worker_receipt(proof, launch, process.pid)
            result['supervision_verified'] = True
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            result['supervision_error'] = error(exc)
            if process.returncode == 0:
                result['failure'] = dict(stage='worker-supervision', **error(exc))
                return False, {}
    try:
        return terminal_result(output, process.returncode,
                               public_writer=launch.get('public_writer') if launch else None)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result['terminal_evidence_error'] = error(exc)
        try:
            report = json.loads((output/'report.json').read_text(encoding='utf-8'))
            failure = report.get('failure')
        except (OSError, ValueError, AttributeError):
            report, failure = {}, None
        result['failure'] = failure if isinstance(failure, dict) else error(exc)
        return False, report


def supervise(command, output, *, launch=None, environment=None,
              spawn=None, monotonic=None, now=None, sleep=None):
    """Launch one child; kill only that child on timeout/corrupt evidence. Never kill CAD by name."""
    import subprocess
    spawn=subprocess.Popen if spawn is None else spawn
    monotonic=time.monotonic if monotonic is None else monotonic
    now=monotonic if now is None else now
    sleep=time.sleep if sleep is None else sleep
    output=Path(output);started=monotonic()
    result=dict(success=False,worker_attempts=1,native_timeout_seconds=NATIVE_SECONDS,group_timeout_seconds=GROUP_SECONDS,
                native_process_exit_unconfirmed=True,child_started=False)
    process=None;code=1
    with (output/'worker.stdout.log').open('xb') as stdout,(output/'worker.stderr.log').open('xb') as stderr:
        try:
            options = {}
            if launch is not None:
                options.update(executable=launch['launch_executable'], stdin=subprocess.PIPE, env=environment)
            process = spawn(command, stdout=stdout, stderr=stderr, **options)
            result.update(worker_pid=process.pid, child_started=True)
            if launch is not None:
                try:
                    with process.stdin as handoff:
                        handoff.write(f'{process.pid}\n'.encode('ascii'))
                except OSError as exc:
                    result['launch_pipe_error'] = error(exc)
            reason=None
            while process.poll() is None:
                trace=output/'trace.jsonl'
                try:stack=trace_open_calls(trace.read_bytes()) if trace.exists() else []
                except Exception as exc:
                    reason='invalid-trace';result['trace_error']=error(exc);break
                reason=timeout_reason(monotonic()-started,stack,now())
                if reason:break
                sleep(0.25)
            if reason:
                result['failure']=dict(type='SupervisorStopped',message=reason)
                result['timeout']=reason in ('native-600s','group-1800s')
                process.kill()
                try:process.wait(timeout=10)
                except Exception as exc:result['worker_exit_error']=error(exc)
                code=124 if result.get('timeout') else 1
            else:
                result['worker_returncode']=process.returncode
                passed,report=completed_worker(output,process,result,launch)
                if passed and monotonic()-started >= GROUP_SECONDS:
                    result['failure'] = dict(type='SupervisorStopped', message='group-1800s')
                    result['timeout'] = True
                    passed = False
                result.update(success=passed,native_process_exit_unconfirmed=report.get('owned_exit_confirmed') is not True,
                              worker_failure=report.get('failure'),source_commit=report.get('source_commit'))
                code=0 if passed else (124 if result.get('timeout') else 1)
        except Exception as exc:
            result['failure']=error(exc)
            if process is not None and process.poll() is None:
                process.kill()
                try:process.wait(timeout=10)
                except Exception as cleanup:result['worker_exit_error']=error(cleanup)
        finally:
            result['supervisor_returncode']=code
            durable_json(output/'supervisor.json',result)
    return code,result
