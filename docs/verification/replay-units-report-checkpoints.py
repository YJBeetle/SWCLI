"""Offline persistence replay; no CAD, no mutation-domain or native acceptance proof."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--calls',type=int,default=1000);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();spec=importlib.util.spec_from_file_location('units_checkpoint_replay',Path(__file__).resolve().parents[2]/'scripts/ci/calibrate-document-unit-profile.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    results=[]
    for each_call in (True,False):
        report=json.loads(args.report.read_bytes());checkpoints=0;entered=0
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def persist():
                nonlocal checkpoints
                checkpoints+=1;module.durable(root/'report.json',report)
            def getter():
                nonlocal entered
                entered+=1;return 42
            started=time.perf_counter()
            with (root/'trace.jsonl').open('w',encoding='utf-8') as trace:
                call=module.traced_calls(trace,persist,checkpoint_each_call=each_call)
                persist()  # Complete source/intent checkpoint before the operation.
                for _ in range(args.calls):assert call('OFFLINE-getter',getter)==42
                report['OFFLINE-observation']=42;persist()  # Full new observation.
            rows=[json.loads(s) for s in (root/'trace.jsonl').read_text().splitlines()]
            assert len(rows)==args.calls*2 and entered==args.calls
            assert json.loads((root/'report.json').read_bytes())==report
            results.append(dict(checkpoint_each_call=each_call,full_report_serializations=checkpoints,synthetic_getters=entered,durable_trace_events=len(rows),elapsed_seconds=time.perf_counter()-started))
    require_counts=(results[0]['full_report_serializations']==args.calls+2 and results[1]['full_report_serializations']==2)
    assert require_counts
    args.output.write_text(json.dumps(dict(native_executed=False,source_report_sha256=hashlib.sha256(args.report.read_bytes()).hexdigest(),report_bytes=args.report.stat().st_size,calls=args.calls,results=results,scope='offline IO/serialization replay only; does not establish Windows/native completion'),indent=2)+'\n')

if __name__=='__main__':main()
