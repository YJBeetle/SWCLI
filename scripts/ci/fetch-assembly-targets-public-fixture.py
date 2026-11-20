"""Fixed GitHub artifact fetch only; no CAD/COM, retries or fixture construction."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from gate_support.assembly_target_public_plan import ARTIFACT_ID,verify_metadata,verify_zip,durable
from gate_support.assembly_target_public_evidence import raw_file


def once(output, role, command, stdout_name, *, run):
    durable(output/(role+'-intent.json'),dict(argv=command,attempts=1))
    try:result=run(command,capture_output=True,timeout=40)
    except subprocess.TimeoutExpired as first:
        first.evidence_errors=[]
        for name,data in [(stdout_name,first.stdout or b''),(role+'.stderr',first.stderr or b'')]:
            try:raw_file(output/name,data)
            except BaseException as secondary:first.evidence_errors.append(dict(stage=name,type=type(secondary).__name__,message=str(secondary)))
        try:durable(output/(role+'-command.json'),dict(argv=command,returncode=None,attempts=1,unknown=True,evidence_errors=first.evidence_errors))
        except BaseException as secondary:first.evidence_errors.append(dict(stage='outcome',type=type(secondary).__name__,message=str(secondary)))
        raise
    raw_file(output/stdout_name,result.stdout)
    raw_file(output/(role+'.stderr'),result.stderr)
    durable(output/(role+'-command.json'),dict(argv=command,returncode=result.returncode,attempts=1,unknown=False))
    if type(result.returncode) is not int or result.returncode!=0:raise RuntimeError('fixed artifact '+role+' request failed; no retry')
    return result.stdout


def fetch(output, *, run=subprocess.run):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    base='repos/YJBeetle/SWCLI/actions/artifacts/'+str(ARTIFACT_ID)
    metadata=once(output,'metadata',['gh','api',base],'artifact-metadata.json',run=run)
    verify_metadata(json.loads(metadata))
    once(output,'archive',['gh','api',base+'/zip'],'internal.zip',run=run)
    verify_zip(output/'internal.zip')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();fetch(args.output_dir)


if __name__=='__main__':main()
