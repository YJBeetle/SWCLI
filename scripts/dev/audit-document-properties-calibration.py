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
    required = {'report.json', 'trace.jsonl', 'context.json', 'standards-36/report.json',
                'standards-36/trace.jsonl', 'standards-36-driver/driver.json'}
    checked(required <= listed, 'mandatory original evidence missing')
    context = load_json(root / 'context.json')
    checked(context['source_head'] == expected_head and context['run_id'] == manifest['run_id']
            and context['run_attempt'] == manifest['run_attempt'], 'context/run/head mismatch')
    harness = load_json(root / 'report.json')
    report = load_json(root / 'standards-36/report.json')
    driver = load_json(root / 'standards-36-driver/driver.json')
    checked(report['script_sha256'] == manifest['sources'][SOURCES[0]], 'report/calibrator source hash mismatch')
    worker_pid = driver['child_python_pid']
    checked(type(worker_pid) is int and worker_pid > 0
            and report['python_process_id'] == worker_pid == driver['worker_identity']['pid'],
            'authorized worker/report PID mismatch')
    trace = trace_summary(root / 'standards-36/trace.jsonl')
    spec = importlib.util.spec_from_file_location('_docprops_offline_complete_check', ROOT / SOURCES[2])
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    coverage_error = None
    try:
        transitions = verifier.verify_complete_report(report, driver, harness['host']['process_id'])
        checked(harness['success'] is True and harness['cleanup_errors'] == [], 'owned harness/cleanup failed')
        owner = harness['cases'][0]['owned_interface']
        checked(owner['marshaled'] is True and owner['released'] is True, 'owned marshal table cleanup incomplete')
        parent_phases = {}
        for line in (root / 'trace.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            parent_phases.setdefault(row['call'], []).append(row['phase'])
        for label in ('owned-interface.CoReleaseMarshalData', 'ExitApp', 'WaitForOwnedProcess', 'CloseProcessHandle', 'CoUninitialize'):
            checked(parent_phases.get(label) == ['begin', 'end'], 'owned cleanup trace incomplete: ' + label)
        checked(not trace['error_records'] and trace['unfinished_call'] is None, 'trace incomplete or failed')
        checked(trace['categories'].get('standard_setter', {}).get('calls') == 36, 'trace does not prove 36 single setters')
        checked(trace['categories'].get('fixed_profile_reader', {}).get('calls') == 216,
                'trace does not prove all 216 initial/before/after/final/saved/readonly/continuation profiles')
        checked(type(driver['elapsed_seconds']) in (int, float) and 0 <= driver['elapsed_seconds'] < 1800,
                'driver group budget exceeded')
        complete = True
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
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
            'first_failure': report.get('first_call_failure') or report.get('failure') or trace['first_error']
                             or driver.get('failure') or harness.get('failure'),
            'driver_elapsed_seconds': driver.get('elapsed_seconds'), 'trace': trace,
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
