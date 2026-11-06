"""Opt-in units read/CAS calibration, never write-domain authorization.

One fresh host, three fixtures, first failure stops. No preference writes,
retries, rollback or host replacement. Parent bounds call/group to 600/1800s.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def durable(path, value):
    data = (json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2)+'\n').encode()
    if path.exists() and path.read_bytes() == data:
        return
    with path.open('wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def expired(now, started, begins):
    return now-started > 1800 or any(now-value > 600 for value in begins.values())


def require_closed_refusal(result):
    require(result.get('ok') is False
            and result.get('mutation')==dict(attempted=False,may_have_changed=False)
            and result.get('error',{}).get('type') in ('UnitProfileCalibrationRequired','ValueError'),
            'unproved write escaped closed domain or failed unexpectedly')


def record_geometry(measure,case,label,persist):
    result=measure()
    case[label+'_measurement']=result
    persist()
    require(result['ok'],'part measurement failed')
    metrics=result['metrics']
    case[label]=metrics
    persist()
    for key,value in (('volume_mm3',12000),('surface_area_mm2',3800)):
        require(math.isclose(metrics[key],value,rel_tol=1e-7,abs_tol=1e-5),'analytic box mismatch: '+key)
    require(metrics['solid_body_count']==1,'box body count differs')
    for axis,value in zip(('x','y','z'),(0,0,5)):
        require(math.isclose(metrics['centroid_mm'][axis],value,rel_tol=1e-7,abs_tol=1e-5),'analytic box centroid mismatch: '+axis)
    return metrics


def record_exact_geometry(before,after,case,label,persist,message):
    def scalars(metrics):
        return {**{k:metrics[k] for k in ('solid_body_count','volume_mm3','surface_area_mm2')},
                **{'centroid_mm.'+k:v for k,v in metrics['centroid_mm'].items()}}
    left,right=scalars(before),scalars(after)
    case[label]=dict(exact_equal=before==after,differences={
        k:dict(before=left[k],after=right[k],before_hex=float(left[k]).hex(),after_hex=float(right[k]).hex(),delta=right[k]-left[k])
        for k in left if left[k]!=right[k]})
    persist()
    # Preserve the original exact equality assertion; no tolerance substitution.
    require(before==after,message)


def supervise(args):
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-I', str(Path(__file__).resolve()), '--worker', '--output-dir', str(output), '--swconst', str(args.swconst.resolve()), '--drawing-template', str(args.drawing_template.resolve())]
    with (output/'worker.stdout').open('wb') as stdout, (output/'worker.stderr').open('wb') as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        started=time.monotonic(); position=0; begins={}
        while child.poll() is None:
            trace=output/'trace.jsonl'
            if trace.exists():
                with trace.open(encoding='utf-8') as stream:
                    stream.seek(position)
                    while True:
                        line=stream.readline()
                        if not line or not line.endswith('\n'):break
                        event=json.loads(line);position=stream.tell()
                        if event['phase']=='begin':begins[event['sequence']]=event['monotonic']
                        else:begins.pop(event['sequence'],None)
            if expired(time.monotonic(),started,begins):
                durable(output/'watchdog.json',dict(success=False,reason='600s call or 1800s group budget exceeded',open_calls=begins))
                child.kill();child.wait();return 1
            time.sleep(1)
    return child.returncode


def worker(args):
    import pythoncom
    import win32com.client as client
    import win32api
    import win32con
    import win32event
    from swcli.host_processes import solidworks_process_ids
    from swcli.hosts.windows import _com_value
    from swcli.hosts.windows_parts import create_part_windows_with_handle
    from swcli.hosts.windows_assemblies import create_assembly_windows_with_handle
    from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
    from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle
    from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
    from swcli.hosts.windows_measurements import measure_part_windows
    from swcli.hosts.windows_documents import open_windows_document_with_handle
    from swcli.hosts.windows_native_files import save_as_native_windows
    from swcli.hosts import windows_document_unit_profile as adapter
    from swcli.document_unit_profile import FIELDS, LINKAGE, CALIBRATED_UNIT_WRITES
    from swcli.daemon.documents import DocumentRegistry
    from swcli.daemon.operations import execute_operation
    from swcli.result_schemas import validate_operation_result
    output=args.output_dir
    report=dict(success=False,profile='units-read-cas-v1',full_acceptance_eligible=False,write_acceptance_eligible=False,cases=[],cleanup_errors=[],source_commit=os.environ.get('GITHUB_SHA'),budgets=dict(native_seconds=600,group_seconds=1800))
    sequence=0
    trace=(output/'trace.jsonl').open('a',encoding='utf-8')
    def persist():durable(output/'report.json',report)
    def call(name, function):
        nonlocal sequence
        sequence+=1;current=sequence
        def event(phase, **extra):
            trace.write(json.dumps(dict(sequence=current,call=name,phase=phase,monotonic=time.monotonic(),**extra))+'\n');trace.flush();os.fsync(trace.fileno())
        event('begin');persist()
        try:result=function()
        except BaseException as error:
            event('error',error_type=type(error).__name__,error=str(error));raise
        event('end');return result
    def geometry(document,case,label):
        return record_geometry(lambda:call('measure-part-mm',lambda:measure_part_windows(document=document)),case,label,persist)
    app=handle=None;owned=False
    pythoncom.CoInitialize()
    try:
        require(not CALIBRATED_UNIT_WRITES,'read calibration cannot authorize writes')
        report['swconst_sha256']=hashlib.sha256(args.swconst.read_bytes()).hexdigest()
        library=call('LoadTypeLib',lambda:pythoncom.LoadTypeLib(str(args.swconst)))
        enums={}
        for index in range(library.GetTypeInfoCount()):
            info=library.GetTypeInfo(index);attr=info.GetTypeAttr()
            if attr.typekind!=pythoncom.TKIND_ENUM:continue
            name=info.GetDocumentation(-1)[0]
            if name not in ('swUserPreferenceIntegerValue_e','swUserPreferenceToggle_e','swUnitSystem_e','swLengthUnit_e','swAngleUnit_e','swUnitsMassPropMass_e','swUnitsMassPropVolume_e'):continue
            enums[name]={info.GetDocumentation(info.GetVarDesc(i)[0])[0]:info.GetVarDesc(i).value for i in range(attr.cVars)}
        report['official_enums']=enums;persist()
        for spec in FIELDS.values():require(enums['swUserPreferenceIntegerValue_e'][spec['symbol']]==spec['id'],'primary preference id differs')
        for name,(family,value) in LINKAGE.items():
            require(enums['swUserPreferenceToggle_e' if family=='Toggle' else 'swUserPreferenceIntegerValue_e'][name]==value,'linkage id differs: '+name)
        previous=call('inventory-processes-before',solidworks_process_ids);report['pids_before']=previous
        app=call('DispatchEx',lambda:client.DispatchEx('SldWorks.Application'))
        pid=call('GetProcessID',lambda:_com_value(app,'GetProcessID'))
        report['host_pid']=pid;persist()
        require(type(pid)is int and pid>0 and pid not in previous,'DispatchEx did not create a fresh host')
        require(call('GetDocumentCount.initial',lambda:_com_value(app,'GetDocumentCount'))==0,'fresh host is not empty')
        owned=True
        handle=call('OpenProcess.owned',lambda:win32api.OpenProcess(win32con.SYNCHRONIZE,False,pid))
        report['revision']=call('RevisionNumber',lambda:_com_value(app,'RevisionNumber'))
        # Every adapter native boundary is durable. Other helpers have their
        # operation boundary recorded as well; no argument/result credentials.
        with ExitStack() as stack:
            for name,module in list(sys.modules.items()):
                if not name.startswith('swcli.') or module is None:continue
                if hasattr(module,'native_call'):
                    stack.enter_context(patch.object(module,'native_call',side_effect=lambda stage,name,fn:call(stage+'.'+name,fn)))
                if hasattr(module,'_com_value'):
                    stack.enter_context(patch.object(module,'_com_value',side_effect=lambda obj,name:call(name,lambda:_com_value(obj,name))))
            for kind,suffix,creator in ((1,'SLDPRT',create_part_windows_with_handle),(2,'SLDASM',create_assembly_windows_with_handle),(3,'SLDDRW',create_drawing_windows_with_handle)):
                case=dict(document_type=kind,success=False);report['cases'].append(case);persist()
                template=None
                if kind==3:
                    template=args.drawing_template
                    made,document=call('create-drawing',lambda:creator(app=app,template=str(template),projection='first-angle'))
                else:made,document=call('create-model',lambda:creator(app=app))
                case['creation']=made;persist();require(made['ok'] and document is not None,'fixture creation failed')
                template=Path(made['template']['path']);case['template_sha256']=hashlib.sha256(template.read_bytes()).hexdigest()
                if kind==1:
                    sketch_result,sketch=call('box-profile-mm',lambda:create_rectangle_sketch_windows_with_handle(app=app,document=document,plane='front',width_mm=40,height_mm=30))
                    case['sketch']=sketch_result;require(sketch_result['ok'] and sketch is not None and not sketch_result.get('warnings'),'box sketch failed')
                    boss,feature=call('box-extrusion-mm',lambda:extrude_sketch_windows_with_handle(app=app,document=document,sketch_feature=sketch,depth_mm=10))
                    case['boss']=boss;require(boss['ok'] and feature is not None and not boss.get('warnings'),'box extrusion failed')
                    case['geometry_before']=geometry(document,case,'geometry_before')
                # Save before observing so no read may hide preexisting dirtiness.
                path=output/('units.'+suffix)
                case['save']=call('save-own-fixture',lambda:save_as_native_windows(str(path),document=document));persist()
                require(case['save']['ok'] and case['save']['save_errors']==0 and case['save']['save_warnings'] is None and not _com_value(document,'GetSaveFlag'),'fixture save failed')
                digest=hashlib.sha256(path.read_bytes()).hexdigest();case['file_sha256']=digest
                front_result,front=call('create-foreground',lambda:create_part_windows_with_handle(app=app))
                require(front_result['ok'] and front is not None,'foreground creation failed')
                registry=DocumentRegistry(app);entry=registry.register(document);registry.register(front)
                lease=registry.acquire_lease(entry,session_id='unit-calibration',ttl_seconds=600)
                def operation(name,values=None,write=False):
                    result=execute_operation(app,name,values or {},documents=registry,session_id='unit-calibration',document_id=entry.document_id,expected_update_stamp=_com_value(document,'GetUpdateStamp'),lease_id=lease['lease_id'] if write else None)
                    validate_operation_result(name,result);return result
                read=case['read']=call('read-background-profile',lambda:operation('document.unit-profile'));persist()
                require(read['ok'] and not read['document']['active'] and not read['document']['modified'],'profile read failed or changed background state')
                before=read['unit_profile'];source=before['values']['linear.precision']['native_value'];value=0 if source!=0 else 8
                if 0<=source<=8:
                    noop=case['noop']=call('public-same-value',lambda:operation('document.unit-profile-set',dict(field='linear.precision',value=source,expected_snapshot=before),True));persist()
                    require(noop['ok'] and not noop['changed'] and noop['mutation']==dict(attempted=False,may_have_changed=False) and noop['document']==read['document'],'same-value write changed state')
                refused=case['refused']=call('public-unproved-write',lambda:operation('document.unit-profile-set',dict(field='linear.precision',value=value,expected_snapshot=before),True));persist()
                require_closed_refusal(refused)
                again=case['after_refusal']=call('read-after-refusal',lambda:operation('document.unit-profile'));persist()
                require(again['ok'] and again['unit_profile']==before and again['document']==read['document'],'refusal changed profile or state')
                if kind==1:
                    after_geometry=geometry(document,case,'geometry_after_refusal')
                    record_exact_geometry(case['geometry_before'],after_geometry,case,'comparison_after_refusal',persist,'unit observation changed geometry')
                for target in (front,document):
                    title=_com_value(target,'GetTitle');require(sum(_com_value(d,'GetTitle')==title for d in (_com_value(app,'GetDocuments') or ()))==1,'close title is not unique')
                    call('close-owned-unique-document',lambda:app.CloseDoc(title))
                require(_com_value(app,'GetDocumentCount')==0,'fixture catalog not empty')
                opened,reopened=call('reopen-readonly',lambda:open_windows_document_with_handle(str(path),app=app,read_only=True));case['reopen']=opened;persist()
                require(opened['ok'] and opened['api_errors']==opened['api_warnings']==0 and _com_value(reopened,'IsOpenedReadOnly') is True,'readonly reopen failed')
                result=case['reopened_profile']=call('read-reopened-profile',lambda:adapter.read_document_unit_profile_windows(app=app,document=reopened));persist()
                require(result['ok'] and result['unit_profile']==before,'saved profile did not persist exactly')
                ro_refusal=case['readonly_refusal']=call('readonly-write-refusal',lambda:adapter.set_document_unit_profile_windows(app=app,document=reopened,field='linear.precision',value=value,expected_snapshot=before));persist()
                require(not ro_refusal['ok'] and ro_refusal['mutation']==dict(attempted=False,may_have_changed=False),'readonly write was not refused')
                if kind==1:
                    reopened_geometry=geometry(reopened,case,'geometry_reopened')
                    record_exact_geometry(case['geometry_before'],reopened_geometry,case,'comparison_reopened',persist,'reopened geometry changed')
                require(not _com_value(reopened,'GetSaveFlag') and hashlib.sha256(path.read_bytes()).hexdigest()==digest,'readonly observation modified file/state')
                call('close-reopened-owned-document',lambda:app.CloseDoc(_com_value(reopened,'GetTitle')))
                require(_com_value(app,'GetDocumentCount')==0,'reopened fixture remains')
                case['success']=True;persist()
        report['success']=True
    except BaseException as error:
        report['failure']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc());persist()
    finally:
        if owned:
            try:
                call('ExitApp.owned-once',lambda:_com_value(app,'ExitApp'))
                require(call('wait-owned-process',lambda:win32event.WaitForSingleObject(handle,10000))==win32event.WAIT_OBJECT_0,'owned host exit timeout')
            except BaseException as error:report['cleanup_errors'].append(str(error))
        if handle is not None:handle.Close()
        pythoncom.CoUninitialize()
        report['success']=report['success'] and not report['cleanup_errors'];persist();trace.close()
    return 0 if report['success'] else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--swconst',type=Path,required=True)
    parser.add_argument('--drawing-template',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    require(args.swconst.is_file() and args.drawing_template.is_file(),'explicit native inputs are required')
    return worker(args) if args.worker else supervise(args)

if __name__=='__main__':raise SystemExit(main())
