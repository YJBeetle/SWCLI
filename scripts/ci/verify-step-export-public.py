"""Public CLI/daemon STEP acceptance group; all CAD writes use the worker.

This is independent of internal calibration. No COM imports, native retry or
host replacement. A separate output-readback group imports these actual files.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid

from swcli.hosts.windows_step_export import verify_step_output
from swcli.result_schemas import validate_operation_result
from swcli.sdk import Client
from swcli.mcp import DaemonBridge

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.step_fixture_checks import verify_source_sketch


def checked(value, message):
    if not value:
        raise RuntimeError(message)


def validate_public_result(operation, value):
    # CLI adds transport correlation metadata; the operation schema validates
    # exactly the native result, while the raw file retains these fields.
    validate_operation_result(operation, {key: item for key, item in value.items()
                                         if key not in ("request_id", "replayed")})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    output.mkdir()
    report = dict(success=False, source_commit=os.environ.get("GITHUB_SHA"), evidence_scope="step-public-cli-daemon", events=[], outputs=[], cleanup_errors=[])
    session = "step-public-" + uuid.uuid4().hex[:12]
    report["session_id"] = session
    documents = {}
    daemon = None
    host_handle = None
    def persist():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    def expire():
        (output / "timeout.json").write_text(json.dumps(dict(success=False, reason="public-group-1800s")) + "\n")
        os._exit(124)
    watchdog = threading.Timer(1800, expire)
    watchdog.daemon = True
    watchdog.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = "127.0.0.1:" + str(port)
    report["endpoint"] = endpoint
    def cli(label, *arguments, operation=None, error=None, parse_error=False, chosen_session=None):
        event = dict(label=label, arguments=list(arguments), state="running", timeout_seconds=600)
        report["events"].append(event)
        persist()
        command = [sys.executable, "-I", "-m", "swcli", "--endpoint", endpoint,
                   "--session", chosen_session or session, "--request-timeout", "600", *map(str, arguments), "--json"]
        try:
            completed = subprocess.run(command, capture_output=True, timeout=610)
            stdout, stderr = completed.stdout.decode("utf-8-sig"), completed.stderr.decode("utf-8", errors="replace")
            (output / (label + ".stdout.json")).write_text(stdout, encoding="utf-8")
            (output / (label + ".stderr.log")).write_text(stderr, encoding="utf-8")
            event.update(returncode=completed.returncode, state="returned")
            if parse_error:
                checked(completed.returncode == 2, "illegal CLI option was not rejected before export")
                return None
            value = json.loads(stdout)
            event["result"] = value
            persist()
            if error:
                checked(completed.returncode != 0 and not value.get("ok", value.get("success", False))
                        and value["error"].get("type", value["error"].get("code")) == error,
                        label + " did not preserve expected error: " + str(value))
            else:
                checked(completed.returncode == 0 and value.get("ok", value.get("success", False)),
                        label + " failed: " + str(value))
                if operation:
                    validate_public_result(operation, value)
            return value
        except BaseException as exc:
            event.update(state="failed", error=repr(exc))
            persist()
            raise
    def context(document, lease, stamp):
        return ["--document", document, "--lease", lease, "--expected-update-stamp", str(stamp)]
    def stamp(document):
        return cli("inspect-" + str(len(report["events"])), "document", "inspect", "--document", document,
                   operation="document.inspect")["document"]["update_stamp"]
    def verify_output(path, protocol, geometry, value, surface):
        validate_public_result("document.export", value)
        checked(value["ok"] and not value["document"]["active"] and not value["document"]["current"],
                "background export changed foreground/current")
        checked(value["step_preferences"]["restored"] and
                value["step_preferences"]["before"] == value["step_preferences"]["after"], "preferences leaked")
        actual = verify_step_output(path, protocol, geometry)
        checked(value["step_output"] == actual and path.stat().st_size == value["artifact"]["size_bytes"]
                and Path(value["output"]) == path and Path(value["artifact"]["path"]) == path
                and value["artifact"]["format"] == path.suffix[1:].upper(),
                "public metadata differs from actual output")
        report["outputs"].append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                      protocol=protocol, geometry=geometry, surface=surface, content=actual))
        persist()
    stdout_file = (output / "daemon.stdout.log").open("wb")
    stderr_file = (output / "daemon.stderr.log").open("wb")
    try:
        daemon = subprocess.Popen([sys.executable, "-I", "-m", "swcli", "daemon", "serve",
                                   "--port", str(port), "--tray", "off", "--startup-timeout", "120"],
                                  stdout=stdout_file, stderr=stderr_file,
                                  env={**os.environ, "SWCLI_TRACE_NATIVE_CALLS": "1"})
        report["daemon_pid"] = daemon.pid
        (output / "daemon.pid").write_text(str(daemon.pid))
        if os.environ.get("SWCLI_SMOKE_ROOT"):
            (Path(os.environ["SWCLI_SMOKE_ROOT"]) / "swclid.pid").write_text(str(daemon.pid))
        deadline = time.monotonic() + 150
        while True:
            checked(daemon.poll() is None, "daemon exited during startup; no restart attempted")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                checked(time.monotonic() < deadline, "daemon readiness deadline expired")
                time.sleep(1)
        host = cli("host-before", "daemon", "status")["result"]["host"]
        import win32api
        import win32con
        host_handle = win32api.OpenProcess(win32con.SYNCHRONIZE, False, host["process_id"])
        report["host"] = host
        checked(host["owned_by_daemon"] and not host["visible"] and not host["shared_interactive"],
                "public gate requires an owned hidden host")
        source = output / "public-source.SLDPRT"
        made = cli("create-box", "part", "create-box", str(source), "--width-mm", "40", "--height-mm", "30",
                   "--depth-mm", "10", operation="part.create-box")
        document = made["document"]["document_id"]
        documents[document] = None
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        lease = cli("source-lease", "document", "lease", "acquire", "--ttl-seconds", "1800", "--document", document)["lease"]["lease_id"]
        documents[document] = lease
        listing = cli("list-source-sketch", "sketch", "list", "--document", document, operation="sketch.list")
        checked(listing["count"] == 1, "public box fixture must have one source sketch")
        observed_sketch = cli("inspect-source-sketch", "sketch", "inspect", listing["sketches"][0]["sketch_id"],
                              "--document", document, operation="sketch.inspect")
        report["source_sketch_oracle"] = verify_source_sketch(observed_sketch)
        foreground = cli("create-foreground", "document", "create", "--type", "part")["document"]["document_id"]
        documents[foreground] = None
        for protocol in ("ap203", "ap214"):
            for geometry in ("solid-surface", "wireframe", "wireframe-sketches"):
                path = output / (protocol + "-" + geometry + ".step")
                value = cli(protocol + "-" + geometry, "document", "export", str(path),
                    "--step-protocol", protocol, "--step-geometry", geometry,
                    *context(document, lease, stamp(document)), operation="document.export")
                verify_output(path, protocol, geometry, value, "cli")
        # Independent public frontends use the same daemon/worker, never COM.
        client = Client(endpoint=endpoint, session_id=session, timeout_seconds=600)
        path = output / "sdk-ap214-solid-surface.STP"
        receipt = client.document.export(output=str(path), step_protocol="ap214", step_geometry="solid-surface",
            document_id=document, lease_id=lease, expected_update_stamp=stamp(document))
        report["sdk_reply"] = dict(receipt.raw)
        persist()
        value = receipt.require_result()
        verify_output(path, "ap214", "solid-surface", value, "sdk")
        path = output / "mcp-ap203-wireframe.step"
        reply = DaemonBridge(endpoint=endpoint, session_id=session, timeout_seconds=600).call("execute", dict(
            operation="document.export", parameters=dict(output=str(path), step_protocol="ap203",
                step_geometry="wireframe", include_content=False), document_id=document,
                lease_id=lease, expected_update_stamp=stamp(document)))
        report["mcp_reply"] = reply
        persist()
        checked(reply["success"], "MCP public STEP export failed")
        verify_output(path, "ap203", "wireframe", reply["result"], "mcp")
        base = ["document", "export", str(output / "rejected.step"), "--step-protocol", "ap214",
                "--step-geometry", "solid-surface"]
        cli("stale-cas", *base, *context(document, lease, stamp(document) + 1), error="DocumentUpdateConflict")
        cli("foreign-lease", *base, *context(document, lease, stamp(document)),
            chosen_session=session + "-contender", error="DocumentLeaseConflict")
        cli("illegal-protocol", "document", "export", str(output / "rejected.step"), "--step-protocol", "ap242", parse_error=True)
        checked(not (output / "rejected.step").exists(), "rejected export created output")
        cli("close-source", "document", "close", "--document", document, "--lease", lease)
        del documents[document]
        reopened = cli("reopen-readonly", "document", "open", str(source), "--read-only", operation="document.open")
        document = reopened["document"]["document_id"]
        documents[document] = None  # Retain cleanup ownership even if status validation fails.
        checked(reopened["api_errors"] == reopened["api_warnings"] == 0
                and reopened["read_only"] is True and reopened["document"]["modified"] is False,
                "public source readonly reopen returned native errors/warnings or modified state")
        measured = cli("measure-reopened-source", "document", "measure", "--document", document, operation="document.measure")
        for key, expected in (("volume_mm3", 12000), ("surface_area_mm2", 3800)):
            checked(math.isclose(measured["metrics"][key], expected, rel_tol=1e-7, abs_tol=1e-5),
                    "saved/reopened source geometry mismatch")
        checked(hashlib.sha256(source.read_bytes()).hexdigest() == digest, "source native file bytes changed")
        report["source_sha256"] = digest
        lease = cli("readonly-lease", "document", "lease", "acquire", "--ttl-seconds", "1800", "--document", document)["lease"]["lease_id"]
        documents[document] = lease
        cli("readonly-export-rejected", *base, *context(document, lease, stamp(document)), error="ValueError")
        checked(not (output / "rejected.step").exists(), "readonly export created output")
        after = cli("host-after", "daemon", "status")["result"]["host"]
        checked(after["process_id"] == host["process_id"] and after["revision"] == host["revision"], "native host changed")
        report["host_after"] = after
        report["success"] = True
    except BaseException as exc:
        report["failure"] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc(),
                                 outcome_unknown=getattr(exc, "outcome_unknown", False))
        if hasattr(exc, "raw"):
            report["failure"]["raw_response"] = exc.raw
    finally:
        for document, lease in list(documents.items()):
            try:
                extra = ["--lease", lease] if lease else []
                cli("cleanup-" + document, "document", "close", "--discard", "--document", document, *extra)
            except Exception as exc:
                report["cleanup_errors"].append(dict(document=document, error=repr(exc)))
        if daemon is not None:
            try:
                cli("daemon-stop", "daemon", "stop")
                daemon.wait(timeout=20)
                checked(daemon.returncode == 0, "daemon did not exit cleanly")
                if host_handle is not None:
                    import win32event
                    checked(win32event.WaitForSingleObject(host_handle, 10000) == win32event.WAIT_OBJECT_0,
                            "owned SOLIDWORKS process exit was not confirmed")
            except Exception as exc:
                report["cleanup_errors"].append(dict(stage="daemon-stop", error=repr(exc)))
                if daemon.poll() is None:
                    daemon.kill()
        if host_handle is not None:
            host_handle.Close()
        watchdog.cancel()
        stdout_file.close()
        stderr_file.close()
        report["success"] = report["success"] and not report["cleanup_errors"]
        persist()
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
