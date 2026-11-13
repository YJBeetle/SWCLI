"""Replay existing05 receipts only. Exact differences, no acceptance tolerance or VM/CAD work."""
from collections import Counter
from decimal import Decimal,localcontext
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import zipfile

REPO=Path('/Users/YJBeetle/.codex/worktrees/glb-export-repair/SWCLI')
SHARE=Path('/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-a7ecb97-05')
HEAD='a7ecb97d30f0913105080d93e1725acea6e67ce7'


def require(value,message):
    if not value:raise RuntimeError(message)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':'))
def differences(a,b,path=()):
    if type(a) is not type(b):return [dict(path=list(path),before=a,after=b)]
    if isinstance(a,dict):
        if a.keys()!=b.keys():return [dict(path=list(path),before=a,after=b)]
        return [r for k in a for r in differences(a[k],b[k],path+(k,))]
    if isinstance(a,list):
        if len(a)!=len(b):return [dict(path=list(path),before=a,after=b)]
        return [r for i,(x,y) in enumerate(zip(a,b)) for r in differences(x,y,path+(i,))]
    # Preserve signed zero and scalar type distinctions; never remove fields.
    return [] if canonical(a)==canonical(b) else [dict(path=list(path),before=a,after=b)]
def ordered_bits(value):
    require(type(value) is float and math.isfinite(value),'finite binary64 observation required')
    bits=struct.unpack('>Q',struct.pack('>d',value))[0]
    return (~bits)&((1<<64)-1) if bits>>63 else bits|(1<<63)


def audit():
    report=json.loads((SHARE/'native-output/report.json').read_bytes())
    launcher=json.loads((SHARE/'launcher-context.json').read_bytes())
    host=json.loads((SHARE/'host-execution-context.json').read_bytes())
    supervisor=json.loads((SHARE/'native-output/markingjig-supervisor.json').read_bytes())
    proposal=json.loads((SHARE/'proposal.json').read_bytes())
    require(proposal['source_head']==host['source_head']==HEAD,'runtime head differs')
    require(host['guest_execution_attempts']==launcher['candidate_launch_attempts']==1,'unique candidate execution not proved')
    require(report['success'] is False and supervisor['success'] is False,'failed outcome changed')
    require(len(report['cases'])==1,'one real case required')
    case=report['cases'][0];observations=case['observations'];phase=case['file_phases']
    require(case['export_attempts']==supervisor['audit']['modern_save_attempts']==0,'export occurred')
    require(case['component_context_policy']=='component-bodies-probe','component context differs')
    require(len(observations)==1 and observations[0]['complete'] is False,'complete model observation invented')
    require(phase['loaded_baseline_sealed'] is False and phase['state']=='opened-not-admitted','loaded seal changed')
    rows=observations[0]['components']
    require(len(rows)==2 and rows[1]['name']=='MarkingJig-1/MarkingJigEpoxy-1','first reached part differs')
    row=rows[1];context=row['component_context'];before=row['model'];after=context['model_state_after']
    require(context['bodies_returned_type']==context['body_info_returned_type']=='tuple','native return types differ')
    require(context['body_count']==len(context['bodies'])==3 and context['body_info_raw']==[1,1,1],'native component bodies differ')
    require(all(len(body['bounds_raw'])==6 and len(body['mass_properties_raw'])==12 for body in context['bodies']),
            'three body geometries incomplete')
    require(context['complete'] is False,'context completion invented')
    changed=differences(before,after)
    expected={('geometry',0,'centroid_m',2),('geometry',1,'centroid_m',0),('geometry',1,'volume_m3')}
    require(len(changed)==3 and {tuple(r['path']) for r in changed}==expected,'additional model state difference')
    for delta in changed:
        a,b=delta['before'],delta['after'];distance=abs(ordered_bits(a)-ordered_bits(b))
        require(distance==1,'observed adjacent binary64 values changed')
        with localcontext() as precision:
            precision.prec=200
            exact=abs(Decimal.from_float(a)-Decimal.from_float(b))
            delta.update(before_repr=repr(a),after_repr=repr(b),before_hex=a.hex(),after_hex=b.hex(),
                         binary64_ULP_distance=distance,absolute_delta_exact_decimal=str(exact),
                         source_unit='m' if delta['path'][2]=='centroid_m' else 'm3')
            if delta['path'][2]=='centroid_m':delta['absolute_delta_mm_exact_decimal']=str(exact*1000)
    require(report['failure']['message']=='independent model state changed during component body observation','original fatal differs')
    require(launcher['candidate_failure']==launcher['primary_failure']==report['failure'],'native first failure not retained')
    require(launcher['first_error'] is None,'unexpected launcher first error')
    for key in ('cleanup_errors','secondary_errors'):require(launcher[key]==[],'launcher '+key)
    require(report['cleanup_errors']==[],'native cleanup error')
    for key in ('native_pids_before','native_pids_after','native_pids_after_postcleanup_OS'):
        require(launcher[key]==[],'native inventory not empty: '+key)
    for key in ('private_source_postcleanup_proof_complete','copy_hash_postcheck_complete','code_hash_postcheck_complete'):
        require(launcher[key] is True,'post proof not complete: '+key)
    bootstrap=launcher['preparation_source_postcheck']
    require(bootstrap['code_hash_postcheck_complete'] is True and bootstrap['secondary_errors']==[],'bootstrap postcheck')
    require(launcher['code_hashes_after']==proposal['code_files_sha256'],'candidate post hashes differ')
    require(bootstrap['code_hashes_after']==proposal['preparation_files_sha256'],'preparation post hashes differ')
    require(len(launcher['copy_hashes_after'])==10 and launcher['copy_hash_missing_names']==[], 'ten private input hashes incomplete')
    proofs={name:json.loads((SHARE/('host-originals-'+name+'.json')).read_bytes()) for name in ('before','after')}
    require(all(p['success'] is True and len(p['files'])==11 and p['errors']==[] for p in proofs.values()),'Mac original proof incomplete')
    require(proofs['before']['files']==proofs['after']['files'],'Mac original full fingerprints differ')
    entry=json.loads((SHARE/'entry-arrived.json').read_bytes())
    require(entry['session_query']['ok'] is True and entry['session_query']['session']==1,'actual launcher session differs')
    require(entry['entry_source_sha256']==digest(SHARE/'launch-probe.py'),'entry source identity differs')
    require('Pause idle: on' in (SHARE/'host-after.stdout').read_text(),'historical idle restoration missing')
    trace=[json.loads(line) for line in (SHARE/'native-output/trace.jsonl').read_text().splitlines() if line]
    stack=[];pairs=Counter()
    for event in trace:
        if event['phase']=='begin':stack.append(event['call'])
        else:
            require(event['phase']=='end' and stack and stack.pop()==event['call'],'unpaired trace')
            pairs[event['call']]+=1
    require(not stack,'unterminated trace')
    unique=('acquire-owned-host','OpenDoc7-readonly','read-component-GetBodies3','CloseDoc','ExitApp',
            'WaitForOwnedProcess','CloseProcessHandle','CoUninitialize')
    require(all(pairs[call]==1 for call in unique),'one native entry or cleanup count differs')
    require(not any('SaveAs' in name for name in pairs),'SaveAs trace observed')
    with zipfile.ZipFile(SHARE/'markingjig-code-a7ecb97.zip') as packed:
        require(len(packed.infolist())==8,'ZIP member count differs')
        for name,pinned in proposal['code_files_sha256'].items():
            data=packed.read(name)
            require(data==subprocess.check_output(['git','show',HEAD+':'+name],cwd=REPO),'runtime Git blob differs: '+name)
            require(hashlib.sha256(data).hexdigest()==pinned,'runtime source hash differs')
    names=('native-output/report.json','native-output/trace.jsonl','native-output/markingjig-supervisor.json',
           'launcher-context.json','entry-arrived.json','host-execution-context.json',
           'host-originals-before.json','host-originals-after.json','proposal.json','launch-probe.py','host-original-guard.py',
           'markingjig-code-a7ecb97.zip')
    return dict(schema='swcli.markingjig-probe05-native-observation-audit.v1',
      status='native-first-failure-stop; comparison-rule-unchanged',source_head=HEAD,product_head=proposal['product_head'],
      original_failure=report['failure'],host=report['host'],unique_native_call_counts={call:pairs[call] for call in unique},
      trace_events=len(trace),all_trace_begin_end_paired=True,save_export_attempts=0,
      reached_component=row['name'],referenced_configuration=row['referenced_configuration'],model_active_configuration=before['configuration'],
      GetBodies3_observed=dict(calls=1,bodies_returned_type='tuple',body_info_returned_type='tuple',bodies=3,body_info_raw=[1,1,1],
        three_component_body_geometries_retained=True,scope='one reached part only, not whole assembly or prior MarkingJigBlock mismatch'),
      independent_model_state_changes=changed,other_model_state_differences=0,
      full_model_observation_complete=False,loaded_baseline_sealed=False,context_geometry_CAS_complete=False,
      source_code_and_preparation_postchecks_complete=True,private_input_hashes=10,native_after=[],native_after_postcleanup=[],
      cleanup_errors=[],secondary_errors=[],Mac_original_files=11,Mac_original_full_fingerprints_before_after_equal=True,
      historical_idle_pause_restored='on',native_process_exit_code_not_recorded=True,
      original_evidence_sha256={name:digest(SHARE/name) for name in names},
      comparison_changes_made=False,tolerance_decision='pending user reply in coordinating chat; no acceptance decision made by this audit',
      own_operations=dict(VM=0,COM=0,CAD=0,original_artifact_writes=0,rule_changes=0,push=0,new_CI=0),
      limits=['binary64 distance quantifies serialized observations; does not establish physical change or acceptable error',
              'first-part BYREF binding success does not prove native TYPEDESC or all component configurations',
              'no complete graph/geometry/probe or GLB acceptance',
              'worker/candidate exit1 is not a recorded SOLIDWORKS native exit code'])


if __name__=='__main__':print(json.dumps(audit(),indent=2,ensure_ascii=False))
