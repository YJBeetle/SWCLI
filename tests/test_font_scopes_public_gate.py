"""Portable public-gate logic proof, never native SOLIDWORKS acceptance."""
from contextlib import redirect_stderr
from copy import deepcopy
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_document_font_scopes as portable_adapter
from swcli.hosts.native_trace import trace_native_request
from swcli.sdk import Client
from swcli.mcp import DaemonBridge

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_font_scopes_public_gate', ROOT / 'scripts/ci/verify-font-scopes-public.py')
gate_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate_module)


class FontScopesPublicGateTests(unittest.TestCase):
    def setUp(self):
        self.adapter = portable_adapter.FontScopeTests()
        self.adapter.setUp()
        self.addCleanup(self.adapter.doCleanups)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.trace = Path(self.temporary.name) / 'daemon.stderr.log'

    def event(self, *, changed=True):
        stream = StringIO()
        name = 'document.font-scope-set' if changed else 'document.font-scopes'
        with patch.dict(os.environ, {'SWCLI_TRACE_NATIVE_CALLS': '1'}), redirect_stderr(stream):
            with trace_native_request('public-font-proof', name):
                response = self.adapter.edit(internal=True) if changed else self.adapter.operation(name)
        self.assertTrue(response['ok'], response)
        response['request_id'] = 'public-font-proof'
        self.trace.write_text(stream.getvalue())
        command = ['swcli', 'document', name.split('.')[1], 'notes', 'bold', 'true']
        gate = SimpleNamespace(record={'events': [{'command': command, 'result': response}]})
        return gate

    def test_public_trace_accepts_complete_real_adapter_boundaries(self):
        gate = self.event()
        proof = gate_module.FontScopeTrace(self.trace).verify(gate, field='bold', changed=True)
        self.assertEqual(proof['document_setters'], 1)
        self.assertEqual(proof['property_setters'], 1)
        self.assertEqual(proof['native_getter_cycles'], 3)

    def test_public_read_trace_requires_all_four_seventeen_member_snapshots(self):
        gate = self.event(changed=False)
        proof = gate_module.FontScopeTrace(self.trace).verify(gate)
        self.assertEqual(proof['document_setters'], 0)
        self.assertEqual(proof['native_getter_cycles'], 1)

    def test_public_trace_rejects_missing_reordered_duplicate_or_wrong_member(self):
        gate = self.event()
        original = self.trace.read_text().splitlines()
        def wrong_member(rows):
            index = next(index for index, row in enumerate(rows) if 'ITextFormat.' in row)
            rows[index] = rows[index].replace('ITextFormat.', 'ArbitraryCOM.')
        for mutate in (lambda rows: rows.pop(3),
                       lambda rows: rows.reverse(),
                       lambda rows: rows.insert(2, rows[2]),
                       wrong_member):
            rows = list(original)
            mutate(rows)
            self.trace.write_text('\n'.join(rows) + '\n')
            with self.assertRaises(RuntimeError):
                gate_module.FontScopeTrace(self.trace).verify(gate, field='bold', changed=True)

    def test_duplicate_request_or_native_budget_overrun_cannot_pass(self):
        gate = self.event()
        trace = gate_module.FontScopeTrace(self.trace)
        trace.verify(gate, field='bold', changed=True)
        with self.assertRaises(RuntimeError):
            trace.verify(gate, field='bold', changed=True)
        rows = [json.loads(line) for line in self.trace.read_text().splitlines()]
        next(row for row in rows if row['phase'] == 'end')['duration_ms'] = 600000
        self.trace.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
        with self.assertRaises(RuntimeError):
            gate_module.FontScopeTrace(self.trace).verify(gate, field='bold', changed=True)

    def test_public_cli_arguments_preserve_scalar_complete_cas_and_stamp(self):
        before = dict(fonts=self.adapter.fonts(), document={'update_stamp': 17})
        args = gate_module.arguments('notes', 'bold', True, before)
        self.assertEqual(args[:5], ['document', 'font-scope-set', 'notes', 'bold', 'true'])
        self.assertEqual(json.loads(args[args.index('--if-fonts') + 1]), before['fonts'])
        self.assertEqual(args[-2:], ['--if-update-stamp', '17'])
        stale = gate_module.arguments('notes', 'bold', True, before, stale=True)
        snapshot = json.loads(stale[stale.index('--if-fonts') + 1])
        self.assertNotEqual(snapshot['annotations']['bold'], before['fonts']['annotations']['bold'])
        self.assertEqual(snapshot['notes'], before['fonts']['notes'])

    def test_target_plan_changes_all_fields_and_persists_each_height_mode(self):
        fonts = self.adapter.fonts()['notes']
        plan = gate_module.targets(fonts)
        self.assertEqual(len(plan), 7)
        self.assertEqual([field for field, value in plan][-2:], ['height_mm', 'height_points'])
        self.assertTrue(all(fonts[field] != value for field, value in plan))

    def test_sdk_preserves_complete_snapshot_scalar_and_required_context_once(self):
        expected = self.adapter.fonts()
        def wire(operation, parameters, **context):
            result = self.adapter.operation(operation, parameters)
            return {'api_version': 'swcli/v1', 'request_id': context['request_id'],
                    'success': True, 'duration_ms': 1.0, 'result': result}
        client = Client(session_id='writer')
        with patch('swcli.sdk.client.call_daemon', side_effect=wire) as transport:
            client.document.font_scope_set(scope='notes', field='bold', value=True,
                expected_fonts=expected, document_id=self.adapter.entry.document_id,
                expected_update_stamp=7, lease_id=self.adapter.lease['lease_id'], request_id='font-sdk-once')
        transport.assert_called_once()
        self.assertEqual(transport.call_args.args, ('document.font-scope-set',
            {'scope': 'notes', 'field': 'bold', 'value': True, 'expected_fonts': expected}))
        self.assertEqual(transport.call_args.kwargs['expected_update_stamp'], 7)
        self.assertEqual(transport.call_args.kwargs['lease_id'], self.adapter.lease['lease_id'])
        self.adapter.assert_no_mutation()

    def test_sdk_incomplete_cas_or_wrong_scalar_fails_before_transport(self):
        client = Client()
        with patch('swcli.sdk.client.call_daemon') as transport:
            for snapshot, value in (({}, True), (self.adapter.fonts(), 1)):
                with self.assertRaises(ValueError):
                    client.document.font_scope_set(scope='notes', field='bold', value=value,
                        expected_fonts=snapshot, document_id=self.adapter.entry.document_id,
                        expected_update_stamp=7, lease_id=self.adapter.lease['lease_id'])
            transport.assert_not_called()

    def test_mcp_execute_preserves_font_context_and_partial_receipt_once(self):
        parameters = dict(scope='notes', field='bold', value=True, expected_fonts=self.adapter.fonts())
        refused = self.adapter.edit()
        envelope = {'api_version': 'swcli/v1', 'success': True, 'request_id': 'font-mcp-once',
                    'duration_ms': 1.0, 'result': refused}
        bridge = DaemonBridge(session_id='writer')
        with patch('swcli.mcp.call_daemon', return_value=envelope) as transport:
            result = bridge.call('execute', dict(operation='document.font-scope-set', parameters=parameters,
                document_id=self.adapter.entry.document_id, expected_update_stamp=7,
                lease_id=self.adapter.lease['lease_id'], request_id='font-mcp-once'))
        transport.assert_called_once()
        self.assertEqual(transport.call_args.args, ('document.font-scope-set', parameters))
        self.assertEqual(transport.call_args.kwargs['expected_update_stamp'], 7)
        self.assertEqual(transport.call_args.kwargs['lease_id'], self.adapter.lease['lease_id'])
        self.assertEqual(result['result']['mutation'], {'attempted': False, 'may_have_changed': False})
        self.adapter.assert_no_mutation()

    def test_public_wrapper_owns_one_hidden_daemon_and_has_hard_group_timeout(self):
        text = (ROOT / 'scripts/ci/windows/verify-font-scopes-public.ps1').read_text()
        self.assertIn('WaitForExit(1800 * 1000)', text)
        self.assertIn('Stop-Process -Id $worker.Id', text)
        self.assertNotIn('Stop-Process -Name', text)
        self.assertNotIn('taskkill', text.lower())
        self.assertIn('pre-existing SOLIDWORKS host', text)
        self.assertIn('--request-timeout 600 daemon stop', text)
        self.assertIn('"--startup-timeout", "120"', text)
        self.assertNotIn('daemon restart', text)
        self.assertNotIn('"--visible"', text)
        self.assertIn('GITHUB_EVENT_NAME -ne "workflow_dispatch"', text)

    def test_public_gate_never_imports_com_or_calls_internal_adapter(self):
        source = (ROOT / 'scripts/ci/verify-font-scopes-public.py').read_text()
        self.assertNotIn('import pythoncom', source)
        self.assertNotIn('import win32com', source)
        self.assertNotIn('_calibrate_set_document_font_scope', source)
        self.assertNotIn('operations.execute_operation', source)
        self.assertIn("'installed-public-cli-gate'", source)
        self.assertIn("--cli-command", source)
        self.assertIn('support.same_geometry', source)
        self.assertIn('read_only=True', source)


if __name__ == '__main__':
    unittest.main()
