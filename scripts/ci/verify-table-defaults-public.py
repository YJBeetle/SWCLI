"""Public CLI/daemon table-default acceptance using digest-pinned owned fixtures.

No COM imports, native retries, source saves, host replacement or rollback.
Only values proved by the preceding internal calibration are exercised.
"""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time

from swcli import __version__
from swcli.document_tables import TABLE_FIELDS
from swcli.mcp import DaemonBridge
from swcli.sdk import Client
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location("_table_annotation_helpers", Path(__file__).with_name("verify-document-annotations.py"))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
modeling, require = helpers.modeling, helpers.require


class TableSmoke(modeling.ModelingSmoke):
    def __init__(self, **kwargs):
        super().__init__(request_timeout_seconds=600, depth_request_timeout_seconds=600, **kwargs)
        self.group_started = time.monotonic()
        self.record['group_timeout_seconds'] = 1800

    def cleanup(self):
        if self.record.get('success') is not True:
            # A timed-out worker may be gone. Sending close/status here could
            # start a replacement through the generic manager; the owned
            # wrapper performs process cleanup without further CAD requests.
            self.cleaning_up = True
            self.record['cleanup_deferred_to_owned_wrapper'] = sorted(self.owned)
            return
        super().cleanup()

    def command(self, *args, **kwargs):
        require(self.cleaning_up or time.monotonic() - self.group_started < 1800, 'table public group exceeded 1800 seconds')
        result = super().command(*args, **kwargs)
        require(self.cleaning_up or time.monotonic() - self.group_started < 1800, 'table public group exceeded 1800 seconds')
        return result


class NativeTrace:
    def __init__(self, path):
        self.path, self.requests, self.worker = path, set(), None

    def verify(self, gate, *, operation, result, request_id, kind, setters=0, getters=None):
        require(request_id and request_id not in self.requests, 'table trace requires a fresh request ID')
        records = []
        for line in self.path.read_text(encoding='utf-8-sig').splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                require('swcli.native-call' not in line, 'malformed table native trace')
                continue
            if isinstance(row, dict) and row.get('event') == 'swcli.native-call' and row.get('request_id') == request_id:
                records.append(row)
        require(records and records[0]['sequence'] == records[-1]['sequence'] == 0
                and records[0]['phase'] == 'begin' and records[-1]['phase'] in ('end', 'error')
                and all(row['operation'] == operation for row in records), 'missing table operation trace boundary')
        begins = Counter((row['sequence'], row['call']) for row in records if row['phase'] == 'begin')
        ends = Counter((row['sequence'], row['call']) for row in records if row['phase'] in ('end', 'error'))
        require(begins == ends and begins[(0, operation)] == 1 and all(count == 1 for count in begins.values()),
                'missing or repeated table native call boundaries')
        calls = records[1:-1]
        require(len(calls) % 2 == 0, 'incomplete table native trace pair')
        for number, (begin, end) in enumerate(zip(calls[::2], calls[1::2]), 1):
            require(begin['sequence'] == end['sequence'] == number and begin['phase'] == 'begin'
                    and end['phase'] in ('end', 'error') and begin['call'] == end['call'], 'table native trace order changed')
        worker = records[0]['worker_pid']
        require(type(worker) is int and worker > 0 and all(row['worker_pid'] == worker for row in records), 'table trace worker changed')
        require(self.worker in (None, worker), 'table acceptance replaced the owning worker')
        self.worker = worker
        cycle = ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in TABLE_FIELDS.values() if kind in spec['types']]
        reads = [row['call'] for row in records if row['phase'] == 'begin' and row['call'].startswith('IModelDocExtension.GetUserPreference')]
        writes = [row['call'] for row in records if row['phase'] == 'begin' and row['call'].startswith('IModelDocExtension.SetUserPreference')]
        dirty = [row for row in records if row['phase'] == 'begin' and row['call'] == 'IModelDoc2.SetSaveFlag']
        count = (3 if setters else 1) if getters is None else getters
        require(reads == cycle * count and len(writes) == setters and len(dirty) <= setters,
                'table native getter/setter/dirty count differs from its lifecycle')
        relevant = [row['call'] for row in records if row['phase'] == 'begin' and
                    (row['call'].startswith('IModelDocExtension.GetUserPreference') or
                     row['call'].startswith('IModelDocExtension.SetUserPreference') or row['call'] == 'IModelDoc2.SetSaveFlag')]
        expected = cycle * count
        if setters:
            require(result.get('field') in TABLE_FIELDS, 'table write trace has no field')
            method = 'IModelDocExtension.SetUserPreference' + TABLE_FIELDS[result['field']]['kind']
            expected = cycle + [method] + cycle + ['IModelDoc2.SetSaveFlag'] * len(dirty) + cycle
        require(relevant == expected, 'table native readback order changed')
        require(not any(row['call'].startswith(('ISldWorks.SetUserPreference', 'SldWorks.SetUserPreference')) for row in records),
                'table request called an application preference setter')
        require(not result.get('ok') or all(row['phase'] != 'error' for row in records), 'successful table result has a native trace error')
        self.requests.add(request_id)
        proof = dict(request_id=request_id, operation=operation, worker_pid=worker,
                     native_getter_calls=len(reads), native_setter_calls=len(writes), dirty_calls=len(dirty))
        gate.record.setdefault('native_call_proofs', []).append(proof)
        return proof

    def snapshot(self):
        content = self.path.read_bytes()
        return dict(path=str(self.path), prefix_size_bytes=len(content), prefix_sha256=hashlib.sha256(content).hexdigest(),
                    verified_request_count=len(self.requests), worker_pid=self.worker)


def observed(gate, trace, document, kind, *, session=None):
    result = gate.command('document', 'table-options', document=document, session=session)
    validate_operation_result('document.table-options', result)
    trace.verify(gate, operation='document.table-options', result=result,
                 request_id=gate.record['events'][-1]['result']['request_id'], kind=kind)
    gate.background(result, document)
    return result


def change(gate, trace, document, kind, current, field, value, *, expected=None, error=None, contender=False, stamp=None):
    before = current['options'] if expected is None else expected
    arguments = ('document', 'table-option-set', field, helpers.scalar_argument(value),
                 '--if-options-json', json.dumps(before, separators=(',', ':')),
                 '--if-update-stamp', current['document']['update_stamp'] if stamp is None else stamp)
    if contender:
        result = gate.command(*arguments, document=document, lease=gate.leases[document],
                              session=gate.session + '-contender', expected_error=error)
    else:
        result = gate.write(*arguments, document=document, expected_error=error)
    validate_operation_result('document.table-option-set', result)
    changed = not error and current['options'][field].get('value') != value
    zero_read = error in ('DocumentLeaseConflict', 'DocumentUpdateConflict', 'ValueError', 'DocumentTableCalibrationRequired')
    trace.verify(gate, operation='document.table-option-set', result=result, kind=kind,
                 request_id=gate.record['events'][-1]['result']['request_id'], setters=int(changed),
                 getters=0 if zero_read else None)
    if error in ('DocumentLeaseConflict', 'DocumentUpdateConflict'):
        require('mutation' not in result or result['mutation'] == dict(attempted=False, may_have_changed=False), 'pre-adapter refusal claims a mutation')
    else:
        require(result['mutation'] == dict(attempted=bool(changed), may_have_changed=bool(changed)), 'table mutation receipt differs from native calls')
    if error:
        return result
    require(result['before'] == current['options'] and result['changed'] is changed
            and result['options'][field]['value'] == value
            and all(result['options'][key] == current['options'][key] for key in TABLE_FIELDS if key != field),
            'public table write changed more than one expected scalar')
    require(not changed or result['document']['modified'], 'public table setter did not mark the target dirty')
    if not changed:
        require(result['document'] == current['document'], 'table no-op changed native document state')
    gate.background(result, document)
    return result


def verify_clients(gate, trace, document, kind, current, field, value):
    client = Client(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    read = client.document.table_options(document_id=document, expected_update_stamp=current['document']['update_stamp'])
    result = read.require_result()
    require(result['options'] == current['options'] and result['document'] == current['document'], 'typed SDK read changed table state')
    trace.verify(gate, operation='document.table-options', result=result, request_id=read.request_id, kind=kind)
    noop = client.document.table_option_set(field=field, value=value, expected_options=current['options'],
        document_id=document, expected_update_stamp=current['document']['update_stamp'], lease_id=gate.leases[document])
    result = noop.require_result()
    require(not result['changed'] and result['mutation'] == dict(attempted=False, may_have_changed=False)
            and result['options'] == current['options'] and result['document'] == current['document'], 'typed SDK no-op changed table state')
    trace.verify(gate, operation='document.table-option-set', result=result, request_id=noop.request_id, kind=kind)
    bridge = DaemonBridge(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    mcp = bridge.call('execute', dict(operation='document.table-options', parameters={}, document_id=document,
                                     expected_update_stamp=current['document']['update_stamp']))
    require(mcp['success'] and mcp['result']['ok'], 'MCP bridge table read failed')
    validate_operation_result('document.table-options', mcp['result'])
    require(mcp['result']['options'] == current['options'] and mcp['result']['document'] == current['document'], 'MCP read changed table state')
    trace.verify(gate, operation='document.table-options', result=mcp['result'], request_id=mcp['request_id'], kind=kind)
    mcp_noop = bridge.call('execute', dict(operation='document.table-option-set', parameters=dict(
        field=field, value=value, expected_options=current['options']), document_id=document,
        expected_update_stamp=current['document']['update_stamp'], lease_id=gate.leases[document]))
    require(mcp_noop['success'] and mcp_noop['result']['ok'], 'MCP bridge table no-op failed')
    validate_operation_result('document.table-option-set', mcp_noop['result'])
    require(not mcp_noop['result']['changed'] and mcp_noop['result']['mutation'] == dict(attempted=False, may_have_changed=False)
            and mcp_noop['result']['options'] == current['options'] and mcp_noop['result']['document'] == current['document'], 'MCP no-op changed table state')
    trace.verify(gate, operation='document.table-option-set', result=mcp_noop['result'], request_id=mcp_noop['request_id'], kind=kind)
    gate.record.setdefault('client_contracts', []).append(dict(document_type=kind, sdk_read=dict(read.raw), sdk_noop=dict(noop.raw), mcp_read=mcp, mcp_noop=mcp_noop))


def run(gate, fixtures, trace, internal, proof):
    require(internal.get('success') is True and internal.get('full_acceptance_eligible') is False
            and internal.get('diagnostic_case') == 'document-table-defaults-internal', 'internal candidate evidence is incomplete')
    cases = internal['cases']
    requested = internal.get('requested_document_types', [1, 2, 3])
    require(type(requested) is list and requested and requested == sorted(set(requested)) and set(requested) <= {1, 2, 3}
            and [case['document_type'] for case in cases] == requested and all(case['success'] for case in cases), 'internal document-type coverage is incomplete')
    gate.record.update(profile='document-table-defaults', evidence_kind='installed-public-cli-daemon-gate',
                       covers_full_modeling_suite=False, feature_acceptance_eligible=True, internal_proof=proof, table_cases=[])
    health = gate.health()
    gate.record['accepted_document_types'] = requested
    gate.record['host'] = host = health['host']
    require(health.get('server_version') == __version__ and host.get('owned_by_daemon') is True
            and host.get('visible') is False and host.get('shared_interactive') is False
            and host.get('revision') == internal['host']['revision'], 'public table gate host/version differs from internal proof')
    gate.require_empty()
    if 1 not in requested:
        part = gate.create()
        peer = gate.create()
        gate.command('document', 'lease', 'acquire', '--ttl-seconds', 1800, document=part)
        part_before = observed(gate, trace, part, 1)
        part_refusal = change(gate, trace, part, 1, part_before, 'all.use_template_settings',
                              not part_before['options']['all.use_template_settings']['value'], error='DocumentTableCalibrationRequired')
        part_after = observed(gate, trace, part, 1)
        require(part_after['options'] == part_before['options'] and part_after['document'] == part_before['document'],
                'excluded part write changed options or document state')
        gate.record['excluded_part_write'] = dict(before=part_before, refusal=part_refusal, after=part_after)
        gate.close(part)
        gate.close(peer)
        gate.require_empty(after_case='excluded-part-write')
    for candidate in cases:
        kind = candidate['document_type']
        suffix = {1: 'SLDPRT', 2: 'SLDASM', 3: 'SLDDRW'}[kind]
        source = fixtures / ('annotations.' + suffix)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        require(source_hash == candidate['file_sha256'], 'original internal fixture digest mismatch')
        opened, document, peer = helpers.open_background(gate, str(source), kind)
        case = dict(document_type=kind, source_sha256=source_hash, open=opened, writes=[], noops=[], conflicts=[], success=False)
        gate.record['table_cases'].append(case)
        gate.command('document', 'lease', 'acquire', '--ttl-seconds', 1800, document=document)
        initial = observed(gate, trace, document, kind, session=gate.session + '-reader')
        case['initial'] = initial
        require(initial['options'] == candidate['original']['options'] and not initial['document']['modified'], 'public fixture differs from its verified initial values')
        if kind == 1:
            case['geometry_initial'] = helpers.geometry(gate, document)
            values = case['geometry_initial']
            require(values['solid_body_count'] == 1 and math.isclose(values['volume_mm3'], 12000, rel_tol=1e-9, abs_tol=1e-6)
                    and math.isclose(values['surface_area_mm2'], 3800, rel_tol=1e-9, abs_tol=1e-6)
                    and all(math.isclose(values['centroid_mm'][axis], expected, rel_tol=0, abs_tol=1e-6)
                            for axis, expected in (('x', 0), ('y', 0), ('z', 5))), 'public table fixture differs from its analytic box')
        targets = {field: candidate['final_options'][field]['value'] for field, spec in TABLE_FIELDS.items() if kind in spec['types']}
        field = next(iter(targets))
        case['lease_refusal'] = change(gate, trace, document, kind, initial, field, targets[field], error='DocumentLeaseConflict', contender=True)
        case['stamp_refusal'] = change(gate, trace, document, kind, initial, field, targets[field], error='DocumentUpdateConflict', stamp=initial['document']['update_stamp'] + 1)
        current = initial
        for field, value in targets.items():
            require(current['options'][field]['value'] != value, 'each accepted field needs a real changed-value public write')
            previous = deepcopy(current)
            current = change(gate, trace, document, kind, current, field, value)
            case['writes'].append(current)
            if len(case['writes']) == 1:
                other = next(key for key in targets if key != field)
                stale = deepcopy(current['options'])
                stale[field] = deepcopy(initial['options'][field])
                case['unrelated_cas_refusal'] = change(gate, trace, document, kind, current, other, targets[other],
                    expected=stale, error='DocumentTableConflict')
            case['noops'].append(change(gate, trace, document, kind, current, field, value))
            case['conflicts'].append(change(gate, trace, document, kind, current, field, value, expected=previous['options'], error='DocumentTableConflict'))
            after_refusal = observed(gate, trace, document, kind)
            require(after_refusal['options'] == current['options'] and after_refusal['document'] == current['document'], 'complete-snapshot CAS refusal changed native state')
        verify_clients(gate, trace, document, kind, current, field, value)
        if kind == 1:
            helpers.same_geometry(case['geometry_initial'], helpers.geometry(gate, document))
        saved = case['saved'] = helpers.save_copy(gate, document, 'public-table-defaults.' + suffix, suffix)
        case['final_options'] = current['options']
        gate.close(document)
        gate.close(peer)
        reopened, fresh, peer = helpers.open_background(gate, saved['host_path'], kind, read_only=True)
        case['reopen'] = reopened
        require(fresh != document, 'table saved reopen reused a retired document handle')
        gate.command('document', 'lease', 'acquire', '--ttl-seconds', 1800, document=fresh)
        observed_copy = case['persisted'] = observed(gate, trace, fresh, kind)
        require(observed_copy['options'] == current['options'] and not observed_copy['document']['modified'], 'table defaults failed save/reopen persistence')
        case['readonly_refusal'] = change(gate, trace, fresh, kind, observed_copy, field, value, error='ValueError')
        final = observed(gate, trace, fresh, kind)
        require(final['options'] == observed_copy['options'] and final['document'] == observed_copy['document']
                and hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
                and hashlib.sha256(Path(saved['path']).read_bytes()).hexdigest() == saved['sha256'], 'public table gate changed source/saved file or read-only state')
        if kind == 1:
            helpers.same_geometry(case['geometry_initial'], helpers.geometry(gate, fresh))
        gate.close(fresh)
        gate.close(peer)
        gate.require_empty(after_case='tables-' + suffix)
        case['success'] = True
        gate.checkpoint('tables-' + suffix + '-verified')
    require(not gate.owned, 'public table ownership journal still contains open documents')
    gate.record['host_after'] = gate.health()['host']
    require(gate.record['host_after'] == host, 'public table gate replaced its owning host')
    gate.record.update(state='completed', success=True, elapsed_seconds=time.monotonic() - gate.group_started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--fixture-dir', type=Path, required=True)
    parser.add_argument('--native-trace', type=Path, required=True)
    parser.add_argument('--internal-report-sha256', required=True)
    parser.add_argument('--internal-head', required=True)
    parser.add_argument('--internal-run', required=True)
    parser.add_argument('--endpoint', default=os.environ.get('SWCLI_ENDPOINT', modeling.DEFAULT_ENDPOINT))
    args = parser.parse_args(argv)
    report_path = args.fixture_dir / 'report.json'
    content = report_path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == args.internal_report_sha256, 'internal report digest mismatch')
    internal = json.loads(content)
    args.output_dir.mkdir()
    gate = TableSmoke(directory=args.output_dir, host_directory=str(args.output_dir), endpoint=args.endpoint)
    gate.record_path = args.output_dir / 'table-defaults-public.json'
    trace = NativeTrace(args.native_trace)
    with gate.record_path.open('x', encoding='utf-8') as stream:
        json.dump(gate.record, stream)
    try:
        run(gate, args.fixture_dir, trace, internal, dict(run=args.internal_run, head=args.internal_head,
            report_sha256=args.internal_report_sha256))
    except BaseException as error:
        gate.record.update(state='failed', success=False, error=dict(type=type(error).__name__, message=str(error)))
        raise
    finally:
        gate.cleanup()
        if gate.record['cleanup_errors'] or gate.checkpoint_error is not None:
            gate.record.update(state='failed', success=False)
        try:
            gate.record['native_trace_snapshot'] = trace.snapshot()
        except Exception as error:
            gate.record['cleanup_errors'].append(dict(stage='native-trace-snapshot', type=type(error).__name__, message=str(error)))
            gate.record.update(state='failed', success=False)
        gate.checkpoint('table-defaults-public-final')
    require(not gate.record['cleanup_errors'] and gate.checkpoint_error is None, 'table public cleanup/checkpoint failed')


if __name__ == '__main__':
    main()
