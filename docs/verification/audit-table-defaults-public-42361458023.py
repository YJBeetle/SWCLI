"""Offline audit of the exact public 42361458023 ZIP and pinned internal inputs."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import subprocess
import sys
import tempfile
import zipfile

PUBLIC = dict(run=42361458023, head='c95ecdefa40689b2c8723a2e85998bbde2b6633f',
              artifact=13569274991, name='table-defaults-public-42361458023-1',
              digest='f1877623dfc909900ba9784644e4266809d67afd68dd109feee49f42c82e66ad')
INTERNAL = dict(run=42301331238, head='50db73af937cd78aa9adcd8c4bfdd5467c956533',
                artifact=13545815581, name='table-defaults-internal-42301331238-1',
                digest='7e473478064998f3e116329d29007f8f21c441be74d7827a7d3bfbc90fc2f4f6')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def extract_original(evidence, pinned, output):
    run, artifact = load(evidence / 'run.json'), load(evidence / 'artifact.json')
    require((run['id'], run['head_sha'], run['head_branch'], run['event'], run['status'], run['conclusion']) ==
            (pinned['run'], pinned['head'], 'codex/docprops-table-defaults', 'workflow_dispatch', 'completed', 'success'),
            'run provenance mismatch')
    require((artifact['id'], artifact['name'], artifact['workflow_run']['id'], artifact['expired']) ==
            (pinned['artifact'], pinned['name'], pinned['run'], False), 'artifact provenance mismatch')
    original = evidence / 'original.zip'
    require(digest(original.read_bytes()) == pinned['digest'] and artifact['digest'] == 'sha256:' + pinned['digest'],
            'original ZIP digest differs from pinned official digest')
    with zipfile.ZipFile(original) as archive:
        names = set()
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            require(not path.is_absolute() and '..' not in path.parts and '\\' not in entry.filename
                    and not stat.S_ISLNK(entry.external_attr >> 16) and entry.filename not in names
                    and entry.file_size < 10_000_000, 'unsafe or duplicate original ZIP entry')
            names.add(entry.filename)
        archive.extractall(output)
    return output


def without_request_id(result):
    return {key: value for key, value in result.items() if key != 'request_id'}


def argument(command, name):
    return command[command.index(name) + 1]


def audit(source, public, internal):
    product = subprocess.run(['git', 'diff', '--exit-code', PUBLIC['head'], '--',
                              'src', 'scripts', '.github', 'tests', 'pyproject.toml'],
                             cwd=source, capture_output=True)
    require(product.returncode in (0, 1), 'cannot compare current product with audited head')
    subprocess.run(['git', 'diff', '--exit-code', PUBLIC['head'], '--',
                    'src/swcli/document_tables.py', 'src/swcli/document_table_profiles.py',
                    'src/swcli/result_schemas.py'], cwd=source, check=True, capture_output=True)
    sys.path.insert(0, str(source / 'src'))
    from swcli.document_tables import TABLE_FIELDS, validate_table_options
    from swcli.document_table_profiles import PROFILES, INTERNAL_PROOF
    from swcli.result_schemas import validate_operation_result

    report_path = public / 'public/gate/table-defaults-public.json'
    report = load(report_path)
    candidate_path = internal / 'calibration/report.json'
    candidate = load(candidate_path)
    require(report['state'] == 'completed' and report['success'] is True and not report['cleanup_errors']
            and report['evidence_kind'] == 'installed-public-cli-daemon-gate' and report['feature_acceptance_eligible'] is True,
            'public gate is incomplete')
    require(report['covers_full_modeling_suite'] is False and report['accepted_document_types'] == [2, 3], 'wrong accepted scope')
    require(candidate['success'] is True and candidate['requested_document_types'] == [2, 3]
            and all(case['success'] for case in candidate['cases']), 'incomplete pinned internal inputs')
    require(INTERNAL_PROOF['run_id'] == INTERNAL['run'] and INTERNAL_PROOF['head'] == INTERNAL['head']
            and INTERNAL_PROOF['artifact_digest'] == 'sha256:' + INTERNAL['digest']
            and digest(candidate_path.read_bytes()) == INTERNAL_PROOF['report_sha256'], 'internal input pin mismatch')
    require(report['internal_proof'] == dict(run=str(INTERNAL['run']), head=INTERNAL['head'],
            report_sha256=INTERNAL_PROOF['report_sha256']), 'public report references another internal run')
    require(digest((internal / 'calibration/trace.jsonl').read_bytes()) == INTERNAL_PROOF['harness_trace_sha256']
            and digest((internal / 'worker.native.stderr.jsonl').read_bytes()) == INTERNAL_PROOF['native_trace_sha256'],
            'internal trace hash mismatch')
    require(set(PROFILES) == {('33.5.0', 2), ('33.5.0', 3)}, 'runtime profile extends accepted document types')
    wrapper = load(public / 'public/wrapper-result.json')
    require(wrapper == dict(success=True, native_seconds=600, group_seconds=1800, daemon_exit_confirmed=True), 'wrapper did not confirm exit')
    stop = load(public / 'public/daemon-stop.json')
    require(stop['success'] is True and stop['result'] == {'stopping': True}, 'daemon stop failed')
    host = report['host']
    require(host == report['host_after'] and host['revision'] == '33.5.0' and host['platform'] == 'windows'
            and host['owned_by_daemon'] is True and host['shared_interactive'] is False and host['visible'] is False,
            'host identity or ownership changed')
    startup = [json.loads(line) for line in (public / 'public/daemon.stdout.jsonl').read_text().splitlines()]
    require(len(startup) == 2 and startup[0]['phase'] == 'host-acquired' and startup[0]['host']['process_id'] == host['process_id']
            and startup[1]['action'] == 'daemon.serve' and startup[1]['host'] == host, 'daemon restarted or startup differed')
    require(report['request_timeout_seconds'] == 600 and report['group_timeout_seconds'] == 1800
            and 0 < report['elapsed_seconds'] <= 1800, 'public request/group budget mismatch')

    # Rebuild request ownership and CLI results from the original event journal.
    events = report['events']
    journals = list((public / 'public/gate').glob('*events*.jsonl'))
    require(len(journals) == 1, 'event journal missing or duplicated')
    journal = [json.loads(line) for line in journals[0].read_text().splitlines()]
    require(len(journal) == 2 * len(events) == 240, 'CLI event plan incomplete')
    responses, commands, document_types, owned = {}, {}, {}, set()
    leases, stamps = {}, {}
    case_unrelated = {case['initial']['document']['document_id']: case['unrelated_cas_refusal'] for case in report['table_cases']}
    for index, event in enumerate(events):
        require(event['state'] == 'completed' and event['request_timeout_seconds'] == 600
                and json.loads(event['stdout']) == event['result'], 'CLI result differs from original stdout')
        start, end = journal[2 * index:2 * index + 2]
        require(start['event_index'] == end['event_index'] == index and start['state'] == 'running'
                and start['command'] == event['command']
                and {key: value for key, value in end.items() if key not in ('event_index', 'stage')} == event,
                'event journal differs from report or is reordered')
        raw = event['result']
        require(raw['request_id'] not in responses, 'request ID reused')
        commands[raw['request_id']] = event['command']
        require(argument(event['command'], '--endpoint') == report['endpoint'], 'CLI endpoint changed')
        result = raw.get('result', raw)
        responses[raw['request_id']] = without_request_id(result)
        successful = raw.get('success', result.get('ok'))
        require((event['returncode'] == 0) is successful, 'CLI exit code disagrees with result')
        action = result.get('action')
        if action == 'document.table-option-set':
            command = event['command']
            document_id = argument(command, '--document')
            expected = validate_table_options(json.loads(argument(command, '--if-options-json')))
            lease = leases[argument(command, '--lease')]
            require(lease['document_id'] == document_id, 'write lease targets another document')
            error = result.get('error', {}).get('type')
            same_session = argument(command, '--session') == lease['session_id']
            same_stamp = int(argument(command, '--if-update-stamp')) == stamps[document_id]
            require(same_session is (error != 'DocumentLeaseConflict')
                    and same_stamp is (error != 'DocumentUpdateConflict'), 'lease/stamp refusal request does not test its guard')
            if 'before' in result:
                differences = [field for field in TABLE_FIELDS if expected[field] != result['before'][field]]
                require((len(differences) == 1) if error == 'DocumentTableConflict' else not differences,
                        'complete CAS request differs from its claimed outcome')
                if without_request_id(result) == case_unrelated.get(document_id):
                    require(result['field'] not in differences, 'unrelated CAS tested the selected field')
        if 'document' in result:
            descriptor = result['document']
            document_types[descriptor['document_id']] = descriptor['type']
            stamps[descriptor['document_id']] = descriptor['update_stamp']
        if action in ('document.lease.acquire', 'document.lease.renew') and result['ok']:
            leases[result['lease']['lease_id']] = result['lease']
        if action in ('document.create', 'document.open') and result['ok']:
            require(descriptor['document_id'] not in owned, 'duplicate live handle')
            owned.add(descriptor['document_id'])
        if action == 'document.close' and result['ok']:
            require(result['closed'] is True and descriptor['document_id'] in owned, 'unexpected or repeated close')
            owned.remove(descriptor['document_id'])
    require(not owned and events[-2]['result']['count'] == 0 and events[-2]['result']['documents'] == [], 'owned documents remain open')
    for event in (events[0], events[-1]):
        status = event['result']['result']
        require(status['host'] == host and status['worker_alive'] is True and status['recovery_required'] is False, 'daemon required recovery')

    require([case['document_type'] for case in report['table_cases']] == [2, 3], 'public case plan incomplete')
    require([client['document_type'] for client in report['client_contracts']] == [2, 3], 'client contract plan incomplete')
    for client, case, baseline in zip(report['client_contracts'], report['table_cases'], candidate['cases']):
        kind = case['document_type']
        fields = [field for field, spec in TABLE_FIELDS.items() if kind in spec['types']]
        require(case['success'] is True and len(case['writes']) == len(case['noops']) == len(case['conflicts']) == len(fields), 'field plan incomplete')
        suffix = {2: 'SLDASM', 3: 'SLDDRW'}[kind]
        original = internal / ('calibration/annotations.' + suffix)
        require(digest(original.read_bytes()) == case['source_sha256'] == baseline['file_sha256'], 'source fixture hash mismatch')
        current = case['initial']['options']
        require(current == baseline['original']['options'] and case['initial']['document']['modified'] is False, 'initial options or dirty state differ')
        for name, expected_error in (('lease_refusal', 'DocumentLeaseConflict'), ('stamp_refusal', 'DocumentUpdateConflict'),
                                     ('unrelated_cas_refusal', 'DocumentTableConflict'), ('readonly_refusal', 'ValueError')):
            refusal = case[name]
            require(refusal['ok'] is False and refusal['error']['type'] == expected_error
                    and refusal.get('mutation', {'attempted': False, 'may_have_changed': False}) == {'attempted': False, 'may_have_changed': False}, 'refusal mutated or returned wrong error')
        for field, write, noop, conflict in zip(fields, case['writes'], case['noops'], case['conflicts']):
            require(write['field'] == field and write['before'] == current and write['changed'] is True
                    and write['native_returned'] is True and write['mutation'] == {'attempted': True, 'may_have_changed': True}
                    and write['options'][field] == baseline['final_options'][field]
                    and all(write['options'][key] == current[key] for key in TABLE_FIELDS if key != field), 'changed-value write chain differs')
            require((current[field]['native_value'], write['options'][field]['native_value']) in PROFILES[('33.5.0', kind)][field], 'unproved raw transition')
            current = write['options']
            require(noop['changed'] is False and noop['options'] == current and noop['document'] == write['document']
                    and noop['mutation'] == {'attempted': False, 'may_have_changed': False}, 'no-op changed options/state')
            require(conflict['ok'] is False and conflict['error']['type'] == 'DocumentTableConflict' and conflict['before'] == current
                    and conflict['mutation'] == {'attempted': False, 'may_have_changed': False}, 'CAS refusal differs')
        require(current == case['final_options'] == case['persisted']['options'] == baseline['final_options'], 'saved/reopened options differ')
        saved = case['saved']
        native_file = public / ('public/gate/public-table-defaults.' + suffix)
        require(native_file.stat().st_size == saved['size_bytes'] >= 512 and digest(native_file.read_bytes()) == saved['sha256'], 'new public CAD file hash/size differs')
        require(saved['result']['api_saved'] is True and saved['result']['save_errors'] == 0 and saved['result']['save_warnings'] is None
                and saved['result']['document']['modified'] is False and case['reopen']['read_only'] is True
                and case['reopen']['api_errors'] == case['reopen']['api_warnings'] == 0
                and case['persisted']['document']['modified'] is False
                and case['persisted']['document']['document_id'] != case['initial']['document']['document_id']
                and PureWindowsPath(saved['host_path']) == PureWindowsPath(case['persisted']['document']['path'])
                and PureWindowsPath(saved['host_path']) != PureWindowsPath(case['initial']['document']['path']), 'save/reopen identity or access proof differs')
        for name in ('sdk_read', 'sdk_noop', 'mcp_read', 'mcp_noop'):
            raw = client[name]
            require(raw['success'] is True and raw['request_id'] not in responses, 'client response failed or reused ID')
            result = raw['result']
            require(result['options'] == current and result['document'] == case['writes'][-1]['document'], 'client result/state differs from CLI')
            if name.endswith('noop'):
                require(result['changed'] is False and result['mutation'] == {'attempted': False, 'may_have_changed': False}, 'client no-op mutated')
            responses[raw['request_id']] = result
    excluded = report['excluded_part_write']
    require(excluded['before'] == excluded['after'] and excluded['before']['document']['type'] == 1
            and excluded['refusal']['error']['type'] == 'DocumentTableCalibrationRequired'
            and excluded['refusal']['mutation'] == {'attempted': False, 'may_have_changed': False}, 'excluded part write did not fail closed')

    # Independently pair original native frames and derive counts/order per request.
    trace_path = public / 'public/daemon.native.stderr.jsonl'
    raw_trace = trace_path.read_bytes()
    snapshot = report['native_trace_snapshot']
    require(len(raw_trace) == snapshot['prefix_size_bytes'] and digest(raw_trace) == snapshot['prefix_sha256'], 'original native trace differs from gate snapshot')
    groups = defaultdict(list)
    for line in raw_trace.decode('utf-8-sig').splitlines():
        row = json.loads(line)
        if row.get('event') == 'swcli.native-call':
            groups[row['request_id']].append(row)
    require(len(groups) == 126 and set(groups) <= set(responses), 'native dispatch omitted, repeated or uncorrelated')
    trace_elapsed = max(rows[-1]['monotonic_seconds'] for rows in groups.values()) - min(rows[0]['monotonic_seconds'] for rows in groups.values())
    require(0 < trace_elapsed <= 1800, 'original native group exceeded 1800 seconds')
    derived, workers, total_getters, total_setters, maximum = [], set(), 0, 0, 0.0
    for request_id, rows in groups.items():
        stack, sequence = [], 0
        for row in rows:
            workers.add(row['worker_pid'])
            require(row['request_id'] == request_id and row['operation'] == rows[0]['operation'], 'native request identity changed')
            if row['phase'] == 'begin':
                require(row['sequence'] == sequence, 'native begin repeated/reordered')
                sequence += 1
                stack.append(row)
            else:
                require(row['phase'] in ('end', 'error') and stack, 'unmatched native end/error')
                begin = stack.pop()
                require((begin['sequence'], begin['call']) == (row['sequence'], row['call']), 'native call nesting/order mismatch')
                elapsed = row['monotonic_seconds'] - begin['monotonic_seconds']
                require(0 <= elapsed <= 600, 'native call exceeded 600 seconds')
                maximum = max(maximum, elapsed)
                require(row['phase'] != 'error' or (row['sequence'] == 0 and responses[request_id]['ok'] is False
                        and responses[request_id]['error']['type'] in ('DocumentLeaseConflict', 'DocumentUpdateConflict')), 'unexpected native error')
        require(not stack and rows[0]['sequence'] == rows[-1]['sequence'] == 0, 'native operation boundary incomplete')
        calls = [row['call'] for row in rows if row['phase'] == 'begin']
        require(not any(name.startswith(('SldWorks.SetUserPreference', 'ISldWorks.SetUserPreference')) for name in calls), 'application preference setter occurred')
        operation = rows[0]['operation']
        if operation not in ('document.table-options', 'document.table-option-set'):
            require(not any(name.startswith('IModelDocExtension.SetUserPreference') for name in calls), 'setter outside table request')
            continue
        result = responses[request_id]
        validate_operation_result(operation, result)
        if 'document' in result:
            require(result['document']['active'] is False, 'table request activated the background target')
            kind = result['document']['type']
        else:
            kind = document_types[argument(commands[request_id], '--document')]
        cycle = ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in TABLE_FIELDS.values() if kind in spec['types']]
        changed = result.get('changed') is True
        error = result.get('error', {}).get('type')
        reads = 0 if error in ('DocumentLeaseConflict', 'DocumentUpdateConflict', 'DocumentTableCalibrationRequired', 'ValueError') else 1
        dirty = calls.count('IModelDoc2.SetSaveFlag')
        require(dirty <= int(changed), 'extra dirty setter')
        relevant = [name for name in calls if name.startswith(('IModelDocExtension.GetUserPreference', 'IModelDocExtension.SetUserPreference')) or name == 'IModelDoc2.SetSaveFlag']
        expected = cycle * reads
        if changed:
            expected = cycle + ['IModelDocExtension.SetUserPreference' + TABLE_FIELDS[result['field']]['kind']] + cycle + ['IModelDoc2.SetSaveFlag'] * dirty + cycle
        require(relevant == expected, 'native table getter/setter/readback order differs')
        getters = sum(name.startswith('IModelDocExtension.GetUserPreference') for name in relevant)
        setters = sum(name.startswith('IModelDocExtension.SetUserPreference') for name in relevant)
        derived.append(dict(request_id=request_id, operation=operation, worker_pid=rows[0]['worker_pid'], native_getter_calls=getters, native_setter_calls=setters, dirty_calls=dirty))
        total_getters += getters
        total_setters += setters
    require(workers == {snapshot['worker_pid']} and derived == report['native_call_proofs'] and len(derived) == 57
            and (total_setters, total_getters) == (8, 274), 'derived native scope/counts differ from original report')
    return dict(success=True, run=PUBLIC['run'], head=PUBLIC['head'], artifact_id=PUBLIC['artifact'],
                current_product_matches_audited_head=product.returncode == 0,
                zip_sha256=PUBLIC['digest'], accepted_document_types=[2, 3], revision='33.5.0',
                native_table_requests=len(derived), native_setters=total_setters, native_getters=total_getters,
                maximum_native_call_seconds=maximum, native_group_seconds=trace_elapsed, gate_elapsed_seconds=report['elapsed_seconds'],
                cli_events=len(events), sdk_contracts=4, mcp_bridge_contracts=4, daemon_exit_confirmed=True,
                report_sha256=digest(report_path.read_bytes()), native_trace_sha256=digest(raw_trace),
                original_file_sha256={str(path.relative_to(public)): digest(path.read_bytes()) for path in sorted(public.rglob('*')) if path.is_file()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-evidence', type=Path, required=True)
    parser.add_argument('--internal-evidence', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='table-public-original-audit-') as temporary:
        temporary = Path(temporary)
        public = extract_original(args.public_evidence, PUBLIC, temporary / 'public')
        internal = extract_original(args.internal_evidence, INTERNAL, temporary / 'internal')
        result = audit(source, public, internal)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
