"""Offline audit only: compiled bytes, receipts, trace, source reads and raw GLB."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
sys.dont_write_bytecode=True
BASE=Path('/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110')
REPORTS={'identity':'1bde576e93376b971451834c2e810b879ba3a22c11ee0a994cd49c3115612aaa','invoke':'a1a482bf9c3070b2ea7854281e6f2bf32cb8efda484247fa6ea1dce3ad3f4d42'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();repo=args.repo.resolve()
 buildroot=BASE/'glb-typed-build-267a34c-01';build=read(buildroot/'build.json');launcher=read(buildroot/'launcher-context.json')
 assert build['success'] is True and build['compiler_exit']==0 and launcher['helper_executions']==launcher['cad_calls']==0
 assert sha(buildroot/'TypedGlbBridge.exe')==build['helper_sha256']=='dd7567afb7f16233a62101712acea31d9e9bbfc0cde6e8ef191b83572c59aede'
 assert sha(buildroot/'SolidWorks.Interop.sldworks.dll')==build['pia_sha256']=='a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1'
 for name,value in launcher['sources'].items():assert hashlib.sha256(subprocess.check_output(['git','show','267a34c:scripts/diagnostics/typed_glb/'+name],cwd=repo)).hexdigest()==value
 for name,value in build['sources'].items():assert value==build['source_after'][name]==launcher['sources'][name]
 image=(buildroot/'TypedGlbBridge.exe').read_bytes();pe=struct.unpack_from('<I',image,0x3c)[0]
 assert image[:2]==b'MZ' and image[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',image,pe+4)[0]==0x8664 and struct.unpack_from('<H',image,pe+24)[0]==0x20b
 result=dict(schema='swcli.typed-glb-control-267a34c-offline-audit.v1',source_head=launcher['source_head'],build_original=str(buildroot),
  build_files={f.name:dict(bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(buildroot.iterdir()) if f.is_file()},helper_sha256=build['helper_sha256'],PE='AMD64/PE32+',attempts={})
 spec=importlib.util.spec_from_file_location('strict_export',repo/'src/swcli/hosts/export_validation.py');strict=importlib.util.module_from_spec(spec);spec.loader.exec_module(strict)
 for mode,wanted in REPORTS.items():
  root=BASE/('glb-typed-'+mode+'-267a34c-01');report=read(root/'report.json');supervisor=read(root/'local-supervisor.json');control=report['typed_glb_control'];producer=control['producer'];helper=read(root/'typed-glb/helper.json')
  assert sha(root/'report.json')==wanted and report['success'] is False and report['cleanup_errors']==[]
  assert producer['helper_result']==producer['helper_durable']==helper and read(root/'typed-glb/producer.json')==producer
  assert producer['success'] is True and producer['helper_exit']==0 and producer['marshal_cleanup_known'] is True
  assert producer['parcel_states']==dict.fromkeys(('app','document','extension'),'consumed') and producer['consumption_uncertain']==producer['marshal_outcome_unknown']==[]
  assert helper['success'] is True and helper['contract_accepted'] is True and helper['identity_accepted'] is True and helper['cleanup_errors']==[]
  assert helper['first_error'] is None and helper['hresult'] is None and helper['before']==producer['expected']
  assert helper['before']['exe_path']==r'C:\PROGRA~1\SOLIDW~1\SOLIDW~1\SLDWORKS.exe'
  assert helper['before']['pid']==report['host']['process_id'] and helper['python_worker_pid']==producer['python_worker_pid']==report['native_call_worker_pid']
  assert supervisor['pids_before']==supervisor['pids_after']==[] and supervisor['worker_exit']==1 and supervisor['report_sha256']==wanted
  source=sha(root/'component.SLDPRT');assert source==helper['before']['source_sha256']==producer['source_sha256']==report['cases'][0]['source_sha256']
  phases=['handshake'] if mode=='identity' else ['handshake','before-save','after-normal-return']
  assert [x['phase'] for x in helper['identity_checks']]==phases
  assert all(x['document_iunknown_same'] is True and x['extension_iunknown_same'] is True and type(x['foreground_same']) is int and x['foreground_same']==1 for x in helper['identity_checks'])
  assert [x['phase'] for x in helper['observations']]==phases and all(x['complete'] and x['current_field'] is None for x in helper['observations'])
  for observation in helper['observations']:
   fields={x['name']:x for x in observation['fields']};assert len(fields)==22
   for field in observation['fields']:
    value=field.get({'string':'text','strings':'strings','int32':'integer','int64':'integer','bool':'boolean'}[field['kind']])
    assert type(value) is type(helper['before'][field['name']]) and value==helper['before'][field['name']]
  assert [x['phase'] for x in helper['source_reads']]==phases
  for row in helper['source_reads']:
   assert row['complete'] and row['access']=='Read' and row['share']=='ReadWrite (no Delete)' and row['sha256']==source and row['error'] is None
   assert row['before']==row['after']==row['path_after'] and row['bytes_read']==row['before']['size_bytes']==(root/'component.SLDPRT').stat().st_size
  if mode=='invoke':assert all(x['before']==helper['source_reads'][0]['before'] for x in helper['source_reads'])
  native=[]
  for line in (root/'worker.stderr.log').read_text().splitlines():
   if line.startswith('{'):
    try:item=json.loads(line)
    except ValueError:continue
    if item.get('event')=='swcli.native-call':native.append(item)
  counts={fmt:sum(x.get('phase')=='begin' and x.get('request_id')=='local-export-'+fmt and x.get('call')=='IModelDocExtension.SaveAs3' for x in native) for fmt in ('STL','3MF','AMF','GLB')}
  assert counts==dict(STL=1,**{'3MF':1,'AMF':1,'GLB':0})
  assert not any(x.get('phase')=='begin' and ('SetUserPreference' in x.get('call','') or x.get('call') in ('IModelDoc2.SaveAs','IModelDoc2.SaveAs2','IModelDoc2.SaveAs3','SldWorks.CommandInProgress.enter','SldWorks.CommandInProgress.restore')) for x in native)
  ht=[json.loads(x) for x in (root/'typed-glb/helper-native.jsonl').read_text().splitlines()]
  assert [x['phase'] for x in ht]==([] if mode=='identity' else ['begin','end']) and all(x['helper_pid']==helper['helper_pid'] for x in ht)
  trace=[json.loads(x) for x in (root/'trace.jsonl').read_text().splitlines()]
  for label in ('CloseDoc','ExitApp','WaitForOwnedProcess','CloseProcessHandle','CoUninitialize'):assert [x['phase'] for x in trace if x['call']==label]==['begin','end']
  for fmt in ('STL','3MF','AMF'):assert strict.export_file_valid(fmt,root/('component-export.'+fmt))
  audit=read(root/'typed-control-audit.json');assert audit['success'] is (mode=='identity')
  record=dict(original_directory=str(root),report_sha256=wanted,producer_success=True,fixture_success=False,identity_only=mode=='identity',source_sha256=source,
    pids=dict(SW=helper['before']['pid'],python=producer['python_worker_pid'],helper=helper['helper_pid'],launch=supervisor['worker_pid']),
    Python_modern_export_counts=counts,CSharp_save_attempts=helper['save_attempts'],before=helper['before'],after=helper['after'],
    identity_checks=helper['identity_checks'],source_reads=helper['source_reads'],native_arguments=helper['arguments'],
    api_saved=helper['api_saved'],save_errors=helper['save_errors'],save_warnings=helper['save_warnings'],helper_and_owned_cleanup=True,
    files={str(f.relative_to(root)):dict(bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(root.rglob('*')) if f.is_file()})
  if mode=='identity':assert helper['save_attempts']==0 and helper['api_saved'] is None and helper['after'] is None and not list(root.rglob('*.glb'))
  else:
   assert helper['save_attempts']==1 and helper['api_saved'] is True and helper['save_errors']==helper['save_warnings']==0 and helper['before']==helper['after'] and helper['post_state_accepted']
   assert helper['arguments']['name']==producer['output'] and helper['arguments']['version']==0 and helper['arguments']['options']==1
   path=root/'component-export.invalid-native.glb';data=path.read_bytes();baseline=BASE/'glb-host-control-70d8c9e-01/component-export.invalid-native.glb'
   assert sha(root/'component.SLDPRT')!=sha(baseline.parent/'component.SLDPRT')
   assert data==baseline.read_bytes() and sha(path)=='04b83d8e0a2ebccd297fc116d17964e183eb081717ef27e1049d6340abcda2ba'
   assert len(data)==3732 and struct.unpack_from('<I',data,12)[0]==3704 and struct.unpack_from('<I4s',data,3724)==(0,b'BIN\0')
   model=json.loads(data[20:3724]);assert model['buffers']==[{'byteLength':720}] and not strict.export_file_valid('GLB',path)
   manifests=list(root.rglob('manifest.json'));assert len(manifests)==1;manifest=read(manifests[0]);rows=manifest['phases']['after']['files'];assert len(rows)==1
   assert (manifests[0].parent/rows[0]['copy']).read_bytes()==data and rows[0]['sha256']==sha(path) and manifest['staging_path']==helper['arguments']['name']
   record['glb']=dict(bytes=len(data),JSON=3704,BIN=0,declared_buffer=720,sha256=sha(path),strict_valid=False,byte_identical_to_hidden_Python_baseline=True,
    native_input_bytes_are_not_historical_baseline=True,file_access_monitor=manifest['file_access_monitor'],module_snapshots='filtered lists only; not runtime dependency proof')
  result['attempts'][mode]=record
 result['conclusion']='Changing this part export binding to C# alone did not restore GLB; no underlying API/exporter/environment cause established, no retry authorized.'
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:dict(source=v['source_sha256'],CSharp_calls=v['CSharp_save_attempts']) for k,v in result['attempts'].items()}))
if __name__=='__main__':main()
