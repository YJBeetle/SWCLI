"""Verify the fixed 90-degree direction case from a CI or local Windows checkout."""
import argparse
import hashlib
import importlib.util
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile

CI = Path(__file__).resolve().parent
sys.path.insert(0,str(CI))
from gate_support.revolve_direction import Evidence, durable, require, run_direction

NEXT_REF = "refs/heads/codex/swcli-revolve-feature-next"


def require_ci_route(expected_head):
    spec=importlib.util.spec_from_file_location("_direction_route",CI/"validate-native-profile.py")
    route=importlib.util.module_from_spec(spec);spec.loader.exec_module(route)
    profile=route.resolve(os.environ.get("GITHUB_EVENT_NAME"),os.environ.get("GITHUB_REF"),
        dict(native_revolve_direction=True,revolve_direction_head=expected_head),head=os.environ.get("GITHUB_SHA"))
    require(profile=="native_revolve_direction","wrong direction route")


def require_local_route():
    require(sys.platform == "win32", "local direction verification requires Windows")
    require(sys.flags.isolated, "invoke local direction verification with python -I")
    require(not any(key in os.environ for key in
                    ("GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_SHA")),
            "local direction verification requires a local shell without GitHub routing variables")


def verify_local_wheel(root, head, installed, wheel_path, wheel_sha256):
    require(wheel_path.suffix.lower() == ".whl" and wheel_path.is_file(),
            "local direction verification requires the original wheel file")
    actual_sha256 = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    require(actual_sha256 == wheel_sha256, "wheel archive SHA256 differs from the declared digest")
    dist = distribution("swcli")
    require(Path(dist.locate_file("swcli")).resolve() == installed,
            "imported swcli is outside the installed distribution")
    provenance = json.loads(dist.read_text("direct_url.json") or "{}")
    archive = provenance.get("archive_info", {})
    require(not provenance.get("dir_info") and archive.get("hashes", {}).get("sha256") == actual_sha256,
            "install SWCLI from the declared wheel file with pip before verification")
    tracked = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", "--name-only", head, "--", "src/swcli"], cwd=root,
    ).decode("utf-8").rstrip("\0").split("\0")
    members = {name.removeprefix("src/") for name in tracked if name}
    require(bool(members), "declared commit has no tracked SWCLI package files")
    installed_members = {"swcli/" + path.relative_to(installed).as_posix()
                         for path in installed.rglob("*")
                         if path.is_file() and "__pycache__" not in path.relative_to(installed).parts}
    require(installed_members == members, "installed package file set differs from the declared commit")
    with ZipFile(wheel_path) as wheel:
        package_entries = [item.filename for item in wheel.infolist()
                           if item.filename.startswith("swcli/") and not item.is_dir()]
        require(len(package_entries) == len(members) and set(package_entries) == members,
                "wheel package file set differs from the declared commit")
        for name in sorted(members):
            expected = (root / "src" / name).read_bytes()
            actual = (installed / name.removeprefix("swcli/")).read_bytes()
            require(wheel.read(name) == expected == actual,
                    "source, wheel and installed package differ: " + name)
    return dict(wheel_sha256=actual_sha256, wheel_filename=wheel_path.name,
                package_files_verified=len(members), installed_version=dist.version)


def exact_source(expected_head, *, local_wheel=None, wheel_sha256=None):
    if local_wheel is None:
        require_ci_route(expected_head)
    else:
        require_local_route()
    root=CI.parents[1]
    checked=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    require(checked==expected_head,"checkout head differs from declared source")
    if local_wheel is not None:
        branch_head = subprocess.check_output(["git", "rev-parse", "--verify", NEXT_REF], cwd=root, text=True).strip()
        require(branch_head == expected_head, "local next branch differs from the declared source")
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
    proof = dict(source_commit=checked, installed_files_sha256=hashes,
                 entrypoint="local-windows" if local_wheel is not None else "github-workflow-dispatch")
    if local_wheel is not None:
        proof.update(verify_local_wheel(root, checked, installed, local_wheel, wheel_sha256))
    return proof


def require_local_installation(swconst, sldworks):
    from gate_support.unit_owned_native import EXPECTED_CI_IMAGE

    executable = Path(EXPECTED_CI_IMAGE)
    require(executable.is_file(), "local SOLIDWORKS is missing from " + str(executable))
    for typelib, filename in ((swconst, "swconst.tlb"), (sldworks, "sldworks.tlb")):
        expected = executable.with_name(filename)
        require(expected.is_file() and typelib.samefile(expected),
                "local verification requires the installed type library " + str(expected))


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
    parser.add_argument("--local-windows", action="store_true", help="verify from a local installed Windows checkout")
    parser.add_argument("--wheel", type=Path, help="original wheel used to install SWCLI in local mode")
    parser.add_argument("--wheel-sha256", help="SHA256 of the prepared wheel in local mode")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if re.fullmatch(r"[0-9a-f]{40}",args.expected_head) is None:parser.error("full lowercase commit SHA required")
    local_args = []
    if args.local_windows:
        if args.wheel is None or re.fullmatch(r"[0-9a-fA-F]{64}", args.wheel_sha256 or "") is None:
            parser.error("--local-windows requires --wheel and its full SHA256 in --wheel-sha256")
        args.wheel = args.wheel.resolve()
        args.wheel_sha256 = args.wheel_sha256.lower()
        local_args = ["--local-windows", "--wheel", str(args.wheel), "--wheel-sha256", args.wheel_sha256]
        proof = exact_source(args.expected_head, local_wheel=args.wheel, wheel_sha256=args.wheel_sha256)
    else:
        if args.wheel is not None or args.wheel_sha256 is not None:
            parser.error("wheel arguments require --local-windows")
        proof = exact_source(args.expected_head)
    require(args.swconst.is_file() and args.sldworks.is_file(),"both installed official type libraries are required")
    if args.local_windows:
        require_local_installation(args.swconst, args.sldworks)
    if args.worker:
        parent_proof = json.loads((args.output_dir / "source-proof-parent.json").read_text(encoding="utf-8"))
        require(proof == parent_proof, "worker provenance differs from the supervisor preflight")
        from gate_support.revolve_direction_native import NativeBackend
        durable(args.output_dir/"source-proof.json",proof)
        report=run_direction(NativeBackend(args.output_dir,args.swconst,args.sldworks),Evidence(args.output_dir),args.expected_head)
        print(json.dumps(dict(success=report["success"],failure=report.get("failure"),public_acceptance=False)))
        return 0 if report["success"] else 1
    output=args.output_dir.resolve()
    output.mkdir(parents=True,exist_ok=False)
    durable(output/"source-proof-parent.json",proof)
    if args.local_windows:
        with (output / "verify-installed.log").open("wb") as receipt:
            subprocess.run([sys.executable, "-I", str(CI / "verify-installed.py")],
                           check=True, stdout=receipt, stderr=subprocess.STDOUT)
    command=[sys.executable,"-I",str(Path(__file__).resolve()),"--worker","--expected-head",args.expected_head,
        "--output-dir",str(output),"--swconst",str(args.swconst.resolve()),"--sldworks",str(args.sldworks.resolve()), *local_args]
    return supervise(command,output)


if __name__=="__main__":raise SystemExit(main())
