"""Offline full-report serialization benchmark; stdlib only, no native/CI claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=args.report.read_bytes();report=json.loads(source);results={}
    with tempfile.TemporaryDirectory() as directory:
        for mode,indent,separators in [('original_pretty',2,None),('compact_equivalent',None,(',',':'))]:
            samples=[]
            for index in range(5):
                start=time.monotonic();raw=(json.dumps(report,ensure_ascii=True,allow_nan=False,indent=indent,separators=separators)+'\n').encode()
                path=Path(directory)/(mode+str(index))
                with path.open('wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                samples.append(time.monotonic()-start)
                assert json.loads(raw)==report
            results[mode]=dict(report_bytes=len(raw),median_seconds=statistics.median(samples),samples_seconds=samples,complete_roundtrip_equal=True)
    result=dict(kind='offline macOS stdlib CPython3.12, matching hosted major/minor only; not Windows timing proof',python=sys.version,report_sha256=hashlib.sha256(source).hexdigest(),serialization=results)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
