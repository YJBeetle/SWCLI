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
            pending.pop(key, None)
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--execute-owned-native", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_owned_native or sys.platform != "win32":
        parser.error("separate native execution authorization and native Windows required")
    args.output_dir.mkdir()
    output = args.output_dir.resolve()
    evidence = output / "internal"
    command = [sys.executable, "-I", str(Path(__file__).with_name("verify-detailing-lines-calibration.py")),
        "--output-dir", str(evidence), "--swconst", str(args.swconst.resolve()),
        "--drawing-template", str(args.drawing_template.resolve()), "--source-head", args.source_head,
        "--execute-owned-native", "--watchdog-pid", str(os.getpid())]
    receipt = dict(profile="drawing-detailing-lines-v1", source_commit=args.source_head,
        success=False, native_accepted=False, public_acceptance=False,
        native_timeout_seconds=600, group_timeout_seconds=1800)
    def persist():
        (output / "watchdog.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    started = time.monotonic()
    with (output / "stdout.log").open("wb") as stdout, (output / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        receipt["process_id"] = process.pid
        persist()
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
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    receipt["termination_unconfirmed"] = True
                break
            time.sleep(1)
    receipt.update(returncode=process.poll(), elapsed_seconds=time.monotonic() - started)
    receipt["success"] = process.returncode == 0 and "failure" not in receipt
    persist()
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
