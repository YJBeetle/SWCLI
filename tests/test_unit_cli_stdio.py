"""Exact standard text-writer bytes: platform defaults and Windows CRLF emulation."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('units_cli_stdio_worker_test',ROOT/'scripts/ci/gate_support/unit_cli_worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
spec=importlib.util.spec_from_file_location('units_cli_stdio_front_test',ROOT/'scripts/ci/gate_support/unit_cli_frontend.py')
frontend=importlib.util.module_from_spec(spec);spec.loader.exec_module(frontend)


class CLIStdioBytesTests(unittest.TestCase):
    text='中文UTF8\n第二行\r\n保留CR\r结尾\n'

    def test_fresh_writer_and_capture_preserve_default_crlf_utf8_and_actual_stderr_codec(self):
        script="import json,sys; p=json.loads(sys.argv[1]); sys.stdout.reconfigure(encoding='utf-8',newline=p['newline']); sys.stderr.reconfigure(encoding=p['stderr_encoding'],errors='backslashreplace',newline=p['newline']); sys.stdout.write(p['text']); sys.stderr.write(p['text'])"
        for newline in (None,'\r\n'):
            for encoding in ('utf-8','cp1252','cp932'):
                with self.subTest(newline=newline,stderr_encoding=encoding):
                    data=dict(newline=newline,stderr_encoding=encoding,text=self.text)
                    fresh=subprocess.run([sys.executable,'-I','-c',script,json.dumps(data)],capture_output=True,check=True,timeout=30)
                    template=io.TextIOWrapper(io.BytesIO(),encoding=encoding,errors='backslashreplace')
                    argv=['same-argv','中文'];observed=[]
                    def main(args):
                        observed.append(args);sys.stdout.write(self.text);sys.stderr.write(self.text);return 0
                    with template,mock.patch.object(worker.sys,'stderr',template),mock.patch.object(worker.cli,'main',side_effect=main):reply=worker.capture_cli(argv,newline=newline)
                    out,err=frontend.output_bytes(reply,dict(stderr_encoding=encoding))
                    self.assertEqual((reply['returncode'],out,err),(0,fresh.stdout,fresh.stderr));self.assertEqual(observed,[argv])
                    # The UTF-8 JSON frame preserves bytes; no replacement or newline cleanup.
                    frame=json.loads(json.dumps(reply,ensure_ascii=True).encode('utf-8'))
                    self.assertEqual(base64.b64decode(frame['stdout_b64'],validate=True),fresh.stdout)
                    self.assertEqual(base64.b64decode(frame['stderr_b64'],validate=True),fresh.stderr)
                    if newline=='\r\n':
                        self.assertIn(b'\r\r\n',out)
                        old=io.StringIO();old.write(self.text);self.assertNotEqual(old.getvalue().encode('utf-8'),fresh.stdout)

    def test_nonroundtrip_multibyte_codec_keeps_authoritative_original_stderr_bytes(self):
        raw=b'\x87\x90';self.assertNotEqual(raw.decode('cp932').encode('cp932'),raw)
        script="import sys; sys.stderr.reconfigure(encoding='cp932'); sys.stderr.buffer.write(bytes.fromhex('8790'))"
        fresh=subprocess.run([sys.executable,'-I','-c',script],capture_output=True,check=True,timeout=30)
        template=io.TextIOWrapper(io.BytesIO(),encoding='cp932',errors='backslashreplace')
        def main(argv):sys.stderr.buffer.write(raw);return 0
        with template,mock.patch.object(worker.sys,'stderr',template),mock.patch.object(worker.cli,'main',side_effect=main):reply=worker.capture_cli([])
        out,err=frontend.output_bytes(reply,dict(stderr_encoding='cp932'))
        self.assertEqual(out,fresh.stdout);self.assertEqual(err,fresh.stderr);self.assertEqual(err,raw)

    def test_invalid_utf8_is_retained_as_raw_bytes_and_rejected_without_replacement(self):
        def main(argv):sys.stdout.buffer.write(b'\xff');return 0
        with mock.patch.object(worker.cli,'main',side_effect=main):reply=worker.capture_cli([])
        self.assertIsNone(reply['stdout']);self.assertEqual(base64.b64decode(reply['stdout_b64'],validate=True),b'\xff')
        self.assertEqual(reply['exception']['type'],'UnicodeDecodeError')
        with self.assertRaises(UnicodeDecodeError):frontend.output_bytes(reply,dict(stderr_encoding='utf-8'))
