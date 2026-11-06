"""Portable public-gate trace/client contracts; not native acceptance proof."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.document_tables import TABLE_FIELDS
from swcli.sdk import Client
from swcli.sdk.runtime import Response
from swcli.mcp import DaemonBridge
from tests import test_document_tables as fakes

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('table_public_gate_test', ROOT / 'scripts/ci/verify-table-defaults-public.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PublicTableContractTests(unittest.TestCase):
    def test_sdk_and_mcp_preserve_complete_snapshot_identity_stamp_and_lease(self):
        fixture = fakes.DocumentTableTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        observed = fixture.read()
        values = dict(field='bom.box_border', value='normal', expected_options=observed['options'])
        result = fixture.edit('bom.box_border', 'normal')
        envelope = dict(api_version='swcli/v1', success=True, request_id='table-sdk-noop', duration_ms=1, result=result)
        with mock.patch('swcli.sdk.client.call_daemon', return_value=envelope) as sdk_wire:
            response = Client(session_id='writer').document.table_option_set(**values, document_id=fixture.entry.document_id,
                expected_update_stamp=7, lease_id=fixture.lease, request_id='table-sdk-noop')
            self.assertTrue(response.ok)
            self.assertEqual(sdk_wire.call_args.args, ('document.table-option-set', values))
            self.assertEqual(sdk_wire.call_args.kwargs['expected_update_stamp'], 7)
            self.assertEqual(sdk_wire.call_args.kwargs['lease_id'], fixture.lease)
        with mock.patch('swcli.mcp.call_daemon', return_value=envelope) as mcp_wire:
            bridge = DaemonBridge(session_id='writer')
            response = bridge.call('execute', dict(operation='document.table-option-set', parameters=values,
                document_id=fixture.entry.document_id, expected_update_stamp=7, lease_id=fixture.lease))
            self.assertTrue(response['success'])
            self.assertEqual(mcp_wire.call_args.args, ('document.table-option-set', values))
            self.assertEqual(mcp_wire.call_args.kwargs['document_id'], fixture.entry.document_id)
            self.assertEqual(mcp_wire.call_args.kwargs['lease_id'], fixture.lease)

    def test_declared_wine_write_is_refused_before_worker_start_or_queue(self):
        from swcli.daemon import server
        from swcli.result_schemas import validate_operation_result
        for platform in ('macos-wine', 'linux-wine'):
            with self.subTest(platform=platform), mock.patch.object(server.WorkerManager, '_start_worker') as start:
                manager = server.WorkerManager(host_platform=platform)
                start.reset_mock()
                with mock.patch.object(manager, '_refresh_worker_state_locked'):
                    response = manager.call(dict(request_id='wine-table', operation='document.table-option-set',
                        timeout_ms=600000, parameters={}, document_id='d-abcdef', expected_update_stamp=7, lease_id='l-abcdefghijkl'))
                self.assertFalse(response['success'])
                self.assertEqual(response['result']['mutation'], dict(attempted=False, may_have_changed=False))
                self.assertEqual(response['error']['code'], 'DocumentTableCalibrationRequired')
                validate_operation_result('document.table-option-set', response['result'])
                start.assert_not_called()
                self.assertIsNone(manager._request_queue)

    def trace_rows(self, operation, calls):
        base = dict(event='swcli.native-call', request_id='fresh-table-request', operation=operation, worker_pid=99)
        rows = [dict(base, sequence=0, call=operation, phase='begin')]
        for number, call in enumerate(calls, 1):
            rows.extend(dict(base, sequence=number, call=call, phase=phase) for phase in ('begin', 'end'))
        return rows + [dict(base, sequence=0, call=operation, phase='end')]

    def test_native_trace_accepts_one_setter_and_rejects_missing_reads_reordering_and_duplicate_calls(self):
        cycle = ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in TABLE_FIELDS.values() if 1 in spec['types']]
        calls = cycle + ['IModelDocExtension.SetUserPreferenceInteger'] + cycle + ['IModelDoc2.SetSaveFlag'] + cycle
        result = dict(ok=True, field='bom.box_border')
        for defect in (None, 'getter', 'setter', 'order', 'boundary', 'worker', 'global'):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                rows = self.trace_rows('document.table-option-set', calls)
                if defect == 'getter': rows = self.trace_rows('document.table-option-set', calls[1:])
                if defect == 'setter': rows = self.trace_rows('document.table-option-set', calls + ['IModelDocExtension.SetUserPreferenceInteger'])
                if defect == 'order': rows[1], rows[2] = rows[2], rows[1]
                if defect == 'boundary': rows.pop()
                if defect == 'worker': rows[2]['worker_pid'] = 100
                if defect == 'global': rows = self.trace_rows('document.table-option-set', calls + ['ISldWorks.SetUserPreferenceToggle'])
                path = Path(temporary) / 'trace.jsonl'
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                trace = gate.NativeTrace(path)
                arguments = dict(operation='document.table-option-set', result=result, request_id='fresh-table-request', kind=1, setters=1)
                if defect:
                    with self.assertRaises(RuntimeError): trace.verify(SimpleNamespace(record={}), **arguments)
                else:
                    proof = trace.verify(SimpleNamespace(record={}), **arguments)
                    self.assertEqual((proof['native_setter_calls'], proof['native_getter_calls']), (1, 9))
                    with self.assertRaises(RuntimeError): trace.verify(SimpleNamespace(record={}), **arguments)

    def test_pre_adapter_lease_refusal_needs_no_mutation_field_or_native_preferences(self):
        current = dict(options={}, document={'update_stamp': 7})
        response = dict(ok=False, action='document.table-option-set', error=dict(type='DocumentLeaseConflict', message='leased'))
        fake = SimpleNamespace(session='writer', leases={'d-abcdef': 'l-abcdefghijkl'},
            record={'events': [{'result': dict(response, request_id='lease-refusal')}]}, command=mock.Mock(return_value=response))
        trace = mock.Mock()
        result = gate.change(fake, trace, 'd-abcdef', 1, current, 'bom.box_border', 'normal', error='DocumentLeaseConflict', contender=True)
        self.assertEqual(result, response)
        self.assertEqual(trace.verify.call_args.kwargs['getters'], 0)


from tests.test_modeling_smoke import FakeCLI
from swcli.cli import _typed_operation
from swcli.document_tables import LINE_WEIGHTS
import hashlib
import io
import subprocess


def options_for(kind):
    result = {}
    for field, spec in TABLE_FIELDS.items():
        if kind not in spec['types']:
            result[field] = {'unavailable': 'document_type'}
        elif spec['kind'] == 'Toggle':
            result[field] = dict(value=True, native_value=True)
        else:
            value = 'normal' if 'box' in field else 'thin'
            result[field] = dict(value=value, native_value=LINE_WEIGHTS[value])
    return result


class TableCLI(FakeCLI):
    def __init__(self, directory, trace):
        super().__init__(directory)
        self.trace = trace
        self.native_calls = []
        self.request_override = None
        self.table_defect = None
        self.setters = 0

    def run(self, command, **kwargs):
        self.native_calls = []
        completed = super().run(command, **kwargs)
        args = self.calls[-1]
        result = json.loads(completed.stdout)
        if self.request_override:
            result['request_id'] = self.request_override
            self.request_override = None
        if args.command == 'document' and args.document_command.startswith('table-'):
            operation = 'document.' + args.document_command
            calls = list(self.native_calls)
            if self.table_defect == 'missing-getter':
                calls = [call for call in calls if not call.startswith('IModelDocExtension.GetUserPreference')]
            rows = PublicTableContractTests().trace_rows(operation, calls)
            for row in rows:
                row['request_id'] = result['request_id']
            with self.trace.open('a') as stream:
                stream.write(''.join(json.dumps(row) + '\n' for row in rows))
        return subprocess.CompletedProcess(command, completed.returncode, json.dumps(result).encode(), completed.stderr)

    def dispatch(self, args):
        if args.command == 'document' and args.document_command.startswith('table-'):
            doc = self.documents[args.document_id]
            operation = 'document.' + args.document_command
            options = doc['tables']
            cycle = ['IModelDocExtension.GetUserPreference' + spec['kind'] for spec in TABLE_FIELDS.values() if doc['type'] in spec['types']]
            result = dict(ok=True, action=operation, session_id=args.session, document=self.descriptor(doc, args.session))
            if args.document_command == 'table-options':
                self.native_calls += cycle
                return dict(result, options=deepcopy(options))
            if args.expected_update_stamp != doc['stamp']:
                return dict(ok=False, action=operation, error=dict(type='DocumentUpdateConflict', message='stamp changed'))
            if doc['lease']['session'] != args.session:
                return dict(ok=False, action=operation, error=dict(type='DocumentLeaseConflict', message='leased'))
            mutation = dict(attempted=False, may_have_changed=False)
            if doc['read_only']:
                return dict(ok=False, action=operation, mutation=mutation, error=dict(type='ValueError', message='readonly'))
            _, values, *_ = _typed_operation(args)
            self.native_calls += cycle
            if values['expected_options'] != options:
                return dict(ok=False, action=operation, mutation=mutation, error=dict(type='DocumentTableConflict', message='snapshot changed'))
            field, value = values['field'], values['value']
            before = deepcopy(options)
            changed = options[field]['value'] != value
            if changed:
                self.setters += 1
                self.native_calls += ['IModelDocExtension.SetUserPreference' + TABLE_FIELDS[field]['kind']]
                if self.table_defect == 'setter-failure':
                    return dict(ok=False, action=operation, mutation=dict(attempted=True, may_have_changed=True),
                                error=dict(type='NativeTableFailure', message='first native setter failure'))
                native = value if type(value) is bool else LINE_WEIGHTS[value]
                options[field] = dict(value=value, native_value=native)
                self.native_calls += cycle
                if not doc['modified']:
                    self.native_calls.append('IModelDoc2.SetSaveFlag')
                doc['modified'] = True
                doc['stamp'] += 1
                self.native_calls += cycle
            result.update(field=field, before=before, options=deepcopy(options), changed=changed,
                          mutation=dict(attempted=changed, may_have_changed=changed), document=self.descriptor(doc, args.session))
            if changed:
                result['native_returned'] = True
            return result
        result = super().dispatch(args)
        if args.command == 'daemon':
            result['result'].update(server_version=gate.__version__)
            result['result']['host'].update(revision='33.5.0', owned_by_daemon=True, shared_interactive=False, visible=False)
        if args.command == 'document' and args.document_command in ('open', 'create'):
            doc = self.documents[result['document']['document_id']]
            doc.setdefault('tables', options_for(doc['type']))
            doc['area'] = 3800
            if args.document_command == 'open' and args.read_only and self.table_defect == 'lost-persisted-value':
                doc['tables']['all.use_template_settings'] = dict(value=True, native_value=True)
        if args.command == 'document' and args.document_command == 'measure':
            result['metrics']['centroid_mm'] = dict(x=0, y=0, z=5)
        if args.command == 'document' and args.document_command == 'save-as':
            result['save_warnings'] = None
        return result

    def transport(self, operation, values, **context):
        args = ['swcli', '--endpoint', 'unused', '--session', context['session_id'], 'document', operation.split('.')[1]]
        if operation.endswith('-set'):
            args += [values['field'], gate.helpers.scalar_argument(values['value']), '--if-options-json', json.dumps(values['expected_options'])]
        args += ['--document', context['document_id'], '--if-update-stamp', str(context['expected_update_stamp'])]
        if context.get('lease_id'):
            args += ['--lease', context['lease_id']]
        self.request_override = context['request_id']
        completed = self.run(args + ['--json'])
        result = json.loads(completed.stdout)
        result.pop('request_id', None)
        return dict(api_version='swcli/v1', request_id=context['request_id'], success=result['ok'], duration_ms=1, result=result)


class PublicTableGateControlTests(unittest.TestCase):
    def exercise(self, defect=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        directory, fixtures = root / 'public', root / 'fixtures'
        directory.mkdir()
        fixtures.mkdir()
        trace_path = root / 'trace.jsonl'
        trace_path.write_text('')
        internal = dict(success=True, full_acceptance_eligible=False, diagnostic_case='document-table-defaults-internal',
                        host={'revision': '33.5.0'}, cases=[])
        for kind, suffix in enumerate(('SLDPRT', 'SLDASM', 'SLDDRW'), 1):
            source = fixtures / ('annotations.' + suffix)
            source.write_bytes(b'owned fixture' * 100)
            before = options_for(kind)
            after = deepcopy(before)
            for field, entry in after.items():
                if 'value' not in entry: continue
                value = False if type(entry['value']) is bool else 'thick' if entry['value'] == 'normal' else 'normal'
                entry.update(value=value, native_value=value if type(value) is bool else LINE_WEIGHTS[value])
            internal['cases'].append(dict(document_type=kind, success=True, original={'options': before},
                final_options=after, file_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
        fake = TableCLI(directory, trace_path)
        fake.table_defect = defect
        instance = gate.TableSmoke(directory=directory, host_directory=r'C:\proof', endpoint='127.0.0.1:18495')
        instance.record_path = directory / 'table-defaults-public.json'
        instance.record_path.write_text('{}')
        with mock.patch.object(gate.modeling.subprocess, 'run', side_effect=fake.run), \
             mock.patch('swcli.sdk.client.call_daemon', side_effect=fake.transport), \
             mock.patch('swcli.mcp.call_daemon', side_effect=fake.transport), mock.patch('sys.stdout', new=io.StringIO()):
            if defect:
                with self.assertRaises(RuntimeError):
                    gate.run(instance, fixtures, gate.NativeTrace(trace_path), internal, {'run': 1, 'head': 'verified', 'report_sha256': 'verified'})
            else:
                gate.run(instance, fixtures, gate.NativeTrace(trace_path), internal, {'run': 1, 'head': 'verified', 'report_sha256': 'verified'})
        return fake, instance.record

    def test_three_types_public_writes_clients_and_readonly_persistence_are_distinct(self):
        fake, report = self.exercise()
        self.assertTrue(report['success'])
        self.assertEqual([case['document_type'] for case in report['table_cases']], [1, 2, 3])
        self.assertEqual(fake.setters, 11)
        self.assertEqual(len(report['client_contracts']), 3)
        self.assertEqual(fake.documents, {})
        self.assertEqual(report['host'], report['host_after'])
        for case in report['table_cases']:
            self.assertEqual(case['persisted']['options'], case['final_options'])
            self.assertTrue(case['success'])

    def test_first_failure_stops_native_trace_setter_or_persistence_plan(self):
        for defect in ('missing-getter', 'setter-failure', 'lost-persisted-value'):
            with self.subTest(defect=defect):
                fake, report = self.exercise(defect)
                self.assertLessEqual(len(report['table_cases']), 1)
                if defect == 'setter-failure':
                    self.assertEqual(fake.setters, 1)


if __name__ == '__main__':
    unittest.main()
