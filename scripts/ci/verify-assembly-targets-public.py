"""Two explicit PUBLIC readonly cases, never a recovery host or private fixture write.

Run only after coordinator approval. All CAD actions use the installed public
CLI/SDK/MCP -> daemon -> owning worker. OS-only handles have no terminate right.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parent))
from gate_support.assembly_target_public_plan import (
    FILES, NAMES, ARTIFACT_ID, HANDLE_PATTERN_REFUSAL, digest, durable, require, verify_metadata, execution_plan,
)
from gate_support.assembly_target_public_evidence import WireProxy,raw_file,trace_budget,intent_budget


def load_owned_os():
    spec=importlib.util.spec_from_file_location('_assembly_owned_os',Path(__file__).parent/'gate_support/unit_owned_native.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class PublicGate:
    def __init__(self, output, fixture_dir, expected_image, *, monotonic=time.monotonic):
        self.output,self.fixture_dir=Path(output),Path(fixture_dir)
        self.expected_image=str(expected_image);self.clock=monotonic;self.started=self.clock()
        self.report=dict(success=False,public_native_acceptance=False,write_authorized=False,first_error=None,cleanup_errors=[],cases=[],phases=[],native_seconds=600,group_seconds=1800,outer_seconds=1840)
        self.uncertain=False;self.sequence=0;self.trace_paths=[];self.sdk={};self.mcp=None;self.native_handle=None;self.native_identity=None;self.declared_requests={}
        self.report_counter=0;self.events=(self.output/'events.jsonl').open('x',encoding='utf-8')
        self.owned_os=load_owned_os()

    def persist(self):
        self.report_counter+=1
        durable(self.output/('report-%04d.json'%self.report_counter),self.report)

    def event(self, value):
        self.events.write(json.dumps(value,allow_nan=False)+'\n');self.events.flush();os.fsync(self.events.fileno())

    def secondary(self, stage, error):
        self.report['cleanup_errors'].append(dict(stage=stage,type=type(error).__name__,message=str(error)))

    def save_first(self, first, **context):
        if self.report['first_error'] is None:
            self.report['first_error']=dict(type=type(first).__name__,message=str(first),**context)
        try:self.persist()
        except BaseException as secondary:self.secondary('persist-first-error',secondary)

    def authorize_request(self, value):
        expected=self.declared_requests.pop(value.get('request_id'),None)
        require(expected is not None,'undeclared/duplicate public request; no forwarding')
        actual={key:value[key] for key in expected if key in value}
        require(json.dumps(actual,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False)
                and set(value)==set(expected)|{'timeout_ms'} and type(value['timeout_ms']) is int
                and 0<value['timeout_ms']<=600000,'public request differs from durable declared intent')

    def remaining(self):
        if (self.output.parent/'supervisor-stop.json').exists():self.uncertain=True
        remaining=1800-(self.clock()-self.started)
        require(remaining>0 and not self.uncertain,'group expired or outcome unknown; no further CAD request')
        return remaining

    def check_files(self):
        actual={name:digest(self.fixture_dir/name) for name in FILES}
        require(actual==FILES,'readonly input hashes changed')
        require(all(not (self.fixture_dir/name).stat().st_mode & 0o222 for name in FILES),'fixtures must remain filesystem readonly')
        return actual

    def process(self, label, argv, *, timeout=600, env=None):
        self.remaining();directory=self.output/label;directory.mkdir()
        self.event(dict(event='client-begin',label=label,argv=argv,monotonic=self.clock()))
        durable(directory/'command.json',dict(argv=argv))
        bounded_timeout=min(timeout,self.remaining())
        process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        try:out,err=process.communicate(timeout=bounded_timeout)
        except BaseException as first:
            self.uncertain=True
            self.save_first(first,label=label)
            for name,data in [('stdout.bin',getattr(first,'stdout',None) or b''),('stderr.bin',getattr(first,'stderr',None) or b'')]:
                try:raw_file(directory/name,data)
                except BaseException as secondary:self.secondary('timeout-'+name,secondary)
            # Evidence failure never prevents the one exact-client stop attempt.
            try:process.terminate()
            except BaseException as secondary:self.secondary('timeout-client-terminate',secondary)
            exit_code=None
            try:exit_code=process.poll()
            except BaseException as secondary:self.secondary('timeout-client-poll',secondary)
            try:durable(directory/'outcome.json',dict(exit_code=exit_code,unknown=True,terminated_exact_client_pid=process.pid))
            except BaseException as secondary:self.secondary('timeout-outcome',secondary)
            raise
        raw_file(directory/'stdout.bin',out);raw_file(directory/'stderr.bin',err)
        durable(directory/'outcome.json',dict(exit_code=process.returncode,unknown=False,pid=process.pid))
        self.event(dict(event='client-end',label=label,raw_exit=process.returncode,monotonic=self.clock()))
        return process.returncode,out,err

    def cli(self,label,arguments,*,endpoint=None,session='assembly-public-owner',request_id=None):
        request_id=request_id or str(uuid.uuid4())
        command=[sys.executable,'-I','-m','swcli','--endpoint',endpoint or self.proxy.endpoint,'--session',session,'--request-id',request_id,'--request-timeout',str(min(600,self.remaining())),*arguments,'--json']
        code,out,err=self.process(label,command)
        value=json.loads(out.decode('utf-8-sig'))
        return value,dict(exit_code=code,request_id=request_id)

    def request(self,label,transport,operation,parameters,*,document=None,stamp=None,lease=None,session='assembly-public-owner',expected='success',cli_args=None,owners=None):
        self.remaining()
        require(operation in {'assembly.targets.list','assembly.targets.validate','document.open',
                'document.lease.acquire','document.lease.release','document.close','document.list'},'undeclared readonly operation')
        if operation=='document.list':
            require(label in {'p%d-%s'%(i,suffix) for i in (1,2) for suffix in ('final-document-list','final-empty-document-list')}
                    and transport=='sdk' and parameters=={} and document is None and stamp is None and lease is None
                    and session=='assembly-public-owner' and expected=='success','undeclared final document inventory')
        require(not any(r['id']==label for r in self.report['cases']),'duplicate case label')
        if operation.startswith('assembly.targets.'):
            planned=next((r for r in execution_plan()['cases'] if r['id']==label),None)
            require(planned is not None and (transport,operation,expected,owners)==
                    (planned['transport'],planned['operation'],planned['expected'],planned['owner_reads']),
                    'unplanned/different assembly target request')
        if self.native_handle is not None:
            require(not self.owned_os.exited(self.native_handle)
                    and self.owned_os.process_identity(self.native_handle)==self.native_identity,'same owned native host no longer live')
        request_id=str(uuid.uuid4());context=dict(request_id=request_id)
        require(not any(r['request_id']==request_id for r in self.report['cases']),'duplicate request ID')
        context.update({k:v for k,v in dict(document_id=document,expected_update_stamp=stamp,lease_id=lease).items() if v is not None})
        self.event(dict(event='request-intent',id=label,request_id=request_id,transport=transport,operation=operation,parameters=parameters,context=context,session=session,monotonic=self.clock()))
        declared=dict(api_version='swcli/v1',request_id=request_id,operation=operation,parameters=parameters,session_id=session,**{k:v for k,v in context.items() if k!='request_id'})
        self.declared_requests[request_id]=declared
        row=dict(id=label,request_id=request_id,transport=transport,operation=operation,expected=expected,expected_owner_reads=owners,request=declared)
        self.report['cases'].append(row);self.persist()
        try:
            if transport=='cli':
                args=list(cli_args)
                if document is not None:args+=['--document',document]
                if stamp is not None:args+=['--if-update-stamp',str(stamp)]
                if lease is not None:args+=['--lease',lease]
                _,presentation=self.cli(label,args,session=session,request_id=request_id)
                require(type(presentation['exit_code']) is int and presentation['exit_code']==(0 if expected=='success' else 1),'CLI raw exit disagrees with planned outcome')
                # Every finite CLI case reaches the daemon ingress, including
                # the two malformed handles rejected before worker dispatch.
                wire=self.proxy.directory/request_id/'response.bin'
                require(wire.is_file(),'CLI case lacks its original daemon response')
                raw=json.loads(wire.read_bytes())
            elif transport=='sdk':
                from swcli.sdk import Client
                key=(session,min(600,self.remaining()))
                client=Client(endpoint=self.proxy.endpoint,session_id=session,timeout_seconds=key[1])
                if operation=='assembly.targets.list':reply=client.assembly.targets.list(**parameters,**context)
                elif operation=='assembly.targets.validate':reply=client.assembly.targets.validate(**parameters,**context)
                else:reply=client.execute(operation,parameters,**context)
                raw=dict(reply.raw);presentation=raw
            elif transport=='mcp':
                if self.mcp is None:
                    from gate_support.unit_public_transports import MCPStdio
                    self.mcp=MCPStdio(self.proxy.endpoint,session,self.phase_directory);self.mcp.start()
                raw,presentation=self.mcp.call('execute',dict(operation=operation,parameters=parameters,session_id=session,**context))
            else:raise RuntimeError('unknown public transport')
            evidence=self.phase_directory/('presentation-'+label);evidence.mkdir()
            durable(evidence/'protocol.json',raw);durable(evidence/'presentation.json',presentation)
            row.update(response=raw,presentation=presentation,presentation_directory=str(evidence))
            if expected!='success':
                partial=raw.get('result',{})
                require(not isinstance(partial,dict) or not any(k in partial for k in ('snapshot_id','targets','target_ids','census','unchanged')),'failed readonly request published partial handles')
            self.event(dict(event='request-reply',id=label,request_id=request_id,response=raw,monotonic=self.clock()))
            if expected=='success':
                if raw.get('success') is not True:self.report['first_business_error']=dict(request_id=request_id,error=raw.get('error'))
                require(raw.get('success') is True,'public request failed: '+label)
            else:
                require(raw.get('success') is False and raw.get('error',{}).get('code')==expected,'unexpected refusal: '+label)
                if expected=='ValueError':
                    require(raw['error'].get('message')==HANDLE_PATTERN_REFUSAL,'unexpected malformed-handle refusal')
            self.check_files();self.persist()
            return raw.get('result',{})
        except BaseException as error:
            if not isinstance(error,(ValueError,RuntimeError)) or getattr(error,'outcome_unknown',False):self.uncertain=True
            raise

    def open_doc(self,label,path,transport='sdk'):
        value=self.request(label,transport,'document.open',dict(path=str(path),read_only=True,configuration=''),cli_args=['document','open',str(path),'--read-only'])
        return value['document']

    def lease(self,label,doc,*,session='assembly-public-owner',ttl=3600):
        return self.request(label,'sdk','document.lease.acquire',dict(ttl_seconds=ttl),document=doc['document_id'],session=session)['lease']['lease_id']

    def release(self,label,lease,session='assembly-public-owner'):
        return self.request(label,'sdk','document.lease.release',{},lease=lease,session=session)

    def targets(self,label,transport,doc,lease,*,snapshot=None,ids=None,expected='success',session='assembly-public-owner',stamp=None):
        if snapshot is None:
            op='assembly.targets.list';params=dict(components=NAMES);argv=['assembly','targets','list',*NAMES]
        else:
            op='assembly.targets.validate';params=dict(snapshot_id=snapshot,target_ids=ids);argv=['assembly','targets','validate',snapshot,*ids]
        owners=next((r['owner_reads'] for r in execution_plan()['cases'] if r['id']==label),None)
        return self.request(label,transport,op,params,document=doc['document_id'],stamp=doc['update_stamp'] if stamp is None else stamp,lease=lease,expected=expected,session=session,cli_args=argv,owners=owners)

    def close_doc(self,label,doc,lease=None):
        return self.request(label,'sdk','document.close',dict(discard=False),document=doc['document_id'],lease=lease)

    def source_remains(self, inventory, source):
        """Accept only an empty native catalog or the original clean source alone."""
        require(type(source.get('type')) is int and source['type']==1 and type(source.get('document_id')) is str
                and Path(source['path'])==self.fixture_dir/'coincident-aligned-component.SLDPRT',
                'original source document differs')
        documents=inventory.get('documents')
        count=inventory.get('count')
        require(inventory.get('ok') is True and inventory.get('action')=='document.list'
                and inventory.get('session_id')=='assembly-public-owner' and 'current_document_id' in inventory
                and type(documents) is list and type(count) is int and count==len(documents),
                'final document inventory response differs')
        current=inventory['current_document_id']
        if not documents:
            require(current is None,'empty document inventory retained a current document')
            return False
        require(count==1 and isinstance(documents[0],dict),'unexpected documents in final inventory')
        remaining=documents[0]
        require(remaining.get('document_id')==source['document_id'] and type(remaining.get('path')) is str
                and Path(remaining['path'])==Path(source['path']) and type(remaining.get('type')) is int
                and remaining['type']==1 and remaining.get('modified') is False and current in (None,source['document_id']),
                'final inventory did not contain the exact clean source')
        return True

    @staticmethod
    def require_document_closed(result, document):
        descriptor=result.get('document')
        require(result.get('ok') is True and result.get('action')=='document.close'
                and result.get('closed') is True and result.get('discard') is False
                and isinstance(descriptor,dict) and descriptor.get('document_id')==document['document_id']
                and type(descriptor.get('path')) is str and Path(descriptor['path'])==Path(document['path']),
                'exact document close not proven')

    def finish_source(self, index, source):
        prefix='p%d-final-'%index
        def inventory(suffix):
            return self.request(prefix+suffix,'sdk','document.list',{})
        if self.source_remains(inventory('document-list'),source):
            self.require_document_closed(self.close_doc(prefix+'source-close',source),source)
            require(not self.source_remains(inventory('empty-document-list'),source),
                    'source survived its one planned close')

    def phase(self,index,previous=None):
        from swcli.host_processes import solidworks_process_ids
        phase=dict(index=index,success=False,host_exit=None,daemon_exit=None,cleanup_errors=[])
        self.report['phases'].append(phase);self.persist()
        handle=daemon=out=err=None;self.proxy=None;failure=None
        try:
            before=solidworks_process_ids();phase['native_before']=before;require(before==[],'preexisting CAD prevents this explicit phase')
            directory=self.output/('phase%d'%index);directory.mkdir();self.phase_directory=directory
            with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
            self.endpoint='127.0.0.1:'+str(port)
            self.proxy=WireProxy(('127.0.0.1',port),self.output/'wire' if index==1 else self.output/'wire-phase2',authorize=self.authorize_request);self.proxy.start()
            # All wire receipt paths are recorded, without changing request bytes.
            phase['wire_directory']=str(self.proxy.directory)
            launched=datetime.now(timezone.utc).timestamp();out=(directory/'daemon.stdout').open('xb');err=(directory/'daemon.stderr').open('xb')
            self.trace_paths.append(directory/'daemon.stderr')
            command=[sys.executable,'-u','-I','-m','swcli','daemon','serve','--host','127.0.0.1','--port',str(port),'--startup-timeout','120','--tray','off']
            phase.update(command=command,launch_utc_timestamp=launched);self.persist()
            daemon=subprocess.Popen(command,stdout=out,stderr=err,env={**os.environ,'SWCLI_TRACE_NATIVE_CALLS':'1'})
            phase['daemon_pid']=daemon.pid
            # Read only the one daemon's startup output, not repeated business RPCs.
            start=self.clock()
            while b'"action": "daemon.serve"' not in (directory/'daemon.stdout').read_bytes():
                require(daemon.poll() is None and self.clock()-start<180,'single daemon startup failed; no replacement')
                self.remaining();time.sleep(.2)
            status,status_cli=self.cli('p%d-identity'%index,['daemon','status'],endpoint=self.endpoint)
            require(type(status_cli['exit_code']) is int and status_cli['exit_code']==0,'identity CLI exit is not0')
            state=status['result'];host=state['host'];pid=host['process_id']
            require(state.get('host_connected') is True and type(pid) is int and pid>0 and host.get('owned_by_daemon') is True,'native owned host not proven')
            phase['host']=host
            handle,identity=self.owned_os.capture(pid,launched,self.expected_image,terminate_right=False,
                observe=lambda value:durable(directory/'identity-observation.json',value))
            self.native_handle,self.native_identity=handle,identity
            phase['held_identity']=identity;self.persist()
            source=self.open_doc('p%d-open-source'%index,self.fixture_dir/'coincident-aligned-component.SLDPRT','cli')
            doc=self.open_doc('p%d-open-assembly'%index,self.fixture_dir/'coincident-aligned.SLDASM')
            lease=self.lease('p%d-lease'%index,doc)
            if index==1:
                first=self.targets('p1-cli-list','cli',doc,lease)
                ids=[t['target_id'] for t in first['targets']]
                self.targets('p1-sdk-validate','sdk',doc,lease,snapshot=first['snapshot_id'],ids=ids)
                self.targets('p1-mcp-subset','mcp',doc,lease,snapshot=first['snapshot_id'],ids=ids[:2])
                self.targets('p1-wrong-kind','cli',doc,lease,snapshot=first['snapshot_id'],ids=['e-abc123'],expected='ValueError')
                reference_hash=first['census']['components'][0]['faces'][0]['reference_sha256']
                self.targets('p1-reference-hash-as-handle','cli',doc,lease,snapshot=first['snapshot_id'],ids=[reference_hash],expected='ValueError')
                part_lease=self.lease('p1-part-lease',source)
                self.targets('p1-cross-document','sdk',source,part_lease,snapshot=first['snapshot_id'],ids=ids[:1],expected='AssemblyTargetNotFound')
                self.release('p1-part-release',part_lease)
                self.release('p1-owner-release',lease)
                other=self.lease('p1-other-lease',doc,session='assembly-public-other')
                # Same MCP connection, explicitly different execute session.
                self.targets('p1-cross-session','mcp',doc,other,snapshot=first['snapshot_id'],ids=ids[:1],session='assembly-public-other',expected='AssemblyTargetNotFound')
                self.release('p1-other-release',other,session='assembly-public-other')
                short=self.lease('p1-short-lease',doc,ttl=1)
                require(self.remaining()>1.1,'no budget for predeclared lease expiry');time.sleep(1.1)
                self.targets('p1-expired-lease','sdk',doc,short,snapshot=first['snapshot_id'],ids=ids[:1],expected='DocumentLeaseNotFound')
                lease=self.lease('p1-renewed-lease',doc)
                isolated=self.open_doc('p1-open-isolated',self.fixture_dir/'concentric-aligned-component.SLDPRT')
                self.targets('p1-background','cli',doc,lease,snapshot=first['snapshot_id'],ids=ids[:1],expected='AssemblyNotActive')
                self.close_doc('p1-close-assembly',doc,lease)
                doc=self.open_doc('p1-reopen-assembly',self.fixture_dir/'coincident-aligned.SLDASM')
                lease=self.lease('p1-reopen-lease',doc)
                newer=self.targets('p1-reopened-list','mcp',doc,lease)
                phase['reference_hashes_before_after_reopen']=[
                    [f['reference_sha256'] for c in value['census']['components'] for f in c['faces']]
                    for value in (first,newer)]
                self.targets('p1-old-snapshot-reopened','sdk',doc,lease,snapshot=first['snapshot_id'],ids=ids[:1],expected='AssemblyTargetNotFound')
                self.targets('p1-old-target-new-snapshot','cli',doc,lease,snapshot=newer['snapshot_id'],ids=ids[:1],expected='AssemblyTargetNotFound')
                new_ids=[t['target_id'] for t in newer['targets']]
                self.targets('p1-wrong-stamp','mcp',doc,lease,snapshot=newer['snapshot_id'],ids=new_ids[:1],stamp=doc['update_stamp']+1,expected='DocumentUpdateConflict')
                self.targets('p1-stale-does-not-revive','sdk',doc,lease,snapshot=newer['snapshot_id'],ids=new_ids[:1],expected='AssemblyTargetStale')
                previous=newer
                self.close_doc('p1-final-assembly-close',doc,lease)
                self.close_doc('p1-final-isolated-close',isolated)
            else:
                fresh=self.targets('p2-new-worker-list','sdk',doc,lease)
                old_ids=[t['target_id'] for t in previous['targets']]
                self.targets('p2-prior-worker-snapshot','mcp',doc,lease,snapshot=previous['snapshot_id'],ids=old_ids[:1],expected='AssemblyTargetNotFound')
                self.targets('p2-prior-worker-target','cli',doc,lease,snapshot=fresh['snapshot_id'],ids=old_ids[:1],expected='AssemblyTargetNotFound')
                self.close_doc('p2-final-assembly-close',doc,lease)
            self.finish_source(index,source)
            closed,stop_cli=self.cli('p%d-public-stop'%index,['daemon','stop'],endpoint=self.endpoint)
            require(type(stop_cli['exit_code']) is int and stop_cli['exit_code']==0,'shutdown CLI exit is not0')
            require(closed.get('success') is True and closed.get('result',{}).get('stopping') is True,'public shutdown was not the one live daemon stop')
            import win32event,win32process
            require(win32event.WaitForSingleObject(handle,int(self.remaining()*1000))==win32event.WAIT_OBJECT_0,'held native exit unknown')
            phase['host_exit']=win32process.GetExitCodeProcess(handle)
            require(type(phase['host_exit']) is int and phase['host_exit']==0,'held native exit is not strict0')
            phase['daemon_exit']=daemon.wait(timeout=self.remaining())
            require(type(phase['daemon_exit']) is int and phase['daemon_exit']==0,'owned public daemon exit differs')
            phase['native_after']=solidworks_process_ids();require(phase['native_after']==[],'native host survived explicit phase')
            require(not self.proxy.errors,'wire recorder has unknown outcomes')
            phase['success']=True;self.persist()
            return previous
        except BaseException as error:
            failure=error
            self.save_first(error,phase=index)  # Attempt before finally; secondary I/O never replaces it.
            self.uncertain=True
            raise
        finally:
            self.native_handle=self.native_identity=None
            for name,cleanup in [('mcp-close',lambda:self.mcp.close() if self.mcp is not None else None),
                                 ('handle-close',lambda:handle.Close() if handle is not None else None),
                                 ('daemon-stdout-close',lambda:out.close() if out is not None else None),
                                 ('daemon-stderr-close',lambda:err.close() if err is not None else None),
                                 ('raw-proxy-close',lambda:self.proxy.close() if self.proxy is not None else None)]:
                try:cleanup()
                except BaseException as secondary:
                    phase['success']=False
                    self.secondary(name,secondary)
                    if failure is None:failure=secondary
            self.mcp=None
            try:self.persist()
            except BaseException as secondary:
                phase['success']=False;self.secondary('phase-final-persist',secondary)
                if failure is None:failure=secondary
            if failure is not None and sys.exc_info()[0] is None:raise failure
            # On failure the disposable coordinator owns recovery. Do not append
            # more CAD/daemon business requests or terminate a CAD process.

    def expected_target_requests(self):
        rows={r['id']:r for r in self.report['cases']}
        def result(label):
            row=rows[label]
            phase=self.report['phases'][0 if label.startswith('p1-') else 1]
            raw=json.loads((Path(phase['wire_directory'])/row['request_id']/'response.bin').read_bytes())
            require(raw.get('success') is True,'planned source response failed: '+label)
            return raw['result']
        def doc(label, name, kind):
            value=result(label)['document']
            require(value['type']==kind and Path(value['path'])==self.fixture_dir/name,'planned document differs')
            return value
        def lease(label):return result(label)['lease']['lease_id']
        expected={}
        def add(label, document, token, params, *, session='assembly-public-owner', stamp=None):
            expected[label]=dict(api_version='swcli/v1',operation='assembly.targets.list' if 'components' in params else 'assembly.targets.validate',
                parameters=params,session_id=session,document_id=document['document_id'],
                expected_update_stamp=document['update_stamp'] if stamp is None else stamp,lease_id=token)
        def selected(snapshot, ids=None):
            return dict(snapshot_id=snapshot['snapshot_id'],target_ids=ids if ids is not None else [t['target_id'] for t in snapshot['targets']])
        assembly=doc('p1-open-assembly','coincident-aligned.SLDASM',2)
        require(assembly['active'] is True and doc('p1-open-isolated','concentric-aligned-component.SLDPRT',1)['active'] is True,'planned foreground transitions not proven')
        source=doc('p1-open-source','coincident-aligned-component.SLDPRT',1)
        baseline=result('p1-cli-list');ids=[t['target_id'] for t in baseline['targets']]
        add('p1-cli-list',assembly,lease('p1-lease'),dict(components=NAMES))
        add('p1-sdk-validate',assembly,lease('p1-lease'),selected(baseline))
        add('p1-mcp-subset',assembly,lease('p1-lease'),selected(baseline,ids[:2]))
        add('p1-wrong-kind',assembly,lease('p1-lease'),selected(baseline,['e-abc123']))
        reference=baseline['census']['components'][0]['faces'][0]['reference_sha256']
        add('p1-reference-hash-as-handle',assembly,lease('p1-lease'),selected(baseline,[reference]))
        add('p1-cross-document',source,lease('p1-part-lease'),selected(baseline,ids[:1]))
        add('p1-cross-session',assembly,lease('p1-other-lease'),selected(baseline,ids[:1]),session='assembly-public-other')
        add('p1-expired-lease',assembly,lease('p1-short-lease'),selected(baseline,ids[:1]))
        add('p1-background',assembly,lease('p1-renewed-lease'),selected(baseline,ids[:1]))
        reopened=doc('p1-reopen-assembly','coincident-aligned.SLDASM',2)
        newer=result('p1-reopened-list');newids=[t['target_id'] for t in newer['targets']]
        require(reopened['document_id']!=assembly['document_id'],'reopen document ID was reused')
        require(newer['snapshot_id']!=baseline['snapshot_id'],'reopen snapshot ID was reused')
        require(set(newids).isdisjoint(ids),'reopen reused an old target token')
        add('p1-reopened-list',reopened,lease('p1-reopen-lease'),dict(components=NAMES))
        add('p1-old-snapshot-reopened',reopened,lease('p1-reopen-lease'),selected(baseline,ids[:1]))
        add('p1-old-target-new-snapshot',reopened,lease('p1-reopen-lease'),selected(newer,ids[:1]))
        add('p1-wrong-stamp',reopened,lease('p1-reopen-lease'),selected(newer,newids[:1]),stamp=reopened['update_stamp']+1)
        add('p1-stale-does-not-revive',reopened,lease('p1-reopen-lease'),selected(newer,newids[:1]))
        if len(self.report['phases'])==2:
            freshdoc=doc('p2-open-assembly','coincident-aligned.SLDASM',2)
            fresh=result('p2-new-worker-list')
            fresh_ids={t['target_id'] for t in fresh['targets']}
            require(freshdoc['document_id'] not in {assembly['document_id'],reopened['document_id']},'new worker document ID was reused')
            require(fresh['snapshot_id'] not in {baseline['snapshot_id'],newer['snapshot_id']},'new worker snapshot ID was reused')
            require(fresh_ids.isdisjoint(ids) and fresh_ids.isdisjoint(newids),'new worker reused a prior target token')
            add('p2-new-worker-list',freshdoc,lease('p2-lease'),dict(components=NAMES))
            add('p2-prior-worker-snapshot',freshdoc,lease('p2-lease'),selected(newer,newids[:1]))
            add('p2-prior-worker-target',freshdoc,lease('p2-lease'),dict(snapshot_id=fresh['snapshot_id'],target_ids=newids[:1]))
        return expected

    def audit_document_cleanup(self, index, rows, journal, native_events):
        prefix='p%d-'%index
        by_label={row['id']:row for row in rows}
        source=by_label[prefix+'open-source']['response']['result']['document']
        first=prefix+'final-document-list'
        close=prefix+'final-source-close'
        empty=prefix+'final-empty-document-list'
        require(first in by_label,'final document inventory missing')
        remains=self.source_remains(by_label[first]['response']['result'],source)
        assembly_open=prefix+('reopen-assembly' if index==1 else 'open-assembly')
        assembly_lease=prefix+('reopen-lease' if index==1 else 'lease')
        assembly=by_label[assembly_open]['response']['result']['document']
        lease=by_label[assembly_lease]['response']['result']['lease']['lease_id']
        closes={prefix+'final-assembly-close':(assembly,lease)}
        if index==1:
            isolated=by_label['p1-open-isolated']['response']['result']['document']
            closes['p1-final-isolated-close']=(isolated,None)
        cleanup=[*closes,first]
        if remains:
            closes[close]=(source,None)
            cleanup.extend((close,empty))
        require([r['id'] for r in rows[-len(cleanup):]]==cleanup
                and [r['id'] for r in rows if r['operation']=='document.list']
                    ==([first,empty] if remains else [first])
                and (close in by_label)==remains,'final document inventory/close order differs')
        ordered=[(e['event'],e.get('id')) for e in journal if e.get('id') in cleanup]
        require(ordered==[(event,label) for label in cleanup for event in ('request-intent','request-reply')],
                'final document inventory/close journal order differs')
        for label in cleanup:
            row=by_label[label]
            is_close=label in closes
            operation='document.close' if is_close else 'document.list'
            request=dict(api_version='swcli/v1',request_id=row['request_id'],operation=operation,
                         parameters={'discard':False} if is_close else {},session_id='assembly-public-owner')
            if is_close:
                document,lease=closes[label]
                request['document_id']=document['document_id']
                if lease is not None:request['lease_id']=lease
            require(row['request']==request and row['operation']==operation and row['transport']=='sdk'
                    and row['expected']=='success' and row['response'].get('success') is True,
                    'final document inventory/close request or response differs')
            call='SldWorks.CloseDoc' if is_close else 'GetDocuments'
            trace=[e for e in native_events if e['request_id']==row['request_id']]
            observed=[e['phase'] for e in trace if e['call']==call]
            require(observed==['begin','end'] and not any(e['phase']=='error' for e in trace),
                    'final document inventory/close native proof differs')
            if is_close:self.require_document_closed(row['response']['result'],document)
        if remains:
            require(not self.source_remains(by_label[empty]['response']['result'],source),
                    'final document inventory is not empty')
        return 'closed-exact-source' if remains else 'already-absent'

    def audit_phase(self, index, *, persist=True):
        """A is fully audited before B can launch any daemon/native host."""
        phase=self.report['phases'][index-1]
        require(phase['success'] is True and not self.report['cleanup_errors']
                and type(phase.get('host_exit')) is int and phase['host_exit']==0
                and type(phase.get('daemon_exit')) is int and phase['daemon_exit']==0
                and phase.get('native_before')==phase.get('native_after')==[],
                'phase lifecycle/cleanup incomplete')
        sample=trace_budget([self.output/('phase%d'%index)/'daemon.stderr'],group_started=self.started,clock=self.clock)
        require(not sample['pending'],'phase native trace has incomplete calls')
        all_rows=self.report['cases']
        require(len({r['id'] for r in all_rows})==len(all_rows) and len({r['request_id'] for r in all_rows})==len(all_rows),'duplicate case/request ID in original ledger')
        rows=[r for r in self.report['cases'] if r['id'].startswith('p%d-'%index)]
        planned={r['id']:r for r in execution_plan()['cases'] if r['id'].startswith('p%d-'%index)}
        target_rows={r['id']:r for r in rows if r['operation'].startswith('assembly.targets.')}
        require(len(target_rows)==sum(r['operation'].startswith('assembly.targets.') for r in rows)
                and set(target_rows)==set(planned),'phase finite target case set differs')
        actual={r['request_id']:0 for r in rows};workers=set()
        for event in sample['events']:
            if event.get('request_id') in actual:workers.add(event['worker_pid'])
            if event.get('phase')=='begin' and event.get('stage')=='read' and event.get('call')=='GetComponent':
                actual[event['request_id']]=actual.get(event['request_id'],0)+1
            require(not any(token in event.get('call','') for token in
                    ('CreateMate','ActivateDoc','SelectBy','Save3','SaveAs','EditRebuild','ForceRebuild')),
                    'forbidden native call in readonly phase')
        require(sum(actual.values())==sum(r['owner_reads'] for r in planned.values()),'phase total native owner attempts differs')
        require(len(workers)==1,'phase used multiple/no owning workers')
        expected_requests=self.expected_target_requests()
        journal=[json.loads(line) for line in (self.output/'events.jsonl').read_bytes().split(b'\n')[:-1]]
        for row in rows:
            begins=[e for e in journal if e.get('event')=='request-intent' and e.get('request_id')==row['request_id']]
            replies=[e for e in journal if e.get('event')=='request-reply' and e.get('request_id')==row['request_id']]
            require(len(begins)==len(replies)==1 and begins[0]['id']==replies[0]['id']==row['id']
                    and begins[0]['operation']==row['operation'] and begins[0]['parameters']==row['request']['parameters']
                    and replies[0]['response']==row['response'],'phase original intent/reply journal differs')
        for label,row in target_rows.items():
            expected=planned[label]
            response=row['response']
            json.dumps(response,allow_nan=False)
            if row['expected']=='success':
                from swcli.result_schemas import validate_operation_result
                require(response.get('success') is True,'planned positive wire response failed')
                validate_operation_result(row['operation'],response['result'])
                require(response['result']['census']['face_count']==6,'fixed fixture complete six-face response missing')
            else:
                require(response.get('success') is False and response.get('error',{}).get('code')==row['expected']
                        and not any(k in response.get('result',{}) for k in ('snapshot_id','targets','target_ids','census','unchanged')),'planned refusal response differs/publishes partial handles')
                if row['expected']=='ValueError':
                    require(response['error'].get('message')==HANDLE_PATTERN_REFUSAL
                            and not any(e['request_id']==row['request_id'] for e in sample['events']),
                            'malformed-handle refusal reason or pre-worker boundary differs')
            request={key:value for key,value in row['request'].items() if key!='request_id'}
            require(request==expected_requests[label],'target parameters/context differ from original source wire responses')
            require(row['transport']==expected['transport'] and row['expected']==expected['expected']
                    and row['operation']==expected['operation'],'phase target transport/outcome differs')
            if row['expected']=='success':
                events=[e for e in sample['events'] if e['request_id']==row['request_id']]
                require(not any(e['phase']=='error' for e in events)
                        and sum(e['phase']=='end' and e['stage']=='read' and e['call']=='GetComponent' for e in events)==expected['owner_reads'],
                        'successful phase request has native errors/incomplete owner reads')
            row['actual_owner_reads']=actual.get(row['request_id'],0)
            require(row['actual_owner_reads']==expected['owner_reads'],'phase owner count differs')
            if row['expected']!='success':
                require(not any(e['request_id']==row['request_id'] and e['call']=='SldWorks.CommandInProgress.enter'
                                for e in sample['events']),'known refusal touched command setter')
        wire=Path(phase['wire_directory'])
        expected_wire={r['request_id']:r for r in rows}
        require({p.name for p in wire.iterdir()}==set(expected_wire),'missing/extra phase wire requests')
        for request_id,row in expected_wire.items():
            directory=wire/request_id
            receipt=json.loads((directory/'receipt.json').read_text())
            require(type(receipt.get('forward_attempts')) is int and receipt['forward_attempts']==1
                    and receipt['request_sha256']==digest(directory/'request.bin')
                    and receipt['response_sha256']==digest(directory/'response.bin'),'phase wire receipt incomplete/different')
            request=json.loads((directory/'request.bin').read_bytes())
            require({k:request.get(k) for k in row['request']}==row['request'],'phase wire request differs from durable intent')
            response=json.loads((directory/'response.bin').read_bytes())
            require(response==row['response'],'phase protocol presentation differs from original wire')
            presentation=Path(row['presentation_directory'])
            require(json.loads((presentation/'protocol.json').read_text())==response
                    and json.loads((presentation/'presentation.json').read_text())==row['presentation'],'phase client presentation not durable')
            require(not (directory/'failure.json').exists(),'phase wire forwarding failed')
        source_cleanup=self.audit_document_cleanup(index,rows,journal,sample['events'])
        for row in rows:
            if row['transport']!='cli':continue
            directory=self.output/row['id']
            outcome=json.loads((directory/'outcome.json').read_text())
            stdout=json.loads((directory/'stdout.bin').read_bytes())
            require(type(outcome.get('exit_code')) is int and outcome['exit_code']==(0 if row['expected']=='success' else 1)
                    and outcome.get('unknown') is False,'CLI raw exit differs from planned outcome')
            from swcli.cli import _typed_payload
            original_presentation=_typed_payload(row['operation'],row['response'])
            require(stdout==original_presentation,'CLI raw stdout differs from original protocol/presentation')
            from swcli.cli import build_parser,_typed_operation
            argv=json.loads((directory/'command.json').read_text())['argv']
            require(argv[:4]==[sys.executable,'-I','-m','swcli'],'unexpected CLI frontend')
            args=build_parser().parse_args(argv[4:]);op,params,_,document,stamp,lease=_typed_operation(args)
            original=dict(api_version='swcli/v1',operation=op,parameters=params,session_id=args.session,
                document_id=document,expected_update_stamp=stamp,lease_id=lease)
            planned_cli=expected_requests[row['id']] if row['id'] in expected_requests else {k:v for k,v in row['request'].items() if k!='request_id'}
            require({k:v for k,v in original.items() if v is not None}==planned_cli and args.request_id==row['request_id'],
                    'raw CLI argv differs from planned request')
        self.check_files()
        require(not intent_budget(self.output/'events.jsonl',group_started=self.started,clock=self.clock),'phase public intent incomplete')
        phase.update(audited=True,worker_pid=next(iter(workers)),trace_events=len(sample['events']),
                     wire_requests=len(expected_wire),source_cleanup=source_cleanup,final_documents=0)
        if persist:durable(self.output/('phase%d-audit.json'%index),phase)
        return phase

    def execute(self):
        self.report['files_before']=self.check_files()
        previous=self.phase(1)
        self.audit_phase(1)  # No second host until all A evidence passes.
        self.phase(2,previous)
        self.audit_phase(2)
        require(self.report['phases'][0]['worker_pid']!=self.report['phases'][1]['worker_pid'],'second explicit worker identity did not change')
        targets=[r for r in self.report['cases'] if r['operation'].startswith('assembly.targets.')]
        require(len(targets)==len(execution_plan()['cases']) and sum(r['actual_owner_reads'] for r in targets)==30
                and sum(r['expected']=='success' for r in targets)==5,'route case/pass/owner total differs')
        self.report['files_after']=self.check_files()
        self.report.update(success=True,public_native_acceptance=True,full_acceptance_eligible=False,
            files_unchanged=True,trace_events=sum(p['trace_events'] for p in self.report['phases']),group_elapsed=self.clock()-self.started)
        self.persist();durable(self.output/'final-report.json',self.report);self.events.close()


def verify_source(manifest_path, expected_sha):
    require(digest(manifest_path)==expected_sha,'source manifest digest differs')
    manifest=json.loads(Path(manifest_path).read_text())
    root=Path(__file__).resolve().parents[2]
    import swcli
    installed=Path(swcli.__file__).resolve().parent
    for name,expected in manifest['source_files'].items():
        require(digest(root/name)==expected,'checkout source bytes differ: '+name)
        if name.startswith('src/swcli/'):
            require(digest(installed/name[len('src/swcli/'):])==expected,'installed package bytes differ: '+name)
    return manifest


def approve(args):
    require(sys.platform=='win32','native public gate requires Windows; preparation is separate')
    plan=json.loads((args.prepared_dir/'once-only-plan.json').read_text())
    require(plan.get('prepared_metadata_sha256')==digest(args.prepared_dir/'artifact-metadata.json'),'prepared metadata bytes differ')
    metadata=json.loads((args.prepared_dir/'artifact-metadata.json').read_text());verify_metadata(metadata)
    grant=json.loads(args.grant_json.read_text())
    require(grant.get('authorized') is True and grant.get('root_reviewed') is True and grant.get('write_permission') is False
            and grant.get('phase_count')==2 and grant.get('group_seconds')==1800 and grant.get('native_seconds')==600
            and grant.get('outer_seconds')==1840 and grant.get('plan_sha256')==digest(args.prepared_dir/'once-only-plan.json')
            and type(grant.get('source_commit')) is str and grant['source_commit']==os.environ.get('GITHUB_SHA')
            and grant.get('artifact_id')==ARTIFACT_ID and grant.get('source_manifest_sha256')==args.source_manifest_sha,
            'exact coordinator grant missing/different; no host access')
    for key,expected in execution_plan().items():
        require(plan.get(key)==expected,'finite approved plan differs: '+key)
    require(plan.get('preparer_sha256')==digest(Path(__file__).with_name('prepare-assembly-targets-public.py'))
        and plan.get('plan_module_sha256')==digest(Path(__file__).parent/'gate_support/assembly_target_public_plan.py'),
        'prepared source provenance differs')
    verify_source(args.source_manifest,args.source_manifest_sha)
    from importlib.metadata import version
    require(all(version(name) for name in ('mcp','jsonschema','pywin32')),'public client dependencies missing')
    require(digest(args.expected_host_image)==grant['host_executable_sha256']
            and digest(args.expected_host_image.with_name('sldworks.tlb'))==grant['host_type_library_sha256'],
            'installed EXE/TLB bytes differ from reviewed grant')
    return grant


def supervise(args,grant):
    """Zero-COM manager: strict live trace watchdog, exact Python stop only."""
    root=args.output_dir.resolve();root.mkdir(parents=True,exist_ok=False)
    outer_started=getattr(args,'outer_started',time.monotonic())
    started=time.monotonic();failure=None;report=dict(success=False,first_error=None,child_exit=None,resource_released=False,
        source_commit=grant['source_commit'],native_seconds=600,group_seconds=1800,outer_seconds=1840)
    command=[sys.executable,'-I','-B',str(Path(__file__).resolve()),'--role','parent',
        '--prepared-dir',str(args.prepared_dir.resolve()),'--output-dir',str(root/'parent'),
        '--expected-host-image',str(args.expected_host_image.resolve()),'--grant-json',str(args.grant_json.resolve()),
        '--source-manifest',str(args.source_manifest.resolve()),'--source-manifest-sha',args.source_manifest_sha]
    report['actual_parent_argv']=command
    durable(root/'supervisor-intent.json',report)
    launched=datetime.now(timezone.utc).timestamp();handle=None;child=None
    with (root/'parent.stdout').open('xb') as out,(root/'parent.stderr').open('xb') as err:
        try:
            require(time.monotonic()-outer_started<1840,'outer1840 expired before parent launch')
            child=subprocess.Popen(command,stdout=out,stderr=err)
            report['parent_pid']=child.pid
            own=load_owned_os()
            handle,identity=own.capture(child.pid,launched,sys.executable,terminate_right=True,
                observe=lambda value:durable(root/'parent-python-identity.json',value))
            durable(root/'parent-admitted.json',dict(pid=child.pid,source_commit=grant['source_commit'],python_executable_sha256=digest(sys.executable)))
            while child.poll() is None:
                require(time.monotonic()-outer_started<=1840,'outer1840 elapsed')
                trace_budget(sorted((root/'parent').glob('phase*/daemon.stderr')),group_started=started)
                intent_budget(root/'parent/events.jsonl',group_started=started)
                time.sleep(.1)
            report['child_exit']=child.returncode
            sample=trace_budget(sorted((root/'parent').glob('phase*/daemon.stderr')),group_started=started)
            require(not intent_budget(root/'parent/events.jsonl',group_started=started),'public request journal incomplete')
            require(type(child.returncode) is int and child.returncode==0 and not sample['pending'],'public parent failed/incomplete')
            result=json.loads((root/'parent/final-report.json').read_text())
            require(result.get('success') is True and result.get('public_native_acceptance') is True
                    and len(result.get('phases',[]))==2 and all(type(p.get('host_exit')) is int and p['host_exit']==0 and type(p.get('daemon_exit')) is int and p['daemon_exit']==0
                    and p.get('native_before')==p.get('native_after')==[] for p in result['phases']),
                    'both explicit public phases/held exits not proven')
            # Independent zero-CAD re-read of the parent's actual files, not
            # merely its success flags, before deriving resource release.
            reader=object.__new__(PublicGate)
            reader.output=root/'parent';reader.fixture_dir=args.prepared_dir/'fixtures'
            reader.report=result;reader.started=started;reader.clock=time.monotonic
            for index in (1,2):
                audited=reader.audit_phase(index,persist=False)
                require(audited==json.loads((reader.output/('phase%d-audit.json'%index)).read_text()),'phase original audit differs')
            require(time.monotonic()-started<=1800,'whole route group exceeded1800')
            verify_source(args.source_manifest,args.source_manifest_sha)
            require(digest(args.expected_host_image)==grant['host_executable_sha256']
                and digest(args.expected_host_image.with_name('sldworks.tlb'))==grant['host_type_library_sha256'],'installed EXE/TLB changed')
            report['success']=True
        except BaseException as first:
            failure=first;report['first_error']=dict(type=type(first).__name__,message=str(first))
            try:durable(root/'supervisor-stop.json',report)
            except BaseException as secondary:report.setdefault('cleanup_errors',[]).append(dict(stage='stop-receipt',type=type(secondary).__name__,message=str(secondary)))
            # Receipt failure must not bypass the one verified exact-Python stop.
            if child is not None and handle is not None:
                try:
                    if child.poll() is None:own.terminate(handle,identity)
                except BaseException as secondary:report['python_stop_error']=dict(type=type(secondary).__name__,message=str(secondary))
            try:report['child_exit']=child.poll() if child is not None else None
            except BaseException as secondary:report['child_exit']=None;report['poll_error']=type(secondary).__name__
        finally:
            if handle is not None:
                try:handle.Close()
                except BaseException as secondary:
                    report['success']=False
                    report.setdefault('cleanup_errors',[]).append(dict(type=type(secondary).__name__,message=str(secondary)))
                    if failure is None:failure=secondary;report['first_error']=dict(type=type(secondary).__name__,message=str(secondary))
            report['resource_scope']='two declared CAD/daemon lifetimes, frontend/proxy and parent; runner/bootstrap cleanup remains coordinator-owned'
            report['resource_released']=(report['success'] is True and failure is None
                and type(report['child_exit']) is int and report['child_exit']==0)
            report['elapsed_seconds']=time.monotonic()-started
            report['outer_elapsed_seconds']=time.monotonic()-outer_started
            if report['outer_elapsed_seconds']>1840:
                report['success']=report['resource_released']=False
                if failure is None:failure=RuntimeError('outer1840 elapsed before final receipt')
            try:durable(root/'supervisor-final.json',report)
            except BaseException as secondary:
                report['success']=report['resource_released']=False
                report.setdefault('cleanup_errors',[]).append(dict(stage='final-receipt',type=type(secondary).__name__,message=str(secondary)))
                if failure is None:failure=secondary
    if failure is not None:raise failure
    require(report['success'],'public gate failed; preserve original error/native uncertainty, no retry')


def main():
    outer_started=time.monotonic()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=('supervisor','parent'),default='supervisor')
    parser.add_argument('--prepared-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--expected-host-image',type=Path,required=True)
    parser.add_argument('--grant-json',type=Path,required=True)
    parser.add_argument('--source-manifest',type=Path,required=True)
    parser.add_argument('--source-manifest-sha',required=True)
    args=parser.parse_args();args.outer_started=outer_started;grant=approve(args)
    if args.role=='supervisor':return supervise(args,grant)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    durable(args.output_dir/'started.json',dict(plan_sha256=digest(args.prepared_dir/'once-only-plan.json'),grant=grant,script_sha256=digest(__file__)))
    admission=args.output_dir.parent/'parent-admitted.json';waiting=time.monotonic()
    while not admission.exists():
        require(not (args.output_dir.parent/'supervisor-stop.json').exists() and time.monotonic()-waiting<30,'parent Python identity was not admitted; no CAD launch')
        time.sleep(.05)
    admitted=json.loads(admission.read_text())
    require(admitted.get('pid')==os.getpid() and admitted.get('source_commit')==grant['source_commit']
        and admitted.get('python_executable_sha256')==digest(sys.executable),'parent Python identity admission differs')
    gate=PublicGate(args.output_dir,args.prepared_dir/'fixtures',args.expected_host_image)
    try:gate.execute()
    except BaseException as first:
        gate.report['success']=gate.report['public_native_acceptance']=False
        gate.save_first(first)
        try:durable(args.output_dir/'failed-report.json',gate.report)
        except BaseException as secondary:gate.secondary('parent-failed-report',secondary)
        raise


if __name__=='__main__':main()
