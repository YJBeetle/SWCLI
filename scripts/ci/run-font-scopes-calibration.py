"""Hard watchdog for the single internal font-scopes worker, never a host killer."""

import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support import font_worker_process as supervision

NATIVE_TIMEOUT_SECONDS = 600
GROUP_TIMEOUT_SECONDS = 1800
WORKERS = {
    "internal": "verify-font-scopes-calibration.py",
    "next-fixture": "prepare-font-scopes-next-fixture.py",
    "inheritance-seed": "verify-font-scopes-inheritance.py",
    "inheritance-observe": "verify-font-scopes-inheritance.py",
}


def worker_command(args, output):
    profile = args.profile
    if profile not in WORKERS:
        raise ValueError("unsupported font calibration profile")
    scope = getattr(args, "scope", None)
    if scope is not None and (profile not in ("internal", "next-fixture") or scope not in ("dimensions", "tables")):
        raise ValueError("a next font scope requires internal or next-fixture and dimensions/tables")
    if profile == "next-fixture" and scope is None:
        raise ValueError("next fixture preparation requires a dimensions/tables scope")
    command = [sys.executable, "-I", str(Path(__file__).with_name(WORKERS[profile])),
               "--output-dir", str(output / "native"), "--swconst", str(args.swconst),
               "--drawing-template", str(args.drawing_template)]
    if scope is not None:
        command.extend(["--scope", scope])
    drawing, digest = getattr(args, "inheritance_drawing", None), getattr(args, "inheritance_sha256", None)
    if drawing is not None or digest is not None:
        if scope is None or drawing is None or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("inheritance requires one next scope, a drawing and its exact SHA-256")
        command.extend(["--inheritance-drawing", str(drawing.resolve()), "--inheritance-sha256", digest])
    if profile == "next-fixture" and scope == "dimensions" and drawing is None:
        raise ValueError("dimensions requires a manually generated drawing and its SHA-256")
    if profile in ("inheritance-seed", "inheritance-observe"):
        command.extend(["--phase", "seed" if profile == "inheritance-seed" else "observe"])
    if profile == "inheritance-observe":
        if args.fixture_dir is None or args.gate_dir is None:
            raise ValueError("inheritance observer requires fixture-dir and gate-dir")
        command.extend(["--fixture-dir", str(args.fixture_dir), "--gate-dir", str(args.gate_dir)])
    return command


def source_head(args, environment):
    explicit = getattr(args, "source_head", None)
    inherited = environment.get("GITHUB_SHA")
    head = explicit or inherited
    if explicit is not None:
        if not isinstance(explicit, str) or re.fullmatch(r"[0-9a-f]{40}", explicit) is None:
            raise ValueError("explicit font source head must be exact")
        if inherited and explicit != inherited:
            raise ValueError("explicit font source head differs from GITHUB_SHA")
    if getattr(args, "scope", None) is not None:
        if not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40}", head) is None:
            raise ValueError("next font scope requires an exact source head")
    return head


def timeout_reason(elapsed, call_elapsed):
    if elapsed >= GROUP_TIMEOUT_SECONDS:
        return "group-timeout"
    if call_elapsed >= NATIVE_TIMEOUT_SECONDS:
        return "native-call-timeout"
    return None


def monitor(process, output, *, clock=time.monotonic, sleep=time.sleep):
    started = last_boundary = clock()
    trace = output / "native" / "trace.jsonl"
    observed = b""
    while process.poll() is None:
        current = trace.read_bytes() if trace.exists() else b""
        if current != observed:
            # The worker emits a flushed begin/end/error boundary around each
            # synchronous operation. An entire dispatcher call, including all
            # property getters/setters, must complete inside the 600s budget.
            observed = current
            last_boundary = clock()
        reason = timeout_reason(clock() - started, clock() - last_boundary)
        if reason:
            process.kill()  # exact Popen child only, never taskkill/process search
            process.wait(timeout=10)
            return {"success": False, "reason": reason, "elapsed_seconds": clock() - started,
                    "terminated_pid": process.pid, "terminated_scope": "this-python-worker-only"}
        sleep(0.25)
    report_path = output / "native" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return {"success": process.returncode == 0 and report.get("success") is True,
            "worker_exit_code": process.returncode, "elapsed_seconds": clock() - started,
            "first_failure": report.get("failure"), "cleanup_errors": report.get("cleanup_errors", [])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--swconst", required=True, type=Path)
    parser.add_argument("--drawing-template", required=True, type=Path)
    parser.add_argument("--profile", choices=tuple(WORKERS), default="internal")
    parser.add_argument("--source-head", help="exact next checkout head; must match GITHUB_SHA when set")
    parser.add_argument("--scope", choices=("dimensions", "tables"), help="internal next candidate only")
    parser.add_argument("--inheritance-drawing", type=Path, help="isolated owned drawing fixture for one scope")
    parser.add_argument("--inheritance-sha256", help="SHA-256 of the supplied inheritance drawing")
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--gate-dir", type=Path)
    parser.add_argument("--supervision-probe", action="store_true", help="verify the scoped Windows launch without COM")
    args = parser.parse_args(argv)
    head = source_head(args, os.environ)
    output = args.output_dir.resolve()
    command = worker_command(args, output)
    bound = sys.platform == "win32" and args.scope is not None
    if args.supervision_probe and not bound:
        parser.error("--supervision-probe requires a scoped Windows worker")
    env = {**os.environ, **({"GITHUB_SHA": head} if head else {}), "SWCLI_TRACE_NATIVE_CALLS": "1"}
    launch = {}
    if bound:
        executable, env = supervision.base_launch(env)
        command[0] = executable
        command.extend(["--watchdog-pid", str(os.getpid()), "--watchdog-prefix", sys.prefix])
        if args.supervision_probe:
            command.append("--supervision-probe")
        launch = {"executable": executable, "stdin": subprocess.PIPE}
    output.mkdir(parents=True, exist_ok=False)
    record = {"evidence_kind": ("internal-native-calibration" if args.profile == "internal" else
                                "native-fixture-seed" if args.profile in ("inheritance-seed", "next-fixture") else
                                "native-observer-of-public-output"), "profile": args.profile, "public_acceptance": False,
              "source_head": head, "requested_scope": args.scope, "native_timeout_seconds": NATIVE_TIMEOUT_SECONDS,
              "group_timeout_seconds": GROUP_TIMEOUT_SECONDS, "retry_count": 0, "host_restart_count": 0,
              "automatic_rollback": False, "success": False}
    if args.supervision_probe:
        record.update(evidence_kind="windows-process-supervision-probe", native_executed=False)
    if args.profile == "next-fixture":
        record["preparation_only"] = True
        record["inheritance_acceptance"] = False
    if args.inheritance_drawing is not None:
        record["inheritance_fixture_sha256"] = args.inheritance_sha256
        record["inheritance_acceptance"] = False  # independent limited witness is in the worker report
    if bound:
        record.update(supervisor_pid=os.getpid(), launch_executable=executable, supervisor_prefix=sys.prefix,
                      supervision_probe=args.supervision_probe, supervision_verified=False)
    record_path = output / "watchdog.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with (output / "worker.stdout.log").open("xb") as stdout, (output / "worker.stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, **launch)
        try:
            record["worker_pid"] = process.pid
            record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            if bound:
                try:
                    with process.stdin as pipe:
                        pipe.write(f"{process.pid}\n".encode("ascii"))
                except OSError as exc:
                    record["supervision_pipe_error"] = str(exc)
            record.update(monitor(process, output))
            if bound:
                try:
                    supervision.check_worker_proof(
                        output / "native/supervision.json", worker_pid=process.pid, parent_pid=os.getpid(),
                        executable=executable, prefix=sys.prefix)
                    record["supervision_verified"] = True
                except (OSError, KeyError, TypeError, ValueError) as exc:
                    record["supervision_error"] = str(exc)
                if args.supervision_probe and record.get("worker_exit_code") == 0:
                    record["success"] = not any((output / "native" / name).exists()
                                                for name in ("report.json", "trace.jsonl"))
                record["success"] = (record["success"] and record["supervision_verified"]
                                     and "supervision_pipe_error" not in record)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
