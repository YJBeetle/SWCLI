"""Read back the four terminal public periodic STEP files in a fresh English native host.

One supervised worker and one owned hidden native Windows 2025 SP5 host. No STEP export.
Execution requires coordinator scheduling and a successful public writer of the same head.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gate_support import step_periodic_launch
from gate_support.step_periodic_supervisor import durable_json, error, supervise


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--swconst',type=Path,required=True)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--public-writer-report', nargs=2, required=True, metavar=('REPORT', 'SHA256'),
                        help='terminal English public periodic writer report and its SHA-256')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if not re.fullmatch('[0-9a-f]{40}',args.source_commit):parser.error('source-commit must be one exact lowercase Git head')
    args.output_dir=args.output_dir.resolve();args.swconst=args.swconst.resolve()
    if args.swconst.name.lower()!='swconst.tlb' or not args.swconst.is_file() or not args.swconst.with_name('sldworks.tlb').is_file():
        parser.error('installed swconst.tlb and sibling sldworks.tlb are required')
    if os.environ.get('GITHUB_SHA') and os.environ['GITHUB_SHA']!=args.source_commit:parser.error('source head differs from GITHUB_SHA')
    filename, expected = args.public_writer_report
    path = Path(filename).resolve()
    if (path.name != 'report.json' or not path.is_file() or args.output_dir in path.parents
            or not re.fullmatch('[0-9a-f]{64}', expected)):
        parser.error('public readback requires the terminal writer report outside output and lowercase SHA256')
    args.public_writer_report = dict(path=str(path), sha256=expected)
    return args


def identity(args):
    return dict(source_commit=args.source_commit,swconst_path=str(args.swconst),swconst_sha256=sha(args.swconst),
                sldworks_tlb_sha256=sha(args.swconst.with_name('sldworks.tlb')),
                entry_sha256=sha(Path(__file__).resolve()),
                launch_helper_sha256=sha(Path(step_periodic_launch.__file__).resolve()),parent_pid=os.getpid(),
                public_writer=args.public_writer_report)



def main(argv=None):
    args=parse(argv);output=args.output_dir
    if args.worker:
        try:
            original = json.loads((output/'input-identity.json').read_text(encoding='utf-8'))
            current = identity(args)
            if any(original.get(name) != current[name] for name in
                   ('source_commit', 'swconst_path', 'swconst_sha256', 'sldworks_tlb_sha256', 'entry_sha256',
                    'launch_helper_sha256', 'public_writer')):
                raise RuntimeError('parent/child input identity differs')
            stream = sys.stdin.buffer if sys.stdin is not None and not sys.stdin.isatty() else None
            receipt = step_periodic_launch.verify_worker_identity(original, stream)
            durable_json(output/'worker-supervision.json', receipt)
        except Exception as exc:
            try:
                durable_json(output/'worker-startup-failure.json', dict(
                    stage='worker-startup', worker_pid=os.getpid(), observed_parent_pid=os.getppid(),
                    error=error(exc),
                ))
            except OSError:
                pass  # The original exception remains in worker stderr.
            raise
        from gate_support.step_periodic_driver import run
        code,report=run(output,args.swconst,args.source_commit,public_writer=args.public_writer_report)
        # A green last report alone is insufficient; the parent requires this final digest receipt plus child exit0.
        durable_json(output/'worker-finished.json',dict(returncode=code,success=code==0 and report.get('complete') is True and report.get('success') is True,
                    report_sha256=sha(output/'report.json'),trace_sha256=sha(output/'trace.jsonl')))
        return code
    output.mkdir()  # Existing runs and their failures are never overwritten.
    executable, environment = step_periodic_launch.worker_python()
    launch = dict(identity(args), launch_executable=executable, parent_prefix=sys.prefix,
                  supervisor_executable=sys.executable)
    durable_json(output/'input-identity.json', launch)
    command = [executable, '-I', str(Path(__file__).resolve()), '--worker',
               '--output-dir', str(output), '--swconst', str(args.swconst),
               '--source-commit', args.source_commit]
    command.extend(['--public-writer-report', args.public_writer_report['path'], args.public_writer_report['sha256']])
    return supervise(command, output, launch=launch, environment=environment)[0]


if __name__=='__main__':raise SystemExit(main())
