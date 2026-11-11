"""Audit only the pinned original public timeout ZIP; no product, gate or COM imports."""
import argparse
from collections import Counter,defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import zipfile

spec=importlib.util.spec_from_file_location('_unit_data_checks',Path(__file__).with_name('audit-units-write-42414478796.py'))
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
require=checks.require;typed=checks.typed;fingerprint=checks.fingerprint
RUN=42664223806
HEAD='64af40c908c01ca20027d06799eaec702627e5ee'
ARTIFACT=13698368440
DIGEST='5ac6169f03d869379d349e48c116d5ec7a204f7ab47d7fe68f7f933c875f34a9'
BASE='swcli-native-smoke/'


def audit(archive,metadata):
    digest=hashlib.sha256(archive.read_bytes()).hexdigest();require(digest==DIGEST,'original ZIP digest')
    a=json.loads((metadata/'artifact.json').read_bytes());r=json.loads((metadata/'run-completed.json').read_bytes());jobs=json.loads((metadata/'jobs-completed.json').read_bytes())
    require(a['id']==ARTIFACT and a['digest']=='sha256:'+digest and a['size_in_bytes']==archive.stat().st_size,'artifact identity/size')
    require(a['workflow_run']['id']==r['id']==RUN and a['workflow_run']['head_sha']==r['head_sha']==HEAD and r['conclusion']=='failure','run/head/status')
    require([s['name'] for j in jobs['jobs'] for s in j['steps'] if s['conclusion']=='failure']==['Verify public document unit profile CLI'],'first failed step')
    with zipfile.ZipFile(archive) as z:
        raw=z.read(BASE+'units-public-acceptance/cli/public-unit-profile.json');p=json.loads(raw)
        host=json.loads(z.read(BASE+'units-public-acceptance/host-report.json'));native=json.loads(z.read(BASE+'units-write-calibration/report.json'))
        require(p['success'] is False and p['changed_write_acceptance'] is False and p['state']=='running' and p['stage']=='unit-write-source-preflight','interrupted public state')
        require(host['source_commit']==native['source_commit']==HEAD and native['success'] is True and [len(c['write_steps']) for c in native['cases']]==[46,46,47],'internal source/reach')
        require(native['duration_seconds']<=1800 and native['owned_native_exit_confirmed'] is True and native['cleanup_errors']==[] and native['pids_before']==native['pids_after']==[],'internal budget/lifecycle')
        require(host['failure']==dict(type='RuntimeError',message='public group exceeded 1800s') and host['duration_seconds']>1800 and host['success'] is False,'first error/budget')
        stop=json.loads(z.read(BASE+'units-public-acceptance/stop.stdout'))
        require(stop['success'] is False and stop['error']['code']=='ActiveDocument' and host['stop_exit_code']==1 and not host.get('owned_native_exit_confirmed') and 'pids_after' not in host,'cleanup not confirmed')
        require([c['type'] for c in host['cleanup_errors'] if 'type' in c]==['RuntimeError'] and {c.get('stage') for c in host['cleanup_errors']}=={None,'owned-daemon-termination','group-budget'},'secondary cleanup errors')
        require(len(p['unit_cases'])==155 and [c['transport'] for c in p['unit_cases']]==['cli']*139+['sdk']*16,'actual transport start')
        steps=[s for c in native['cases'] for s in c['write_steps']];counts=Counter();negative=Counter();geometry_count=nonexact=0;files=0;deferred=[]
        for index,case in enumerate(p['unit_cases'][:154]):
            s=steps[index%139];require(case['success'] is True and case['domain']==[s['before']['document_type'],fingerprint(s['before']),s['field'],s['native_target']],'complete domain binding')
            before=case['read'];write=case['write'];after=case['after_write'];ro=case['readonly_read'];final=case['final_read']
            require(typed(before['unit_profile'])==typed(write['before'])==typed(s['before']),'complete source')
            require(typed(write['unit_profile'])==typed(after['unit_profile'])==typed(ro['unit_profile'])==typed(final['unit_profile'])==typed(s['after']),'complete after/readonly')
            require(write['native_return_value'] is True and write['changed'] is True and write['mutation']==dict(attempted=True,may_have_changed=True),'single changed receipt')
            noop=case['noop'];reference=before if case['noop_phase']=='before-write' else after
            require(noop['changed'] is False and noop['mutation']==dict(attempted=False,may_have_changed=False) and noop['document']==reference['document'] and typed(noop['before'])==typed(noop['unit_profile'])==typed(reference['unit_profile']),'noop zero exact state')
            if case['noop_phase']=='after-write':
                require(case['read_only_source_value']=='inch' and case['document_type']==3 and s['field']=='mass_properties.length_unit' and s['value']=='mm' and after['document']['modified'] is True,'old illegal inch fix');deferred.append(dict(case=index+1,transport=case['transport'],changed_target='mm',noop_changed=False))
            require(after['document']==write['document'] and final['document']==ro['document'] and case['reopen']['document']['document_id']!=case['open']['document']['document_id'],'exact reread/fresh identity')
            require(case['save']['api_saved'] is True and case['save']['save_errors']==0 and case['save']['save_warnings'] is None and case['save']['document']['modified'] is False,'save')
            require(all(c['document']['active'] is False for c in (before,write,ro,final)),'background state')
            for label,error in [('lease_refusal','DocumentLeaseConflict'),('stamp_refusal','DocumentUpdateConflict'),('cas_refusal','DocumentUnitProfileConflict'),('readonly_refusal','ValueError')]:
                receipt=case[label];require(receipt['ok'] is False and receipt['error']['type']==error,'actual negative receipt')
                if label not in ('lease_refusal','stamp_refusal'):require(receipt['mutation']==dict(attempted=False,may_have_changed=False),'negative zero mutation')
                negative[error]+=1
            if 'custom_closed_refusal' in case:
                receipt=case['custom_closed_refusal'];require(receipt['error']['type']=='UnitProfileCalibrationRequired' and receipt['mutation']==dict(attempted=False,may_have_changed=False),'closed domain zero write');negative['UnitProfileCalibrationRequired']+=1
            require(hashlib.sha256(z.read(BASE+'units-write-calibration/'+s['source_file'].replace('\\','/'))).hexdigest()==s['source_sha256']==case['source_sha256'],'native source bytes')
            filename='public-write-%03d.%s'%(index+1,('SLDPRT','SLDASM','SLDDRW')[case['document_type']-1])
            require(hashlib.sha256(z.read(BASE+'units-public-acceptance/cli/'+filename)).hexdigest()==case['saved_sha256'],'saved public bytes');files+=2
            if case['document_type']==1:
                for label,compare in [('geometry_after_write','comparison_after_write'),('geometry_readonly','comparison_readonly')]:
                    checks.geometry(case['geometry_before'],case[label],case[compare]);geometry_count+=1;nonexact+=not case[compare]['exact_equal']
            counts[(case['transport'],case['document_type'])]+=1
        require(dict(counts)=={('cli',1):46,('cli',2):46,('cli',3):47,('sdk',1):15} and len(deferred)==1,'completed counts/old fix')
        rows=[json.loads(line) for line in z.read(BASE+'units-public-acceptance/cli/transport-events.jsonl').splitlines()]
        require([r['sequence'] for r in rows]==list(range(1,len(rows)+1)),'durable journal sequence')
        latest={r['event_index']:r for r in rows};pending=[v for v in latest.values() if v['event']['state']!='completed'];require(len(pending)==1,'one interrupted request')
        interrupted=pending[0];request=interrupted['event']['wire_request'];require(request['operation']=='document.create' and interrupted['transport']=='sdk' and 'wire_response' not in interrupted['event'],'raw pending boundary')
        require(latest[interrupted['event_index']-1]['event']['wire_response']['success'] is True and latest[interrupted['event_index']-1]['event']['wire_request']['operation']=='document.open','source open reached')
        require(p['unit_cases'][-1]['success'] is False and 'write' not in p['unit_cases'][-1] and p['unit_cases'][-1]['domain']==[1,fingerprint(steps[15]['before']),steps[15]['field'],steps[15]['native_target']],'SDK16 not counted')
        traces=[]
        for line in z.read(BASE+'units-public-acceptance/daemon.stderr').decode(errors='replace').splitlines():
            if line.startswith('{'):
                try:t=json.loads(line)
                except ValueError:continue
                if t.get('event')=='swcli.native-call':traces.append(t)
        errors=[t for t in traces if t['phase']=='error'];require(len(errors)==308 and all(t['sequence']==0 and t['exception_type'] in ('DocumentLeaseConflict','DocumentUpdateConflict') for t in errors),'only expected operation errors')
        setters=[t for t in traces if t['phase']=='begin' and t['call']=='IModelDocExtension.SetUserPreferenceInteger']
        require(len(setters)==154 and len({t['worker_pid'] for t in traces})==1,'actual setters/single worker')
        require(any(t['request_id']==request['request_id'] and t['sequence']==0 and t['phase']=='end' for t in traces),'pending create native end without durable reply')
        terminals=[t['duration_ms']/1000 for t in traces if t['phase']!='begin'];require(max(terminals)<=600,'native call bound')
        events=p['events'];timing={}
        for transport in ('cli','sdk','mcp'):
            durations=[c['duration_seconds'] for c in p['unit_cases'] if c['transport']==transport and c.get('success')];ev=[e for e in events if e.get('transport')==transport];ops=defaultdict(list)
            for e in ev:
                offset=e['command'].index('--request-timeout')+2;operation='.'.join(e['command'][offset:offset+2]);ops[operation].append(e['transport_elapsed_seconds'])
            timing[transport]=dict(completed_cases=len(durations),case_seconds=sum(durations),transport_seconds=sum(e['transport_elapsed_seconds'] for e in ev),events=len(ev),case_median_seconds=statistics.median(durations) if durations else None,operations={k:dict(count=len(v),seconds=sum(v),median_seconds=statistics.median(v)) for k,v in sorted(ops.items())})
        # Link acquired real owner token and contender session to actual transport events.
        for c in p['unit_cases'][:154]:
            document=c['read']['document']['document_id'];ev=[e for e in events if '--document' in e['command'] and e['command'][e['command'].index('--document')+1]==document]
            owner=next(e['result']['lease']['lease_id'] for e in ev if e['command'][e['command'].index('--request-timeout')+2:e['command'].index('--request-timeout')+5]==['document','lease','acquire'])
            contender=next(e for e in ev if e.get('result',{}).get('error',{}).get('type')=='DocumentLeaseConflict')
            require(contender['command'][contender['command'].index('--lease')+1]==owner and contender['command'][contender['command'].index('--session')+1]!=p['session_id'],'real lease owner/contender')
        return dict(audit_success=True,run_id=RUN,head_sha=HEAD,artifact_id=ARTIFACT,zip_sha256=digest,public_report_sha256=hashlib.sha256(raw).hexdigest(),first_error=host['failure'],public_overall_accepted=False,completed=dict(cli=dict(cases=139,part=46,assembly=46,drawing=47),sdk=dict(cases=15,part=15,assembly=0,drawing=0),mcp=dict(cases=0)),pending=dict(transport='sdk',case_in_transport=16,field=steps[15]['field'],value=steps[15]['value'],source_open_reply_durable=True,foreground_create_native_ended=True,foreground_create_reply_durable=False,changed_setter_reached=False),old_inch_noop_fix=deferred,negative_receipts=dict(negative),native_setter_calls=154,native_error_events=0,expected_operation_error_events=len(errors),trace_events=len(traces),max_native_boundary_seconds=max(terminals),public_native_files_checked=files,part_geometry_comparisons=geometry_count,part_geometry_nonexact=nonexact,public_group_seconds=host['duration_seconds'],owned_native_exit_confirmed=False,cleanup_errors=host['cleanup_errors'],pids_before=host['pids_before'],pids_after=None,internal=dict(success=True,steps=139,duration_seconds=native['duration_seconds']),timing=timing)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--metadata-dir',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();data=json.dumps(audit(args.archive,args.metadata_dir),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(data)
    else:print(data,end='')

if __name__=='__main__':main()
