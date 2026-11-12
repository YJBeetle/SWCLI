"""Offline audit of the single OS-only current-user transport attempt."""
import base64
import hashlib
import json
from pathlib import Path
import sys


def audit(root):
    load=lambda name:json.loads((root/name).read_text())
    manifest=load('artifact-sha256.json')
    for name,value in manifest['files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==value,name
    ctx=load('host-context.json');assert ctx['allocation_id']=='VM-20261113-OS-USER-CONTEXT-01'
    assert ctx['allocation_snapshot']['CAD_execution_authorized'] is False and ctx['CAD_execution_authorized'] is False
    assert ctx['query_attempts']==1 and ctx['VM_boots']==ctx['VM_restarts']==ctx['COM_or_CAD_calls']==ctx['Python_children_started_in_guest']==0
    assert ctx['resume_same_boot']==1 and ctx['VM_settings_changed'] is False
    argv=ctx['query_argv'];assert argv[:4]==['prlctl','exec','{da36dd51-bd6d-4e7a-995b-547464583302}','--current-user']
    assert argv[4]==r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    assert '--user' not in argv and '--password' not in argv
    source=(root/'query-current-user-context.ps1').read_bytes()
    assert hashlib.sha256(source).hexdigest()==ctx['query_source_sha256']
    assert base64.b64decode(argv[-1]).decode('utf-16le')==source.decode()
    assert not any(word in source.decode() for word in ('CommandLine','Get-CimInstance','Get-WmiObject','pythoncom','win32com','DispatchEx','Start-Process'))
    guest_commands=[r for r in ctx['commands'] if r['argv'][:2]==['prlctl','exec']]
    assert len(guest_commands)==1 and guest_commands[0]['argv']==argv and guest_commands[0]['exit']==255
    assert (root/'current-user-query.stdout').read_bytes()==b''
    error=(root/'current-user-query.stderr').read_text()
    assert error.startswith('PrlVmGuest_RunProgram: Unable to open new session in this virtual machine.')
    assert ctx['first_error']['type']=='RuntimeError' and 'exit 255' in ctx['first_error']['message']
    assert 'guest_output' not in ctx and 'CAD_busy' not in ctx and 'query_returned' not in ctx
    before=(root/'host-before-state.stdout').read_text();after=(root/'host-after-state.stdout').read_text()
    assert 'State: paused' in before and 'State: running' in after
    assert 'Pause idle: on' in before and 'Pause idle: on' in after
    assert [r['name'] for r in ctx['commands']]==['host-before-state','resume-same-boot-for-OS-read','current-user-query','host-after-state']
    return dict(schema='swcli.os-current-user-query-audit.v1',allocation_id=ctx['allocation_id'],query_attempts=1,
      query_timeout_seconds=30,query_exit=255,query_returned_metadata=False,guest_payload_execution_confirmed=False,
      first_transport_error=error.rstrip('\n'),stdout_bytes=0,explicit_current_user_in_submitted_host_argv=True,
      current_user_identity_switch_proven=False,guest_user=None,guest_user_SID=None,guest_session_id=None,CAD_busy=None,
      guest_process_command_lines_collected=False,credentials_collected=False,guest_Python_children_started=0,
      explicit_COM_or_CAD_calls=0,SW_started_by_payload=0,VM_boots=0,VM_restarts=0,resume_same_boot=1,
      VM_settings_changed=False,idle_pause_before_after='on',host_VM_state_before='paused',host_VM_state_after='running',
      subsequent_guest_queries=0,System_fallback_attempts=0,DispatchEx_retries=0,new_probe_authorized=False,
      allocation_return_requested=True,query_source_sha256=ctx['query_source_sha256'],
      host_receipt_sha256=hashlib.sha256((root/'host-context.json').read_bytes()).hexdigest(),
      raw_manifest_sha256=hashlib.sha256((root/'artifact-sha256.json').read_bytes()).hexdigest(),raw_manifest_entries=len(manifest['files']),
      audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      no_root_cause_inferred_from_generic_transport_suggestions=True)

if __name__=='__main__':print(json.dumps(audit(Path(sys.argv[1])),ensure_ascii=False,indent=2))
