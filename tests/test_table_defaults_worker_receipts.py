"""Portable real handler/worker flow after adapter receipts; no CAD process starts."""

from copy import deepcopy
import unittest
from unittest import mock

from swcli.daemon import operations, server
from tests import test_document_tables as fixtures


class TableWorkerReceiptTests(unittest.TestCase):
    def test_success_and_first_business_failure_retain_partial_receipts_through_worker(self):
        for business_failure in (False, True):
            with self.subTest(business_failure=business_failure):
                fixture = fixtures.DocumentTableTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                fixture.app.GetProcessID = lambda: 1234
                fixture.app.CommandInProgress = False
                before = fixture.read()['options']
                after = deepcopy(before)
                after['bom.box_border'] = dict(value='thick', native_value=2)
                receipt = dict(ok=not business_failure, action='document.table-option-set', field='bom.box_border',
                               before=before, mutation=dict(attempted=True, may_have_changed=True), native_returned=not business_failure)
                if business_failure:
                    receipt['error'] = dict(type='NativeTableFailure', message='first native business failure')
                else:
                    receipt.update(changed=True, options=after)
                state = dict(adapter_calls=0, descriptor_calls_after_adapter=0)
                original_describe = fixture.documents.describe
                def describe(*args, **kwargs):
                    if state['adapter_calls']:
                        state['descriptor_calls_after_adapter'] += 1
                        raise RuntimeError('post-adapter descriptor failed')
                    return original_describe(*args, **kwargs)
                def adapter(**kwargs):
                    state['adapter_calls'] += 1
                    return receipt
                request = dict(request_id='table-receipt-worker', operation='document.table-option-set',
                    parameters=dict(field='bom.box_border', value='thick', expected_options=before),
                    session_id='writer', document_id=fixture.entry.document_id, expected_update_stamp=7,
                    lease_id=fixture.lease, timeout_ms=600000)
                pythoncom, com_client = mock.Mock(), mock.Mock()
                responses, lifecycle = mock.Mock(), mock.Mock()
                with mock.patch.dict('sys.modules', {'pythoncom': pythoncom,
                        'win32com': mock.Mock(client=com_client), 'win32com.client': com_client}), \
                     mock.patch.object(server, 'acquire_resident_app', return_value=(fixture.app, True)) as acquire, \
                     mock.patch.object(server, 'wait_windows_host_ready', return_value=0), \
                     mock.patch.object(server, 'DocumentRegistry', return_value=fixture.documents), \
                     mock.patch.object(server, '_describe_app', return_value={'process_id': 1234}), \
                     mock.patch.object(server, '_wait_for_worker_request', side_effect=[request, None]) as wait, \
                     mock.patch.object(fixture.documents, 'describe', side_effect=describe), \
                     mock.patch.object(operations, 'set_document_table_option_windows', side_effect=adapter), \
                     mock.patch.object(server, 'validate_operation_result', wraps=server.validate_operation_result) as validate:
                    server._worker_main(mock.Mock(), responses, lifecycle, False, 120, False)
                self.assertEqual(state['adapter_calls'], 1)
                self.assertEqual(state['descriptor_calls_after_adapter'], 0 if business_failure else 1)
                acquire.assert_called_once()
                self.assertEqual(wait.call_count, 2)
                validate.assert_called_once()
                self.assertFalse(fixture.app.CommandInProgress)
                pythoncom.CoUninitialize.assert_called_once()
                responses.put.assert_called_once()
                response = responses.put.call_args.args[0]
                self.assertFalse(response['success'])
                self.assertEqual(response['request_id'], request['request_id'])
                self.assertEqual(response['result']['mutation'], dict(attempted=True, may_have_changed=True))
                self.assertNotIn('document', response['result'])
                self.assertEqual(response['result']['before'], before)
                if business_failure:
                    self.assertEqual(response['error']['code'], 'NativeTableFailure')
                    self.assertEqual(response['result']['error'], dict(type='NativeTableFailure', message='first native business failure'))
                else:
                    self.assertEqual(response['error']['code'], 'RuntimeError')
                    self.assertEqual(response['result']['error']['message'], 'post-adapter descriptor failed')
                    self.assertTrue(response['result']['changed'])
                    self.assertEqual(response['result']['options'], after)
