"""Actual worker path retains font mutation evidence after context/validation faults."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from unittest import mock
import unittest

import test_document_font_scopes as portable
from swcli.daemon import server
from swcli.hosts.native_sequence import NativeCommandRestoreFailed
from swcli.hosts import windows_document_font_scopes as adapter
from swcli.result_schemas import validate_operation_result


class FontWorkerPostflightTests(unittest.TestCase):
    def setUp(self):
        self.fixture = portable.FontScopeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.app.RevisionNumber = lambda: '33.5.0'
        self.fixture.app.GetProcessID = lambda: 1234

    def worker(self, *, restore_error=False, validation_error=False):
        fixture = self.fixture
        request = dict(request_id='font-worker-once', operation='document.font-scope-set',
            parameters=dict(scope='notes', field='bold', value=True, expected_fonts=fixture.fonts()),
            session_id='writer', document_id=fixture.entry.document_id,
            expected_update_stamp=7, lease_id=fixture.lease['lease_id'])
        @contextmanager
        def sequence(*args, **kwargs):
            yield
            if restore_error:
                raise NativeCommandRestoreFailed(RuntimeError('restore failed'), None)
        responses, lifecycle = mock.Mock(), mock.Mock()
        pythoncom, client = mock.Mock(), mock.Mock()
        validation = mock.patch.object(server, 'validate_operation_result', side_effect=RuntimeError('validator postflight failed')) if validation_error else nullcontext()
        with mock.patch.dict('sys.modules', {'pythoncom':pythoncom, 'win32com':mock.Mock(client=client), 'win32com.client':client}), \
                mock.patch.object(server,'acquire_resident_app',return_value=(fixture.app,True)), \
                mock.patch.object(server,'wait_windows_host_ready',return_value=0), \
                mock.patch.object(server,'DocumentRegistry',return_value=fixture.registry), \
                mock.patch.object(server,'_describe_app',return_value={'process_id':1234}), \
                mock.patch.object(server,'_wait_for_worker_request',side_effect=[request,None]), \
                mock.patch.object(server,'native_api_sequence',side_effect=sequence), \
                mock.patch.object(adapter,'_native_windows_runtime',return_value=True), validation:
            server._worker_main(mock.Mock(),responses,lifecycle,False,120,False)
        self.assertEqual(responses.put.call_count,1)
        return responses.put.call_args.args[0], lifecycle

    def test_restore_error_after_real_setter_returns_partial_result_and_recovery_event(self):
        response, lifecycle = self.worker(restore_error=True)
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'],'NativeCommandRestoreFailed')
        self.assertEqual(response['result']['mutation'],dict(attempted=True,may_have_changed=True))
        self.assertFalse(response['result']['ok'])
        self.assertTrue(self.fixture.native['notes']['Bold'])
        self.assertTrue(self.fixture.modified)
        self.fixture.extension.SetUserPreferenceTextFormat.assert_called_once()
        validate_operation_result('document.font-scope-set',response['result'])
        self.assertTrue(any(call.args[0].get('event')=='host-disconnected' for call in lifecycle.put.call_args_list))

    def test_restore_fault_does_not_replace_first_native_font_error(self):
        self.fixture.extension.SetUserPreferenceTextFormat.side_effect=RuntimeError('first native error')
        response,_=self.worker(restore_error=True)
        self.assertEqual(response['result']['error']['message'],'first native error')
        self.assertTrue(response['result']['mutation']['may_have_changed'])
        self.assertIn('restore failed',response['result']['warnings'][0]['message'])
        self.fixture.extension.SetUserPreferenceTextFormat.assert_called_once()

    def test_later_predispatch_fault_cannot_reuse_previous_request_receipt(self):
        fixture = self.fixture
        responses, lifecycle = mock.Mock(), mock.Mock()
        index = [0]
        def request(*args):
            index[0] += 1
            if index[0] > 2:
                return None
            return dict(request_id='font-worker-' + str(index[0]), operation='document.font-scope-set',
                parameters=dict(scope='notes', field='bold', value=index[0] == 1, expected_fonts=fixture.fonts()),
                session_id='writer', document_id=fixture.entry.document_id,
                expected_update_stamp=7, lease_id=fixture.lease['lease_id'])
        entered = [0]
        @contextmanager
        def sequence(*args, **kwargs):
            entered[0] += 1
            if entered[0] == 2:
                raise RuntimeError('before second native dispatch')
            yield
        pythoncom, client = mock.Mock(), mock.Mock()
        with mock.patch.dict('sys.modules', {'pythoncom':pythoncom, 'win32com':mock.Mock(client=client), 'win32com.client':client}), \
                mock.patch.object(server,'acquire_resident_app',return_value=(fixture.app,True)), \
                mock.patch.object(server,'wait_windows_host_ready',return_value=0), \
                mock.patch.object(server,'DocumentRegistry',return_value=fixture.registry), \
                mock.patch.object(server,'_describe_app',return_value={'process_id':1234}), \
                mock.patch.object(server,'_wait_for_worker_request',side_effect=request), \
                mock.patch.object(server,'native_api_sequence',side_effect=sequence), \
                mock.patch.object(adapter,'_native_windows_runtime',return_value=True):
            server._worker_main(mock.Mock(),responses,lifecycle,False,120,False)
        values = [call.args[0] for call in responses.put.call_args_list]
        self.assertTrue(values[0]['success'])
        self.assertFalse(values[1]['success'])
        self.assertNotIn('result', values[1])
        fixture.extension.SetUserPreferenceTextFormat.assert_called_once()

    def test_validation_fault_after_real_write_cannot_erase_mutation(self):
        response,_=self.worker(validation_error=True)
        self.assertFalse(response['success'])
        self.assertEqual(response['result']['mutation'],dict(attempted=True,may_have_changed=True))
        self.assertEqual(response['result']['error']['message'],'validator postflight failed')
        self.assertTrue(self.fixture.native['notes']['Bold'])
        self.assertTrue(self.fixture.modified)
        self.fixture.extension.SetUserPreferenceTextFormat.assert_called_once()


if __name__=='__main__':
    unittest.main()
