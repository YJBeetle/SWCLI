"""CI-only isolated CLI frontend. This is NOT one fresh CLI process per command."""
import contextlib
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys

from swcli import __version__,cli

MAX_FRAME_BYTES=32*1024*1024


def emit(value):
    raw=(json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(',',':'))+'\n').encode()
    if len(raw)>MAX_FRAME_BYTES:raise ValueError('CLI frontend reply exceeds frame limit')
    sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()


def stdio_capture():
    # -I ignores PYTHONIOENCODING. CLI main explicitly sets only stdout UTF-8;
    # stderr must retain this actual isolated process's startup codec/errors.
    return dict(stdout_encoding='utf-8',stderr_encoding=sys.stderr.encoding,stderr_errors=sys.stderr.errors,newline='platform-default',raw_bytes='base64')


def capture_cli(argv,*,newline=None):
    # The IPC always uses newline=None; explicit newline is only a portable
    # regression seam for emulating the Windows standard text writer.
    policy=stdio_capture();out=io.BytesIO();err=io.BytesIO();exception=None
    with io.TextIOWrapper(out,encoding='utf-8',errors='strict',newline=newline) as stdout,io.TextIOWrapper(err,encoding=policy['stderr_encoding'],errors=policy['stderr_errors'],newline=newline) as stderr:
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            try:code=cli.main(argv)
            except SystemExit as error:code=error.code if type(error.code) is int else 1
            except BaseException as error:
                code=1;exception=dict(type=type(error).__name__,message=str(error))
        stdout.flush();stderr.flush();raw_out=out.getvalue();raw_err=err.getvalue()
    texts={}
    for name,raw,encoding in (('stdout',raw_out,'utf-8'),('stderr',raw_err,policy['stderr_encoding'])):
        try:texts[name]=raw.decode(encoding,errors='strict')
        except UnicodeError as error:
            texts[name]=None
            if exception is None:exception=dict(type=type(error).__name__,message=str(error))
    return dict(returncode=code,**texts,stdout_b64=base64.b64encode(raw_out).decode('ascii'),stderr_b64=base64.b64encode(raw_err).decode('ascii'),exception=exception)


def main():
    emit(dict(kind='ready',pid=os.getpid(),swcli_version=__version__,cli_module=str(Path(cli.__file__).resolve()),cli_main_sha256=hashlib.sha256(Path(cli.__file__).read_bytes()).hexdigest(),stdio_capture=stdio_capture()))
    sequence=0
    for raw in iter(lambda:sys.stdin.buffer.readline(MAX_FRAME_BYTES+1),b''):
        if len(raw)>MAX_FRAME_BYTES or not raw.endswith(b'\n'):raise ValueError('invalid CLI frontend request frame')
        request=json.loads(raw)
        if type(request) is not dict or set(request)!={'sequence','argv'} or type(request['sequence']) is not int or request['sequence']!=sequence+1 or type(request['argv']) is not list or not all(type(x) is str for x in request['argv']):raise ValueError('invalid CLI frontend request sequence/argv')
        sequence=request['sequence']
        emit(dict(kind='reply',sequence=sequence,**capture_cli(request['argv'])))
    emit(dict(kind='closed',sequence=sequence,pid=os.getpid()))

if __name__=='__main__':main()
