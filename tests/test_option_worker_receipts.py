"""Late worker faults preserve actual adapter mutations and retire unknown hosts."""
from contextlib import contextmanager
from unittest import TestCase, mock
import test_document_line_font as line
import test_dimension_format as dimension
from swcli.daemon import server
from swcli.hosts import windows_dimension_format
from swcli.hosts.native_sequence import NativeCommandRestoreFailed
from swcli.result_schemas import validate_operation_result


class OptionWorkerReceiptTests(TestCase):
    def run_worker(self, kind, native_failure=False, validation_failure=False):
        if kind == 'line':
            case = line.LineFontTests(); case.setUp(); self.addCleanup(case.doCleanups)
            fx = case.fx
            operation = 'document.line-font-set'
            params = dict(field='visible_edges.style', value=1, expected_options=case.before)
            setter = fx.extension.SetUserPreferenceInteger
        else:
            case = dimension.DimensionFormatTests(); case.setUp(); self.addCleanup(case.doCleanups)
            fx = case
            operation = 'document.dimension-format-set'
            params = case.values()
            setter = fx.extension.SetUserPreferenceToggle
        fx.app.RevisionNumber = '33.5.0'; fx.app.GetProcessID = lambda: 1234
        if native_failure:
            setter.side_effect = RuntimeError('first native failure')
        responses, lifecycle = mock.Mock(), mock.Mock()
        request = dict(request_id='late-worker-fault', operation=operation, parameters=params,
                       session_id='writer', document_id=fx.entry.document_id,
                       expected_update_stamp=7, lease_id=fx.lease['lease_id'])
        @contextmanager
        def late_failure(app, *, enabled):
            yield
            if not validation_failure:
                raise NativeCommandRestoreFailed(RuntimeError('late restore failure'), None)
        real_validate = server.validate_operation_result
        def validate(name, value):
            if validation_failure and value.get('ok'):
                raise RuntimeError('late validator failure')
            return real_validate(name, value)
        com, client = mock.Mock(), mock.Mock()
        with mock.patch.dict('sys.modules', {'pythoncom': com, 'win32com': mock.Mock(client=client), 'win32com.client': client}), \
             mock.patch.object(server, 'acquire_resident_app', return_value=(fx.app, True)), \
             mock.patch.object(server, 'wait_windows_host_ready', return_value=0), \
             mock.patch.object(server, 'DocumentRegistry', return_value=fx.documents), \
             mock.patch.object(server, '_describe_app', return_value={}), \
             mock.patch.object(server, '_wait_for_worker_request', side_effect=[request, None]) as wait, \
             mock.patch.object(server, 'native_api_sequence', side_effect=late_failure), \
             mock.patch.object(server, 'validate_operation_result', side_effect=validate), \
             mock.patch.object(windows_dimension_format, '_native_windows', return_value=True):
            server._worker_main(mock.Mock(), responses, lifecycle, False, 120, False)
        responses.put.assert_called_once()
        response = responses.put.call_args.args[0]
        self.assertFalse(response['success'])
        self.assertEqual(response['result']['mutation'], dict(attempted=True, may_have_changed=True))
        if native_failure:
            self.assertEqual(response['result']['error']['message'], 'first native failure')
            self.assertIn('worker_error', response['result']['error'])
        validate_operation_result(operation, response['result'])
        setter.assert_called_once()
        if not validation_failure:
            self.assertEqual(wait.call_count, 1)  # no subsequent CAD request
            self.assertTrue(any(c.args[0].get('event') == 'host-disconnected' for c in lifecycle.put.call_args_list))
        com.CoUninitialize.assert_called_once()

    def test_restore_failure_after_success_or_first_native_failure_keeps_receipt(self):
        for kind in ('line', 'dimension'):
            for native_failure in (False, True):
                with self.subTest(kind=kind, native_failure=native_failure):
                    self.run_worker(kind, native_failure=native_failure)

    def test_late_validator_failure_keeps_actual_changed_receipt(self):
        for kind in ('line', 'dimension'):
            with self.subTest(kind=kind):
                self.run_worker(kind, validation_failure=True)

    def test_untrusted_and_previous_receipts_are_not_fabricated(self):
        for operation in ('document.line-font-set', 'document.dimension-format-set'):
            for result in (None, {}, {'mutation': {'attempted': 1, 'may_have_changed': True}}):
                self.assertNotIn('result', server._preserve_option_receipt({}, operation, result, RuntimeError('fault')))
        self.assertNotIn('result', server._preserve_option_receipt({}, 'document.inspect',
                        dict(mutation=dict(attempted=True, may_have_changed=True)), RuntimeError('fault')))
