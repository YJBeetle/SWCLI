"""Pure tests: no pywin32, no SOLIDWORKS, no helper process."""
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('typed_glb_bridge_tested', HERE / 'bridge_control.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
spec = importlib.util.spec_from_file_location('typed_glb_runner_tested', HERE / 'run-typed-glb-control.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Duplex:
    def __init__(self, messages):
        self.input = io.BytesIO(b''.join(struct.pack('<I', len(data)) + data for data in
                                      (json.dumps(m).encode() for m in messages)))
        self.output = io.BytesIO()
    def read(self, length):
        return self.input.read(min(length, 7))
    def write(self, data):
        return self.output.write(data[:5])
    def flush(self):
        pass
    def sent(self):
        self.output.seek(0)
        rows = []
        while self.output.tell() < len(self.output.getvalue()):
            length, = struct.unpack('<I', self.output.read(4))
            rows.append(json.loads(self.output.read(length)))
        return rows


class ProtocolTests(unittest.TestCase):
    nonce = 'a' * 64
    expected = dict(pid=123)
    payloads = {role: b'PRIVATE-OBJREF-'+role.encode() for role in bridge.ROLES}
    def ledger(self):
        ledger = bridge.ParcelLedger()
        for role in bridge.ROLES:
            ledger.transition(role, 'not_marshaled', 'marshaled')
        return ledger
    def messages(self, mode='invoke'):
        rows = [dict(kind='ready', nonce=self.nonce)]
        for role in bridge.ROLES:
            rows += [dict(kind=kind, nonce=self.nonce, role=role) for kind in ('prepared', 'consumed')]
        receipt = dict(contract_accepted=True, identity_accepted=True, save_attempts=0, before=self.expected)
        rows.append(dict(kind='identity', nonce=self.nonce, receipt=receipt))
        rows.append(dict(kind='result', nonce=self.nonce, receipt=dict(success=True, save_attempts=0 if mode=='identity' else 1)))
        return rows
    def run_session(self, messages, mode='invoke'):
        stream, ledger, receipt = Duplex(messages), self.ledger(), {}
        bridge.io_session(stream, self.nonce, mode, self.expected, 'original-stage.GLB', self.payloads, ledger, receipt)
        return stream, ledger, receipt
    def test_normal_one_use_and_exact_staging(self):
        stream, ledger, receipt = self.run_session(self.messages())
        sent = stream.sent()
        self.assertEqual([m['kind'] for m in sent], ['hello','parcel','consume','parcel','consume','parcel','consume','invoke'])
        self.assertEqual(sent[0]['output'], 'original-stage.GLB')
        self.assertEqual([m['role'] for m in sent if m['kind']=='consume'], list(bridge.ROLES))
        self.assertEqual(ledger.states, dict.fromkeys(bridge.ROLES, 'consumed'))
        self.assertEqual(ledger.releasable(), [])
        self.assertEqual(ledger.uncertain(), [])
        self.assertEqual(receipt['helper_result']['save_attempts'], 1)
        self.assertNotIn('PRIVATE-OBJREF', json.dumps(receipt))
    def test_identity_mode_cannot_send_invoke(self):
        stream, _, receipt = self.run_session(self.messages('identity'), mode='identity')
        self.assertEqual(stream.sent()[-1]['kind'], 'finish')
        self.assertEqual(receipt['helper_result']['save_attempts'], 0)
    def test_ack_loss_never_releases_uncertain_packet(self):
        for count, consumed, uncertain, releasable in (
                (0, [], [], list(bridge.ROLES)),
                (2, [], ['app'], ['document','extension']),
                (4, ['app'], ['document'], ['extension']),
                (6, ['app','document'], ['extension'], [])):
            with self.subTest(messages=count):
                stream, ledger = Duplex(self.messages()[:count]), self.ledger()
                with self.assertRaises(EOFError):
                    bridge.io_session(stream, self.nonce, 'invoke', self.expected, 's.GLB', self.payloads, ledger, {})
                self.assertEqual([role for role,state in ledger.states.items() if state=='consumed'], consumed)
                self.assertEqual(ledger.uncertain(), uncertain)
                self.assertEqual(ledger.releasable(), releasable)
                self.assertNotIn('invoke', [m['kind'] for m in stream.sent()])
    def test_identity_mismatch_stops_at_zero(self):
        messages = self.messages()
        messages[-2]['receipt']['before'] = dict(pid=456)
        stream, ledger = Duplex(messages), self.ledger()
        with self.assertRaisesRegex(RuntimeError, 'identity gate'):
            bridge.io_session(stream, self.nonce, 'invoke', self.expected, 's.GLB', self.payloads, ledger, {})
        self.assertNotIn('invoke', [m['kind'] for m in stream.sent()])
        self.assertEqual(ledger.uncertain(), [])
    def test_early_terminal_result_preserves_helper_first_error_without_invoke(self):
        result=dict(success=False,first_error='System.IO.IOException: source sharing violation',hresult=-2147024864,
                    save_attempts=0,identity_accepted=False)
        for mode in ('identity','invoke'):
            with self.subTest(mode=mode):
                rows=self.messages(mode)[:7]+[dict(kind='result',nonce=self.nonce,receipt=result)]
                stream,ledger,receipt=Duplex(rows),self.ledger(),{}
                with self.assertRaises(bridge.HelperTerminated) as caught:
                    bridge.io_session(stream,self.nonce,mode,self.expected,'s.GLB',self.payloads,ledger,receipt)
                self.assertEqual(caught.exception.receipt,result)
                self.assertIn('System.IO.IOException',str(caught.exception))
                self.assertIn('-2147024864',str(caught.exception))
                self.assertEqual(receipt['helper_result'],result)
                self.assertEqual(receipt['protocol_terminal']['awaiting'],'identity')
                self.assertEqual(ledger.states,dict.fromkeys(bridge.ROLES,'consumed'))
                self.assertFalse(any(m['kind'] in ('finish','invoke') for m in stream.sent()))
    def test_terminal_result_during_consume_ack_keeps_ownership_uncertain(self):
        rows=self.messages()[:2]+[dict(kind='result',nonce=self.nonce,receipt=dict(success=False,first_error='unmarshal error',save_attempts=0))]
        stream,ledger,receipt=Duplex(rows),self.ledger(),{}
        with self.assertRaises(bridge.HelperTerminated):
            bridge.io_session(stream,self.nonce,'invoke',self.expected,'s.GLB',self.payloads,ledger,receipt)
        self.assertEqual(ledger.uncertain(),['app'])
        self.assertEqual(ledger.releasable(),['document','extension'])
        self.assertEqual([m['kind'] for m in stream.sent()],['hello','parcel','consume'])
    def test_wrong_nonce_terminal_cannot_supply_trusted_first_error(self):
        rows=[dict(kind='result',nonce='wrong',receipt=dict(first_error='untrusted'))]
        stream,ledger,receipt=Duplex(rows),self.ledger(),{}
        with self.assertRaises(RuntimeError) as caught:
            bridge.io_session(stream,self.nonce,'invoke',self.expected,'s.GLB',self.payloads,ledger,receipt)
        self.assertNotIsInstance(caught.exception,bridge.HelperTerminated)
        self.assertNotIn('helper_result',receipt)
        self.assertEqual(ledger.releasable(),list(bridge.ROLES))
    def test_early_success_result_cannot_replace_identity_handshake(self):
        rows=self.messages()[:7]+[dict(kind='result',nonce=self.nonce,receipt=dict(success=True,save_attempts=0))]
        stream,ledger,receipt=Duplex(rows),self.ledger(),{}
        with self.assertRaises(bridge.HelperTerminated):
            bridge.io_session(stream,self.nonce,'invoke',self.expected,'s.GLB',self.payloads,ledger,receipt)
        self.assertNotIn('identity_receipt',receipt)
        self.assertNotIn('invoke',[m['kind'] for m in stream.sent()])
    def test_wrong_role_or_nonce_cannot_allow_consume(self):
        for key, value in (('nonce','b'*64), ('role','document')):
            with self.subTest(key=key):
                messages = self.messages()
                messages[1][key] = value
                stream, ledger = Duplex(messages), self.ledger()
                with self.assertRaises(RuntimeError):
                    bridge.io_session(stream, self.nonce, 'invoke', self.expected, 's.GLB', self.payloads, ledger, {})
                self.assertEqual(ledger.releasable(), list(bridge.ROLES))
                self.assertFalse(any(m['kind']=='consume' for m in stream.sent()))
    def test_frame_limits_and_truncation(self):
        for data in (struct.pack('<I',0), struct.pack('<I',bridge.MAX_FRAME+1), struct.pack('<I',10)+b'{}'):
            with self.subTest(data=data), self.assertRaises((RuntimeError, EOFError)):
                bridge.receive(io.BytesIO(data), self.nonce, 'ready')
    def test_cannot_consume_twice(self):
        ledger = self.ledger()
        ledger.transition('app','marshaled','buffered')
        ledger.transition('app','buffered','consumption_uncertain')
        ledger.transition('app','consumption_uncertain','consumed')
        with self.assertRaises(RuntimeError):
            ledger.transition('app','buffered','consumption_uncertain')


class NativeReceiptTests(unittest.TestCase):
    def result(self, **changes):
        result = dict(success=True, save_attempts=1, api_saved=True, save_errors=0,
                      save_warnings=2, post_state_accepted=True)
        result.update(changes)
        return result
    def test_normal_warn_is_recorded_without_inventing_warning_zero_gate(self):
        receipt = {}
        self.assertIs(bridge.adapt_result(self.result(), receipt), True)
        self.assertEqual(receipt, dict(save_attempted=True, api_saved=True, save_errors=0, save_warnings=2))
    def test_false_or_native_error_retains_original_codes(self):
        for changes in (dict(api_saved=False), dict(save_errors=32), dict(success=False)):
            receipt = {}
            with self.assertRaises(RuntimeError):
                bridge.adapt_result(self.result(**changes), receipt)
            self.assertEqual(receipt['api_saved'], changes.get('api_saved',True))
            self.assertEqual(receipt['save_errors'], changes.get('save_errors',0))
    def test_exceptional_or_unwritten_outs_remain_unknown(self):
        for changes in (dict(api_saved=None, save_errors=None, save_warnings=None), dict(save_warnings=None)):
            receipt = dict(api_saved=False, save_errors=99, save_warnings=99)
            with self.assertRaises(RuntimeError):
                bridge.adapt_result(self.result(**changes), receipt)
            for key,value in changes.items():
                if value is None:
                    self.assertNotIn(key, receipt)
    def test_bool_is_not_integer_code_and_integer_is_not_boolean_result(self):
        for changes in (dict(save_errors=False), dict(save_warnings=True), dict(api_saved=1),dict(save_attempts=True)):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                bridge.adapt_result(self.result(**changes), {})
    def test_two_attempts_or_missing_poststate_rejected(self):
        for changes in (dict(save_attempts=0),dict(save_attempts=2),dict(post_state_accepted=False)):
            with self.assertRaises(RuntimeError):
                bridge.adapt_result(self.result(**changes), {})




class WrapperControlTests(unittest.TestCase):
    def exercise(self, mode='invoke', twice=False):
        documents=types.ModuleType('swcli.hosts.windows_documents')
        original_save=mock.Mock(return_value=True)
        documents.save_as3=original_save
        trace=types.ModuleType('swcli.hosts.native_trace')
        trace.native_call=lambda stage,name,fn: fn()
        hosts=types.ModuleType('swcli.hosts'); hosts.windows_documents=documents
        package=types.ModuleType('swcli'); package.hosts=hosts
        source_alias=original_save
        case=dict(outputs=[dict(format=fmt,result=dict(ok=True)) for fmt in ('STL','3MF','AMF')],source_sha256='source')
        report=dict(host=dict(process_id=777))
        result=dict(success=True, save_attempts=0 if mode=='identity' else 1, api_saved=True,
                    save_errors=0,save_warnings=0,post_state_accepted=True)
        existing_app,existing_doc=object(),object()
        output=Path('/original-fixture')
        def original_case(app, out, constants, plane, reverse, call, case, report, live, **kwargs):
            self.assertIs(app,existing_app); self.assertEqual(out,output)
            self.assertEqual((plane,reverse),('front',False))
            for fmt in ('STL','3MF','AMF'):
                documents.save_as3(existing_doc,str(output/('component-export.'+fmt)),receipt={},stage='document-export')
            receipt={}
            documents.save_as3(existing_doc,str(output/('.component-export.'+'a'*32+'.swcli.GLB')),receipt=receipt,stage='document-export')
            if twice:
                documents.save_as3(existing_doc,str(output/('.component-export.'+'b'*32+'.swcli.GLB')),receipt=receipt,stage='document-export')
            return receipt
        def run(out, constants, visible, **kwargs):
            return kwargs['case_runner'](existing_app,out,constants,'front',False,None,case,report,{})
        baseline=types.SimpleNamespace(module=types.SimpleNamespace(harness=types.SimpleNamespace(run=run)))
        def invoke(*args):
            self.assertIs(args[0],existing_app); self.assertIs(args[1],existing_doc)
            self.assertEqual(args[-1],777)
            args[-2].update(helper_result=result)
            return result
        modules={'swcli':package,'swcli.hosts':hosts,'swcli.hosts.windows_documents':documents,'swcli.hosts.native_trace':trace}
        with mock.patch.dict(sys.modules,modules), mock.patch.object(runner.bridge,'invoke_existing',side_effect=invoke) as bridge_call:
            runner.install_call_control(baseline,Path('/reviewed/helper.exe'),mode,{})
            if mode=='identity' or twice:
                with self.assertRaises(RuntimeError):
                    baseline.module.harness.run(output,None,False,case_runner=original_case,case_plan=[('part','front',False)])
                receipt=None
            else:
                receipt=baseline.module.harness.run(output,None,False,case_runner=original_case,case_plan=[('part','front',False)])
            self.assertEqual(bridge_call.call_count,1)
        self.assertIs(documents.save_as3,original_save)
        self.assertIs(source_alias,original_save)
        self.assertEqual(original_save.call_count,3)
        self.assertEqual([Path(c.args[1]).suffix for c in original_save.call_args_list],['.STL','.3MF','.AMF'])
        return receipt,report
    def test_preserves_prior_exports_and_restores_alias(self):
        receipt,report=self.exercise()
        self.assertEqual(receipt,dict(save_attempted=True,api_saved=True,save_errors=0,save_warnings=0))
        self.assertEqual(report['typed_glb_control']['binding_entries'],1)
    def test_zero_save_handshake_stops_and_restores_alias(self):
        _,report=self.exercise(mode='identity')
        self.assertTrue(report['typed_glb_control']['identity_only_accepted'])
    def test_second_glb_is_refused_without_fallback(self):
        self.exercise(twice=True)

class OfflineAuditTests(unittest.TestCase):
    def fixture(self, root, mode):
        folder = root / 'typed-glb'
        folder.mkdir()
        phases = ['handshake'] if mode == 'identity' else ['handshake','before-save','after-normal-return']
        expected = dict(pid=777)
        helper = dict(success=True, identity_accepted=True, save_attempts=0 if mode=='identity' else 1,
                      helper_pid=222, python_worker_pid=111, before=expected, after=expected,
                      post_state_accepted=mode=='invoke', api_saved=True, save_errors=0, save_warnings=2,
                      arguments=dict(name='original.GLB', version=0, options=1),
                      identity_checks=[dict(phase=p, document_iunknown_same=True, extension_iunknown_same=True,
                                            foreground_same=1) for p in phases])
        (folder/'helper.json').write_text(json.dumps(helper))
        helper_trace = [] if mode=='identity' else [dict(event='typed-glb.native-call', phase=p, helper_pid=222,
                                                        call='IModelDocExtension.SaveAs3') for p in ('begin','end')]
        (folder/'helper-native.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in helper_trace))
        producer = dict(success=True, marshal_cleanup_known=True, expected=expected, output='original.GLB',
                        helper_pid=222, python_worker_pid=111, helper_result=helper,
                        helper_receipt_sha256=bridge.digest(folder/'helper.json'),
                        helper_trace_sha256=bridge.digest(folder/'helper-native.jsonl'))
        (folder/'producer.json').write_text(json.dumps(producer))
        report = dict(success=mode=='invoke', cleanup_errors=[], native_call_worker_pid=111,
                      host=dict(process_id=777), cases=[dict(glb_mesh=dict(valid=True))],
                      typed_glb_control=dict(binding_entries=1, producer=producer, identity_only_accepted=mode=='identity'))
        (root/'report.json').write_text(json.dumps(report))
        (root/'local-supervisor.json').write_text(json.dumps(dict(pids_before=[], pids_after=[], worker_pid=333,
                                                                report_sha256=bridge.digest(root/'report.json'))))
        rows=[]
        for fmt in ('STL','3MF','AMF','GLB'):
            call = 'IModelDocExtension.SaveAs3' if fmt!='GLB' else ('CSharpBridge.IdentityOnly' if mode=='identity' else 'CSharpBridge.SaveAs3')
            rows.extend(dict(event='swcli.native-call',request_id='local-export-'+fmt, call=call, phase=p,
                             worker_pid=111) for p in ('begin','end'))
        (root/'worker.stderr.log').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return folder
    def test_identity_success_keeps_failed_fixture_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.fixture(root,'identity')
            result=runner.offline_audit(root,'identity')
            self.assertTrue(result['success'])
            self.assertFalse(json.loads((root/'report.json').read_text())['success'])
            self.assertFalse(result['identity_only_is_export_acceptance'])
            self.assertEqual(result['helper_save_attempts'],0)
    def test_invoke_success_requires_original_worker_and_native_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder=self.fixture(root,'invoke')
            self.assertTrue(runner.offline_audit(root,'invoke')['success'])
            (folder/'helper-native.jsonl').write_text('')
            self.assertFalse(runner.offline_audit(root,'invoke')['success'])
    def test_cleanup_or_unknown_producer_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.fixture(root,'identity')
            supervisor=json.loads((root/'local-supervisor.json').read_text())
            supervisor['pids_after']=[777]
            (root/'local-supervisor.json').write_text(json.dumps(supervisor))
            self.assertFalse(runner.offline_audit(root,'identity')['success'])
    def test_duplicate_bridge_attempt_is_not_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.fixture(root,'identity')
            extra=root/'extra'/'typed-glb'; extra.mkdir(parents=True)
            (extra/'producer.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'more than one'):
                runner.offline_audit(root,'identity')

if __name__ == '__main__':
    unittest.main()
