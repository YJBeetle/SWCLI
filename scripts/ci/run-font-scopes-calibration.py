"""Hard watchdog for the single internal font-scopes worker, never a host killer."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

NATIVE_TIMEOUT_SECONDS = 600
GROUP_TIMEOUT_SECONDS = 1800
WORKERS = {
    "internal": "verify-font-scopes-calibration.py",
    "inheritance-seed": "verify-font-scopes-inheritance.py",
    "inheritance-observe": "verify-font-scopes-inheritance.py",
}


def worker_command(args, output):
    profile = args.profile
    if profile not in WORKERS:
        raise ValueError("unsupported font calibration profile")
    command = [sys.executable, "-I", str(Path(__file__).with_name(WORKERS[profile])),
               "--output-dir", str(output / "native"), "--swconst", str(args.swconst),
               "--drawing-template", str(args.drawing_template)]
    if profile != "internal":
        command.extend(["--phase", "seed" if profile == "inheritance-seed" else "observe"])
    if profile == "inheritance-observe":
        if args.fixture_dir is None or args.gate_dir is None:
            raise ValueError("inheritance observer requires fixture-dir and gate-dir")
        command.extend(["--fixture-dir", str(args.fixture_dir), "--gate-dir", str(args.gate_dir)])
    return command


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
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--gate-dir", type=Path)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    command = worker_command(args, output)
    output.mkdir(parents=True, exist_ok=False)
    record = {"evidence_kind": ("internal-native-calibration" if args.profile == "internal" else
                                "native-fixture-seed" if args.profile == "inheritance-seed" else
                                "native-observer-of-public-output"), "profile": args.profile, "public_acceptance": False,
              "source_head": os.environ.get("GITHUB_SHA"), "native_timeout_seconds": NATIVE_TIMEOUT_SECONDS,
              "group_timeout_seconds": GROUP_TIMEOUT_SECONDS, "retry_count": 0, "host_restart_count": 0,
              "automatic_rollback": False, "success": False}
    record_path = output / "watchdog.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with (output / "worker.stdout.log").open("xb") as stdout, (output / "worker.stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   env={**os.environ, "SWCLI_TRACE_NATIVE_CALLS": "1"})
        record["worker_pid"] = process.pid
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        try:
            record.update(monitor(process, output))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
