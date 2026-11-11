"""Pinned original-run audit; stdlib and prior pure evidence validators only."""
import argparse
import base64
import hashlib
import importlib.util
import json
import ntpath
from pathlib import Path
import re
import zipfile

RUN=42928824277
HEAD='95a2edccd26dfa274e0f66468248838d71cf7e53'
NATIVE_ID=13816502372
NATIVE_SHA='90fb3eb856a671a1cc5c98f56e3fc219d76208203d35a7934e14428cdaa4681b'
INSTALL_ID=13816611572
INSTALL_SHA='76e85630997b8241e150d55ad7691803b800bc570fdac9e088b52c630e30643a'
LOG_SHA='8143e35f82298445213f362c7815632e16719e0d28935f4ec48d5dc1546f8bd3'
PREFIX='swcli-native-smoke/'
spec=importlib.util.spec_from_file_location('_pure_unit_original_checks',Path(__file__).with_name('audit-units-write-42414478796.py'))
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
require=checks.require

def audit(metadata,raw):
    run=json.loads((metadata/'run-terminal.json').read_bytes());jobs=json.loads((metadata/'jobs-terminal.json').read_bytes())['jobs'];artifacts=json.loads((metadata/'artifacts-terminal.json').read_bytes())['artifacts']
    require(run['id']==RUN and run['head_sha']==HEAD and run['event']=='workflow_dispatch' and run['head_branch']=='codex/docprops-units-expanded' and run['run_attempt']==1 and run['status']=='completed' and run['conclusion']=='failure','exact failed run/head')
    require(all(j['run_id']==RUN and j['head_sha']==HEAD for j in jobs),'job binding')
    success={'Windows / Python 3.9','Windows / Python 3.14','Build wheel','Validate manual units routing before private native setup'}
    require({j['name'] for j in jobs if j['conclusion']=='success'}==success,'all portable/package/route prerequisites pass')
    failed=[j for j in jobs if j['conclusion']=='failure'];require(len(failed)==1 and failed[0]['id']==130224083602 and [s['name'] for s in failed[0]['steps'] if s['conclusion']=='failure']==['Verify public document unit profile CLI'],'actual failed job/step')
    for aid,name,sha,size in [(NATIVE_ID,'original-native.zip',NATIVE_SHA,10937528),(INSTALL_ID,'original-install-logs.zip',INSTALL_SHA,3211059)]:
        a=next(a for a in artifacts if a['id']==aid);p=raw/name
        require(a['workflow_run']['id']==RUN and a['workflow_run']['head_sha']==HEAD and a['size_in_bytes']==p.stat().st_size==size and a['digest']=='sha256:'+sha and hashlib.sha256(p.read_bytes()).hexdigest()==sha,'official artifact identity/digest')
    require(hashlib.sha256((raw/'native.original.log').read_bytes()).hexdigest()==LOG_SHA,'original native job log')
    with zipfile.ZipFile(raw/'original-native.zip') as z:
        read=lambda n:json.loads(z.read(PREFIX+n))
        h=read('units-public-acceptance/host-report.json');internal=read('units-write-calibration/report.json')
        require(h['source_commit']==internal['source_commit']==HEAD and h['success'] is False and 0<h['duration_seconds']<1800,'source and failure budget')
        require(h['failure']==dict(type='RuntimeError',message='native full image differs from this CI installation'),'first exact-path failure')
        pre=h['identity_preflight'];response=read('units-public-acceptance/identity-preflight.stdout')
        require(pre['returncode']==0 and pre['response']==response and response['success'] is True and response['result']['host_connected'] is True and response['result']['recovery_required'] is False,'durable raw preflight response')
        require(pre['requested_cli_timeout_seconds']==600 and pre['effective_health_rpc_timeout_seconds']==10 and pre['effective_health_connect_timeout_seconds']==1 and pre['process_timeout_seconds']==600,'actual timeout layers')
        obs=h['identity_observations'];require(len(obs)==1 and obs[0]['role']=='native-host' and obs[0]['capture_status']['phase']=='persisting','pre-validation durable observation')
        obs=obs[0];q=obs['image_query'];identity=obs['observed_identity'];expected=r'C:\Program Files\SOLIDWORKS\SLDWORKS.exe';actual=r'C:\PROGRA~1\SOLIDW~1\SLDWORKS.exe'
        require(q['api']=='QueryFullProcessImageNameW' and q['flags']==0 and q['success'] is True and q['last_error'] is None and q['input_capacity_chars']==32768 and q['ctypes_bytes']==dict(HANDLE=8,DWORD=4,BOOL=4,wchar=2),'native real query ABI')
        require(identity['image']==q['image']==actual and obs['expected_image']==expected and q['image_repr']==repr(actual) and q['returned_chars']==q['image_length_py_chars']==q['image_length_utf16_units']==33 and q['nul_at_returned_index'] is True and q['byteorder']=='little','raw image/expected/length/NUL')
        require(base64.b64decode(q['buffer_prefix_b64'],validate=True)==actual.encode('utf-16-le')+b'\0\0','raw wchar bytes without truncation')
        require(obs['requested_pid']==identity['pid']==response['result']['host']['process_id']==9980 and obs['launch_timestamp']<=identity['creation_timestamp']<=obs['observed_timestamp'],'observed PID/creation values; creation predicate not reached')
        require(obs['comparison_inputs']==dict(actual_image_normalized=ntpath.normcase(ntpath.normpath(actual)),expected_image_normalized=ntpath.normcase(ntpath.normpath(expected))) and ntpath.normcase(ntpath.normpath(actual))!=ntpath.normcase(ntpath.normpath(expected)),'actual exact path rejection')
        failure=h['identity_capture_failure'];require(failure['role']=='native-host' and failure['message']==h['failure']['message'] and failure['observation']['image_query']==q and failure['observation_error'] is None and failure['handle_close_error'] is None,'first identity failure details')
        require('public_command' not in h and not any(n.startswith(PREFIX+'units-public-acceptance/cli/') or n.endswith('/public.stdout') or n.endswith('/public.stderr') for n in z.namelist()),'no public worker/CLI/SDK/MCP/cold probes started')
        traces=[]
        for line in z.read(PREFIX+'units-public-acceptance/daemon.stderr').decode().splitlines():
            if line.startswith('{'):
                try:t=json.loads(line)
                except ValueError:continue
                if t.get('event')=='swcli.native-call':traces.append(t)
        require(traces==[],'no public CAD operation trace/setter')
        stop=read('units-public-acceptance/stop.stdout');require(h['stop_exit_code']==0 and stop['success'] is True and stop['result']['stopping'] is True,'single normal shutdown receipt success')
        require(not h.get('forced_native_termination_attempted') and not h.get('owned_native_exit_confirmed') and 'pids_after' not in h and 'owned_native_identity' not in h and [x['message'] for x in h['cleanup_errors']]==['no native handle retained before public exit; do not reopen PID','owned native process handle unavailable'],'no verified native exit; do not reopen/kill/claim cleanup pass')
        require(internal['success'] is True and internal['cleanup_errors']==[] and internal['owned_native_exit_confirmed'] is True and internal['pids_before']==internal['pids_after']==[] and [len(c['write_steps']) for c in internal['cases']]==[46,46,47],'separate private 139 lifecycle')
        files=geometry=nonexact=0
        for case in internal['cases']:
            require(case['success'] is True,'private case')
            for step in case['write_steps']:
                require(step['success'] is True and step['result']['native_return_value'] is True and checks.fingerprint(step['before'])==step['before_fingerprint'] and checks.fingerprint(step['after'])==step['after_fingerprint'] and checks.typed(step['after'])==checks.typed(step['readonly_profile']),'internal full after/readonly profile')
                for kind in ('source','target'):
                    require(hashlib.sha256(z.read(PREFIX+'units-write-calibration/'+step[kind+'_file'].replace('\\','/'))).hexdigest()==step[kind+'_sha256'],'internal native source/target hash');files+=1
                if case['document_type']==1:
                    for label,comparison in [('geometry_after_write','comparison_geometry_after_write'),('geometry_readonly','comparison_geometry_readonly')]:
                        checks.geometry(case['geometry_before'],step[label],step[comparison]);geometry+=1;nonexact+=not step[comparison]['exact_equal']
        summary=json.loads(z.read('swcli-test-summary/summary.json'));require(summary['source']['commit']==HEAD and next(p for p in summary['phases'] if p['name']=='public-evidence')['status']=='SKIP','summary no public receipts')
    with zipfile.ZipFile(raw/'original-install-logs.zip') as z:msi=z.read('solidworks-msi.log')
    require(hashlib.sha256(msi).hexdigest()=='418bed1f830a46b42cc53a587ce668b769a4f62f8327c27ce067dd848789bc26','MSI receipt hash')
    text=msi.decode('utf-16' if msi.startswith(b'\xff\xfe') else 'utf-8');install_dir=re.search(r'^Property\(S\): INSTALLDIR = (.+)$',text,re.M).group(1).strip()
    require(ntpath.normcase(ntpath.normpath(ntpath.join(install_dir,'SLDWORKS.exe')))==ntpath.normcase(ntpath.normpath(expected)),'MSI long path matches expected')
    return dict(audit_success=True,run_id=RUN,head_sha=HEAD,first_failure=h['failure'],first_boundary='synchronous native-host identity admission before public worker',duration_seconds=h['duration_seconds'],actual_image=actual,expected_image=expected,query_raw_complete=True,query=q,observed_identity=identity,creation_observed_within_window=True,creation_predicate_executed=False,short_form_path_observed=True,short_and_long_same_file_proven=False,public=dict(worker_started=False,completed_cases=dict(cli=0,sdk=0,mcp=0),cold_probes_completed=0,native_trace_events=0,native_setters=0),cleanup=dict(stop_exit_code=0,stop_receipt_success=True,daemon_wait_zero_inferred_from_postwait_error=True,native_exit_confirmed=False,helper_started=False,pids_after=None,unknown_native_termination_attempted=False,errors=h['cleanup_errors']),internal=dict(success=True,steps=139,duration_seconds=internal['duration_seconds'],native_files_checked=files,part_geometry_comparisons=geometry,part_geometry_nonexact=nonexact,owned_exit_confirmed=True),artifacts=dict(native_id=NATIVE_ID,native_zip_sha256=NATIVE_SHA,install_id=INSTALL_ID,install_zip_sha256=INSTALL_SHA,original_native_job_log_sha256=LOG_SHA),installer_expected_long_path_agree=True,public_native_accepted=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metadata-dir',type=Path,required=True);p.add_argument('--raw-dir',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();value=json.dumps(audit(a.metadata_dir,a.raw_dir),ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(value)
    else:print(value,end='')
if __name__=='__main__':main()
