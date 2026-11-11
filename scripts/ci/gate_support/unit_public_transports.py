"""Actual connection-only SDK and MCP stdio clients; never start/recover CAD."""
import asyncio
from datetime import timedelta
import json
import os
import sys
import threading
import uuid

from swcli import PROTOCOL_VERSION, __version__
from swcli.cli import build_parser, _typed_operation, _typed_payload
from swcli.sdk import Client


def require(value,message):
    if not value:raise RuntimeError(message)


class MCPStdio:
    def __init__(self,endpoint,session,directory):
        self.endpoint,self.session_id,self.directory=endpoint,session,directory
        self.ready=threading.Event();self.error=None;self.thread=None;self.info={}

    def start(self):
        require(self.thread is None,'MCP frontend must not be restarted')
        self.thread=threading.Thread(target=self.worker,name='units-mcp-stdio',daemon=True);self.thread.start()
        require(self.ready.wait(30),'MCP initialization deadline exceeded; no retry')
        if self.error:raise self.error
        require(self.thread.is_alive(),'MCP frontend exited during initialization')

    def worker(self):
        try:asyncio.run(self.serve())
        except BaseException as error:
            self.error=error;self.info['failure']=dict(type=type(error).__name__,message=str(error));self.ready.set()

    async def serve(self):
        from importlib.metadata import version
        self.info['client_library_version']=version('mcp')
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        args=['-I','-m','swcli','--endpoint',self.endpoint,'--session',self.session_id,'--request-timeout','600','mcp','serve']
        self.info['command']=[sys.executable,*args]
        with (self.directory/'mcp.stderr.log').open('w',encoding='utf-8') as errors:
            async with stdio_client(StdioServerParameters(command=sys.executable,args=args,env={**os.environ,'PYTHONIOENCODING':'utf-8'}),errlog=errors) as (reader,writer):
                async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=600)) as session:
                    initialized=await asyncio.wait_for(session.initialize(),30)
                    tools=await asyncio.wait_for(session.list_tools(),30)
                    require(initialized.serverInfo.name=='swcli' and {'execute','capabilities'}<=set(t.name for t in tools.tools),'unexpected MCP server/tools')
                    self.info.update(initialize=initialized.model_dump(mode='json'),tools=tools.model_dump(mode='json'))
                    self.loop=asyncio.get_running_loop();self.session=session;self.done=asyncio.Event();self.ready.set()
                    await self.done.wait()

    def call(self,name,arguments):
        if self.thread is None:self.start()
        if self.error:raise self.error
        require(self.thread.is_alive(),'MCP frontend disconnected; no replacement')
        future=asyncio.run_coroutine_threadsafe(self.session.call_tool(name,arguments,read_timeout_seconds=timedelta(seconds=600)),self.loop)
        reply=future.result(timeout=610)
        body=reply.structuredContent
        text=next((v.text for v in reply.content if v.type=='text'),None)
        try:consistent=type(body) is dict and text is not None and json.loads(text)==body
        except (ValueError,TypeError):consistent=False
        if not consistent:
            error=RuntimeError('MCP structured/text replies differ')
            error.raw=body;error.mcp_reply=reply.model_dump(mode='json');error.outcome_unknown=True
            raise error
        return body,reply.model_dump(mode='json')

    def close(self):
        if self.thread is None:return
        if self.thread.is_alive() and hasattr(self,'loop') and hasattr(self,'done'):self.loop.call_soon_threadsafe(self.done.set)
        self.thread.join(30)
        require(not self.thread.is_alive(),'MCP frontend shutdown timeout')
        if self.error:raise self.error
        self.info['closed']=True


class Transports:
    def __init__(self,endpoint,session,directory):
        self.endpoint,self.session,self.directory=endpoint,session,directory
        self.parser=build_parser();self.sdk={};self.mcp=MCPStdio(endpoint,session,directory)
        self.metadata={'swcli_sdk_version':__version__,'python':sys.version,'sdk_method':'Client.document.unit_profile_set; Client.execute for other typed operations','mcp':self.mcp.info}
        self.capability_checked=False

    def prepare(self,command):
        args=self.parser.parse_args(command[command.index('--endpoint'):])
        mapped=_typed_operation(args)
        require(mapped is not None,'non-typed command cannot use SDK/MCP route')
        operation,parameters,_,document,stamp,lease=mapped
        request=dict(api_version=PROTOCOL_VERSION,request_id=str(uuid.uuid4()),operation=operation,parameters=parameters,session_id=args.session,timeout_ms=int(args.request_timeout*1000))
        request.update({k:v for k,v in dict(document_id=document,expected_update_stamp=stamp,lease_id=lease).items() if v is not None})
        return request

    def invoke(self,transport,request):
        context={k:request[k] for k in ('request_id','document_id','expected_update_stamp','lease_id') if k in request}
        if transport=='sdk':
            key=(request['session_id'],request['timeout_ms'])
            if key not in self.sdk:self.sdk[key]=Client(endpoint=self.endpoint,session_id=key[0],timeout_seconds=key[1]/1000)
            client=self.sdk[key]
            if request['operation']=='document.unit-profile-set':
                response=client.document.unit_profile_set(**request['parameters'],**context)
            else:response=client.execute(request['operation'],request['parameters'],**context)
            raw=dict(response.raw);presentation=None
        elif transport=='mcp':
            if not self.capability_checked:
                capability,presented=self.mcp.call('capabilities',dict(operation='document.unit-profile-set'))
                require(capability.get('success') is True,'MCP operation schema discovery failed')
                self.metadata['mcp']['unit_profile_capability']=presented;self.capability_checked=True
            args={k:v for k,v in request.items() if k not in ('api_version','timeout_ms')}
            raw,presentation=self.mcp.call('execute',args)
        else:raise RuntimeError('unknown transport')
        require(raw.get('request_id')==request['request_id'],'transport response request ID differs')
        return _typed_payload(request['operation'],raw),raw,presentation

    def close(self):self.mcp.close()
