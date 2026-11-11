"""Pinned successful ORIGINAL evidence audit; stdlib, no product/gate/COM imports."""
import argparse
import ast
import base64
from collections import Counter,defaultdict
import hashlib
import importlib.util
import json
import math
import ntpath
from pathlib import Path
import re
import subprocess
import zipfile

RUN=42935636514
HEAD='459b0cf88892fe1af013156994568d6e52e6df2e'
ARTIFACT=13820837309
ZIP_SHA='c34b58cd4796d7778eae31b01d69bacc1108d9c9c12e22908b6d054c37fb7117'
BASE='swcli-native-smoke/'
PREFIX=BASE+'units-write-calibration/'
LOG_SHA='4b3c7a246f92db6825b176563050d05bcbad01c2636141e42acca104699babfb'
WINDOWS={
 '3.9':dict(job=130244936740,artifact=13817964066,zip_sha='0bb8091df33452d2d60f2e4398ea7caf905c20c9d03d6cd8f536e0b0b3e902cb',log_sha='43bae8aa989f1c2607584d2d4a4cf5f72894da450b80c640fce15352d9a26104',seconds=252.285,skipped=11),
 '3.14':dict(job=130244936949,artifact=13818087697,zip_sha='3c964d83bebfa37b9ccccdc3b91edd6be8365e4307842f8229f336a19673f216',log_sha='437d2ac789396a712e1798fc2f4f952f261e0e03bd4fa99f5ef14324351d8c92',seconds=178.279,skipped=4),
}
spec=importlib.util.spec_from_file_location('_unit_success_pure_checks',Path(__file__).with_name('audit-units-write-42414478796.py'))
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
require=checks.require;typed=checks.typed;fingerprint=checks.fingerprint;geometry=checks.geometry
FIELDS=checks.FIELDS;TARGETS=checks.TARGETS;RAW=checks.RAW

def digest(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':'))
def clean(value):return {k:v for k,v in value.items() if k not in ('request_id','replayed')}
def same(a,b,message):require(typed(a)==typed(b),message)
def norm(path):return ntpath.normcase(ntpath.normpath(path))
def source_bytes(repo,path):return subprocess.check_output(['git','show',HEAD+':'+path],cwd=repo)
def source_forms(raw):
    lf=raw.replace(b'\r\n',b'\n');return {digest(lf):'LF',digest(lf.replace(b'\n',b'\r\n')):'CRLF'}
def source_hash(repo,path,value):
    forms=source_forms(source_bytes(repo,path));require(value in forms,'source bytes '+path);return forms[value]
def literals(repo,path):
    result={}
    for node in ast.parse(source_bytes(repo,path)).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            try:result[node.targets[0].id]=ast.literal_eval(node.value)
            except (ValueError,TypeError):pass
    return result

def check_artifact(artifacts,aid,path,sha):
    a=next(a for a in artifacts if a['id']==aid)
    require(a['workflow_run']['id']==RUN and a['workflow_run']['head_sha']==HEAD and a['size_in_bytes']==path.stat().st_size and a['digest']=='sha256:'+sha and digest(path.read_bytes())==sha,'official artifact/run/head/size/digest '+str(aid))
    return a

def windows_probes(metadata,raw,artifacts,jobs):
    results={}
    for version,expected in WINDOWS.items():
        job=next(j for j in jobs if j['id']==expected['job']);require(job['name']=='Windows / Python '+version and job['conclusion']=='success','Windows job')
        check_artifact(artifacts,expected['artifact'],raw/('summary-'+version+'.original.zip'),expected['zip_sha'])
        with zipfile.ZipFile(raw/('summary-'+version+'.original.zip')) as z:
            summary=json.loads(z.read('summary.json'));require(summary['source']['commit']==HEAD and summary['source']['scope']=='portable-checks-python-'+version and summary['first_failure'] is None and summary['cleanup_errors']==[],'portable summary source/status')
        b=(raw/('windows-'+version+'.original.log')).read_bytes();require(digest(b)==expected['log_sha'],'original Windows log hash')
        text=b.decode('utf-8-sig');require(re.findall(r'Ran (\d+) tests in ([\d.]+)s',text)==[('2008',str(expected['seconds']))] and re.findall(r'OK \(skipped=(\d+)\)',text)==[str(expected['skipped'])],'Windows full suite actual counts')
        for test in ('test_real_windows_short_and_long_file_paths_have_same_os_identity','test_real_windows_different_and_missing_files_cannot_supply_same_file_proof'):
            rows=[l for l in text.splitlines() if test+' (' in l];require(len(rows)==1 and rows[0].endswith(' ... ok'),'Windows real probe executed, not skipped '+test)
        marker='units.short-long-file-identity-observation ';rows=[l for l in text.splitlines() if marker in l];require(len(rows)==1,'one actual Windows short/long observation')
        observation=json.loads(rows[0].split(marker,1)[1]);e=observation['evidence'];q=e['expansion'];image=observation['expanded']
        require(norm(observation['short_image'])!=norm(observation['expected']) and image==observation['expected'] and e['samefile'] is True and e['recorded_file_ids_match'] is True and e['file_ids_available'] is True and e['raw_stat']==e['expected_stat'] and e['raw_stat']['inode']>0,'actual distinct short/long same OS file')
        require(q['api']=='GetLongPathNameW' and q['ctypes_bytes']==dict(DWORD=4,wchar=2) and q['last_error'] is None and q['returned_chars']==q['image_length_utf16_units']==len(image.encode('utf-16-le'))//2 and q['nul_at_returned_index'] is True and base64.b64decode(q['buffer_prefix_b64'],validate=True)==image.encode('utf-16-le')+b'\0\0','actual Windows expansion ABI/raw buffer')
        results[version]=dict(job_id=job['id'],tests=2008,seconds=expected['seconds'],skipped=expected['skipped'],real_positive_probe_passed=True,real_negative_probe_passed=True,raw_log_sha256=expected['log_sha'],summary_zip_sha256=expected['zip_sha'],observation=observation)
    return results

def identity_proof(value):
    identity=value['observed_identity'];q=value['image_query'];path=value['image_path_identity'];expanded=path['expansion'];expected=value['expected_image']
    require(value['capture_status']['phase']=='persisting' and value['requested_pid']==identity['pid'] and value['launch_timestamp']<=identity['creation_timestamp']<=value['observed_timestamp'],'durable pre-admission identity/PID/creation')
    require(q['success'] is True and q['last_error'] is None and q['ctypes_bytes']==dict(HANDLE=8,DWORD=4,BOOL=4,wchar=2) and q['image']==identity['image'] and q['returned_chars']==q['image_length_utf16_units']==len(identity['image'].encode('utf-16-le'))//2 and q['nul_at_returned_index'] is True and base64.b64decode(q['buffer_prefix_b64'],validate=True)==identity['image'].encode('utf-16-le')+b'\0\0','raw Query ABI/image bytes')
    actual=expanded['expanded_image'];require(expanded['api']=='GetLongPathNameW' and expanded['ctypes_bytes']==dict(DWORD=4,wchar=2) and expanded['returned_chars']==expanded['image_length_utf16_units']==len(actual.encode('utf-16-le'))//2 and expanded['nul_at_returned_index'] is True and expanded['last_error'] is None and base64.b64decode(expanded['buffer_prefix_b64'],validate=True)==actual.encode('utf-16-le')+b'\0\0','expanded full image ABI/raw bytes')
    require(norm(actual)==norm(expected) and path['expanded_matches_expected'] is True and path['samefile'] is True and path['recorded_file_ids_match'] is True and path['file_ids_available'] is True and path['raw_stat']==path['expected_stat'] and path['raw_stat']['inode']>0,'full expected and OS same-file proof')
    same(value['admission_identity'],{**identity,'image':actual},'explicit expanded admission copy')
    return dict(role=value['role'],pid=identity['pid'],raw_image=identity['image'],expanded_image=actual,expected_image=expected,file_stat=path['raw_stat'],samefile=True,raw_identity_retained=True)


def audit_private(archive,repo):
    with zipfile.ZipFile(archive) as z:
        report_bytes=z.read(PREFIX+'report.json');p=json.loads(report_bytes)
        require(p['source_commit']==HEAD and p['success'] is True and p['profile']=='units-write-calibration-v1' and p['public_write_domain_count']==137,'internal source/scope')
        require(p['write_acceptance_eligible'] is False and p['full_acceptance_eligible'] is False,'internal is not public/full')
        require(p['revision']=='33.5.0' and typed(p['budgets'])==typed(dict(native_seconds=600,group_seconds=1800)) and 0<p['duration_seconds']<=1800,'revision/budgets')
        require(p['cleanup_errors']==[] and 'failure' not in p and p['owned_native_exit_confirmed'] is True,'native cleanup')
        require(type(p['host_pid']) is int and p['host_pid']>0 and p['host_pid'] not in p['pids_before'] and p['pids_before']==p['pids_after'],'owned process inventory')
        require(PREFIX+'watchdog.json' not in z.namelist(),'watchdog failure present')
        rows=[json.loads(line) for line in z.read(PREFIX+'trace.jsonl').decode().splitlines()];stack=[];durations=[];counts=Counter()
        for row in rows:
            if row['phase']=='begin':stack.append(row);counts[row['call']]+=1
            else:
                require(row['phase']=='end' and stack and stack[-1]['sequence']==row['sequence'],'native error/incomplete/nesting')
                start=stack.pop();elapsed=row['monotonic']-start['monotonic'];require(0<=elapsed<=600,'native budget');durations.append(elapsed)
        require(not stack and rows[-1]['monotonic']-rows[0]['monotonic']<=p['duration_seconds']<=1800,'complete trace/group')
        for name in ('DispatchEx','ExitApp.owned-once','wait-owned-process','inventory-processes-before','inventory-processes-after'):
            require(counts[name]==1,'unexpected host lifecycle: '+name)
        require(counts['document-unit-profile.IModelDocExtension.SetUserPreferenceInteger']==139,'unit setter count')
        source_forms={}
        for label,path in dict(calibration='scripts/ci/calibrate-document-unit-profile.py',write_harness='scripts/ci/gate_support/unit_profile_writes.py',native_adapter='src/swcli/hosts/windows_document_unit_profile.py',catalog='src/swcli/document_unit_profile.py').items():
            raw_source=subprocess.check_output(['git','show',HEAD+':'+path],cwd=repo);lf=raw_source.replace(b'\r\n',b'\n')
            forms={hashlib.sha256(lf).hexdigest():'LF',hashlib.sha256(lf.replace(b'\n',b'\r\n')).hexdigest():'CRLF'}
            require(p['operating_source_sha256'][label] in forms,'operating source bytes: '+path);source_forms[path]=forms[p['operating_source_sha256'][label]]
        require([c['document_type'] for c in p['cases']]==[1,2,3],'exact three types')
        domains={};case_summaries=[];file_count=0;geom_count=0;nonexact=0;max_delta=0.0
        baseline=p['cases'][0]['geometry_before']
        for k,v in (('volume_mm3',12000),('surface_area_mm2',3800)):
            require(math.isclose(baseline[k],v,rel_tol=1e-7,abs_tol=1e-5),'analytic box')
        for axis,v in zip('xyz',(0,0,5)):require(math.isclose(baseline['centroid_mm'][axis],v,rel_tol=1e-7,abs_tol=1e-5),'analytic centroid')
        for case,suffix in zip(p['cases'],('SLDPRT','SLDASM','SLDDRW')):
            kind=case['document_type'];config='Default' if kind in (1,2) else None
            require(case['success'] is case['write_diagnostic_success'] is True,'case incomplete')
            require(len(case['template_sha256'])==64 and hashlib.sha256(z.read(PREFIX+'units.'+suffix)).hexdigest()==case['file_sha256'],'initial native/template hash')
            current=case['initial_profile'];fingerprint(current);initial=current['values']['system']['native_value']
            prepared=[];scalar=[];system=[];phase='prepare';previous_native_sha=case['file_sha256']
            for index,s in enumerate(case['write_steps'],1):
                before,after,result=s['before'],s['after'],s['result'];bf,af=fingerprint(before),fingerprint(after)
                require(s['success'] is True and typed(before)==typed(current) and s['before_fingerprint']==bf and s['after_fingerprint']==af,'complete source chain/fingerprint')
                require(before['document_type']==after['document_type']==kind,'snapshot type')
                field,value=s['field'],s['value'];target=FIELDS[field][value] if FIELDS[field] else value
                require(type(target) is int and target==s['native_target']==after['values'][field]['native_value']!=before['values'][field]['native_value'],'changed target')
                require(result['ok'] is True and result['changed'] is True and result['native_return_value'] is True and result['mutation']==dict(attempted=True,may_have_changed=True),'single setter success receipt')
                require(typed(result['before'])==typed(before) and typed(result['unit_profile'])==typed(after) and typed(result['observed'])==typed(after),'raw result')
                if s['role']=='explicit-custom-preparation':require(phase=='prepare' and field=='system','prepare phase');prepared.append(target)
                elif s['role']=='scalar':
                    require(phase in ('prepare','scalar') and field!='system','scalar phase');phase='scalar';scalar.append((field,target))
                    require(before['values']['system']['native_value']==4 and before['native_units']['fraction_base']==1 and before['native_units']['fraction_value'] in (0,8) and before['native_units']['round_to_fraction']==0,'Custom decimal source')
                    require(all(typed(before['values'][f])==typed(after['values'][f]) for f in FIELDS if f!=field) and typed(before['linkage'])==typed(after['linkage']),'scalar non-target/linkage strict')
                    allowed='length_unit' if field=='linear.unit' else 'significant_digits' if field=='linear.precision' else None
                    require(all(before['native_units'][f]==after['native_units'][f] for f in RAW if f!=allowed),'raw5 unrelated drift')
                    if allowed:require(after['native_units'][allowed]==target,'raw5 target coupling')
                elif s['role']=='system-spoke':require(phase in ('scalar','system') and field=='system','system phase');phase='system';system.append((before['values']['system']['native_value'],target))
                else:raise ValueError('unplanned role')
                if field=='system':require(5 in (before['values']['system']['native_value'],target),'unplanned system pair')
                cb,ca=s['context_before'],s['context_after']
                require(cb['target_identity']==ca['target_identity'] and cb['peer_state']==ca['peer_state'] and cb['peer_identity']==ca['peer_identity'],'target/peer identity or state')
                require(cb['target_state'][0]==ca['target_state'][0]==kind and cb['target_state'][3]==ca['target_state'][3]==config and cb['target_state'][2] is False and ca['target_state'][2] is True,'config/dirty/type')
                require(s['source_sha256']==s['source_original_sha256']==previous_native_sha,'original native byte chain')
                for label in ('source','target'):
                    path=s[label+'_file'].replace('\\','/');require(path==f'kind-{kind}/step-{index:03d}/{label}.{suffix}','exact native path')
                    require(hashlib.sha256(z.read(PREFIX+path)).hexdigest()==s[label+'_sha256'],'native byte hash');file_count+=1
                require(s['save']['ok'] is True and s['save']['save_errors']==0 and s['save']['save_warnings'] is None and s['save']['document']['modified'] is False,'save')
                require(typed(s['readonly_profile'])==typed(after),'readonly full snapshot')
                require(s['readonly_refusal']['ok'] is False and s['readonly_refusal']['error']['type']=='ValueError' and s['readonly_refusal']['mutation']==dict(attempted=False,may_have_changed=False),'readonly zero mutation')
                for label,readonly in (('reopen_readonly',True),('reopen_writable_for_next_case',False)):
                    require(s[label]['ok'] is True and s[label]['read_only'] is readonly and s[label]['api_errors']==s[label]['api_warnings']==0 and s[label]['document']['modified'] is False,'planned reopen')
                if kind==1:
                    for label in ('geometry_after_write','geometry_readonly'):
                        require(s[label+'_measurement']['ok'] is True and typed(s[label+'_measurement']['metrics'])==typed(s[label]),'raw geometry receipt')
                        geometry(baseline,s[label],s['comparison_'+label]);geom_count+=1;nonexact+=not s['comparison_'+label]['exact_equal']
                        max_delta=max(max_delta,max(abs(s[label]['centroid_mm'][a]-baseline['centroid_mm'][a]) for a in 'xyz'))
                key=(kind,bf,field,target)
                require(key not in domains or domains[key]['after']==af,'same domain has conflicting native results')
                domains[key]=dict(after=af,configuration=config)
                current=after;previous_native_sha=s['target_sha256']
            expected={(f,FIELDS[f][v] if FIELDS[f] else v) for f in FIELDS if f!='system' for v in TARGETS.get(f,range(9))}
            require(len(scalar)==37 and set(scalar)==expected,'all eight scalars/precision0..8')
            require(len(system)==8 and set(system)==({(5,c) for c in (1,2,3,4)}|{(c,5) for c in (1,2,3,4)}),'all eight system directions')
            require(prepared==([] if initial==4 else [4] if initial==5 else [5,4]),'actual initial system preserved')
            case_summaries.append(dict(document_type=kind,steps=len(case['write_steps']),scalar_targets=37,system_directions=8,preparation_targets=prepared,configuration=config,template_sha256=case['template_sha256']))
        require(len(domains)==137 and file_count==278 and geom_count==92,'exact native coverage')
        return dict(audit_success=True,run_id=RUN,verified_head=HEAD,artifact_id=ARTIFACT,zip_sha256=ZIP_SHA,report_sha256=hashlib.sha256(report_bytes).hexdigest(),revision=p['revision'],duration_seconds=p['duration_seconds'],trace_rows=len(rows),completed_native_boundaries=len(durations),max_native_call_seconds=max(durations),native_error_events=0,setter_calls=139,native_files_checked=file_count+3,cases=case_summaries,part_geometry_comparisons=geom_count,part_nonexact_comparisons=nonexact,max_centroid_absolute_delta_mm=max_delta,part_raw_baseline_with_hex={**{k:dict(value=baseline[k],hex=float(baseline[k]).hex()) for k in ('volume_mm3','surface_area_mm2')},'solid_body_count':baseline['solid_body_count'],'centroid_mm':{k:dict(value=v,hex=float(v).hex()) for k,v in baseline['centroid_mm'].items()}},owned_native_pid=p['host_pid'],owned_native_exit_confirmed=True,pids_before=p['pids_before'],pids_after=p['pids_after'],source_byte_forms=source_forms,registry_lease_coverage='not exercised by internal direct adapter; required in public validation',public_write_accepted=False,template_bytes_in_zip=False,reviewable_domains=[dict(document_type=k[0],source_snapshot_sha256=k[1],field=k[2],native_target=k[3],after_snapshot_sha256=v['after'],configuration=v['configuration']) for k,v in sorted(domains.items())])


def audit_events(p,cli_directory,repo):
    events=p['events'];by_document=defaultdict(list);ids={};frames=[];cold=[];leases={};counts=Counter()
    f=p['cli_frontend'];require(f['strategy']=='isolated-reused-cli-main' and f['cold_start_per_command'] is False and f['starts']==f['exit_waits']==1 and f['exit_confirmed'] is True and f['normal_eof'] is True and f['exit_code']==0,'one isolated CLI frontend lifecycle')
    source_hash(repo,'scripts/ci/gate_support/unit_cli_worker.py',f['helper_sha256']);source_hash(repo,'src/swcli/cli.py',f['ready']['cli_main_sha256'])
    require(f['pid']==f['ready']['pid'] and f['ready']['swcli_version']=='0.2.4' and f['ready']['stdio_capture']['stdout_encoding']=='utf-8' and f['ready']['stdio_capture']['raw_bytes']=='base64','CLI frontend identity/stdio')
    for index,e in enumerate(events):
        require(e['state']=='completed' and e['returncode'] in (0,1) and e['request_timeout_seconds']==600 and 0<=e['transport_elapsed_seconds']<=615,'completed bounded command')
        same(json.loads(e['stdout']),e['result'],'raw stdout parsed result')
        command=e['command'];result=e['result'];transport=e.get('transport','cli');counts[transport]+=1
        require(e['returncode']==(1 if result.get('ok') is False else 0),'actual process outcome')
        rid=result.get('request_id');require(type(rid) is str and rid not in ids,'unique actual request ID');ids[rid]=dict(index=index,event=e)
        if 'cli_frontend_reply' in e:
            frame=json.loads(e['cli_frontend_reply']);request=e['cli_frontend_request'];require(frame['kind']=='reply' and frame['sequence']==request['sequence'] and frame['exception'] is None,'CLI frame sequence/outcome')
            same(json.loads(e['cli_frontend_request_json']),request,'raw CLI request frame');same(request['argv'],command[command.index('--endpoint'):],'unmodified actual CLI arguments')
            out=base64.b64decode(frame['stdout_b64'],validate=True);err=base64.b64decode(frame['stderr_b64'],validate=True)
            require(out.decode('utf-8')==frame['stdout']==e['stdout'] and err.decode(f['ready']['stdio_capture']['stderr_encoding'])==frame['stderr']==e['stderr'] and frame['returncode']==e['returncode'],'strict authoritative CLI bytes/codec')
            frames.append(frame['sequence'])
        elif e.get('cold_start_probe'):
            require(command[1:4]==['-I','-m','swcli'] and e['cli_process_strategy']=='fresh-subprocess','real independent cold CLI process');cold.append(e)
        if transport in ('sdk','mcp'):
            request=e['wire_request'];wire=e['wire_response'];require(request['request_id']==wire['request_id']==rid and request['timeout_ms']==600000 and request['api_version']=='swcli/v1','SDK/MCP actual envelope/600s context')
            if isinstance(wire.get('result'),dict):body=dict(wire['result'])
            else:body=dict(ok=False,action=request['operation'],error=dict(type=wire['error']['code'],message=wire['error']['message']))
            body['request_id']=wire['request_id']
            if wire.get('replayed') is True:body['replayed']=True
            same(body,result,'SDK/MCP raw reply vs presented result');require(wire.get('replayed') is not True,'no replay used as fresh receipt')
            if transport=='mcp':
                presented=e['mcp_call_tool_result'];same(presented['structuredContent'],wire,'MCP structured response');same(json.loads(next(v['text'] for v in presented['content'] if v['type']=='text')),wire,'MCP text response');require(presented['isError'] is (wire['success'] is False),'MCP actual error flag')
        if result.get('action')=='document.unit-profile-set':
            doc=command[command.index('--document')+1];by_document[doc].append((index,e))
        if result.get('action')=='document.lease.acquire':
            lease=result['lease'];require(command[command.index('--ttl-seconds')+1]=='600' and lease['session_id']==p['session_id'] and math.isfinite(lease['expires_in_seconds']) and lease['expires_in_seconds']>=0,'actual requested 600s lease and finite remaining-time receipt');leases[lease['document_id']]=lease['lease_id']
            if transport in ('sdk','mcp'):require(e['wire_request']['parameters']['ttl_seconds']==600,'wire requested lease TTL600')
    require(frames==list(range(1,len(frames)+1)) and len(frames)==f['commands']==4676 and len(cold)==3,'CLI single sequence and exactly three cold processes')
    latest={};sequence=0
    with (cli_directory/'transport-events.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);sequence+=1;require(row['sequence']==sequence and 0<=row['event_index']<len(events),'durable journal contiguous order');latest[row['event_index']]=digest(canonical(row['event']).encode())
    # daemon status is lifecycle CLI and still journaled by this gate.
    require(set(latest)==set(range(len(events))),'durable journal covers every command')
    for index,e in enumerate(events):require(latest[index]==digest(canonical(e).encode()),'final raw journal matches semantic event '+str(index))
    mcp=p['transport_setup']['mcp'];require(mcp['closed'] is True and mcp['initialize']['serverInfo']['name']=='swcli' and {'execute','capabilities'}<={t['name'] for t in mcp['tools']['tools']},'actual single MCP stdio setup and close')
    require(mcp['command'][1:4]==['-I','-m','swcli'] and mcp['command'][-2:]==['mcp','serve'] and mcp['command'][mcp['command'].index('--endpoint')+1]==p['endpoint'],'MCP same owned endpoint')
    cap=mcp['unit_profile_capability'];require(cap['structuredContent']['success'] is True and cap['isError'] is False,'MCP actual operation discovery');same(json.loads(next(v['text'] for v in cap['content'] if v['type']=='text')),cap['structuredContent'],'MCP capability text/structured agreement')
    return by_document,ids,leases,cold,dict(counts),sequence


def request_context(e):
    command=e['command'];position=command.index('unit-profile-set')
    value=command[position+2];field=command[position+1]
    if FIELDS[field] is None:value=int(value)
    return dict(document_id=command[command.index('--document')+1],lease_id=command[command.index('--lease')+1],session_id=command[command.index('--session')+1],stamp=int(command[command.index('--if-update-stamp')+1]),snapshot=json.loads(command[command.index('--if-snapshot')+1]),field=field,value=value)


def audit_public(p,private,private_bytes,archive,z,repo,raw,host):
    require(p['profile']=='units-public-writes-v1' and p['success'] is True and p['state']=='completed' and p['changed_write_acceptance'] is True and p['cleanup_errors']==[] and p['full_acceptance_eligible'] is False,'complete bounded public report')
    require(p['calibration_source_commit']==HEAD and p['calibration_sha256']==digest(private_bytes) and len(p['unit_cases'])==417 and [c['transport'] for c in p['unit_cases']]==['cli']*139+['sdk']*139+['mcp']*139,'same run full 139x3 source and order')
    manifest=literals(repo,'src/swcli/document_unit_write_domains.py');reviewed=set(manifest['REVIEWED_UNIT_TRANSITIONS']);require(len(reviewed)==137 and sum(x[2]=='system' for x in reviewed)==26,'manual exact finite domains/system results')
    admission=p['admission'];require(admission['finite_domains']==137 and admission['system_results']==26 and admission['revision']==private['revision']=='33.5.0','bounded revision/domain count')
    for key,source in [('run','AUDITED_RUN'),('head','AUDITED_HEAD'),('artifact','AUDITED_ARTIFACT'),('zip_sha256','AUDITED_ZIP_SHA256'),('report_sha256','AUDITED_REPORT_SHA256')]:same(admission[key],manifest[source],'manual manifest origin '+key)
    source_hash(repo,'src/swcli/document_unit_write_domains.py',admission['installed_manifest_sha256'])
    cli_directory=raw/'original'/BASE/'units-public-acceptance/cli'
    by_document,ids,leases,cold,event_counts,journal_rows=audit_events(p,cli_directory,repo)
    fixture_root=host['public_command'][host['public_command'].index('--fixture-dir')+1];output_root=host['public_command'][host['public_command'].index('--output-dir')+1]
    steps=[s for c in private['cases'] for s in c['write_steps']];counts=Counter();negatives=Counter();setters={};used=set();geometry_count=nonexact=0;deferred=[];coverage=defaultdict(Counter)
    def bind(receipt,doc,reference,field,value,*,error=None,stamp=None,snapshot=None,contender=False):
        matches=[(i,e) for i,e in by_document[doc] if typed(clean(e['result']))==typed(receipt)]
        require(len(matches)==1,'unique semantic receipt -> actual command for '+str((doc,error)))
        index,e=matches[0];rid=e['result']['request_id'];require(rid not in used,'same request counted twice');used.add(rid)
        context=request_context(e);wanted=dict(document_id=doc,lease_id=leases[doc],session_id=p['session_id']+('-contender' if contender else ''),stamp=reference['document']['update_stamp'] if stamp is None else stamp,snapshot=reference['unit_profile'] if snapshot is None else snapshot,field=field,value=value)
        same(context,wanted,'actual full CAS/stamp/lease/session/field/value')
        if e.get('transport') in ('sdk','mcp'):
            request=e['wire_request'];same(request['parameters'],dict(field=field,value=value,expected_snapshot=wanted['snapshot']),'typed SDK/MCP complete expected snapshot')
            require(request['document_id']==doc and request['lease_id']==wanted['lease_id'] and request['expected_update_stamp']==wanted['stamp'] and request['session_id']==wanted['session_id'],'wire typed registry/CAS context')
        if error:require(receipt['ok'] is False and receipt['error']['type']==error,'expected zero-write refusal');negatives[error]+=1
        return index,e
    for index,case in enumerate(p['unit_cases']):
        s=steps[index%139];kind=case['document_type'];transport=case['transport'];field=s['field'];value=s['value'];target=s['native_target'];bf=fingerprint(s['before']);af=fingerprint(s['after'])
        require(case['success'] is True and case['domain']==[kind,bf,field,target] and (kind,bf,field,target,af) in reviewed,'exact complete domain and reviewed after fingerprint')
        before=case['read'];write=case['write'];after=case['after_write'];ro=case['readonly_read'];final=case['final_read'];doc=before['document']['document_id'];fresh=ro['document']['document_id']
        same(before['unit_profile'],s['before'],'full9 raw5 linkage19 source');same(write['before'],s['before'],'changed before full CAS')
        for snapshot in (write['unit_profile'],write['observed'],after['unit_profile'],ro['unit_profile'],final['unit_profile']):require(fingerprint(snapshot)==af,'full saved/readonly/observed snapshot fingerprint');same(snapshot,s['after'],'full exact after')
        require(write['ok'] is True and write['native_return_value'] is True and write['changed'] is True and write['mutation']==dict(attempted=True,may_have_changed=True),'one real changed success')
        require(after['document']==write['document'] and final['document']==ro['document'] and write['document']['modified'] is True,'exact after/readonly state')
        same({k:v for k,v in write['document'].items() if k not in ('update_stamp','modified')},{k:v for k,v in before['document'].items() if k not in ('update_stamp','modified')},'write exact identity/path/background')
        for receipt in (before,write,after,ro,final):require(receipt['document']['active'] is False and receipt['document']['current'] is False,'target remains background/current false')
        require(case['open']['api_errors']==case['open']['api_warnings']==0 and case['open']['document']['type']==kind and doc==case['open']['document']['document_id'] and fresh!=doc and case['reopen']['read_only'] is True and case['reopen']['api_errors']==case['reopen']['api_warnings']==0 and ro['document']['modified'] is False,'clean source/fresh readonly native reopen')
        expected_source=ntpath.join(fixture_root,s['source_file']);require(norm(case['open']['document']['path'])==norm(expected_source),'actual opened source path is exact hashed fixture')
        for opened,expected_path in ((case['open'],expected_source),(case['reopen'],case['save']['document']['path'])):
            candidates=[e for e in p['events'] if e['result'].get('action')=='document.open' and e['result'].get('document',{}).get('document_id')==opened['document']['document_id']]
            require(len(candidates)==1,'one actual native open per case identity');same(clean(candidates[0]['result']),opened,'actual raw open receipt')
            command=candidates[0]['command'];require(norm(command[command.index('open')+1])==norm(expected_path),'actual open argv exact native path')
            if transport in ('sdk','mcp'):require(norm(candidates[0]['wire_request']['parameters']['path'])==norm(expected_path),'actual SDK/MCP open wire exact native path')
        noop=case['noop'];reference=before if case['noop_phase']=='before-write' else after
        require(noop['changed'] is False and noop['mutation']==dict(attempted=False,may_have_changed=False) and noop['document']==reference['document'],'exact no-op state');same(noop['before'],reference['unit_profile'],'noop before');same(noop['unit_profile'],reference['unit_profile'],'noop full after')
        bind(noop,doc,reference,field,reference['unit_profile']['values'][field]['value'])
        if case['noop_phase']=='after-write':require(kind==3 and field=='mass_properties.length_unit' and case['read_only_source_value']=='inch' and value=='mm','deferred legal noop only');deferred.append(dict(case=index+1,transport=transport))
        lease_i,_=bind(case['lease_refusal'],doc,before,field,value,error='DocumentLeaseConflict',contender=True)
        stamp_i,_=bind(case['stamp_refusal'],doc,before,field,value,error='DocumentUpdateConflict',stamp=before['document']['update_stamp']+1)
        wrong=json.loads(json.dumps(before['unit_profile']));wrong['linkage']['swUnitsTimeUnits']+=-1 if wrong['linkage']['swUnitsTimeUnits']==2147483647 else 1
        cas_i,_=bind(case['cas_refusal'],doc,before,field,value,error='DocumentUnitProfileConflict',snapshot=wrong);require(case['cas_refusal']['mutation']==dict(attempted=False,may_have_changed=False),'CAS rejection zero mutation')
        if 'custom_closed_refusal' in case:
            receipt=case['custom_closed_refusal'];matches=[e for _,e in by_document[doc] if typed(clean(e['result']))==typed(receipt)];require(len(matches)==1,'closed refusal binding');context=request_context(matches[0]);closed_target=FIELDS[context['field']][context['value']] if FIELDS[context['field']] else context['value']
            require(before['unit_profile']['values']['system']['native_value']==4 and (kind,bf,context['field'],closed_target) not in {x[:4] for x in reviewed},'closed exact domain absent from manual catalog')
            bind(receipt,doc,before,context['field'],context['value'],error='UnitProfileCalibrationRequired');require(receipt['mutation']==dict(attempted=False,may_have_changed=False),'closed refusal zero write')
        write_i,event=bind(write,doc,before,field,value);rid=event['result']['request_id'];setters[rid]=dict(case=index+1,transport=transport,document_type=kind)
        rereads=[(i,e) for i,e in enumerate(p['events']) if max(lease_i,stamp_i,cas_i)<i<write_i and e['result'].get('action')=='document.unit-profile' and e['result'].get('document',{}).get('document_id')==doc]
        require(len(rereads)==1,'one post-refusal pre-write guarded reread');same(clean(rereads[0][1]['result']),before,'pre-write refusal/noop preserved complete profile and state')
        bind(case['readonly_refusal'],fresh,ro,field,value,error='ValueError');require(case['readonly_refusal']['mutation']==dict(attempted=False,may_have_changed=False),'readonly zero write')
        saved=case['save'];require(saved['api_saved'] is True and saved['save_errors']==0 and saved['save_warnings'] is None and saved['document']['modified'] is False and norm(saved['document']['path'])==norm(ro['document']['path']),'clean save and exact readonly native path')
        filename='public-write-%03d.%s'%(index+1,('SLDPRT','SLDASM','SLDDRW')[kind-1]);require(ntpath.basename(saved['document']['path'])==filename and digest(z.read(BASE+'units-public-acceptance/cli/'+filename))==case['saved_sha256'],'saved native exact file hash')
        require(norm(saved['document']['path'])==norm(ntpath.join(output_root,filename)),'exact public output directory native file')
        saves=[e for e in p['events'] if e['result'].get('action')=='document.save-as' and e['result'].get('document',{}).get('document_id')==doc]
        require(len(saves)==1,'one actual save copy');same(clean(saves[0]['result']),saved,'actual raw save receipt')
        command=saves[0]['command'];require(norm(command[command.index('save-as')+1])==norm(saved['document']['path']),'actual save argv exact output native file')
        if transport in ('sdk','mcp'):require(norm(saves[0]['wire_request']['parameters']['output'])==norm(saved['document']['path']),'actual SDK/MCP save wire exact output')
        require(case['source_sha256']==s['source_sha256'],'original source native hash binding')
        if kind==1:
            for label,comparison in [('geometry_after_write','comparison_after_write'),('geometry_readonly','comparison_readonly')]:geometry(case['geometry_before'],case[label],case[comparison]);geometry_count+=1;nonexact+=not case[comparison]['exact_equal']
        counts[(transport,kind)]+=1;coverage[transport][field]+=1
    require(len(setters)==417 and len(used)==2844 and dict(negatives)==dict(DocumentLeaseConflict=417,DocumentUpdateConflict=417,DocumentUnitProfileConflict=417,ValueError=417,UnitProfileCalibrationRequired=342),'all changed/noop/negative receipts accounted')
    require(dict(counts)=={(t,k):n for t in ('cli','sdk','mcp') for k,n in ((1,46),(2,46),(3,47))} and all(set(v)==set(FIELDS) for v in coverage.values()) and len(deferred)==3,'complete nine-field/type/transport coverage')
    domain_counts={t:len({tuple(c['domain']) for c in p['unit_cases'] if c['transport']==t}) for t in ('cli','sdk','mcp')};require(set(domain_counts.values())=={137},'all 137 exact domains each route')
    require(len(p['case_cleanup'])==417 and all(x['empty'] is True and x['open_document_count']==0 and x['remaining_document_ids']==[] for x in p['case_cleanup']),'empty catalog after every case')
    probes=p['cold_start_coverage']['probes'];require([x['document_type'] for x in probes]==[1,2,3],'exact three cold document types')
    for probe,event in zip(probes,cold):
        h=json.loads(probe['helper_stdout']);fresh=json.loads(probe['fresh_stdout']);require(probe['equal'] is True and h['request_id']!=fresh['request_id'] and event['stdout']==probe['fresh_stdout'],'independent actual cold raw result')
        same(clean(h),clean(fresh),'cold vs helper identical except request ID');same(h['unit_profile'],probe['snapshot'],'full cold snapshot');same(h['document'],probe['helper_document'],'same cold state')
    return dict(exact_admitted_domains_per_transport=domain_counts,system_full_result_domains=26,actual_source_open_readonly_open_and_save_requests_bound=1251,completed_cases={t:sum(n for (transport,_),n in counts.items() if transport==t) for t in ('cli','sdk','mcp')},per_type={t:{str(k):counts[(t,k)] for k in (1,2,3)} for t in ('cli','sdk','mcp')},field_counts={t:dict(c) for t,c in coverage.items()},negative_receipts=dict(negatives),native_saved_files_checked=417,source_file_references_checked=417,part_geometry_comparisons=geometry_count,part_nonexact_comparisons=nonexact,deferred_legal_noops=deferred,cold_probes=3,events=len(p['events']),transport_events=event_counts,durable_journal_rows=journal_rows,cli_frontend_commands=len([e for e in p['events'] if 'cli_frontend_reply' in e]),cli_frontend_starts=1,cli_frontend_exit_confirmed=True,mcp_closed=True,requested_lease_ttl_seconds=600,remaining_lease_receipt_values=dict(Counter(repr(e['result']['lease']['expires_in_seconds']) for e in p['events'] if e['result'].get('action')=='document.lease.acquire')),case_seconds={t:sum(c['duration_seconds'] for c in p['unit_cases'] if c['transport']==t) for t in ('cli','sdk','mcp')}),ids,setters

def audit_trace(path,events,setters,group_seconds):
    stack=[];workers=set();phases=Counter();operations=Counter();errors=Counter();setter_ids=Counter();roots={};first=last=None;max_seconds=0.0
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.startswith('{'):continue
            row=json.loads(line)
            if row.get('event')!='swcli.native-call':continue
            rid=row['request_id'];require(rid in events,'native request maps to actual transport result');workers.add(row['worker_pid']);phases[row['phase']]+=1
            stamp=row['monotonic_seconds'];first=stamp if first is None else first;last=stamp
            if row['phase']=='begin':
                stack.append(row)
                if row['sequence']==0:require(rid not in roots,'no request retry');roots[rid]=row['operation'];operations[row['operation']]+=1
                if row['call']=='IModelDocExtension.SetUserPreferenceInteger':setter_ids[rid]+=1
            else:
                require(row['phase'] in ('end','error') and stack,'balanced native terminal');start=stack.pop()
                require((start['request_id'],start['sequence'],start['call'],start['operation'],start['worker_pid'])==(rid,row['sequence'],row['call'],row['operation'],row['worker_pid']),'native nesting/source order')
                seconds=row['duration_ms']/1000;require(0<=seconds<=600 and stamp>=start['monotonic_seconds'],'every native boundary 600s');max_seconds=max(max_seconds,seconds)
                if row['phase']=='error':
                    require(row['sequence']==0 and row['exception_type'] in ('DocumentLeaseConflict','DocumentUpdateConflict'),'no unexpected native API error')
                    result=events[rid]['event']['result'];require(result['ok'] is False and result['error']['type']==row['exception_type'],'actual expected operation rejection');errors[row['exception_type']]+=1
    expected={rid:v['event']['result']['action'] for rid,v in events.items() if v['event']['result'].get('action')}
    require(not stack and roots==expected and len(workers)==1 and sum(phases.values())==1710960,'all actual typed requests complete on single worker')
    require(dict(setter_ids)=={rid:1 for rid in setters} and dict(errors)==dict(DocumentLeaseConflict=417,DocumentUpdateConflict=417),'417 exactly one setters; all noop/refusals zero setters')
    require(last-first<=group_seconds<=1800,'single uninterrupted public group')
    return dict(frames=sum(phases.values()),phases=dict(phases),worker_pid=next(iter(workers)),actual_typed_requests=len(roots),operations=dict(operations),setter_calls=sum(setter_ids.values()),native_api_error_events=0,expected_operation_errors=dict(errors),max_native_boundary_seconds=max_seconds,trace_span_seconds=last-first)


def audit(metadata,raw,repo):
    run=json.loads((metadata/'run-terminal.json').read_bytes());jobs=json.loads((metadata/'jobs-terminal.json').read_bytes())['jobs'];artifacts=json.loads((metadata/'artifacts-terminal.json').read_bytes())['artifacts']
    require(run['id']==RUN and run['head_sha']==HEAD and run['head_branch']=='codex/docprops-units-expanded' and run['event']=='workflow_dispatch' and run['run_attempt']==1 and run['status']=='completed' and run['conclusion']=='success','exact successful original run')
    require(len(jobs)==7 and all(j['run_id']==RUN and j['head_sha']==HEAD for j in jobs) and {j['name'] for j in jobs if j['conclusion']=='success'}=={'Windows / Python 3.9','Windows / Python 3.14','Build wheel','Validate manual units routing before private native setup','Public finite units write acceptance'} and sum(j['conclusion']=='skipped' for j in jobs)==2,'exact successful native/prerequisite jobs; release skipped')
    native_job=next(j for j in jobs if j['id']==130247230662);require(next(s for s in native_job['steps'] if s['name']=='Upload private installer logs')['conclusion']=='skipped','installer log upload skipped on success')
    require(not [a for a in artifacts if a['name'].startswith('swcli-install-logs-')],'installer ZIP absent, never substituted')
    workflow=source_bytes(repo,'.github/workflows/ci.yml').decode();require('name: Upload private installer logs\n        if: failure()' in workflow,'installer upload only on failure at exact source')
    archive=raw/'original-native.zip';check_artifact(artifacts,ARTIFACT,archive,ZIP_SHA);require(archive.stat().st_size==47688318,'pinned native ZIP size')
    require(digest((raw/'native.original.log').read_bytes())==LOG_SHA,'original native job log hash')
    source_hash(repo,'docs/verification/audit-units-write-42414478796.py',digest(Path(checks.__file__).read_bytes()))
    portable=windows_probes(metadata,raw,artifacts,jobs)
    internal=audit_private(archive,repo)
    root=raw/'original'/BASE
    with zipfile.ZipFile(archive) as z:
        h=json.loads(z.read(BASE+'units-public-acceptance/host-report.json'));private_bytes=z.read(PREFIX+'report.json');private=json.loads(private_bytes);p=json.loads(z.read(BASE+'units-public-acceptance/cli/public-unit-profile.json'))
        require(h['source_commit']==HEAD and h['success'] is True and 'failure' not in h and h['cleanup_errors']==[] and h['public_exit_code']==h['stop_exit_code']==0 and h['owned_native_exit_confirmed'] is True and h['cli_frontend_exit_confirmed_by_wrapper'] is True and h['pids_before']==h['pids_after']==[] and 0<h['duration_seconds']<=1800,'public original lifecycle success')
        require(not h.get('forced_native_termination_attempted') and h['native_handle_captured_early'] is True and h['public_host_matches_preflight'] is True,'early retained verified native handle, no force exit')
        require(h['owned_native_pid']==p['host']['process_id']==9208 and p['host']['owned_by_daemon'] is True and p['host']['visible'] is False and p['host']['shared_interactive'] is False and h['owned_native_pid']!=private['host_pid'],'same owned public host; private separate')
        same(json.loads(z.read(BASE+'units-public-acceptance/identity-preflight.stdout')),h['identity_preflight']['response'],'original preflight raw response')
        pre=h['identity_preflight'];require(pre['returncode']==0 and pre['requested_cli_timeout_seconds']==600 and pre['effective_health_rpc_timeout_seconds']==10 and pre['effective_health_connect_timeout_seconds']==1 and pre['process_timeout_seconds']==600,'health requested/effective/process timing')
        proofs=[identity_proof(value) for value in h['identity_observations']];require([p['role'] for p in proofs]==['native-host','cli-frontend'],'native + read-only helper identities')
        same(h['owned_native_identity'],h['identity_observations'][0]['observed_identity'],'retained raw native identity');same(h['cli_frontend_retained_identity'],h['identity_observations'][1]['observed_identity'],'retained raw helper identity')
        require(h['identity_observations'][0]['terminate_right'] is True and h['identity_observations'][1]['terminate_right'] is False and h['cli_frontend_retained_identity']['pid']==p['cli_frontend']['pid']==8500,'helper handle query/wait only')
        require(proofs[0]['raw_image']==r'C:\PROGRA~1\SOLIDW~1\SLDWORKS.exe' and proofs[0]['expanded_image']==proofs[0]['expected_image']==r'C:\Program Files\SOLIDWORKS\SLDWORKS.exe','real SW short -> original full installation path')
        stop=json.loads(z.read(BASE+'units-public-acceptance/stop.stdout'));require(stop['success'] is True and stop['result']['stopping'] is True,'normal stop raw receipt')
        public,events,setters=audit_public(p,private,private_bytes,archive,z,repo,raw,h)
        health=[e['result']['result']['host'] for e in p['events'] if e['command'][-3:]==['daemon','status','--json']];require(len(health)==2 and all(typed(x)==typed(p['host']) for x in health),'start/end real daemon status same host')
        trace=audit_trace(root/'units-public-acceptance/daemon.stderr',events,setters,h['duration_seconds'])
        summary=json.loads(z.read('swcli-test-summary/summary.json'));require(summary['source']['commit']==HEAD and summary['first_failure'] is None and summary['cleanup_errors']==[] and all(x['status']=='PASS' for x in summary['phases'] if x['name'] in ('units-calibration','units-public-acceptance','cleanup')),'summary agrees with raw native/public stages')
        summary_public=next(x for x in summary['phases'] if x['name']=='public-evidence');require(summary_public['status']=='SKIP' and summary_public['detail']=='no public acceptance receipts found','preserve generic summary coverage gap without rewriting raw success evidence')
    internal['reviewed_domains_sha256']=digest(canonical(internal.pop('reviewable_domains')).encode())
    return dict(audit_success=True,run_id=RUN,head_sha=HEAD,native_artifact_id=ARTIFACT,native_zip_sha256=ZIP_SHA,native_zip_bytes=archive.stat().st_size,install_zip_available=False,install_zip_absence_reason='exact workflow Upload private installer logs uses if: failure(); successful original job skipped it; official artifact list has no install ZIP',original_native_job_log_sha256=LOG_SHA,windows=portable,public=public,public_trace=trace,identity_proofs=proofs,public_group_seconds=h['duration_seconds'],public_native_pid=h['owned_native_pid'],owned_native_exit_confirmed=True,cli_frontend_exit_confirmed=True,normal_stop_exit_code=0,forced_native_termination=False,pids_before=h['pids_before'],pids_after=h['pids_after'],cleanup_errors=[],internal_private=internal,generic_summary_public_evidence=summary_public,public_acceptance_accepted=True,scope='bounded SOLIDWORKS33.5.0/three configurations and 137 admitted exact domains; no full native product gate, merge, or release claimed')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--metadata-dir',type=Path,required=True);parser.add_argument('--raw-dir',type=Path,required=True);parser.add_argument('--repo-root',type=Path,required=True);parser.add_argument('--output',type=Path)
    a=parser.parse_args();value=json.dumps(audit(a.metadata_dir,a.raw_dir,a.repo_root),ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(value)
    else:print(value,end='')
if __name__=='__main__':main()
