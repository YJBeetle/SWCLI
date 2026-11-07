"""Run two explicit 1800-second groups, preserving first failure and all output."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

GROUP_TIMEOUT = 1800
NATIVE_TIMEOUT = 600


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    root = args.output_dir.resolve()
    scripts = Path(__file__).resolve().parent
    report = {"success": False, "full_acceptance_eligible": False,
              "source_commit": os.environ.get("GITHUB_SHA"), "native_timeout_seconds": NATIVE_TIMEOUT,
              "group_timeout_seconds": GROUP_TIMEOUT, "groups": [], "cleanup_errors": []}
    daemon = None
    def persist():
        (root/"targeted.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    def command(name, args, timeout):
        item = {"name": name, "args": args, "timeout_seconds": timeout, "success": False}
        report["groups"].append(item); persist()
        with (root/(name+".stdout.log")).open("wb") as stdout, (root/(name+".stderr.log")).open("wb") as stderr:
            try:
                result = subprocess.run(args, stdout=stdout, stderr=stderr, timeout=timeout,
                                        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                item["exit_code"] = result.returncode
                if result.returncode:
                    raise RuntimeError(name + " failed; inspect original logs/report")
                item["success"] = True
            except BaseException as error:
                item["error"] = {"type": type(error).__name__, "message": str(error)}
                raise
            finally: persist()
    host, port = "127.0.0.1", 45191
    endpoint = f"{host}:{port}"
    daemon_ready = False
    try:
        command("internal-calibration", [sys.executable, "-I", str(scripts/"verify-topology-calibration.py"),
            "--output-dir", str(root/"internal"), "--swconst", str(args.swconst)], GROUP_TIMEOUT)
        # A separate public group starts one owned host exactly once. No restart
        # inside either group, including after any failure or timeout.
        with (root/"daemon.stdout.log").open("wb") as stdout, (root/"daemon.stderr.log").open("wb") as stderr:
            daemon = subprocess.Popen([sys.executable, "-I", "-m", "swcli", "daemon", "serve",
                "--host", host, "--port", str(port), "--startup-timeout", "120"], stdout=stdout, stderr=stderr,
                env={**os.environ, "SWCLI_TRACE_NATIVE_CALLS": "1"})
            deadline = time.monotonic() + 180
            while True:
                if daemon.poll() is not None:
                    raise RuntimeError("targeted daemon exited during startup")
                for line in (root/"daemon.stdout.log").read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(message, dict) or message.get("action") != "daemon.serve":
                        continue
                    if message.get("ok") is not True or message.get("endpoint") != endpoint:
                        raise RuntimeError(f"targeted daemon did not confirm {endpoint}: {message!r}")
                    daemon_ready = True
                    break
                if daemon_ready:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("targeted daemon startup exceeded 180 seconds")
                time.sleep(0.5)
            command("public-proof", [sys.executable, "-I", str(scripts/"verify-topology-references.py"),
                "--output-dir", str(root/"public"), "--host-output-dir", str(root/"public"),
                "--endpoint", endpoint, "--request-timeout", str(NATIVE_TIMEOUT),
                "--depth-request-timeout", str(NATIVE_TIMEOUT)], GROUP_TIMEOUT)
            report["success"] = True
    except BaseException as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if daemon_ready and daemon.poll() is None:
            try:
                command("shutdown", [sys.executable, "-I", "-m", "swcli", "--endpoint", endpoint,
                    "--request-timeout", "30", "daemon", "stop", "--json"], 45)
                daemon.wait(timeout=30)
                if daemon.returncode != 0:
                    raise RuntimeError("owned daemon exit was nonzero")
            except BaseException as error:
                report["cleanup_errors"].append({"type": type(error).__name__, "message": str(error)})
        report["success"] = report["success"] and not report["cleanup_errors"]
        persist()
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
