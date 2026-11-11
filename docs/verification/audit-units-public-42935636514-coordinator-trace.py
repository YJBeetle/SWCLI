from pathlib import Path
import argparse
import json,zipfile,collections,hashlib
parser=argparse.ArgumentParser();parser.add_argument('--repository',type=Path,default=Path(__file__).resolve().parents[2]);parser.add_argument('--output',type=Path);args=parser.parse_args()
repo=args.repository;archive=repo/'evidence/units-profile/public-short-path-42935636514/original-native.zip';out=args.output
with zipfile.ZipFile(archive) as z:
 b='swcli-native-smoke/units-public-acceptance/';p=json.loads(z.read(b+'cli/public-unit-profile.json'));counts=collections.defaultdict(collections.Counter);pending={};workers=set();errors=collections.Counter();frames=0;maxms=0
 with z.open(b+'daemon.stderr') as f:
  for line in f:
   if not line.startswith(b'{'):continue
   try:t=json.loads(line)
   except ValueError:continue
   if t.get('event')!='swcli.native-call':continue
   frames+=1;workers.add(t['worker_pid']);key=(t['request_id'],t['sequence']);phase=t['phase'];call=t['call'];counts[t['request_id']][(phase,call)]+=1
   if phase=='begin':
    assert key not in pending;pending[key]=call
   else:
    assert pending.pop(key)==call
    maxms=max(maxms,t.get('duration_ms',0));assert maxms<=600000
    if phase=='error':errors[(t['exception_type'],t['sequence'])]+=1
 assert sum(c[('begin','IModelDocExtension.SetUserPreferenceInteger')] for c in counts.values())==417
 assert not pending and workers=={6088} and errors=={('DocumentLeaseConflict',0):417,('DocumentUpdateConflict',0):417}
 events=p['events'];ids=[e['result']['request_id'] for e in events];assert len(ids)==len(set(ids))
 changed=noop=guard=0;native_setters=0;negative=collections.Counter();guard_bodies=collections.Counter()
 case_docs={c['read']['document']['document_id']:c for c in p['unit_cases']};leases={}
 for e in events:
  command=e['command'];result=e['result'];rid=result['request_id'];counter=counts[rid];action=result.get('action');doc=result.get('document',{}).get('document_id')
  if '--document' in command and 'lease' in command:
   requested=command[command.index('--document')+1]
   if action=='document.lease-acquire' and result.get('ok'):leases[requested]=result['lease']['lease_id']
  offset=command.index('--request-timeout')+2
  if action!='document.unit-profile-set' and command[offset:offset+2]!=['document','unit-profile-set']:continue
  setters=counter[('begin','IModelDocExtension.SetUserPreferenceInteger')];native_setters+=setters
  if result.get('ok') and result.get('changed'):
   assert setters==1 and counter[('end','IModelDocExtension.SetUserPreferenceInteger')]==1
   assert counter[('begin','IModelDoc2.SetSaveFlag')]<=1
   assert doc in case_docs;case=case_docs[doc];body={k:v for k,v in result.items() if k!='request_id'};assert body==case['write']
   assert json.loads(command[command.index('--if-snapshot')+1])==case['read']['unit_profile']
   assert command[command.index('--if-update-stamp')+1]==str(case['read']['document']['update_stamp']);changed+=1
  elif result.get('ok'):
   assert result['changed'] is False and setters==counter[('begin','IModelDoc2.SetSaveFlag')]==0;noop+=1
  else:
   assert setters==counter[('begin','IModelDoc2.SetSaveFlag')]==0;guard+=1
   negative[result['error']['type']]+=1;guard_bodies[json.dumps({k:v for k,v in result.items() if k!='request_id'},sort_keys=True)]+=1
 print('counts',dict(changed=changed,noop=noop,guard=guard,setters=native_setters),flush=True)
 assert changed==noop==417 and guard==2010 and native_setters==417
 assert negative=={'DocumentLeaseConflict':417,'DocumentUpdateConflict':417,'DocumentUnitProfileConflict':417,'ValueError':417,'UnitProfileCalibrationRequired':342}
 expected_guard_bodies=collections.Counter(json.dumps(c[k],sort_keys=True) for c in p['unit_cases'] for k in ('lease_refusal','stamp_refusal','cas_refusal','readonly_refusal'))
 assert all(guard_bodies[k]>=v for k,v in expected_guard_bodies.items())
 # Lease conflicts use an actual held owner token in another session.
 for e in events:
  result=e['result'];command=e['command']
  if result.get('error',{}).get('type')=='DocumentLeaseConflict':
   doc=command[command.index('--document')+1]
   relevant=[x for x in events if '--document' in x['command'] and x['command'][x['command'].index('--document')+1]==doc and x['result'].get('lease') and x['command'][x['command'].index('--request-timeout')+2:x['command'].index('--request-timeout')+5]==['document','lease','acquire']]
   owner=next(x['result']['lease']['lease_id'] for x in relevant if x['result'].get('ok'))
   assert command[command.index('--lease')+1]==owner and command[command.index('--session')+1]!=p['session_id']
 result=dict(success=True,trace_frames=frames,one_worker=list(workers),all_native_begin_terminal_pairs_complete=True,max_native_boundary_seconds=maxms/1000,expected_operation_errors={str(k):v for k,v in errors.items()},native_api_errors=0,changed_setters=changed,noop_zero_write=noop,guards_zero_write=guard,negative_receipts=dict(negative),changed_full_snapshot_and_stamp_correlated=True,lease_owner_and_contender_correlated=True,transport_events=len(events),public_report_sha256=hashlib.sha256(z.read(b+'cli/public-unit-profile.json')).hexdigest())
 if out:out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
