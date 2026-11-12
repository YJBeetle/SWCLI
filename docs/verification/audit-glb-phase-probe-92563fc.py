"""Offline replay of one failed acquisition, not a native phase/export acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile

HEAD='92563fcf2a887a984d6d309812b2169313ec8fec'
INVENTORY_SHA='d7db20f8041424115a97b91376001be759b32fad6e5faa2cc405fe971a13185d'
PY_FIELDS=('st_dev','st_ino','st_mode','st_size','st_atime_ns','st_mtime_ns','st_ctime_ns','st_birthtime_ns','st_file_attributes','st_reparse_tag','st_nlink')


def sha(data):return hashlib.sha256(data).hexdigest()
def load(root,name):return json.loads((root/name).read_text(encoding='utf-8-sig'))
def projection(row):
    result=copy.deepcopy(row)
    for channel in ('python_path','python_held'):result[channel].pop('st_atime_ns')
    for channel in ('win32_held','win32_path_reopen'):result[channel]['basic'].pop('LastAccessTime')
    result['raw_python_cross_channel_differences'].pop('st_atime_ns',None)
    return result

def delta(a,b,path=()):
    if type(a) is not type(b):return [dict(path=list(path),before=a,after=b)]
    if isinstance(a,dict):
        if a.keys()!=b.keys():return [dict(path=list(path),before=a,after=b)]
        return [r for key in a for r in delta(a[key],b[key],path+(key,))]
    if isinstance(a,list):
        if len(a)!=len(b):return [dict(path=list(path),before=a,after=b)]
        return [r for i,(x,y) in enumerate(zip(a,b)) for r in delta(x,y,path+(i,))]
    return [] if a==b else [dict(path=list(path),before=a,after=b)]

def metadata(frame,projected=False):
    raw={name:[projection(r) for r in rows] for name,rows in frame['raw'].items()} if projected else frame['raw']
    return dict(stable=frame['stable'],raw=raw)

def validate_frame(frame,inv):
    assert frame['complete'] is True and frame['access_time_policy']=='record-only'
    assert set(frame['stable'])==set(frame['raw'])==set(frame['captures'])==set(inv['files'])
    ids={}
    for name,pinned in inv['files'].items():
        stable=frame['stable'][name];capture=frame['captures'][name]
        assert stable['sha256']==pinned['sha256'] and stable['size_bytes']==pinned['size_bytes']
        assert capture['complete'] and capture['access_time_policy']=='record-only' and capture['first_error'] is None and capture['cleanup_errors']==[]
        assert capture['hash']==dict(sha256=pinned['sha256'],bytes_read=pinned['size_bytes'])
        assert capture['snapshots']==frame['raw'][name] and len(capture['snapshots'])==2
        assert not capture['stability_same_channel_changes']
        before,after=capture['snapshots']
        assert projection(before)|{'label':'same'}==projection(after)|{'label':'same'}
        for row in capture['snapshots']:
            path,held=row['python_path'],row['python_held']
            assert row['physical_identity_proven'] is True
            for value in (path,held):
                assert all(type(value[k]) is int for k in PY_FIELDS)
                assert stat.S_ISREG(value['st_mode']) and value['st_file_attributes']&1 and not value['st_file_attributes']&0x400
                assert value['st_reparse_tag']==0 and value['st_nlink']==1 and value['st_dev']>0 and value['st_ino']>0
                assert value['st_size']==pinned['size_bytes']
            assert all(path[k]==held[k] for k in PY_FIELDS if k not in ('st_ctime_ns','st_atime_ns'))
            assert row['raw_python_cross_channel_differences']=={k:dict(path=path[k],held=held[k]) for k in PY_FIELDS if path[k]!=held[k]}
            first=row['win32_held']['id_before']
            assert len(first['FileId128_bytes_hex'])==32 and int(first['FileId128_bytes_hex'],16)>0
            assert first['VolumeSerialNumber']==held['st_dev']
            assert int.from_bytes(bytes.fromhex(first['FileId128_bytes_hex']),'little')==held['st_ino']
            for channel in ('win32_held','win32_path_reopen'):
                native=row[channel];basic=native['basic'];standard=native['standard']
                assert native['id_before']==native['id_after']==first
                assert standard['EndOfFile']==pinned['size_bytes'] and standard['NumberOfLinks']==1
                assert standard['DeletePending']==standard['Directory']==0
                assert basic['FileAttributes']==held['st_file_attributes']
            left=copy.deepcopy(row['win32_held']);right=copy.deepcopy(row['win32_path_reopen'])
            left['basic'].pop('LastAccessTime');right['basic'].pop('LastAccessTime');assert left==right
            for raw_channel,stable_channel in (('python_path','path_before'),('python_held','handle_before')):
                assert all(row[raw_channel][k]==v for k,v in stable[stable_channel].items())
            if name in ids:assert ids[name]==first
            ids[name]=first
    return ids

def audit(root):
    manifest=load(root,'artifact-sha256.json')
    for name,expected in manifest['files'].items():assert sha((root/name).read_bytes())==expected,name
    cfg=load(root,'allocation-inputs.json');guest=load(root,'launcher-context.json');host=load(root,'host-run-context.json')
    report=load(root,'native-output/report.json');supervisor=load(root,'native-output/markingjig-supervisor.json')
    assert cfg['source_head']==guest['source_head']==host['source_head']==HEAD
    assert cfg['product_source_head']=='70d8c9ecf3c02b099ca9c2cc64fe1880061cea44'
    assert (cfg['native_timeout_seconds'],cfg['group_timeout_seconds'])==(600,1800)
    package=root/'markingjig-code-92563fc.zip';assert sha(package.read_bytes())==cfg['package_sha256']
    with zipfile.ZipFile(package) as z:
        assert set(z.namelist())==set(cfg['code_files_sha256'])
        for name,value in cfg['code_files_sha256'].items():assert sha(z.read(name))==value
        data=z.read('docs/evidence/glb-markingjig-input-inventory-2026-11-12.json');assert sha(data)==INVENTORY_SHA
        inv=json.loads(data)
    assert guest['copied_code_sha256']==cfg['code_files_sha256']
    assert 'code_hashes_after' not in guest  # Original secondary exception skipped this step; do not infer proof.
    protected=dict(inv['files'],protected_existing_GLB=inv['protected_existing_glb'])
    before=load(root,'mac-originals-before.json');after=load(root,'mac-originals-after.json')
    assert before['complete'] and after['complete'] and before['files']==after['files']==protected and len(protected)==11
    assert host['Mac_originals_before_complete'] and host['Mac_originals_after_complete'] and host['cleanup_errors']==[]
    assert guest['candidate_launch_attempts']==host['candidate_launch_attempts']==host['launcher_transport_attempts']==1
    assert guest['candidate_exit']==host['candidate_exit']==supervisor['worker_exit']==1
    assert guest['native_pids_before']==guest['native_pids_immediately_before_probe']==guest['native_pids_after']==guest['native_pids_after_postcleanup_OS']==[]
    assert supervisor['native_pids_before']==supervisor['native_pids_after']==[] and supervisor['failure'] is None
    assert guest['mode']=='probe' and guest['phase_policy']=='opening-transition-probe' and guest['access_time_policy']=='record-only'
    assert len(guest['copies'])==10 and {r['name'] for r in guest['copies']}==set(inv['files'])
    initial=guest['private_source_pre_CAD_frame'];post=guest['private_source_after_owned_cleanup_frame']
    ids_before=validate_frame(initial,inv);ids_after=validate_frame(post,inv);assert ids_before==ids_after
    assert guest['private_source_before']==initial['stable']
    for item in guest['copies']:
        pinned=inv['files'][item['name']]
        assert item['sha256']==pinned['sha256'] and item['size_bytes']==pinned['size_bytes'] and item['readonly'] and item['nlink']==1
    raw_delta=delta(metadata(initial),metadata(post));strict_delta=delta(metadata(initial,True),metadata(post,True))
    assert strict_delta==[], 'non-access private metadata changed across full attempt'
    trace=[json.loads(x) for x in (root/'native-output/trace.jsonl').read_text().splitlines()]
    calls=[r['call'] for r in trace if r['phase']=='begin']
    assert calls==['read-official-swconst','acquire-owned-host','CoUninitialize']
    assert sum(r['call']=='acquire-owned-host' and r['phase']=='error' for r in trace)==1
    assert any(r['call']=='CoUninitialize' and r['phase']=='end' for r in trace)
    assert report['success'] is False and report['cases']==[] and report['cleanup_errors']==[] and 'host' not in report
    assert report['failure']['type']=='com_error' and "-2146959355" in report['failure']['message']
    assert supervisor['success'] is False and supervisor['audit_error']==dict(type='IndexError',message='list index out of range')
    assert len(guest['cleanup_errors'])==1 and guest['cleanup_errors'][0]['stage']=='OS-post-owned-cleanup-input-proof'
    assert guest['cleanup_errors'][0]['error']=='list index out of range'
    assert host['idle_pause_restored'] is True and 'Pause idle: on' in (root/'host-after-state.stdout').read_text()
    progress=load(root,'progress-01-distilled.json')
    assert progress['native']==[dict(Id=4860,SessionId=0)]
    constants_begin=next(x['time'] for x in trace if x['call']=='acquire-owned-host' and x['phase']=='begin')
    after_error=next(x['time'] for x in trace if x['call']=='CoUninitialize' and x['phase']=='begin')
    return dict(schema='swcli.markingjig-phase-probe-native-audit.v1',audit_source_sha256=sha(Path(__file__).read_bytes()),source_head=HEAD,allocation_id=cfg['allocation_id'],
      original_report_sha256=sha((root/'native-output/report.json').read_bytes()),original_report_failure=report['failure'],
      candidate_attempts=1,worker_normal_exit=True,worker_exit=1,watchdog_failure=None,
      failure_stage='acquire-owned-host / DispatchEx',fatal_hresult_signed=-2146959355,fatal_hresult_hex='0x80080005',
      expected_unavailable_ROT_context_hresult=-2147221021,acquisition_window_seconds=after_error-constants_begin,
      first_fatal_error_not_replaced=True,case_runner_entered=False,OpenDoc7_calls=0,SaveAs_calls=0,exports=0,
      complete_model_observations=0,opening_phase_frames=0,loaded_baseline_sealed=False,phase_policy_native_acceptance=False,
      startup_process_observed=progress['native'],owned_COM_handle_acquired=False,owned_process_exit_code_receipt=False,
      CloseDoc_calls=0,ExitApp_calls=0,owned_wait_receipt=False,CoUninitialize_completed=True,
      native_pids_before=[],native_pids_after=[],native_pids_after_postcleanup_OS=[],
      normal_SW_exit_proven=False,Mac_originals_11_full_fingerprints_and_sha_unchanged=True,
      private_10_full_sha_and_native_128bit_ID_unchanged=True,private_post_exit_raw_frame_complete=True,
      copied_code_prelaunch_hashes_verified=True,copied_code_post_exit_hashes_available=False,
      raw_post_frame_label_is_not_CloseDoc_or_ExitApp_call_evidence=True,
      private_window_raw_changes=raw_delta,private_window_policy_projected_changes=strict_delta,
      post_exit_proof_replayed_offline=True,original_launcher_postcheck_failure_retained=guest['cleanup_errors'],
      original_supervisor_audit_failure_retained=supervisor['audit_error'],
      offline_replay_does_not_rewrite_or_upgrade_native_result=True,
      raw_access_time_policy='record-only',idle_pause_restored='on',host_after_state='running' if 'State: running' in (root/'host-after-state.stdout').read_text() else 'see original state',
      resource_return_requested=True,native_success=False,export_acceptance=False,
      evidence_manifest_sha256=sha((root/'artifact-sha256.json').read_bytes()),evidence_manifest_entries=len(manifest['files']))

if __name__=='__main__':
    print(json.dumps(audit(Path(sys.argv[1])),ensure_ascii=False,indent=2,allow_nan=False))
