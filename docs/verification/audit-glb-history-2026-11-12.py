"""Offline original ZIP/receipt/GLB audit. No CAD, Blender, CI, network or repair."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from zipfile import ZipFile
sys.dont_write_bytecode = True
HISTORY = Path('/Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107/glb-history-offline')
SERIES = Path('/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110')
MODERN = Path('/Users/YJBeetle/.codex/task-artifacts/saveas3-modern/20261108-combined/run-42405530053')
PFX = 'swcli-native-smoke/hidden/runtime-sets/assemblies/modeling/'
RUNS = {
 '42173065847': ('254d1ad11847d002f0af07d630beba3350b7f66d','ef7dee25e3d995c5cc918d8a41d8d2cb4fc08a59f574fe6c941e12f8f4c323f4'),
 '42199134982': ('77be93d7d709cdc998f552ff715d75115f020114','bb200e9a0fd5e67381107c69fdc333aabe96086b9cd1898c5a9aa3dfcea060b5')}


def sha(data):
 return hashlib.sha256(data).hexdigest()


def load(path, name):
 spec = importlib.util.spec_from_file_location(name,path)
 module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
 return module


def inspect(data, strict, mesh):
 assert struct.unpack_from('<4sII',data)==(b'glTF',2,len(data))
 offset=12; chunks=[]; model=None
 while offset<len(data):
  length,kind=struct.unpack_from('<I4s',data,offset); offset+=8
  assert length%4==0 and offset+length<=len(data)
  chunks.append(dict(kind=kind.decode('ascii'),length=length))
  if kind==b'JSON': model=json.loads(data[offset:offset+length])
  offset+=length
 assert offset==len(data)
 with tempfile.TemporaryDirectory() as temp:
  path=Path(temp)/'unchanged.GLB'; path.write_bytes(data)
  valid=strict.export_file_valid('GLB',path)
  try: decoded=mesh.inspect_glb(path); error=None
  except (ValueError,RuntimeError) as exc: decoded=None; error=dict(type=type(exc).__name__,message=str(exc))
 return dict(sha256=sha(data),size_bytes=len(data),chunks=chunks,declared_buffers=model.get('buffers'),
             generator=model.get('asset',{}).get('generator'),current_strict_valid=valid,decoded_mesh=decoded,
             mesh_error=error),model


def summarize_event(index,event):
 r=event.get('result',{});d=r.get('document',{});a=r.get('artifact',{})
 return dict(index=index,action=r.get('action'),request_id=r.get('request_id'),document_id=d.get('document_id'),
             document_type=d.get('type'),path=d.get('path'),modified=d.get('modified'),read_only=r.get('read_only'),
             format=a.get('format'),ok=r.get('ok'),api_saved=r.get('api_saved'),save_errors=r.get('save_errors'),save_warnings=r.get('save_warnings'))


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--repo',type=Path,required=True)
 ap.add_argument('--output',type=Path,required=True)
 args=ap.parse_args();repo=args.repo.resolve()
 strict=load(repo/'src/swcli/hosts/export_validation.py','history_strict')
 mesh=load(repo/'scripts/ci/gate_support/glb_mesh.py','history_mesh')
 result=dict(schema='swcli.glb-history-offline.v1',user_report='Prior SWCLI GLB was imported and usable in Blender',
             blender_file_identity='unknown; user has not identified file/run; no mapping asserted',
             scope='existing local originals only; no CAD/Blender/VM/CI/network/repair',historical_runs=[],recent_failures=[])
 for run,(head,zipsha) in RUNS.items():
  archive=HISTORY/run/'original-native.zip'; assert sha(archive.read_bytes())==zipsha
  with ZipFile(archive) as z:
   report_bytes=z.read(PFX+'modeling.json'); report=json.loads(report_bytes)
   assert report_bytes==(HISTORY/run/'original-modeling.json').read_bytes()
   source={name:dict(sha256=sha(z.read(PFX+name)),size_bytes=len(z.read(PFX+name))) for name in ('component.SLDPRT','generated.SLDASM')}
   assert source['component.SLDPRT']['sha256']==report['generated_assembly']['component_sha256']
   assert source['generated.SLDASM']['sha256']==report['generated_assembly']['sha256']
   docsource=subprocess.check_output(['git','show',head+':src/swcli/hosts/windows_documents.py'],cwd=repo)
   validation=subprocess.check_output(['git','show',head+':src/swcli/hosts/export_validation.py'],cwd=repo)
   assert b'int(document.SaveAs3(str(export_path), 0, 1))' in docsource
   with tempfile.TemporaryDirectory() as temp:
    oldpath=Path(temp)/'old_validator.py';oldpath.write_bytes(validation);old=load(oldpath,'history_old_'+run)
    exports=[];models=[]
    for stem in ('component','assembly'):
     member=PFX+stem+'-export.GLB';data=z.read(member)
     assert data==(HISTORY/run/(stem+'-export.GLB')).read_bytes()
     summary,model=inspect(data,strict,mesh);models.append(model)
     path=Path(temp)/(stem+'.GLB');path.write_bytes(data)
     matching=[(i,e) for i,e in enumerate(report['events']) if e.get('result',{}).get('artifact',{}).get('format')=='GLB'
               and e['result']['artifact']['path'].endswith(stem+'-export.GLB')]
     assert len(matching)==1;i,event=matching[0];native=event['result'];document_id=native['document']['document_id']
     prior=[summarize_event(n,e) for n,e in enumerate(report['events'][:i]) if e.get('result',{}).get('document',{}).get('document_id')==document_id
            and e['result'].get('action') in ('document.open','document.create','document.save-as','document.save','document.close')]
     receipt=next(r for r in report['model_exports'] if r['artifact']['format']=='GLB' and r['artifact']['path'].endswith(stem+'-export.GLB'))
     assert receipt['sha256']==summary['sha256']
     summary.update(zip_member=member,crc32='%08x'%z.getinfo(member).CRC,zip_crc_verified=True,
                    document_type=native['document']['type'],receipt=summarize_event(i,event),
                    old_validator_accepts=old.export_file_valid('GLB',path),
                    document_lifecycle_before_export=prior,raw_native_save_return='not retained in export receipt',
                    source_bytes_unchanged_receipt=receipt['source_bytes_unchanged'],
                    source_state_unchanged_receipt=receipt['source_state_unchanged'])
     exports.append(summary)
   common={k:models[0].get(k)==models[1].get(k) for k in ('buffers','bufferViews','accessors','meshes')}
   result['historical_runs'].append(dict(run_id=run,head_from_existing_verification_document=head,archive=str(archive),archive_sha256=zipsha,
    report_sha256=sha(report_bytes),host=report['host'],source_models=source,
    source_head_provenance='existing verification docs; git blob read, not new CI query or new deployed-wheel proof',
    source_files_sha256={'windows_documents.py':sha(docsource),'export_validation.py':sha(validation)},
    API_source='IModelDoc2.SaveAs3(Name,0,1); return integer save-error, no null/Errors/Warnings arguments',
    API_parameter_evidence='inferred from recorded tested-head source, no raw native-call argument trace retained',
    visibility_evidence='startup cached false; export-time Visible and UserControl flags unknown',
    CIP_evidence='source owned scope inference only; no raw per-export boolean retained',
    generated_assembly=report['generated_assembly'],exports=exports,geometry_declarations_equal=common,
    python_cli=report['events'][0].get('command',[None])[0]))
 modernzip=MODERN/'original-native-artifact.zip'
 assert sha(modernzip.read_bytes())=='a55c00d7e4b7d07cbece2acd0ef5847138efc074f9ddaa3bfead0aef9e967ec9'
 with ZipFile(modernzip) as z:
  rb=z.read(PFX+'modeling.json');j=json.loads(rb);data=z.read(PFX+'component-export.invalid-native.glb')
  measured,_=inspect(data,strict,mesh)
  result['recent_failures'].append(dict(kind='modern CI 42405530053',archive=str(modernzip),archive_sha256=sha(modernzip.read_bytes()),report_sha256=sha(rb),
   host=j['host'],source_model_sha256=sha(z.read(PFX+'component.SLDPRT')),
   events=[summarize_event(i,e) for i,e in enumerate(j['events']) if e.get('result',{}).get('action') in ('document.open','document.save-as','document.export')],
   api='IModelDocExtension.SaveAs3(Name,0,1,null-dispatch,null-dispatch,byref-I4,byref-I4)',glb=measured,
   visibility='startup cached false; actual export-time unknown',CIP='entered/checked/restored sequence in old audited trace; raw bool not retained'))
 for name in ('glb-host-control-70d8c9e-01','glb-visible-startup-70d8c9e-01'):
  folder=SERIES/name;rb=(folder/'report.json').read_bytes();j=json.loads(rb);c=j['cases'][0]
  measured,_=inspect((folder/'component-export.invalid-native.glb').read_bytes(),strict,mesh)
  source_sha=sha((folder/'component.SLDPRT').read_bytes());assert source_sha==c['source_sha256']
  row=dict(kind=name,report_sha256=sha(rb),host=j['host'],source_model_sha256=source_sha,
           source_lifecycle='fresh saved writable part, no close/reopen before export; fixed driver source',
           api='modern Python extension SaveAs3(Name,0,1,null-dispatch,null-dispatch,byref-I4,byref-I4)',
           glb=measured,native_receipt=c['outputs'][-1]['result'],
           actual_host_before_fixture=j.get('actual_host_before_fixture'),export_controls=c.get('export_controls'),
           owned_cleanup_errors=j['cleanup_errors'])
  result['recent_failures'].append(row)
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(historical_runs=len(result['historical_runs']),recent_failures=len(result['recent_failures']),
                      valid_assembly_sha256=result['historical_runs'][0]['exports'][1]['sha256'],
                      valid_assembly_triangles=result['historical_runs'][0]['exports'][1]['decoded_mesh']['triangles'])))

if __name__=='__main__': main()
