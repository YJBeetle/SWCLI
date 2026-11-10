"""One retained CI CLI subprocess; no restart, retry, SDK routing, or CAD access."""
import hashlib
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

from swcli import __version__,cli

MAX_FRAME_BYTES=32*1024*1024


class FrontendError(RuntimeError):
    outcome_unknown=True


class CLIFrontend:
    def __init__(self,directory,*,helper_path=None,startup_timeout=30,metadata=None):
        self.sequence=0;self.poisoned=False;self.closed=False;self.partial=bytearray();self.frames=queue.Queue();self.lock=threading.Lock()
        path=Path(helper_path or Path(__file__).with_name('unit_cli_worker.py')).resolve()
        self.metadata=metadata if metadata is not None else {}
        self.metadata.update(strategy='isolated-reused-cli-main',command=[sys.executable,'-I',str(path)],helper_path=str(path),helper_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cold_start_per_command=False,starts=1,exit_confirmed=False)
        self.errors=(directory/'cli-helper.stderr.log').open('wb')
        self.metadata['launch_utc_timestamp']=datetime.now(timezone.utc).timestamp()
        try:self.process=subprocess.Popen(self.metadata['command'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors,env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        except BaseException as error:
            self.metadata['startup_error']=str(error);self.errors.close();raise
        self.metadata['pid']=self.process.pid
        self.reader=threading.Thread(target=self._read,name='units-cli-frontend-reader',daemon=True);self.reader.start()
        try:
            ready=self._receive(startup_timeout)
            if ready.get('kind')!='ready' or ready.get('pid')!=self.process.pid or ready.get('swcli_version')!=__version__ or ready.get('cli_main_sha256')!=hashlib.sha256(Path(cli.__file__).read_bytes()).hexdigest():raise ValueError('CLI frontend identity mismatch')
            self.metadata['ready']=ready
        except BaseException:
            self.poisoned=True
            try:self.close()
            except BaseException as cleanup:self.metadata['startup_cleanup_error']=str(cleanup)
            raise

    def _read(self):
        try:
            while True:
                chunk=os.read(self.process.stdout.fileno(),65536)
                if not chunk:break
                with self.lock:
                    self.partial.extend(chunk)
                    if len(self.partial)>MAX_FRAME_BYTES:raise ValueError('CLI frontend frame exceeds limit')
                    while b'\n' in self.partial:
                        line,_,rest=self.partial.partition(b'\n');self.partial[:]=rest;self.frames.put(bytes(line)+b'\n')
        except BaseException as error:self.frames.put(error)
        finally:self.frames.put(None)

    def _receive(self,timeout):
        try:
            raw=self.frames.get(timeout=timeout)
            if raw is None:raise EOFError('CLI frontend EOF before reply')
            if isinstance(raw,BaseException):raise raw
            self.last_frame=raw.decode('utf-8');value=json.loads(self.last_frame)
            if type(value) is not dict:raise ValueError('CLI frontend reply is not an object')
            return value
        except BaseException as cause:
            self.poisoned=True
            with self.lock:partial=bytes(self.partial)
            error=FrontendError('CLI frontend stopped without a valid reply: '+type(cause).__name__+': '+str(cause));error.partial_stdout=partial.decode('utf-8',errors='replace');error.raw_frame=getattr(self,'last_frame',None)
            raise error from cause

    def invoke(self,argv,*,timeout,before_send=None,after_receive=None):
        if self.closed or self.poisoned:raise FrontendError('CLI frontend cannot be restarted or reused after failure')
        sequence=self.sequence+1;request=dict(sequence=sequence,argv=list(argv))
        raw=(json.dumps(request,ensure_ascii=True,allow_nan=False,separators=(',',':'))+'\n').encode()
        if len(raw)>MAX_FRAME_BYTES:raise ValueError('CLI frontend request exceeds frame limit')
        self.last_request=raw.decode('utf-8')
        if before_send:before_send(request)
        self.sequence=sequence;self.last_frame=None
        try:
            self.process.stdin.write(raw);self.process.stdin.flush();reply=self._receive(timeout)
            if reply.get('kind')!='reply' or type(reply.get('sequence')) is not int or reply['sequence']!=self.sequence or type(reply.get('returncode')) is not int or type(reply.get('stdout')) is not str or type(reply.get('stderr')) is not str or reply.get('exception') is not None:raise ValueError('CLI frontend reply sequence/contract/exception mismatch')
        except BaseException as cause:
            self.poisoned=True
            if isinstance(cause,FrontendError):raise
            error=FrontendError(str(cause));error.raw_frame=getattr(self,'last_frame',None);raise error from cause
        if after_receive:after_receive(self.last_frame)
        return subprocess.CompletedProcess(argv,reply['returncode'],reply['stdout'].encode(),reply['stderr'].encode())

    def close(self):
        if self.closed:return
        self.closed=True;failure=None;normal=False
        try:
            self.process.stdin.close()
            if not self.poisoned:
                reply=self._receive(10)
                if reply!=dict(kind='closed',sequence=self.sequence,pid=self.process.pid):raise FrontendError('CLI frontend close frame mismatch')
                normal=True
        except BaseException as error:failure=error
        finally:
            try:
                if not normal and self.process.poll() is None:
                    self.process.terminate();self.metadata['forced_frontend_termination']=True
                code=self.process.wait(timeout=10)  # One retained child, one exit wait.
                self.metadata.update(exit_confirmed=True,exit_code=code,commands=self.sequence,exit_waits=1)
                if normal and code!=0:raise FrontendError('CLI frontend failed on close')
                if normal:self.metadata['normal_eof']=True
            except BaseException as error:
                self.metadata['exit_error']=str(error)
                if failure is None:failure=error
            finally:
                self.process.stdout.close();self.errors.close();self.reader.join(1)
        if failure:raise failure
