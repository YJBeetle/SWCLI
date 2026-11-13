"""Offline audit of static containers; never launches Docker, Wine, or CAD."""
import hashlib
import json
from pathlib import Path
import sys

EXPECTED={
 'latest-zh-cn-cli':('7823979a9862730bdc765113b1e751d366d9557787cd2bbdb350f22f608db926','0.1.0a2'),
 '2025-zh-cn-cli':('377e9edd59f86333740cc1e3b049d546997b826907b5ce9851b571ebc205ecab','0.1.0a13')}
SW_SHA='911309f7494e806f22914bab40aa65531c01b45888ec482ac555fbd8b4f0a18b'

def audit(root):
 manifest=json.loads((root/'artifact-sha256.json').read_text())
 for name,value in manifest['files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==value,name
 rows=[json.loads(line) for line in (root/'remote-static.stdout').read_text().splitlines()]
 state=next(x for x in rows if x['kind']=='runtime-and-cache')
 finished=next(x for x in rows if x['kind']=='static-window-finished')
 assert state['version']['Version']=='5.4.2' and state['host']['arch']=='amd64' and state['host']['os']=='linux'
 assert state['rootless'] is False
 before_ids={x.split('\t')[0] for x in state['existing_containers_before']}
 after_ids={x.split('\t')[0] for x in finished['existing_containers_after']}
 assert before_ids==after_ids and len(before_ids)==11 and finished['original_container_IDs_present']
 assert finished['Wine_COM_CAD_calls']==finished['pulls']==finished['business_inputs_copied']==0
 image_rows={x['requested_tag']:x for x in state['images']};summary={};names=[]
 for result in (x for x in rows if x['kind']=='own-static-container-result'):
  tag=result['tag_context'];pinned,version=EXPECTED[tag];image=image_rows[tag]
  assert (image.get('Id') or image.get('ID'))==result['image_id']==pinned
  assert image['ManifestType']=='application/vnd.oci.image.manifest.v1+json'
  assert image['RootFS']['Layers'] and image['declared_volume_paths']==[]
  assert result['exit']==0 and result['removed_confirmed'] and result['exists_exit']==1
  start=next(x for x in rows if x['kind']=='own-static-container-start' and x['name']==result['name']);args=start['argv'];names.append(result['name'])
  for flag in ('--read-only','--pull=never','--network=none','--cap-drop=all','--security-opt=no-new-privileges','--image-volume=ignore'):assert flag in args
  assert args[args.index('--entrypoint')+1]=='/usr/bin/python3' and args[-3:]==['-I','-B','-']
  assert pinned in args and '--privileged' not in args and not any(a.startswith(('--volume','--mount','--pid=host')) for a in args)
  data=result['metadata'];complete=next(x for x in data if x.get('kind')=='metadata-collection-complete')
  assert complete['root_filesystem_readonly'] and int(complete['effective_capability_mask'],16)==0 and not complete['business_inputs_mounted']
  packages=next(x for x in data if 'wine_deb_package_version_rows' in x)
  assert packages['query_exit']==0 and all(line.endswith('\t11.16~jammy-1') for line in packages['wine_deb_package_version_rows'])
  runtime=next(x['runtime_version_file'] for x in data if 'runtime_version_file' in x)
  assert runtime['selected_version_fields']['WINE_VERSION']=='11.16'
  sw=next(x['installed_PE'] for x in data if x.get('installed_PE',{}).get('path','').endswith('Program Files/SOLIDWORKS/SLDWORKS.exe'))
  assert sw['sha256']==SW_SHA and sw['size_bytes']==712576 and sw['fixed_version_records'][0]['file_version']==[33,5,0,53]
  winpython=next(x['installed_PE'] for x in data if x.get('installed_PE',{}).get('path','').endswith('Python311/python.exe'))
  assert winpython['fixed_version_records'][0]['file_version'][:2]==[3,11]
  module=next(x['swcli_source_metadata'] for x in data if x.get('swcli_source_metadata',{}).get('path')=='/opt/swcli/src/swcli/__init__.py')
  assert module['version_literals']==[version]
  exporter=next(x['export_API_source'] for x in data if 'export_API_source' in x)
  assert any('document.SaveAs3(str(export_path), 0, 1)' in r['text'] for r in exporter['save_API_source_lines'])
  summary[tag]=dict(image_id=pinned,local_OCI_manifest_digest=image['Digest'],local_repo_digest_associations=image['RepoDigests'],rootfs_diff_ids=image['RootFS']['Layers'],manifest_type=image['ManifestType'],image_created=image['Created'],bundled_swcli_source_version=version,swcli_module_sha256=module['sha256'],wine_package_version='11.16~jammy-1',wine_version_file=runtime['selected_version_fields'],SW_static_PE_version=[33,5,0,53],SW_exe_sha256=SW_SHA,WinPython_static_PE_version=winpython['fixed_version_records'][0]['file_version'],WinPython_exe_sha256=winpython['sha256'],export_API_source=exporter,default_entrypoint=image['entrypoint'],owned_metadata_container=result['name'],removed=True)
 source_rows=[json.loads(line) for line in (root/'remote-source.stdout').read_text().splitlines()]
 src=next(x for x in source_rows if x['kind']=='source-container-result');assert src['image_id']==EXPECTED['latest-zh-cn-cli'][0] and src['exit']==0 and src['removed_confirmed']
 names.append(src['name']);assert len(set(names))==3 and not set(names)&before_ids
 entry=next(x for x in source_rows if x['kind']=='source-container-start');assert entry['argv'][entry['argv'].index('--entrypoint')+1]=='/usr/bin/python3'
 for flag in ('--read-only','--pull=never','--network=none','--cap-drop=all','--security-opt=no-new-privileges','--image-volume=ignore'):assert flag in entry['argv']
 aliases={x['alias_source']['path']:x['alias_source'] for x in src['metadata'] if 'alias_source' in x}
 assert aliases['/usr/local/bin/sw-cli']['present'] and not aliases['/usr/local/bin/swcli']['present']
 hosts={x['host_source']['path']:x['host_source'] for x in src['metadata'] if 'host_source' in x}
 acquire=next(x for x in hosts['/opt/swcli/src/swcli/daemon/server.py']['selected_functions'] if x['name']=='acquire_resident_app')
 assert 'attach_existing: bool = False' in acquire['source'] and 'raise ExistingHostRequiresAttach' in acquire['source'] and 'DispatchEx' in acquire['source']
 receipt=json.loads((root/'host-receipt.json').read_text());assert receipt['remote_exit']==0 and receipt['COM_Wine_CAD_calls']==0 and receipt['pulls']==0 and receipt['business_inputs_copied']==0
 ci=json.loads((root/'push-CI-single-snapshot.stdout').read_text());assert len(ci)==1 and ci[0]['headSha']=='7d6858e65d089ec4f49f2fd9cbcdfd9258c05270' and ci[0]['event']=='push'
 assert receipt['CI_snapshot']['polls']==1 and receipt['CI_snapshot']['manual_dispatches']==0
 push=json.loads((root/'push-backup.json').read_text());assert push['after']==ci[0]['headSha'] and push['force'] is False and push['main_pushed'] is False
 return dict(schema='swcli.glb-docker-readonly-preparation.v1',metadata_kind='installed-file/package/source evidence; no Wine/COM runtime version claim',
  runtime=dict(alias='workspaceroot',engine='Podman',version='5.4.2',platform='linux/amd64',rootless=False),
  images=summary,cached_alias='/usr/local/bin/sw-cli',cached_current_name_swcli_present=False,
  cached_acquire_source=acquire,cached_host_source_sha256={k:v.get('sha256') for k,v in hosts.items()},
  local_client=dict(docker_cli_available=False,podman_connection_available=False,local_VM_not_started=True),
  owned_static_containers=names,all_three_owned_containers_removed=True,original_container_IDs_preserved=len(before_ids),
  Wine_invocations=0,COM_calls=0,CAD_OpenDoc_SaveAs_calls=0,Windows_VM_calls=0,business_files_copied=0,registry_pulls=0,
  readonly_probe_execution_ready=False,blocking_host_contracts=['Wine CPython3.11 vs existing strict CPython3.14.7 backend','raw birthtime and full128bit file identity semantics','Wine Windows PID and private Linux process ownership mapping','private prefix/display/license bootstrap without default daemon warmup'],
  future_probe_mode_only=True,future_export_attempts=0,future_model_graph_state_geometry_and_file_guards_not_relaxed=True,
  current_cache_not_historical_MarkingJig_job_provenance=True,
  pushed_backup=push,automatic_CI_single_snapshot=ci,CI_terminal_not_polled=True,
  raw_manifest_sha256=hashlib.sha256((root/'artifact-sha256.json').read_bytes()).hexdigest(),raw_manifest_entries=len(manifest['files']),
  audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

if __name__=='__main__':print(json.dumps(audit(Path(sys.argv[1])),ensure_ascii=False,indent=2))
