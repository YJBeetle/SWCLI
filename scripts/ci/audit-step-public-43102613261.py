"""Offline pinned first-failure audit. No GitHub queries, downloads, COM or CAD."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path,PureWindowsPath
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
from gate_support.step_wire_evidence import audit_wire

HEAD='f56f7929c6877248926ba2497523c8be9d65c5f4'
ZIP_SHA='6b69d6b9671b9af4fd2220552d6d8b2939a706ac38181acc109aef00717cba18'
JOB_SHA='c3ee4025692d2c0d8dcb748f9ab98a84fe308583974529c88a8c7f0cc8af4f0a'
WRITER_SHA='d30aca39c5361e9e2207557b956db4c6f2db3a0b8863bc4d0706caa50b7bdc19'
READER_SHA='e77d690128d0262f480aa9e84cd681bc63dffd10b0911dddcb3dd70f9efd9713'
NAMES=('swMultiCAD_Enable3DInterconnect','swImportSolidSurface','swImportFreeCurves','swImportNeutral_SolidandSurface',
       'swImportNeutral_FreeCurvesAndPoints','swImportStepConfigData','swImportCurvePreference','swImportNeutral_CurvesAndPointsOption')
BEFORE=dict(zip(NAMES,(True,True,False,True,False,False,0,0)))
REQUESTED={**BEFORE,NAMES[0]:False,NAMES[2]:True}
EXPECTED=tuple((p,g,'cli') for p in ('ap203','ap214') for g in ('solid-surface','wireframe','wireframe-sketches'))+(('ap214','solid-surface','sdk'),('ap203','wireframe','mcp'))


def check(ok,message):
    if not ok:raise RuntimeError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def mass(value):
    check(value['ok'] and value['method']=='native-body-mass-properties','Mass method differs')
    check(value['metrics']['solid_body_count']==len(value['bodies'])==1,'Body count differs')
    for row in (value['metrics'],value['bodies'][0]):
        for key,target in (('volume_mm3',12000),('surface_area_mm2',3800)):
            check(math.isfinite(row[key]) and math.isclose(row[key],target,rel_tol=1e-7,abs_tol=1e-5),'Physical metric differs')
        for axis,target in zip('xyz',(0,0,5)):
            check(math.isfinite(row['centroid_mm'][axis]) and math.isclose(row['centroid_mm'][axis],target,rel_tol=0,abs_tol=1e-9),'Centroid differs')


def trace(raw):
    rows=[json.loads(s) for s in raw.decode().splitlines()];stack=[];seq=[];errors=[]
    for row in rows:
        if row['phase']=='begin':stack.append(row['call']);seq.append(row['call'])
        else:
            check(row['phase'] in ('end','error') and stack and stack.pop()==row['call'],'Unpaired trace')
            if row['phase']=='error':errors.append(row)
    check(not stack,'Unfinished trace')
    return dict(rows=len(rows),calls=len(seq),counts=dict(Counter(seq)),errors=errors,sequence=seq)


def audit(bundle):
    zpath=bundle/'native.zip';meta=json.loads((bundle/'artifacts-api.json').read_text())
    check(sha(zpath.read_bytes())==ZIP_SHA,'Original ZIP differs')
    artifact=next(x for x in meta['artifacts'] if x['id']==13895175070)
    check(artifact['digest']=='sha256:'+ZIP_SHA and artifact['size_in_bytes']==zpath.stat().st_size and
          artifact['workflow_run']['id']==43102613261 and artifact['workflow_run']['head_sha']==HEAD and
          artifact['workflow_run']['head_branch']=='codex/swcli-step-export-options','Official artifact identity differs')
    check(sha((bundle/'job-130800591762.log').read_bytes())==JOB_SHA,'Original job log differs')
    with zipfile.ZipFile(zpath) as z:
        files=[x for x in z.infolist() if not x.is_dir()];members={x.filename:z.read(x) for x in files}
    check(len(files)==len(members)==105,'Artifact members differ')
    for name,data in members.items():check((bundle/'native'/name).read_bytes()==data,'Expanded original differs: '+name)
    prefix='swcli-native-smoke/';wraw=members[prefix+'step-public/report.json'];rraw=members[prefix+'step-public-readback/report.json']
    check(sha(wraw)==WRITER_SHA and sha(rraw)==READER_SHA,'Original report differs')
    w=json.loads(wraw);r=json.loads(rraw);cases=r['cases'];identity=json.loads(members[prefix+'step-public-readback/input-identity.json'])
    check(w['source_commit']==identity['source_commit']==HEAD and w['success'] is True and w['cleanup_errors']==[] and 'failure' not in w,'Writer/head differs')
    check(json.loads(members[prefix+'step-public-readback/source-public-report.json'])==w,'Reader consumed different writer report')
    check(w['host']==w['host_after'] and w['host']['process_id']==1232 and w['host']['revision']=='33.5.0' and
          w['host']['owned_by_daemon'] and not w['host']['visible'] and not w['host']['shared_interactive'] and w['host']['platform']=='windows','Writer host differs')
    check(w['foreground_before']==w['foreground_after'],'Foreground state changed')
    check(sha(members[prefix+'step-public/public-source.SLDPRT'])==w['source_sha256'],'Source native hash differs')
    check(tuple((x['protocol'],x['geometry'],x['surface']) for x in w['outputs'])==EXPECTED,'Eight public outputs differ')
    outputs=[]
    for row in w['outputs']:
        name=PureWindowsPath(row['path']).name;raw=members[prefix+'step-public/'+name];check(sha(raw)==row['sha256'],'Output digest differs')
        entry=dict(file=name,protocol=row['protocol'],geometry=row['geometry'],surface=row['surface'],sha256=sha(raw))
        if row['geometry']!='solid-surface':
            geometry=audit_wire(raw);lengths=sorted(x['length_mm'] for x in geometry['curves'])
            expected=sorted([10]*4+[30]*4+[40]*4+([30]*2+[40]*2+[50]*2 if row['geometry']=='wireframe-sketches' else []))
            check(len(lengths)==len(expected) and all(math.isclose(v,t,rel_tol=0,abs_tol=1e-9) for v,t in zip(lengths,expected)),'Raw STEP vector differs')
            entry.update(raw_segments=len(lengths),raw_total_mm=geometry['total_length_mm'],geometry_signature=geometry['geometry_signature'])
        outputs.append(entry)
    native=[json.loads(s) for s in members[prefix+'step-public/daemon.stderr.log'].decode('utf-8-sig').splitlines() if s.strip().startswith('{')]
    exports=[x for x in native if x.get('stage')=='document-export' and x.get('call')=='IModelDoc2.SaveAs3']
    check(Counter(x['phase'] for x in exports)==dict(begin=8,end=8),'Native exports incomplete or repeated')
    check(r['success'] is False and r['cleanup_errors']==[] and r['diagnostic_case']=='step-public-explicit-sketch-readback-candidate' and not r['full_acceptance_eligible'],'Reader scope differs')
    check(r['host']==dict(process_id=5980,revision='33.5.0',visible=False) and len(cases)==2,'Reader host/started count differs')
    a,b=cases
    check(a['public_output']==w['outputs'][0] and b['public_output']==w['outputs'][1] and a['success'] is True and b['success'] is False,'First failed case differs')
    check(a['import_return']['document_returned'] is True and a['step_import_errors']==a['import_return']['errors']==0,'Solid import failed')
    mass(a['imported_geometry']);mass(a['reopened_imported_geometry'])
    check(a['imported_save']['ok'] and a['imported_save']['save_errors']==0 and a['imported_save']['save_warnings'] is None,'Solid save differs')
    reopened=a['imported_reopen'];check(reopened['ok'] and reopened['read_only'] and reopened['api_errors']==reopened['api_warnings']==0 and not reopened['document']['modified'],'Solid readonly reopen differs')
    saved=members[prefix+'step-public-readback/ap203-solid-surface-imported.SLDPRT'];check(len(saved)==46785 and sha(saved)==a['imported_native_sha256'],'Saved native bytes differ')
    check(b['import_return']==dict(state='returned',document_returned=False,errors=1,arg_string='r',python_type='NoneType') and b['step_import_errors']==1,'Wire native result differs')
    check(not any(x in b for x in ('imported_geometry','imported_save','imported_reopen','reopened_imported_geometry')),'Unavailable wire geometry invented')
    check(r['failure']['type']=='RuntimeError' and r['failure']['message']=='STEP geometry readback failed','First business error differs')
    for c,reads,stages in ((a,88,11),(b,80,10)):
        check(c['import_data_observation']['returned'] is True and c['import_data_observation']['interfaces']['IImportStepData']==dict(status='observed',value=True) and
              c['import_data_observation']['map_configuration_data']==dict(status='observed',value=False),'Factory/QI/Map differs')
        p=c['sketch_observer_preferences'];check(p['before']==p['after']==BEFORE and p['requested']==REQUESTED and p['restored'] is True and p['restore_errors']==[],'Preference values/restore differ')
        check([x['name'] for x in p['writes']]==[NAMES[0],NAMES[2]] and [x['name'] for x in p['restore']]==[NAMES[2],NAMES[0]],'Owned order differs')
        expected=dict(BEFORE);index=0
        for stage in p['stages']:
            check(stage['status']=='observed','Unknown stage')
            if stage['label']=='sketch-readback-after-set':
                row=p['writes'][index];expected[row['name']]=row['requested'];index+=1;check(row['readback']==expected,'Write full readback differs')
            if stage['label']=='sketch-verify-full-original-restored':expected=dict(BEFORE)
            check(stage['values']==expected,'Full CAS stage differs')
        check(index==2 and len(p['reads'])==reads and len(p['stages'])==stages,'Journal differs')
        check(all(x['status']=='verified' for x in p['writes']+p['restore']),'Unverified setter/restore')
        for x in p['restore']:check(x['current']==REQUESTED[x['name']] and x['readback']==BEFORE[x['name']],'Restore CAS differs')
    traces={name:trace(members[prefix+'step-public-readback/'+name]) for name in ('trace.jsonl','observation-trace.jsonl')}
    main=traces['trace.jsonl'];obs=traces['observation-trace.jsonl'];counts=main['counts']
    check((main['rows'],main['calls'],obs['rows'],obs['calls'])==(476,238,74,37) and main['errors']==obs['errors']==[],'Trace size/errors differ')
    check(counts['LoadFile4']==counts['GetImportFileData']==2 and counts['save-imported-native']==counts['reopen-imported-native']==1,'Attempt counts differ')
    check(not any(k in counts or k in obs['counts'] for k in ('read-imported-wireframe','GetSketchSegments','GetLength','sketch-feature.GetErrorCode2')),'Wire measurement unexpectedly attempted')
    check(main['sequence'][-4:]==['ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'] and all(counts[k]==1 for k in main['sequence'][-4:]),'Owned cleanup differs')
    check(not any(name.endswith('timeout.json') for name in members),'Timeout present')
    return dict(run_id=43102613261,head=HEAD,artifact_id=13895175070,zip_sha256=ZIP_SHA,job_sha256=JOB_SHA,writer_report_sha256=WRITER_SHA,reader_report_sha256=READER_SHA,
        expanded_members_equal=105,writer_success=True,writer_cleanup_errors=[],public_outputs=outputs,native_export_calls=8,
        reader_cases_planned=8,reader_cases_started=2,reader_cases_completed=1,first_failed_index_zero_based=1,first_failed_output=b['public_output'],
        first_failure=r['failure'],failed_import_return=b['import_return'],failed_geometry_status='unavailable; no observation attempted',failed_geometry_value=None,
        completed_solid_case=dict(import_return=a['import_return'],geometry=a['imported_geometry'],save=a['imported_save'],reopen=reopened,reopened_geometry=a['reopened_imported_geometry'],native_sha256=a['imported_native_sha256']),
        before=BEFORE,requested=REQUESTED,full_original_restored_both_cases=True,reader_cleanup_errors=[],reader_host=r['host'],writer_host=w['host'],
        input_identity=identity,reader_trace={k:{key:value for key,value in v.items() if key!='sequence'} for k,v in traces.items()},native_acceptance=False,
        limitations=['No sketch geometry or feature health measured; null document errors1 precedes observer assertions','No native cause inferred from error1 or different-environment prior459 success',
                    'Head attested by artifact metadata/writer/input-identity/job log; artifact has no loaded source byte fingerprint manifest','Owned wait/close/exit observed; no global native-process inventory captured'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    check(a.bundle.resolve() not in a.output.resolve().parents and a.output.resolve()!=a.bundle.resolve(),'Do not change originals')
    a.output.write_text(json.dumps(audit(a.bundle),indent=2)+'\n',encoding='utf-8')
    print('Pinned original audit PASS: writer8/8; solid roundtrip1/1; first failure wire None/errors1; acceptance FAILED')


if __name__=='__main__':main()
