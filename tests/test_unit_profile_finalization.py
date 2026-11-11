"""Complete registry/handler/worker fault injection; no native write authorization."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
import unittest
import test_document_unit_profile as fixture
from swcli.daemon import operations,server
from swcli.result_schemas import validate_operation_result

class UnitProfileFinalizationTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixture.UnitProfileTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.fx.app.GetProcessID=lambda:1234
        self.fx.app.RevisionNumber='33.5.0'
    def receipt(self,first_failure):
        before=deepcopy(self.fx.expected);after=deepcopy(before)
        after['values']['linear.unit']=dict(value='inch',native_value=3)
        after['native_units']['length_unit']=3
        result=dict(ok=not first_failure,action='document.unit-profile-set',field='linear.unit',before=before,observed=after,native_return_value=True,mutation=dict(attempted=True,may_have_changed=True))
        if first_failure:result['error']=dict(type='NativeUnitsFailure',message='first native verification failure')
        else:result.update(changed=True,unit_profile=after)
        return result
    def request(self):
        return dict(request_id='unit-partial',operation='document.unit-profile-set',parameters=dict(field='linear.unit',value='inch',expected_snapshot=self.fx.expected),session_id='writer',document_id=self.fx.entry.document_id,expected_update_stamp=7,lease_id=self.fx.lease['lease_id'])
    def failing_descriptor(self):
        original=self.fx.documents.describe;calls=0
        def describe(*args,**kw):
            nonlocal calls
            calls+=1
            if calls==1:return original(*args,**kw)
            raise RuntimeError('post-adapter descriptor failed')
        return describe
    def check_receipt(self,result,first_failure):
        validate_operation_result('document.unit-profile-set',result)
        self.assertFalse(result['ok'])
        self.assertEqual(result['mutation'],dict(attempted=True,may_have_changed=True))
        self.assertIs(result['native_return_value'],True)
        self.assertEqual(result['session_id'],'writer')
        self.assertEqual(result['warnings'][-1]['code'],'document-descriptor-unavailable')
        self.assertIn('post-adapter descriptor failed',result['warnings'][-1]['message'])
        self.assertEqual(result['error']['type'],'NativeUnitsFailure' if first_failure else 'RuntimeError')
        self.assertEqual(result['observed']['native_units']['length_unit'],3)
        if first_failure:self.assertEqual(result['error']['message'],'first native verification failure')
    def test_handler_full_dispatch_preserves_receipt_after_success_or_first_failure(self):
        for failed in (False,True):
            with self.subTest(first_failure=failed):
                with mock.patch.object(operations,'set_document_unit_profile_windows',return_value=self.receipt(failed)) as adapter,mock.patch.object(self.fx.documents,'describe',side_effect=self.failing_descriptor()) as descriptor:
                    req=self.request()
                    result=operations.execute_operation(self.fx.app,req['operation'],req['parameters'],documents=self.fx.documents,session_id='writer',document_id=req['document_id'],expected_update_stamp=7,lease_id=req['lease_id'])
                self.check_receipt(result,failed)
                adapter.assert_called_once();self.assertEqual(descriptor.call_count,2)
    def test_real_worker_carries_partial_receipt_after_descriptor_fault(self):
        for failed in (False,True):
            with self.subTest(first_failure=failed):
                pythoncom,client=mock.Mock(),mock.Mock();responses,lifecycle=mock.Mock(),mock.Mock()
                with mock.patch.dict('sys.modules',{'pythoncom':pythoncom,'win32com':mock.Mock(client=client),'win32com.client':client}),mock.patch.object(server,'acquire_resident_app',return_value=(self.fx.app,False)),mock.patch.object(server,'wait_windows_host_ready',return_value=0),mock.patch.object(server,'DocumentRegistry',return_value=self.fx.documents),mock.patch.object(server,'_describe_app',return_value=dict(process_id=1234)),mock.patch.object(server,'_wait_for_worker_request',side_effect=[self.request(),None]),mock.patch.object(operations,'set_document_unit_profile_windows',return_value=self.receipt(failed)) as adapter,mock.patch.object(self.fx.documents,'describe',side_effect=self.failing_descriptor()) as descriptor:
                    server._worker_main(mock.Mock(),responses,lifecycle,False,120,True)
                response=responses.put.call_args.args[0]
                self.assertFalse(response['success'])
                self.assertEqual(response['request_id'],'unit-partial')
                self.check_receipt(response['result'],failed)
                self.assertEqual(response['error']['code'],'NativeUnitsFailure' if failed else 'RuntimeError')
                adapter.assert_called_once();self.assertEqual(descriptor.call_count,2)
                pythoncom.CoUninitialize.assert_called_once()
                self.assertFalse(any(c.args[0].get('event')=='host-disconnected' for c in lifecycle.put.call_args_list))
    def test_read_handler_descriptor_fault_is_schema_valid_failure(self):
        context=SimpleNamespace(app=self.fx.app,documents=SimpleNamespace(describe=mock.Mock(side_effect=RuntimeError('read descriptor'))),entry=self.fx.entry,session_id='reader')
        result=operations.document_unit_profile(context,{})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['message'],'read descriptor')
        validate_operation_result('document.unit-profile',result)
