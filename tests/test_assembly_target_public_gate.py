"""Offline evidence/plan verification; never launches native public cases."""
import ast
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import socketserver
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/ci'))
from gate_support import assembly_target_public_plan as plan
from gate_support.assembly_target_public_evidence import trace_budget,intent_budget,WireProxy

spec=importlib.util.spec_from_file_location('assembly_public_gate',ROOT/'scripts/ci/verify-assembly-targets-public.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


class PublicGateOfflineTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.folder=Path(self.temporary.name)

    @staticmethod
    def metadata():
        return dict(id=plan.ARTIFACT_ID,name='swcli-assembly-mates-42279916240-1',size_in_bytes=plan.ZIP_SIZE,
            digest='sha256:'+plan.ZIP_SHA,expired=False,expires_at='2026-11-20T19:49:09Z',
            workflow_run=dict(id=plan.ARTIFACT_RUN,head_sha=plan.ARTIFACT_HEAD,head_branch='codex/swcli-assembly-mates'))

    def test_metadata_requires_exact_id_digest_size_provenance_and_actual_expiry(self):
        now=datetime(2026,11,15,tzinfo=timezone.utc)
        plan.verify_metadata(self.metadata(),now=now)
        for key,value in [('id',1),('size_in_bytes',False),('digest','sha256:bad'),('expired',True)]:
            metadata=self.metadata();metadata[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):plan.verify_metadata(metadata,now=now)
        with self.assertRaises(RuntimeError):plan.verify_metadata(self.metadata(),now=datetime(2026,11,21,tzinfo=timezone.utc))
        metadata=self.metadata();metadata['workflow_run']['head_sha']='f'*40
        with self.assertRaises(RuntimeError):plan.verify_metadata(metadata,now=now)

    def test_plan_is_finite_two_explicit_lifetimes_30_owners_and_no_authority(self):
        value=plan.execution_plan()
        self.assertFalse(value['authorized_to_execute'] or value['public_native_acceptance'])
        self.assertEqual((value['phases'],value['daemon_launches'],value['owned_native_hosts']),(2,2,2))
        self.assertEqual((value['native_seconds'],value['group_seconds'],value['outer_seconds']),(600,1800,1840))
        cases=value['cases'];self.assertEqual(len({r['id'] for r in cases}),len(cases))
        self.assertEqual(sum(r['owner_reads'] for r in cases),30)
        self.assertEqual(sum(r['expected']=='success' for r in cases),5)
        self.assertEqual({r['transport'] for r in cases},{'cli','sdk','mcp'})
        self.assertTrue(value['portable_only']);self.assertTrue(value['native_coverage_limits'])

    @staticmethod
    def row(phase,stamp,**values):
        return dict(event='swcli.native-call',worker_pid=42,request_id='request',sequence=1,stage='read',call='GetComponent',phase=phase,monotonic_seconds=stamp,**values)

    def trace(self,rows,tail=b''):
        path=self.folder/'trace.log';path.write_bytes(b''.join(json.dumps(r).encode()+b'\n' for r in rows)+tail);return path

    def test_native_budget_completed_and_pending_have_no_end_or_future_loophole(self):
        path=self.trace([self.row('begin',1),self.row('end',2)])
        sample=trace_budget([path],now=3,group_started=0);self.assertFalse(sample['pending']);self.assertEqual(len(sample['completed']),1)
        for rows,now in [([self.row('begin',1),self.row('end',602)],603),([self.row('begin',1)],602),
                         ([self.row('begin',4)],3),([self.row('end',2)],3),([self.row('begin',True)],3)]:
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):trace_budget([self.trace(rows)],now=now,group_started=0)
        with self.assertRaises(RuntimeError):trace_budget([path],now=1801,group_started=0)

    def test_incomplete_terminal_is_not_an_end_and_now_sample_follows_read(self):
        path=self.trace([self.row('begin',1)],json.dumps(self.row('end',2)).encode())
        self.assertTrue(trace_budget([path],now=3,group_started=0)['pending'])
        called=[]
        def sample():called.append(path.read_bytes());return 3
        trace_budget([path],group_started=0,clock=sample)
        self.assertEqual(called,[path.read_bytes()])

    def test_unknown_native_identity_types_rejected_without_coercion(self):
        for key,value in [('worker_pid',False),('sequence',True),('request_id',None),('stage',None)]:
            row=self.row('begin',1);row[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):trace_budget([self.trace([row])],now=2,group_started=0)

    def test_intent600_bounds_requests_even_without_native_trace_begin(self):
        path=self.folder/'events.jsonl'
        begin=dict(event='request-intent',request_id='r',monotonic=1)
        path.write_text(json.dumps(begin)+'\n')
        self.assertTrue(intent_budget(path,group_started=0,clock=lambda:2))
        with self.assertRaises(RuntimeError):intent_budget(path,group_started=0,clock=lambda:602)
        end=dict(event='request-reply',request_id='r',monotonic=602)
        path.write_text(json.dumps(begin)+'\n'+json.dumps(end)+'\n')
        with self.assertRaises(RuntimeError):intent_budget(path,group_started=0,clock=lambda:603)

    def test_wire_recorder_preserves_exact_request_response_and_forwards_once(self):
        requests=[]
        response=b'{"api_version":"swcli/v1", "request_id":"req-1", "success":false, "error":{"code":"AssemblyTargetStale","message":"unchanged raw"}}\n'
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):requests.append(self.rfile.readline());self.wfile.write(response);self.wfile.flush()
        upstream=socketserver.TCPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=upstream.serve_forever,daemon=True);thread.start()
        proxy=WireProxy(upstream.server_address,self.folder/'wire');proxy.start()
        request=b'{"request_id":"req-1", "operation":"assembly.targets.validate", "parameters":{}}\n'
        import socket
        try:
            with socket.create_connection(proxy.server.server_address) as connection:
                connection.sendall(request);returned=connection.makefile('rb').readline()
            self.assertEqual(returned,response);self.assertEqual(requests,[request])
            self.assertEqual((self.folder/'wire/req-1/request.bin').read_bytes(),request)
            self.assertEqual((self.folder/'wire/req-1/response.bin').read_bytes(),response)
            receipt=json.loads((self.folder/'wire/req-1/receipt.json').read_text())
            self.assertEqual(receipt['forward_attempts'],1)
            self.assertFalse(proxy.errors)
        finally:proxy.close();upstream.shutdown();upstream.server_close();thread.join()

    def test_failed_durable_wire_intent_cannot_forward(self):
        import socket
        proxy=WireProxy(('127.0.0.1',1),self.folder/'wire');proxy.start()
        try:
            with mock.patch('gate_support.assembly_target_public_evidence.raw_file',side_effect=OSError('fsync failed')):
                with socket.create_connection(proxy.server.server_address) as connection:
                    connection.sendall(b'{"request_id":"req-1","operation":"assembly.targets.list"}\n');connection.makefile('rb').readline()
            self.assertFalse(proxy.records)
            self.assertEqual(proxy.errors[0]['type'],'OSError')
        finally:proxy.close()

    def test_parent_failure_never_starts_second_lifetime(self):
        instance=object.__new__(gate.PublicGate);instance.report={'files_before':None,'phases':[]}
        instance.check_files=mock.Mock(return_value={})
        first=RuntimeError('phase1 fails; no restart')
        instance.phase=mock.Mock(side_effect=first)
        with self.assertRaises(RuntimeError) as caught:instance.execute()
        self.assertIs(caught.exception,first);instance.phase.assert_called_once_with(1)

    def test_windows_execution_requires_grant_before_any_gate_object_or_host(self):
        args=mock.Mock()
        with mock.patch.object(gate.sys,'platform','darwin'),mock.patch.object(gate,'PublicGate') as native:
            with self.assertRaises(RuntimeError):gate.approve(args)
        native.assert_not_called()

    def test_gate_source_uses_only_public_CAD_routes_and_os_handle_with_no_cad_kill(self):
        source=(ROOT/'scripts/ci/verify-assembly-targets-public.py').read_text()
        ast.parse(source,feature_version=(3,9))
        self.assertIn('terminate_right=False',source)
        self.assertIn("--role','parent'",source)
        self.assertIn('own.terminate(handle,identity)',source)  # Exact parent Python, never CAD.
        self.assertNotIn('pythoncom',source)
        self.assertNotIn('DispatchEx(',source)
        self.assertNotIn('observe_readonly_active_targets(',source)
        self.assertNotIn('taskkill',source)
        self.assertIn('client.assembly.targets.validate',source)
        self.assertIn("self.mcp.call('execute'",source)


    def test_fixed_fetch_expiry_failure_does_not_download_or_retry(self):
        spec=importlib.util.spec_from_file_location('assembly_fetch',ROOT/'scripts/ci/fetch-assembly-targets-public-fixture.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        metadata=self.metadata();metadata['expired']=True
        run=mock.Mock(return_value=mock.Mock(returncode=0,stdout=json.dumps(metadata).encode(),stderr=b'original stderr'))
        with self.assertRaises(RuntimeError):module.fetch(self.folder/'download',run=run)
        run.assert_called_once()
        self.assertEqual((self.folder/'download/metadata.stderr').read_bytes(),b'original stderr')
        self.assertFalse((self.folder/'download/internal.zip').exists())

    def test_fixed_fetch_timeout_retains_partial_raw_and_unknown_code_without_retry(self):
        import subprocess
        spec=importlib.util.spec_from_file_location('assembly_fetch_timeout',ROOT/'scripts/ci/fetch-assembly-targets-public-fixture.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        first=subprocess.TimeoutExpired(['gh','api'],40,output=b'partial original metadata',stderr=b'first timeout')
        run=mock.Mock(side_effect=first)
        with self.assertRaises(subprocess.TimeoutExpired) as caught:module.fetch(self.folder/'download',run=run)
        self.assertIs(caught.exception,first);run.assert_called_once()
        self.assertEqual((self.folder/'download/artifact-metadata.json').read_bytes(),b'partial original metadata')
        receipt=json.loads((self.folder/'download/metadata-command.json').read_text())
        self.assertIsNone(receipt['returncode']);self.assertTrue(receipt['unknown'])

    def test_parent_remaining_rejects_supervisor_stop_without_another_public_call(self):
        parent=self.folder/'parent';parent.mkdir()
        instance=object.__new__(gate.PublicGate);instance.output=parent;instance.clock=lambda:2;instance.started=1;instance.uncertain=False
        self.assertEqual(instance.remaining(),1799)
        (self.folder/'supervisor-stop.json').write_text('{}')
        with self.assertRaises(RuntimeError):instance.remaining()
        self.assertTrue(instance.uncertain)

    def make_gate(self, label='output'):
        from types import SimpleNamespace as NS
        output=self.folder/label;output.mkdir()
        with mock.patch.object(gate,'load_owned_os',return_value=NS()):
            value=gate.PublicGate(output,output/'fixtures','unused.exe',monotonic=lambda:200)
        self.addCleanup(value.events.close)
        value.started=0;value.phase_directory=output/'phase1';value.phase_directory.mkdir()
        value.check_files=mock.Mock(return_value=plan.FILES.copy())
        value.proxy=NS(endpoint='127.0.0.1:1',directory=output/'wire')
        return value

    def fake_phase_a(self, label='audit'):
        """Control-plane fixture: real files/wire formats, synthetic native trace."""
        from swcli.cli import _typed_payload
        value=self.make_gate(label);wire=value.output/'wire';wire.mkdir()
        phase=dict(index=1,success=True,host_exit=0,daemon_exit=0,native_before=[],native_after=[],wire_directory=str(wire))
        value.report['phases']=[phase]
        def document(name,kind,token,stamp):
            return dict(title=name,path=str(value.fixture_dir/name),type=kind,modified=False,update_stamp=stamp,
                document_id=token,current=True,active=True)
        assembly=document('coincident-aligned.SLDASM',2,'d-aaaaaa',7)
        reopened=document('coincident-aligned.SLDASM',2,'d-bbbbbb',7)
        source=document('coincident-aligned-component.SLDPRT',1,'d-cccccc',12)
        isolated=document('concentric-aligned-component.SLDPRT',1,'d-dddddd',13)
        def observed(doc,offset):
            state=lambda path,stamp:dict(configuration='Default',update_stamp=stamp,path=path,modified=False,readonly=True,view_only=False)
            components=[];targets=[]
            for ci,name in enumerate(plan.NAMES):
                faces=[]
                for fi in range(3):
                    sg=dict(available=True,coordinate_system='part-model',boundary='untrimmed-surface',face_normal_opposes_surface=False)
                    if fi==0:sg['cylinder']=dict(axis_point_mm=[0,0,0],axis_direction=[0,0,1],radius_mm=3)
                    else:sg['plane']=dict(point_mm=[0,0,fi],surface_normal=[0,0,1],outward_normal=[0,0,1])
                    geometry=dict(kind='face',surface_kind='cylinder' if fi==0 else 'plane',area_mm2=1,
                        area_accuracy='approximate',surface_geometry=sg)
                    faces.append(dict(index=fi,geometry=geometry,reference_sha256=format(ci*3+fi+1,'064x'),exact_native_owner=True))
                    targets.append(dict(target_id='at-'+format(offset+ci*3+fi,'032x'),kind='assembly-face',component_name=name,face_index=fi))
                components.append(dict(name=name,path=source['path'],source_state=state(source['path'],12),
                    transform=[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],fixed=ci==0,suppression=2,
                    source_face_count=3,component_face_count=3,faces=faces))
            return dict(ok=True,action='assembly.targets.list',session_id='assembly-public-owner',document=deepcopy(doc),
                scope='active-assembly-readonly-targets-v1',snapshot_id='as-'+format(offset,'032x'),targets=targets,
                census=dict(assembly=state(doc['path'],7),components=components,face_count=6,all_faces_observed=True),
                read_gate=dict(scope='complete-readonly-target-census',mate_tree_compared=False,write_authorized=False))
        baseline=observed(assembly,100);newer=observed(reopened,200)
        ids=[t['target_id'] for t in baseline['targets']];newids=[t['target_id'] for t in newer['targets']]
        leases={name:'l-'+chr(97+i)*12 for i,name in enumerate(['main','part','other','short','renewed','reopen'])}
        rows=[];native=[];journal=[]
        def record(label,transport,operation,parameters,result,*,doc=None,lease=None,session='assembly-public-owner',stamp=None,expected='success',owners=None,client=False):
            request_id='r-'+str(len(rows)+1);begin=1+len(rows)*2
            request=dict(api_version='swcli/v1',request_id=request_id,operation=operation,parameters=parameters,session_id=session)
            if doc is not None:
                request['document_id']=doc['document_id']
                if operation.startswith('assembly.targets.'):
                    request['expected_update_stamp']=doc['update_stamp'] if stamp is None else stamp
            if lease is not None:request['lease_id']=lease
            if client:raw=dict(ok=False,action=operation,error=dict(type='ValueError',message='typed handle pattern refused'))
            elif expected=='success':raw=dict(api_version='swcli/v1',request_id=request_id,success=True,duration_ms=1,result=result)
            else:raw=dict(api_version='swcli/v1',request_id=request_id,success=False,duration_ms=1,error=dict(code=expected,message='planned refusal'))
            row=dict(id=label,request_id=request_id,transport=transport,operation=operation,expected=expected,
                expected_owner_reads=owners,request=request,response=raw,presentation=raw)
            rows.append(row)
            if not client:
                path=wire/request_id;path.mkdir()
                req=json.dumps({**request,'timeout_ms':600000}).encode()+b'\n';res=json.dumps(raw).encode()+b'\n'
                (path/'request.bin').write_bytes(req);(path/'response.bin').write_bytes(res)
                (path/'receipt.json').write_text(json.dumps(dict(forward_attempts=1,request_sha256=hashlib.sha256(req).hexdigest(),response_sha256=hashlib.sha256(res).hexdigest())))
            presented=value.phase_directory/('presentation-'+label);presented.mkdir()
            row['presentation_directory']=str(presented)
            (presented/'protocol.json').write_text(json.dumps(raw));(presented/'presentation.json').write_text(json.dumps(raw))
            journal.extend([dict(event='request-intent',id=label,request_id=request_id,operation=operation,parameters=deepcopy(parameters),monotonic=begin),
                            dict(event='request-reply',id=label,request_id=request_id,response=deepcopy(raw),monotonic=begin+1)])
            for i in range(owners or 0):
                for terminal,stamp_value in [('begin',begin+.1),('end',begin+.2)]:
                    native.append(dict(event='swcli.native-call',worker_pid=42,request_id=request_id,sequence=i,
                        stage='read',call='GetComponent',phase=terminal,monotonic_seconds=stamp_value))
            if transport=='cli':
                args=['assembly','targets','list',*plan.NAMES] if 'components' in parameters else ['assembly','targets','validate',parameters['snapshot_id'],*parameters['target_ids']]
                argv=[sys.executable,'-I','-m','swcli','--endpoint','127.0.0.1:1','--session',session,'--request-id',request_id,'--request-timeout','600',*args,
                      '--document',doc['document_id'],'--if-update-stamp',str(request['expected_update_stamp']),'--lease',lease,'--json']
                path=value.output/label;path.mkdir();(path/'command.json').write_text(json.dumps(dict(argv=argv)))
                (path/'stdout.bin').write_text(json.dumps(raw if client else _typed_payload(operation,raw)))
                (path/'outcome.json').write_text(json.dumps(dict(exit_code=0 if expected=='success' else 1,unknown=False)))
            return row
        for label,doc_value in [('p1-open-source',source),('p1-open-assembly',assembly),('p1-open-isolated',isolated),('p1-reopen-assembly',reopened)]:
            record(label,'sdk','document.open',dict(path=doc_value['path'],read_only=True,configuration=''),dict(document=doc_value))
        for label,key,doc_value in [('p1-lease','main',assembly),('p1-part-lease','part',source),('p1-other-lease','other',assembly),
                                   ('p1-short-lease','short',assembly),('p1-renewed-lease','renewed',assembly),('p1-reopen-lease','reopen',reopened)]:
            record(label,'sdk','document.lease.acquire',dict(ttl_seconds=3600),dict(lease=dict(lease_id=leases[key])),doc=doc_value)
        base=lambda ids_value:dict(snapshot_id=baseline['snapshot_id'],target_ids=ids_value)
        new=lambda ids_value:dict(snapshot_id=newer['snapshot_id'],target_ids=ids_value)
        specs={
            'p1-cli-list':(assembly,'main',dict(components=plan.NAMES)),
            'p1-sdk-validate':(assembly,'main',base(ids)), 'p1-mcp-subset':(assembly,'main',base(ids[:2])),
            'p1-wrong-kind':(assembly,'main',base(['e-abc123'])),
            'p1-reference-hash-as-handle':(assembly,'main',base([baseline['census']['components'][0]['faces'][0]['reference_sha256']])),
            'p1-cross-document':(source,'part',base(ids[:1])), 'p1-cross-session':(assembly,'other',base(ids[:1])),
            'p1-expired-lease':(assembly,'short',base(ids[:1])), 'p1-background':(assembly,'renewed',base(ids[:1])),
            'p1-reopened-list':(reopened,'reopen',dict(components=plan.NAMES)),
            'p1-old-snapshot-reopened':(reopened,'reopen',base(ids[:1])),
            'p1-old-target-new-snapshot':(reopened,'reopen',new(ids[:1])),
            'p1-wrong-stamp':(reopened,'reopen',new(newids[:1])), 'p1-stale-does-not-revive':(reopened,'reopen',new(newids[:1])),
        }
        for item in plan.execution_plan()['cases']:
            label=item['id']
            if not label.startswith('p1-'):continue
            document_value,key,params=specs[label]
            result=deepcopy(newer if label=='p1-reopened-list' else baseline)
            if item['operation'].endswith('validate'):
                result['action']='assembly.targets.validate';result.pop('targets')
                result.update(target_ids=params['target_ids'],unchanged=True)
            record(label,item['transport'],item['operation'],params,result,doc=document_value,lease=leases[key],
                stamp=8 if label=='p1-wrong-stamp' else None,session='assembly-public-other' if label=='p1-cross-session' else 'assembly-public-owner',
                expected=item['expected'],owners=item['owner_reads'],client=item['expected']=='client-refusal')
        value.report['cases']=rows
        (value.phase_directory/'daemon.stderr').write_bytes(b''.join(json.dumps(r).encode()+b'\n' for r in native))
        value.events.write(''.join(json.dumps(r)+'\n' for r in journal));value.events.flush()
        return value,{r['id']:r for r in rows}

    def test_A_audit_validates_real_files_and_blocks_B_on_duplicate_unknown_or_bad_context(self):
        valid,_=self.fake_phase_a('valid');self.assertTrue(valid.audit_phase(1)['audited'])
        for scenario in ['duplicate-label','duplicate-request','unplanned','operation','context','wire','owner']:
            with self.subTest(scenario=scenario):
                value,rows=self.fake_phase_a(scenario)
                first=rows['p1-cli-list']
                if scenario=='duplicate-label':
                    extra=deepcopy(first);extra['request_id']='extra-request';value.report['cases'].append(extra)
                elif scenario=='duplicate-request':rows['p1-sdk-validate']['request_id']=first['request_id']
                elif scenario=='unplanned':
                    extra=deepcopy(first);extra.update(id='p1-unplanned',request_id='extra-request',expected_owner_reads=None);value.report['cases'].append(extra)
                elif scenario=='operation':rows['p1-sdk-validate']['operation']='assembly.targets.list'
                elif scenario=='context':rows['p1-sdk-validate']['request']['expected_update_stamp']=99
                elif scenario=='wire':
                    path=Path(value.report['phases'][0]['wire_directory'])/first['request_id']/'response.bin';path.write_bytes(b'{}\n')
                else:
                    path=value.phase_directory/'daemon.stderr';events=path.read_text().splitlines();path.write_text('\n'.join(events[:-2])+'\n')
                value.phase=mock.Mock(return_value=None)
                with self.assertRaises(Exception):value.execute()
                value.phase.assert_called_once_with(1)

    def test_process_timeout_evidence_failure_preserves_first_and_stops_exact_client(self):
        import subprocess
        value=self.make_gate('timeout')
        first=subprocess.TimeoutExpired(['client'],600,output=b'partial out',stderr=b'partial err')
        child=mock.Mock(pid=77);child.communicate.side_effect=first;child.poll.return_value=None
        real_durable=gate.durable
        def fail_after_intent(path,payload):
            if Path(path).name=='command.json':return real_durable(path,payload)
            raise OSError('disk full while recording')
        with mock.patch.object(gate.subprocess,'Popen',return_value=child), \
             mock.patch.object(gate,'raw_file',side_effect=OSError('partial evidence failed')), \
             mock.patch.object(gate,'durable',side_effect=fail_after_intent):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:value.process('timeout-client',['client'])
        self.assertIs(caught.exception,first);child.terminate.assert_called_once();child.poll.assert_called_once()
        self.assertTrue(value.uncertain);self.assertGreaterEqual(len(value.report['cleanup_errors']),3)

    def test_cli_nonzero_cannot_be_overridden_by_successful_wire_response(self):
        from types import SimpleNamespace as NS
        value=self.make_gate('bad-cli')
        with mock.patch.object(value,'cli',return_value=({'success':True},{'exit_code':17,'request_id':'r'})):
            with self.assertRaisesRegex(RuntimeError,'CLI raw exit'):
                value.request('p1-cli-list','cli','assembly.targets.list',dict(components=plan.NAMES),
                    document='d-aaaaaa',stamp=7,lease='l-aaaaaaaaaaaa',owners=6,cli_args=['assembly','targets','list',*plan.NAMES])
        self.assertFalse(value.report['success'])

    def test_MCP_two_lifetimes_keep_distinct_stderr_and_presentation_files(self):
        value=self.make_gate('mcp-evidence');opened=[]
        class Frontend:
            def __init__(self,endpoint,session,directory):self.directory=directory
            def start(self):
                opened.append(self.directory)
                with (self.directory/'mcp.stderr.log').open('w') as stream:stream.write('phase-'+str(len(opened)))
            def call(self,*args):return {'success':True,'result':{}},{'client':'original-'+str(len(opened))}
        with mock.patch('gate_support.unit_public_transports.MCPStdio',Frontend):
            value.request('p1-mcp-subset','mcp','assembly.targets.validate',dict(snapshot_id='as-'+'a'*32,target_ids=['at-'+'b'*32]),owners=6)
            first=(value.phase_directory/'mcp.stderr.log').read_bytes()
            value.mcp=None;value.phase_directory=value.output/'phase2';value.phase_directory.mkdir()
            # Use a lifecycle operation to test the second frontend independently
            # of a deliberate negative target result.
            value.request('p2-probe','mcp','document.lease.release',{},lease='l-aaaaaaaaaaaa')
        self.assertNotEqual(opened[0],opened[1]);self.assertEqual((opened[0]/'mcp.stderr.log').read_bytes(),first)
        self.assertEqual((opened[1]/'mcp.stderr.log').read_text(),'phase-2')
        self.assertTrue((opened[0]/'presentation-p1-mcp-subset/presentation.json').exists())
        self.assertTrue((opened[1]/'presentation-p2-probe/presentation.json').exists())

    def test_phase_recording_and_cleanup_secondary_do_not_replace_native_first_error(self):
        from types import SimpleNamespace as NS
        value=self.make_gate('phase-errors');value.phase_directory.rmdir();first=RuntimeError('original native identity failure')
        secondary=OSError('disk full or cleanup failure');attempts=[]
        def persist():
            attempts.append(1)
            if len(attempts)>2:raise secondary
        value.persist=persist
        value.owned_os=NS(capture=mock.Mock(side_effect=first))
        value.cli=mock.Mock(return_value=({'result':{'host_connected':True,'host':{'process_id':42,'owned_by_daemon':True}}},{'exit_code':0}))
        proxy=mock.Mock(endpoint='127.0.0.1:1',directory=value.output/'fake-wire');proxy.close.side_effect=secondary
        child=mock.Mock(pid=51);child.poll.return_value=None
        def spawn(*args,**kwargs):
            kwargs['stdout'].write(b'{"action": "daemon.serve"}\n');kwargs['stdout'].flush()
            return child
        with mock.patch('swcli.host_processes.solidworks_process_ids',return_value=[]), \
             mock.patch.object(gate,'WireProxy',return_value=proxy),mock.patch.object(gate.subprocess,'Popen',side_effect=spawn):
            with self.assertRaises(RuntimeError) as caught:value.phase(1)
        self.assertIs(caught.exception,first)
        self.assertEqual(value.report['first_error']['message'],str(first))
        self.assertTrue(value.uncertain);self.assertGreaterEqual(len(value.report['cleanup_errors']),2)
        child.terminate.assert_not_called();proxy.close.assert_called_once()

    def test_supervisor_stop_receipt_and_handle_errors_preserve_first_and_stop_python_once(self):
        from types import SimpleNamespace as NS
        import subprocess
        first=subprocess.TimeoutExpired(['budget'],600)
        child=mock.Mock(pid=55,returncode=None);child.poll.return_value=None
        handle=mock.Mock();handle.Close.side_effect=OSError('secondary handle close')
        owned=NS(capture=mock.Mock(return_value=(handle,{'pid':55})),terminate=mock.Mock())
        args=NS(output_dir=self.folder/'supervisor',prepared_dir=self.folder/'prepared',expected_host_image=self.folder/'host.exe',
            grant_json=self.folder/'grant.json',source_manifest=self.folder/'source.json',source_manifest_sha='0'*64)
        actual_argv={};real_durable=gate.durable;final=[]
        def record(path,payload):
            if Path(path).name=='supervisor-intent.json':actual_argv['argv']=payload['actual_parent_argv']
            if Path(path).name in ('supervisor-stop.json','supervisor-final.json'):
                final.append(deepcopy(payload));raise OSError('secondary receipt full')
            return real_durable(path,payload)
        with mock.patch.object(gate,'load_owned_os',return_value=owned), \
             mock.patch.object(gate.subprocess,'Popen',return_value=child) as spawn, \
             mock.patch.object(gate,'trace_budget',side_effect=first),mock.patch.object(gate,'durable',side_effect=record):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:gate.supervise(args,{'source_commit':'a'*40})
        self.assertIs(caught.exception,first);owned.terminate.assert_called_once_with(handle,{'pid':55})
        spawn.assert_called_once();self.assertIs(spawn.call_args.args[0],actual_argv['argv'])
        self.assertIsNone(final[-1]['child_exit']);self.assertFalse(final[-1]['success'])
        self.assertEqual(final[-1]['first_error']['type'],'TimeoutExpired')

    def test_parent_failed_report_secondary_keeps_execute_first_error(self):
        import os
        first=RuntimeError('original parent business failure');captured=[]
        parent=self.folder/'parent';admission=self.folder/'parent-admitted.json'
        prepared=self.folder/'prepared';prepared.mkdir();(prepared/'once-only-plan.json').write_text('{}')
        admission.write_text(json.dumps(dict(pid=os.getpid(),source_commit='a'*40,python_executable_sha256=gate.digest(sys.executable))))
        real_class=gate.PublicGate;real_durable=gate.durable
        def factory(*args,**kwargs):
            value=real_class(*args,**kwargs);value.execute=mock.Mock(side_effect=first)
            value.persist=mock.Mock(side_effect=OSError('secondary parent persist'));captured.append(value)
            self.addCleanup(value.events.close);return value
        def record(path,payload):
            if Path(path).name=='failed-report.json':raise OSError('secondary final report')
            return real_durable(path,payload)
        argv=['gate','--role','parent','--prepared-dir',str(self.folder/'prepared'),'--output-dir',str(parent),
              '--expected-host-image',str(self.folder/'host.exe'),'--grant-json',str(self.folder/'grant.json'),
              '--source-manifest',str(self.folder/'source.json'),'--source-manifest-sha','0'*64]
        with mock.patch.object(gate.sys,'argv',argv),mock.patch.object(gate,'approve',return_value={'source_commit':'a'*40}), \
             mock.patch.object(gate,'PublicGate',side_effect=factory),mock.patch.object(gate,'durable',side_effect=record):
            with self.assertRaises(RuntimeError) as caught:gate.main()
        self.assertIs(caught.exception,first);self.assertEqual(captured[0].report['first_error']['message'],str(first))
        self.assertEqual(len(captured[0].report['cleanup_errors']),2)

    def test_real_proxy_retains_partial_response_and_never_retries_or_marks_receipt(self):
        import socket
        requests=[];partial=b'{"request_id":"partial","success":'
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):requests.append(self.rfile.readline());self.wfile.write(partial);self.wfile.flush()
        upstream=socketserver.TCPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=upstream.serve_forever,daemon=True);thread.start()
        proxy=WireProxy(upstream.server_address,self.folder/'partial-wire');proxy.start()
        try:
            with socket.create_connection(proxy.server.server_address) as connection:
                connection.sendall(b'{"request_id":"partial","operation":"assembly.targets.list"}\n')
                self.assertEqual(connection.makefile('rb').readline(),b'')
            self.assertEqual(len(requests),1)
            self.assertEqual((self.folder/'partial-wire/partial/response.bin').read_bytes(),partial)
            self.assertFalse((self.folder/'partial-wire/partial/receipt.json').exists())
            self.assertTrue((self.folder/'partial-wire/partial/failure.json').exists())
        finally:proxy.close();upstream.shutdown();upstream.server_close();thread.join()

    def test_real_proxy_duplicate_and_undeclared_requests_do_not_forward(self):
        import socket
        requests=[];declared={'allowed'}
        def authorize(value):
            if value['request_id'] not in declared:raise RuntimeError('undeclared')
            declared.remove(value['request_id'])
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                requests.append(self.rfile.readline())
                self.wfile.write(b'{"request_id":"allowed","success":false}\n');self.wfile.flush()
        upstream=socketserver.TCPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=upstream.serve_forever,daemon=True);thread.start()
        proxy=WireProxy(upstream.server_address,self.folder/'once-wire',authorize=authorize);proxy.start()
        try:
            for request_id in ['allowed','allowed','undeclared']:
                with socket.create_connection(proxy.server.server_address) as connection:
                    connection.sendall(json.dumps(dict(request_id=request_id,operation='assembly.targets.list')).encode()+b'\n')
                    returned=connection.makefile('rb').readline()
                self.assertEqual(bool(returned),request_id=='allowed' and len(requests)==1 and not proxy.errors)
            self.assertEqual(len(requests),1);self.assertEqual(len(proxy.records),1)
            self.assertGreaterEqual(len(proxy.errors),2)
        finally:proxy.close();upstream.shutdown();upstream.server_close();thread.join()

    def test_wire_tampered_context_cannot_pass_even_when_receipt_hash_is_rewritten(self):
        value,rows=self.fake_phase_a('self-consistent-wrong-context')
        row=rows['p1-mcp-subset'];wrong=row['request']['parameters']['target_ids'][:1]
        row['request']['parameters']['target_ids']=wrong
        row['response']['result']['target_ids']=wrong;row['presentation']=row['response']
        directory=Path(value.report['phases'][0]['wire_directory'])/row['request_id']
        request=json.loads((directory/'request.bin').read_bytes());request['parameters']['target_ids']=wrong
        req=json.dumps(request).encode()+b'\n';res=json.dumps(row['response']).encode()+b'\n'
        (directory/'request.bin').write_bytes(req);(directory/'response.bin').write_bytes(res)
        (directory/'receipt.json').write_text(json.dumps(dict(forward_attempts=1,request_sha256=hashlib.sha256(req).hexdigest(),response_sha256=hashlib.sha256(res).hexdigest())))
        presentation=Path(row['presentation_directory'])
        (presentation/'protocol.json').write_text(json.dumps(row['response']));(presentation/'presentation.json').write_text(json.dumps(row['presentation']))
        events=[]
        for line in Path(value.events.name).read_text().splitlines():
            event=json.loads(line)
            if event.get('request_id')==row['request_id']:
                if event['event']=='request-intent':event['parameters']=row['request']['parameters']
                else:event['response']=row['response']
            events.append(event)
        Path(value.events.name).write_text(''.join(json.dumps(e)+'\n' for e in events))
        with self.assertRaisesRegex(RuntimeError,'target parameters/context differ'):value.audit_phase(1)


    def test_CI_proposal_has_no_head_self_reference_and_preserves_25_inputs_and_part_route(self):
        try:import yaml
        except ImportError:self.skipTest('workflow proposal semantic checks require PyYAML')
        import re
        lines=(ROOT/'docs/verification/assembly-mates-public-readonly-ci-route-2026-11-15.patch').read_text().splitlines(True)
        proposed={};index=0
        current_profile=(ROOT/'scripts/ci/validate-native-profile.py').read_text()
        current_workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        applied_profile='return "assembly-targets-readonly-public"' in current_profile
        applied_workflow='id: assembly_targets_public' in current_workflow
        self.assertEqual(applied_profile,applied_workflow,'CI proposal is only partially applied')
        if applied_profile:
            proposed={'scripts/ci/validate-native-profile.py':current_profile,'.github/workflows/ci.yml':current_workflow}
            index=len(lines)  # Do not apply a patch to its already-applied tree.
        while index<len(lines):
            if not lines[index].startswith('--- a/'):
                index+=1;continue
            name=lines[index][6:].strip();original=(ROOT/name).read_text().splitlines(True)
            output=[];cursor=0;index+=2
            while index<len(lines) and not lines[index].startswith('--- a/'):
                match=re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@',lines[index])
                self.assertIsNotNone(match)
                start=int(match.group(1))-1;output.extend(original[cursor:start]);cursor=start;index+=1
                while index<len(lines) and not lines[index].startswith(('@@','--- a/')):
                    line=lines[index];prefix=line[0];content=line[1:]
                    if prefix in (' ','-'):
                        self.assertEqual(original[cursor],content);cursor+=1
                    if prefix in (' ','+'):output.append(content)
                    index+=1
            output.extend(original[cursor:]);proposed[name]=''.join(output)
        workflow=yaml.load(proposed['.github/workflows/ci.yml'],Loader=yaml.BaseLoader)
        original=yaml.load((ROOT/'.github/workflows/ci.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(len(workflow['on']['workflow_dispatch']['inputs']),25)
        job=workflow['jobs']['solidworks-e2e'];old=original['jobs']['solidworks-e2e']
        part=lambda job:next(step for step in job['steps'] if step.get('id')=='topology_targeted')
        self.assertEqual(part(job),{'name': 'Run targeted topology reference calibration and public proof', 'id': 'topology_targeted', 'if': "${{ github.event_name == 'workflow_dispatch' && inputs.native_topology_targeted && !inputs.native_full && github.ref == 'refs/heads/codex/swcli-topology-references' }}", 'timeout-minutes': '65', 'shell': 'powershell', 'run': 'python -I scripts/ci/run-topology-targeted.py `\n  --output-dir "$env:SWCLI_SMOKE_ROOT\\topology-targeted" `\n  --swconst "C:\\Program Files\\SOLIDWORKS\\swconst.tlb"\nif ($LASTEXITCODE -ne 0) { throw "Targeted topology proof failed; retain original report, traces and native files" }\n'})
        self.assertIn('assembly-targets-readonly-public',job['name'])
        scope={"__name__":"offline_proposed_profile"}
        exec(compile(proposed['scripts/ci/validate-native-profile.py'],'proposed','exec'),scope)
        selector=dict(native_topology_targeted=True)
        self.assertEqual(scope['resolve']('workflow_dispatch','refs/heads/codex/swcli-topology-references',selector),'native_topology_targeted')
        self.assertEqual(scope['resolve']('workflow_dispatch','refs/heads/codex/swcli-assembly-mates-active',selector),'assembly-targets-readonly-public')
        for conflict in ['native_full','units_calibration','units_write_calibration','units_public_acceptance',*scope['FEATURE_REFS']]:
            if conflict=='native_topology_targeted':continue
            with self.subTest(conflict=conflict),self.assertRaises(ValueError):
                scope['resolve']('workflow_dispatch','refs/heads/codex/swcli-assembly-mates-active',{**selector,conflict:True})
        for event,ref in [('push','refs/heads/codex/swcli-assembly-mates-active'),('workflow_dispatch','refs/heads/main')]:
            with self.assertRaises(ValueError):scope['resolve'](event,ref,selector)
        native=next(step['run'] for step in job['steps'] if step.get('id')=='assembly_targets_public')
        self.assertNotIn('ROOT_REVIEWED_FINAL_HEAD_REQUIRED',native)
        self.assertIn('$actualHead = $env:GITHUB_SHA',native)
        self.assertIn('source_commit=$actualHead',native)
        self.assertRegex(native,r"\$reviewedManifest = '(?:ROOT_REVIEWED_SOURCE_MANIFEST_SHA256_REQUIRED|[0-9a-f]{64})'")
        self.assertIn('externally',native)


    def test_fresh_identity_uses_all_original_wire_tokens_and_allows_same_reference_hashes(self):
        def original(value,row):
            phase=value.report['phases'][0 if row['id'].startswith('p1-') else 1]
            return Path(phase['wire_directory'])/row['request_id']/'response.bin'
        valid,rows=self.fake_phase_a('fresh-valid')
        first=json.loads(original(valid,rows['p1-cli-list']).read_bytes())['result']
        newer=json.loads(original(valid,rows['p1-reopened-list']).read_bytes())['result']
        self.assertEqual([f['reference_sha256'] for c in first['census']['components'] for f in c['faces']],
                         [f['reference_sha256'] for c in newer['census']['components'] for f in c['faces']])
        valid.expected_target_requests()  # Same persistent hashes are permitted.
        for scenario in ['same-doc','same-snapshot','partial-token']:
            with self.subTest(scenario=scenario):
                value,rows=self.fake_phase_a('reopen-'+scenario)
                first=json.loads(original(value,rows['p1-cli-list']).read_bytes())['result']
                selected=rows['p1-reopen-assembly'] if scenario=='same-doc' else rows['p1-reopened-list']
                path=original(value,selected);raw=json.loads(path.read_bytes())
                if scenario=='same-doc':raw['result']['document']['document_id']=first['document']['document_id']
                elif scenario=='same-snapshot':raw['result']['snapshot_id']=first['snapshot_id']
                else:raw['result']['targets'][-1]['target_id']=first['targets'][-1]['target_id']
                path.write_text(json.dumps(raw))
                with self.assertRaisesRegex(RuntimeError,'reused'):value.expected_target_requests()
        for scenario in ['same-doc','same-snapshot','partial-old-initial','partial-old-reopened']:
            with self.subTest(worker=scenario):
                value,rows=self.fake_phase_a('worker-'+scenario)
                old=json.loads(original(value,rows['p1-cli-list']).read_bytes())['result']
                reopened=json.loads(original(value,rows['p1-reopened-list']).read_bytes())['result']
                wire=value.output/'wire-phase2';wire.mkdir()
                value.report['phases'].append(dict(wire_directory=str(wire)))
                document=deepcopy(reopened['document']);document['document_id']='d-eeeeee'
                fresh=deepcopy(reopened);fresh['document']=document;fresh['snapshot_id']='as-'+format(300,'032x')
                for i,t in enumerate(fresh['targets']):t['target_id']='at-'+format(300+i,'032x')
                if scenario=='same-doc':document['document_id']=old['document']['document_id']
                elif scenario=='same-snapshot':fresh['snapshot_id']=reopened['snapshot_id']
                else:fresh['targets'][-1]['target_id']=(old if scenario=='partial-old-initial' else reopened)['targets'][-1]['target_id']
                for i,(label,result) in enumerate([('p2-open-assembly',dict(document=document)),
                    ('p2-lease',dict(lease=dict(lease_id='l-eeeeeeeeeeee'))),('p2-new-worker-list',fresh)]):
                    request_id='p2-raw-'+str(i);path=wire/request_id;path.mkdir()
                    (path/'response.bin').write_text(json.dumps(dict(success=True,result=result)))
                    value.report['cases'].append(dict(id=label,request_id=request_id))
                with self.assertRaisesRegex(RuntimeError,'reused'):value.expected_target_requests()

    def test_supervisor_resource_release_requires_two_audits_and_strict_native_exits(self):
        from types import SimpleNamespace as NS
        for name,host_exit,expected in [('complete',0,True),('unknown',None,False),('boolean',False,False)]:
            with self.subTest(name=name):
                root=self.folder/('resource-'+name)
                args=NS(output_dir=root,prepared_dir=self.folder/'prepared',expected_host_image=self.folder/'host.exe',
                    grant_json=self.folder/'grant.json',source_manifest=self.folder/'source.json',source_manifest_sha='0'*64)
                grant=dict(source_commit='a'*40,host_executable_sha256='checked',host_type_library_sha256='checked')
                phases=[dict(index=i,success=True,audited=True,host_exit=host_exit if i==2 else 0,daemon_exit=0,
                    native_before=[],native_after=[],worker_pid=100+i) for i in (1,2)]
                child=mock.Mock(pid=55,returncode=0);child.poll.return_value=0
                def launch(*args,**kwargs):
                    parent=root/'parent';parent.mkdir()
                    (parent/'final-report.json').write_text(json.dumps(dict(success=True,public_native_acceptance=True,cleanup_errors=[],phases=phases)))
                    for phase in phases:(parent/('phase%d-audit.json'%phase['index'])).write_text(json.dumps(phase))
                    return child
                handle=mock.Mock();owned=NS(capture=mock.Mock(return_value=(handle,{'pid':55})),terminate=mock.Mock())
                def audit(reader,index,*,persist):
                    self.assertFalse(persist)
                    return reader.report['phases'][index-1]
                with mock.patch.object(gate,'load_owned_os',return_value=owned), \
                     mock.patch.object(gate.subprocess,'Popen',side_effect=launch), \
                     mock.patch.object(gate,'trace_budget',return_value={'pending':[]}), \
                     mock.patch.object(gate,'intent_budget',return_value={}), \
                     mock.patch.object(gate,'verify_source'),mock.patch.object(gate,'digest',return_value='checked'), \
                     mock.patch.object(gate.PublicGate,'audit_phase',autospec=True,side_effect=audit) as audits:
                    if expected:gate.supervise(args,grant)
                    else:
                        with self.assertRaises(RuntimeError):gate.supervise(args,grant)
                result=json.loads((root/'supervisor-final.json').read_text())
                self.assertIs(result['resource_released'],expected)
                self.assertIs(result['success'],expected)
                if expected:self.assertEqual(audits.call_count,2)
                owned.terminate.assert_not_called()
