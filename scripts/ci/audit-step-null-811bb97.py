"""Independent offline audit: pinned NULL candidate stopped before LoadFile4."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
HEAD='811bb976a614cd9cda2660fe096b5fcc8ca8f197'
REPORT_SHA='297e635248a9473ee3f27fb6c29d0f87ec1ab36c3033275c2a27ea67067ce352'
ARCHIVE_SHA='a6bf3df44e81cf057d58b10f2205e9cce96838c20ed8134d51d16c158300e80e'
FAILURE='NULL binding refused: unsupported wrapper class; do not replace it'
NAMES=('swMultiCAD_Enable3DInterconnect','swImportSolidSurface','swImportFreeCurves',
       'swImportNeutral_SolidandSurface','swImportNeutral_FreeCurvesAndPoints','swImportStepConfigData',
       'swImportCurvePreference','swImportNeutral_CurvesAndPointsOption')
BEFORE=dict(zip(NAMES,(True,True,False,True,False,False,0,0)))
CANDIDATE=dict(zip(NAMES,(False,True,True,True,True,False,1,1)))
OWNED=[NAMES[i] for i in (0,2,6,4,7)]


def check(value,message):
    if not value:raise RuntimeError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def audit(bundle,archive,input_file):
    raw=(bundle/'report.json').read_bytes();check(sha(raw)==REPORT_SHA,'Report differs')
    r=json.loads(raw);c=r['cases'][0];p=c['preferences'];pre=json.loads((bundle/'preflight.json').read_text())
    check(r['success'] is c['success'] is False and len(r['cases'])==1,'Unexpected result/plan')
    check(not r['production_public_acceptance'] and not r['full_acceptance_eligible'],'Acceptance falsely claimed')
    check(r['diagnostic_case']=='step-wire-null-import-data-once' and r['null_import_data_candidate'] is True,'Wrong mode')
    check(r['host']==dict(process_id=7952,revision='33.5.0',visible=False),'Host differs')
    check(r['pywin32']=='312' and r['cleanup_errors']==[] and r['nohost_before']==r['remaining_native_pids']==[],'Runtime/cleanup differs')
    check(c['first_error']['message']==r['failure']['message']==FAILURE,'First error differs')
    check(c['null_binding']==dict(status='unknown',wrapper_type='win32com.client.CDispatch',
          bound_method_invocation_attempted=False,mode='same bound method; no replacement invocation',
          error=dict(type='RuntimeError',message=FAILURE)),'Binding refusal differs')
    check(c['load_return']==dict(state='not-attempted',document_returned=None,errors=None),'Native return invented')
    check(c['geometry']==dict(status='unavailable',value=None),'Unmeasured geometry invented')
    check(c['GetImportFileData']['returned'] is True and 'observation only' in c['GetImportFileData']['role'],'Factory role differs')
    check(c['IImportStepData.QueryInterface']==dict(status='observed',value=True) and
          c['MapConfigurationData']==dict(status='observed',value=False),'QI/map differs')
    check(r['input']==r['input_final']==pre['input']==c['input_before'],'Input metadata drift')
    check(r['input']['sha256']==sha(input_file.read_bytes())=='3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90','Input bytes differ')
    check(r['input']['metadata']['size']==10595 and r['input']['metadata']['attributes']==33 and r['input']['readonly'],'Input guards differ')
    check(sha(archive.read_bytes())==ARCHIVE_SHA,'Archive differs')
    expected_archive=subprocess.run(['git','archive','--format=zip',HEAD],cwd=ROOT,capture_output=True,check=True).stdout
    with zipfile.ZipFile(archive) as a,zipfile.ZipFile(io.BytesIO(expected_archive)) as b:
        members={x.filename:a.read(x) for x in a.infolist() if not x.is_dir()}
        expected={x.filename:b.read(x) for x in b.infolist() if not x.is_dir()}
        check(len(members)==424 and len(members)==len([x for x in a.infolist() if not x.is_dir()]) and members==expected,'Whole source commit differs')
        check(len(r['code'])==7,'Loaded code set differs')
        for name,digest in r['code'].items():check(sha(members[name.replace('\\','/')])==digest,'Loaded code hash differs')
    package=json.loads((bundle/'null-binding-package.json').read_text())
    check(package==r['binding_package'] and package['verified'] is True,'Package proof differs')
    for name,digest in dict(dynamic='b217819b4d9b1cbd474b463b4181a683e311d2cf0a2a14fd1dd1b00595bb7797',
                            build='ef246eee3d2bb7b852d522b65a155678f3fc01f7010c1c38f5ed6c8b7424056f',
                            client='a0fa92dcf3bd6cb6ce8bba38c6bee95b12b95a325852b1dbeb559464d431b36a').items():
        check(package['files'][name]['normalized_sha256']==digest,'Installed package source differs')
    check(set(package['runtime_handlers'])=={'__getattr__','_LazyAddAttr_','_make_method_','_ApplyTypes_'},'Handler proof incomplete')
    check(all(len(x)==64 for x in package['runtime_handlers'].values()),'Handler digest missing')
    check(p['snapshot']==p['after']==BEFORE and p['candidate_readback']==CANDIDATE and p['changed_from_60f1cf8']==[],'Profile drift')
    check(p['restored'] is True and p['restore_errors']==[],'Restoration failed')
    check([x['name'] for x in p['writes']]==OWNED and [x['name'] for x in p['restore']]==OWNED[::-1],'Owned order differs')
    for row in p['writes']+p['restore']:
        check(row['status']=='verified' and row['possible_mutation'],'Unverified mutation')
        check(row['returned'] is (True if row['name'] in NAMES[6:] else None),'Setter return differs')
    expected=dict(BEFORE);index=0
    for stage in p['stages']:
        check(stage['status']=='observed','Unknown stage')
        if stage['label']=='readback-after-set':
            row=p['writes'][index];expected[row['name']]=row['requested'];index+=1
            check(row['readback']==expected,'Setter full readback differs')
        if stage['label']=='verify-full-original-restored':expected=dict(BEFORE)
        check(stage['values']==expected,'Full CAS stage differs')
    check(index==5 and len(p['stages'])==18 and len(p['reads'])==154 and all(x['status']=='observed' for x in p['reads']),'Read journal differs')
    for row in p['restore']:
        check(row['current']==row['requested']==CANDIDATE[row['name']] and row['readback']==row['original']==BEFORE[row['name']],'Restore CAS differs')
    counts={};sequences={};errors={}
    for filename in ('trace.jsonl','observation-trace.jsonl'):
        rows=[json.loads(x) for x in (bundle/filename).read_text().splitlines()];stack=[];sequence=[];bad=[]
        for row in rows:
            if row['phase']=='begin':stack.append(row['call']);sequence.append(row['call'])
            else:
                check(row['phase'] in ('end','error') and stack and stack.pop()==row['call'],'Trace pairing failed')
                if row['phase']=='error':bad.append(row)
        check(not stack,'Unfinished call')
        counts[filename]=dict(Counter(sequence));sequences[filename]=sequence;errors[filename]=bad
    main=counts['trace.jsonl'];seq=sequences['trace.jsonl']
    check(len(seq)==181 and len(sequences['observation-trace.jsonl'])==7,'Trace size differs')
    check(errors['trace.jsonl']==[dict(call='verify-original-LoadFile4-binding',phase='error',error=FAILURE)] and errors['observation-trace.jsonl']==[],'Trace first error differs')
    for name in ('acquire-owned-host','GetImportFileData','IImportStepData.QueryInterface','MapConfigurationData','verify-original-LoadFile4-binding','ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'):
        check(main[name]==1,'Count differs: '+name)
    check(seq[-4:]==['ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'],'Cleanup order differs')
    check([x.removeprefix('set-owned-option.') for x in seq if x.startswith('set-owned-option.')]==OWNED,'Trace writes differ')
    check([x.removeprefix('restore-owned-option.') for x in seq if x.startswith('restore-owned-option.')]==OWNED[::-1],'Trace restore differs')
    for sequence in sequences.values():
        for prefix in ('LoadFile4','CloseDoc','OpenDoc','New','Save','Select','ClearSelection','Export','GetSketch','GetLength','read-imported'):
            check(not any(x.startswith(prefix) for x in sequence),'Forbidden/unreached call present: '+prefix)
    check(not any((bundle/x).exists() for x in ('timeout.json','partial-acquisition-trace.jsonl')),'Timeout/partial activation present')
    return dict(source_commit=HEAD,report_sha256=REPORT_SHA,source_archive_sha256=ARCHIVE_SHA,
        source_archive_scope='complete 424-file commit archive; every member byte equal; no Git metadata',
        original_files_sha256={x.name:sha(x.read_bytes()) for x in sorted(bundle.iterdir()) if x.is_file()},
        loaded_code_sha256=r['code'],first_error=FAILURE,host=r['host'],python=r['python'],pywin32=r['pywin32'],
        binding_refusal=c['null_binding'],binding_package=package,load_return=c['load_return'],geometry=c['geometry'],
        native_LoadFile4_count=0,measurement_scope='none; no geometry read attempted',call_counts=counts,
        input=r['input'],input_metadata_all_checkpoints_equal=True,preferences_before=BEFORE,candidate=CANDIDATE,
        owned_write_order=OWNED,owned_restore_order=OWNED[::-1],full_original_restored=True,
        cleanup_errors=[],nohost_before=[],remaining_native_pids=[],native_acceptance=False,
        limitation='Failure is a local wrapper allowlist gate, not an observed SOLIDWORKS import or null conversion result')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','archive','input-file','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();target=a.output.resolve()
    check(target!=a.bundle.resolve() and a.bundle.resolve() not in target.parents and target not in (a.archive.resolve(),a.input_file.resolve()),'Do not overwrite originals')
    result=audit(a.bundle,a.archive,a.input_file)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Pinned original audit PASS: wrapper refusal before LoadFile4; five owned restores and exit verified')


if __name__=='__main__':main()
