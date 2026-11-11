"""Audit only this original ZIP/head; stdlib, no product/gate/COM imports."""
import argparse
import base64
import hashlib
import importlib.util
import json
import re
import ntpath
from pathlib import Path
import zipfile

RUN=42865595677
HEAD='085ae73570f023706319738d1130fd21256e4144'
ARTIFACT=13790060166
DIGEST='207a75330e6bb35b368f2d5ba054ec908bfa661205e068c3c8f275a32d246c75'
LOG_SHA='38c14c1bdb3cc942bbf702b71231bb205afc0833816be7d3e9d9a02ae2d101be'
PREFIX='swcli-native-smoke/'
spec=importlib.util.spec_from_file_location('_image_failure_pure_checks',Path(__file__).with_name('audit-units-write-42414478796.py'))
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
require=checks.require;typed=checks.typed


def audit(metadata,raw):
    r=json.loads((metadata/'run-completed.json').read_bytes());jobs=json.loads((metadata/'jobs-completed.json').read_bytes())['jobs'];a=json.loads((metadata/'native-artifact.json').read_bytes());archive=raw/'original-native.zip'
    require(r['id']==RUN and r['head_sha']==HEAD and r['status']=='completed' and r['conclusion']=='failure','exact failed run')
    require(a['id']==ARTIFACT and a['workflow_run']['id']==RUN and a['workflow_run']['head_sha']==HEAD and a['digest']=='sha256:'+DIGEST and archive.stat().st_size==a['size_in_bytes']==10930120 and hashlib.sha256(archive.read_bytes()).hexdigest()==DIGEST,'official native ZIP identity/digest')
    require(all(j['conclusion']=='success' for j in jobs if j['name'] in ('Windows / Python 3.9','Windows / Python 3.14','Build wheel','Validate manual units routing before private native setup')),'portable/route/package pass')
    failed=[j for j in jobs if j['conclusion']=='failure'];require(len(failed)==1 and failed[0]['name']=='Public finite units write acceptance' and [s['name'] for s in failed[0]['steps'] if s['conclusion']=='failure']==['Verify public document unit profile CLI'],'actual failed step')
    require(hashlib.sha256((raw/'failed.original.log').read_bytes()).hexdigest()==LOG_SHA,'root original failed log')
    with zipfile.ZipFile(archive) as z:
        read=lambda name:json.loads(z.read(PREFIX+name))
        host=read('units-public-acceptance/host-report.json');p=read('units-public-acceptance/cli/public-unit-profile.json');internal=read('units-write-calibration/report.json')
        require(host['source_commit']==internal['source_commit']==HEAD,'report source')
        require(host['success'] is False and host['failure']==dict(type='RuntimeError',message='native full image differs from this CI installation') and 0<host['duration_seconds']<=1800,'first failure, not budget')
        require(not any('identity' in k or 'image' in k for k in host),'actual identity was not persisted')
        require(host['stop_exit_code']==1 and not host.get('owned_native_exit_confirmed') and 'pids_after' not in host and not host.get('forced_native_termination_attempted'),'owned native exit unconfirmed, no unknown termination')
        stop=read('units-public-acceptance/stop.stdout');require(stop['success'] is False and stop['error']['code']=='ActiveDocument','cleanup secondary refusal')
        require([x.get('stage') for x in host['cleanup_errors']]==['capture-owned-native-process',None,'owned-daemon-termination'],'secondary cleanup evidence')
        require(p['success'] is False and p['changed_write_acceptance'] is False and len(p['unit_cases'])==1 and p['unit_cases'][0]['transport']=='cli' and p['unit_cases'][0]['success'] is False and 'write' not in p['unit_cases'][0],'public zero completed')
        require(p['cold_start_coverage']['probes']==[],'zero of three cold probes')
        require(p['host']['owned_by_daemon'] is True and p['host']['shared_interactive'] is False and p['host']['visible'] is False and host['pids_before']==[],'declared owned host preconditions')
        rows=[json.loads(x) for x in z.read(PREFIX+'units-public-acceptance/cli/transport-events.jsonl').splitlines()];latest={x['event_index']:x for x in rows}
        require([x['sequence'] for x in rows]==list(range(1,len(rows)+1)),'raw journal contiguous')
        require(len(latest)==3 and latest[0]['stage']=='daemon.status.completed' and latest[1]['stage']=='document.list.completed' and latest[2]['stage']=='cli.frontend.request.started','actual durable reach')
        pending=latest[2]['event'];require(pending['state']=='running' and pending['cli_frontend_request']['argv'][pending['cli_frontend_request']['argv'].index('document')+1]=='open' and 'cli_frontend_reply' not in pending,'source open no durable reply')
        complete=latest[1]['event'];frame=json.loads(complete['cli_frontend_reply']);stdout=base64.b64decode(frame['stdout_b64'],validate=True)
        require(stdout.decode('utf-8')==frame['stdout']==complete['stdout'] and json.loads(stdout)==complete['result'] and b'\r\n' in stdout,'native-host CLI list raw B64 CRLF contract')
        frontend=p['cli_frontend'];require(frontend['starts']==1 and frontend['exit_confirmed'] is False and frontend['ready']['stdio_capture']['stderr_encoding']=='cp1252','helper startup/stdio/unconfirmed exit')
        traces=[]
        for line in z.read(PREFIX+'units-public-acceptance/daemon.stderr').decode(errors='strict').splitlines():
            if line.startswith('{'):
                try:value=json.loads(line)
                except ValueError:continue
                if value.get('event')=='swcli.native-call':traces.append(value)
        require(len({t['worker_pid'] for t in traces})==1 and not [t for t in traces if t['phase']=='error'],'single public worker/no native API error')
        require(not [t for t in traces if t['call']=='IModelDocExtension.SetUserPreferenceInteger'],'zero public setter')
        require(traces[-1]['operation']=='document.open' and traces[-1]['sequence']==0 and traces[-1]['phase']=='end','open native ended but no durable frontend reply')
        max_boundary=max(t['duration_ms']/1000 for t in traces if t['phase']!='begin');require(max_boundary<=600,'native boundary budget')
        require(internal['success'] is True and internal['cleanup_errors']==[] and internal['owned_native_exit_confirmed'] is True and internal['pids_before']==internal['pids_after']==[] and internal['duration_seconds']<=1800,'separate internal lifecycle')
        require([len(c['write_steps']) for c in internal['cases']]==[46,46,47] and all(c['success'] for c in internal['cases']),'internal 139 reach')
        files=0;geometry=0;nonexact=0
        for case in internal['cases']:
            for step in case['write_steps']:
                require(step['success'] is True and step['result']['native_return_value'] is True and step['result']['mutation']==dict(attempted=True,may_have_changed=True),'private changed receipt')
                require(checks.fingerprint(step['before'])==step['before_fingerprint'] and checks.fingerprint(step['after'])==step['after_fingerprint'] and typed(step['after'])==typed(step['readonly_profile']),'private full profiles/readonly persistence')
                for field in ('source','target'):
                    require(hashlib.sha256(z.read(PREFIX+'units-write-calibration/'+step[field+'_file'].replace('\\','/'))).hexdigest()==step[field+'_sha256'],'private native bytes hash');files+=1
                if case['document_type']==1:
                    for label,comparison in [('geometry_after_write','comparison_geometry_after_write'),('geometry_readonly','comparison_geometry_readonly')]:
                        checks.geometry(case['geometry_before'],step[label],step[comparison]);geometry+=1;nonexact+=not step[comparison]['exact_equal']
        installation=json.loads((metadata/'installation-path-evidence.json').read_bytes())
        install_zip=raw/'original-install-logs.zip';require(install_zip.stat().st_size==3215896 and hashlib.sha256(install_zip.read_bytes()).hexdigest()=='2a52d351cc9f74cbc4be2e94a761a591748f3dceedbe6981c6a72f6f2b0f4cec','official installer ZIP digest')
        with zipfile.ZipFile(install_zip) as logs:msi=logs.read('solidworks-msi.log')
        require(hashlib.sha256(msi).hexdigest()==installation['msi_log_sha256'],'original MSI receipt')
        text=msi.decode('utf-16' if msi.startswith(b'\xff\xfe') else 'utf-8');install_dir=re.search(r'^Property\(S\): INSTALLDIR = (.+)$',text,re.M).group(1).strip()
        require(ntpath.normcase(ntpath.normpath(ntpath.join(install_dir,'SLDWORKS.exe')))==ntpath.normcase(ntpath.normpath(installation['failed_head_expected_image_raw'])),'actual MSI path and expected differ')
        require(installation['normalized_path_agrees'] is True and installation['installer_verified_com_registration'] is True and installation['query_observed_image_available'] is False,'install recipe agrees, returned image unknown')
        return dict(audit_success=True,run_id=RUN,head_sha=HEAD,native_artifact_id=ARTIFACT,native_zip_sha256=DIGEST,failed_log_sha256=LOG_SHA,first_failure=host['failure'],first_boundary='wrapper native-host identity admission',actual_returned_image_available=False,deeper_mismatch_cause_established=False,installer_and_expected_path_agree=True,public=dict(started_cli_cases=1,completed_cases=dict(cli=0,sdk=0,mcp=0),cold_probes_completed=0,native_setter_calls=0,native_trace_events=len(traces),native_api_errors=0,source_open_native_ended=True,source_open_reply_durable=False,max_native_boundary_seconds=max_boundary),cleanup=dict(owned_native_exit_confirmed=False,helper_exit_confirmed=False,pids_after=None,stop_error='ActiveDocument',errors=host['cleanup_errors'],unknown_native_termination_attempted=False),internal=dict(success=True,steps=139,duration_seconds=internal['duration_seconds'],native_files_checked=files,part_geometry_comparisons=geometry,part_geometry_nonexact=nonexact,owned_exit_confirmed=True),stdio=dict(windows_portable_jobs_passed=True,completed_cli_list_raw_crlf_b64_verified=True,observed_isolated_stderr_codec='cp1252'),public_native_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--metadata-dir',type=Path,required=True);parser.add_argument('--raw-dir',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();data=json.dumps(audit(args.metadata_dir,args.raw_dir),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(data)
    else:print(data,end='')

if __name__=='__main__':main()
