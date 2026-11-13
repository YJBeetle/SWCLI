"""Manual direction singleton only; default off, exact next-branch head, no matrix."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CI = Path(__file__).resolve().parent
sys.path.insert(0,str(CI))
from gate_support.revolve_direction import Evidence, durable, require, run_direction


def exact_source(expected_head):
    # Validate the same route before imports of any native backend or process API.
    spec=importlib.util.spec_from_file_location("_direction_route",CI/"validate-native-profile.py")
    route=importlib.util.module_from_spec(spec);spec.loader.exec_module(route)
    profile=route.resolve(os.environ.get("GITHUB_EVENT_NAME"),os.environ.get("GITHUB_REF"),
        dict(native_revolve_direction=True,revolve_direction_head=expected_head),head=os.environ.get("GITHUB_SHA"))
    require(profile=="native_revolve_direction","wrong direction route")
    root=CI.parents[1]
    checked=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    require(checked==expected_head,"checkout head differs from declared source")
    dirty=subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--","src","scripts",".github/workflows"],cwd=root,text=True)
    require(not dirty.strip(),"native source/harness worktree is not clean")
    import swcli
    installed=Path(swcli.__file__).resolve().parent
    source_package=root/"src/swcli"
    files=sorted(str(path.relative_to(source_package)) for path in source_package.rglob("*.py"))
    installed_files=sorted(str(path.relative_to(installed)) for path in installed.rglob("*.py"))
    require(files==installed_files,"installed Python module set differs from declared source")
    hashes={}
    for relative in files:
        actual=hashlib.sha256((installed/relative).read_bytes()).hexdigest()
        expected=hashlib.sha256((root/"src/swcli"/relative).read_bytes()).hexdigest()
        require(actual==expected,"installed wheel differs from declared source: "+relative)
        hashes[relative]=actual
    return dict(source_commit=checked,installed_files_sha256=hashes)


def stop_owned_after_timeout(output):
    """Never search for replacement hosts; admit only the recorded exact identity."""
    manifest=Path(output)/"owned-host.json"
    if not manifest.is_file():
        return dict(terminated=False,reason="no proven owned host identity; no host termination")
    from gate_support.revolve_direction_native import load_script
    owner=load_script("_direction_timeout_owner",CI/"gate_support/unit_owned_native.py")
    saved=json.loads(manifest.read_text())
    handle=None
    try:
        handle,identity=owner.capture(saved["identity"]["pid"],saved["launch_timestamp"],
            observe=lambda observed:durable(Path(output)/"timeout-identity-observation.json",observed))
        require(identity==saved["identity"],"recorded native process identity changed; never terminate replacement")
        owner.terminate(handle,identity)
        import win32event
        require(win32event.WaitForSingleObject(handle,10000)==win32event.WAIT_OBJECT_0,"timed out owned host did not exit")
        return dict(terminated=True,identity=identity)
    finally:
        if handle is not None:handle.Close()


def supervise(command, output):
    with (output/"stdout.log").open("wb") as stdout,(output/"stderr.log").open("wb") as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,env={**os.environ,"SWCLI_TRACE_NATIVE_CALLS":"1"})
        try:
            code=child.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            timeout=dict(seconds=1800,worker_pid=child.pid)
            try:durable(output/"group-timeout.json",timeout)
            except BaseException as error:timeout["initial_evidence_error"]=str(error)
            try:child.kill();child.wait(timeout=10)
            except BaseException as error:timeout["worker_cleanup_error"]=str(error)
            try:timeout["owned_cleanup"]=stop_owned_after_timeout(output)
            except BaseException as error:timeout["cleanup_error"]=dict(type=type(error).__name__,message=str(error))
            try:durable(output/"group-timeout.json",timeout)
            except BaseException as error:
                timeout["final_evidence_error"]=str(error)
                sys.stderr.write(json.dumps(timeout)+"\n");sys.stderr.flush()
            return 124
        report_path=output/"report.json"
        try:report=json.loads(report_path.read_text())
        except (OSError,ValueError):report={}
        if code == 0:
            require(report.get("success") is True and report.get("owned_cleanup_completed") is True and
                    report.get("public_acceptance") is False and report.get("matrix_enabled") is False,
                    "worker exited zero without complete direction-only evidence")
        if code != 0 and not report.get("owned_cleanup_completed"):
            # A 600s os._exit watchdog bypasses worker finally; retain its first
            # report and clean only a separately reverified recorded process.
            cleanup={}
            try:cleanup=stop_owned_after_timeout(output)
            except BaseException as error:cleanup=dict(cleanup_error=str(error))
            durable(output/"supervisor-failure-cleanup.json",cleanup)
        return code


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head",required=True)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--swconst",required=True,type=Path)
    parser.add_argument("--sldworks",required=True,type=Path)
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if re.fullmatch(r"[0-9a-f]{40}",args.expected_head) is None:parser.error("full lowercase commit SHA required")
    proof=exact_source(args.expected_head)
    require(args.swconst.is_file() and args.sldworks.is_file(),"both installed official type libraries are required")
    if args.worker:
        from gate_support.revolve_direction_native import NativeBackend
        durable(args.output_dir/"source-proof.json",proof)
        report=run_direction(NativeBackend(args.output_dir,args.swconst,args.sldworks),Evidence(args.output_dir),args.expected_head)
        print(json.dumps(dict(success=report["success"],failure=report.get("failure"),public_acceptance=False)))
        return 0 if report["success"] else 1
    output=args.output_dir.resolve()
    output.mkdir(parents=True,exist_ok=False)
    durable(output/"source-proof-parent.json",proof)
    command=[sys.executable,"-I",str(Path(__file__).resolve()),"--worker","--expected-head",args.expected_head,
        "--output-dir",str(output),"--swconst",str(args.swconst.resolve()),"--sldworks",str(args.sldworks.resolve())]
    return supervise(command,output)


if __name__=="__main__":raise SystemExit(main())
