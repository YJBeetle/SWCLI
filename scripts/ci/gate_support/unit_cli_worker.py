"""CI-only isolated CLI frontend. This is NOT one fresh CLI process per command."""
import contextlib
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


def main():
    emit(dict(kind='ready',pid=os.getpid(),swcli_version=__version__,cli_module=str(Path(cli.__file__).resolve()),cli_main_sha256=hashlib.sha256(Path(cli.__file__).read_bytes()).hexdigest()))
    sequence=0
    for raw in iter(lambda:sys.stdin.buffer.readline(MAX_FRAME_BYTES+1),b''):
        if len(raw)>MAX_FRAME_BYTES or not raw.endswith(b'\n'):raise ValueError('invalid CLI frontend request frame')
        request=json.loads(raw)
        if type(request) is not dict or set(request)!={'sequence','argv'} or type(request['sequence']) is not int or request['sequence']!=sequence+1 or type(request['argv']) is not list or not all(type(x) is str for x in request['argv']):raise ValueError('invalid CLI frontend request sequence/argv')
        sequence=request['sequence'];stdout=io.StringIO();stderr=io.StringIO();exception=None
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            try:code=cli.main(request['argv'])
            except SystemExit as error:code=error.code if type(error.code) is int else 1
            except BaseException as error:
                code=1;exception=dict(type=type(error).__name__,message=str(error))
        emit(dict(kind='reply',sequence=sequence,returncode=code,stdout=stdout.getvalue(),stderr=stderr.getvalue(),exception=exception))
    emit(dict(kind='closed',sequence=sequence,pid=os.getpid()))

if __name__=='__main__':main()
