"""Readonly whole-target gate called once with root's already-owned STA app.

Never initializes COM, acquires/attaches a host, opens/activates/closes documents,
creates mates or saves. Root owns transport, exclusive ticket, budgets and cleanup.
Call verify_candidate before host acquisition, then run on that same owning STA.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

from swcli.hosts.windows import _com_value
from swcli.hosts.windows_feature_inspection import _same
from swcli.hosts.native_trace import trace_native_request
from swcli.hosts.native_sequence import native_api_sequence
from swcli.hosts.windows_assembly_target_observation import observe_readonly_active_targets, require_active_assembly

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    'coincident-aligned.SLDASM':'b535588ae3ff2e7656178cea139e974542b3fa1eb82aba2da2b8ee2c6459a081',
    'coincident-aligned-component.SLDPRT':'7a2867363b3e6022916cf039c0ddfab9f60df4dcf2e18064dac9a66dd8f629d8',
    'concentric-aligned-component.SLDPRT':'9b6d73c3a85a5ae7df9bf0b24bdded7f6eb7bf760033b9921f5c7ce3f01bdf66',
}
NAMES = ['coincident-aligned-component-1','coincident-aligned-component-2']
PYTHON_SHA = '4942b86a6597e5aee0128daa00050ed79bc21f6e709a78eb19cbfeb0c2f39ac9'


def require(condition, message):
    if not condition:raise RuntimeError(message)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_candidate(options):
    require(digest(options.source_manifest)==options.source_manifest_sha, 'source manifest digest differs')
    manifest=json.loads(options.source_manifest.read_text(encoding='utf-8'))
    expected=manifest['source_files']
    actual={path.relative_to(ROOT).as_posix():path for folder in ('src','scripts','tests')
            for path in (ROOT/folder).rglob('*') if path.is_file()
            and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo') and path.name!='.DS_Store'
            and not any(part.casefold().endswith('.egg-info') for part in path.relative_to(ROOT).parts)}
    require(set(expected)==set(actual), 'complete source inventory differs')
    for name,sha in expected.items():require(digest(actual[name])==sha, 'source bytes differ: '+name)
    require(manifest['mode']=='active-assembly-complete-census-readonly-v1', 'wrong readonly proof mode')
    require(manifest['fixtures']==FILES, 'fixture contract differs')
    require(sys.version_info[:3]==(3,14,7) and digest(sys.executable)==PYTHON_SHA, 'diagnostic Python version/binary differs')
    require(importlib.metadata.version('pywin32')=='312' and importlib.metadata.version('jsonschema')=='4.26.0', 'diagnostic dependencies differ')
    for field in ('internal_zip','public_zip','host_executable','host_type_library'):
        require(digest(getattr(options,field))==manifest['pins'][field],field+' bytes differ')
    require(options.host_type_library.resolve()==options.host_executable.resolve().with_name('sldworks.tlb'), 'official TLB not beside host')
    return manifest


def verify_files(directory):
    rows={}
    for name,expected in FILES.items():
        path=directory/name
        require(not path.is_symlink() and not getattr(path,'is_junction',lambda:False)(), 'fixture link refused')
        require(path.resolve(strict=True).parent==directory.resolve(strict=True), 'fixture escaped directory')
        stat=path.stat()
        require(bool(stat.st_file_attributes & 1) if sys.platform=='win32' else stat.st_mode & 0o222==0,
                'fixture not filesystem readonly')
        require(digest(path)==expected, 'fixture bytes differ: '+name)
        rows[name]=dict(sha256=expected,size_bytes=stat.st_size)
    return rows


def preflight(app, expected_pid, directory):
    pid=_com_value(app,'GetProcessID')
    require(type(pid) is int and pid==expected_pid, 'owned host PID differs')
    require(_com_value(app,'RevisionNumber')=='33.5.0', 'native revision differs')
    count,documents=_com_value(app,'GetDocumentCount'),_com_value(app,'GetDocuments')
    require(type(count) is int and isinstance(documents,(tuple,list)) and len(documents)==count==3, 'incomplete document catalog')
    expected={str((directory/name).resolve()).casefold():name for name in FILES}
    observed={}
    for document in documents:
        path=_com_value(document,'GetPathName')
        require(type(path) is str and path.casefold() in expected and path.casefold() not in observed, 'foreign/duplicate/unresolved document')
        kind=2 if expected[path.casefold()].endswith('.SLDASM') else 1
        actual_type=_com_value(document,'GetType')
        require(type(actual_type) is int and actual_type==kind, 'fixture type differs')
        require(_com_value(document,'GetSaveFlag') is False and _com_value(document,'IsOpenedReadOnly') is True
                and _com_value(document,'IsOpenedViewOnly') is False, 'fixture not clean readonly non-view-only')
        observed[path.casefold()]=document
    require(set(observed)==set(expected),'fixture catalog differs')
    target=observed[str((directory/'coincident-aligned.SLDASM').resolve()).casefold()]
    require_active_assembly(app,target)
    require(not _same(app,target,observed[str((directory/'concentric-aligned-component.SLDPRT').resolve()).casefold()]), 'independent PRT aliases ASM')
    components=target.GetComponents(True)
    require(isinstance(components,(tuple,list)) and len(components)==2, 'complete component catalog required')
    source=str((directory/'coincident-aligned-component.SLDPRT').resolve()).casefold()
    require(all(_com_value(c,'GetPathName').casefold()==source for c in components), 'source outside fixed readonly directory')
    return target


def run(app, options, report):
    """One whole census; failure means no second observer or business read."""
    report.update(mode='active-assembly-complete-census-readonly-v1',success=False,public_acceptance=False,
                  handles_issued=False,write_CAS_executed=False,resource_released=False)
    verify_candidate(options)
    report['files_before']=verify_files(options.fixture_dir)
    document=preflight(app,options.expected_pid,options.fixture_dir)
    try:
        with trace_native_request(report['request_id'],'diagnostic-only.assembly.active-target-census'),native_api_sequence(app,enabled=True):
            try:
                census=observe_readonly_active_targets(app=app,document=document,components=NAMES)
                report['result']=census.value  # No native bindings or persistent bytes leave this gate.
                del census
            except BaseException as error:
                report['first_business_error']=dict(type=getattr(error,'code',type(error).__name__),message=str(error))
                raise
        preflight(app,options.expected_pid,options.fixture_dir)  # Success-only catalog/foreground check.
        report['success']=True
    finally:
        original_error=sys.exc_info()[1]
        try:
            report['files_after']=verify_files(options.fixture_dir)
            report['files_unchanged']=report['files_before']==report['files_after']
            require(report['files_unchanged'],'readonly file bytes changed')
        except Exception as error:
            report['success']=False
            report['filesystem_audit_error']=dict(type=type(error).__name__,message=str(error))
            if original_error is None:raise
