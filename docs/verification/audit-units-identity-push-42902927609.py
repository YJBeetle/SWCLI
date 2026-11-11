"""Independent stdlib audit of one push; no product, gate, COM or native calls."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import zipfile

RUN = 42902927609
HEAD = 'e2f787666c504e72c289825a7753f27f6bdbb049'
CASES = {
    '3.9': (130133366083, 13802729441, 1073, '7ba0026806436d58fff9fde2ec198f357e7ada1719367e9f9e8c03aabea3f92e', '21d684e0b8ef896ab098e1461bc3b5bf31d9022b134ded04aa72494dd1123a31', 160.412, 11),
    '3.14': (130133365639, 13803896789, 1062, 'bf74b4ff67491c2db9b7f82eb88ebca2057b579981ab48b3d6b9c4ee4e01a03f', '470b0e2ace5ab8d0037cb0b3004d1d5ff80c555ec5d985914e812afe70e04dc9', 202.445, 4),
}

def require(value, message):
    if not value:
        raise ValueError(message)

def audit(metadata, raw):
    run = json.loads((metadata/'run-terminal.json').read_bytes())
    jobs = json.loads((metadata/'jobs-terminal.json').read_bytes())['jobs']
    artifacts = json.loads((metadata/'artifacts-terminal.json').read_bytes())['artifacts']
    require(run['id'] == RUN and run['head_sha'] == HEAD and run['event'] == 'push' and run['head_branch'] == 'codex/docprops-units-expanded' and run['run_attempt'] == 1 and run['status'] == 'completed' and run['conclusion'] == 'success', 'exact successful push')
    require(len(jobs) == 7 and all(j['run_id'] == RUN and j['head_sha'] == HEAD for j in jobs), 'job source binding')
    require({j['name'] for j in jobs if j['conclusion'] == 'success'} == {'Windows / Python 3.9', 'Windows / Python 3.14', 'Build wheel'} and sum(j['conclusion'] == 'skipped' for j in jobs) == 4, 'portable only; native skipped')
    results = {}
    for version, (job_id, artifact_id, size, digest, log_sha, seconds, skipped) in CASES.items():
        job = next(j for j in jobs if j['id'] == job_id)
        require(job['name'] == 'Windows / Python '+version and job['conclusion'] == 'success' and next(s for s in job['steps'] if s['name'] == 'Run unit tests')['conclusion'] == 'success', 'exact Windows test job')
        artifact = next(a for a in artifacts if a['id'] == artifact_id)
        archive = raw/('summary-'+version+'.original.zip')
        require(artifact['workflow_run']['id'] == RUN and artifact['workflow_run']['head_sha'] == HEAD and artifact['name'] == 'swcli-portable-summary-'+version+'-'+str(RUN)+'-1' and artifact['size_in_bytes'] == archive.stat().st_size == size and artifact['digest'] == 'sha256:'+digest and hashlib.sha256(archive.read_bytes()).hexdigest() == digest, 'official summary ZIP identity and digest')
        with zipfile.ZipFile(archive) as z:
            require(set(z.namelist()) == {'summary.json', 'summary.md'}, 'summary ZIP member set')
            summary = json.loads(z.read('summary.json'))
        require(summary['source']['commit'] == HEAD and summary['source']['scope'] == 'portable-checks-python-'+version and summary['first_failure'] is None and summary['cleanup_errors'] == [] and next(p for p in summary['phases'] if p['name'] == 'unit-tests')['status'] == 'PASS' and next(p for p in summary['phases'] if p['name'] == 'public-evidence')['status'] == 'SKIP', 'summary source and no public claim')
        log = (raw/('windows-'+version+'.original.log')).read_bytes()
        require(hashlib.sha256(log).hexdigest() == log_sha, 'pinned original job log digest')
        text = log.decode('utf-8-sig')
        marker = 'units.current-process-image-observation '
        rows = [line for line in text.splitlines() if marker in line]
        require(len(rows) == 1, 'one actual current-process observation')
        observation = json.loads(rows[0].split(marker, 1)[1])
        q = observation['query']; identity = observation['identity']; image = identity['image']
        require(q['api'] == 'QueryFullProcessImageNameW' and q['argtypes'] == ['HANDLE','DWORD','LPWSTR','PDWORD'] and q['restype'] == 'BOOL' and q['flags'] == 0 and q['success'] is True and q['last_error'] is None and q['input_capacity_chars'] == 32768, 'actual query contract')
        require(q['ctypes_bytes'] == dict(HANDLE=8,DWORD=4,BOOL=4,wchar=2) and q['byteorder'] == 'little', 'observed Windows ABI')
        require(q['image'] == image == observation['module_image'] and q['image_repr'] == repr(image), 'raw query and independent module paths agree')
        require(q['returned_chars'] == q['image_length_py_chars'] == q['image_length_utf16_units'] == observation['module_returned_chars'] == len(image.encode('utf-16-le'))//2 and q['nul_at_returned_index'] is True and observation['module_last_error'] is None, 'actual lengths and terminator')
        require(base64.b64decode(q['buffer_prefix_b64'],validate=True) == image.encode('utf-16-le')+b'\0\0', 'raw wchar prefix exactly image and NUL')
        passed = [line for line in text.splitlines() if 'test_windows_current_process_query_has_complete_image_without_assuming_venv_entry_is_image (' in line]
        require(len(passed) == 1 and passed[0].endswith(' ... ok'), 'test performed self PID and os.path.samefile assertions on Windows')
        require(re.findall(r'Ran (\d+) tests in ([\d.]+)s',text) == [('1973',str(seconds))] and re.findall(r'OK \(skipped=(\d+)\)',text) == [str(skipped)], 'full suite result')
        results[version] = dict(job_id=job_id,artifact_id=artifact_id,artifact_bytes=size,official_and_download_zip_sha256=digest,original_job_log_sha256=log_sha,unit_tests=1973,seconds=seconds,skipped=skipped,probe_test_passed=True,self_pid_and_samefile_assertions_passed=True,raw_query_module_paths_exact_equal=True,raw_buffer_verified=True,observation_log_utc=rows[0].split(' ',1)[0],observation=observation,summary_totals=summary['totals'])
    return dict(audit_success=True,run_id=RUN,head_sha=HEAD,event='push',run_attempt=1,conclusion='success',windows=results,native_job_skipped=True,solidworks_image_observed=False,solidworks_mismatch_resolved=False,public_acceptance_completed=dict(cli=0,sdk=0,mcp=0),notes=['Python self-query only; no CAD/native result from this run.','samefile and self PID assertions are evidenced by the exact Windows test pass; this audit does not call Windows APIs.','Original job logs have locally pinned SHA256; official artifact digests apply to summary ZIPs.'])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-dir',type=Path,required=True)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    value=json.dumps(audit(args.metadata_dir,args.raw_dir),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(value)
    else:print(value,end='')

if __name__ == '__main__':main()
