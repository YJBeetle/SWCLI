"""Pinned offline audit of 459ff87: model returned, strict representation failed."""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
HEAD='459ff8714d544b4a148af39a5d854715127602fa'
REPORT_SHA='26f7be0f5515781db1cc043c1ddd918aac69f03c6d2eff929b0d6c3d21b7eb7d'
ARCHIVE_SHA='ebf7de18971cdae3236db6236ba73d70e0dd1eb415c091ed2d07ddfaa63b6427'
INPUT_SHA='3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90'
FAILURE='reference-curve profile unexpectedly produced sketch geometry'
NAMES=('swMultiCAD_Enable3DInterconnect','swImportSolidSurface','swImportFreeCurves',
       'swImportNeutral_SolidandSurface','swImportNeutral_FreeCurvesAndPoints','swImportStepConfigData',
       'swImportCurvePreference','swImportNeutral_CurvesAndPointsOption')
BEFORE=dict(zip(NAMES,(True,True,False,True,False,False,0,0)))
CANDIDATE=dict(zip(NAMES,(False,True,True,True,True,False,1,1)))
OWNED=[NAMES[i] for i in (0,2,6,4,7)]


def check(ok,message):
    if not ok:raise RuntimeError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def audit(bundle,archive,input_file):
    raw=(bundle/'report.json').read_bytes();check(sha(raw)==REPORT_SHA,'Original report differs')
    r=json.loads(raw);c=r['cases'][0];p=c['preferences'];e=c['explicit_installed_binding'];g=c['geometry']
    pre=json.loads((bundle/'preflight.json').read_text())
    check(r['success'] is c['success'] is False and len(r['cases'])==1,'Plan/result differs')
    check(not r['full_acceptance_eligible'] and not r['production_public_acceptance'],'Acceptance falsely claimed')
    check(r['installed_explicit_null_candidate'] is True and r['null_import_data_candidate'] is False and
          r['diagnostic_case']=='step-wire-installed-explicit-null-once','Wrong candidate')
    check(r['host']==dict(process_id=4404,revision='33.5.0',visible=False) and r['pywin32']=='312','Host/runtime differs')
    check(c['first_error']['message']==r['failure']['message']==FAILURE,'First error differs')
    check(c['load_return']==dict(state='returned',document_returned=True,errors=0,arg_string='r',
          import_data='NULL IDispatch; explicit installed binding; factory observed only',possible_document_mutation=True,
          python_type='win32com.client.CDispatch'),'Load outcome differs')
    check(c['imported-document-type']['value']==1 and c['owned-import-count']['value']==1,'Not one owned part')
    check(c['IImportStepData.QueryInterface']==dict(status='observed',value=True) and
          c['MapConfigurationData']==dict(status='observed',value=False),'QI/Map differs')
    check('observation only' in c['GetImportFileData']['role'],'Factory actual argument misreported')
    check(e['status']=='verified' and e['explicit_invoke_attempted'] is True and
          e['changed_variables_from_60f1cf8']==['invocation binding','ImportData semantic value'] and
          e['single_null_causal_claim'] is False and e['original_bound_method_used'] is False and e['host_rewrapped'] is False,'Binding boundary differs')
    check(e['GetIDsOfNames']==dict(status='observed',lcid=0,names=['LoadFile4'],value=227,python_type='builtins.int'),'Name ID differs')
    state=e['existing_python_state'];check(state==e['state_after_name_lookup'],'Name lookup changed maps')
    check(state['lazydata']==dict(key_present=True,is_none=True,python_type='builtins.NoneType') and
          not state['maps']['mapFuncs']['targets']['LoadFile4']['present'] and not state['built_methods']['load_present'],'Original map facts differ')
    check(e['actual_argument']==dict(python_form='VARIANT(VT_DISPATCH,None)',observed_varianttype=9,
          observed_value_is_none=True,null_dispatch_pointer_by_conversion_proof=True),'Actual carrier differs')
    check(e['raw_return']==dict(returned=True,python_type='builtins.PyIDispatch',scope='after Invoke; before original Python return policy') and
          e['original_return_policy_completed'] is True,'Raw return/wrapping differs')
    contract=json.loads((bundle/'installed-invocation-contract.json').read_text())
    check(contract==e['installed_contract']==r['installed_invocation_contract'] and contract['verified'] is True and
          contract['tlb_sha256']=='585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159' and
          (contract['dispid'],contract['lcid'],contract['invkind'])==(227,0,1) and
          contract['arg_types']==[[8,1],[8,1],[9,1],[16387,3]],'Installed signature differs')
    package=json.loads((bundle/'null-binding-package.json').read_text())
    check(package==r['binding_package'] and package['verified'] is True,'Package proof differs')
    expected_files=dict(dynamic='b217819b4d9b1cbd474b463b4181a683e311d2cf0a2a14fd1dd1b00595bb7797',
        build='ef246eee3d2bb7b852d522b65a155678f3fc01f7010c1c38f5ed6c8b7424056f',client='a0fa92dcf3bd6cb6ce8bba38c6bee95b12b95a325852b1dbeb559464d431b36a')
    check(all(package['files'][k]['normalized_sha256']==v for k,v in expected_files.items()),'b312 files differ')
    for group,names in [('runtime_handlers',{'__getattr__','_LazyAddAttr_','_make_method_','_ApplyTypes_'}),
                        ('runtime_return_handlers',{'_get_good_object_','_get_good_single_object_','_wrap_dispatch_'}),
                        ('client_wrapper_handlers',{'_wrap_dispatch_','__dir__'}),('client_factory_handlers',{'DispatchEx','Dispatch','__WrapDispatch'})]:
        check(set(package[group])==names and all(len(v)==64 for v in package[group].values()),'Missing runtime proof')
    check(r['input']==r['input_final']==pre['input']==c['input_before'],'Input metadata drift')
    check(r['input']['sha256']==sha(input_file.read_bytes())==INPUT_SHA and
          r['input']['metadata']['size']==10595 and r['input']['metadata']['attributes']==33 and r['input']['readonly'],'Input bytes/readonly differ')
    check(sha(archive.read_bytes())==ARCHIVE_SHA,'Archive hash differs')
    expected=subprocess.check_output(['git','archive','--format=zip',HEAD],cwd=ROOT)
    with zipfile.ZipFile(archive) as a,zipfile.ZipFile(io.BytesIO(expected)) as b:
        rows=[i for i in a.infolist() if not i.is_dir()];members={i.filename:a.read(i) for i in rows}
        reference={i.filename:b.read(i) for i in b.infolist() if not i.is_dir()}
        check(len(rows)==len(members)==434 and members==reference,'Full reviewed commit archive differs')
        check(len(r['code'])==10 and all(sha(members[k.replace('\\','/')])==v for k,v in r['code'].items()),'Loaded hashes differ')
    rawg=g['raw_observation'];inventory=rawg['feature_inventory'];sketches=[x for x in inventory if x['kind']=='3DProfileFeature']
    check(g['status']=='unavailable' and g['value'] is None and rawg['complete'] is False,'Failure promoted')
    check(len(inventory)==len(set(x['feature_id'] for x in inventory))==18 and
          [x['feature_id'] for x in sketches]==rawg['representation_mismatches']==[17,18] and
          [len(x['lengths_mm']) for x in sketches]==[6,6],'Inventory/representation differs')
    lengths=sorted(v for x in sketches for v in x['lengths_mm'])
    check(not any(x['lengths_mm'] for x in inventory if x not in sketches),'Unexpected measured feature')
    check(rawg['segment_count']==len(lengths)==12 and lengths==rawg['lengths_mm'] and
          all(math.isfinite(v) and math.isclose(v,w,rel_tol=0,abs_tol=1e-9) for v,w in zip(lengths,[10]*4+[30]*4+[40]*4)),'Partial vector differs')
    check(sum(lengths)==rawg['total_length_mm']==320.0,'Partial total differs')
    check(p['snapshot']==p['after']==BEFORE and p['candidate_readback']==CANDIDATE and p['changed_from_60f1cf8']==[],'Profile drift')
    check(p['restored'] is True and p['restore_errors']==[] and [x['name'] for x in p['writes']]==OWNED and
          [x['name'] for x in p['restore']]==OWNED[::-1],'Owned restoration differs')
    expected=dict(BEFORE);index=0
    for stage in p['stages']:
        check(stage['status']=='observed','Unknown stage')
        if stage['label']=='readback-after-set':
            row=p['writes'][index];expected[row['name']]=row['requested'];index+=1
            check(row['readback']==expected,'Full write readback differs')
        if stage['label']=='verify-full-original-restored':expected=dict(BEFORE)
        check(stage['values']==expected,'Full stage/CAS differs')
    check(index==5 and len(p['stages'])==19 and len(p['reads'])==162 and all(x['status']=='observed' for x in p['reads']),'Read journal differs')
    for row in p['writes']+p['restore']:
        check(row['status']=='verified' and row['possible_mutation'] and
              row['returned'] is (True if row['name'] in NAMES[6:] else None),'Setter verification differs')
    for row in p['restore']:check(row['current']==row['requested']==CANDIDATE[row['name']] and row['readback']==row['original']==BEFORE[row['name']],'Restore CAS differs')
    counts={};sequences={};errors={}
    for name in ('trace.jsonl','observation-trace.jsonl'):
        rows=[json.loads(line) for line in (bundle/name).read_text().splitlines()];stack=[];seq=[];bad=[]
        for row in rows:
            if row['phase']=='begin':stack.append(row['call']);seq.append(row['call'])
            else:
                check(row['phase'] in ('end','error') and stack and stack.pop()==row['call'],'Unpaired trace')
                if row['phase']=='error':bad.append(row)
        check(not stack,'Unfinished call');counts[name]=dict(Counter(seq));sequences[name]=seq;errors[name]=bad
    main=counts['trace.jsonl'];obs=counts['observation-trace.jsonl'];seq=sequences['trace.jsonl']
    check(len(seq)==196 and len(sequences['observation-trace.jsonl'])==109,'Trace sizes differ')
    check(errors['trace.jsonl']==[dict(call='read-imported-wireframe',phase='error',error=FAILURE)] and errors['observation-trace.jsonl']==[],'First trace error differs')
    for name in ('acquire-owned-host','GetImportFileData','IImportStepData.QueryInterface','MapConfigurationData','binding.GetIDsOfNames.LoadFile4','LoadFile4','read-imported-wireframe','CloseDoc','ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'):
        check(main[name]==1,'Call count differs: '+name)
    check(obs['GetSketchSegments']==2 and obs['GetLength']==12 and seq[-5:]==['CloseDoc','ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'],'Measurement/cleanup differs')
    for sequence in sequences.values():
        check(not any(x.startswith(prefix) for x in sequence for prefix in ('OpenDoc','New','Save','Select','ClearSelection','Export','GetTypeInfo')),'Forbidden/unperformed call')
    check(r['cleanup_errors']==r['nohost_before']==r['remaining_native_pids']==[],'Cleanup/native catalog differs')
    check(not any((bundle/name).exists() for name in ('timeout.json','partial-acquisition-trace.jsonl')),'Timeout/partial acquisition present')
    return dict(source_commit=HEAD,report_sha256=REPORT_SHA,source_archive_sha256=ARCHIVE_SHA,source_archive_scope='complete 434-file commit archive; every member equal',
        original_files_sha256={x.name:sha(x.read_bytes()) for x in sorted(bundle.iterdir()) if x.is_file()},loaded_code_sha256=r['code'],
        host=r['host'],python=r['python'],pywin32=r['pywin32'],first_error=FAILURE,binding=e,load_return=c['load_return'],
        raw_observation=rawg,geometry_status='unavailable',geometry_value=None,strict_representation_passed=False,native_acceptance=False,
        input=r['input'],all_input_metadata_equal=True,preferences_before=BEFORE,candidate=CANDIDATE,owned_write_order=OWNED,owned_restore_order=OWNED[::-1],
        full_original_restored=True,read_count=162,stage_count=19,call_counts=counts,cleanup_errors=[],nohost_before=[],remaining_native_pids=[],
        limitations=['Two changed variables; no single-null causality claim','Raw partial sketch lengths are not successful reference-curve acceptance',
                    'No native save/reopen or sketch feature error-code observation in this zero-save diagnostic','Cannot replace fresh eight-file public acceptance'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','archive','input-file','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    check(a.bundle.resolve() not in out.parents and out not in (a.bundle.resolve(),a.archive.resolve(),a.input_file.resolve()),'Do not overwrite originals')
    a.output.write_text(json.dumps(audit(a.bundle,a.archive,a.input_file),indent=2)+'\n',encoding='utf-8')
    print('Original audit PASS; explicit Invoke returned part/errors0; reference representation FAILED; no acceptance')


if __name__=='__main__':main()
