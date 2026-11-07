"""Real handler/adapter/registry/worker paths, portable postflight fault injection."""
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import test_document_annotation_fonts as ft
import test_document_display_options as dt
import test_document_drafting_standard as st
from swcli.daemon import operations, server
from swcli.daemon.documents import DocumentRegistry
from swcli.hosts import windows_document_drafting_standard as standard_adapter
from swcli.result_schemas import validate_operation_result
from swcli.hosts.native_sequence import NativeCommandRestoreFailed

class RestoreFaultApp:
    def __init__(self, original):
        self.original=original;self.command=False
    def __getattr__(self,name):return getattr(self.original,name)
    @property
    def CommandInProgress(self):return self.command
    @CommandInProgress.setter
    def CommandInProgress(self,value):
        if value is False:raise RuntimeError('late restore failure')
        self.command=value

class PreferenceReceiptFaults(unittest.TestCase):
    def fixture(self, kind, restore=False):
        cls={'fonts':ft.DocumentAnnotationFontTests,'display':dt.DocumentDisplayOptionsTests,'standards':st.DocumentDraftingStandardTests}[kind]
        f=cls();f.setUp();self.addCleanup(f.doCleanups)
        f.app.RevisionNumber='33.5.0';f.app.GetProcessID=lambda:1234
        f.app.GetDocuments=lambda:(f.document,f.foreground)
        if restore:f.app=RestoreFaultApp(f.app)
        docs=DocumentRegistry(f.app);entry=docs.register(f.document);lease=docs.acquire_lease(entry,session_id='writer',ttl_seconds=600)
        if kind=='fonts':
            operation='document.annotation-font-set';params={'field':'bold','value':True,'expected_font':f.expected};setter=f.extension.SetUserPreferenceTextFormat
        elif kind=='display':
            operation='document.display-option-set';params={'field':'grid.display','value':True,'expected_value':False};setter=f.extension.SetUserPreferenceToggle
        else:
            operation='document.drafting-standard-set';params={'value':'iso','expected_snapshot':f.expected()};setter=f.extension.SetUserPreferenceInteger
        request={'request_id':'receipt-fault','operation':operation,'parameters':params,'session_id':'writer','document_id':entry.document_id,'expected_update_stamp':f.stamp,'lease_id':lease['lease_id']}
        return f,docs,request,setter

    def test_descriptor_fault_keeps_success_or_native_first_error_and_mutation(self):
        for kind in ('fonts','display','standards'):
            for native_failure in (False,True):
                with self.subTest(kind=kind,native_failure=native_failure):
                    f,docs,request,setter=self.fixture(kind)
                    if native_failure:setter.side_effect=RuntimeError('first native failure')
                    describe=docs.describe;calls=[]
                    def descriptor(*args,**kwargs):
                        calls.append(True)
                        if len(calls)>1:raise RuntimeError('secondary descriptor failure')
                        return describe(*args,**kwargs)
                    with patch.object(docs,'describe',side_effect=descriptor),patch.object(standard_adapter,'_require_calibrated_native_host',return_value=None):
                        result=operations.execute_operation(f.app,request['operation'],request['parameters'],documents=docs,**{k:request[k] for k in ('session_id','document_id','expected_update_stamp','lease_id')})
                    self.assertFalse(result['ok']);self.assertEqual(result['mutation'],{'attempted':True,'may_have_changed':True})
                    self.assertEqual(result['error']['descriptor_error']['message'],'secondary descriptor failure')
                    if native_failure:self.assertEqual(result['error']['message'],'first native failure')
                    validate_operation_result(request['operation'],result);setter.assert_called_once()

    def worker(self,kind,native_failure=False,validator_failure=False,poison=False):
        f,docs,request,setter=self.fixture(kind,restore=not validator_failure)
        if native_failure:setter.side_effect=RuntimeError('first native failure')
        responses,lifecycle=Mock(),Mock();com,client=Mock(),Mock()
        validate=server.validate_operation_result
        def validator(name,value):
            if validator_failure and value.get('ok'):
                if poison:value['document']={'broken':True}
                raise RuntimeError('late validator failure')
            return validate(name,value)
        @contextmanager
        def no_sequence(*args,**kwargs):yield
        context=patch.object(server,'native_api_sequence',side_effect=no_sequence) if validator_failure else nullcontext()
        with patch.dict('sys.modules',{'pythoncom':com,'win32com':Mock(client=client),'win32com.client':client}),patch.object(server,'acquire_resident_app',return_value=(f.app,True)),patch.object(server,'wait_windows_host_ready',return_value=0),patch.object(server,'DocumentRegistry',return_value=docs),patch.object(server,'_describe_app',return_value={}),patch.object(server,'_wait_for_worker_request',side_effect=[request,None]) as wait,patch.object(server,'validate_operation_result',side_effect=validator),patch.object(standard_adapter,'_require_calibrated_native_host',return_value=None),context:
            server._worker_main(Mock(),responses,lifecycle,False,120,False)
        responses.put.assert_called_once();response=responses.put.call_args.args[0]
        self.assertFalse(response['success']);self.assertEqual(response['result']['mutation'],{'attempted':True,'may_have_changed':True})
        error=response['result']['error']
        if native_failure:
            self.assertEqual(error['message'],'first native failure');self.assertIn('worker_error',error)
        else:self.assertIn('validator' if validator_failure else 'restore',error['message'])
        validate_operation_result(request['operation'],response['result']);setter.assert_called_once()
        if not validator_failure:
            self.assertEqual(wait.call_count,1)
            self.assertTrue(any(c.args[0].get('event')=='host-disconnected' for c in lifecycle.put.call_args_list))
        com.CoUninitialize.assert_called_once()

    def test_real_sequence_restore_fault_after_success_and_native_failure(self):
        for kind in ('fonts','display','standards'):
            for failure in (False,True):
                with self.subTest(kind=kind,native_failure=failure):self.worker(kind,native_failure=failure)

    def test_worker_late_validator_keeps_actual_receipt(self):
        for kind in ('fonts','display','standards'):
            for poison in (False,True):
                with self.subTest(kind=kind,poison=poison):self.worker(kind,validator_failure=True,poison=poison)

    def test_untrusted_receipts_are_not_fabricated(self):
        for op in ('document.annotation-font-set','document.display-option-set','document.drafting-standard-set'):
            for value in (None,{}, {'action':op,'mutation':{'attempted':1,'may_have_changed':True}}, {'action':'document.inspect','mutation':{'attempted':True,'may_have_changed':True}}):
                self.assertNotIn('result',server._preserve_preference_receipt({},op,value,RuntimeError('late fault')))


    def test_descriptor_fault_after_noop_preserves_zero_write_boundary(self):
        for kind in ('fonts','display','standards'):
            with self.subTest(kind=kind):
                f,docs,request,setter=self.fixture(kind)
                request['parameters']['value']='gb' if kind=='standards' else False
                describe=docs.describe;count=[0]
                def descriptor(*args,**kwargs):
                    count[0]+=1
                    if count[0]>1:raise RuntimeError('descriptor after no-op')
                    return describe(*args,**kwargs)
                with patch.object(docs,'describe',side_effect=descriptor),patch.object(standard_adapter,'_require_calibrated_native_host',return_value=None):
                    result=operations.execute_operation(f.app,request['operation'],request['parameters'],documents=docs,**{k:request[k] for k in ('session_id','document_id','expected_update_stamp','lease_id')})
                self.assertFalse(result['ok']);self.assertEqual(result['mutation'],{'attempted':False,'may_have_changed':False})
                self.assertFalse(result['changed']);setter.assert_not_called();f.document.SetSaveFlag.assert_not_called()
                validate_operation_result(request['operation'],result)

    def test_second_request_enter_failure_never_reuses_first_request_receipt(self):
        for kind in ('fonts','display','standards'):
            with self.subTest(kind=kind):
                f,docs,request,setter=self.fixture(kind)
                second=dict(request,request_id='not-executed')
                responses,lifecycle=Mock(),Mock();com,client=Mock(),Mock();entries=[0]
                @contextmanager
                def sequence(app,*,enabled):
                    entries[0]+=1
                    if entries[0]==2:raise NativeCommandRestoreFailed(RuntimeError('enter/restore unknown'),None)
                    yield
                with patch.dict('sys.modules',{'pythoncom':com,'win32com':Mock(client=client),'win32com.client':client}),patch.object(server,'acquire_resident_app',return_value=(f.app,True)),patch.object(server,'wait_windows_host_ready',return_value=0),patch.object(server,'DocumentRegistry',return_value=docs),patch.object(server,'_describe_app',return_value={}),patch.object(server,'_wait_for_worker_request',side_effect=[request,second,None]) as wait,patch.object(server,'native_api_sequence',side_effect=sequence),patch.object(standard_adapter,'_require_calibrated_native_host',return_value=None):
                    server._worker_main(Mock(),responses,lifecycle,False,120,False)
                self.assertEqual(responses.put.call_count,2)
                first,response=[c.args[0] for c in responses.put.call_args_list]
                self.assertTrue(first['success']);self.assertTrue(first['result']['mutation']['attempted'])
                self.assertFalse(response['success']);self.assertNotIn('result',response)
                self.assertEqual(response['request_id'],'not-executed');setter.assert_called_once()
                self.assertEqual(wait.call_count,2)
                self.assertTrue(any(c.args[0].get('event')=='host-disconnected' for c in lifecycle.put.call_args_list))
