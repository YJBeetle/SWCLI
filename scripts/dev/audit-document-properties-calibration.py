"""Offline hash/coverage/timing audit of one owned calibration artifact.

Never executes CAD or changes a transition whitelist. Even complete internal
calibration remains full_acceptance_eligible=False. Put --output outside raw
--artifact-root so the downloaded originals remain byte-for-byte intact.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('scripts/dev/calibrate-document-properties.py',
           'scripts/dev/run-document-properties-calibration.py',
           'scripts/ci/verify-document-properties-calibration.py',
           'scripts/ci/verify-through-all-calibration.py')


def checked(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def trace_summary(path):
    active = None
    totals = {}
    begins = errors = terminals = 0
    first_error = None
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        row = json.loads(line)
        label, phase = row['call'], row['phase']
        checked(type(label) is str and label, f'invalid trace label at {number}')
        if phase == 'begin':
            checked(active is None, f'overlapping trace begin at {number}')
            active = label
            begins += 1
            continue
        checked(phase in ('end', 'error') and active == label, f'unpaired trace terminal at {number}')
        active = None
        terminals += 1
        if phase == 'error':
            errors += 1
            if first_error is None:
                first_error = row
        elapsed = row['elapsed_seconds']
        checked(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
                f'invalid wrapper timing at {number}')
        if phase == 'end':
            checked(elapsed < 600, f'success terminal exceeds unchanged budget at {number}')
        category = ('identity' if label == 'ISldWorks.IsSame' else
                    'standard_setter' if '.SetUserPreferenceInteger.once' in label else
                    'fixed_profile_reader' if '.fixed-observed-defaults-reader' in label else 'other_guards_and_io')
        total = totals.setdefault(category, {'calls': 0, 'wrapper_seconds': 0.0,
                                            'begin_trace_seconds': 0.0, 'checkpoint_seconds': 0.0,
                                            'function_body_seconds': 0.0, 'pre_native_failures': 0})
        total['calls'] += 1
        total['wrapper_seconds'] += elapsed
        for key in ('begin_trace_seconds', 'checkpoint_seconds', 'native_seconds'):
            value = row[key]
            if key == 'native_seconds' and value is None:
                checked(row['native_started'] is False, 'missing started function timing')
                total['pre_native_failures'] += 1
                continue
            checked(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                    f'invalid {key} at {number}')
            total['function_body_seconds' if key == 'native_seconds' else key] += value
        checked(type(row['native_started']) is bool and type(row['native_completed']) is bool,
                'invalid native timing state')
        if phase == 'end':
            checked(row['native_started'] and row['native_completed'], 'successful terminal without native completion')
    return {'begin_records': begins, 'terminal_records': terminals, 'error_records': errors,
            'unfinished_call': active, 'first_error': first_error, 'categories': totals,
            'scope': 'completed wrappers only; wrapper excludes terminal fsync; function body may contain multiple COM leaves'}


def fixed_reader_cycle(kind):
    import sys
    source = str(ROOT / 'src')
    if source not in sys.path:
        sys.path.insert(0, source)
    from swcli.document_annotation_fonts import ANNOTATION_FONT_MEMBERS
    from swcli.document_annotations import ANNOTATION_FIELDS
    from swcli.document_display_options import display_fields_for_document
    return (['IModelDocExtension.GetUserPreferenceInteger']
            + ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in ANNOTATION_FIELDS.values()]
            + ['IModelDocExtension.GetUserPreferenceTextFormat']
            + ['ITextFormat.' + member + ('' if member == 'IsHeightSpecifiedInPts' else '.get')
               for member in ANNOTATION_FONT_MEMBERS.values()]
            + ['IModelDoc2.GetUnits']
            + ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in display_fields_for_document(kind).values()]
            + ['IModelDocExtension.GetUserPreferenceInteger'] * 4)


def sdk_trace_summary(path, report, worker_pid):
    expected = {}
    prefix = report['prefix']
    for label, row in report['standard_reads'].items():
        expected[prefix + '-' + label] = ('diagnostic.document-drafting-standard-snapshot',
                                         fixed_reader_cycle(row['snapshot']['observed_defaults']['document_type']))
    for case in report['cases']:
        for row in case['writes']:
            if row.get('native_setter_calls') == 0:
                continue
            label = case['kind'] + '.standard-' + str(row['plan_index']) + '-' + row['source_name'] + '-to-' + row['target_name']
            expected[prefix + '-' + label] = ('diagnostic.document-drafting-standard-set',
                                              ['IModelDocExtension.SetUserPreferenceInteger'])
    requests = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            checked('"swcli.native-call"' not in line, 'malformed SDK native trace')
            continue
        if type(row) is dict and row.get('event') == 'swcli.native-call':
            requests.setdefault(row['request_id'], []).append(row)
    checked(set(requests) == set(expected), 'SDK request IDs differ from complete report observations/setters')
    setters = readers = leaves = 0
    for request, rows in requests.items():
        operation, cycle = expected[request]
        checked(all(row.get('operation') == operation and row.get('worker_pid') == worker_pid for row in rows),
                'SDK operation/authorized worker changed')
        first, last = rows[0], rows[-1]
        checked(first.get('sequence') == last.get('sequence') == 0 and first.get('phase') == 'begin'
                and last.get('phase') == 'end' and first.get('call') == last.get('call') == operation,
                'SDK request incomplete, failed or duplicated')
        checked(type(last.get('duration_ms')) in (int, float) and math.isfinite(last['duration_ms'])
                and 0 <= last['duration_ms'] < 600000, 'SDK request budget exceeded')
        calls = rows[1:-1]
        checked(len(calls) % 2 == 0, 'SDK call pair incomplete')
        begins = []
        for sequence, (begin, end) in enumerate(zip(calls[::2], calls[1::2]), 1):
            checked(begin.get('sequence') == end.get('sequence') == sequence and begin.get('phase') == 'begin'
                    and end.get('phase') == 'end' and begin.get('call') == end.get('call'),
                    'SDK call order/error/repetition differs')
            checked(type(end.get('duration_ms')) in (int, float) and math.isfinite(end['duration_ms'])
                    and 0 <= end['duration_ms'] < 600000, 'SDK native call budget exceeded')
            begins.append(begin['call'])
        tracked = [name for name in begins if name.startswith(('IModelDocExtension.GetUserPreference',
                   'IModelDocExtension.SetUserPreference', 'ITextFormat.')) or name in ('IModelDoc2.GetUnits', 'IModelDoc2.SetSaveFlag')]
        checked(tracked == cycle, 'SDK fixed getter cycle or single setter differs')
        checked(not any(name.startswith('ISldWorks.SetUserPreference') for name in begins), 'SDK trace reached global preference setter')
        setters += operation == 'diagnostic.document-drafting-standard-set'
        readers += operation == 'diagnostic.document-drafting-standard-snapshot'
        leaves += len(begins)
    return {'reader_requests': readers, 'single_setter_requests': setters, 'native_call_pairs': leaves,
            'authorized_worker_pid': worker_pid, 'error_records': 0, 'repeated_setters': 0,
            'scope': 'flat SDK leaf boundaries, complete fixed getter cycles and exactly one setter per transition'}


def audit(artifact_root, expected_head, source_root=None):
    root = artifact_root.resolve()
    checked(re.fullmatch('[0-9a-f]{40}', expected_head or '') is not None, 'exact expected head required')
    manifest = load_json(root / 'manifest.json')
    checked(manifest['source_head'] == expected_head, 'manifest source head differs')
    checked(manifest['full_acceptance_eligible'] is False, 'unexpected acceptance scope')
    checked(manifest['native_timeout_seconds'] == 600 and manifest['group_timeout_seconds'] == 1800,
            'manifest budgets changed')
    listed = set()
    for row in manifest['files']:
        relative = row['path']
        path = (root / relative).resolve()
        checked(type(relative) is str and relative not in listed and root in path.parents
                and not (root / relative).is_symlink(), 'duplicate/unsafe manifest path')
        checked(path.is_file() and path.stat().st_size == row['bytes'] and digest(path) == row['sha256'],
                'original hash/size differs: ' + relative)
        listed.add(relative)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root / 'manifest.json'}
    checked(actual == listed, 'artifact files differ from original manifest')
    checked(set(manifest['sources']) == set(SOURCES), 'source hash catalog changed')
    source_byte_forms = {}
    if source_root is not None:
        for relative in SOURCES:
            expected = (source_root / relative).read_bytes()
            # Git may check out text as LF or CRLF on Windows. Compare explicit
            # expected byte hashes; never normalize original artifact bytes.
            lf = expected.replace(b'\r\n', b'\n')
            forms = {'exact': expected, 'git-LF': lf, 'git-CRLF': lf.replace(b'\n', b'\r\n')}
            matching = [name for name, data in forms.items()
                        if hashlib.sha256(data).hexdigest() == manifest['sources'][relative]]
            checked(matching, 'source bytes differ: ' + relative)
            source_byte_forms[relative] = matching[0]
    required = {'report.json', 'trace.jsonl', 'context.json'}
    checked(required <= listed, 'mandatory original evidence missing')
    context = load_json(root / 'context.json')
    checked(context['source_head'] == expected_head and context['run_id'] == manifest['run_id']
            and context['run_attempt'] == manifest['run_attempt'], 'context/run/head mismatch')
    harness = load_json(root / 'report.json')
    spec = importlib.util.spec_from_file_location('_docprops_offline_complete_check', ROOT / SOURCES[2])
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    preparation = None
    report = driver = {}
    trace = sdk_trace = None
    coverage_error = None
    transitions = None
    active_group = 'standards-prepare' if context.get('fixture_preparation_required') is True else 'standards-36'

    def read_group(name):
        report = load_json(root / name / 'report.json')
        driver = load_json(root / (name + '-driver') / 'driver.json')
        checked(report['script_sha256'] == manifest['sources'][SOURCES[0]], 'report/calibrator source hash mismatch')
        worker_pid = driver['child_python_pid']
        checked(type(worker_pid) is int and worker_pid > 0
                and report['python_process_id'] == worker_pid == driver['worker_identity']['pid'],
                'authorized worker/report PID mismatch')
        return report, driver, trace_summary(root / name / 'trace.jsonl'), worker_pid

    def verify_trace(name, report, driver, trace, worker_pid, setters, readers):
        checked(not trace['error_records'] and trace['unfinished_call'] is None, 'trace incomplete or failed')
        checked(trace['categories'].get('standard_setter', {}).get('calls', 0) == setters,
                'trace single setter count differs')
        checked(trace['categories'].get('fixed_profile_reader', {}).get('calls', 0) == readers,
                'trace fixed profile count differs')
        checked(type(driver['elapsed_seconds']) in (int, float) and 0 <= driver['elapsed_seconds'] < 1800,
                'driver group budget exceeded')
        sdk = sdk_trace_summary(root / (name + '-driver') / 'stderr.log', report, worker_pid)
        checked(sdk['reader_requests'] == readers and sdk['single_setter_requests'] == setters,
                'SDK trace does not prove full fixed profile / single setter coverage')
        return sdk

    try:
        if active_group == 'standards-prepare':
            report, driver, trace, worker_pid = read_group(active_group)
            inputs, setters = verifier.verify_prepared_report(report, driver, harness['host']['process_id'])
            readers = sum(6 if case['writes'][0]['native_setter_calls'] == 1 else 3 for case in report['cases'])
            prep_sdk = verify_trace(active_group, report, driver, trace, worker_pid, setters, readers)
            prepared = load_json(root / 'prepared-inputs.json')
            checked(prepared == {'format': 'owned-prepared-gb-v1', 'attach_pid': harness['host']['process_id'],
                                  'script_sha256': report['script_sha256'], 'inputs': inputs},
                    'prepared manifest identity/source/profile differs')
            from pathlib import PureWindowsPath
            output = PureWindowsPath(driver['output'])
            for item in inputs.values():
                relative = PureWindowsPath(item['path']).relative_to(output)
                path = root / 'standards-prepare' / Path(*relative.parts)
                checked(path.is_file() and digest(path) == item['sha256'], 'prepared native bytes differ')
            preparation = {'complete': True, 'setter_requests': setters, 'profile_reads': readers,
                           'driver_elapsed_seconds': driver['elapsed_seconds'], 'trace': trace, 'sdk_trace': prep_sdk}
            active_group = 'standards-36'
        report, driver, trace, worker_pid = read_group('standards-36')
        transitions = verifier.verify_complete_report(report, driver, harness['host']['process_id'])
        if preparation is not None:
            for case in report['cases']:
                item = prepared['inputs'][case['kind']]
                checked(case.get('prepared_input') == item
                        and json.dumps(case['standard_initial'], sort_keys=True, allow_nan=False)
                        == json.dumps(item['profile'], sort_keys=True, allow_nan=False),
                        'standard group prepared input/profile lineage differs')
        checked(harness['success'] is True and harness['cleanup_errors'] == [], 'owned harness/cleanup failed')
        owner = harness['cases'][0]['owned_interface']
        checked(owner['marshaled'] is True and owner['released'] is True, 'owned marshal table cleanup incomplete')
        parent_phases = {}
        for line in (root / 'trace.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            parent_phases.setdefault(row['call'], []).append(row['phase'])
        for label in ('owned-interface.CoReleaseMarshalData', 'ExitApp', 'WaitForOwnedProcess', 'CloseProcessHandle', 'CoUninitialize'):
            checked(parent_phases.get(label) == ['begin', 'end'], 'owned cleanup trace incomplete: ' + label)
        sdk_trace = verify_trace('standards-36', report, driver, trace, worker_pid, 36, 216)
        complete = True
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        complete, transitions, coverage_error = False, None, str(error)
    counts = {}
    for case in report.get('cases', []):
        rows = case.get('writes', [])
        counts[case['kind']] = {
            'setter_attempts': sum(row.get('native_setter_calls', 0) for row in rows),
            'strict_true_returns': sum(row.get('native_return') is True for row in rows),
            'complete_saved_readonly_transitions': sum(row.get('success') is True and bool(row.get('saved'))
                                                     and 'readonly_profile' in row for row in rows),
        }
    return {'audit_success': True, 'auditor_sha256': digest(Path(__file__)), 'all_original_hashes_verified': True, 'source_head': expected_head,
            'run_id': manifest['run_id'], 'run_attempt': manifest['run_attempt'], 'source_hashes': manifest['sources'],
            'source_byte_forms_verified_locally': source_byte_forms,
            'manifest_sha256': digest(root / 'manifest.json'), 'native_group_complete': complete,
            'completed_transitions': transitions, 'per_kind': counts, 'coverage_error': coverage_error,
            'first_failure': report.get('first_call_failure') or report.get('failure') or (trace or {}).get('first_error')
                             or driver.get('failure') or harness.get('failure') or coverage_error,
            'active_group_at_conclusion': active_group, 'fixture_preparation': preparation,
            'driver_elapsed_seconds': driver.get('elapsed_seconds'), 'trace': trace, 'sdk_trace': sdk_trace,
            'full_acceptance_eligible': False, 'public_whitelist_updates': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-root', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checked(args.artifact_root.resolve() not in args.output.resolve().parents, 'output must be outside raw artifact')
    try:
        result = audit(args.artifact_root, args.expected_head, args.source_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'audit_success': False, 'native_group_complete': False, 'full_acceptance_eligible': False,
                  'first_failure': {'type': type(error).__name__, 'message': str(error)}, 'public_whitelist_updates': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['audit_success'] and result['native_group_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
