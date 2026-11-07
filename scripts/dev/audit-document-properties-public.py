"""First-layer offline replay of public gate receipts, hashes and native traces.
Uses the existing strict trace validator; final independent review is separate.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import re
import zipfile
import stat
from pathlib import Path, PureWindowsPath, PurePosixPath
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]

def check(ok, message):
    if not ok: raise ValueError(message)

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,allow_nan=False)

class IndexedTrace:
    """Preserve each original request's line order, parse the full log only once."""
    def __init__(self, path):
        self.rows = {}; self.request = None
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            try: row = json.loads(line)
            except json.JSONDecodeError:
                check('"swcli.native-call"' not in line, 'malformed native trace')
                continue
            if type(row) is dict and row.get('event') == 'swcli.native-call':
                self.rows.setdefault(row['request_id'], []).append(line)
    def read_text(self, **kwargs):
        return '\n'.join(self.rows.get(self.request, []))


def business(result):
    return {key:value for key,value in result.items() if key not in ('request_id','replayed')}


def background(result, document_id=None):
    doc = result['document']
    check(doc['active'] is False and doc['current'] is False, 'foreground/current was changed')
    if document_id is not None: check(doc['document_id'] == document_id, 'document identity changed')


def refusal(row, expected, proofs):
    result = row['result']; trace = row['native_trace']
    check(result['ok'] is False and result['error']['type'] == expected, 'wrong refusal')
    check(trace == proofs[trace['request_id']] and trace['native_setters'] == []
          and trace['text_format_assignments'] == [] and trace['set_save_flag_calls'] == 0,
          'refusal reached mutation')
    if 'mutation' in result:
        check(result['mutation'] == {'attempted':False,'may_have_changed':False}, 'refusal mutation receipt differs')


def verify_case(case, profile, directory, record, gate, events, proofs):
    from swcli.document_annotation_fonts import (ANNOTATION_FONT_MEMBERS, annotation_font_requested_value_matches,
                                                annotation_font_native_normalizations)
    kind = case['document_type']; initial = case['initial']
    expected = 12 if profile == 'standards' else 7 if profile == 'fonts' else 5 if kind == 3 else 10
    plan = gate.targets(profile, initial)
    check(canonical(case['planned_targets']) == canonical(plan) and len(plan) == expected, 'finite field/transition plan differs')
    check(case['success'] is True and len(case['writes']) == len(case['value_refusals'])
          == len(case['same_values']) == expected, 'write/refusal/noop coverage missing')
    saved_expected = expected if profile in ('standards','fonts') else 1
    check(len(case['saved_copies']) == len(case['clean_same_values']) == saved_expected, 'saved/noop coverage missing')
    opened = case['open']; check(opened['ok'] is True and opened['read_only'] is False
        and opened['api_errors'] == opened['api_warnings'] == 0 and opened['document']['modified'] is False,
        'initial input did not open clean/writable')
    check(initial['document']['modified'] is False, 'initial snapshot dirty'); background(initial, opened['document']['document_id'])
    def reject_and_unchanged(row, error, prior):
        refusal(row,error,proofs)
        event=events[row['native_trace']['request_id']]
        position=record['events'].index(event)
        follow=next((e['result'] for e in record['events'][position+1:]
                     if e.get('result',{}).get('action') in ('document.'+gate.READS[profile],'document.'+gate.SETS[profile])),None)
        check(follow is not None and follow['action']=='document.'+gate.READS[profile]
              and follow['ok'] is True and follow['document']==prior['document']
              and canonical(gate.payload(profile,follow))==canonical(gate.payload(profile,prior)),
              'refused request changed snapshot/document state')
    reject_and_unchanged(case['lease_refusal'], 'DocumentLeaseConflict', initial)
    reject_and_unchanged(case['stamp_refusal'], 'DocumentUpdateConflict', initial)
    current = initial; retired = {initial['document']['document_id']}; saved_index = 0
    for index, ((field, target), row, same, rejected) in enumerate(zip(plan, case['writes'],case['same_values'],case['value_refusals'])):
        result = row['result']; proof = row['native_trace']; check(proof == proofs[proof['request_id']], 'write proof differs')
        check(result['ok'] is True and result['changed'] is True and result['document']['modified'] is True
              and result['mutation'] == {'attempted':True,'may_have_changed':True}, 'changed receipt differs')
        background(result, current['document']['document_id'])
        event = events[proof['request_id']]; cmd = event['command']
        check(int(cmd[cmd.index('--if-update-stamp')+1]) == current['document']['update_stamp']
              and cmd[cmd.index('--document')+1] == current['document']['document_id']
              and bool(cmd[cmd.index('--lease')+1]), 'public stamp/document/lease differs')
        before = current['font'] if profile == 'fonts' else current['options'] if profile == 'display' else gate.payload(profile,current)
        check(canonical(result['before']) == canonical(before), 'CAS before receipt differs')
        if profile == 'fonts':
            check(canonical(json.loads(cmd[cmd.index('--if-font')+1])) == canonical(before), 'font full CAS differs')
            check(result['field'] == field and annotation_font_requested_value_matches(result['font'], field, target), 'font target/mode differs')
            check(result['native_normalizations'] == annotation_font_native_normalizations(result['native_before'],result['native_font'],ANNOTATION_FONT_MEMBERS[field]), 'font normalization differs')
        elif profile == 'display':
            check(result['field'] == field and result['options'][field]['value'] == target
                  and all(result['options'][k] == before[k] for k in before if k != field), 'display changed target/unrequested fields')
        else:
            check(canonical(json.loads(cmd[cmd.index('--if-snapshot')+1])) == canonical(before), 'standard full CAS differs')
            check(result['standard']['value'] == target and gate.payload(profile,result) == result['after'] == result['final'], 'standard target/final differs')
        reject_and_unchanged(rejected, gate.CONFLICTS[profile], current)
        for noop, prior, clean in ((same,result,False),):
            r=noop['result']; t=noop['native_trace']
            check(r['ok'] is True and r['changed'] is False and r['mutation']=={'attempted':False,'may_have_changed':False}
                  and t == proofs[t['request_id']] and t['native_setters']==[] and t['text_format_assignments']==[] and t['set_save_flag_calls']==0,
                  'same-value request mutated')
            check(canonical(gate.payload(profile,r)) == canonical(gate.payload(profile,prior))
                  and r['document'] == prior['document'], 'same-value state/profile drift')
        current = result
        if profile in ('standards','fonts') or index == len(plan)-1:
            saved = case['saved_copies'][saved_index]; clean = case['clean_same_values'][saved_index]; saved_index += 1
            path = directory/PureWindowsPath(saved['host_path']).name
            check(sha(path)==saved['sha256'] and path.stat().st_size==saved['size_bytes'], 'saved native hash/size differs')
            reopen = saved['reopen']; observed = saved['reopened']; fresh = observed['document']
            check(reopen['read_only'] is True and reopen['api_errors']==reopen['api_warnings']==0 and reopen['ok'] is True,
                  'readonly native reopen failed')
            check(fresh['document_id']==reopen['document']['document_id'] and fresh['document_id'] not in retired
                  and fresh['modified'] is False, 'readonly fresh ID/clean state differs'); retired.add(fresh['document_id'])
            background(observed)
            check(canonical(gate.payload(profile,observed)) == canonical(gate.payload(profile,result)), 'saved/readonly profile differs')
            reject_and_unchanged(saved['read_only_refusal'],'ValueError',observed)
            r=clean['result']; t=clean['native_trace']
            check(r['ok'] is True and r['changed'] is False and r['document']['modified'] is False
                  and r['document']['document_id'] not in retired and t==proofs[t['request_id']]
                  and t['native_setters']==[] and t['text_format_assignments']==[] and t['set_save_flag_calls']==0
                  and r['mutation']=={'attempted':False,'may_have_changed':False}, 'clean continuation no-op differs')
            retired.add(r['document']['document_id']); background(r)
            check(canonical(gate.payload(profile,r))==canonical(gate.payload(profile,observed)), 'writable continuation profile differs')
            if kind==1: gate.support.same_geometry(case['geometry_initial'],saved['reopened_geometry'])
            current=r
    if profile=='display': check(len(initial['options'])==expected,'display applicability differs')
    return {'kind':kind,'writes':expected,'dirty_noops':expected,'clean_noops':saved_expected,
            'value_conflict_refusals':expected,'lease_refusals':1,'stamp_refusals':1,
            'readonly_refusals':saved_expected,'saved_readonly':saved_expected}


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
    indexed=IndexedTrace(root/'daemon.stderr.log')
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        paths=list(directory.glob('document-preferences-*.json'))
        if not paths:continue
        check(len(paths)==1,'ambiguous group');record=read(paths[0]);profile=record['profile'].removeprefix('document-preferences-')
        check(record['success'] is True and record['cleanup_errors']==[] and record['group_timeout_seconds']==1800 and record['elapsed_seconds']<1800,'group incomplete')
        if host is None:host=record['host']
        check(record['host']==record['host_after']==host and host['owned_by_daemon'] is True and host['visible'] is False and host['shared_interactive'] is False,'host changed')
        indexed.request = None
        trace=gate.PreferenceTrace(indexed)
        events={e.get('result',{}).get('request_id'):e for e in record['events']}
        proofs={}
        for proof in record['native_call_proofs']:
            event=events[proof['request_id']];result=event['result'];replay=SimpleNamespace(record={'events':[event]})
            indexed.request=proof['request_id']
            actual=trace.verify(replay,profile,changed=result.get('changed') is True,rejected=result.get('ok') is False)
            check(actual==proof,'native proof replay differs');proofs[proof['request_id']]=proof
            if result.get('ok') is True:
                gate.validate_operation_result(result['action'], business(result));background(result)
        check(len(proofs)==len(record['native_call_proofs']),'duplicate proof request')
        pref_events=[e for e in record['events'] if e.get('result',{}).get('action') in ('document.'+gate.READS[profile],'document.'+gate.SETS[profile])]
        check(len(pref_events)==len(proofs) and {e['result']['request_id'] for e in pref_events}==set(proofs),'unverified/duplicate public preference request')
        counts=[verify_case(case,profile,directory,record,gate,events,proofs) for case in record['preference_cases']]
        cleanup=record['case_cleanup']
        check(len(cleanup)==len(counts) and all(c['empty'] is True and c['open_document_count']==0 and c['remaining_document_ids']==[] for c in cleanup),'case cleanup incomplete')
        contracts=record['sdk_mcp_contracts'];check(len(contracts)==len(counts),'SDK/MCP kinds missing')
        for item,case in zip(contracts,record['preference_cases']):
            check([p['transport'] for p in item['proofs']]==['sdk','mcp'],'SDK/MCP transport missing')
            for proof in item['proofs']:
                response=proof['response'];background(response,item['document_id'])
                check(proof['native_trace']==proofs[response['request_id']], 'contract trace differs')
                check(canonical(gate.payload(profile,response))==canonical(gate.payload(profile,case['initial']))
                      and response['document']==case['initial']['document'],'SDK/MCP snapshot/state differs')
        groups.append({'profile':profile,'elapsed_seconds':record['elapsed_seconds'],'cases':counts,'replayed_requests':len(trace.requests)})
    check(len(groups)==len(report['groups']) and all(g['success'] is True for g in report['groups']),'group count differs')
    if report['scope'].startswith('batch:'):
        coverage={(g['profile'],c['kind']) for g in groups for c in g['cases']}
        check(coverage=={(p,k) for p in ('standards','fonts','display') for k in (1,2,3)}
              and len(groups)==5,'batch group/kind coverage differs')
    context=read(root/'context.json')['public_context']
    check(context['source_head']==head and context['native_timeout_seconds']==600
          and context['group_timeout_seconds']==1800,'source context differs')
    totals={}
    for g in groups:
        item=totals.setdefault(g['profile'],{})
        for case in g['cases']:
            for key,value in case.items():
                if key!='kind':item[key]=item.get(key,0)+value
    fixture_provenance=read(root/'fixture-provenance.json')
    for fixture in fixture_provenance['fixtures']:
        path=root.parent/'public-fixtures'/PureWindowsPath(fixture['path']).name
        check(sha(path)==fixture['sha256'],'immutable input fixture hash differs')
    stop=read(root/'daemon-stop.stdout.log')
    check(stop.get('ok') is True or stop.get('success') is True,'daemon shutdown receipt failed')
    return {'first_layer_audit_success':True,'source_head':head,'manifest_sha256':sha(root/'manifest.json'),'host':host,'groups':groups,'totals':totals,'run_id':context['run_id'],'run_attempt':context['run_attempt'],
            'input_fixtures_unchanged':True,'daemon_shutdown_verified':True,
            'limits':['Drawing plane writes were not attempted in native gate; applicability omission and portable rejection tests only.', 'Native forced-failure/partial-mutation injection and visual rendering were not exercised by this successful public run.'],'full_modeling_acceptance':False,'scope':'hash/receipt/strict native-trace replay; final independent review by coordinator'}

def verify_download(root, head, archive, run_metadata, artifact_metadata):
    run = read(run_metadata); artifacts = read(artifact_metadata)['artifacts']
    check(run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==head
          and run['run_attempt']==1 and run['event']=='workflow_dispatch'
          and run['workflow_id']==362005755 and run['repository']['full_name']=='YJBeetle/SWCLI'
          and run['head_branch']=='codex/docprops-calibration-performance','official run scope differs')
    check(len(artifacts)==1,'ambiguous artifact catalog'); artifact=artifacts[0]
    check(artifact['workflow_run']['head_sha']==head and artifact['workflow_run']['id']==run['id']
          and artifact['name']==f"swcli-docprops-public-{run['id']}-1"
          and 'sha256:'+sha(archive)==artifact['digest'] and archive.stat().st_size==artifact['size_in_bytes'],
          'official artifact digest/size/head differs')
    extracted=root.parent.resolve(); listed=set()
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name=PurePosixPath(info.filename)
            check(not name.is_absolute() and '..' not in name.parts and '\\' not in info.filename
                  and not stat.S_ISLNK(info.external_attr>>16),'unsafe original archive path')
            if info.is_dir():continue
            check(info.filename not in listed,'duplicate original archive path');listed.add(info.filename)
            path=extracted/info.filename
            check(path.is_file() and not path.is_symlink() and path.stat().st_size==info.file_size
                  and sha(path)==hashlib.sha256(z.read(info)).hexdigest(),'extracted bytes differ from official ZIP')
    check(listed=={p.relative_to(extracted).as_posix() for p in extracted.rglob('*') if p.is_file()},'original extraction file catalog differs')
    context=read(root/'context.json')['public_context']
    check(str(run['id'])==context['run_id'] and context['run_attempt']=='1','artifact context/run differs')
    return {'official_digest_verified':True,'zip_matches_all_extracted_files':True,'original_file_count':len(listed),
            'run_id':run['id'],'run_attempt':1,'artifact_id':artifact['id'],'artifact_sha256':sha(archive)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--head',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--run-metadata',type=Path)
    parser.add_argument('--artifact-metadata',type=Path)
    args=parser.parse_args()
    check(args.root.resolve().parent not in args.output.resolve().parents,'keep all originals immutable')
    check(all((args.archive,args.run_metadata,args.artifact_metadata)) or not any((args.archive,args.run_metadata,args.artifact_metadata)),
          'official archive verification requires archive and both metadata files')
    official=verify_download(args.root,args.head,args.archive,args.run_metadata,args.artifact_metadata) if args.archive else None
    result=audit(args.root,args.head)
    result['official_download']=official
    result['auditor_sha256']=sha(Path(__file__))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
