"""Coordinator independent audit of the immutable successful bounded STEP run."""
import collections,hashlib,json,math,re,sys
from pathlib import Path,PureWindowsPath
ROOT=Path(sys.argv[1])
N=ROOT/'native/swcli-native-smoke'; HEAD='422a123fbef25c8a89fbcacbd7ba5db06a74b02c'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def near(a,b,abs=1e-9,rel=0):assert math.isfinite(a) and math.isclose(a,b,abs_tol=abs,rel_tol=rel),(a,b)
run=read(ROOT/'run-api.json');assert (run['id'],run['head_sha'],run['event'],run['conclusion'])==(43299699392,HEAD,'workflow_dispatch','success')
art=next(a for a in read(ROOT/'artifacts-api.json')['artifacts'] if a['id']==13983045935)
assert art['workflow_run']['head_sha']==HEAD and sha(ROOT/'native.zip')==art['digest'].removeprefix('sha256:')
w=read(N/'step-public/report.json');r=read(N/'step-public-readback/report.json')
assert w['success'] is True and w['source_commit']==HEAD and w['cleanup_errors']==[]
assert w['host']==w['host_after'] and w['foreground_before']==w['foreground_after']
assert w['host']['owned_by_daemon'] is True and w['host']['visible'] is False and w['host']['revision']=='33.5.0'
expected=[(p,g,'cli') for p in ('ap203','ap214') for g in ('solid-surface','wireframe','wireframe-sketches')]+[('ap214','solid-surface','sdk'),('ap203','wireframe','mcp')]
assert [(x['protocol'],x['geometry'],x['surface']) for x in w['outputs']]==expected
assert len({x['path'] for x in w['outputs']})==8
files=[]
for x in w['outputs']:
 p=N/'step-public'/PureWindowsPath(x['path']).name;t=p.read_text();assert sha(p)==x['sha256']
 assert t.startswith('ISO-10303-21;') and t.rstrip().endswith('END-ISO-10303-21;')
 assert ('CONFIG_CONTROL_DESIGN' if x['protocol']=='ap203' else 'AUTOMOTIVE_DESIGN') in t
 files.append(dict(name=p.name,sha256=sha(p),size=p.stat().st_size,protocol=x['protocol'],geometry=x['geometry'],surface=x['surface']))
assert sha(N/'step-public/public-source.SLDPRT')==w['source_sha256']
events={e['label']:e for e in w['events']}
reject={'stale-cas':(1,'DocumentUpdateConflict'),'foreign-lease':(1,'DocumentLeaseConflict'),'readonly-export-rejected':(1,'ValueError')}
for name,(rc,kind) in reject.items():
 e=events[name];assert e['returncode']==rc and e['result']['error']['type']==kind
assert events['readonly-export-rejected']['result']['mutation']=={'attempted':False,'may_have_changed':False}
assert events['illegal-protocol']['returncode']==2
assert all(e['returncode']==0 for e in w['events'] if e['label'] not in {*reject,'illegal-protocol'})
receipts=[]
for output in w['outputs']:
 if output['surface']=='cli':envelope=events[output['protocol']+'-'+output['geometry']]['result']
 else:envelope=w[output['surface']+'_reply']
 if output['surface']=='cli':v=envelope
 else:
  assert envelope['success'] is True;v=envelope['result']
 assert v['ok'] is True
 pref=v['step_preferences'];assert pref['restored'] is True and pref['before']==pref['after']
 assert not v.get('preference_restore_errors')
 assert pref['requested']['swStepAP']==int(output['protocol'][2:])
 assert v['step_output']==output['content']
 assert v['document']['modified'] is False and v['document']['active'] is False and v['document']['current'] is False
 receipts.append(v)
assert r['success'] is True and r['cleanup_errors']==[] and r['full_acceptance_eligible'] is False and len(r['cases'])==8
assert r['host']['visible'] is False and r['host']['revision']=='33.5.0'
raw=[]
for output,c in zip(w['outputs'],r['cases']):
 assert c['public_output']==output and c['success'] is True and c['actual_step']==output['content']
 assert c['import_return']['document_returned'] is True and c['step_import_errors']==0 and c['import_return']['arg_string']=='r'
 b=c['null_sketch_import']['binding'];assert b['status']=='verified' and b['explicit_invoke_attempted'] is True
 assert b['actual_argument']['observed_varianttype']==9 and b['actual_argument']['observed_value_is_none'] is True
 assert b['GetIDsOfNames']['value']==227 and b['original_return_policy_completed'] is True
 assert b['existing_python_state']==b['state_after_name_lookup']
 assert b['host_rewrapped'] is False and b['original_bound_method_used'] is False
 assert b['installed_contract']['verified'] is True and b['installed_contract']['arg_types']==[[8,1],[8,1],[9,1],[16387,3]]
 assert c['null_sketch_import']['factory_argument_used'] is False
 assert c['null_sketch_import']['prehost_proof']['binding_package']['verified'] is True
 j=c['sketch_observer_preferences'];assert j['status']=='restored' and j['restored'] is True and j['before']==j['after'] and j['restore_errors']==[]
 desired={k:v['value'] for k,v in c['actual_import_preferences'].items()};assert desired==j['requested'] and len(desired)==8
 assert desired==dict(swMultiCAD_Enable3DInterconnect=False,swImportSolidSurface=True,swImportFreeCurves=True,swImportNeutral_SolidandSurface=True,swImportNeutral_FreeCurvesAndPoints=True,swImportStepConfigData=False,swImportCurvePreference=0,swImportNeutral_CurvesAndPointsOption=0)
 a,z=c['imported_geometry'],c['reopened_imported_geometry']
 if output['geometry']=='solid-surface':
  assert a['metrics']['solid_body_count']==z['metrics']['solid_body_count']==1
  assert len(a['bodies'])==len(z['bodies'])==1
  for aa,zz in ((a['metrics'],z['metrics']),(a['bodies'][0],z['bodies'][0])):
   for k,value in (('volume_mm3',12000),('surface_area_mm2',3800)):
    assert aa[k]==zz[k];near(aa[k],value,abs=1e-5,rel=1e-7)
   for k,value in [('x',0),('y',0),('z',5)]:near(aa['centroid_mm'][k],value);near(zz['centroid_mm'][k],value);near(aa['centroid_mm'][k],zz['centroid_mm'][k])
 else:
  lengths=[10]*4+[30]*4+[40]*4
  if output['geometry']=='wireframe-sketches':lengths=sorted(lengths+[30]*2+[40]*2+[50]*2)
  for g in (a,z):
   assert g['complete'] is True and g['segment_count']==len(lengths)==len(g['lengths_mm'])
   for x,y in zip(g['lengths_mm'],lengths):near(x,y)
   near(g['total_length_mm'],sum(lengths))
   inv=g['feature_inventory'];assert len({x['feature_id'] for x in inv})==len(inv)
   for row in inv:
    if row['kind']=='3DProfileFeature':assert type(row['feature_health']['code']) is int and row['feature_health']['code']==0
 s=c['imported_save'];o=c['imported_reopen'];assert s['ok'] is True and s['save_errors']==0 and s['save_warnings'] is None
 assert s['document']['modified'] is False and o['document']['modified'] is False
 assert o['ok'] is True and o['read_only'] is True and o['api_errors']==o['api_warnings']==0 and s['output']==o['path']
 p=N/'step-public-readback'/PureWindowsPath(s['output']).name
 assert sha(p)==c['imported_native_sha256'] and p.stat().st_size==s['artifact']['size_bytes']
 raw.append(dict(output=output,native_sha256=sha(p),before=a,after=z,preferences=j))
t=[json.loads(l) for l in (N/'step-public-readback/trace.jsonl').read_text().splitlines()]
counts=collections.Counter((x.get('call'),x.get('phase')) for x in t)
for label,num in [('LoadFile4',8),('save-imported-native',8),('reopen-imported-native',8),('ExitApp',1),('WaitForOwnedProcess',1),('CloseProcessHandle',1)]:
 assert counts[label,'begin']==counts[label,'end']==num
assert not any(x.get('phase')=='error' for x in t)
native=[]
for l in (N/'step-public/daemon.stderr.log').read_text().splitlines():
 try:x=json.loads(l)
 except ValueError:continue
 if x.get('phase')=='begin' and 'SaveAs' in x.get('call',''):native.append(x)
assert len(native)==8 and all(x['call']=='IModelDoc2.SaveAs3' and x['operation']=='document.export' for x in native)
result=dict(schema='swcli.step-public-success-independent.v1',run=run['id'],head=HEAD,artifact_id=art['id'],original_zip_sha256=sha(ROOT/'native.zip'),source_and_digest_verified=True,public_writer_cases=8,reader_save_readonly_reopen_cases=8,cli_cases=6,sdk_cases=1,mcp_cases=1,public_outputs=files,writer_receipts=receipts,reader_raw_geometry_and_restoration=raw,source_foreground_host_unchanged=True,cas_lease_readonly_refusals_verified=True,reader_owned_exit_wait_completed=True,global_process_empty_not_asserted=True,old_scalar_save_still_used=True,modern_api_migration_not_claimed=True,bounded_step_acceptance=True,full_19_group_acceptance=False,native_acceptance_passed=True,merge_ready=True,released=False,writer_report_sha256=sha(N/'step-public/report.json'),reader_report_sha256=sha(N/'step-public-readback/report.json'),reader_trace_sha256=sha(N/'step-public-readback/trace.jsonl'))
print(json.dumps(result,indent=2))
