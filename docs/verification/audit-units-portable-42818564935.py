"""Pinned original Windows portable failure; no product/gate/COM imports or network."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

RUN=42818564935
HEAD='473b26a06e09538a4565cc0adb765988f61b44ee'
LOG_SHA='8d614a43c26f600194b6c0fa3e503475acacd73b2cba5667359dfeb11be848a4'
ARTIFACTS={13766028046:'a80489c6a9a35bbb8401676ee4b4239d7e5669166f192086e974f7a87d83bde3',13765898140:'c6bd22a941b36d48fc23a3e4afd6f1ec30e2c3676d7ebfa356a2d4f8cd78dfe0',13765683939:'fb4ab17b20811cbe39659bbd42988d04e2c76b6f6da688dca4ac40813c84ada2',13764544642:'54fec4142a05823656fae925a79e6d886d361821e86f1fc5eeab838759f49223'}
TESTS=['test_actual_cli_read_changed_and_all_guard_refusals_match_without_restarts','test_protocol_and_parser_failures_match_without_business_rpc']


def require(value,message):
    if not value:raise ValueError(message)


def audit(metadata,raw,repo):
    r=json.loads((metadata/'run-completed.json').read_bytes());j=json.loads((metadata/'jobs-completed.json').read_bytes());a=json.loads((metadata/'artifacts.json').read_bytes())
    require(r['id']==RUN and r['head_sha']==HEAD and r['status']=='completed' and r['conclusion']=='failure','exact failed run')
    jobs=j['jobs'];failed=[x for x in jobs if x['conclusion']=='failure']
    require({x['name'] for x in failed}=={'Windows / Python 3.9','Windows / Python 3.14'},'actual failed jobs')
    for job in failed:require([x['name'] for x in job['steps'] if x['conclusion']=='failure']==['Run unit tests'],'actual failed step')
    native=next(x for x in jobs if 'Public finite units write acceptance' in x['name'])
    require(native['conclusion']=='skipped' and native['steps']==[],'native not entered')
    require(set(x['id'] for x in a['artifacts'])==set(ARTIFACTS) and not any('windows-hosted' in x['name'] for x in a['artifacts']),'only portable/package artifacts')
    verified=[]
    for item in a['artifacts']:
        archive=raw/'artifacts'/str(item['id'])/'original.zip';digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        require(digest==ARTIFACTS[item['id']] and item['digest']=='sha256:'+digest and item['size_in_bytes']==archive.stat().st_size,'original ZIP digest/size')
        require(item['workflow_run']['id']==RUN and item['workflow_run']['head_sha']==HEAD,'artifact run/head binding')
        with zipfile.ZipFile(archive) as z:
            if 'portable-summary' in item['name']:
                summary=json.loads(z.read('summary.json'));require(summary['source']['commit']==HEAD and summary['source']['host']=='windows','portable summary source')
                require(summary['first_failure']['phase']=='unit-tests' and [x['status'] for x in summary['phases'] if x['name']=='public-evidence']==['SKIP'],'portable summary reach')
        verified.append(dict(id=item['id'],name=item['name'],zip_sha256=digest))
    log=(raw/'failed.original.log').read_bytes();require(hashlib.sha256(log).hexdigest()==LOG_SHA,'original failed job logs')
    clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',log.decode());matrices={};first=[]
    for version,seconds,skipped in [('3.9',245.823,11),('3.14',184.297,4)]:
        prefix='Windows / Python '+version+'\t';lines=[line for line in clean.splitlines() if line.startswith(prefix)]
        summaries=[line.split('FAIL: ',1)[1].split(' (',1)[0] for line in lines if 'FAIL: ' in line]
        require(summaries==TESTS and not any('ERROR: ' in line for line in lines),'only the two compare assertions')
        require(any('Ran 1960 tests in '+str(seconds)+'s' in line for line in lines) and any('FAILED (failures=2, skipped='+str(skipped)+')' in line for line in lines),'original test totals')
        differences=[line for line in lines if 'AssertionError: Tuples differ:' in line]
        require(len(differences)==2 and all(r"b'{\r\n" in line and r"b'{\n" in line for line in differences),'actual raw CRLF versus LF')
        chronological=next(line for line in lines if TESTS[0] in line and '... FAIL' in line);timestamp=chronological.split('\t')[2].split()[0]
        first.append(dict(timestamp=timestamp,matrix=version,test=TESTS[0]))
        matrices[version]=dict(tests=1960,failures=2,skipped=skipped,seconds=seconds,failed_tests=summaries,first_failure_utc=timestamp)
    old=subprocess.check_output(['git','show',HEAD+':scripts/ci/gate_support/unit_cli_worker.py'],cwd=repo)
    require(b'stdout=io.StringIO();stderr=io.StringIO()' in old,'actual old capture at failed head')
    return dict(audit_success=True,run_id=RUN,head_sha=HEAD,conclusion='failure',first_failure=min(first,key=lambda x:x['timestamp']),matrices=matrices,first_cause='actual standalone Windows CLI bytes use CRLF, StringIO helper uses LF; raw byte contract fails',failed_log_sha256=LOG_SHA,failed_worker_source_sha256=hashlib.sha256(old).hexdigest(),official_artifacts=verified,native_job_conclusion='skipped',native_job_started=False,private_cad_cases=0,public_cad_cases=dict(cli=0,sdk=0,mcp=0),public_native_accepted=False,package_success=True,prior_native_runs_not_used=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--metadata-dir',type=Path,required=True);parser.add_argument('--raw-dir',type=Path,required=True);parser.add_argument('--repo-root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();data=json.dumps(audit(args.metadata_dir,args.raw_dir,args.repo_root),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(data)
    else:print(data,end='')

if __name__=='__main__':main()
