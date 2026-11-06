"""Bounded LOCAL diagnostic runner; never kills SOLIDWORKS or another host.

Only the child Python created here can be terminated on a native/group timeout.
No retry, host restart, automatic rollback or user-document cleanup is attempted.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4

NATIVE_TIMEOUT_SECONDS = 600
GROUP_TIMEOUT_SECONDS = 1800
AUTHORIZATION_TIMEOUT_SECONDS = 10
WORKSPACE_ROOT = r'C:\Workspace'
IDENTITY_PROTOCOL = 'swcli-docprops-worker-v1'

# -I -S keeps source, user site, sitecustomize and .pth execution out of the
# pre-authorization process. No runpy/SWCLI/COM import occurs before the grant.
BOOTSTRAP = r'''
import json, os, sys, time
from pathlib import Path
config = json.loads(sys.argv[1])
normal = lambda value: os.path.normcase(str(Path(value).resolve()))
identity = {
    'protocol': 'swcli-docprops-worker-v1', 'nonce': config['nonce'],
    'pid': os.getpid(), 'parent_pid': os.getppid(),
    'executable': normal(sys.executable),
    'base_executable': normal(getattr(sys, '_base_executable', sys.executable)),
    'source_root': config['source_root'], 'script_args': config['script_args'],
    'owned_interface_size': config.get('owned_interface_size', 0),
    'site_packages': config['site_packages'], 'attach_pid': config['attach_pid'],
    'preauthorization_imports': sorted(name for name in sys.modules
        if name in ('runpy', 'pythoncom', 'swcli', 'win32com') or name.startswith(('swcli.', 'win32com.'))),
}
identity_path = Path(config['identity_file'])
temporary = identity_path.with_suffix('.tmp')
with temporary.open('x', encoding='utf-8') as stream:
    json.dump(identity, stream, ensure_ascii=True, allow_nan=False)
    stream.flush()
    os.fsync(stream.fileno())
os.rename(temporary, identity_path)
authorization_path = Path(config['authorization_file'])
deadline = time.monotonic() + 10.0
while not authorization_path.exists():
    if time.monotonic() >= deadline:
        raise SystemExit('worker authorization was not received within 10 seconds; script not executed')
    time.sleep(0.02)
authorization = json.loads(authorization_path.read_text(encoding='utf-8'))
expected_grant = {'protocol': 'swcli-docprops-worker-v1',
                  'authorized_by_pid': os.getppid(), 'identity': identity}
canonical = lambda value: json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))
if canonical(authorization) != canonical(expected_grant):
    raise SystemExit('worker authorization does not match this process; script not executed')
owned_interface = None
packet_size = config.get('owned_interface_size', 0)
if packet_size:
    if type(packet_size) is not int or not 0 < packet_size <= 65536:
        raise SystemExit('invalid owned interface size; script not executed')
    owned_interface = sys.stdin.buffer.read(packet_size + 1)
    if len(owned_interface) != packet_size:
        raise SystemExit('owned interface transfer incomplete; script not executed')
import site
for directory in config['site_packages']:
    site.addsitedir(directory)
sys.path.insert(0, str(Path(config['source_root']) / 'src'))
sys.argv = config['script_args']
import runpy
runpy.run_path(sys.argv[0], run_name='__main__',
               init_globals={'_SWCLI_OWNED_INTERFACE': owned_interface} if packet_size else None)
'''


def default_python():
    return str(Path(getattr(sys, '_base_executable', sys.executable)).resolve())


def normal_path(value):
    return os.path.normcase(str(Path(value).resolve()))


def driver_site_packages():
    import site
    return list(dict.fromkeys(normal_path(value) for value in site.getsitepackages() if Path(value).is_dir()))


def worker_config(args, script, source, driver):
    script_args = [str(script), '--attach-pid', str(args.attach_pid), '--stage', args.stage,
                   '--output', str(Path(args.output).resolve())]
    packet = getattr(args, 'owned_interface_data', None)
    if packet is not None:
        if type(packet) is not bytes or not 0 < len(packet) <= 65536 or not getattr(args, 'isolated_host', False):
            raise ValueError('owned interface requires bounded bytes and explicit isolation')
        script_args.append('--owned-interface-stdin')
    if getattr(args, 'isolated_host', False):
        script_args.append('--isolated-host')
    for flag, value in (('--swconst', args.swconst),
                        ('--part-template', getattr(args, 'part_template', None)),
                        ('--assembly-template', getattr(args, 'assembly_template', None)),
                        ('--drawing-template', args.drawing_template),
                        ('--font-typeface', args.font_typeface)):
        if value is not None:
            script_args += [flag, value]
    return {'nonce': uuid4().hex, 'source_root': normal_path(source), 'script_args': script_args,
            'site_packages': driver_site_packages(), 'attach_pid': args.attach_pid,
            'owned_interface_size': 0 if packet is None else len(packet),
            'identity_file': str(driver / 'worker-identity.json'),
            'authorization_file': str(driver / 'worker-authorized.json')}


def expected_identity(config, child_pid, executable):
    return {'protocol': IDENTITY_PROTOCOL, 'nonce': config['nonce'],
            'pid': child_pid, 'parent_pid': os.getpid(),
            'executable': normal_path(executable), 'base_executable': normal_path(executable),
            'source_root': config['source_root'], 'script_args': config['script_args'],
            'owned_interface_size': config.get('owned_interface_size', 0),
            'site_packages': config['site_packages'], 'attach_pid': config['attach_pid'],
            'preauthorization_imports': []}


def exact_json(first, second):
    return json.dumps(first, sort_keys=True, allow_nan=False, separators=(',', ':')) == json.dumps(
        second, sort_keys=True, allow_nan=False, separators=(',', ':'))


def authorize_worker(config, child, executable):
    """Grant once only to the exact process owned by this Popen object."""
    identity_path = Path(config['identity_file'])
    deadline = time.monotonic() + AUTHORIZATION_TIMEOUT_SECONDS
    while not identity_path.exists():
        if child.poll() is not None:
            raise ValueError('launcher exited before worker identity; no authorization')
        if time.monotonic() >= deadline:
            raise ValueError('worker identity timed out after 10 seconds; no authorization')
        time.sleep(0.02)
    identity = json.loads(identity_path.read_text(encoding='utf-8'))
    expected = expected_identity(config, child.pid, executable)
    if not exact_json(identity, expected):
        raise ValueError('worker identity/Popen PID mismatch; no authorization')
    if child.poll() is not None:
        raise ValueError('worker exited before authorization')
    path = Path(config['authorization_file'])
    if path.exists():
        raise ValueError('worker authorization file already exists; never authorize twice')
    temporary = path.with_suffix('.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump({'protocol': IDENTITY_PROTOCOL, 'authorized_by_pid': os.getpid(), 'identity': identity},
                  stream, ensure_ascii=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(temporary, path)
    return identity


class TraceProgress:
    def __init__(self, started):
        self.active = None
        self.started = self.last_progress = started
        self.offset = 0
        self.complete_records = 0
        self.error_records = 0

    def consume(self, path, now):
        if not path.exists():
            return
        with path.open('rb') as stream:
            stream.seek(self.offset)
            while True:
                start = stream.tell()
                line = stream.readline()
                if not line:
                    break
                if not line.endswith(b'\n'):
                    stream.seek(start)
                    break
                row = json.loads(line.decode('utf-8'))
                phase, label = row['phase'], row['call']
                if type(label) is not str or not label:
                    raise ValueError('native trace call label is missing')
                if phase == 'begin':
                    if self.active is not None:
                        raise ValueError('overlapping native trace calls')
                    self.active = {'call': label, 'observed_start': now}
                elif phase in ('end', 'error'):
                    if self.active is None or self.active['call'] != label:
                        raise ValueError('native trace terminal has no matching begin')
                    if 'elapsed_seconds' not in row or type(row['elapsed_seconds']) not in (int, float) or not 0 <= row['elapsed_seconds'] < NATIVE_TIMEOUT_SECONDS:
                        raise ValueError('native trace terminal exceeds its call budget')
                    self.error_records += int(phase == 'error')
                    self.active = None
                else:
                    raise ValueError('unknown native trace phase')
                self.offset = stream.tell()
                self.last_progress = now
                self.complete_records += 1

    def finish(self, path, now):
        self.consume(path, now)
        if not path.is_file() or path.stat().st_size != self.offset or self.active is not None or not self.complete_records or self.error_records:
            raise ValueError('final native trace is incomplete')
        if now - self.started >= GROUP_TIMEOUT_SECONDS:
            raise ValueError('group budget exceeded before final evidence')

    def limit_failure(self, now):
        if now - self.started >= GROUP_TIMEOUT_SECONDS:
            return 'group-timeout'
        start = self.active['observed_start'] if self.active else self.last_progress
        if now - start >= NATIVE_TIMEOUT_SECONDS:
            return 'native-timeout' if self.active else 'native-progress-timeout'
        return None


def run(args):
    output = Path(args.output).resolve()
    workspace = Path(WORKSPACE_ROOT).resolve()
    if output == workspace or workspace not in output.parents or output.exists():
        raise ValueError('calibration output must be a new path below C:\\Workspace')
    script = Path(args.script).resolve()
    source = Path(args.source_root).resolve()
    if not script.is_file() or not (source / 'src/swcli/__init__.py').is_file():
        raise ValueError('explicit trusted script and source snapshot are required')
    driver = output.parent / (output.name + '-driver')
    driver.mkdir(parents=True, exist_ok=False)
    executable = normal_path(args.python)
    if not Path(executable).is_file():
        raise ValueError('child Python must be an explicit executable file')
    config = worker_config(args, script, source, driver)
    command = [executable, '-I', '-S', '-c', BOOTSTRAP, json.dumps(config, ensure_ascii=True, allow_nan=False)]
    started = time.monotonic()
    progress = TraceProgress(started)
    receipt = {'success': False, 'full_acceptance_eligible': False, 'attach_pid': args.attach_pid,
               'native_timeout_seconds': NATIVE_TIMEOUT_SECONDS, 'group_timeout_seconds': GROUP_TIMEOUT_SECONDS,
               'host_termination_attempted': False, 'child_termination_attempted': False,
               'automatic_retry': False, 'automatic_rollback': False, 'output': str(output),
               'worker_authorized': False, 'authorization_timeout_seconds': AUTHORIZATION_TIMEOUT_SECONDS,
               'worker_identity_file': config['identity_file'], 'worker_authorization_file': config['authorization_file'],
               'child_executable': executable, 'driver_venv_prefix': normal_path(sys.prefix),
               'driver_site_packages': config['site_packages']}
    with (driver / 'stdout.log').open('wb') as stdout, (driver / 'stderr.log').open('wb') as stderr:
        packet = getattr(args, 'owned_interface_data', None)
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 stdin=subprocess.PIPE if packet is not None else subprocess.DEVNULL, bufsize=0)
        transfer_done, transfer_errors = threading.Event(), []
        def transfer_owned_interface():
            try:
                if child.stdin.write(packet) != len(packet):
                    raise OSError('short owned interface pipe write; no retry')
                child.stdin.close()
                transfer_done.set()
            except OSError as error:
                transfer_errors.append(type(error).__name__)  # never log capability bytes
        writer = None
        receipt['child_python_pid'] = child.pid
        failure = None
        try:
            receipt['worker_identity'] = authorize_worker(config, child, executable)
            receipt['worker_authorized'] = True
            if packet is not None:
                writer = threading.Thread(target=transfer_owned_interface, daemon=True)
                writer.start()
        except (OSError, ValueError, TypeError, KeyError) as error:
            failure = 'worker-authorization-failed: ' + str(error)
        while failure is None and child.poll() is None:
            now = time.monotonic()
            try:
                if transfer_errors:
                    raise ValueError('owned interface pipe transfer failed: ' + transfer_errors[0])
                progress.consume(output / 'trace.jsonl', now)
                failure = progress.limit_failure(now)
            except (OSError, ValueError, KeyError) as error:
                failure = 'invalid-native-trace: ' + str(error)
            if failure:
                break
            time.sleep(0.2)
        if failure is not None and child.poll() is None:
            # Only this Popen handle can be killed. An unapproved launcher child
            # receives no grant and exits at its own fixed 10-second deadline.
            child.kill()
            receipt['child_termination_attempted'] = True
        receipt['child_exit_code'] = child.wait(timeout=10)
        if packet is not None:
            if writer is not None:
                writer.join(timeout=1)
            if not transfer_done.is_set() and failure is None:
                failure = 'owned-interface-transfer-incomplete'
            receipt['owned_interface_transfer_completed'] = transfer_done.is_set()
            try:
                child.stdin.close()
            except OSError as error:
                if failure is None:
                    failure = 'owned-interface-pipe-close-failed: ' + type(error).__name__
    receipt['elapsed_seconds'] = time.monotonic() - started
    receipt['failure'] = failure
    receipt['trace_complete_records'] = progress.complete_records
    if failure is None:
        try:
            # Retain the producer's first cause and cleanup receipt even when
            # a completed error terminal must subsequently reject success.
            report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
            receipt['child_failure'] = report.get('failure')
            receipt['child_cleanup_errors'] = report.get('cleanup_errors')
            receipt['child_report_python_pid'] = report.get('python_process_id')
            if type(report.get('python_process_id')) is not int or report['python_process_id'] != child.pid:
                raise ValueError('terminal report Python PID differs from the authorized Popen worker')
            progress.finish(output / 'trace.jsonl', time.monotonic())
            receipt['success'] = (receipt['worker_authorized'] is True and receipt['child_exit_code'] == 0 and report['success'] is True
                and report['cleanup_errors'] == [] and report['manual_host_still_running'] is True
                and report['actual_attach_pid'] == args.attach_pid and progress.active is None)
        except (OSError, ValueError, KeyError) as error:
            receipt['failure'] = 'invalid-final-evidence: ' + str(error)
    else:
        receipt['cleanup_status'] = 'incomplete; inspect recorded test documents; no host cleanup attempted'
    receipt['trace_complete_records'] = progress.complete_records
    receipt['trace_error_records'] = progress.error_records
    (driver / 'driver.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=True))
    return 0 if receipt['success'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default=default_python(), help='explicit real child executable (default: sys._base_executable)')
    parser.add_argument('--script', default=str(Path(__file__).with_name('calibrate-document-properties.py')))
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--attach-pid', type=int, required=True)
    parser.add_argument('--stage', choices=('read', 'fonts', 'display', 'standards'), required=True)
    parser.add_argument('--swconst')
    parser.add_argument('--part-template')
    parser.add_argument('--assembly-template')
    parser.add_argument('--drawing-template')
    parser.add_argument('--font-typeface')
    parser.add_argument('--isolated-host', action='store_true', help='forward explicit target-instance isolation; never controls other SW processes')
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('this driver requires Windows; pure trace checks are portable')
    if args.attach_pid <= 0:
        parser.error('attach PID must be positive')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
