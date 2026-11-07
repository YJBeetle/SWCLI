"""Real SDK TCP and optional real MCP stdio to a fake daemon; never CAD evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socketserver
import tempfile
import threading
import unittest
from unittest import mock

from swcli.daemon.server import validate_request
from test_unit_profile_public_gate import profile
from test_unit_profile_write_public import public


class TransportWireTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.requests=[];requests=self.requests
        class Handler(socketserver.StreamRequestHandler):
            def handle(handler):
                req=json.loads(handler.rfile.readline());validate_request(req);requests.append(req)
                envelope=dict(api_version='swcli/v1',request_id=req['request_id'],duration_ms=1.0,success=True)
                if req['operation']=='daemon.capabilities':envelope['result']={'operations':['document.unit-profile-set']}
                elif req['session_id']=='contender':envelope.update(success=False,error={'code':'DocumentLeaseConflict','message':'real owner required'})
                else:
                    before=req['parameters']['expected_snapshot'];after=deepcopy(before)
                    after['values']['linear.unit']={'value':'inch','native_value':3};after['native_units']['length_unit']=3
                    envelope['result']=dict(ok=True,action='document.unit-profile-set',field='linear.unit',before=before,unit_profile=after,changed=True,native_return_value=True,mutation=dict(attempted=True,may_have_changed=True),session_id=req['session_id'],document=dict(title='part',path='',type=1,document_id=req['document_id'],update_stamp=0,modified=True,active=False,current=False))
                handler.wfile.write(json.dumps(envelope).encode()+b'\n')
        self.server=socketserver.ThreadingTCPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        endpoint='127.0.0.1:'+str(self.server.server_address[1])
        self.clients=public.transports.Transports(endpoint,'transport-owner',self.root)
        self.addCleanup(self.clients.close)

    def command(self,session='transport-owner'):
        return ['swcli','--endpoint',self.clients.endpoint,'--session',session,'--request-timeout','600','document','unit-profile-set','linear.unit','inch','--if-snapshot',json.dumps(profile(1)),'--if-update-stamp','0','--document','d-012345','--lease','l-0123456789ab','--json']

    def verify(self,transport):
        request=self.clients.prepare(self.command())
        value,raw,presented=self.clients.invoke(transport,request)
        self.assertTrue(value['ok']);self.assertTrue(value['native_return_value'])
        self.assertEqual(raw['request_id'],request['request_id'])
        self.assertEqual(self.requests[-1]['parameters']['expected_snapshot'],profile(1))
        self.assertEqual(self.requests[-1]['expected_update_stamp'],0)
        self.assertEqual(self.requests[-1]['lease_id'],'l-0123456789ab')
        self.assertEqual(self.requests[-1]['session_id'],'transport-owner')
        if transport=='mcp':
            self.assertEqual(presented['structuredContent'],raw)
            self.assertEqual(json.loads(presented['content'][0]['text']),raw)
            self.assertEqual(self.clients.mcp.info['initialize']['serverInfo']['name'],'swcli')
        request=self.clients.prepare(self.command('contender'))
        value,raw,_=self.clients.invoke(transport,request)
        self.assertFalse(value['ok']);self.assertEqual(value['error']['type'],'DocumentLeaseConflict')
        self.assertFalse(raw['success'])
        self.assertEqual([x['operation'] for x in self.requests].count('document.unit-profile-set'),2)
        self.assertFalse(any(x['operation'] in ('daemon.start','daemon.shutdown') for x in self.requests))

    def test_real_typed_sdk_tcp_preserves_source_lease_zero_stamp_and_refusal(self):self.verify('sdk')

    @unittest.skipUnless(importlib.util.find_spec('mcp'),'optional MCP SDK unavailable')
    def test_real_mcp_stdio_preserves_structured_text_session_cas_and_no_lifecycle(self):self.verify('mcp')

    def test_intent_journal_failure_prevents_sdk_request(self):
        gate=public.WriteGate(directory=self.root,host_directory=str(self.root),endpoint=self.clients.endpoint,request_timeout_seconds=600)
        gate.transport='sdk'
        with mock.patch.object(public.os,'fsync',side_effect=OSError('journal disk failure')):
            with self.assertRaises(OSError):gate.command('document','unit-profile-set','linear.unit','inch','--if-snapshot',json.dumps(profile(1)),'--if-update-stamp',0,document='d-012345',lease='l-0123456789ab')
        self.assertEqual(self.requests,[])

    def test_reply_journal_failure_preserves_successful_wire_receipt_without_retry(self):
        gate=public.WriteGate(directory=self.root,host_directory=str(self.root),endpoint=self.clients.endpoint,request_timeout_seconds=600)
        gate.transport='sdk';calls=0;original=public.os.fsync
        def fsync(fd):
            nonlocal calls
            calls+=1
            if calls==3:raise OSError('reply journal failure')
            return original(fd)
        with mock.patch.object(public.os,'fsync',side_effect=fsync):
            with self.assertRaisesRegex(OSError,'reply journal failure'):
                gate.command('document','unit-profile-set','linear.unit','inch','--if-snapshot',json.dumps(profile(1)),'--if-update-stamp',0,document='d-012345',lease='l-0123456789ab')
        self.assertEqual(len(self.requests),1)
        self.assertTrue(gate.record['events'][-1]['wire_response']['result']['native_return_value'])
        gate.clients().close()

    def test_protocol_validator_failure_keeps_raw_success_receipt_and_does_not_retry(self):
        from swcli.sdk import ProtocolError
        gate=public.WriteGate(directory=self.root,host_directory=str(self.root),endpoint=self.clients.endpoint,request_timeout_seconds=600)
        gate.transport='sdk'
        raw=dict(success=True,result=dict(native_return_value=True,mutation=dict(attempted=True,may_have_changed=True)))
        cause=ProtocolError('document.unit-profile-set','test',raw,ValueError('result validation failed'))
        with mock.patch.object(gate.clients(),'invoke',side_effect=cause) as invoke:
            with self.assertRaises(ProtocolError):gate.command('document','unit-profile-set','linear.unit','inch','--if-snapshot',json.dumps(profile(1)),'--if-update-stamp',0,document='d-012345',lease='l-0123456789ab')
        invoke.assert_called_once()
        self.assertEqual(gate.record['events'][-1]['wire_response'],raw)
        self.assertTrue(gate.record['events'][-1]['outcome_unknown'])
        rows=[json.loads(s) for s in (self.root/'transport-events.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['event']['wire_response'],raw)
        gate.clients().close()
