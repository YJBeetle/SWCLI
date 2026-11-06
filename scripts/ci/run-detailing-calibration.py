"""Run one owned calibration process, bounded to 600s per traced call and 1800s total."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def timeout_reason(started, now, records):
    if now - started > 1800:
        return "calibration exceeded the 1800-second group budget"
    # Each harness boundary encloses its native calls. Limiting the whole
    # boundary to 600s also bounds every individual nested native call.
    pending = {}
    for record in records:
        name = record.get("call")
        if record.get("phase") == "begin":
            pending[name] = record["time"]
        elif record.get("phase") in ("end", "error"):
            pending.pop(name, None)
    if any(now - began > 600 for began in pending.values()):
        return "native calibration call exceeded the 600-second budget"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", required=True)
    parser.add_argument("--drawing-template", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir()
    evidence = args.output_dir / "calibration"
    command = [sys.executable, "-I", str(Path(__file__).with_name("verify-detailing-calibration.py")),
               "--output-dir", str(evidence), "--swconst", args.swconst,
               "--drawing-template", args.drawing_template]
    started = time.time()
    receipt = dict(schema_version=1, source_commit=os.environ.get("GITHUB_SHA"),
                   public_acceptance=False, native_timeout_seconds=600, group_timeout_seconds=1800)
    with (args.output_dir / "stdout.log").open("wb") as stdout, (args.output_dir / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        receipt["process_id"] = process.pid
        while process.poll() is None:
            records = []
            trace = evidence / "trace.jsonl"
            if trace.exists():
                for line in trace.read_text(encoding="utf-8").splitlines():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # Ignore only an in-progress final line.
            reason = timeout_reason(started, time.time(), records)
            if reason:
                receipt["failure"] = reason
                (args.output_dir / "watchdog.json").write_text(json.dumps(receipt, indent=2) + "\n")
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                process.wait(timeout=30)
                break
            time.sleep(1)
    receipt.update(returncode=process.returncode, elapsed_seconds=time.time() - started)
    receipt["success"] = process.returncode == 0 and "failure" not in receipt
    (args.output_dir / "watchdog.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
