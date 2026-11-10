"""Root-operated single-file STEP metadata/QI probe. Zero import/save/new/select.

No CI entry or VM control. Existing owned harness, same600s/1800s deadlines.
Every diagnostic error stops the case; only owned cleanup may follow.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import ntpath
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parent.parent
if not (SOURCE_ROOT / 'src/swcli/hosts/windows_step_export.py').is_file():
    raise RuntimeError('Run from the reviewed isolated STEP source snapshot, never a partial script copy')
sys.path.insert(0, str(SOURCE_ROOT / 'src'))
sys.path.insert(0, str(HERE))
from gate_support.step_import_observation import TOGGLES, INTEGERS, error
from swcli.hosts.windows_step_export import _native_windows_runtime, _read_native_enum_constants

spec = importlib.util.spec_from_file_location('_step_qi_owned', HERE / 'verify-through-all-calibration.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
INPUT = r'C:\Workspace\SWCLI-series-20261111\step-qi-input\ap203-wireframe.step'
EVIDENCE_ROOT = r'C:\Workspace\SWCLI-series-20261111\step-qi-evidence'
INPUT_SHA = '3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90'
STEP_IID = '{AD749A73-9AA2-4A3E-BCA5-8FC012114BB0}'
LIBRARY_HASHES = {
    'swconst.tlb': '95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6',
    'sldworks.tlb': '585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159',
}
SOURCE = dict(run_id=42413805736, head='060f26178b4deabc330ef0959b9ec0f1704159cf', artifact_id=13591430613,
              zip_sha256='de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def plain(path):
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            st = item.lstat()
            require(not item.is_symlink() and not getattr(st, 'st_file_attributes', 0) & 0x400,
                    'Path contains a link/reparse point')


def input_metadata():
    path = Path(INPUT)
    plain(path)
    require(path.is_file() and ntpath.normcase(str(path.resolve())) == ntpath.normcase(INPUT), 'Fixed input path differs')
    def snapshot():
        st = path.stat()
        return dict(size=st.st_size, device=st.st_dev, file_id=st.st_ino,
                    mtime_ns=st.st_mtime_ns, ctime_ns=st.st_ctime_ns,
                    attributes=getattr(st, 'st_file_attributes', 0))
    before = snapshot()
    require(before['attributes'] & 1, 'Fixed input must already have Windows READONLY attribute')
    # No chmod/attribute setter, copy, extraction, repair or source write.
    with path.open('rb') as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    require(snapshot() == before and digest == INPUT_SHA, 'Fixed input metadata/hash differs')
    return dict(path=INPUT, sha256=digest, readonly=True, metadata=before, original_source=SOURCE)


def native_pids():
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=10, check=True)
    rows = list(csv.reader(result.stdout.splitlines()))
    require(rows and all(len(row) >= 2 and row[1].isdecimal() for row in rows), 'Native process inventory is unknown')
    return [int(row[1]) for row in rows if ntpath.basename(row[0]).lower() == 'sldworks.exe']


class ReadOnlyApp:
    """An allowlist: forbidden CAD methods cannot reach even a permissive COM object."""
    ALLOWED = frozenset(('GetDocumentCount', 'GetProcessID', 'RevisionNumber', 'Visible', 'StartupProcessCompleted',
                         'ExitApp', 'GetUserPreferenceToggle', 'GetUserPreferenceIntegerValue', 'GetImportFileData'))
    def __init__(self, app):
        object.__setattr__(self, '_app', app)
    def __getattr__(self, name):
        require(name in self.ALLOWED, 'Forbidden CAD member: ' + name)
        return getattr(self._app, name)
    def __setattr__(self, name, value):
        raise RuntimeError('Diagnostic host property writes are forbidden')


def strict(case, call, label, function, predicate=lambda value: True):
    row = case[label] = dict(status='started')
    try:
        value = call(label, function)
        require(predicate(value), 'Diagnostic value is unknown/invalid: ' + label)
    except BaseException as exc:
        row.update(status='observed' if label == 'IImportStepData.QueryInterface' and getattr(exc, 'hresult', None) == -2147467262 else 'unknown', error=error(exc))
        if row['status'] == 'observed':
            row['value'] = False
        raise  # Preserve the first exception; no later business/diagnostic call.
    row.update(status='observed', value=value)
    return value


def case_runner(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind):
    require(profile_kind == 'single-step-iid' and live['document'] is None, 'Unexpected diagnostic plan/document')
    case['scope'] = 'GetImportFileData/QI only; not an import'
    case['input_before'] = call('verify-readonly-input-before', input_metadata)
    strict(case, call, 'host-hidden', lambda: harness._com_value(app, 'Visible'), lambda x: x is False)
    strict(case, call, 'host-revision', lambda: harness._com_value(app, 'RevisionNumber'), lambda x: x == '33.5.0')
    strict(case, call, 'empty-catalog-before', lambda: harness._com_value(app, 'GetDocumentCount'), lambda x: type(x) is int and x == 0)
    # Exactly six toggles + two integers. A failed read stops before the next read.
    for name in TOGGLES + INTEGERS:
        expected = bool if name in TOGGLES else int
        kind = 'Toggle' if expected is bool else 'IntegerValue'
        strict(case, call, name, lambda: getattr(app, 'GetUserPreference' + kind)(constants[name]), lambda x: type(x) is expected)
    case['input_before_data'] = call('verify-readonly-input-before-data', input_metadata)
    require(case['input_before_data'] == case['input_before'], 'Input changed during preference reads')
    case['GetImportFileData'] = dict(status='started', returned=None)
    try:
        data = call('GetImportFileData', lambda: app.GetImportFileData(INPUT))
        case['GetImportFileData'].update(returned=data is not None, python_type=type(data).__module__ + '.' + type(data).__name__)
        require(data is not None, 'GetImportFileData returned None; no alternate entry')
        case['GetImportFileData']['status'] = 'observed'
    except BaseException as exc:
        case['GetImportFileData'].update(status='unknown', error=error(exc))
        raise
    try:
        import pythoncom
        iid = constants['step_interface']['iid']
        def query():
            found = getattr(data, '_oleobj_', data).QueryInterface(iid, pythoncom.IID_IUnknown)
            require(found is not None, 'STEP QueryInterface returned None')
            return True  # Do not expose or invoke any custom vtable.
        strict(case, call, 'IImportStepData.QueryInterface', query, lambda x: x is True)
        strict(case, call, 'MapConfigurationData', lambda: data.MapConfigurationData, lambda x: type(x) is bool)
    finally:
        data = None  # Release before the existing owned cleanup, even on QI/getter failure.
    case['input_after'] = call('verify-readonly-input-after', input_metadata)
    require(case['input_after'] == case['input_before'], 'Input bytes/metadata changed')
    strict(case, call, 'empty-catalog-after', lambda: harness._com_value(app, 'GetDocumentCount'), lambda x: type(x) is int and x == 0)
    case['success'] = True


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def worker(args):
    output = args.output_dir
    acquisition = dict(created=None, returned=False)
    partial_errors = []
    original_acquire = harness.acquire_resident_app
    original_com_value = harness._com_value
    def observed_value(obj, name):
        with (output / 'observation-trace.jsonl').open('a', encoding='utf-8', buffering=1) as stream:
            stream.write(json.dumps(dict(call=name, phase='begin', time=time.time())) + '\n')
            try:
                value = original_com_value(obj, name)
            except BaseException:
                stream.write(json.dumps(dict(call=name, phase='error', time=time.time())) + '\n')
                raise
            stream.write(json.dumps(dict(call=name, phase='end', time=time.time())) + '\n')
            return value
    harness._com_value = observed_value
    context = dict(production_public_acceptance=False, zero_import=True, zero_save=True, zero_new=True, zero_select=True)
    try:
        require(_native_windows_runtime(), 'Verified native Windows is required')
        require(importlib.metadata.version('pywin32') == '312', 'Only reviewed pywin32312 wrapper semantics are allowed')
        context['input'] = input_metadata()
        require(args.swconst.name.casefold() == 'swconst.tlb', 'Enum library must be the hash-verified swconst.tlb')
        context['libraries'] = {}
        for name, expected in LIBRARY_HASHES.items():
            path = args.swconst.with_name(name)
            plain(path)
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            require(observed == expected, 'Installed library hash differs: ' + name)
            context['libraries'][name] = dict(path=str(path), sha256=observed)
        context['code'] = {str(p.relative_to(SOURCE_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                           (Path(__file__).resolve(), Path(harness.__file__).resolve(), HERE / 'gate_support/step_import_observation.py', SOURCE_ROOT / 'src/swcli/hosts/windows_step_export.py')}
        context['source_snapshot'] = str(SOURCE_ROOT)
        context['python'] = sys.version
        context['pywin32'] = '312'
        context['nohost_before'] = native_pids()
        require(not context['nohost_before'], 'Pre-existing SOLIDWORKS processes; no attachment/termination')
        write_json(output / 'preflight.json', context)

        def constants(pythoncom, path):
            library = pythoncom.LoadTypeLib(str(path.with_name('sldworks.tlb')))
            info = library.GetTypeInfoOfGuid(STEP_IID)  # One expected official IID, never an IID scan.
            require(info.GetDocumentation(-1)[0] == 'IImportStepData' and str(info.GetTypeAttr()[0]).upper() == STEP_IID,
                    'Installed STEP interface name/IID differs')
            found = _read_native_enum_constants(path, {'swUserPreferenceToggle_e': set(TOGGLES), 'swUserPreferenceIntegerValue_e': set(INTEGERS)})
            return {**found, 'step_interface': dict(name='IImportStepData', iid=STEP_IID, wrapper='IUnknown')}
        harness.read_constants = constants

        def acquire(client, *, visible):
            import pythoncom
            require(not visible and not native_pids(), 'Host appeared before activation')
            try:
                client.GetActiveObject('SldWorks.Application')
            except pythoncom.com_error as exc:
                if exc.hresult & 0xFFFFFFFF not in (0x800401E3, 0x80040154):
                    raise  # Unknown ROT errors are not absence.
                absence = exc
            else:
                raise RuntimeError('Existing COM host; do not attach')
            class CheckedClient:
                def GetActiveObject(self, name):
                    raise absence  # Reuse the one checked ROT result, not another COM request.
                def DispatchEx(self, name):
                    app = client.DispatchEx(name)
                    acquisition['created'] = app
                    return app
            try:
                app, owned = original_acquire(CheckedClient(), visible=False)
            except BaseException as first:
                context['partial_acquisition_first_failure'] = error(first)
                write_json(output / 'partial-acquire-first-failure.json', context['partial_acquisition_first_failure'])
                # Clean a known newly created object before the harness calls
                # CoUninitialize. Never replace the activation/configuration error.
                app, handle = acquisition['created'], None
                def cleanup_call(label, function):
                    with (output / 'partial-acquisition-trace.jsonl').open('a', encoding='utf-8', buffering=1) as stream:
                        stream.write(json.dumps(dict(call=label, phase='begin', time=time.time())) + '\n')
                        try:
                            value = function()
                            stream.write(json.dumps(dict(call=label, phase='end', time=time.time())) + '\n')
                            return value
                        except Exception as exc:
                            partial_errors.append(dict(stage=label, **error(exc)))
                            stream.write(json.dumps(dict(call=label, phase='error', time=time.time())) + '\n')
                if app is not None:
                    def capture():
                        pid = harness._com_value(app, 'GetProcessID')
                        context['partial_owned_pid'] = pid
                        write_json(output / 'partial-owned-host.json', dict(process_id=pid, owned_by_probe=True))
                        return harness.capture_process(pid)
                    handle = cleanup_call('partial-acquire.capture-owned-process', capture)
                    cleanup_call('partial-acquire.ExitApp', lambda: harness._com_value(app, 'ExitApp'))
                    if handle is not None:
                        cleanup_call('partial-acquire.WaitForOwnedProcess', lambda: harness.wait_process(handle))
                        cleanup_call('partial-acquire.CloseProcessHandle', handle.Close)
                raise
            acquisition['returned'] = True
            return ReadOnlyApp(app), owned
        harness.acquire_resident_app = acquire
        result = harness.run(output, args.swconst, False, case_runner=case_runner,
                             case_plan=[('single-step-iid', 'front', False)], diagnostic_case='step-import-data-only')
    except BaseException as exc:
        write_json(output / 'report.json', dict(success=False, diagnostic_case='step-import-data-only', full_acceptance_eligible=False,
                   cases=[], cleanup_errors=[], failure=dict(**error(exc), traceback=traceback.format_exc())))
        result = 1
    finally:
        harness.acquire_resident_app = original_acquire
        harness._com_value = original_com_value
    report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    report['cleanup_errors'].extend(partial_errors)
    # Read-only postflight checks are evidence/cleanup, never more CAD work.
    if 'input' in context:
        try:
            context['input_final'] = input_metadata()
            require(context['input_final'] == context['input'], 'Input changed across diagnostic/cleanup')
        except Exception as exc:
            report['cleanup_errors'].append(dict(stage='input-postflight', **error(exc)))
    if acquisition['created'] is not None:
        try:
            context['remaining_native_pids'] = native_pids()
            require(not context['remaining_native_pids'], 'Native processes remain; no global termination')
        except Exception as exc:
            report['cleanup_errors'].append(dict(stage='host-postflight', **error(exc)))
    if report['cleanup_errors']:
        report['success'] = False
        result = 1
    report.update(context)
    write_json(output / 'report.json', report)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--swconst', type=Path, default=Path(r'C:\Program Files\SOLIDWORKS\swconst.tlb'))
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    require(ntpath.normcase(str(args.output_dir.parent)) == ntpath.normcase(EVIDENCE_ROOT), 'Evidence must be a new direct child of the fixed Workspace evidence root')
    plain(args.output_dir)
    if args.worker:
        return worker(args)
    args.output_dir.mkdir()  # Root prepares parent; never reuse a prior report.
    started = time.monotonic()
    with (args.output_dir / 'worker.stdout.log').open('wb') as stdout, (args.output_dir / 'worker.stderr.log').open('wb') as stderr:
        process = subprocess.Popen([sys.executable, '-I', __file__, '--worker', '--output-dir', str(args.output_dir), '--swconst', str(args.swconst)], stdout=stdout, stderr=stderr)
        while process.poll() is None:
            time.sleep(0.25)
            active = None
            for filename in ('trace.jsonl', 'observation-trace.jsonl', 'partial-acquisition-trace.jsonl'):
                trace = args.output_dir / filename
                latest = None
                if trace.exists():
                    for line in trace.read_text(encoding='utf-8').splitlines():
                        try:
                            latest = json.loads(line)
                        except ValueError:
                            continue
                if latest and latest.get('phase') == 'begin' and (active is None or latest['time'] < active['time']):
                    active = latest
            if time.monotonic() - started >= 1800 or active and time.time() - active['time'] >= 600:
                write_json(args.output_dir / 'timeout.json', dict(success=False, active=active, reason='native-600s-or-group-1800s', owned_exit='unknown; root cleanup required'))
                process.kill()  # No process-name/global CAD termination or host restart.
                process.wait()
                return 124
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())
