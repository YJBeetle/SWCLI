"""Offline cost measurements with real CLI/parser/TCP and a fake daemon; never native acceptance."""
import contextlib,hashlib,io,json,os,socketserver,statistics,subprocess,sys,tempfile,threading,time
from pathlib import Path
from swcli import cli
from swcli.daemon.server import validate_request

root=Path.cwd();source=root/'evidence/units-profile/public-noop-42664223806/original/swcli-native-smoke/units-public-acceptance/cli/public-unit-profile.json';report=json.loads(source.read_bytes())
requests=[]
class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        request=json.loads(self.rfile.readline());validate_request(request);requests.append(request)
        response=dict(api_version='swcli/v1',request_id=request['request_id'],success=True,duration_ms=0.0,result=report['unit_cases'][0]['read'])
        self.wfile.write(json.dumps(response).encode()+b'\n')
server=socketserver.ThreadingTCPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
endpoint='127.0.0.1:'+str(server.server_address[1]);timing={}
try:
    for mode in ('fresh_cli_process','same_cli_main_process'):
        times=[];start_count=len(requests)
        for i in range(20):
            request_id=mode+'-'+str(i);args=['--endpoint',endpoint,'--session','benchmark-owner','--request-timeout','600','--request-id',request_id,'document','unit-profile','--document','d-012345','--json'];start=time.monotonic()
            if mode=='fresh_cli_process':
                result=subprocess.run([sys.executable,'-I','-m','swcli',*args],capture_output=True,timeout=610);assert result.returncode==0;payload=json.loads(result.stdout)
            else:
                output=io.StringIO()
                with contextlib.redirect_stdout(output):assert cli.main(args)==0
                payload=json.loads(output.getvalue())
            times.append(time.monotonic()-start)
            assert payload['request_id']==request_id and payload['unit_profile']==report['unit_cases'][0]['read']['unit_profile']
            assert requests[-1]['parameters']=={} and requests[-1]['document_id']=='d-012345' and requests[-1]['operation']=='document.unit-profile'
        assert len(requests)-start_count==20
        timing[mode]=dict(strategy=('one fresh actual CLI subprocess per request' if mode=='fresh_cli_process' else 'direct cli.main function calls in benchmark parent; lower-bound measurement only, not a CLI subprocess transport'),calls=20,requests_received=20,total_seconds=sum(times),median_seconds=statistics.median(times),samples_seconds=times)
finally:server.shutdown();server.server_close()
serialization={}
with tempfile.TemporaryDirectory() as td:
    for mode,indent,separators in [('original_pretty',2,None),('compact_equivalent',None,(',',':'))]:
        times=[]
        for i in range(5):
            start=time.monotonic();raw=(json.dumps(report,ensure_ascii=True,allow_nan=False,indent=indent,separators=separators)+'\n').encode()
            path=Path(td)/(mode+str(i))
            with path.open('wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            times.append(time.monotonic()-start);assert json.loads(raw)==report
        serialization[mode]=dict(report_bytes=len(raw),samples=5,total_seconds=sum(times),median_seconds=statistics.median(times),samples_seconds=times,complete_roundtrip_equal=True)
result=dict(benchmark_kind='offline fake daemon; not Windows or native runtime proof',python=sys.version,report_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),cli=timing,serialization=serialization,product_files_changed=False,notes=['Same-process measurement is direct function invocation in the benchmark parent. It is only a lower-bound diagnostic and neither a fresh CLI subprocess nor an implemented persistent frontend.','Every CLI call still creates one actual TCP request and returns actual CLI JSON.','Compact JSON retains every value and raw response; this only measures encoding overhead.'])
(root/'docs/evidence/units-profile/public-noop-42664223806/offline-overhead-benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
