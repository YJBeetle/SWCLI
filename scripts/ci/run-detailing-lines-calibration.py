"""Bound one separately authorized NEW line-default internal gate; never dispatch CI."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def timeout_reason(started, now, records):
    if now - started >= 1800:
        return "1800-second group budget exceeded"
    pending = {}
    for row in records:
        key = row.get("call")
        if row.get("phase") == "begin":
            pending[key] = row["time"]
        elif row.get("phase") in ("end", "error"):
            began = pending.pop(key, None)
            if began is not None and row["time"] - began >= 600:
                return "600-second native boundary budget exceeded"
    if any(now - value >= 600 for value in pending.values()):
        return "600-second native boundary budget exceeded"
    if now - max((r["time"] for r in records), default=started) >= 600:
        return "600-second untraced startup/cleanup budget exceeded"
    return None


def progress_records(path):
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    rows = []
    for index, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # Only tolerate a writer's incomplete last line, never a corrupt
            # completed boundary (which could hide a hung native call).
            if index != len(lines) - 1 or line.endswith("\n"):
                raise
    return rows


def worker_python():
    # Match CPython's Windows multiprocessing spawn: the venv executable
    # redirects through another process, so CreateProcess must start the base
    # interpreter directly while retaining venv path initialization.
    base = sys._base_executable
    if not os.path.isabs(base) or not Path(base).is_file():
        raise RuntimeError("absolute base Python executable unavailable")
    env = os.environ.copy()
    env.pop("__PYVENV_LAUNCHER__", None)
    if os.path.normcase(base) != os.path.normcase(sys.executable):
        env["__PYVENV_LAUNCHER__"] = sys.executable
    return base, env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--wheel", type=Path, help="exact wheel installed in this Python environment")
    parser.add_argument("--execute-owned-native", action="store_true")
    parser.add_argument("--supervision-probe", action="store_true", help="prove parent/child identity without COM")
    parser.add_argument("--public-gate", action="store_true", help="verify the installed public transport")
    args = parser.parse_args(argv)
    if sys.platform != "win32" or args.execute_owned_native == args.supervision_probe:
        parser.error("native Windows and exactly one of --execute-owned-native or --supervision-probe required")
    args.output_dir.mkdir()
    output = args.output_dir.resolve()
    evidence = output / ("public" if args.public_gate else "internal")
    base, env = worker_python()
    supervisor_pid = os.getpid()
    script = "verify-detailing-lines-public.py" if args.public_gate else "verify-detailing-lines-calibration.py"
    command = [base, "-I", str(Path(__file__).with_name(script)),
        "--output-dir", str(evidence), "--swconst", str(args.swconst.resolve()),
        "--drawing-template", str(args.drawing_template.resolve()), "--source-head", args.source_head,
        "--supervision-probe" if args.supervision_probe else "--execute-owned-native",
        "--watchdog-pid", str(supervisor_pid), "--watchdog-prefix", sys.prefix]
    if args.wheel is not None:
        command += ["--wheel", str(args.wheel.resolve())]
    receipt = dict(profile="drawing-detailing-lines-v1", source_commit=args.source_head,
        success=False, native_accepted=False, public_acceptance=False,
        supervisor_pid=supervisor_pid, launch_executable=base, supervisor_executable=sys.executable,
        supervisor_prefix=sys.prefix, supervision_probe=args.supervision_probe, public_gate=args.public_gate,
        native_timeout_seconds=600, group_timeout_seconds=1800)
    def persist():
        (output / "watchdog.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    started = time.monotonic()
    with (output / "stdout.log").open("wb") as stdout, (output / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, executable=base, stdin=subprocess.PIPE,
                                   stdout=stdout, stderr=stderr, env=env)
        receipt["process_id"] = process.pid
        persist()
        try:
            with process.stdin as handoff:
                handoff.write(f"{process.pid}\n".encode("ascii"))
        except OSError as exc:
            receipt["supervision_pipe_error"] = str(exc)
        while process.poll() is None:
            try:
                records = progress_records(evidence / "progress.jsonl")
                # Parent and child share the system monotonic clock. Wall
                # clock correction cannot extend a native/group deadline.
                failure = timeout_reason(started, time.monotonic(), records)
            except Exception as exc:
                failure = "invalid progress evidence: " + str(exc)
            if failure:
                receipt["failure"] = failure
                persist()
                try:
                    terminated = subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                    )
                    receipt["taskkill_returncode"] = terminated.returncode
                except (OSError, subprocess.TimeoutExpired) as exc:
                    receipt["termination_error"] = str(exc)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    receipt["termination_unconfirmed"] = True
                break
            time.sleep(1)
    finished = time.monotonic()
    receipt.update(returncode=process.poll(), elapsed_seconds=finished - started)
    proof_path = evidence / "supervision.json"
    if proof_path.exists() or process.returncode == 0:
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            if (proof["worker_pid"] != process.pid or proof["spawned_pid"] != process.pid
                    or proof["parent_pid"] != supervisor_pid or proof["claimed_parent_pid"] != supervisor_pid
                    or proof["isolated"] is not True
                    or os.path.normcase(proof["prefix"]) != os.path.normcase(sys.prefix)
                    or not os.path.samefile(proof["process_image"], base)):
                raise RuntimeError("supervision receipt did not match the launched child")
            receipt["supervision_verified"] = True
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            receipt["supervision_error"] = str(exc)
            if process.returncode == 0:
                receipt.setdefault("failure", "invalid supervision evidence: " + str(exc))
    if process.returncode == 0 and "failure" not in receipt:
        try:
            failure = timeout_reason(started, finished, progress_records(evidence / "progress.jsonl"))
        except Exception as exc:
            failure = "invalid terminal progress evidence: " + str(exc)
        if failure:
            receipt["failure"] = failure
    receipt["success"] = process.returncode == 0 and "failure" not in receipt
    persist()
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
