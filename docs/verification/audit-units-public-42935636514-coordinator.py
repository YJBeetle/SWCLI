from pathlib import Path
import argparse
import json,zipfile,hashlib,collections,math,ntpath,base64,ast
parser=argparse.ArgumentParser();parser.add_argument('--repository',type=Path,default=Path(__file__).resolve().parents[2]);parser.add_argument('--output',type=Path);args=parser.parse_args()
repo=args.repository;meta=repo/'docs/evidence/units-profile/public-short-path-42935636514';raw=repo/'evidence/units-profile/public-short-path-42935636514';sha='c34b58cd4796d7778eae31b01d69bacc1108d9c9c12e22908b6d054c37fb7117';head='459b0cf88892fe1af013156994568d6e52e6df2e'
run=json.loads((meta/'run-terminal.json').read_bytes());arts=json.loads((meta/'artifacts-terminal.json').read_bytes())['artifacts'];a=next(a for a in arts if a['id']==13820837309)
assert run['head_sha']==head and run['conclusion']=='success' and run['event']=='workflow_dispatch' and run['run_attempt']==1
assert a['digest']=='sha256:'+sha and (raw/'original-native.zip').stat().st_size==a['size_in_bytes']==47688318 and hashlib.sha256((raw/'original-native.zip').read_bytes()).hexdigest()==sha
assert not any('install-logs' in a['name'] for a in arts)
tree=ast.parse((repo/'src/swcli/document_unit_write_domains.py').read_text());admitted=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and n.targets[0].id=='REVIEWED_UNIT_TRANSITIONS'));admitted={tuple(row[:4]):row[4] for row in admitted};assert len(admitted)==137
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def native_name(path):
 s=path.replace('\\','/')
 while '//' in s:s=s.replace('//','/')
 return 'swcli-native-smoke/'+s.split('/swcli-native-smoke/',1)[1]
with zipfile.ZipFile(raw/'original-native.zip') as z:
 prefix='swcli-native-smoke/units-public-acceptance/';h=json.loads(z.read(prefix+'host-report.json'));p=json.loads(z.read(prefix+'cli/public-unit-profile.json'))
 assert h['success'] and h['source_commit']==head and not h['full_acceptance_eligible'] and h['cleanup_errors']==[] and h['pids_before']==h['pids_after']==[]
 assert h['owned_native_exit_confirmed'] is True and h['cli_frontend_exit_confirmed_by_wrapper'] is True and h['stop_exit_code']==h['public_exit_code']==0 and h['duration_seconds']<1800
 obs=h['identity_observations'][0];e=obs['image_path_identity'];x=e['expansion'];assert e['samefile'] is True and e['recorded_file_ids_match'] is True and e['file_ids_available'] is True
 assert e['raw_stat']==e['expected_stat'] and ntpath.normcase(x['expanded_image'])==ntpath.normcase(obs['expected_image'])
 assert x['ctypes_bytes']=={'DWORD':4,'wchar':2} and base64.b64decode(x['buffer_prefix_b64'])==x['expanded_image'].encode('utf-16-le')+b'\0\0'
 assert h['owned_native_identity']==obs['observed_identity'] and obs['observed_identity']['image']!=x['expanded_image']
 assert p['success'] is True and p['state']=='completed' and p['cleanup_errors']==[] and not p['full_acceptance_eligible']
 cases=p['unit_cases'];assert len(cases)==417;counts=collections.Counter((c['transport'],c['document_type']) for c in cases)
 assert counts==collections.Counter({(t,k):n for t in ['cli','sdk','mcp'] for k,n in [(1,46),(2,46),(3,47)]})
 files=geometry=changed=noops=0;domains={t:set() for t in ['cli','sdk','mcp']}
 for c in cases:
  assert c['success'] is True and c['read']['ok'] and c['write']['ok'] and c['noop']['ok']
  assert c['noop']['changed'] is False and c['noop']['mutation']=={'attempted':False,'may_have_changed':False}
  assert c['write']['before']==c['read']['unit_profile']
  assert c['domain'][0]==c['document_type'] and c['domain'][1]==fingerprint(c['read']['unit_profile'])
  domain=tuple(c['domain']);domains[c['transport']].add(domain)
  assert fingerprint(c['write']['unit_profile'])==admitted[domain] and c['write']['unit_profile']['values'][domain[2]]['native_value']==domain[3]
  assert c['after_write']['unit_profile']==c['write']['unit_profile']==c['readonly_read']['unit_profile']==c['final_read']['unit_profile']
  for k in ['lease_refusal','stamp_refusal','cas_refusal','readonly_refusal']:
   assert c[k]['ok'] is False and not c[k].get('mutation',{}).get('attempted',False)
  changed+=c['write']['changed'] is True;noops+=c['write']['changed'] is False
  if c['write']['changed']:assert c['write']['native_return_value'] is True and c['write']['document']['modified'] is True
  assert c['save']['api_saved'] is True and c['save']['save_errors']==0 and c['save']['save_warnings'] is None
  assert c['reopen']['read_only'] is True and c['reopen']['api_errors']==0 and c['reopen']['document']['modified'] is False
  assert c['open']['document']['document_id']!=c['reopen']['document']['document_id']
  for path,expected in [(c['open']['path'],c['source_sha256']),(c['save']['output'],c['saved_sha256'])]:
   assert hashlib.sha256(z.read(native_name(path))).hexdigest()==expected;files+=1
  if c['document_type']==1:
   before=c['geometry_before']
   for key in ['geometry_after_write','geometry_readonly']:
    after=c[key];assert all(after[k]==before[k] for k in ['solid_body_count','volume_mm3','surface_area_mm2'])
    assert all(math.isfinite(after['centroid_mm'][k]) and abs(after['centroid_mm'][k]-before['centroid_mm'][k])<=1e-12 for k in 'xyz');geometry+=1
 assert all(v==set(admitted) for v in domains.values())
 cold=p['cold_start_coverage'];print('coldkeys',list(cold));assert len(cold['probes'])==3 and all(c['equal'] is True for c in cold['probes'])
 for probe in cold['probes']:
  helper=json.loads(probe['helper_stdout']);fresh=json.loads(probe['fresh_stdout'])
  assert helper['ok'] is fresh['ok'] is True and helper['unit_profile']==fresh['unit_profile']==probe['snapshot']
  assert helper['document']==fresh['document']==probe['helper_document']
  assert {k:v for k,v in helper.items() if k!='request_id'}=={k:v for k,v in fresh.items() if k!='request_id'}
 assert len(p['case_cleanup'])==417 and all(c['empty'] is True and c['remaining_document_ids']==[] and c['open_document_count']==0 for c in p['case_cleanup'])
 result=dict(success=True,run=run['id'],head=head,native_zip_sha256=sha,public_cases=len(cases),transport_counts={str(k):v for k,v in counts.items()},exact_domains_each=137,admitted_complete_after_hashes_each=True,changed_cases=changed,noops_cases=noops,source_target_hashes=files,part_geometry_comparisons=geometry,standalone_cold=3,public_report_sha256=hashlib.sha256(z.read(prefix+'cli/public-unit-profile.json')).hexdigest(),native_identity_raw_retained=True,same_installed_file_proven=True,owned_exit_and_helper_confirmed=True,cleanup_errors=[],duration_seconds=h['duration_seconds'],installation_zip='absent as expected: failure-only upload',note='Fundamental original receipt audit; correlated per-request trace/CAS audit separately required before merge')
 if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
