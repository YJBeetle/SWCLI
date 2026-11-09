"""Independent audit of original internal table-default calibration evidence."""

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

from swcli.document_tables import TABLE_FIELDS, validate_table_options
from swcli.result_schemas import validate_operation_result


geometry_spec = importlib.util.spec_from_file_location('_table_evidence_geometry', Path(__file__).with_name('table_defaults_geometry.py'))
geometry = importlib.util.module_from_spec(geometry_spec)
geometry_spec.loader.exec_module(geometry)


def require(condition, message):
    if not condition:
        raise ValueError('table internal evidence: ' + message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(directory, native_trace, *, report_sha256):
    directory, native_trace = Path(directory), Path(native_trace)
    report_path = directory / 'report.json'
    require(sha256(report_path) == report_sha256, 'report SHA256 mismatch')
    report = json.loads(report_path.read_text())
    require(report.get('success') is True and not report.get('cleanup_errors')
            and report.get('diagnostic_case') == 'document-table-defaults-internal'
            and report.get('full_acceptance_eligible') is False, 'not a clean internal candidate run')
    revision = report['host']['revision']
    require(type(revision) is str and revision and type(report['host']['process_id']) is int, 'host identity unavailable')
    cases = report['cases']
    requested = report.get('requested_document_types', [1, 2, 3])
    require(type(requested) is list and requested and all(type(kind) is int for kind in requested)
            and requested == sorted(set(requested)) and set(requested) <= {1, 2, 3}, 'invalid explicit document-type plan')
    require([case['document_type'] for case in cases] == requested, 'document-type plan incomplete')
    profiles, artifacts, setter_count, getter_count = {}, [], 0, 0
    for case in cases:
        kind = case['document_type']
        suffix = {1: 'SLDPRT', 2: 'SLDASM', 3: 'SLDDRW'}[kind]
        require(case.get('success') is True and case.get('internal_calibration_only') is True
                and case.get('preparation_only') is False, 'case is not completed internal write calibration')
        fields = [field for field, spec in TABLE_FIELDS.items() if kind in spec['types']]
        require(len(case['writes']) == len(case['noops']) == len(case['conflicts']) == len(fields), 'field plan incomplete')
        current = validate_table_options(case['original']['options'])
        require(case['original']['ok'] is True, 'original public read failed')
        for field, spec in TABLE_FIELDS.items():
            require(('unavailable' in current[field]) == (kind not in spec['types']), 'field applicability mismatch')
        gate = case['public_write_gate']
        require(gate['ok'] is False and gate['error']['type'] == 'DocumentTableCalibrationRequired'
                and gate['mutation'] == dict(attempted=False, may_have_changed=False), 'candidate public gate was not closed')
        profile = {}
        for field, changed, noop, conflict in zip(fields, case['writes'], case['noops'], case['conflicts']):
            validate_operation_result('document.table-option-set', changed)
            validate_operation_result('document.table-option-set', noop)
            validate_operation_result('document.table-option-set', conflict)
            require(changed['ok'] is True and changed['field'] == field and changed['before'] == current
                    and changed['changed'] is True and changed.get('native_returned') is True
                    and changed['mutation'] == dict(attempted=True, may_have_changed=True), 'write chain or native receipt mismatch')
            require(all(current[key] == changed['options'][key] for key in TABLE_FIELDS if key != field), 'collateral scalar changed')
            current = changed['options']
            require(noop['ok'] is True and noop['changed'] is False and noop['options'] == current
                    and noop['mutation'] == dict(attempted=False, may_have_changed=False), 'no-op mutated the document')
            require(conflict['ok'] is False and conflict['error']['type'] == 'DocumentTableConflict'
                    and conflict['mutation'] == dict(attempted=False, may_have_changed=False), 'full snapshot conflict mutated the document')
            raw_before, raw_after = changed['before'][field]['native_value'], current[field]['native_value']
            profile[field] = [[raw_before, raw_after], [raw_after, raw_after]]
        if kind == 1:
            checks = case.get('geometry_checks', [])
            require([row['field'] for row in checks] == ['fixture-readonly-reopen', 'before-first-table-write'] + fields + ['saved-reopen'],
                    'missing table part geometry operands')
            measured = case.get('geometry_before_table_write_measurement', {})
            require(case.get('geometry_before_table_write_context_unchanged') is True and measured.get('ok') is True
                    and geometry.compare_table_geometry(case['geometry_reopened'], measured['metrics'])['passed'],
                    'part pre-write measurement/context did not match the readonly baseline')
            for row in checks:
                comparison = geometry.compare_table_geometry(row['before'], row['after'])
                require(comparison['passed'] and {key: row.get(key) for key in comparison} == comparison,
                        'table part geometry comparison/record failed')
                baseline = case['geometry'] if row['field'] == 'fixture-readonly-reopen' else case['geometry_reopened']
                require(row['before'] == baseline, 'table part geometry baseline differs')
            require(checks[0]['after'] == case['geometry_reopened'] and checks[1]['after'] == measured['metrics'],
                    'table part initial geometry observations differ')
        require(current == case['final_options'] == case['persisted']['options'] and case['persisted']['ok'] is True,
                'saved/reopened scalar values differ')
        require(case['save_defaults']['ok'] is True and case['save_defaults']['api_saved'] is True
                and case['save_defaults']['save_errors'] == 0 and case['save_defaults']['save_warnings'] is None, 'native save was not clean')
        require(case['readonly_rejection']['ok'] is False
                and case['readonly_rejection']['mutation'] == dict(attempted=False, may_have_changed=False), 'readonly mutation was not refused')
        for name, digest in (('annotations.' + suffix, case['file_sha256']), ('table-defaults.' + suffix, case['persisted_sha256'])):
            path = directory / name
            require(path.is_file() and path.stat().st_size >= 512 and sha256(path) == digest, 'original/saved fixture hash mismatch: ' + name)
            artifacts.append(dict(name=name, sha256=digest, size_bytes=path.stat().st_size))
        profiles[str(kind)] = profile
        setter_count += len(fields)
        getter_count += 2 * len(fields) + 5 * len(fields) ** 2
    stages = [json.loads(line) for line in (directory / 'trace.jsonl').read_text().splitlines()]
    require(len(stages) % 2 == 0, 'incomplete owned-harness call trace')
    maximum = 0
    for begin, end in zip(stages[::2], stages[1::2]):
        require(begin['phase'] == 'begin' and end['phase'] == 'end' and begin['call'] == end['call'], 'harness call failed or reordered')
        elapsed = end['time'] - begin['time']
        require(0 <= elapsed <= 600, 'native stage exceeded its 600-second bound')
        maximum = max(maximum, elapsed)
    require(stages[-1]['time'] - stages[0]['time'] <= 1800, 'internal group exceeded 1800 seconds')
    counts = Counter(row['call'] for row in stages if row['phase'] == 'begin')
    require(counts['acquire-owned-host'] == counts['ExitApp'] == counts['WaitForOwnedProcess'] == 1, 'owned host lifecycle was restarted/incomplete')
    records = []
    for line in native_trace.read_text(encoding='utf-8-sig').splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            require('swcli.native-call' not in line, 'malformed original native trace')
            continue
        if isinstance(row, dict) and row.get('event') == 'swcli.native-call':
            records.append(row)
    require(records and records[0]['sequence'] == records[-1]['sequence'] == 0
            and records[0]['phase'] == 'begin' and records[-1]['phase'] == 'end', 'internal native operation boundary incomplete')
    require(all(row['request_id'] == 'table-defaults-calibration' and row['operation'] == 'internal.table-defaults'
                and row['worker_pid'] == records[0]['worker_pid'] for row in records), 'internal trace ownership changed')
    begins = Counter((row['sequence'], row['call']) for row in records if row['phase'] == 'begin')
    ends = Counter((row['sequence'], row['call']) for row in records if row['phase'] == 'end')
    require(begins == ends and all(count == 1 for count in begins.values())
            and not any(row['phase'] == 'error' for row in records), 'native call boundaries missing/repeated/failed')
    stack = []
    sequence = 0
    for row in records:
        if row['phase'] == 'begin':
            require(row['sequence'] == sequence, 'native begin sequence mismatch')
            sequence += 1
            stack.append(row)
        else:
            require(stack and (stack[-1]['sequence'], stack[-1]['call']) == (row['sequence'], row['call']),
                    'native nested call order mismatch')
            stack.pop()
    require(not stack, 'native calls did not all terminate')
    methods = Counter(row['call'] for row in records if row['phase'] == 'begin')
    require(sum(count for name, count in methods.items() if name.startswith('IModelDocExtension.SetUserPreference')) == setter_count,
            'native setters were repeated or omitted')
    require(sum(count for name, count in methods.items() if name.startswith('IModelDocExtension.GetUserPreference')) == getter_count,
            'native getters were repeated or omitted')
    # The baseline analytic-box fixture temporarily disables/restores sketch
    # inference before the first table operation. This is not a table write.
    first_table = next(index for index, row in enumerate(records) if row['phase'] == 'begin'
                       and row['call'] in ('GetExecutablePath', 'ISldWorks.GetExecutablePath'))
    global_calls = [(index, row['call']) for index, row in enumerate(records) if row['phase'] == 'begin'
                    and row['call'].startswith(('ISldWorks.SetUserPreference', 'SldWorks.SetUserPreference'))]
    require(all(index < first_table and name == 'SldWorks.SetUserPreferenceToggle(swSketchInference)'
                for index, name in global_calls) and len(global_calls) in ((0, 2) if 1 in requested else (0,)),
            'global preference setter occurred outside owned analytic fixture preparation')
    return dict(success=True, revision=revision, document_types=requested, profiles=profiles, report_sha256=report_sha256,
                harness_trace_sha256=sha256(directory / 'trace.jsonl'), native_trace_sha256=sha256(native_trace),
                native_setter_calls=setter_count, native_getter_calls=getter_count, maximum_native_stage_seconds=maximum,
                artifacts=artifacts, evidence_kind='independent-internal-artifact-audit', full_acceptance_eligible=False)
