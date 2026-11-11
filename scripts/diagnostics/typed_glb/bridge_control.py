"""Private, one-use existing-COM-object transport. Import is portable and zero CAD.

COM work and release stay on the caller's STA. The I/O thread never touches COM.
OBJREF payloads and session nonce are never written to a receipt or trace.
"""
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import threading
import time

MAX_PARCEL = 1024 * 1024
MAX_FRAME = 1500000
ROLES = ('app', 'document', 'extension')
PIA_SHA = 'a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1'
EXE_SHA = '911309f7494e806f22914bab40aa65531c01b45888ec482ac555fbd8b4f0a18b'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_exact(stream, length):
    require(type(length) is int and 0 <= length <= MAX_FRAME, 'frame length outside limit')
    chunks = bytearray()
    while len(chunks) < length:
        block = stream.read(length - len(chunks))
        if not block:
            raise EOFError('pipe closed before complete frame')
        chunks.extend(block)
    return bytes(chunks)


def send(stream, message):
    data = json.dumps(message, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    require(0 < len(data) <= MAX_FRAME, 'frame outside limit')
    data = struct.pack('<I', len(data)) + data
    while data:
        count = stream.write(data)
        require(type(count) is int and 0 < count <= len(data), 'short/invalid pipe write')
        data = data[count:]
    stream.flush()


class HelperTerminated(RuntimeError):
    """A same-session terminal result is a failure, never an identity ACK."""
    def __init__(self, result, awaiting):
        self.receipt = result
        self.awaiting = awaiting
        reason = result.get('first_error') or 'helper terminated without a first_error'
        super().__init__('helper terminal result while awaiting ' + awaiting + ': ' + str(reason)
                         + '; HRESULT=' + str(result.get('hresult')))


def receive(stream, nonce, kind, role=None):
    length, = struct.unpack('<I', read_exact(stream, 4))
    require(0 < length <= MAX_FRAME, 'frame outside limit')
    message = json.loads(read_exact(stream, length).decode('utf-8'))
    require(type(message) is dict and message.get('nonce') == nonce, 'frame nonce mismatch')
    if message.get('kind') == 'result' and kind != 'result':
        require(message.get('role') is None and type(message.get('receipt')) is dict, 'malformed terminal result')
        raise HelperTerminated(message['receipt'], kind + (':' + role if role else ''))
    require(message.get('kind') == kind and message.get('role') == role, 'frame kind/role mismatch')
    return message


class ParcelLedger:
    """Only packets known never permitted can be released by the originating STA."""
    def __init__(self):
        self.states = {role: 'not_marshaled' for role in ROLES}

    def transition(self, role, previous, current):
        require(role in ROLES and self.states[role] == previous, 'invalid parcel state transition')
        self.states[role] = current

    def releasable(self):
        return [role for role in ROLES if self.states[role] in ('marshaled', 'buffered')]

    def uncertain(self):
        return [role for role in ROLES if self.states[role] == 'consumption_uncertain']


def process_identity(pid):
    """Exact kernel FILETIME; no floating point timestamp conversion."""
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        size = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return dict(created_filetime=(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                    exe_path=path.value, exe_sha256=digest(path.value))
    finally:
        kernel.CloseHandle(handle)


def snapshot(app, document, source, source_sha):
    from swcli.hosts.windows import _com_value as value
    from swcli.hosts.windows_custom_properties import _state
    pid = value(app, 'GetProcessID')
    require(type(pid) is int and pid > 0, 'actual host PID unavailable')
    result = dict(pid=pid, **process_identity(pid))
    result.update(runtime=value(app, 'RevisionNumber'), document_count=value(app, 'GetDocumentCount'))
    for name, key in (('Visible', 'visible'), ('CommandInProgress', 'command_in_progress'),
                      ('UserControl', 'user_control'), ('UserControlBackground', 'background')):
        result[key] = value(app, name)
        require(type(result[key]) is bool, 'host boolean unreadable: ' + name)
    kind, stamp, modified, config = _state(document)
    names = value(document, 'GetConfigurationNames')
    require(isinstance(names, (list, tuple)) and 0 < len(names) <= 1000 and all(type(x) is str and x for x in names)
            and len(set(names)) == len(names), 'configuration names unreadable')
    sketches = value(document, 'SketchManager')
    require(sketches is not None, 'sketch manager unreadable')
    same = app.IsSame(document, value(app, 'ActiveDoc'))
    require(type(same) is int and same == 1, 'foreground identity differs')
    result.update(path=value(document, 'GetPathName'), title=value(document, 'GetTitle'), document_type=kind,
                  update_stamp=stamp, modified=modified, configuration=config, configurations=list(names),
                  read_only=value(document, 'IsOpenedReadOnly'), view_only=value(document, 'IsOpenedViewOnly'),
                  active_sketch=value(sketches, 'ActiveSketch') is not None, foreground_same=same,
                  source_sha256=digest(source))
    require(result['exe_sha256'] == EXE_SHA and result['document_count'] == 1 and type(result['document_count']) is int,
            'owned installation/document count differs')
    require(not result['visible'] and kind == 1 and modified is False and result['read_only'] is False
            and result['view_only'] is False and not result['active_sketch'] and result['source_sha256'] == source_sha,
            'expected clean saved hidden writable part outside sketch edit')
    require(str(source) == result['path'] and config in names and isinstance(result['runtime'], str)
            and isinstance(result['title'], str) and result['title'], 'source/document identity differs')
    return result


def verify_build(helper):
    helper = Path(helper).resolve()
    record = json.loads((helper.parent / 'build.json').read_text(encoding='utf-8-sig'))
    require(record.get('schema') == 'swcli.typed-glb-build.v1' and record.get('success') is True
            and record.get('native_compile') is True and record.get('pia_sha256') == PIA_SHA
            and record.get('helper_sha256') == digest(helper), 'reviewed Windows build receipt differs')
    require(record.get('sources') == {name: digest(Path(__file__).parent / name)
                                    for name in ('BridgeCore.cs', 'TypedGlbBridge.cs')}, 'compiled helper sources differ')
    require(digest(helper.parent / 'SolidWorks.Interop.sldworks.dll') == PIA_SHA, 'copied installed PIA differs')
    return record


def io_session(stream, nonce, mode, expected, output, payloads, ledger, receipt):
    """Transport state machine; all native bytes stay in memory."""
    def expect(kind, role=None):
        try:
            return receive(stream, nonce, kind, role)
        except HelperTerminated as error:
            receipt['helper_result'] = error.receipt
            receipt['protocol_terminal'] = dict(awaiting=error.awaiting, kind='result')
            raise
    send(stream, dict(kind='hello', nonce=nonce, mode=mode, expected=expected, output=output))
    expect('ready')
    for role in ROLES:
        send(stream, dict(kind='parcel', nonce=nonce, role=role, data=base64.b64encode(payloads[role]).decode('ascii')))
        expect('prepared', role)
        ledger.transition(role, 'marshaled', 'buffered')
        # Set this BEFORE writing consume: a disconnect cannot establish nonconsumption.
        ledger.transition(role, 'buffered', 'consumption_uncertain')
        send(stream, dict(kind='consume', nonce=nonce, role=role))
        expect('consumed', role)
        ledger.transition(role, 'consumption_uncertain', 'consumed')
    identity = expect('identity')['receipt']
    receipt['identity_receipt'] = identity
    require(identity.get('contract_accepted') is True and identity.get('identity_accepted') is True
            and identity.get('save_attempts') == 0 and identity.get('before') == expected,
            'helper identity gate failed')
    send(stream, dict(kind='finish' if mode == 'identity' else 'invoke', nonce=nonce))
    receipt['helper_result'] = expect('result')['receipt']


def _connect_pipe(name, helper_pid, process, deadline):
    """Wait only for server startup; exactly one successful pipe connection."""
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetNamedPipeServerProcessId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    while True:
        try:
            stream = open('\\\\.\\pipe\\' + name, 'r+b', buffering=0)
            break
        except FileNotFoundError:
            require(process.poll() is None and time.monotonic() < deadline, 'helper pipe never became available')
            time.sleep(.02)
    try:
        actual = wintypes.ULONG()
        require(kernel.GetNamedPipeServerProcessId(msvcrt.get_osfhandle(stream.fileno()), ctypes.byref(actual))
                and actual.value == helper_pid, 'pipe server PID differs')
        return stream
    except BaseException:
        stream.close()
        raise


def invoke_existing(app, document, output, source, source_sha, helper, directory, mode, report, owned_host_pid):
    """Caller owns app/doc/ext for the full lifetime. Never creates or attaches a host."""
    import pythoncom
    from swcli.hosts.windows import _com_value
    require(mode in ('identity', 'invoke'), 'unsupported bridge mode')
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    record = dict(schema='swcli.typed-glb-producer.v1', python_worker_pid=os.getpid(), mode=mode,
                  unique_variable='SaveAs3 call binding: installed strongly typed C# PIA',
                  source_sha256=source_sha, output=output, success=False, cleanup_errors=[],
                  ci_acceptance=False, public_acceptance=False)
    report.update(record)
    ledger, streams, payloads = ParcelLedger(), {}, {}
    process = None
    io_thread = None
    state = {}
    failure = None
    try:
        record['build'] = verify_build(helper)
        expected = snapshot(app, document, source, source_sha)
        require(type(owned_host_pid) is int and expected['pid'] == owned_host_pid, 'host differs from harness owned process')
        record['expected'] = expected
        extension = _com_value(document, 'Extension')
        require(extension is not None, 'existing document Extension unavailable')
        for role, obj in zip(ROLES, (app, document, extension)):
            stream = pythoncom.CreateStreamOnHGlobal()
            streams[role] = stream
            ledger.transition(role, 'not_marshaled', 'marshal_attempted')
            try:
                pythoncom.CoMarshalInterface(stream, pythoncom.IID_IDispatch, obj._oleobj_,
                                             pythoncom.MSHCTX_LOCAL, pythoncom.MSHLFLAGS_NORMAL)
            except BaseException:
                ledger.states[role] = 'marshal_outcome_unknown'
                raise
            ledger.transition(role, 'marshal_attempted', 'marshaled')
            stream.Seek(0, 0)
            data = stream.Read(MAX_PARCEL + 1)
            require(0 < len(data) <= MAX_PARCEL, 'marshal parcel outside limit')
            payloads[role] = data
        name, nonce = 'swcli-glb-' + secrets.token_hex(16), secrets.token_hex(32)
        record['parcel_lengths'] = {role: len(data) for role, data in payloads.items()}
        receipt_path, trace_path = directory / 'helper.json', directory / 'helper-native.jsonl'
        started = time.monotonic()
        with (directory / 'helper.stdout.log').open('xb') as stdout, (directory / 'helper.stderr.log').open('xb') as stderr:
            process = subprocess.Popen([str(helper), '--pipe', name, '--nonce', nonce, '--parent', str(os.getpid()),
                                        '--receipt', str(receipt_path), '--trace', str(trace_path)],
                                       stdout=stdout, stderr=stderr)
            record['helper_pid'] = process.pid
            def io_work():
                try:
                    with _connect_pipe(name, process.pid, process, started + 15) as pipe:
                        io_session(pipe, nonce, mode, expected, output, payloads, ledger, record)
                except BaseException as error:
                    state['error'] = dict(type=type(error).__name__, message=str(error))
                    state['exception'] = error
            io_thread = threading.Thread(target=io_work, name='typed-glb-pipe-io', daemon=True)
            io_thread.start()
            while io_thread.is_alive() or process.poll() is None:
                pythoncom.PumpWaitingMessages()
                require(time.monotonic() - started < 600, 'helper deadline; native result/consumption may be unknown')
                if 'error' in state:
                    if isinstance(state.get('exception'), HelperTerminated):
                        raise state['exception']
                    raise RuntimeError('pipe exchange failed: ' + str(state['error']))
                time.sleep(.01)
            if isinstance(state.get('exception'), HelperTerminated):
                raise state['exception']
            require('error' not in state, 'pipe exchange failed: ' + str(state.get('error')))
        record['helper_exit'] = process.returncode
        require(receipt_path.exists(), 'helper durable receipt missing')
        durable = json.loads(receipt_path.read_bytes())
        require(durable == record.get('helper_result'), 'durable/helper pipe receipts differ')
        if durable.get('success') is not True:
            raise HelperTerminated(durable, 'final result')
        require(process.returncode == 0 and durable.get('cleanup_errors') == [], 'helper exit/cleanup failed')
        require(durable.get('helper_pid') == process.pid and durable.get('python_worker_pid') == os.getpid()
                and durable.get('pia_sha256') == PIA_SHA and durable.get('consumed_roles') == list(ROLES), 'helper provenance differs')
        attempts = 0 if mode == 'identity' else 1
        require(durable.get('save_attempts') == attempts and durable.get('identity_accepted') is True,
                'helper save count/identity differs')
        record['success'] = True
        return durable
    except BaseException as error:
        failure = error
        record['first_error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        if process is not None and process.poll() is None:
            graceful_until = time.monotonic() + 2
            while process.poll() is None and time.monotonic() < graceful_until:
                pythoncom.PumpWaitingMessages()
                time.sleep(.01)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                record['cleanup_errors'].append('helper termination unconfirmed')
        if io_thread is not None:
            io_thread.join(timeout=2)
            if io_thread.is_alive():
                # Never release a packet while transport can still grant consumption.
                record['cleanup_errors'].append('I/O thread still active; all marshal releases withheld')
        safe_release = io_thread is None or not io_thread.is_alive()
        if safe_release:
            for role in ledger.releasable():
                try:
                    streams[role].Seek(0, 0)
                    pythoncom.CoReleaseMarshalData(streams[role])
                    ledger.states[role] = 'released_unconsumed'
                except BaseException as error:
                    record['cleanup_errors'].append('release ' + role + ': ' + type(error).__name__ + ': ' + str(error))
        record['parcel_states'] = dict(ledger.states)
        record['consumption_uncertain'] = ledger.uncertain()
        record['marshal_outcome_unknown'] = [role for role in ROLES if ledger.states[role] in ('marshal_attempted', 'marshal_outcome_unknown')]
        record['marshal_cleanup_known'] = safe_release and not ledger.uncertain() and not record['marshal_outcome_unknown'] and not record['cleanup_errors']
        if process is not None:
            record['helper_exit'] = process.poll()
            helper_path = directory / 'helper.json'
            if helper_path.exists():
                try:
                    record['helper_durable'] = json.loads(helper_path.read_bytes())
                    record['helper_receipt_sha256'] = digest(helper_path)
                    if record['helper_durable'].get('first_error'):
                        record['native_first_error'] = record['helper_durable']['first_error']
                except (OSError, ValueError) as error:
                    record['cleanup_errors'].append('helper receipt unreadable: ' + str(error))
            trace_path = directory / 'helper-native.jsonl'
            if trace_path.exists():
                record['helper_trace_sha256'] = digest(trace_path)
        if not record['marshal_cleanup_known']:
            record['success'] = False
        payloads.clear()
        streams.clear()
        report.clear()
        report.update(record)
        try:
            with (directory / 'producer.json').open('x', encoding='utf-8') as file:
                json.dump(record, file, ensure_ascii=True, indent=2, allow_nan=False)
                file.write('\n')
        except (OSError, ValueError) as error:
            record['success'] = False
            record['cleanup_errors'].append('producer receipt write: ' + str(error))
            report.clear()
            report.update(record)
        if failure is None and not record['success']:
            raise RuntimeError('bridge cleanup/provenance incomplete')


def adapt_result(result, receipt):
    """No native code claims after exceptional/unknown returns. Never invokes fallback."""
    require(type(result.get('save_attempts')) is int and result['save_attempts'] == 1, 'expected exactly one C# SaveAs3 attempt')
    receipt['save_attempted'] = True
    for key in ('api_saved', 'save_errors', 'save_warnings'):
        receipt.pop(key, None)
        value = result.get(key)
        if value is not None:
            require(type(value) is (bool if key == 'api_saved' else int), 'typed native receipt type differs')
            receipt[key] = value
    require(result.get('success') is True and result.get('post_state_accepted') is True
            and receipt.get('api_saved') is True and type(receipt.get('save_errors')) is int
            and type(receipt.get('save_warnings')) is int and receipt['save_errors'] == 0,
            'typed SaveAs3/identity/post-state failed')
    return receipt['api_saved']
