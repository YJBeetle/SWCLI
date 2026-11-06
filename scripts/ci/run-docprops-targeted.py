"""Bounded single-shot hosted Windows calibration. No attach, retry or host restart."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def pending(path):
    active = None
    if not path.exists():
        return active
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if not line.endswith("\n"):
            break
        row = json.loads(line)
        if row["phase"] == "begin":
            active = row["call"]
        elif row["phase"] in ("end", "error"):
            active = None
    return active


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("requires disposable hosted Windows; never use the occupied VM")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != args.expected_head:
        parser.error("checkout does not match expected head")
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema_version=1, source_head=head, platform=sys.platform,
                   run_id=os.environ.get("GITHUB_RUN_ID"), run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT"),
                   native_timeout_seconds=600, group_timeout_seconds=1800,
                   profile="baseline-properties", exit_code=None, failure=None)
    native = args.output / "native"
    command = [sys.executable, "-I", str(Path(__file__).with_name("verify-properties-calibration.py")),
               "--output-dir", str(native), "--swconst", str(args.swconst)]
    started = call_started = time.monotonic()
    previous = None
    child = None
    try:
        with (args.output / "stdout.txt").open("w", encoding="utf-8") as out, (args.output / "stderr.txt").open("w", encoding="utf-8") as err:
            child = subprocess.Popen(command, stdout=out, stderr=err)
            while child.poll() is None:
                now = time.monotonic()
                current = pending(native / "trace.jsonl")
                if current != previous:
                    previous, call_started = current, now
                if now - started >= 1800 or (current is not None and now - call_started >= 600):
                    receipt["failure"] = dict(reason="timeout", active_call=current,
                                              cleanup="incomplete; child terminated, host exit unproven")
                    child.terminate()
                    break
                time.sleep(0.25)
            receipt["exit_code"] = child.wait(timeout=10)
    except BaseException as error:
        receipt["failure"] = dict(reason=type(error).__name__, message=str(error))
        if child is not None and child.poll() is None:
            child.kill()
            receipt["exit_code"] = child.wait(timeout=10)
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        (args.output / "driver.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0 if receipt["exit_code"] == 0 and receipt["failure"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
