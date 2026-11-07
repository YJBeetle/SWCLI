"""Stdlib audit of the pinned failed ORIGINAL ZIP; no product imports or CAD calls."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

RUN=42406393957
HEAD='4f20723116103c6e5f43def9f3d42b5a91372903'
ARTIFACT=13588889164
ZIP_SHA='aa850757a3940f0d26ac6ccc8fc20a213842ad2ead2a21bab29b986d7dd5b7ad'
PREFIX='swcli-native-smoke/units-write-calibration/'
FIELDS=('system','linear.unit','linear.precision','angular.unit','angular.precision','mass_properties.length_unit','mass_properties.mass_unit','mass_properties.volume_unit','mass_properties.precision')


def require(value,message):
    if not value:raise ValueError(message)


def typed(value):
    if type(value) is dict:return (dict,tuple(sorted((k,typed(v)) for k,v in value.items())))
    if type(value) is list:return (list,tuple(typed(v) for v in value))
    return type(value),value


def fingerprint(value):
    require(set(value['values'])==set(FIELDS) and len(value['native_units'])==5 and len(value['linkage'])==19,'incomplete snapshot')
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def geometry(before,after):
    for key in ('volume_mm3','surface_area_mm2','solid_body_count'):
        require(type(before[key]) is type(after[key]) and before[key]==after[key],'V/S/count changed')
    require(type(before['solid_body_count']) is int and before['solid_body_count']==1,'body count type/value')
    for axis in 'xyz':
        a,b=before['centroid_mm'][axis],after['centroid_mm'][axis]
        require(math.isfinite(a) and math.isfinite(b) and abs(b-a)<=1e-12,'centroid exceeds approved absolute bound')
    for key in ('volume_mm3','surface_area_mm2'):require(math.isfinite(after[key]),'nonfinite geometry')


def audit(archive,metadata,repo):
    raw=archive.read_bytes();require(hashlib.sha256(raw).hexdigest()==ZIP_SHA,'original ZIP digest differs')
    artifact=json.loads((metadata/'artifact.json').read_text());run=json.loads((metadata/'run-completed.json').read_text())
    require(artifact['id']==ARTIFACT and artifact['digest']=='sha256:'+ZIP_SHA and artifact['size_in_bytes']==len(raw),'official artifact association')
    require(artifact['workflow_run']['id']==run['id']==RUN and artifact['workflow_run']['head_sha']==run['head_sha']==HEAD,'run/head association')
    require(run['conclusion']=='failure','failed run status changed')
    with zipfile.ZipFile(archive) as z:
        report_bytes=z.read(PREFIX+'report.json');report=json.loads(report_bytes)
        watchdog=json.loads(z.read(PREFIX+'watchdog.json'))
        rows=[json.loads(line) for line in z.read(PREFIX+'trace.jsonl').decode().splitlines()]
        require(report['source_commit']==HEAD and report['success'] is False and report['public_write_domain_count']==0,'failed source/domain status')
        require(report['profile']=='units-write-calibration-v1' and report['write_acceptance_eligible'] is False,'diagnostic scope')
        require('failure' not in report and report['cleanup_errors']==[],'unexpected business/cleanup error')
        require(watchdog['success'] is False and '600s call or 1800s group' in watchdog['reason'],'watchdog failure missing')
        stack=[];open_calls={};durations=[];errors=[];setters=0
        for row in rows:
            if row['phase']=='begin':
                stack.append(row);open_calls[row['sequence']]=row
                if row['call']=='document-unit-profile.IModelDocExtension.SetUserPreferenceInteger':setters+=1
            else:
                require(stack and stack[-1]['sequence']==row['sequence'],'invalid nested trace')
                begin=stack.pop();open_calls.pop(row['sequence']);durations.append(row['monotonic']-begin['monotonic'])
                if row['phase']=='error':errors.append(row)
        require(not errors and max(durations)<600,'native error or call-budget failure')
        require(rows[-1]['monotonic']-rows[0]['monotonic']>=1800,'not a group-budget expiry')
        require({str(k):v['monotonic'] for k,v in open_calls.items()}==watchdog['open_calls'],'watchdog active calls differ')
        ages={str(k):rows[-1]['monotonic']-v['monotonic'] for k,v in open_calls.items()}
        require(max(ages.values())<600,'incomplete call already exceeded native budget')
        require(not any('ExitApp' in r['call'] or 'wait-owned-process'==r['call'] for r in rows),'unexpected owned exit evidence')
        require('owned_native_exit_confirmed' not in report,'unexpected positive host exit claim')
        source_forms={}
        for label,path in dict(calibration='scripts/ci/calibrate-document-unit-profile.py',write_harness='scripts/ci/gate_support/unit_profile_writes.py',native_adapter='src/swcli/hosts/windows_document_unit_profile.py',catalog='src/swcli/document_unit_profile.py').items():
            source=subprocess.check_output(['git','show',HEAD+':'+path],cwd=repo)
            lf=source.replace(b'\r\n',b'\n');forms={hashlib.sha256(lf).hexdigest():'LF',hashlib.sha256(lf.replace(b'\n',b'\r\n')).hexdigest():'CRLF'}
            digest=report['operating_source_sha256'][label];require(digest in forms,'operating source differs: '+path);source_forms[path]=forms[digest]
        coverage=[];files_checked=0;complete=0;receipts=0;geometry_count=0
        baseline=report['cases'][0]['geometry_before']
        for case in report['cases']:
            path=PREFIX+('units.SLDPRT' if case['document_type']==1 else 'units.SLDASM')
            require(hashlib.sha256(z.read(path)).hexdigest()==case['file_sha256'],'initial native hash')
            done=defaultdict(list);pending=[]
            for index,step in enumerate(case['write_steps'],1):
                before,after=step['before'],step['after'];result=step['result']
                require(result['ok'] is True and result['changed'] is True and result['native_return_value'] is True,'native receipt not successful')
                require(result['mutation']==dict(attempted=True,may_have_changed=True),'mutation receipt')
                require(typed(result['before'])==typed(before) and typed(result['unit_profile'])==typed(after),'receipt/snapshot drift')
                require(step['before_fingerprint']==fingerprint(before) and step['after_fingerprint']==fingerprint(after),'fingerprint')
                field=step['field'];require(before['values'][field]['native_value']!=step['native_target']==after['values'][field]['native_value'],'not a changed target')
                if field!='system':
                    require(before['values']['system']['native_value']==4,'scalar source not Custom')
                    require(all(typed(before['values'][f])==typed(after['values'][f]) for f in FIELDS if f!=field),'scalar changed other field')
                    allowed='length_unit' if field=='linear.unit' else 'significant_digits' if field=='linear.precision' else None
                    require(all(before['native_units'][f]==after['native_units'][f] for f in before['native_units'] if f!=allowed),'raw5 changed unrelated member')
                    if allowed:require(after['native_units'][allowed]==step['native_target'],'raw5 target differs')
                    require(typed(before['linkage'])==typed(after['linkage']),'scalar linkage drift')
                else:require(5 in (before['values'][field]['native_value'],step['native_target']),'unplanned system pair')
                a,b=step['context_before'],step['context_after']
                require(a['target_identity']==b['target_identity'] and a['peer_state']==b['peer_state'] and a['peer_identity']==b['peer_identity'],'identity/peer drift')
                require(a['target_state'][2] is False and b['target_state'][2] is True and a['target_state'][::3]==b['target_state'][::3],'context/dirty drift')
                for label in ('source','target'):
                    relative=step[label+'_file'].replace('\\','/');require(not PurePosixPath(relative).is_absolute() and '..' not in PurePosixPath(relative).parts,'unsafe native path')
                    require(hashlib.sha256(z.read(PREFIX+relative)).hexdigest()==step[label+'_sha256'],'native file hash differs');files_checked+=1
                receipts+=1
                if step['success'] is True:
                    require(typed(step['readonly_profile'])==typed(after),'readonly profile differs')
                    require(step['readonly_refusal']['mutation']==dict(attempted=False,may_have_changed=False),'readonly mutation')
                    for label in ('reopen_readonly','reopen_writable_for_next_case'):
                        require(step[label]['ok'] is True and step[label]['api_errors']==step[label]['api_warnings']==0,'reopen failed')
                    complete+=1;done[field].append(step['value'])
                    if case['document_type']==1:
                        for label in ('geometry_after_write','geometry_readonly'):
                            geometry(baseline,step[label]);comparison=step['comparison_'+label]
                            require(comparison['accepted_under_units_centroid_bound'] is True and comparison['centroid_absolute_limit_mm']==1e-12,'geometry comparator')
                            flat=lambda m:{**{k:m[k] for k in ('solid_body_count','volume_mm3','surface_area_mm2')},**{'centroid_mm.'+k:v for k,v in m['centroid_mm'].items()}}
                            left,right=flat(baseline),flat(step[label])
                            differences={k:dict(before=left[k],after=right[k],before_hex=float(left[k]).hex(),after_hex=float(right[k]).hex(),delta=right[k]-left[k]) for k in left if left[k]!=right[k]}
                            require(comparison['exact_equal'] is (baseline==step[label]) and typed(comparison['differences'])==typed(differences),'raw/delta/hex comparison differs')
                            geometry_count+=1
                else:pending.append(dict(step=index,field=field,value=step['value'],setter_success=True,saved=True,readonly_completed='readonly_profile' in step))
            coverage.append(dict(document_type=case['document_type'],case_success=case['success'],completed_private_steps=sum(map(len,done.values())),completed_targets=dict(done),incomplete_steps=pending))
        require(setters==receipts==50 and complete==49,'unexpected recorded coverage')
        require([c['document_type'] for c in coverage]==[1,2] and coverage[0]['completed_private_steps']==46 and coverage[1]['completed_private_steps']==3,'unexpected fixture reach')
        return dict(audit_success=True,run_id=RUN,head_sha=HEAD,artifact_id=ARTIFACT,zip_sha256=ZIP_SHA,report_sha256=hashlib.sha256(report_bytes).hexdigest(),first_failure='1800s group watchdog; no recorded native/API/assertion failure',trace_rows=len(rows),completed_boundaries=len(durations),trace_group_seconds=rows[-1]['monotonic']-rows[0]['monotonic'],max_completed_call_seconds=max(durations),open_call_ages_at_last_trace=ages,native_error_events=0,unit_setter_calls=receipts,complete_private_steps=complete,coverage=coverage,drawing_reached=False,native_files_checked=files_checked,part_geometry_comparisons=geometry_count,part_raw_baseline={**{k:dict(value=baseline[k],hex=float(baseline[k]).hex()) for k in ('volume_mm3','surface_area_mm2')},'solid_body_count':baseline['solid_body_count'],'centroid_mm':{k:dict(value=v,hex=float(v).hex()) for k,v in baseline['centroid_mm'].items()}},source_byte_forms=source_forms,owned_native_exit_confirmed=False,public_write_accepted=False,production_domains_eligible=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--metadata-dir',type=Path,required=True);parser.add_argument('--repo-root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=audit(args.archive,args.metadata_dir,args.repo_root);data=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(data)
    else:print(data,end='')

if __name__=='__main__':main()
