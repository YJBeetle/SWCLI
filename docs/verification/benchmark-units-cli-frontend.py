"""Actual CI fresh subprocess/helper TCP comparison with fake daemon; never native proof."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socketserver
import statistics
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('units_public_benchmark',ROOT/'scripts/ci/verify-document-unit-writes.py')
public=importlib.util.module_from_spec(spec);spec.loader.exec_module(public)
from swcli.daemon.server import validate_request


def main():
    base=ROOT/'evidence/units-profile/public-noop-42664223806';directory=base/'actual-frontend-benchmark';directory.mkdir(exist_ok=False)
    source=base/'original/swcli-native-smoke/units-public-acceptance/cli/public-unit-profile.json';report=json.loads(source.read_bytes());requests=[]
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            request=json.loads(self.rfile.readline());validate_request(request);requests.append(request)
            self.wfile.write(json.dumps(dict(api_version='swcli/v1',request_id=request['request_id'],success=True,duration_ms=0.0,result=report['unit_cases'][0]['read'])).encode()+b'\n')
    server=socketserver.ThreadingTCPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    gate=public.WriteGate(directory=directory,host_directory=str(directory),endpoint='127.0.0.1:'+str(server.server_address[1]),request_timeout_seconds=600)
    started=time.monotonic();gate.cli_frontend();startup=time.monotonic()-started;timing={'fresh_subprocess':[],'isolated_reused_cli_main':[]}
    try:
        for index in range(20):
            pair=[]
            for mode in timing:
                gate.cold_probe=mode=='fresh_subprocess';start=time.monotonic()
                value=gate.command('--request-id','bench-'+str(index),'document','unit-profile',document='d-012345');timing[mode].append(time.monotonic()-start);pair.append(gate.record['events'][-1])
                assert value['unit_profile']==report['unit_cases'][0]['read']['unit_profile']
            assert pair[0]['stdout']==pair[1]['stdout'] and pair[0]['stderr']==pair[1]['stderr'] and pair[0]['returncode']==pair[1]['returncode']==0
            assert requests[-1]==requests[-2]
        assert len(requests)==40
    finally:
        gate._cli_frontend.close();server.shutdown();server.server_close();gate.checkpoint('benchmark-final')
    result=dict(kind='offline macOS actual isolated CLI helper and real TCP fake daemon; not Windows/CAD/group-budget proof',python=sys.version,complete_replies_byte_equal=True,requests=40,helper_startup_seconds=startup,helper=gate.record['cli_frontend'],timing={k:dict(calls=len(v),median_seconds=statistics.median(v),total_seconds=sum(v),samples_seconds=v) for k,v in timing.items()},raw_journal=str((directory/'transport-events.jsonl').relative_to(ROOT)),raw_journal_sha256=hashlib.sha256((directory/'transport-events.jsonl').read_bytes()).hexdigest())
    (ROOT/'docs/evidence/units-profile/public-noop-42664223806/actual-frontend-benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
