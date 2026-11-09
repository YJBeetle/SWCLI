"""Fixed official public failure ZIP audit; no product/gate/COM imports."""
import argparse
from collections import Counter,defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

spec=importlib.util.spec_from_file_location('_unit_audit_validators',Path(__file__).with_name('audit-units-write-42414478796.py'))
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
require=checks.require;typed=checks.typed;fingerprint=checks.fingerprint
RUN=42423042929
HEAD='ac8e7f26ced8148d16fe236280082d4f78ec9290'
ARTIFACT=13596036567
DIGEST='924c3bab00df410f36761d0ddd4fc03bf2fb554fb8ae3f7d53f5eb58230c72d8'
BASE='swcli-native-smoke/'


def audit(archive,metadata):
    require(hashlib.sha256(archive.read_bytes()).hexdigest()==DIGEST,'official ZIP digest')
    a=json.loads((metadata/'artifact.json').read_bytes());r=json.loads((metadata/'run-completed.json').read_bytes());jobs=json.loads((metadata/'jobs-completed.json').read_bytes())
    require(a['id']==ARTIFACT and a['digest']=='sha256:'+DIGEST and a['size_in_bytes']==archive.stat().st_size,'official artifact identity')
    require(a['workflow_run']['id']==r['id']==RUN and a['workflow_run']['head_sha']==r['head_sha']==HEAD and r['conclusion']=='failure','head/run')
    failed=[s['name'] for j in jobs['jobs'] for s in j['steps'] if s['conclusion']=='failure']
    require(failed==['Verify public document unit profile CLI'],'first failed step')
    with zipfile.ZipFile(archive) as z:
        pbytes=z.read(BASE+'units-public-acceptance/cli/public-unit-profile.json');p=json.loads(pbytes)
        host=json.loads(z.read(BASE+'units-public-acceptance/host-report.json'))
        native=json.loads(z.read(BASE+'units-write-calibration/report.json'))
        require(p['profile']=='units-public-writes-v1' and p['success'] is False and p['changed_write_acceptance'] is False and p['cleanup_errors']==[],'public failed status')
        require(host['source_commit']==HEAD and native['source_commit']==HEAD and native['success'] is True,'native source/head')
        require([len(c['write_steps']) for c in native['cases']]==[46,46,47] and all(c['success'] for c in native['cases']),'internal actual reach')
        require(native['owned_native_exit_confirmed'] is True and native['pids_before']==native['pids_after']==[] and native['cleanup_errors']==[] and native['duration_seconds']<=1800,'internal lifecycle/budget')
        require(host['success'] is False and host['cleanup_errors']==[] and host['owned_native_exit_confirmed'] is True and host['stop_exit_code']==0 and host['pids_before']==host['pids_after']==[] and host['duration_seconds']<=1800,'public cleanup/budget')
        require(len(p['unit_cases'])==117 and all(c['transport']=='cli' for c in p['unit_cases']),'actual transport reach')
        case_counts=Counter();negative_counts=Counter();geometry_count=0;geometry_nonexact=0;native_files=0
        native_steps=[s for c in native['cases'] for s in c['write_steps']]
        for case,s in zip(p['unit_cases'][:116],native_steps):
            require(case['success'] is True and case['domain']==[s['before']['document_type'],fingerprint(s['before']),s['field'],s['native_target']],'completed case/domain binding')
            before=case['read'];write=case['write'];after=case['after_write'];ro=case['readonly_read'];final=case['final_read']
            require(typed(before['unit_profile'])==typed(s['before']) and typed(write['before'])==typed(s['before']) and typed(write['unit_profile'])==typed(s['after']),'actual native profile/read/write')
            require(write['ok'] is True and write['changed'] is True and write['native_return_value'] is True and write['mutation']==dict(attempted=True,may_have_changed=True),'changed receipt')
            require(typed(after['unit_profile'])==typed(ro['unit_profile'])==typed(final['unit_profile'])==typed(s['after']),'full after/readonly persistence')
            require(case['noop']['changed'] is False and case['noop']['mutation']==dict(attempted=False,may_have_changed=False) and case['noop']['document']==before['document'],'noop exact state')
            require(after['document']==write['document'] and final['document']==ro['document'] and case['reopen']['document']['document_id']!=case['open']['document']['document_id'],'fresh readonly/state')
            require(case['save']['api_saved'] is True and case['save']['save_errors']==0 and case['save']['save_warnings'] is None and not case['save']['document']['modified'],'save proof')
            require(case['read']['document']['active'] is False and case['write']['document']['active'] is False and case['readonly_read']['document']['active'] is False,'background target')
            for label,error in (('lease_refusal','DocumentLeaseConflict'),('stamp_refusal','DocumentUpdateConflict'),('cas_refusal','DocumentUnitProfileConflict'),('readonly_refusal','ValueError')):
                receipt=case[label];require(receipt['ok'] is False and receipt['error']['type']==error,'real negative class')
                if label not in ('lease_refusal','stamp_refusal'):require(receipt['mutation']==dict(attempted=False,may_have_changed=False),'negative zero mutation')
                negative_counts[error]+=1
            if 'custom_closed_refusal' in case:
                receipt=case['custom_closed_refusal'];require(receipt['error']['type']=='UnitProfileCalibrationRequired' and receipt['mutation']==dict(attempted=False,may_have_changed=False),'Custom closed-domain refusal');negative_counts['UnitProfileCalibrationRequired']+=1
            source=s['source_file'].replace('\\','/');require(hashlib.sha256(z.read(BASE+'units-write-calibration/'+source)).hexdigest()==case['source_sha256']==s['source_sha256'],'original source unchanged')
            copy='public-write-%03d.%s'%(sum(case_counts.values())+1,('SLDPRT','SLDASM','SLDDRW')[case['document_type']-1])
            require(hashlib.sha256(z.read(BASE+'units-public-acceptance/cli/'+copy)).hexdigest()==case['saved_sha256'],'saved public native bytes');native_files+=2
            if case['document_type']==1:
                for label in ('geometry_after_write','geometry_readonly'):
                    checks.geometry(case['geometry_before'],case[label],case['comparison_'+('after_write' if label=='geometry_after_write' else 'readonly')]);geometry_count+=1;geometry_nonexact+=not case['comparison_'+('after_write' if label=='geometry_after_write' else 'readonly')]['exact_equal']
            case_counts[case['document_type']]+=1
        require(dict(case_counts)=={1:46,2:46,3:24},'per-type completed reach')
        failure=p['unit_cases'][-1];profile=failure['read']['unit_profile'];event=next(e for e in p['events'] if e['state']=='failed')
        require(failure['success'] is False and 'write' not in failure and failure['domain']==[3,fingerprint(profile),'mass_properties.length_unit',0],'first failed target')
        require(profile['values']['mass_properties.length_unit']==dict(value='inch',native_value=3),'real readable noncandidate source')
        require(typed(profile)==typed(json.loads((metadata/'first-failure-source-profile.json').read_bytes())),'versioned regression snapshot is not original')
        require(event['result']['error']==dict(type='ValueError',message='unsupported candidate unit target') and event['returncode']!=0,'actual first frontend error')
        require(json.loads(event['stdout'])==event['result'] and event['command'][event['command'].index('unit-profile-set')+1:event['command'].index('unit-profile-set')+3]==['mass_properties.length_unit','inch'],'original command/stdout')
        failed_id=event['result']['request_id'];traces=[]
        for line in z.read(BASE+'units-public-acceptance/daemon.stderr').decode(errors='replace').splitlines():
            if line.startswith('{'):
                try:value=json.loads(line)
                except ValueError:continue
                if value.get('event')=='swcli.native-call':traces.append(value)
        require(failed_id not in {t['request_id'] for t in traces},'invalid noop unexpectedly reached worker')
        errors=[t for t in traces if t['phase']=='error']
        require(all(t['sequence']==0 and t['exception_type'] in ('DocumentLeaseConflict','DocumentUpdateConflict') for t in errors),'unexpected native error')
        setters=[t for t in traces if t['phase']=='begin' and t['call']=='IModelDocExtension.SetUserPreferenceInteger']
        require(len(setters)==116 and len({t['worker_pid'] for t in traces})==1,'actual setter/worker count')
        terminal=[t['duration_ms']/1000 for t in traces if t['phase']!='begin'];require(max(terminal)<=600,'native call budget')
        events=p['events'];set_events=[e for e in events if e.get('result',{}).get('native_return_value') is True]
        require(len(set_events)==116,'actual native True CLI receipts')
        for c in p['unit_cases'][:116]:
            document=c['read']['document']['document_id']
            lease=next(e['result']['lease']['lease_id'] for e in events if e['command'][e['command'].index('--request-timeout')+2:e['command'].index('--request-timeout')+5]==['document','lease','acquire'] and '--document' in e['command'] and e['command'][e['command'].index('--document')+1]==document)
            contender=next(e for e in events if e.get('result',{}).get('request_id')==c['lease_refusal'].get('request_id')) if 'request_id' in c['lease_refusal'] else next(e for e in events if e.get('result',{}).get('error',{}).get('type')=='DocumentLeaseConflict' and '--document' in e['command'] and e['command'][e['command'].index('--document')+1]==document)
            require(contender['command'][contender['command'].index('--lease')+1]==lease and contender['command'][contender['command'].index('--session')+1]!=p['session_id'],'actual acquired token/contender session')
        return dict(audit_success=True,run_id=RUN,head_sha=HEAD,artifact_id=ARTIFACT,zip_sha256=DIGEST,public_report_sha256=hashlib.sha256(pbytes).hexdigest(),first_error=dict(case=117,transport='cli',document_type=3,field='mass_properties.length_unit',read_value='inch',invalid_noop_target='inch',intended_changed_target='mm',error=event['result']['error'],protocol_validation_reached=True,worker_reached=False,native_setter_reached=False),completed=dict(cli=dict(cases=116,part=46,assembly=46,drawing=24),sdk=dict(cases=0),mcp=dict(cases=0)),registry_negative_receipts=dict(negative_counts),native_setter_calls=116,native_error_events=0,expected_operation_error_events=len(errors),max_native_boundary_seconds=max(terminal),public_group_seconds=host['duration_seconds'],owned_native_exit_confirmed=True,pids_before=host['pids_before'],pids_after=host['pids_after'],public_native_files_checked=native_files,part_geometry_comparisons=geometry_count,part_geometry_nonexact=geometry_nonexact,internal=dict(success=True,steps=139,duration_seconds=native['duration_seconds']),public_overall_accepted=False,remaining_cli_cases=23,sdk_and_mcp_reached=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--metadata-dir',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();data=json.dumps(audit(args.archive,args.metadata_dir),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(data)
    else:print(data,end='')

if __name__=='__main__':main()
