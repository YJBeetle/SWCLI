"""Offline-only audit of the one reviewed Windows file observation. No VM/API invocation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def field_changes(first,second,prefix=''):
    out={}
    for key in sorted(set(first)|set(second)):
        name=prefix+'.'+key if prefix else key
        if isinstance(first.get(key),dict) and isinstance(second.get(key),dict):out.update(field_changes(first[key],second[key],name))
        elif first.get(key)!=second.get(key):out[name]=dict(before=first.get(key),after=second.get(key))
    return out


def audit(root):
    def read(name):return json.loads((root/name).read_text(encoding='utf-8-sig'))
    def sha(name):return hashlib.sha256((root/name).read_bytes()).hexdigest()
    approved=read('allocation.json');launch=read('launcher-context.json');data=read('metadata.json')
    expected='80bfa9d4bc453277dc0ba4dd9dbdf8f0d315a090aa3bab429843b1f9bc308530'
    script_sha='ef1fc427b36f8fcbd05972515db8580cc1c50e8447e444941c6fd1fda86e07c5'
    assert approved['allocation_id']=='VM-20261112-MARKINGJIG-OS-FORENSICS-01'
    assert approved['source_head']=='2a0d52a25d52072f56d4a78503d489e431db5c8a'
    assert sha('file_forensics.py')==approved['script_sha256']==script_sha
    assert launch['tool_attempts']==1 and launch['tool_exit']==1 and launch['tool_pid']>0
    assert launch['first_error'] is None and launch['cleanup_errors']==[] and not launch.get('tool_timeout',False)
    assert launch['tool_sha256_before']==launch['tool_sha256_after']==script_sha
    assert launch['target_sha256_before']==launch['target_sha256_after']==data['hash']['sha256']==expected
    assert data['hash']['bytes_read']==924679 and sha('metadata.json')==launch['output_sha256']
    assert launch['occupancy']['exclusive_read_open_succeeded'] is True and launch['occupancy']['own_handle_closed'] is True
    assert launch['occupancy']['access']=='GENERIC_READ' and launch['occupancy']['share']==0
    assert launch['SW_processes_before']==launch['SW_processes_after']==[]
    assert launch['COM_CAD_calls']==0 and launch['idle_configuration_modified'] is False
    assert data['complete'] is False and data['first_error']['message']=='source metadata changed; not inferred to be a content write'
    assert data['cleanup_errors']==[] and data['application_or_CAD_calls']==data['explicit_source_write_calls']==0
    assert data['admission_or_CAS_replacement'] is False and data['implicit_OS_access_time_updates_not_suppressed'] is True
    assert len(data['snapshots'])==2
    first,last=data['snapshots'];channels=('python_path','python_held','win32_held','win32_path_reopen')
    changed={key:field_changes(first[key],last[key]) for key in channels}
    for channel in ('python_path','python_held'):
        assert set(changed[channel])=={'st_atime_ns'}
        assert first[channel]['st_ctime_ns']==last[channel]['st_ctime_ns']
        assert first[channel]['st_file_attributes']==last[channel]['st_file_attributes']==33
    identity=first['win32_held']['id_before']
    assert identity==dict(VolumeSerialNumber=4217245827768940497,FileId128_bytes_hex='6057020000000a000000000000000000')
    for row in (first,last):
        assert row['physical_identity_proven'] is True
        assert set(row['raw_python_cross_channel_differences'])=={'st_ctime_ns'}
        assert row['python_path']['st_ctime_ns']==row['python_path']['st_birthtime_ns']
        for channel in ('win32_held','win32_path_reopen'):
            native=row[channel];assert native['id_before']==native['id_after']==identity
            assert native['standard']==dict(AllocationSize=925696,EndOfFile=924679,NumberOfLinks=1,DeletePending=0,Directory=0)
            assert native['basic']['FileAttributes']==33
    for channel in ('win32_held','win32_path_reopen'):
        assert set(changed[channel])=={'basic.LastAccessTime'}
    assert data['same_channel_changes']=={key:dict(before=first[key],after=last[key]) for key in channels}
    timeline=data['timeline'];assert len(timeline)==47
    assert [row['sequence'] for row in timeline]==list(range(47))
    assert all(row['phase']=='end' and row['end_monotonic_ns']>=row['monotonic_ns'] for row in timeline)
    counts=Counter(row['operation'] for row in timeline)
    assert counts['close-held']==counts['before-read:close-reopened']==counts['after-read:close-reopened']==1
    close=[row for row in timeline if 'close-' in row['operation']]
    host=read('host-after-state.json');assert host['idle_config_commands_issued']==host['VM_CAD_commands_issued']==0
    assert host['list_exit']==0 and any('Pause idle: on' in row for row in host['selected'])
    transport=read('prlctl-launch-exit.json');assert transport['exit_code']==255
    assert 'PrlJob_GetResult: Invalid argument' in ((root/'prlctl-launch.stdout').read_text()+(root/'prlctl-launch.stderr').read_text())
    checks=[json.loads(line) for line in (root/'post-transport-OS-check.stdout').read_text(encoding='utf-8-sig').splitlines() if line.startswith('{')]
    assert checks[0]['workExists'] is False and checks[0]['pythonProcesses']==[]
    return dict(schema='swcli.markingjig-os-file-forensics-native-audit.v1',allocation_id=approved['allocation_id'],source_head=approved['source_head'],source_sha256=script_sha,evidence_audit_passed=True,
        actual_tool_attempts=1,tool_pid=launch['tool_pid'],tool_exit=1,tool_stable_window_passed=False,
        primary_failure=data['first_error'],collected_identity_proven_rounds=2,all_recorded_file_API_operations_returned_normally=True,
        only_same_channel_changes=changed,raw_time_units=data['raw_time_units'],
        unchanged=dict(content_sha256=expected,bytes_read=924679,file_identity=identity,Win32_creation_write_change_times={name:first['win32_held']['basic'][name] for name in ('CreationTime','LastWriteTime','ChangeTime')},
                       Python_path_ctime_ns=first['python_path']['st_ctime_ns'],Python_held_ctime_ns=first['python_held']['st_ctime_ns'],attributes=33),
        own_handle_close_events=close,own_cleanup_errors=[],source_code_and_input_hashes_before_after_equal=True,output_sha256=sha('metadata.json'),
        SW_before=[],SW_after=[],COM_CAD_open_export_save_calls=0,idle_configuration_modified=False,host_after_state=host,
        transport_failure=dict(exit_code=255,message='PrlJob_GetResult: Invalid argument',tool_not_started_verified_by_missing_required_workdir_and_no_python=True,
                               corrected_entry_only='encoded PowerShell H-drive launcher; same reviewed tool source/arguments',no_tool_retry=True),
        limits=['Same-window changes are only access times; trigger/caller is not independently traced.','No timestamp tolerance, epoch conversion or field replacement; raw Windows/Python fields retained.',
                'This new zero-CAD window does not reconstruct historical OpenDoc7 ChangeTime change or imply a content write/no intervening write.',
                'Source/mode/CAS/readonly/identity guards unchanged; no new CAD acceptance or automatic next phase.'],
        evidence_directory=str(root),raw_sha256={name:sha(name) for name in ('allocation.json','file_forensics.py','metadata.json','launcher-context.json','prlctl-launch.stdout','prlctl-launch.stderr','prlctl-launch-exit.json','post-transport-OS-check.stdout','post-transport-OS-check.stderr','powershell-launch.stdout','powershell-launch.stderr','powershell-launch-exit.json','host-after-state.json')})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);args=p.parse_args()
    print(json.dumps(audit(args.evidence),indent=2,ensure_ascii=False))
