"""Offline audit of the exact public 42419965068 all-type ZIP and pinned internal inputs."""

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import subprocess
import sys
import tempfile
import zipfile

PUBLIC = dict(run=42419965068, head='9bb806b454cdcbcb225135886482a2e555044444',
              artifact=13593611864, name='table-defaults-public-42419965068-1',
              digest='413268d6b2a31d6426da517305b711408bc13e6164b5b2a4e6b2fe0f18d29906')
INTERNAL = dict(run=42415716434, head='f1881a7421200e46028652538892c15a366f2ef8',
                artifact=13591813168, name='table-defaults-internal-42415716434-1',
                digest='7e1d8fcd8c1d8b26346024305c0f30a0c77536b2ea4ade06f3c694e382db9e8e')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def extract_original(evidence, pinned, output):
    run_path = evidence / 'completion-run.json'
    run, artifact = load(run_path if run_path.is_file() else evidence / 'run.json'), load(evidence / 'artifact.json')
    require((run['id'], run['head_sha'], run['head_branch'], run['event'], run['status'], run['conclusion']) ==
            (pinned['run'], pinned['head'], 'codex/docprops-table-defaults', 'workflow_dispatch', 'completed', 'success'),
            'run provenance mismatch')
    require((artifact['id'], artifact['name'], artifact['workflow_run']['id'], artifact['workflow_run']['head_sha'], artifact['expired']) ==
            (pinned['artifact'], pinned['name'], pinned['run'], pinned['head'], False), 'artifact provenance mismatch')
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
                    'src/swcli/result_schemas.py', 'src/swcli/hosts/windows_document_tables.py',
                    'scripts/ci/gate_support/table_defaults_geometry.py', 'src/swcli/daemon/server.py'], cwd=source, check=True, capture_output=True)
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
    require(report['covers_full_modeling_suite'] is False and report['accepted_document_types'] == [1, 2, 3], 'wrong accepted scope')
    require(candidate['success'] is True and candidate['requested_document_types'] == [1, 2, 3]
            and all(case['success'] for case in candidate['cases']), 'incomplete pinned internal inputs')
    require(INTERNAL_PROOF['run_id'] == INTERNAL['run'] and INTERNAL_PROOF['head'] == INTERNAL['head']
            and INTERNAL_PROOF['artifact_digest'] == 'sha256:' + INTERNAL['digest']
            and digest(candidate_path.read_bytes()) == INTERNAL_PROOF['report_sha256'], 'internal input pin mismatch')
    require(report['internal_proof'] == dict(run=str(INTERNAL['run']), head=INTERNAL['head'],
            report_sha256=INTERNAL_PROOF['report_sha256']), 'public report references another internal run')
    require(digest((internal / 'calibration/trace.jsonl').read_bytes()) == INTERNAL_PROOF['harness_trace_sha256']
            and digest((internal / 'worker.native.stderr.jsonl').read_bytes()) == INTERNAL_PROOF['native_trace_sha256'],
            'internal trace hash mismatch')
    require(set(PROFILES) == {('33.5.0', 1), ('33.5.0', 2), ('33.5.0', 3)}, 'runtime profile extends accepted document types')
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
    require(len(journal) == 2 * len(events) == 316, 'CLI event plan incomplete')
    responses, commands, document_types, owned = {}, {}, {}, set()
    leases, stamps, peers, peer_proofs, table_states = {}, {}, {}, [], {}
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
        if action in ('document.table-options', 'document.table-option-set') and result.get('ok'):
            descriptor = result['document']
            document_id = descriptor['document_id']
            if document_id in table_states:
                before_state = table_states[document_id]
                require(all(descriptor[key] == before_state['document'][key] for key in
                            ('document_id', 'path', 'title', 'type', 'update_stamp', 'active', 'current')), 'target identity/state drift')
                if result.get('changed') is not True:
                    require(result['options'] == before_state['options'] and descriptor == before_state['document'], 'observation/no-op changed table state')
                else:
                    require(result['before'] == before_state['options'] and descriptor['modified'] is True, 'write before state/dirty differs')
            table_states[document_id] = result
        if 'document' in result:
            descriptor = result['document']
            document_types[descriptor['document_id']] = descriptor['type']
            stamps[descriptor['document_id']] = descriptor['update_stamp']
        if action in ('document.lease.acquire', 'document.lease.renew') and result['ok']:
            leases[result['lease']['lease_id']] = result['lease']
        if action in ('document.create', 'document.open') and result['ok']:
            require(descriptor['document_id'] not in owned, 'duplicate live handle')
            owned.add(descriptor['document_id'])
            if action == 'document.create':
                peers[descriptor['document_id']] = descriptor
        if action == 'document.close' and result['ok']:
            require(result['closed'] is True and descriptor['document_id'] in owned, 'unexpected or repeated close')
            owned.remove(descriptor['document_id'])
            if descriptor['document_id'] in peers:
                before_peer = peers[descriptor['document_id']]
                require(all(descriptor[key] == before_peer[key] for key in ('document_id', 'title', 'path', 'type', 'update_stamp', 'modified')),
                        'foreground peer identity/stamp/dirty changed')
                peer_proofs.append(dict(before=before_peer, closed=descriptor))
    require(not owned and events[-2]['result']['count'] == 0 and events[-2]['result']['documents'] == [], 'owned documents remain open')
    require(len(peers) == len(peer_proofs) == 6, 'foreground peer plan incomplete')
    require(report['case_cleanup'] == [dict(case='tables-' + suffix, open_document_count=0, empty=True, remaining_document_ids=[])
                                        for suffix in ('SLDPRT', 'SLDASM', 'SLDDRW')], 'per-case cleanup incomplete')
    for event in (events[0], events[-1]):
        status = event['result']['result']
        require(status['host'] == host and status['worker_alive'] is True and status['recovery_required'] is False, 'daemon required recovery')

    def bind_summary(summary, document_id):
        require(any(without_request_id(result) == without_request_id(summary)
                    and '--document' in commands[request_id]
                    and argument(commands[request_id], '--document') == document_id
                    for request_id, result in responses.items() if request_id in commands),
                'case summary does not occur in original CLI stdout for its target')

    require([case['document_type'] for case in report['table_cases']] == [1, 2, 3], 'public case plan incomplete')
    require([client['document_type'] for client in report['client_contracts']] == [1, 2, 3], 'client contract plan incomplete')
    for client, case, baseline in zip(report['client_contracts'], report['table_cases'], candidate['cases']):
        kind = case['document_type']
        fields = [field for field, spec in TABLE_FIELDS.items() if kind in spec['types']]
        require(case['success'] is True and len(case['writes']) == len(case['noops']) == len(case['conflicts']) == len(fields), 'field plan incomplete')
        original_id = case['initial']['document']['document_id']
        reopened_id = case['persisted']['document']['document_id']
        for summary in [case['initial'], case['lease_refusal'], case['stamp_refusal'], case['unrelated_cas_refusal'],
                        case['saved']['result'], *case['writes'], *case['noops'], *case['conflicts']]:
            bind_summary(summary, original_id)
        bind_summary(case['persisted'], reopened_id)
        bind_summary(case['readonly_refusal'], reopened_id)
        suffix = {1: 'SLDPRT', 2: 'SLDASM', 3: 'SLDDRW'}[kind]
        original = internal / ('calibration/annotations.' + suffix)
        require(digest(original.read_bytes()) == case['source_sha256'] == baseline['file_sha256'], 'source fixture hash mismatch')
        require(case['open']['read_only'] is False and case['open']['api_errors'] == case['open']['api_warnings'] == 0, 'initial source is not writable/clean')
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
    require('excluded_part_write' not in report, 'all-type gate must not substitute a refused part write')

    # Recompute the table-only rule and bind each raw metric to a real measure response.
    geometry_spec = importlib.util.spec_from_file_location('_public_table_geometry_rule',
        source / 'scripts/ci/gate_support/table_defaults_geometry.py')
    geometry = importlib.util.module_from_spec(geometry_spec)
    geometry_spec.loader.exec_module(geometry)
    measurements = [response for response in responses.values() if response.get('action') == 'document.measure']
    part = report['table_cases'][0]
    checks = part['geometry_checks']
    require(len(measurements) == 3 and all(m['ok'] is True and m['document']['type'] == 1 for m in measurements), 'missing real part measurements')
    require([row['field'] for row in checks] == ['after-public-writes', 'saved-reopen']
            and measurements[0]['metrics'] == part['geometry_initial'], 'part geometry plan/baseline differs')
    for index, row in enumerate(checks, 1):
        comparison = geometry.compare_table_geometry(row['before'], row['after'])
        require(comparison['passed'] and {key: row.get(key) for key in comparison} == comparison
                and row['before'] == part['geometry_initial'] and row['after'] == measurements[index]['metrics'],
                'raw part geometry comparison or response binding differs')
    source_geometry = geometry.compare_table_geometry(candidate['cases'][0]['geometry_reopened'], measurements[0]['metrics'])
    require(source_geometry['passed'], 'public initial geometry differs from internal original fixture')
    require(measurements[0]['document']['document_id'] == measurements[1]['document']['document_id'] == part['initial']['document']['document_id']
            and measurements[2]['document']['document_id'] == part['persisted']['document']['document_id'], 'geometry measured another document')

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
    require(len(groups) == 168 and set(groups) <= set(responses), 'native dispatch omitted, repeated or uncorrelated')
    trace_elapsed = max(rows[-1]['monotonic_seconds'] for rows in groups.values()) - min(rows[0]['monotonic_seconds'] for rows in groups.values())
    require(0 < trace_elapsed <= 1800, 'original native group exceeded 1800 seconds')
    derived, workers, total_getters, total_setters, maximum = [], set(), 0, 0, 0.0
    guard_proofs = []
    error_frames = 0
    for request_id, rows in groups.items():
        require(rows[0]['operation'] == responses[request_id]['action'], 'native operation differs from actual response')
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
                error_frames += int(row['phase'] == 'error')
                require(row['phase'] != 'error' or (row['sequence'] == 0 and responses[request_id]['ok'] is False
                        and responses[request_id]['error']['type'] in ('DocumentLeaseConflict', 'DocumentUpdateConflict')), 'unexpected native error')
        require(not stack and rows[0]['sequence'] == rows[-1]['sequence'] == 0, 'native operation boundary incomplete')
        calls = [row['call'] for row in rows if row['phase'] == 'begin']
        for mutation_index, mutation_call in enumerate(calls):
            if mutation_call.startswith('IModelDocExtension.SetUserPreference') or mutation_call == 'IModelDoc2.SetSaveFlag':
                previous_read = max(index for index in range(mutation_index) if calls[index].startswith('IModelDocExtension.GetUserPreference'))
                guard_span = calls[previous_read + 1:mutation_index]
                require({'IsOpenedReadOnly', 'IsOpenedViewOnly', 'GetTitle', 'GetPathName', 'Extension',
                         'GetDocuments', 'ActiveDoc', 'GetSaveFlag', 'GetUpdateStamp'} <= set(guard_span),
                        'mutation lacks f188 target/peer/writable guard observations')
                require(guard_span.count('IsOpenedReadOnly') >= 2 and guard_span.count('IsOpenedViewOnly') >= 2,
                        'target and peer permission reads are incomplete')
                guard_proofs.append(dict(request_id=request_id, mutation=mutation_call,
                                         readonly_reads=guard_span.count('IsOpenedReadOnly'),
                                         viewonly_reads=guard_span.count('IsOpenedViewOnly')))
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
    require(workers == {snapshot['worker_pid']} and derived == report['native_call_proofs'] and len(derived) == 77
            and (total_setters, total_getters) == (11, 346), 'derived native scope/counts differ from original report')
    require(sum(proof['dirty_calls'] for proof in derived) == 3 and len(guard_proofs) == 14 and error_frames == 6,
            'dirty marking, guard coverage or expected lease/stamp errors differ')
    return dict(success=True, run=PUBLIC['run'], head=PUBLIC['head'], artifact_id=PUBLIC['artifact'],
                current_product_matches_audited_head=product.returncode == 0,
                zip_sha256=PUBLIC['digest'], accepted_document_types=[1, 2, 3], revision='33.5.0',
                native_table_requests=len(derived), native_setters=total_setters, native_getters=total_getters,
                maximum_native_call_seconds=maximum, native_group_seconds=trace_elapsed, gate_elapsed_seconds=report['elapsed_seconds'],
                cli_events=len(events), journal_entries=len(journal), native_requests=len(groups),
                peer_proofs=peer_proofs, guard_proofs=guard_proofs, expected_lease_stamp_error_frames=error_frames,
                source_geometry_comparison=source_geometry, original_geometry_checks=checks, sdk_contracts=6, mcp_bridge_contracts=6, daemon_exit_confirmed=True,
                report_sha256=digest(report_path.read_bytes()), native_trace_sha256=digest(raw_trace),
                original_file_sha256={str(path.relative_to(public)): digest(path.read_bytes()) for path in sorted(public.rglob('*')) if path.is_file()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-evidence', type=Path, required=True)
    parser.add_argument('--internal-evidence', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('_original_full_internal',
        Path(__file__).with_name('audit-table-defaults-internal-42415716434.py'))
    internal_auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(internal_auditor)
    internal_audit = internal_auditor.audit(args.internal_evidence.resolve())
    from swcli.document_table_profiles import PROFILES
    expected_profiles = {(internal_audit['revision'], int(kind)): {field: [tuple(pair) for pair in pairs]
                         for field, pairs in fields.items()} for kind, fields in internal_audit['profiles'].items()}
    require(PROFILES == expected_profiles, 'manually admitted profile expands or differs from complete audited internal evidence')
    with tempfile.TemporaryDirectory(prefix='table-public-original-audit-') as temporary:
        temporary = Path(temporary)
        public = extract_original(args.public_evidence, PUBLIC, temporary / 'public')
        internal = extract_original(args.internal_evidence, INTERNAL, temporary / 'internal')
        result = audit(source, public, internal)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
