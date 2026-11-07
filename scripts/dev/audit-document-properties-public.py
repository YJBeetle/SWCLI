"""First-layer offline replay of public gate receipts, hashes and native traces.
Uses the existing strict trace validator; final independent review is separate.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]

def check(ok, message):
    if not ok: raise ValueError(message)

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,allow_nan=False)

def audit(root, head):
    manifest=read(root/'manifest.json');check(manifest['source_head']==head,'source head differs')
    listed=set()
    for row in manifest['files']:
        p=root/row['path'];check(root.resolve() in p.resolve().parents and not p.is_symlink() and row['path'] not in listed,'unsafe/duplicate file')
        check(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'hash/size differs: '+row['path']);listed.add(row['path'])
    check(listed=={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'},'unlisted original file')
    report=read(root/'public-report.json');check(report['success'] is True and report['cleanup_errors']==[] and report['source_head']==head,'public report failed')
    check(report['native_timeout_seconds']==600 and report['group_timeout_seconds']==1800,'budget differs')
    spec=importlib.util.spec_from_file_location('replay_preferences',ROOT/'scripts/ci/verify-document-preferences.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    host=None;groups=[]
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        paths=list(directory.glob('document-preferences-*.json'))
        if not paths:continue
        check(len(paths)==1,'ambiguous group');record=read(paths[0]);profile=record['profile'].removeprefix('document-preferences-')
        check(record['success'] is True and record['cleanup_errors']==[] and record['group_timeout_seconds']==1800 and record['elapsed_seconds']<1800,'group incomplete')
        if host is None:host=record['host']
        check(record['host']==record['host_after']==host and host['owned_by_daemon'] is True and host['visible'] is False and host['shared_interactive'] is False,'host changed')
        trace=gate.PreferenceTrace(root/'daemon.stderr.log');events={e.get('result',{}).get('request_id'):e for e in record['events']}
        for proof in record['native_call_proofs']:
            event=events[proof['request_id']];result=event['result'];replay=SimpleNamespace(record={'events':[event]})
            actual=trace.verify(replay,profile,changed=result.get('changed') is True,rejected=result.get('ok') is False)
            check(actual==proof,'native proof replay differs')
        counts=[]
        for case in record['preference_cases']:
            kind=case['document_type'];expected=12 if profile=='standards' else 7 if profile=='fonts' else 5 if kind==3 else 10
            check(case['success'] is True and len(case['writes'])==len(case['value_refusals'])==len(case['same_values'])==expected,'write/refusal/noop coverage missing')
            saved_expected=expected if profile in ('standards','fonts') else 1
            check(len(case['saved_copies'])==len(case['clean_same_values'])==saved_expected,'saved/clean noop coverage missing')
            for row in case['writes']:
                check(row['result']['ok'] is True and row['result']['changed'] is True and row['result']['mutation']=={'attempted':True,'may_have_changed':True},'changed receipt differs')
            for row in case['same_values']+case['clean_same_values']:
                check(row['result']['changed'] is False and row['native_trace']['native_setters']==[] and row['native_trace']['set_save_flag_calls']==0,'noop changed native state')
            retired=set()
            for row in case['saved_copies']:
                path=directory/PureWindowsPath(row['host_path']).name
                check(sha(path)==row['sha256'] and path.stat().st_size==row['size_bytes'],'saved native file hash differs')
                fresh=row['reopened']['document'];check(fresh['modified'] is False and fresh['document_id'] not in retired,'readonly fresh ID/clean state differs');retired.add(fresh['document_id'])
                refusal=row['read_only_refusal']['result'];check(refusal['ok'] is False,'readonly write accepted')
            counts.append({'kind':kind,'writes':expected,'saved_readonly':saved_expected})
        contracts=record['sdk_mcp_contracts'];check(len(contracts)==len(counts),'SDK/MCP kinds missing')
        for item in contracts:check([p['transport'] for p in item['proofs']]==['sdk','mcp'],'SDK/MCP transport missing')
        groups.append({'profile':profile,'elapsed_seconds':record['elapsed_seconds'],'cases':counts,'replayed_requests':len(trace.requests)})
    check(len(groups)==len(report['groups']) and all(g['success'] is True for g in report['groups']),'group count differs')
    return {'first_layer_audit_success':True,'source_head':head,'manifest_sha256':sha(root/'manifest.json'),'host':host,'groups':groups,'full_modeling_acceptance':False,'scope':'hash/receipt/strict native-trace replay; final independent review by coordinator'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--head',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.root.resolve() not in a.output.resolve().parents,'keep originals immutable');result=audit(a.root,a.head);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
