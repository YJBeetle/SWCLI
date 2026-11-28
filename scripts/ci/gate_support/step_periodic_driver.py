"""Independent native import, save and readonly reopen of four terminal public STEP outputs."""
import hashlib
from pathlib import Path

from .step_periodic_evidence import PLAN, READER_SCOPE, verify_cylinder_mass
from .step_periodic_public import writer_inputs
from .step_periodic_supervisor import Recorder, error


class DriverFailure(RuntimeError):
    def __init__(self,message,native_error=None):
        super().__init__(message);self.native_error=native_error


def require(value,message):
    if not value:raise DriverFailure(message)


def checked_result(value,message):
    if not isinstance(value,dict) or value.get('ok') is not True:
        raise DriverFailure(message,value.get('error') if isinstance(value,dict) else None)
    return value


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Documents:
    def __init__(self,api,app,recorder):self.api,self.app,self.recorder,self.items=api,app,recorder,[]
    def add(self,document):
        require(document is not None,'native operation returned no document');self.items.append(document);return document
    def close(self,document,*,cleanup=False):
        title=self.recorder.call('close-document-title',lambda:self.api.value(document,'GetTitle'),cleanup=cleanup)
        self.recorder.call('CloseDoc',lambda:self.app.CloseDoc(title),cleanup=cleanup)
        self.items.remove(document)


def verify_calibration_language(api, app, host, expected_language):
    language = api.value(app, 'GetCurrentLanguage')
    host['language'] = language if type(language) is str else None
    require(host['language'] == expected_language,
            'periodic cylinder calibration requires SOLIDWORKS GetCurrentLanguage=' + expected_language)




def document_count(api,app):
    value=api.value(app,'GetDocumentCount')
    require(type(value) is int and value>=0,'document count unknown')
    return value


def measure(api,document,slot,key,recorder):
    observed=api.mass(document);slot[key]=observed;recorder.persist()
    checked_result(observed,'native cylinder measurement failed')
    return verify_cylinder_mass(observed)







def readonly_open(api,document,opened,path):
    checked_result(opened,'native readonly reopen failed')
    require(document is not None,'readonly open returned no document')
    require(type(opened.get('api_errors')) is int and opened['api_errors']==0 and type(opened.get('api_warnings')) is int and opened['api_warnings']==0,'native reopen status unknown/nonzero')
    require(opened.get('read_only') is True and opened.get('document',{}).get('modified') is False
            and api.value(document,'IsOpenedReadOnly') is True and api.value(document,'GetSaveFlag') is False,'native reopened document not clean/readonly')
    actual=api.value(document,'GetPathName');recorded=opened.get('path')
    require(isinstance(actual,str) and isinstance(recorded,str) and Path(actual).resolve()==Path(path).resolve()
            and Path(recorded).resolve()==Path(path).resolve(),'readonly open returned the wrong native file')


def readback(api,app,target,output,case,recorder,documents,proof):
    require(document_count(api,app)==0,'import profile requires an empty owned host')
    original_step=digest(target);case['import_started']=True
    if hasattr(api,'assert_sources'):api.assert_sources()
    pid=recorder.report['host']['process_id']
    require(api.value(app,'GetProcessID')==pid and api.value(app,'RevisionNumber')=='33.5.0' and api.value(app,'Visible') is False,'import host identity changed')
    with api.import_preferences(app,case,recorder) as verify:
        document=api.import_once(app,target,case,proof,verify,recorder)
        if document is not None:documents.add(document)
        returned=case.get('import_return',{})
        require(document is not None and type(returned.get('errors')) is int and returned['errors']==0 and returned.get('document_returned') is True,'LoadFile4 returned no part or nonzero/unknown error')
        dtype=api.value(document,'GetType');require(type(dtype) is int and dtype==1 and document_count(api,app)==1,'imported cylinder is not the unique owned part')
        case['imported_health']=recorder.call('imported-feature-health',lambda:api.health(document,'imported',app))
        require(case['imported_health'].get('complete') is True,'incomplete imported health census')
        case['imported_topology']=recorder.call('imported-native-topology',lambda:api.topology(document))
        case['imported_geometry']=recorder.call('measure-imported-cylinder',lambda:measure(api,document,case,'imported_geometry',recorder))
        native=output/(target.stem+'-imported.SLDPRT')
        case['imported_save']=recorder.call('save-imported-native',lambda:api.save(native,document))
        checked_result(case['imported_save'],'imported native save failed')
        require(type(case['imported_save'].get('save_errors')) is int and case['imported_save']['save_errors']==0,'native save error/unknown')
        require(native.is_file() and native.stat().st_size>0,'saved native artifact is empty')
        require(Path(api.value(document,'GetPathName')).resolve()==native.resolve(),'native save named the wrong document')
        native_sha=digest(native);case['imported_native_before_sha256']=native_sha;documents.close(document)
        opened,reopened=recorder.call('reopen-imported-readonly',lambda:api.open(native,app))
        if reopened is not None:documents.add(reopened)
        case['imported_reopen']=opened;readonly_open(api,reopened,opened,native)
        require(document_count(api,app)==1,'readonly import catalog differs')
        case['reopened_health']=recorder.call('reopened-feature-health',lambda:api.health(reopened,'imported',app))
        require(case['reopened_health'].get('complete') is True,'incomplete reopened health census')
        case['reopened_geometry']=recorder.call('measure-reopened-cylinder',lambda:measure(api,reopened,case,'reopened_geometry',recorder))
        case['reopened_topology']=recorder.call('reopened-native-topology',lambda:api.topology(reopened))
        require(case['imported_topology']==case['reopened_topology'],'native topology changed after save/reopen')
        api.compare_mass(case['imported_geometry'],case['reopened_geometry'])
        require(digest(native)==native_sha and digest(target)==original_step,'native/STEP bytes changed during readonly readback')
        case['imported_native_sha256']=native_sha;documents.close(reopened)
        require(document_count(api,app)==0,'imported document leaked')
    require(case['sketch_observer_preferences'].get('restored') is True,'import preference restore incomplete')
    require(api.value(app,'GetProcessID')==pid and api.value(app,'Visible') is False,'readback host identity changed')
    case['success']=True;recorder.persist()


def verify_final_artifacts(report):
    expected = {}
    for case in report['cases']:
        step_path = Path(case['output'])
        expected[step_path.stem+'-imported.SLDPRT'] = case['imported_native_sha256']
    observed = {row['file']: row['sha256'] for row in report['artifacts']}
    differences = [
        dict(file=name, expected=sha256, observed=observed.get(name))
        for name, sha256 in expected.items() if observed.get(name) != sha256
    ]
    if differences:
        report['artifact_conflicts'] = differences
        raise DriverFailure('accepted STEP or native file changed before final evidence')


def run(output, swconst, source_commit, api=None, *, public_writer):
    output = Path(output)
    report = dict(
        success=False, diagnostic_case=READER_SCOPE, full_acceptance_eligible=False,
        source_commit=source_commit, public_writer=public_writer, complete=False,
        cases=[dict(protocol=protocol, split_periodic_faces=split, success=False,
                    export_started=False, import_started=False) for protocol,split in PLAN],
        cleanup_errors=[], evidence_errors=[], native_exit_code=None,
        limitations=['Only the public cylinder fixtures and independently observed native reopen are covered',
                     'Owned process wait is required; raw SOLIDWORKS exit code is not captured'],
    )
    recorder=Recorder(output,report);app=handle=None;owned=initialized=False;documents=None;pid=None;tracing=None
    try:
        writer_pid, public_inputs = recorder.call(
            'verify-terminal-public-writer', lambda: writer_inputs(public_writer, source_commit),
        )
        report['public_writer_host_pid'] = writer_pid
        report['public_writer_verified'] = True
        if api is None:
            from .step_periodic_native import NativeAPI
            api=NativeAPI(recorder)
        api.recorder=recorder
        report['health_censuses']=getattr(api,'health_records',[])
        if hasattr(api,'tracing'):
            tracing=api.tracing();tracing.__enter__()
        proof=report['preflight']=recorder.call('prehost-installed-proof',lambda:api.proof(swconst))
        recorder.call('CoInitialize',api.initialize);initialized=True
        app,owned=recorder.call('acquire-owned-host',api.acquire)
        require(owned is True,'must never attach to a shared host')
        pid=recorder.call('capture-owned-pid',lambda:api.value(app,'GetProcessID'))
        require(type(pid) is int and pid>0,'owned PID unavailable')
        handle=recorder.call('capture-owned-process',lambda:api.capture(pid));require(handle is not None,'owned process handle unavailable')
        recorder.call('wait-host-ready',lambda:api.ready(app))
        report['host']=dict(process_id=pid,revision=api.value(app,'RevisionNumber'),visible=api.value(app,'Visible'),owned_by_driver=True)
        require(type(pid) is int and pid>0 and report['host']['revision']=='33.5.0' and report['host']['visible'] is False,'unknown owned native host')
        require(document_count(api,app)==0,'new owned host not empty')
        installed = recorder.call('verify-owned-installation', lambda: api.verify_installation(app, swconst))
        documents=Documents(api,app,recorder)
        recorder.call('verify-calibration-language', lambda: verify_calibration_language(api, app, report['host'], 'english'))
        report['constants'] = recorder.call('read-official-constants', lambda: api.read_constants(installed))
        require(pid != writer_pid, 'public readback requires a different owned host')
        for case, (target, expected) in zip(report['cases'], public_inputs):
            require(digest(target) == expected, 'public STEP changed before independent import')
            case.update(output=str(target), sha256=expected, export_complete=True)
            readback(api, app, target, output, case, recorder, documents, proof)
        report['business_complete']=all(case['success'] for case in report['cases'])
    except BaseException as exc:recorder.fail('driver',exc)
    finally:
        safe_owner=False
        if app is not None and owned is True and pid is not None:
            try:
                observed=recorder.call('cleanup-owned-pid',lambda:api.value(app,'GetProcessID'),cleanup=True)
                # If PID was not captured before readiness failed, never infer ownership of a new identity.
                safe_owner=pid is not None and observed==pid
                require(safe_owner,'cleanup owner identity unavailable/changed')
            except Exception as exc:report['cleanup_errors'].append(dict(stage='owner-proof',error=error(exc)))
        if safe_owner:
            if documents is not None:
                for document in list(reversed(documents.items)):
                    try:documents.close(document,cleanup=True)
                    except Exception:pass  # Recorder retains each cleanup failure; continue owned cleanup only.
            try:recorder.call('ExitApp',lambda:api.exit(app),cleanup=True)
            except Exception:pass
        if handle is not None:
            try:
                recorder.call('WaitForOwnedProcess',lambda:api.wait(handle),cleanup=True);report['owned_exit_confirmed']=True
            except Exception:report['owned_exit_confirmed']=False
            try:recorder.call('CloseProcessHandle',lambda:api.close_handle(handle),cleanup=True)
            except Exception:pass
        if initialized:
            try:recorder.call('CoUninitialize',api.uninitialize,cleanup=True)
            except Exception:pass
        if tracing is not None:
            try:tracing.__exit__(None,None,None)
            except Exception as exc:report['cleanup_errors'].append(dict(stage='restore-python-tracing',error=error(exc)))
        report['success']=bool(report.get('business_complete') and not report['cleanup_errors'] and not report['evidence_errors'] and report.get('owned_exit_confirmed') is True)
        recorder.close()
        report['artifacts']=[]
        try:
            for path in sorted(output.iterdir()):
                if path.is_file() and path.suffix.lower() in ('.step','.stp','.sldprt'):
                    report['artifacts'].append(dict(file=path.name,bytes=path.stat().st_size,sha256=digest(path)))
        except Exception as exc:recorder.evidence_failure('artifact-manifest',exc)
        if report['success'] and not report['evidence_errors']:
            try:
                verify_final_artifacts(report)
                writer_inputs(public_writer, source_commit)
            except (DriverFailure, OSError, ValueError, KeyError) as exc:
                recorder.fail('final-artifact-verification', exc)
        if report['evidence_errors']:report['success']=False
        report['complete']=True
        recorder.safe_persist()
    return (0 if report['success'] and not report['evidence_errors'] else 1),report
