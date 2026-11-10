"""Actual fresh CLI versus isolated CLI frontend over real TCP; no native CAD proof."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from swcli import __version__,cli
from swcli.daemon.server import validate_request
from test_unit_profile_public_gate import profile
from test_unit_profile_write_public import public

frontend=public.frontend


class CLIFrontendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.requests=[];self.mode='success';self.received=threading.Event();outer=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(handler):
                request=json.loads(handler.rfile.readline());outer.requests.append(request);outer.received.set()
                reply=dict(api_version='swcli/v1',request_id=request['request_id'],duration_ms=0.0)
                try:validate_request(request)
                except ValueError as error:reply.update(success=False,error=dict(code='ValueError',message=str(error)))
                else:
                    before=profile(1);document=dict(document_id='d-012345',title='part',path='',type=1,update_stamp=103,modified=False,active=False,current=False)
                    result=dict(ok=True,action=request['operation'],session_id=request['session_id'],document=document,unit_profile=before)
                    if outer.mode=='delay':time.sleep(0.2)
                    if request['operation']=='document.unit-profile-set':
                        if outer.mode in ('DocumentLeaseConflict','DocumentUpdateConflict','DocumentUnitProfileConflict','ValueError','UnitProfileCalibrationRequired','partial'):
                            result=dict(ok=False,error=dict(type='NativeFailure' if outer.mode=='partial' else outer.mode,message='native partial' if outer.mode=='partial' else 'expected refusal'),mutation=dict(attempted=outer.mode=='partial',may_have_changed=outer.mode=='partial'))
                            if outer.mode=='partial':result.update(before=before,native_return_value=False,raw_double=float.fromhex('0x1.0000000000001p-40'),raw_hex='0x1.0000000000001p-40')
                        else:
                            after=deepcopy(before);after['values']['linear.unit']=dict(value='inch',native_value=3);after['native_units']['length_unit']=3
                            result.update(field='linear.unit',before=before,unit_profile=after,changed=True,native_return_value=True,mutation=dict(attempted=True,may_have_changed=True));document.update(update_stamp=104,modified=True)
                    reply.update(success=result['ok'],result=result)
                try:handler.wfile.write(json.dumps(reply).encode()+b'\n')
                except BrokenPipeError:pass
        self.server=socketserver.ThreadingTCPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
        threading.Thread(target=self.server.serve_forever,daemon=True).start();self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.endpoint='127.0.0.1:'+str(self.server.server_address[1]);self.client=frontend.CLIFrontend(self.root);self.addCleanup(self.client.close)

    def argv(self,write=True,value='inch'):
        args=['--endpoint',self.endpoint,'--session','owner','--request-timeout','600','--request-id','frontend-compare', 'document']
        if write:args+=['unit-profile-set','linear.unit',value,'--if-snapshot',json.dumps(profile(1)),'--if-update-stamp','103','--lease','l-0123456789ab']
        else:args+=['unit-profile']
        return args+['--document','d-012345','--json']

    def compare(self,args):
        before=len(self.requests)
        fresh=subprocess.run([sys.executable,'-I','-m','swcli',*args],capture_output=True,timeout=610)
        reused=self.client.invoke(args,timeout=610)
        self.assertEqual((fresh.returncode,fresh.stdout,fresh.stderr),(reused.returncode,reused.stdout,reused.stderr))
        self.assertEqual(len(self.requests)-before,2);self.assertEqual(self.requests[-1],self.requests[-2])
        self.assertEqual(self.requests[-1]['timeout_ms'],600000)
        return json.loads(reused.stdout)

    def test_actual_cli_read_changed_and_all_guard_refusals_match_without_restarts(self):
        pid=self.client.process.pid
        self.assertTrue(self.compare(self.argv(write=False))['ok'])
        self.assertTrue(self.compare(self.argv())['native_return_value'])
        for mode in ('DocumentLeaseConflict','DocumentUpdateConflict','DocumentUnitProfileConflict','ValueError','UnitProfileCalibrationRequired','partial'):
            self.mode=mode;value=self.compare(self.argv());self.assertFalse(value['ok'])
            if mode=='partial':self.assertEqual(value['mutation'],dict(attempted=True,may_have_changed=True));self.assertEqual(value['raw_hex'],'0x1.0000000000001p-40')
        self.assertEqual(self.client.process.pid,pid);self.assertEqual(self.client.metadata['starts'],1)
        self.client.close();self.client.close();self.assertTrue(self.client.metadata['exit_confirmed']);self.assertTrue(self.client.metadata['normal_eof']);self.assertEqual(self.client.metadata['exit_code'],0);self.assertEqual(self.client.metadata['exit_waits'],1)

    def test_protocol_and_parser_failures_match_without_business_rpc(self):
        value=self.compare(self.argv(value='unapproved'));self.assertEqual(value['error']['type'],'ValueError')
        count=len(self.requests);fresh=subprocess.run([sys.executable,'-I','-m','swcli','--not-a-valid-option'],capture_output=True,timeout=30)
        reused=self.client.invoke(['--not-a-valid-option'],timeout=30)
        self.assertEqual((fresh.returncode,fresh.stdout,fresh.stderr),(reused.returncode,reused.stdout,reused.stderr));self.assertEqual(len(self.requests),count)

    def test_timeout_is_unknown_and_never_retried_or_restarted(self):
        self.client.invoke(self.argv(write=False),timeout=10);self.received.clear();self.mode='delay'
        with self.assertRaises(frontend.FrontendError):self.client.invoke(self.argv(write=False),timeout=0.03)
        self.assertTrue(self.received.wait(1));self.assertEqual(len(self.requests),2)
        with self.assertRaises(frontend.FrontendError):self.client.invoke(self.argv(write=False),timeout=1)
        self.assertEqual(len(self.requests),2);self.client.close();self.assertTrue(self.client.metadata['exit_confirmed']);self.assertEqual(self.client.metadata['starts'],1)

    def test_durable_intent_failure_prevents_the_only_request(self):
        with self.assertRaisesRegex(OSError,'disk full'):
            self.client.invoke(self.argv(),timeout=10,before_send=mock.Mock(side_effect=OSError('disk full')))
        self.assertEqual(self.requests,[]);self.assertEqual(self.client.sequence,0)

    def test_durable_reply_failure_keeps_native_partial_bytes_and_sends_once(self):
        received=[];self.mode='partial'
        def fail(raw):received.append(json.loads(raw));raise OSError('reply disk failure')
        with self.assertRaisesRegex(OSError,'reply disk failure'):self.client.invoke(self.argv(),timeout=10,after_receive=fail)
        self.assertEqual(len(self.requests),1);self.assertTrue(json.loads(received[0]['stdout'])['mutation']['may_have_changed'])

    def fault_client(self,body):
        path=self.root/'fault.py'
        prefix="import sys,json,os,time\nfrom swcli import __version__,cli\nfrom pathlib import Path\nimport hashlib\nprint(json.dumps(dict(kind='ready',pid=os.getpid(),swcli_version=__version__,cli_main_sha256=hashlib.sha256(Path(cli.__file__).read_bytes()).hexdigest())),flush=True)\nrequest=json.loads(sys.stdin.readline())\n"
        path.write_text(prefix+body);client=frontend.CLIFrontend(self.root,helper_path=path);self.addCleanup(client.close);return client

    def test_eof_partial_frame_and_wrong_sequence_poison_frontend_and_preserve_bytes(self):
        for body,partial in [("sys.stdout.write('{\\\"kind\\\":');sys.stdout.flush()\n",True),("print(json.dumps(dict(kind='reply',sequence=999,returncode=0,stdout='{}',stderr='',exception=None)),flush=True)\ntime.sleep(2)\n",False)]:
            with self.subTest(body=body):
                client=self.fault_client(body)
                with self.assertRaises(frontend.FrontendError) as caught:client.invoke(self.argv(),timeout=2)
                if partial:self.assertIn('kind',caught.exception.partial_stdout)
                else:self.assertIn('999',caught.exception.raw_frame)
                with self.assertRaises(frontend.FrontendError):client.invoke(self.argv(),timeout=1)
                client.close();self.assertTrue(client.metadata['exit_confirmed'])
        self.assertEqual(self.requests,[])

    def test_gate_cli_intent_and_reply_are_fsynced_and_strategy_is_explicit(self):
        gate=public.WriteGate(directory=self.root,host_directory=str(self.root),endpoint=self.endpoint,request_timeout_seconds=600);self.addCleanup(gate.cleanup)
        value=gate.command('document','unit-profile',document='d-012345');self.assertTrue(value['ok'])
        rows=[json.loads(x) for x in (self.root/'transport-events.jsonl').read_text().splitlines()]
        intent=next(r for r in rows if r['stage']=='cli.frontend.request.started');self.assertEqual(json.loads(intent['event']['cli_frontend_request_json']),intent['event']['cli_frontend_request']);reply=next(r for r in rows if r['stage']=='cli.frontend.reply.received')
        self.assertIn('stdout',json.loads(reply['event']['cli_frontend_reply']));self.assertEqual(gate.record['events'][0]['cli_process_strategy'],'isolated-reused-cli-main')
        gate._cli_frontend.close();self.assertTrue(gate.record['cli_frontend']['exit_confirmed'])

    def test_compact_semantic_checkpoint_preserves_complete_data_and_fails_on_fsync(self):
        gate=public.WriteGate(directory=self.root,host_directory=str(self.root),endpoint=self.endpoint,request_timeout_seconds=600)
        gate.record.update(raw_double=float.fromhex('0x1.0000000000001p-40'),raw_hex='0x1.0000000000001p-40',partial=dict(may_have_changed=True))
        with mock.patch.object(public.os,'fsync',wraps=os.fsync) as sync:gate.checkpoint('complete');sync.assert_called_once()
        self.assertEqual(json.loads(gate.record_path.read_bytes()),gate.record)
        with mock.patch.object(public.os,'fsync',side_effect=OSError('fsync failed')):
            with self.assertRaisesRegex(OSError,'fsync failed'):gate.checkpoint('failed')

    def test_exception_frame_preserves_partial_output_and_never_issues_a_request(self):
        client=self.fault_client("print(json.dumps(dict(kind='reply',sequence=request['sequence'],returncode=1,stdout='native partial bytes',stderr='first exception',exception=dict(type='RuntimeError',message='after dispatch'))),flush=True)\ntime.sleep(2)\n")
        with self.assertRaises(frontend.FrontendError) as caught:client.invoke(self.argv(),timeout=2)
        self.assertIn('native partial bytes',caught.exception.raw_frame);self.assertTrue(caught.exception.outcome_unknown)
        client.close();self.assertEqual(self.requests,[]);self.assertEqual(client.metadata['exit_waits'],1)

    def test_bad_startup_identity_closes_the_only_child_and_records_failure(self):
        path=self.root/'bad-startup.py';path.write_text("import json,os,sys\nprint(json.dumps(dict(kind='ready',pid=os.getpid(),swcli_version='wrong',cli_main_sha256='wrong')),flush=True)\nsys.stdin.read()\n")
        metadata={}
        with mock.patch.object(frontend.subprocess,'Popen',wraps=subprocess.Popen) as popen:
            with self.assertRaisesRegex(ValueError,'identity mismatch'):frontend.CLIFrontend(self.root,helper_path=path,metadata=metadata)
        self.assertEqual(popen.call_count,1);self.assertTrue(metadata['exit_confirmed']);self.assertEqual(metadata['exit_waits'],1);self.assertEqual(self.requests,[])

    def test_later_frontend_cleanup_error_preserves_first_exit_failure_and_records_both(self):
        gate=public.WriteGate(directory=self.root,host_directory=str(self.root),endpoint=self.endpoint,request_timeout_seconds=600)
        gate._clients=mock.Mock();gate._cli_frontend=mock.Mock()
        gate._clients.close.side_effect=RuntimeError('first MCP exit failure');gate._cli_frontend.close.side_effect=RuntimeError('second CLI exit failure')
        with self.assertRaisesRegex(RuntimeError,'first MCP exit failure'):gate.cleanup()
        gate._clients.close.assert_called_once();gate._cli_frontend.close.assert_called_once()
        self.assertEqual([e['message'] for e in gate.record['cleanup_errors']],['first MCP exit failure','second CLI exit failure'])
