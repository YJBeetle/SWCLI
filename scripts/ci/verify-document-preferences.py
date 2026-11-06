"""Installed public CLI gates for bounded document font, display and standard settings.

Prepared fixtures, one already owned hidden daemon, no COM or native retry here.
Each profile has its own fixed 1800-second budget and immutable evidence file.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PureWindowsPath
import time

from swcli import __version__
from swcli.document_annotation_fonts import ANNOTATION_FONT_WRITABLE_FIELDS
from swcli.document_display_options import DISPLAY_FIELDS
from swcli.document_drafting_standard import DRAFTING_STANDARDS
from swcli.result_schemas import validate_operation_result

_spec = importlib.util.spec_from_file_location('_document_preferences_support', Path(__file__).with_name('verify-document-annotations.py'))
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)
require = support.require
READS = {'fonts': 'annotation-font', 'display': 'display-options', 'standards': 'drafting-standard'}
SETS = {'fonts': 'annotation-font-set', 'display': 'display-option-set', 'standards': 'drafting-standard-set'}
CONFLICTS = {'fonts': 'DocumentAnnotationFontConflict', 'display': 'DocumentDisplayConflict', 'standards': 'DocumentDraftingStandardConflict'}
KINDS = (('SLDPRT', 1), ('SLDASM', 2), ('SLDDRW', 3))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def payload(profile, response):
    keys = {'fonts': ('font', 'native_font'), 'display': ('options',), 'standards': ('standard', 'observed_defaults')}[profile]
    return {key: response[key] for key in keys}


class PreferenceTrace:
    def __init__(self, path):
        self.path = path
        self.requests = set()

    def verify(self, gate, profile, *, changed=False, rejected=False):
        event = gate.record['events'][-1]
        response = event['result']
        request = response.get('request_id')
        require(type(request) is str and request and request not in self.requests, 'preference request ID is missing/repeated')
        command = event['command']
        operation = 'document.' + command[command.index('document') + 1]
        records = []
        for line in self.path.read_text(encoding='utf-8-sig').splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                require('"swcli.native-call"' not in line, 'native trace line is malformed')
                continue
            if type(row) is dict and row.get('event') == 'swcli.native-call' and row.get('request_id') == request:
                records.append(row)
        require(records and all(row.get('operation') == operation for row in records), 'completed preference request trace is missing')
        first, last = records[0], records[-1]
        require(first.get('sequence') == last.get('sequence') == 0 and first.get('phase') == 'begin'
                and last.get('phase') in ('end', 'error') and first.get('call') == last.get('call') == operation,
                'preference trace has no enclosing request')
        worker = first.get('worker_pid')
        require(type(worker) is int and worker > 0 and all(row.get('worker_pid') == worker for row in records), 'native worker changed')
        calls = records[1:-1]
        require(len(calls) % 2 == 0, 'native call pair is incomplete')
        for sequence, (begin, end) in enumerate(zip(calls[::2], calls[1::2]), 1):
            require(begin.get('sequence') == end.get('sequence') == sequence and begin.get('phase') == 'begin'
                    and end.get('phase') in ('end', 'error') and begin.get('call') == end.get('call'), 'native call order differs')
            require(type(end.get('duration_ms')) in (int, float) and math.isfinite(end['duration_ms'])
                    and 0 <= end['duration_ms'] < 600000, 'native call exceeded its fixed budget')
        require(type(last.get('duration_ms')) in (int, float) and math.isfinite(last['duration_ms'])
                and 0 <= last['duration_ms'] < 600000, 'preference request exceeded native budget')
        begins = [row['call'] for row in calls if row['phase'] == 'begin']
        setters = [name for name in begins if name.startswith('IModelDocExtension.SetUserPreference')]
        properties = [name for name in begins if name.startswith('ITextFormat.') and name.endswith('.set')]
        dirty = begins.count('IModelDoc2.SetSaveFlag')
        require(len(setters) == int(changed) and len(properties) == int(changed and profile == 'fonts')
                and dirty <= int(changed), 'preference mutation count differs')
        require(not any(name.startswith('ISldWorks.SetUserPreference') for name in begins), 'preference gate reached global settings')
        if changed:
            if profile == 'fonts':
                field = command[command.index(SETS[profile]) + 1]
                from swcli.document_annotation_fonts import ANNOTATION_FONT_MEMBERS
                require(properties == ['ITextFormat.' + ANNOTATION_FONT_MEMBERS[field] + '.set']
                        and setters == ['IModelDocExtension.SetUserPreferenceTextFormat'], 'font setter method differs')
            elif profile == 'display':
                field = command[command.index(SETS[profile]) + 1]
                require(setters == ['IModelDocExtension.SetUserPreference' + DISPLAY_FIELDS[field]['kind']], 'display setter method differs')
            else:
                require(setters == ['IModelDocExtension.SetUserPreferenceInteger'], 'standard setter method differs')
        # Require every declared getter cycle, not merely a plausible zero-set
        # trace. This also detects missing/reordered font-member observations.
        from swcli.document_annotation_fonts import ANNOTATION_FONT_MEMBERS
        from swcli.document_annotations import ANNOTATION_FIELDS
        font_cycle = ['IModelDocExtension.GetUserPreferenceTextFormat'] + [
            'ITextFormat.' + member + ('' if member == 'IsHeightSpecifiedInPts' else '.get')
            for member in ANNOTATION_FONT_MEMBERS.values()]
        if profile == 'fonts':
            cycle = font_cycle
        elif profile == 'display':
            observed = response.get('options', response.get('before', {}))
            cycle = ['IModelDocExtension.GetUserPreference' + DISPLAY_FIELDS[field]['kind'] for field in DISPLAY_FIELDS if field in observed]
        else:
            observed = response.get('observed_defaults', response.get('before', {}).get('observed_defaults', {}))
            cycle = (['IModelDocExtension.GetUserPreferenceInteger']
                     + ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in ANNOTATION_FIELDS.values()]
                     + font_cycle + ['IModelDoc2.GetUnits']
                     + ['IModelDocExtension.GetUserPreference' + DISPLAY_FIELDS[field]['kind'] for field in DISPLAY_FIELDS if field in observed.get('display', {})]
                     + ['IModelDocExtension.GetUserPreferenceInteger'] * 4)
        tracked = [name for name in begins if name.startswith(('IModelDocExtension.GetUserPreference',
                   'IModelDocExtension.SetUserPreference', 'ITextFormat.')) or name in ('IModelDoc2.GetUnits', 'IModelDoc2.SetSaveFlag')]
        if changed:
            expected_calls = cycle + properties + setters + cycle + ['IModelDoc2.SetSaveFlag'] * dirty + cycle
        elif rejected:
            expected_calls = cycle if response.get('error', {}).get('type') == CONFLICTS[profile] else []
        else:
            expected_calls = cycle
        require(tracked == expected_calls, 'native preference observation/write order is incomplete')
        if not rejected:
            require(not any(row['phase'] == 'error' for row in records), 'successful preference request contains native failure')
        self.requests.add(request)
        proof = {'request_id': request, 'operation': operation, 'worker_pid': worker,
                 'native_call_count': len(begins), 'native_setters': setters,
                 'text_format_assignments': properties, 'set_save_flag_calls': dirty}
        gate.record.setdefault('native_call_proofs', []).append(proof)
        return proof

    def snapshot(self):
        content = self.path.read_bytes()
        return {'path': str(self.path), 'prefix_size_bytes': len(content),
                'prefix_sha256': hashlib.sha256(content).hexdigest(), 'verified_request_count': len(self.requests)}


def acquire(gate, document):
    gate.command('document', 'lease', 'acquire', '--ttl-seconds', 600, document=document)
    require(document in gate.leases, 'public gate did not acquire its explicit write lease')


def read(gate, trace, profile, document, *, session=None):
    response = gate.command('document', READS[profile], document=document, session=session)
    validate_operation_result('document.' + READS[profile], response)
    trace.verify(gate, profile)
    gate.background(response, document)
    return response


def arguments(profile, before, field, value, *, stale=False):
    if profile == 'fonts':
        expected = dict(before['font'])
        if stale:
            expected['bold'] = not expected['bold']
        return [SETS[profile], field, support.scalar_argument(value), '--if-font', canonical(expected)]
    if profile == 'display':
        expected = value if stale else before['options'][field]['value']
        return [SETS[profile], field, support.scalar_argument(value), '--if-value', support.scalar_argument(expected)]
    expected = payload(profile, before)
    if stale:
        expected = json.loads(canonical(expected))
        previous = expected['standard']['value']
        other = 'ansi' if previous != 'ansi' else 'gb'
        expected['standard'] = {'value': other, 'native_value': DRAFTING_STANDARDS[other]}
    return [SETS[profile], value, '--if-snapshot', canonical(expected)]


def edit(gate, trace, profile, document, before, field, value, *, changed):
    response = gate.write('document', *arguments(profile, before, field, value), '--if-update-stamp',
                          before['document']['update_stamp'], document=document)
    validate_operation_result('document.' + SETS[profile], response)
    proof = trace.verify(gate, profile, changed=changed)
    gate.background(response, document)
    require(response['changed'] is changed and response['mutation'] == {'attempted': changed, 'may_have_changed': changed}, 'preference mutation receipt differs')
    expected_before = before['font'] if profile == 'fonts' else before['options'] if profile == 'display' else payload(profile, before)
    require(canonical(response['before']) == canonical(expected_before), 'preference CAS before receipt differs')
    if not changed:
        require(payload(profile, response) == payload(profile, before) and response['document'] == before['document'], 'same-value request changed state')
    else:
        require(response['document']['modified'] is True, 'preference edit was not marked dirty')
        if profile == 'fonts':
            from swcli.document_annotation_fonts import annotation_font_requested_value_matches, annotation_font_native_normalizations
            require(annotation_font_requested_value_matches(response['font'], field, value), 'requested font value/mode differs')
            from swcli.document_annotation_fonts import ANNOTATION_FONT_MEMBERS
            require(response['native_normalizations'] == annotation_font_native_normalizations(before['native_font'], response['native_font'], ANNOTATION_FONT_MEMBERS[field]), 'font normalization evidence differs')
        elif profile == 'display':
            require(response['options'][field]['value'] == value
                    and all(response['options'][key] == before['options'][key] for key in before['options'] if key != field), 'display edit changed requested/unrelated field')
        else:
            require(response['standard']['value'] == value and payload(profile, response) == response['after'] == response['final'], 'standard final snapshot differs')
    return {'result': response, 'native_trace': proof}


def refuse(gate, trace, profile, document, before, field, value, error, *, stale=False, foreign=False, stamp=None):
    args = ['document', *arguments(profile, before, field, value, stale=stale), '--if-update-stamp',
            before['document']['update_stamp'] if stamp is None else stamp]
    if foreign:
        response = gate.command(*args, document=document, session=gate.session + '-contender',
                                lease=gate.leases[document], expected_error=error)
    else:
        response = gate.write(*args, document=document, expected_error=error)
    proof = trace.verify(gate, profile, rejected=True)
    if 'mutation' in response:
        require(response['mutation'] == {'attempted': False, 'may_have_changed': False}, 'refusal reached native mutation')
    unchanged = read(gate, trace, profile, document)
    require(payload(profile, unchanged) == payload(profile, before) and unchanged['document'] == before['document'], 'refused write changed document state')
    return {'result': response, 'native_trace': proof}


def targets(profile, initial):
    if profile == 'fonts':
        font = initial['font']
        return [(field, ('Arial' if font[field] != 'Arial' else 'Courier New') if field == 'typeface'
                 else (5.0 if font[field] != 5.0 else 4.0) if field == 'height_mm'
                 else (18 if font[field] != 18 else 16) if field == 'height_points'
                 else not font[field]) for field in ANNOTATION_FONT_WRITABLE_FIELDS]
    if profile == 'display':
        result = []
        for field, row in initial['options'].items():
            value = row['value']
            if DISPLAY_FIELDS[field]['kind'] == 'Toggle': target = not value
            elif field == 'grid.major_spacing_mm': target = 10.0 if value != 10.0 else 20.0
            elif field == 'grid.minor_lines_per_major': target = 10 if value != 10 else 5
            elif field == 'grid.snap_points_per_minor': target = 5 if value != 5 else 4
            elif field == 'virtual_sharp.style': target = 'none' if value != 'none' else 'plus'
            elif field == 'plane.transparency': target = 25 if value != 25 else 50
            else: target = 0x123456 if value != 0x123456 else 0x654321
            result.append((field, target))
        return result
    source = initial['standard']['value']
    require(source in ('ansi', 'iso', 'din', 'jis', 'bsi', 'gost', 'gb'),
            'finite standard gate requires a known named fixture standard')
    # CI templates can begin in ANSI/ISO rather than GB. Make the initial
    # known-source -> GB conversion an explicit public write in this plan,
    # using the same independently calibrated transition and full CAS.
    # No private fixture setter, automatic rollback or arbitrary transition.
    prefix = [(None, 'gb')] if source != 'gb' else []
    return prefix + [(None, target) for named in ('ansi', 'iso', 'din', 'jis', 'bsi', 'gost') for target in (named, 'gb')]


def roundtrip(gate, trace, profile, document, foreground, current, kind, suffix, index, geometry_before, retired, case):
    saved = support.save_copy(gate, document, 'changed-' + profile + '-' + str(index) + '.' + suffix, suffix)
    gate.close(document)
    gate.close(foreground)
    retired.add(document)
    opened, fresh, foreground = support.open_background(gate, saved['host_path'], kind, read_only=True)
    require(fresh not in retired, 'readonly reopen reused a retired public document ID')
    acquire(gate, fresh)
    observed = read(gate, trace, profile, fresh)
    require(payload(profile, observed) == payload(profile, current) and observed['document']['modified'] is False, 'changed preference snapshot did not persist')
    field, value = targets(profile, observed)[0] if profile != 'standards' else (None, 'ansi' if observed['standard']['value'] != 'ansi' else 'gb')
    refusal = refuse(gate, trace, profile, fresh, observed, field, value, 'ValueError')
    if kind == 1:
        measured = support.geometry(gate, fresh)
        support.same_geometry(geometry_before, measured)
        saved['reopened_geometry'] = measured
    require(hashlib.sha256(Path(saved['path']).read_bytes()).hexdigest() == saved['sha256'], 'readonly observation changed saved bytes')
    saved.update(reopen=opened, reopened=observed, read_only_refusal=refusal)
    case['saved_copies'].append(saved)
    gate.close(fresh)
    gate.close(foreground)
    retired.add(fresh)
    opened, writable, foreground = support.open_background(gate, saved['host_path'], kind)
    require(writable not in retired, 'writable reopen reused a retired public document ID')
    acquire(gate, writable)
    current = read(gate, trace, profile, writable)
    require(payload(profile, current) == payload(profile, observed) and current['document']['modified'] is False, 'writable continuation changed preferences or clean state')
    return writable, foreground, current


def run(gate, fixtures, trace, profile, *, host_fixtures=None, kinds=KINDS, contract_probe=None):
    require(kinds and len(set(kinds)) == len(kinds) and all(item in KINDS for item in kinds),
            'finite unique document kinds required')
    sources = [(suffix, kind, fixtures / ('annotations.' + suffix)) for suffix, kind in kinds]
    require(all(path.is_file() for _, _, path in sources), 'three prepared native inputs are required')
    gate.record.update(profile='document-preferences-' + profile, state='running', success=False,
                       preference_cases=[], evidence_kind='installed-public-cli-gate', covers_full_modeling_suite=False,
                       expected_version=__version__)
    health = gate.health()
    gate.record['host'] = host = health['host']
    require(health.get('server_version') == __version__ and host.get('owned_by_daemon') is True
            and host.get('visible') is False and host.get('shared_interactive') is False, 'gate requires an owned hidden daemon of the installed version')
    gate.require_empty()
    for suffix, kind, source in sources:
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        host_path = str(PureWindowsPath(host_fixtures) / source.name) if host_fixtures else str(source)
        opened, document, foreground = support.open_background(gate, host_path, kind)
        acquire(gate, document)
        current = initial = read(gate, trace, profile, document, session=gate.session + '-reader')
        case = {'format': suffix, 'document_type': kind, 'open': opened, 'source_sha256': digest,
                'initial': initial, 'writes': [], 'same_values': [], 'clean_same_values': [], 'value_refusals': [], 'saved_copies': [], 'success': False}
        gate.record['preference_cases'].append(case)
        geometry_before = support.geometry(gate, document) if kind == 1 else None
        if geometry_before is not None: case['geometry_initial'] = geometry_before
        if contract_probe is not None:
            contract_probe(gate, trace, profile, document, initial)
        plan = targets(profile, initial)
        case['planned_targets'] = plan
        first_field, first_value = plan[0]
        case['lease_refusal'] = refuse(gate, trace, profile, document, current, first_field, first_value, 'DocumentLeaseConflict', foreign=True)
        case['stamp_refusal'] = refuse(gate, trace, profile, document, current, first_field, first_value, 'DocumentUpdateConflict', stamp=current['document']['update_stamp'] + 1)
        retired = set()
        for index, (field, value) in enumerate(plan, 1):
            case['value_refusals'].append(refuse(gate, trace, profile, document, current, field, value, CONFLICTS[profile], stale=True))
            row = edit(gate, trace, profile, document, current, field, value, changed=True)
            case['writes'].append(row)
            current = row['result']
            case['same_values'].append(edit(gate, trace, profile, document, current, field, value, changed=False))
            # Each font height mode and each standard transition gets its own
            # saved/readonly proof. Display preserves all applicable fields.
            if profile in ('fonts', 'standards') or index == len(plan):
                document, foreground, current = roundtrip(gate, trace, profile, document, foreground, current,
                                                          kind, suffix, index, geometry_before, retired, case)
                case['clean_same_values'].append(edit(gate, trace, profile, document, current, field, value, changed=False))
            gate.checkpoint(profile + '-' + suffix + '-field-' + str(index))
        gate.close(document)
        gate.close(foreground)
        require(hashlib.sha256(source.read_bytes()).hexdigest() == digest, 'public gate modified the fixture input')
        require(all(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256'] for row in case['saved_copies']), 'a saved native output changed after verification')
        gate.require_empty(after_case=profile + '-' + suffix)
        case['success'] = True
        gate.checkpoint(profile + '-' + suffix + '-verified')
    gate.record['host_after'] = gate.health()['host']
    require(gate.record['host_after'] == host, 'gate replaced its owned host')
    gate.record.update(state='completed', success=True, elapsed_seconds=time.monotonic() - gate.group_started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=tuple(READS), required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--fixture-dir', required=True, type=Path)
    parser.add_argument('--native-trace', required=True, type=Path)
    parser.add_argument('--endpoint', default=os.environ.get('SWCLI_ENDPOINT', support.modeling.DEFAULT_ENDPOINT))
    parser.add_argument('--host-fixture-dir', type=support.modeling.host_directory)
    parser.add_argument('--host-output-dir', type=support.modeling.host_directory)
    parser.add_argument('--cli-command', type=support.modeling.executable)
    args = parser.parse_args(argv)
    require(args.native_trace.is_file(), 'trace-enabled daemon stderr is required')
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    gate = support.AnnotationSmoke(directory=directory, host_directory=args.host_output_dir or str(directory),
                                   cli=[args.cli_command] if args.cli_command else None, endpoint=args.endpoint)
    gate.record_path = directory / ('document-preferences-' + args.profile + '.json')
    with gate.record_path.open('x', encoding='utf-8') as stream: json.dump(gate.record, stream)
    trace = PreferenceTrace(args.native_trace)
    try:
        run(gate, args.fixture_dir, trace, args.profile, host_fixtures=args.host_fixture_dir)
    except BaseException as exc:
        gate.record.update(state='failed', success=False, error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        gate.cleanup()
        if gate.record['cleanup_errors'] or gate.checkpoint_error is not None: gate.record.update(state='failed', success=False)
        try: gate.record['native_trace_snapshot'] = trace.snapshot()
        except Exception as exc:
            gate.record.update(state='failed', success=False)
            gate.checkpoint_error = gate.checkpoint_error or exc
        gate.checkpoint('document-preferences-final')
    if gate.checkpoint_error is not None: raise gate.checkpoint_error
    require(not gate.record['cleanup_errors'], 'public document preference cleanup failed')


if __name__ == '__main__':
    main()
