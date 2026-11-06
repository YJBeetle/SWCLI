"""Public installed CLI/daemon gate for one explicitly selected font scope.

No COM import, direct adapter calls, retries, rollback or host restart. Use only
following independent review of matching-head internal native evidence.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time

from swcli import __version__
from swcli.document_font_scopes import FONT_SCOPES, WRITABLE_FONT_SCOPES
from swcli.font_snapshot import FONT_MEMBERS, font_requested_value_matches, font_unrequested_fields_match
from swcli.result_schemas import validate_operation_result

_spec = importlib.util.spec_from_file_location('_font_scopes_public_support', Path(__file__).with_name('verify-document-annotations.py'))
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)
require = support.require


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


class FontScopeTrace:
    def __init__(self, path):
        self.path, self.requests = path, set()

    def verify(self, gate, *, field=None, changed=False, conflict=False):
        event = gate.record['events'][-1]
        response = event['result']
        request = response.get('request_id')
        require(type(request) is str and request and request not in self.requests, 'font public request ID missing/repeated')
        command = event['command']
        operation = 'document.' + command[command.index('document') + 1]
        records = []
        for line in self.path.read_text(encoding='utf-8-sig').splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                require('"swcli.native-call"' not in line, 'malformed native font trace')
                continue
            if type(row) is dict and row.get('event') == 'swcli.native-call' and row.get('request_id') == request:
                records.append(row)
        require(records and all(row.get('operation') == operation for row in records), 'missing/mismatched font request trace')
        first, last = records[0], records[-1]
        require(first.get('sequence') == last.get('sequence') == 0 and first.get('phase') == 'begin'
                and last.get('phase') in ('end', 'error') and first.get('call') == last.get('call') == operation,
                'font request trace is not enclosed')
        worker = first.get('worker_pid')
        require(type(worker) is int and worker > 0 and all(row.get('worker_pid') == worker for row in records),
                'font trace owning worker changed')
        calls = records[1:-1]
        require(len(calls) % 2 == 0, 'incomplete font native pair')
        for sequence, (begin, end) in enumerate(zip(calls[::2], calls[1::2]), 1):
            require(begin.get('sequence') == end.get('sequence') == sequence and begin.get('phase') == 'begin'
                    and end.get('phase') in ('end', 'error') and begin.get('call') == end.get('call'),
                    'font native calls are missing/reordered')
            require(type(end.get('duration_ms')) in (int, float) and math.isfinite(end['duration_ms'])
                    and 0 <= end['duration_ms'] < 600000, 'font native call exceeded 600 seconds')
        require(type(last.get('duration_ms')) in (int, float) and math.isfinite(last['duration_ms'])
                and 0 <= last['duration_ms'] < 600000, 'font request exceeded 600 seconds')
        begins = [row for row in calls if row['phase'] == 'begin']
        native = [row['call'] for row in begins if row.get('stage') == 'document-font-scopes']
        cycle = ['IModelDocExtension.GetUserPreferenceTextFormat'] + ['ITextFormat.' + member + '.get' for member in FONT_MEMBERS.values()]
        all_scopes = cycle * len(FONT_SCOPES)
        is_read = operation == 'document.font-scopes'
        expected = (all_scopes if is_read or conflict or response.get('ok') is True else [])
        if changed:
            require(field in FONT_MEMBERS, 'changed font proof needs a typed field')
            expected = all_scopes + ['ITextFormat.' + FONT_MEMBERS[field] + '.set',
                                    'IModelDocExtension.SetUserPreferenceTextFormat'] + all_scopes * 2
        require(native == expected, 'font native getter/property/setter order or count differs')
        dirty = sum(row['call'] == 'IModelDoc2.SetSaveFlag' for row in begins)
        require(dirty <= int(changed), 'font request marked dirty unexpectedly or repeatedly')
        require(not any(row['call'].startswith('ISldWorks.SetUserPreference') for row in begins), 'font gate reached global preferences')
        if response.get('ok') is True:
            require(not any(row['phase'] == 'error' for row in records), 'successful font request has native errors')
        self.requests.add(request)
        proof = dict(request_id=request, operation=operation, worker_pid=worker,
                     native_getter_cycles=3 if changed else 1 if expected else 0,
                     property_setters=int(changed), document_setters=int(changed), set_save_flag_calls=dirty)
        gate.record.setdefault('native_call_proofs', []).append(proof)
        return proof

    def snapshot(self):
        data = self.path.read_bytes()
        return dict(path=str(self.path), prefix_size_bytes=len(data), prefix_sha256=hashlib.sha256(data).hexdigest(),
                    verified_request_count=len(self.requests))


def read(gate, trace, document, *, session=None):
    result = gate.command('document', 'font-scopes', document=document, session=session)
    validate_operation_result('document.font-scopes', result)
    trace.verify(gate)
    gate.background(result, document)
    return result


def arguments(scope, field, value, before, *, stale=False, stamp=None):
    expected = deepcopy(before['fonts'])
    if stale:
        expected['annotations']['bold'] = not expected['annotations']['bold']
    return ['document', 'font-scope-set', scope, field, canonical(value), '--if-fonts', canonical(expected),
            '--if-update-stamp', str(before['document']['update_stamp'] if stamp is None else stamp)]


def edit(gate, trace, document, scope, field, value, before, *, changed):
    result = gate.write(*arguments(scope, field, value, before), document=document)
    validate_operation_result('document.font-scope-set', result)
    proof = trace.verify(gate, field=field, changed=changed)
    gate.background(result, document)
    require(result['before'] == before['fonts'] and result['changed'] is changed
            and result['mutation'] == {'attempted': changed, 'may_have_changed': changed}, 'font write CAS/mutation receipt differs')
    require(font_requested_value_matches(result['fonts'][scope], field, value)
            and font_unrequested_fields_match(before['fonts'][scope], result['fonts'][scope], field)
            and all(result['fonts'][key] == before['fonts'][key] for key in FONT_SCOPES if key != scope),
            'font readback target/mode/unrequested values differ')
    if changed:
        require(result['document']['modified'] is True, 'font edit did not mark the document dirty')
    else:
        require(result['fonts'] == before['fonts'] and result['document'] == before['document'], 'same-value font edit changed state')
    return dict(result=result, native_trace=proof)


def refuse(gate, trace, document, scope, before, error, *, stale=False, foreign=False, stamp=None):
    args = arguments(scope, 'bold', not before['fonts'][scope]['bold'], before, stale=stale, stamp=stamp)
    if foreign:
        result = gate.command(*args, document=document, session=gate.session + '-contender',
                              lease=gate.leases[document], expected_error=error)
    else:
        result = gate.write(*args, document=document, expected_error=error)
    proof = trace.verify(gate, conflict=error == 'DocumentFontScopeConflict')
    if 'mutation' in result:
        require(result['mutation'] == {'attempted': False, 'may_have_changed': False}, 'font refusal reached mutation')
    observed = read(gate, trace, document)
    require(observed['fonts'] == before['fonts'] and observed['document'] == before['document'], 'font refusal changed state')
    return dict(result=result, native_trace=proof)


def targets(font):
    return [('typeface', 'Arial' if font['typeface'] != 'Arial' else 'Times New Roman'),
            *[(field, not font[field]) for field in ('bold', 'italic', 'underline', 'strikeout')],
            ('height_mm', 3.5 if font['height_mm'] != 3.5 else 4.0),
            ('height_points', 14 if font['height_points'] != 14 else 16)]


def run(gate, fixture_dir, trace, scope):
    gate.record.update(profile='document-font-scopes-' + scope, state='running', success=False,
                       evidence_kind='installed-public-cli-gate', covers_full_modeling_suite=False,
                       selected_scope=scope, source_head=os.environ.get('GITHUB_SHA'), font_scope_cases=[])
    health = gate.health()
    host = gate.record['host'] = health['host']
    require(health.get('server_version') == __version__ and host.get('owned_by_daemon') is True
            and host.get('visible') is False and host.get('shared_interactive') is False,
            'font gate needs matching installed client and independently owned hidden daemon')
    gate.require_empty()
    for suffix, kind in (('SLDPRT', 1), ('SLDASM', 2), ('SLDDRW', 3)):
        source = fixture_dir / ('annotations.' + suffix)
        require(source.is_file(), 'prepared native font fixture is missing')
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        opened, document, foreground = support.open_background(gate, str(source), kind)
        gate.command('document', 'lease', 'acquire', '--ttl-seconds', 1800, document=document)
        initial = read(gate, trace, document, session=gate.session + '-reader')
        case = dict(format=suffix, opened=opened, initial=initial, source_sha256=source_hash, writes=[], saves=[])
        gate.record['font_scope_cases'].append(case)
        baseline = support.geometry(gate, document) if kind == 1 else None
        case['lease_refusal'] = refuse(gate, trace, document, scope, initial, 'DocumentLeaseConflict', foreign=True)
        case['stamp_refusal'] = refuse(gate, trace, document, scope, initial, 'DocumentUpdateConflict', stamp=initial['document']['update_stamp'] + 1)
        current = initial
        retired = set()
        for field, value in targets(initial['fonts'][scope]):
            case.setdefault('cas_refusals', []).append(refuse(gate, trace, document, scope, current, 'DocumentFontScopeConflict', stale=True))
            row = edit(gate, trace, document, scope, field, value, current, changed=True)
            case['writes'].append(row)
            current = row['result']
            same = edit(gate, trace, document, scope, field, value, current, changed=False)
            case.setdefault('same_values', []).append(same)
            current = same['result']
            if field not in ('height_mm', 'height_points'):
                continue
            if kind == 1:
                support.same_geometry(baseline, support.geometry(gate, document))
            saved = support.save_copy(gate, document, scope + '-' + field + '.' + suffix, suffix)
            expected = deepcopy(current['fonts'])
            gate.close(document)
            gate.close(foreground)
            retired.add(document)
            reopened, document, foreground = support.open_background(gate, saved['host_path'], kind, read_only=True)
            require(document not in retired, 'font reopen reused a retired document ID')
            gate.command('document', 'lease', 'acquire', '--ttl-seconds', 1800, document=document)
            current = read(gate, trace, document)
            require(current['fonts'] == expected and current['document']['modified'] is False, 'font snapshots/modes did not persist after readonly reopen')
            refused = refuse(gate, trace, document, scope, current, 'ValueError')
            if kind == 1:
                support.same_geometry(baseline, support.geometry(gate, document))
            require(hashlib.sha256(Path(saved['path']).read_bytes()).hexdigest() == saved['sha256'], 'font readonly check changed saved bytes')
            saved.update(reopen=reopened, reopened=current, readonly_refusal=refused)
            case['saves'].append(saved)
            gate.close(document)
            gate.close(foreground)
            retired.add(document)
            if field == 'height_mm':
                reopened, document, foreground = support.open_background(gate, saved['host_path'], kind)
                require(document not in retired, 'font writable continuation reused a retired ID')
                gate.command('document', 'lease', 'acquire', '--ttl-seconds', 1800, document=document)
                current = read(gate, trace, document)
                require(current['fonts'] == expected and current['document']['modified'] is False, 'writable font continuation changed persisted state')
        require(hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, 'public gate changed source fixture bytes')
        gate.require_empty(after_case='font-scopes-' + scope + '-' + suffix)
        case['success'] = True
        gate.checkpoint('font-scopes-' + scope + '-' + suffix + '-verified')
    require(gate.health()['host'] == host, 'public font gate replaced its daemon/host')
    gate.record.update(state='completed', success=True, elapsed_seconds=time.monotonic() - gate.group_started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--fixture-dir', required=True, type=Path)
    parser.add_argument('--native-trace', required=True, type=Path)
    parser.add_argument('--scope', required=True, choices=WRITABLE_FONT_SCOPES)
    parser.add_argument('--endpoint', default=os.environ.get('SWCLI_ENDPOINT', support.modeling.DEFAULT_ENDPOINT))
    parser.add_argument('--cli-command', required=True, type=support.modeling.executable)
    args = parser.parse_args(argv)
    require(args.native_trace.is_file(), 'trace-enabled daemon stderr is required')
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    gate = support.AnnotationSmoke(directory=directory, host_directory=str(directory), cli=[args.cli_command], endpoint=args.endpoint)
    gate.record_path = directory / 'font-scopes-public.json'
    trace = FontScopeTrace(args.native_trace)
    with gate.record_path.open('x', encoding='utf-8') as stream:
        json.dump(gate.record, stream)
    try:
        run(gate, args.fixture_dir.resolve(), trace, args.scope)
    except BaseException as exc:
        gate.record.update(state='failed', success=False, error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        gate.cleanup()
        if gate.record['cleanup_errors'] or gate.checkpoint_error is not None:
            gate.record.update(state='failed', success=False)
        try:
            gate.record['native_trace_snapshot'] = trace.snapshot()
        except Exception as exc:
            gate.record.update(state='failed', success=False)
            gate.checkpoint_error = gate.checkpoint_error or exc
        gate.checkpoint('font-scopes-public-final')
    if gate.checkpoint_error is not None:
        raise gate.checkpoint_error
    require(not gate.record['cleanup_errors'], 'public font gate cleanup failed')


if __name__ == '__main__':
    main()
