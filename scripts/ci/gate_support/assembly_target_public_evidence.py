"""Public gate raw wire journal and strict native600/group1800 trace accounting."""
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import socketserver
import threading
import time

from .assembly_target_public_plan import durable, require


def raw_file(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())


def trace_budget(paths, *, now=None, group_started, clock=time.monotonic):
    snapshots=[(str(path),Path(path).read_bytes()) for path in paths]
    # Sample AFTER reading every file; do not add timestamp tolerance.
    if now is None:now=clock()
    require(type(now) in (int,float) and math.isfinite(now)
            and type(group_started) in (int,float) and math.isfinite(group_started)
            and 0 <= now-group_started <= 1800, 'group1800 elapsed/clock invalid')
    pending={};completed=[];read_rows=[]
    for path,data in snapshots:
        # A partial final record is not a terminal call. Complete preceding
        # begins remain pending; bytes are retained in the original log.
        for line in data.split(b'\n')[:-1]:
            try:row=json.loads(line)
            except (ValueError,UnicodeError):continue  # Original non-trace diagnostic lines.
            if not isinstance(row,dict) or row.get('event')!='swcli.native-call':continue
            clock=row.get('monotonic_seconds')
            require(type(clock) in (int,float) and math.isfinite(clock) and group_started<=clock<=now,
                    'unknown/future/out-of-group native timestamp')
            key=(str(path),row.get('worker_pid'),row.get('request_id'),row.get('sequence'),row.get('stage'),row.get('call'))
            require(type(row.get('worker_pid')) is int and row['worker_pid']>0
                    and type(row.get('request_id')) is str and bool(row['request_id'])
                    and type(row.get('stage')) is str and bool(row['stage'])
                    and type(row.get('sequence')) is int and row['sequence']>=0 and type(row.get('call')) is str
                    and row.get('phase') in ('begin','end','error'), 'unknown native trace identity/phase')
            if row['phase']=='begin':
                require(key not in pending, 'duplicate native begin')
                pending[key]=clock
            else:
                require(key in pending, 'native terminal without matching begin')
                began=pending.pop(key);require(0<=clock-began<=600,'completed native span exceeded600')
                completed.append(dict(key=key,began=began,ended=clock,phase=row['phase']))
            read_rows.append(row)
    for key,began in pending.items():require(0<=now-began<=600,'pending native span exceeded600')
    return dict(pending=list(pending),completed=completed,events=read_rows)


class WireProxy:
    """Local byte-for-byte public TCP forwarder; one forwarding attempt per request."""
    def __init__(self, upstream, directory, *, authorize=None):
        self.upstream=upstream;self.directory=Path(directory);self.directory.mkdir()
        self.records=[];self.errors=[];self.handlers=[];self.lock=threading.Lock()
        self.authorize=authorize
        outer=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                with outer.lock:outer.handlers.append(threading.current_thread())
                directory=None
                try:
                    request=self.rfile.readline(16*1024*1024+1)
                    require(len(request)<=16*1024*1024 and request.endswith(b'\n'),'incomplete public request frame')
                    value=json.loads(request);request_id=value['request_id']
                    require(type(request_id) is str and len(request_id)<=128
                            and request_id.replace('-','').isalnum(),'unsafe raw request ID')
                    directory=outer.directory/request_id;directory.mkdir(exist_ok=False)
                    raw_file(directory/'request.bin',request)  # Intent durable before forward.
                    if outer.authorize is not None:outer.authorize(value)
                    record=dict(request_id=request_id,operation=value['operation'],session_id=value.get('session_id'),forward_attempts=0,request_sha256=hashlib.sha256(request).hexdigest())
                    durable(directory/'intent.json',record)
                    with outer.lock:outer.records.append(record)
                    record['forward_attempts']=1
                    with socket.create_connection(outer.upstream,timeout=3) as channel:
                        channel.settimeout(610);channel.sendall(request)
                        # Persist received bytes as they arrive. A timeout/EOF
                        # cannot discard a partial response buffered by readline.
                        response=bytearray()
                        with (directory/'response.bin').open('xb') as stream:
                            while not response.endswith(b'\n'):
                                chunk=channel.recv(min(65536,16*1024*1024+1-len(response)))
                                if not chunk:break
                                response.extend(chunk);stream.write(chunk);stream.flush();os.fsync(stream.fileno())
                                require(len(response)<=16*1024*1024,'public response exceeds bound')
                        response=bytes(response)
                    require(len(response)<=16*1024*1024 and response.endswith(b'\n'),'incomplete public response frame')
                    returned=json.loads(response);require(returned.get('request_id')==request_id,'public wire reply ID differs')
                    record.update(response_sha256=hashlib.sha256(response).hexdigest(),success=returned.get('success'))
                    durable(directory/'receipt.json',record)
                    self.wfile.write(response);self.wfile.flush()
                except BaseException as error:
                    failure=dict(type=type(error).__name__,message=str(error))
                    with outer.lock:outer.errors.append(failure)
                    if directory is not None:
                        try:durable(directory/'failure.json',failure)
                        except BaseException as secondary:
                            with outer.lock:outer.errors.append(dict(type=type(secondary).__name__,message=str(secondary),stage='failure-receipt'))
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=False
            daemon_threads=True
        self.server=Server(('127.0.0.1',0),Handler)
        self.endpoint='127.0.0.1:'+str(self.server.server_address[1])
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.closed=False

    def start(self):self.thread.start()

    def close(self):
        if self.closed:return
        self.closed=True
        if self.thread.is_alive():self.server.shutdown()
        self.server.server_close()
        if self.thread.ident is not None:self.thread.join(5)
        with self.lock:handlers=tuple(self.handlers)
        for handler in handlers:handler.join(.5)
        require(not self.thread.is_alive() and not any(t.is_alive() for t in handlers),'raw wire proxy has unfinished forwarding')


def intent_budget(path, *, group_started, clock=time.monotonic):
    data=Path(path).read_bytes() if Path(path).exists() else b''
    now=clock()
    require(0<=now-group_started<=1800,'group1800 expired')
    pending={}
    for line in data.split(b'\n')[:-1]:
        row=json.loads(line)
        event=row.get('event')
        if event not in ('request-intent','request-reply','client-begin','client-end'):continue
        stamp=row.get('monotonic')
        require(type(stamp) in (float,int) and math.isfinite(stamp) and group_started<=stamp<=now,'invalid public intent clock')
        key=('request',row.get('request_id')) if event.startswith('request-') else ('client',row.get('label'))
        if event in ('request-intent','client-begin'):
            require(key not in pending,'duplicate public intent')
            pending[key]=stamp
        else:
            require(key in pending,'public terminal without intent')
            start=pending.pop(key)
            require(0<=stamp-start<=600,'completed public request exceeded600')
    require(all(0<=now-start<=600 for start in pending.values()),'pending public request exceeded600')
    return pending
