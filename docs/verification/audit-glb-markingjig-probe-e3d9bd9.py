"""Offline audit of one failed reviewed MarkingJig probe. Never imports COM or runs CAD."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def audit(root):
    def read(name):return json.loads((root/name).read_text(encoding='utf-8-sig'))
    def sha(name):return hashlib.sha256((root/name).read_bytes()).hexdigest()
    ctx=read('allocation-inputs.json');launch=read('launcher-context.json');report=read('native-output/report.json')
    supervisor=read('native-output/markingjig-supervisor.json');case=report['cases'][0]
    assert ctx['source_head']=='e3d9bd9a4ce726e6fdb97277c73fca02237c6c08'
    assert ctx['approved_inventory_sha256']=='d7db20f8041424115a97b91376001be759b32fad6e5faa2cc405fe971a13185d'
    assert len(ctx['selected'])==10 and len(set(ctx['selected']))==10
    assert sha('markingjig-code-e3d9bd9.zip')==ctx['package_sha256']
    assert launch['candidate_launch_attempts']==1 and launch['candidate_exit']==1 and launch['first_error'] is None
    assert launch['mode']=='probe' and launch['copied_code_sha256']==launch['code_hashes_after']==ctx['code_files_sha256']
    assert launch['native_pids_before']==launch['native_pids_immediately_before_probe']==launch['native_pids_after']==[]
    assert len(launch['copies'])==10 and {r['name'] for r in launch['copies']}==set(ctx['selected'])
    for row in launch['copies']:
        assert row['readonly'] is True and row['nlink']==1 and row['sha256']==launch['copy_hashes_after'][row['name']]
    assert report['success'] is False and supervisor['success'] is False
    assert supervisor['worker_exit']==1 and supervisor['failure'] is None
    assert supervisor['native_pids_before']==supervisor['native_pids_after']==[]
    assert case['mode']=='probe' and case['export_attempts']==0 and case['observations']==[]
    assert case['open_errors']==0 and case['open_warnings']==2
    assert case['requested_spec']==case['actual_spec']==dict(DocumentType=2,ReadOnly=True,Silent=True,UseLightWeightDefault=False,LightWeight=False,ViewOnly=False,LoadModel=True,AutoRepair=False)
    assert report['failure']['message']=='OpenDoc7 failed/warned; no alternate opening'
    assert report['cleanup_errors']==[dict(stage='source-hash-postcheck',error='working-copy bytes/identity/state changed')]
    assert supervisor['audit']['modern_save_attempts']==0 and supervisor['audit']['forbidden_calls']==[]
    assert supervisor['audit']['report_sha256']==sha('native-output/report.json')
    trace=[json.loads(line) for line in (root/'native-output/trace.jsonl').read_text().splitlines()]
    begin=Counter(r['call'] for r in trace if r['phase']=='begin')
    assert begin['OpenDoc7-readonly']==1 and not any('export' in name.lower() or 'save' in name.lower() for name in begin)
    times={}
    for name in ('OpenDoc7-readonly','CloseDoc','ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'):
        rows=[r for r in trace if r['call']==name]
        assert [r['phase'] for r in rows]==['begin','end']
        times[name]=dict(begin=rows[0]['time'],end=rows[1]['time'],elapsed_seconds=rows[1]['time']-rows[0]['time'])
    events=[]
    for line in (root/'native-output/worker.stderr.log').read_text(encoding='utf-8-sig').splitlines():
        try:r=json.loads(line)
        except ValueError:continue
        if r.get('event')=='swcli.native-call' and r.get('phase')=='begin':events.append(r)
    assert not any('SaveAs' in r.get('call','') or 'GetDependencies' in r.get('call','') for r in events)
    assert not list((root/'native-output').rglob('*.GLB'))
    assert read('mac-originals-before.json')==read('mac-originals-after.json')
    assert len(read('mac-originals-before.json'))==11
    diff=read('vm-copy-metadata-diff.json');assert diff['errors']==[]
    assert set(diff['changes'])=={'MarkingJig.REND.SLDASM'}
    changed=diff['changes']['MarkingJig.REND.SLDASM'];assert set(changed)=={'handle_before','handle_after'}
    for channel in changed:
        assert set(changed[channel])=={'st_ctime_ns'}
        assert changed[channel]['st_ctime_ns']['after']>changed[channel]['st_ctime_ns']['before']
    assert changed['handle_before']==changed['handle_after']
    state=read('host-restore-state.json')
    assert state['restore_exit']==state['list_exit']==0 and state['schedule_modified'] is False
    assert any('Pause idle: on' in line for line in state['selected_info'])
    return dict(schema='swcli.markingjig-probe-native-audit.v1',allocation_id=ctx['allocation_id'],source_head=ctx['source_head'],evidence_audit_passed=True,probe_success=False,native_or_public_acceptance=False,
        mode='probe',candidate_launches=1,OpenDoc7_attempts=1,explicit_export_save_attempts=0,host=report['host'],worker_pid=supervisor['launch_pid'],worker_exit=1,
        primary_failure=dict(stage='OpenDoc7',errors=0,warnings=2,message=report['failure']['message'],official_2025_warning=read('official-warning2025-source.json')),
        incomplete=['actual loaded model readonly/configuration/edit state','resolved component graph','modern dependencies and broken/import census','geometry','observer process identity','GLB'],
        secondary_source_window_failure=dict(message=report['cleanup_errors'][0]['error'],changes=diff['changes'],content_hashes_unchanged=True,all_other_recorded_copy_metadata_fields_unchanged=True),
        owned_cleanup_times=times,native_pids_before=[],native_pids_after=[],Mac_originals_and_existing_GLB_fingerprints_unchanged=True,approved_copies=10,inventory_sha256=ctx['approved_inventory_sha256'],package_sha256=ctx['package_sha256'],code_before_after_unchanged=True,
        host_restoration=state,evidence_directory=str(root),raw_sha256={name:sha(name) for name in ('allocation-inputs.json','launcher-context.json','native-output/report.json','native-output/markingjig-supervisor.json','native-output/trace.jsonl','native-output/worker.stderr.log','mac-originals-before.json','mac-originals-after.json','vm-copy-OS-postcheck.stdout','vm-copy-metadata-diff.json','host-restore-state.json')},
        limits=['No retry/repair/resolve/configuration change/alternate open or invoke.','Warning is checked against official2025 metadata, not a subsequent CAD query.','Only bytes and recorded metadata were checked; no complete file-access timeline or underlying cause inferred.','Source-window postcheck failed independently of successful CloseDoc/ExitApp/owned wait; not a GLB content result.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path);args=parser.parse_args()
    print(json.dumps(audit(args.evidence),indent=2,ensure_ascii=False))
