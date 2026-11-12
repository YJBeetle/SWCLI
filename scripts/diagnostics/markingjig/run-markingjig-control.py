"""Explicit coordinator-run candidate only. No business copying, no native work by default."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import markingjig_control as control
import launcher_receipts as receipts


def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def pinned(args):
    folder=Path(__file__).resolve().parent.parent/'typed_glb'
    typed=module(folder/'run-typed-glb-control.py','markingjig_pinned_loader')
    return typed.load_baseline(Path(args.baseline))


def manifest(args):
    path=Path(args.inventory).resolve();data=path.read_bytes()
    control.require(hashlib.sha256(data).hexdigest()==args.inventory_sha256,'approved inventory bytes changed')
    return json.loads(data)


def constants(pythoncom, path):
    wanted={'swComponentFullyResolved':2,'swComponentResolved':3,'swDocASSEMBLY':2,'swAllBodies':-1,'swFileLoadWarning_ReadOnly':2}
    lib=pythoncom.LoadTypeLib(str(path));found={}
    for i in range(lib.GetTypeInfoCount()):
        info=lib.GetTypeInfo(i);attr=info.GetTypeAttr()
        if attr.typekind!=pythoncom.TKIND_ENUM:continue
        for n in range(attr.cVars):
            desc=info.GetVarDesc(n);name=info.GetDocumentation(desc[0])[0]
            if name in wanted:
                control.require(name not in found,'duplicate native enum')
                found[name]=desc.value
    control.require(found==wanted and all(type(v) is int for v in found.values()),'installed suppression/document enums differ')
    return found


def worker(args):
    base=pinned(args)
    from swcli.hosts.windows import _com_value
    from swcli.hosts.windows_documents import export_active_windows_document
    from swcli.hosts.native_trace import trace_native_request
    bridge=module(Path(__file__).resolve().parent.parent/'typed_glb/bridge_control.py','markingjig_process_identity')
    copy=control.WorkingCopy(manifest(args),args.copy_root,args.selected)
    phase_guard=None
    original_exporter=export_active_windows_document
    def case_runner(app,output,unused,plane,reverse,call,case,report,live,**kwargs):
        nonlocal phase_guard
        import pythoncom
        report.update(execution_kind='authorized-private-markingjig-readonly-control',ci_acceptance=False,public_acceptance=False,
                      native_call_worker_pid=os.getpid(),input_inventory_sha256=args.inventory_sha256,
                      binding='existing Python IModelDocExtension.SaveAs3; no C# expansion',
                      source_files_before=copy.before,selected_copy_names=args.selected)
        case['phase_policy']=args.phase_policy
        if args.phase_policy=='opening-transition-probe':
            phases=module(Path(__file__).with_name('opening_phases.py'),'markingjig_opening_phases')
            phase_guard=phases.PhaseGuard(copy,case)
        def process(pid):
            row=bridge.process_identity(pid)
            control.require(row['exe_sha256']==bridge.EXE_SHA,'owned executable differs from audited installation')
            return row
        def export(*a,**kw):
            with trace_native_request('markingjig-export-GLB','document.export'):
                return original_exporter(*a,**kw)
        try:
            with trace_native_request('markingjig-readonly-observe','diagnostic.readonly-assembly'):
                required=call('read-installed-assembly-enums',lambda:constants(pythoncom,base.SWCONST))
                case['installed_diagnostic_constants']=required
                control.one_case(app,copy,args.mode,output,_com_value,call,live,case,required,
                                 report['host']['process_id'],export,process,phase_guard=phase_guard)
            if args.mode=='invoke':
                mesh=module(base.SOURCE/'scripts/ci/gate_support/glb_mesh.py','markingjig_strict_mesh')
                case['glb_mesh']=mesh.inspect_glb(output/'MarkingJig.REND.GLB')
        finally:
            # OS-only postcheck also runs after failure; first business error is preserved.
            try:report['source_files_after']=phase_guard.postcheck() if phase_guard is not None else copy.unchanged()
            except Exception as error:report['cleanup_errors'].append(dict(stage='source-hash-postcheck',error=str(error)))
    return base.module.harness.run(Path(args.output),base.SWCONST,False,case_runner=case_runner,
                                  case_plan=[('existing-assembly','none',False)],diagnostic_case='markingjig-readonly-modern-control')


def audit(output, mode, phase_policy='strict'):
    report=json.loads((output/'report.json').read_text());observed_case=receipts.single_case(report)
    case=observed_case if observed_case is not None else {}
    events=[]
    for line in (output/'worker.stderr.log').read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('{'):
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('event')=='swcli.native-call':events.append(event)
    saves=[e for e in events if e.get('phase')=='begin' and e.get('call')=='IModelDocExtension.SaveAs3']
    forbidden=[e for e in events if e.get('phase')=='begin' and
               (e.get('call') in ('IModelDoc2.SaveAs','IModelDoc2.SaveAs2','IModelDoc2.SaveAs3') or
                any(x in e.get('call','') for x in ('SetUserPreference','EditRebuild','ResolveAll','SetSuppression','AddComponent','NewDocument')))]
    expected=1 if mode=='invoke' else 0
    complete=report.get('success') is True and observed_case is not None
    ok=complete and len(saves)==expected and not forbidden and not report['cleanup_errors']
    if mode=='invoke':
        ok=ok and case.get('export_attempts')==1 and case.get('success') is True and bool(case.get('glb_mesh'))
        ok=ok and saves[0].get('request_id')=='markingjig-export-GLB' and saves[0].get('worker_pid')==report['native_call_worker_pid']
    else:ok=ok and case.get('probe_success') is True and case.get('export_attempts')==0
    if phase_policy=='opening-transition-probe':
        phases=case.get('file_phases',{})
        observed=case.get('observations',[])
        ok=ok and mode=='probe' and case.get('phase_policy')==phase_policy
        ok=ok and phases.get('loaded_baseline_sealed') is True and phases.get('state')=='loaded'
        ok=ok and phases.get('access_time_policy')=='record-only' and phases.get('raw_access_times_strict') is False and phases.get('export_permitted') is False
        ok=ok and phases.get('opening_classification') in ('opening-metadata-transition','opening-metadata-unchanged')
        ok=ok and len(observed)==2 and all(row.get('complete') is True for row in observed)
        ok=ok and bool(phases.get('frames')) and all(row.get('complete') is True and row.get('access_time_policy')=='record-only' and not row.get('phase_error') for row in phases['frames'])
    return dict(success=bool(ok),mode=mode,phase_policy=phase_policy,case_count=len(report['cases']),
                native_failure=report.get('failure'),modern_save_attempts=len(saves),forbidden_calls=forbidden,
                report_sha256=hashlib.sha256((output/'report.json').read_bytes()).hexdigest(),
                ci_acceptance=False,public_acceptance=False,probe_is_export_acceptance=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory-originals',type=Path)
    p.add_argument('--write-inventory',type=Path)
    p.add_argument('--verify-originals',type=Path)
    p.add_argument('--baseline');p.add_argument('--inventory');p.add_argument('--inventory-sha256')
    p.add_argument('--copy-root');p.add_argument('--selected',action='append');p.add_argument('--output')
    p.add_argument('--phase-policy',choices=('strict','opening-transition-probe'),default='strict')
    p.add_argument('--mode',choices=('probe','invoke'));p.add_argument('--worker',action='store_true')
    args=p.parse_args()
    if args.inventory_originals:
        control.require(args.write_inventory is not None,'metadata output required')
        record=control.inventory(args.inventory_originals)
        with args.write_inventory.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2);f.write('\n')
        return 0
    if args.verify_originals:
        record=json.loads(args.verify_originals.read_text())
        protected={**record['files'],'existing GLB':record['protected_existing_glb']}
        for name,row in protected.items():
            control.require(control.stable_file(row['path'])==row,'original source changed: '+name)
        return 0
    control.require(all((args.baseline,args.inventory,args.inventory_sha256,args.copy_root,args.selected,args.output,args.mode)),
                    'explicit mode, approved inventory hash, selected files, copy and new output required')
    control.require(args.phase_policy=='strict' or args.mode=='probe','opening-transition candidate is zero-export probe only')
    control.require(sys.platform=='win32','native execution is Windows coordinator only')
    source=Path(args.copy_root).resolve();output=Path(args.output).resolve()
    control.require(str(source).casefold().startswith('c:\\workspace\\') and str(output).casefold().startswith('c:\\workspace\\'), 'private C:\\Workspace paths required')
    control.require(source!=output and source not in output.parents and output not in source.parents,'source/output must be separate sibling areas')
    for key in ('SWCLI_GLB_PLAIN_STAGING_CALIBRATION','SWCLI_IMAGE_QUALITY_CALIBRATION','SWCLI_STL_CALIBRATION','SWCLI_STL_EXCLUSIVE_RUNNER'):
        control.require(not os.environ.get(key),'other experiment present: '+key)
    if args.worker:return worker(args)
    base=pinned(args);control.WorkingCopy(manifest(args),source,args.selected)
    control.require(not output.exists(),'refuse prior diagnostic output')
    before=base.inventory();control.require(before==[],'existing SOLIDWORKS; refuse attachment')
    output.mkdir();started=time.monotonic();wall=time.time();failure=None
    args_list=sys.argv[1:]+['--worker']
    with (output/'worker.stdout.log').open('x',encoding='utf-8') as stdout,(output/'worker.stderr.log').open('x',encoding='utf-8') as stderr:
        proc=subprocess.Popen([sys.executable,'-I',str(Path(__file__).resolve()),*args_list],stdout=stdout,stderr=stderr,
          env={**os.environ,'SWCLI_TRACE_NATIVE_CALLS':'1','SWCLI_GLB_RUNTIME_DIAGNOSTICS':'1','SWCLI_GLB_DIAGNOSTICS_SWCONST':str(base.SWCONST),'SWCLI_PRESERVE_REJECTED_GLB':'1','PYTHONIOENCODING':'utf-8'})
        try:
            while proc.poll() is None:
                path=output/'trace.jsonl';rows=[]
                if path.exists():rows=[json.loads(x) for x in path.read_text().splitlines(keepends=True) if x.endswith('\n')]
                failure=base.module.deadline_reason(rows,time.monotonic()-started,time.time(),wall)
                if failure:break
                time.sleep(.25)
        except Exception as error:failure=str(error)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=30)
                except subprocess.TimeoutExpired:failure=(failure or 'worker failure')+'; termination unconfirmed'
    after=base.inventory();receipt=dict(mode=args.mode,phase_policy=args.phase_policy,source_kind='private readonly copy of existing MarkingJig',
      native_pids_before=before,native_pids_after=after,launch_pid=proc.pid,worker_exit=proc.returncode,failure=failure,
      success=False,ci_acceptance=False,public_acceptance=False)
    try:receipt['audit']=audit(output,args.mode,args.phase_policy)
    except Exception as error:receipt['audit_error']=dict(type=type(error).__name__,message=str(error))
    receipt['success']=proc.returncode==0 and failure is None and not after and receipt.get('audit',{}).get('success') is True
    (output/'markingjig-supervisor.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['success'] else 1


if __name__=='__main__':raise SystemExit(main())
