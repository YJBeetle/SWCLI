"""Review candidate: one owned visible-startup GLB control; never CI/public acceptance."""
import argparse
import base64
import hashlib
import importlib.util
import json
import struct
import os
from pathlib import Path
import subprocess
import sys
import time
from zipfile import ZipFile
sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'source-70d8c9e'
HEAD = '70d8c9ecf3c02b099ca9c2cc64fe1880061cea44'
OUT = BASE / 'glb-visible-startup-70d8c9e-01'
SOURCE_ZIP_SHA256 = '06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53'
VISIBLE_STARTUP = True
CONTROL_KIND = 'owned-visible-startup-mode; UserControl and Visible differ from hidden mode'
SWCONST = Path(r'C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swconst.tlb')
def verify_pinned_source():
    archive = BASE / 'getter-source-70d8c9e.zip'
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checked(digest == SOURCE_ZIP_SHA256, 'pinned source archive changed')
    with ZipFile(archive) as packed:
        for name in packed.namelist():
            if not name.endswith('/'):
                checked((SOURCE / name).read_bytes() == packed.read(name), 'pinned extracted source changed: ' + name)
    return digest


def load_pinned_module():
    sys.path.insert(0, str(SOURCE / 'src'))
    spec = importlib.util.spec_from_file_location('pinned_local_getter', SOURCE / 'scripts/ci/verify-native-getter-configurations.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SWCONST = SWCONST
    return module


def checked(condition, message):
    if not condition:
        raise RuntimeError(message)


def host_snapshot(app):
    from swcli.hosts.windows import _com_value
    snapshot = {name: _com_value(app, name) for name in
                ('Visible', 'CommandInProgress', 'UserControl', 'UserControlBackground')}
    checked(all(type(value) is bool for value in snapshot.values()), 'host boolean state is unreadable')
    snapshot['process_id'] = _com_value(app, 'GetProcessID')
    checked(type(snapshot['process_id']) is int and snapshot['process_id'] > 0, 'host PID is unreadable')
    return snapshot


def export_snapshot(app, document, source, expected_sha256):
    from swcli.hosts.windows import _com_value
    from swcli.hosts.windows_custom_properties import _state
    host = host_snapshot(app)
    checked(host['Visible'] is True, 'visible-startup host is no longer visible')
    identity = app.IsSame(document, _com_value(app, 'ActiveDoc'))
    checked(type(identity) is int and identity == 1, 'export foreground identity differs or is unknown')
    state = dict(metadata=list(_state(document)), path=_com_value(document, 'GetPathName'),
                 title=_com_value(document, 'GetTitle'), readonly=_com_value(document, 'IsOpenedReadOnly'))
    checked(state['metadata'][0] == 1 and state['metadata'][2] is False and state['readonly'] is False,
            'export requires the saved clean writable part')
    manager = _com_value(document, 'SketchManager')
    checked(manager is not None and _com_value(manager, 'ActiveSketch') is None, 'export sketch is active or unreadable')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    checked(digest == expected_sha256, 'export source bytes changed')
    return dict(host=host, document=state, foreground_identity=identity, source_sha256=digest)


def observe_export(app, document, source, expected_sha256, expected_host, fmt, exporter, call, row):
    from swcli.hosts.native_trace import trace_native_request
    def observe(phase):
        with trace_native_request('local-control-' + fmt + '-' + phase, 'diagnostic.glb-control-state'):
            return export_snapshot(app, document, source, expected_sha256)
    row['before'] = call('observe-before-' + fmt, lambda: observe('before'))
    checked(row['before']['host'] == expected_host, 'host state changed before export')
    row['result'] = result = call('export-' + fmt, exporter)
    # Preserve the first native/content failure; do not perform post-failure CAD reads.
    checked(result.get('ok') is True, 'first export content/native failure: ' + fmt)
    row['after'] = call('observe-after-' + fmt, lambda: observe('after'))
    checked(row['after'] == row['before'], 'export changed host/document/configuration/source state')
    return result


def audit_control_trace(path, worker_pid, *, complete):
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.startswith('{')]
    native = [row for row in rows if row.get('event') == 'swcli.native-call']
    forbidden = [row for row in native if row.get('phase') == 'begin' and
                 ('SetUserPreference' in row.get('call', '') or
                  row.get('call') in ('SldWorks.CommandInProgress.enter', 'SldWorks.CommandInProgress.restore'))]
    checked(not forbidden, 'control trace contains preference or CommandInProgress writes')
    exports = {}
    for fmt in ('STL', '3MF', 'AMF', 'GLB'):
        request = [row for row in native if row.get('request_id') == 'local-export-' + fmt]
        if not request and not complete:
            continue
        checked(request and all(row.get('worker_pid') == worker_pid for row in request), 'export worker/request differs')
        calls = [row for row in request if row.get('call') == 'IModelDocExtension.SaveAs3']
        checked(sum(row.get('phase') == 'begin' for row in calls) == 1, 'export must attempt modern SaveAs3 once')
        if complete:
            checked(sum(row.get('phase') == 'end' for row in calls) == 1 and
                    not any(row.get('phase') == 'error' for row in request), 'successful export trace is incomplete')
        checked(not any(row.get('call') in ('IModelDoc2.SaveAs', 'IModelDoc2.SaveAs2', 'IModelDoc2.SaveAs3')
                        for row in request), 'obsolete save API appeared')
        exports[fmt] = dict(modern_save_attempts=1)
    return dict(worker_pid=worker_pid, preference_setters=0, CommandInProgress_setters=0, exports=exports)


def collect_glb_artifacts(output):
    """Offline diagnostics after worker exit; never replace its first failure."""
    artifacts = []
    for path in sorted(output.rglob('*')):
        if not path.is_file() or (path.suffix.lower() != '.glb' and path.name != 'manifest.json'):
            continue
        data = path.read_bytes()
        row = dict(path=str(path.relative_to(output)), size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        try:
            if path.name == 'manifest.json':
                row['manifest'] = json.loads(data)
            else:
                magic, version, total = struct.unpack_from('<4sII', data)
                checked((magic, version, total) == (b'glTF', 2, len(data)), 'invalid GLB header')
                chunks = []; offset = 12
                while offset < len(data):
                    length, kind = struct.unpack_from('<I4s', data, offset); offset += 8
                    checked(length % 4 == 0 and offset + length <= len(data), 'invalid GLB chunk')
                    chunks.append(dict(kind=kind.decode('ascii'), bytes=length))
                    if kind == b'JSON': row['declared_buffers'] = json.loads(data[offset:offset + length]).get('buffers')
                    offset += length
                row['chunks'] = chunks
        except Exception as error:
            row['parse_error'] = dict(type=type(error).__name__, message=str(error))
        artifacts.append(row)
    return artifacts


def inventory():
    script = '$a=@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue|Select-Object -ExpandProperty Id); ConvertTo-Json -InputObject $a -Compress;exit 0'
    cmd = [r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', base64.b64encode(script.encode('utf-16le')).decode()]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError('native process inventory unavailable')
    return json.loads(result.stdout.decode('utf-8-sig'))

def worker():
    verify_pinned_source()
    module = load_pinned_module()
    from swcli.hosts.windows_parts import create_part_windows_with_handle
    from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle
    from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
    from swcli.hosts.windows_documents import export_active_windows_document
    from swcli.hosts.windows_native_files import save_as_native_windows
    from swcli.hosts.native_trace import trace_native_request
    def one_case(app, output, constants, plane, reverse, call, case, report, live, **kwargs):
        report.update(execution_kind='authorized-local-private-GLB-host-control', local_source_head=HEAD,
                      ci_acceptance=False, public_acceptance=False)
        case.update(preparation_only=True, outputs=[], export_controls=[])
        report['native_call_worker_pid'] = os.getpid()
        report['control_kind'] = CONTROL_KIND
        report['only_visible_property_changed'] = False
        report['actual_host_before_fixture'] = expected_host = call('observe-owned-visible-host', lambda: host_snapshot(app))
        module.require(expected_host['Visible'] is True and expected_host['process_id'] == report['host']['process_id'],
                       'owned visible-startup host state/PID differs')
        made,doc=call('create-owned-part',lambda:create_part_windows_with_handle(app=app))
        live['document']=doc;case['creation']=made
        module.require(made['ok'] and doc is not None,'part fixture creation failed')
        sketch,handle=call('create-box-profile',lambda:create_rectangle_sketch_windows_with_handle(app=app,document=doc,plane='front',width_mm=40,height_mm=30))
        case['sketch']=sketch;module.require(sketch['ok'] and handle is not None,'box profile failed')
        boss,feature=call('create-box-boss',lambda:extrude_sketch_windows_with_handle(app=app,document=doc,sketch_feature=handle,depth_mm=10))
        case['boss']=boss;module.require(boss['ok'] and feature is not None,'box boss failed')
        case['save']=call('save-owned-source',lambda:save_as_native_windows(str(output/'component.SLDPRT'),document=doc))
        module.require(case['save']['ok'] and case['save']['api_saved'] is True and case['save']['save_errors']==0 and case['save']['save_warnings']==0,'native source save failed')
        case['source_sha256']=hashlib.sha256((output/'component.SLDPRT').read_bytes()).hexdigest()
        for fmt in ('STL','3MF','AMF','GLB'):
            target=output/('component-export.'+fmt)
            def export():
                with trace_native_request('local-export-'+fmt,'document.export'):
                    return export_active_windows_document(str(target),app=app,document=doc)
            row = dict(format=fmt)
            case['export_controls'].append(row)
            result = observe_export(app, doc, output/'component.SLDPRT', case['source_sha256'], expected_host,
                                    fmt, export, call, row)
            case['outputs'].append(dict(format=fmt,result=result))
            case['outputs'][-1].update(sha256=hashlib.sha256(target.read_bytes()).hexdigest(),size_bytes=target.stat().st_size)
        probe_spec=importlib.util.spec_from_file_location('local_glb_mesh',SOURCE/'scripts/ci/gate_support/glb_mesh.py')
        mesh=importlib.util.module_from_spec(probe_spec);probe_spec.loader.exec_module(mesh)
        case['glb_mesh']=mesh.inspect_glb(output/'component-export.GLB')
        module.require(hashlib.sha256((output/'component.SLDPRT').read_bytes()).hexdigest()==case['source_sha256'],'export changed source bytes')
        case['success']=True
    return module.harness.run(OUT,SWCONST,VISIBLE_STARTUP,case_runner=one_case,case_plan=[('part','front',False)],diagnostic_case='local-private-GLB-visible-startup-control')

def main():
    if '--worker' in sys.argv:
        return worker()
    if OUT.exists():
        raise RuntimeError('refuse to replace an earlier local attempt')
    archive_digest = verify_pinned_source()
    module = load_pinned_module()
    before = inventory()
    if before:
        raise RuntimeError('existing SOLIDWORKS processes; local calibration refuses attachment')
    OUT.mkdir()
    record = dict(source_head=HEAD, source_archive_sha256=hashlib.sha256((BASE/'getter-source-70d8c9e.zip').read_bytes()).hexdigest(),
                  execution_kind='authorized-local-private-GLB-host-control', ci_acceptance=False,
                  full_acceptance_eligible=False, public_acceptance=False, pids_before=before,
                  native_timeout_seconds=600, group_timeout_seconds=1800,
                  python=sys.executable, python_version=sys.version, success=False)
    started, wall = time.monotonic(), time.time()
    failure = None
    with (OUT/'worker.stdout.log').open('w',encoding='utf-8') as stdout, (OUT/'worker.stderr.log').open('w',encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable,'-I',str(Path(__file__).resolve()),'--worker'],stdout=stdout,stderr=stderr,
                                   env={**os.environ,'SWCLI_TRACE_NATIVE_CALLS':'1','SWCLI_GLB_RUNTIME_DIAGNOSTICS':'1','SWCLI_GLB_DIAGNOSTICS_SWCONST':str(SWCONST),'SWCLI_PRESERVE_REJECTED_GLB':'1','PYTHONIOENCODING':'utf-8'})
        record['worker_pid']=process.pid
        record['launch_pid_kind']='Popen launch/venv redirector; actual native worker recorded separately'
        try:
            while process.poll() is None:
                trace = OUT/'trace.jsonl'
                rows = []
                if trace.exists():
                    rows=[json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines(keepends=True) if line.endswith('\n')]
                failure=module.deadline_reason(rows,time.monotonic()-started,time.time(),wall)
                if failure:
                    break
                time.sleep(.25)
            if failure is None and process.returncode == 0:
                report=json.loads((OUT/'report.json').read_text(encoding='utf-8'))
                if not report.get('success') or report.get('cleanup_errors'):
                    raise RuntimeError('pinned local fixture/cleanup failed')
                record['glb_mesh']=report['cases'][0]['glb_mesh']
        except Exception as error:
            failure=str(error)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    failure=(failure or 'worker failure')+'; Python worker termination unconfirmed'
    try:
        glb_artifacts = collect_glb_artifacts(OUT)
    except Exception as error:
        glb_artifacts = [dict(diagnostic_error=dict(type=type(error).__name__, message=str(error)))]
    record.update(worker_exit=process.returncode,failure=failure,elapsed_seconds=time.monotonic()-started,pids_after=inventory(),
                  control_kind=CONTROL_KIND, only_visible_property_changed=False, glb_artifacts=glb_artifacts)
    if (OUT/'report.json').exists():
        record['report_sha256']=hashlib.sha256((OUT/'report.json').read_bytes()).hexdigest()
        record['actual_native_call_worker_pid']=json.loads((OUT/'report.json').read_text(encoding='utf-8')).get('native_call_worker_pid')
        try:
            report = json.loads((OUT/'report.json').read_text(encoding='utf-8'))
            record['export_trace_audit'] = audit_control_trace(OUT/'worker.stderr.log', record['actual_native_call_worker_pid'],
                                                              complete=report.get('success') is True)
        except Exception as error:
            record['export_trace_audit_error'] = dict(type=type(error).__name__, message=str(error))
            if process.returncode == 0 and failure is None:
                failure = 'offline export trace audit failed: ' + str(error)
                record['failure'] = failure
    record['success']=process.returncode==0 and failure is None and not record['pids_after']
    (OUT/'local-supervisor.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=True))
    return 0 if record['success'] else 1

if __name__=='__main__':
    raise SystemExit(main())
