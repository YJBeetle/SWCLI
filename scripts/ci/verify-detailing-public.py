"""Public CLI/daemon gate for two drawing defaults; no COM access or host replacement."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from swcli import __version__
from swcli.document_detailing import DETAILING_FIELDS
from swcli.mcp import DaemonBridge
from swcli.result_schemas import validate_operation_result
from swcli.sdk import Client

spec = importlib.util.spec_from_file_location("_detailing_public_support", Path(__file__).with_name("verify-document-annotations.py"))
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
require = support.require


class DetailingTrace:
    def __init__(self, path):
        self.path, self.requests, self.worker = path, set(), None
        self.proofs = []

    def verify(self, request_id, operation, *, getters, setters, refused=False):
        require(request_id not in self.requests, "public request ID was reused")
        records = []
        for line in self.path.read_text(encoding="utf-8-sig").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                require('"swcli.native-call"' not in line, "malformed native trace")
                continue
            if isinstance(row, dict) and row.get("event") == "swcli.native-call" and row.get("request_id") == request_id:
                records.append(row)
        require(len(records) >= 2 and records[0].get("phase") == "begin"
                and records[-1].get("phase") in (("end", "error") if refused else ("end",))
                and records[0].get("sequence") == records[-1].get("sequence") == 0
                and records[0].get("call") == records[-1].get("call") == operation,
                "native operation trace is incomplete")
        require(all(row.get("operation") == operation and (row.get("phase") != "error" or refused and row.get("sequence") == 0) for row in records),
                "native operation trace changed operation or recorded an error")
        worker = records[0].get("worker_pid")
        require(type(worker) is int and worker > 0 and all(row.get("worker_pid") == worker for row in records),
                "native trace lacks one owning worker")
        require(self.worker is None or self.worker == worker, "public gate replaced its worker")
        self.worker = worker
        begins = Counter((row["sequence"], row["call"]) for row in records if row["phase"] == "begin")
        ends = Counter((row["sequence"], row["call"]) for row in records if row["phase"] in ("end", "error"))
        require(begins == ends and all(count == 1 for count in begins.values()), "native trace boundaries repeated or missing")
        calls = records[1:-1]
        require(len(calls) % 2 == 0, "native trace has an incomplete pair")
        for sequence, (begin, end) in enumerate(zip(calls[::2], calls[1::2]), 1):
            require(begin["sequence"] == end["sequence"] == sequence and begin["phase"] == "begin"
                    and end["phase"] == "end" and begin["call"] == end["call"], "native trace ordering is invalid")
            require(0 <= end["monotonic_seconds"] - begin["monotonic_seconds"] <= 600,
                    "native call exceeded 600 seconds")
        names = [row["call"] for row in records if row["phase"] == "begin"]
        observed_getters = names.count("IModelDocExtension.GetUserPreferenceToggle")
        observed_setters = names.count("IModelDocExtension.SetUserPreferenceToggle")
        require(observed_getters == getters and observed_setters == setters
                and names.count("IModelDoc2.SetSaveFlag") <= 1, "native getter/setter/dirty count differs")
        require(not any("SetUserPreference" in name and name != "IModelDocExtension.SetUserPreferenceToggle"
                        for name in names), "public detailing operation reached an unrequested preference setter")
        preference_calls = [name for name in names if "UserPreference" in name or name == "IModelDoc2.SetSaveFlag"]
        expected = (["IModelDocExtension.GetUserPreferenceToggle"] * 2 if not setters else
                    ["IModelDocExtension.GetUserPreferenceToggle"] * 2
                    + ["IModelDocExtension.SetUserPreferenceToggle"]
                    + ["IModelDocExtension.GetUserPreferenceToggle"] * 2
                    + ["IModelDoc2.SetSaveFlag"] * names.count("IModelDoc2.SetSaveFlag")
                    + ["IModelDocExtension.GetUserPreferenceToggle"] * 2)
        if getters == 0:
            expected = []
        require(preference_calls == expected, "native preference lifecycle ordering differs")
        self.requests.add(request_id)
        proof = dict(request_id=request_id, operation=operation, worker_pid=worker,
                     getters=getters, setters=setters, dirty_calls=names.count("IModelDoc2.SetSaveFlag"))
        self.proofs.append(proof)
        return proof

    def cli(self, gate, *, getters, setters):
        event = gate.record["events"][-1]
        command = event["command"]
        operation = "document." + command[command.index("document") + 1]
        return self.verify(event["result"]["request_id"], operation, getters=getters, setters=setters,
                           refused=event["result"].get("ok") is False)


def read(gate, trace, document):
    result = gate.command("document", "detailing-options", document=document)
    validate_operation_result("document.detailing-options", result)
    gate.background(result, document)
    trace.cli(gate, getters=2, setters=0)
    return result


def edit(gate, trace, document, before, field, value, *, expected=None, error=None, session=None, stamp=None):
    arguments = ("document", "detailing-option-set", field, "true" if value else "false",
                 "--if-options", json.dumps(before["options"] if expected is None else expected),
                 "--if-update-stamp", before["document"]["update_stamp"] if stamp is None else stamp)
    lease = gate.leases[document]
    result = gate.command(*arguments, document=document, lease=lease, session=session, expected_error=error)
    # Lease/stamp conflicts are protocol refusals before a business result.
    if error not in ("DocumentLeaseConflict", "DocumentUpdateConflict"):
        validate_operation_result("document.detailing-option-set", result)
    changed = error is None and before["options"][field] != value
    getter_count = (6 if changed else 0 if error in ("DocumentLeaseConflict", "DocumentUpdateConflict")
                    or error == "ValueError" and expected is None else 2)
    trace.cli(gate, getters=getter_count, setters=int(changed))
    if "document" in result:
        gate.background(result, document)
    if error:
        if error not in ("DocumentLeaseConflict", "DocumentUpdateConflict"):
            require(result["mutation"] == {"attempted": False, "may_have_changed": False}, "refused write attempted a mutation")
        return result
    desired = {**before["options"], field: value}
    require(result["before"] == before["options"] and result["options"] == desired
            and result["changed"] is changed
            and result["mutation"] == {"attempted": changed, "may_have_changed": changed},
            "public write changed more than its requested scalar")
    if changed:
        require(result["native_return"] is True and result["document"]["modified"] is True, "public write did not mark dirty")
    else:
        require(result["document"] == before["document"], "public no-op changed native document state")
    return result


def contracts(gate, trace, document, before):
    client = Client(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    sdk_read = client.document.detailing_options(document_id=document,
        expected_update_stamp=before["document"]["update_stamp"])
    result = sdk_read.require_result()
    require(result["options"] == before["options"] and result["document"] == before["document"], "typed SDK read differs from CLI")
    trace.verify(sdk_read.request_id, "document.detailing-options", getters=2, setters=0)
    field = next(iter(DETAILING_FIELDS))
    sdk_noop = client.document.detailing_option_set(field=field, value=before["options"][field],
        expected_options=before["options"], document_id=document,
        expected_update_stamp=before["document"]["update_stamp"], lease_id=gate.leases[document])
    result = sdk_noop.require_result()
    require(not result["changed"] and not result["mutation"]["attempted"] and result["document"] == before["document"], "typed SDK no-op mutated")
    trace.verify(sdk_noop.request_id, "document.detailing-option-set", getters=2, setters=0)
    bridge = DaemonBridge(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    capability = bridge.call("capabilities", {"operation": "document.detailing-option-set"})
    require(capability["success"], "MCP bridge capabilities failed")
    schema = capability["result"]["operation_schemas"]["document.detailing-option-set"]
    require(schema["x-swcli-context"] == {"document_id": "required", "expected_update_stamp": "required", "lease_id": "required"},
            "live capability context does not require exact write protection")
    mcp = bridge.call("execute", {"operation": "document.detailing-option-set",
        "parameters": {"field": field, "value": before["options"][field], "expected_options": before["options"]},
        "document_id": document, "expected_update_stamp": before["document"]["update_stamp"], "lease_id": gate.leases[document]})
    require(mcp["success"] and mcp["result"]["ok"], "MCP bridge no-op failed")
    validate_operation_result("document.detailing-option-set", mcp["result"])
    require(not mcp["result"]["changed"] and not mcp["result"]["mutation"]["attempted"]
            and mcp["result"]["document"] == before["document"], "MCP no-op mutated")
    trace.verify(mcp["request_id"], "document.detailing-option-set", getters=2, setters=0)
    gate.record["sdk_mcp_contracts"] = dict(sdk_read=dict(sdk_read.raw), sdk_noop=dict(sdk_noop.raw),
                                           mcp_capabilities=capability, mcp_noop=mcp, mcp_scope="real-daemon bridge; stdio contract portable-tested")


def run(gate, trace, template):
    health = gate.health()
    gate.record.update(profile="document-detailing", evidence_kind="installed-public-cli-daemon-gate",
        source_commit=os.environ.get("GITHUB_SHA"), expected_version=__version__, host=health["host"], writes=[],
        covers_full_modeling_suite=False, full_acceptance_eligible=False)
    require(health["server_version"] == __version__ and health["host"]["owned_by_daemon"] is True
            and health["host"]["visible"] is False and health["host"]["shared_interactive"] is False
            and health["host"].get("platform") == "windows",
            "public gate requires one owned hidden daemon of the installed version")
    gate.require_empty()
    made = gate.command("document", "create", "--type", "drawing", "--template", template, "--projection", "first-angle")
    require(made["created"] is True and made["views"] == [] and made["document"]["type"] == 3,
            "public drawing creation returned model views or wrong type")
    document = made["document"]["document_id"]
    foreground = gate.create()
    gate.command("document", "lease", "acquire", "--ttl-seconds", 1800, document=document)
    current = gate.record["initial"] = read(gate, trace, document)
    annotation = gate.command("document", "annotation-options", document=document)["options"]
    field = next(iter(DETAILING_FIELDS))
    edit(gate, trace, document, current, field, not current["options"][field],
         session=gate.session + "-contender", error="DocumentLeaseConflict")
    edit(gate, trace, document, current, field, not current["options"][field],
         stamp=current["document"]["update_stamp"] + 1, error="DocumentUpdateConflict")
    require(read(gate, trace, document) == current, "lease/stamp refusal changed document state")
    for field in DETAILING_FIELDS:
        for value in (not current["options"][field], current["options"][field]):
            row = dict(field=field, value=value)
            gate.record["writes"].append(row)
            stale = {**current["options"]}
            other = next(key for key in DETAILING_FIELDS if key != field)
            stale[other] = not stale[other]
            row["cas_refusal"] = edit(gate, trace, document, current, field, value, expected=stale, error="ValueError")
            unchanged = read(gate, trace, document)
            require(unchanged == current, "CAS refusal changed scalar values or document state")
            current = row["write"] = edit(gate, trace, document, current, field, value)
            row["noop"] = edit(gate, trace, document, current, field, value)
            require(gate.command("document", "annotation-options", document=document)["options"] == annotation,
                    "detailing write changed unrelated annotation scalars")
            row["save"] = support.save_copy(gate, document, "public-detailing-" + str(len(gate.record["writes"])) + ".SLDDRW", "SLDDRW")
            gate.close(document)
            gate.close(foreground)
            opened, document, foreground = support.open_background(gate, row["save"]["host_path"], 3, read_only=True)
            row["reopen"] = opened
            observed = row["reopened_options"] = read(gate, trace, document)
            require(observed["options"] == current["options"], "public saved/reopened detailing values differ")
            gate.command("document", "lease", "acquire", "--ttl-seconds", 1800, document=document)
            row["readonly_refusal"] = edit(gate, trace, document, observed, field, not value, error="ValueError")
            final = read(gate, trace, document)
            require(final == observed and hashlib.sha256(Path(row["save"]["path"]).read_bytes()).hexdigest() == row["save"]["sha256"],
                    "read-only observation/refusal changed the saved file or document")
            gate.close(document)
            gate.close(foreground)
            opened, document, foreground = support.open_background(gate, row["save"]["host_path"], 3)
            current = read(gate, trace, document)
            require(current["options"] == final["options"], "writable reopen lost detailing values")
            gate.command("document", "lease", "acquire", "--ttl-seconds", 1800, document=document)
    contracts(gate, trace, document, current)
    gate.close(document)
    gate.close(foreground)
    gate.require_empty(after_case="document-detailing-public")
    gate.record["host_after"] = gate.health()["host"]
    require(gate.record["host_after"] == gate.record["host"], "public gate replaced the owned host")
    gate.record.update(state="completed", success=True, elapsed_seconds=time.monotonic() - gate.group_started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--drawing-template", required=True)
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    directory.mkdir()
    endpoint = "127.0.0.1:18496"
    trace_path = directory / "trace.jsonl"
    gate = support.AnnotationSmoke(directory=directory, host_directory=str(directory), endpoint=endpoint)
    gate.record_path = directory / "public-detailing.json"
    gate.record["success"] = False
    # ModelingSmoke checkpoints atomically replace an existing file and retain
    # its mode. Establish that durable failure record before starting a host.
    with gate.record_path.open("x", encoding="utf-8") as stream:
        json.dump(gate.record, stream)
    daemon = None
    startup = []
    with (directory / "daemon.stdout.log").open("wb") as stdout, trace_path.open("wb") as stderr:
        try:
            daemon = subprocess.Popen([sys.executable, "-I", "-m", "swcli", "daemon", "serve", "--port", "18496",
                "--startup-timeout", "120", "--tray", "off"], stdout=stdout, stderr=stderr,
                env={**os.environ, "SWCLI_TRACE_NATIVE_CALLS": "1"})
            started = time.monotonic()
            while True:
                require(daemon.poll() is None, "owned daemon exited during startup")
                status = subprocess.run([sys.executable, "-I", "-m", "swcli", "--endpoint", endpoint,
                    "--request-timeout", "5", "daemon", "status", "--json"], capture_output=True, timeout=20)
                payload = json.loads(status.stdout.decode("utf-8-sig"))
                startup.append(payload)
                (directory / "startup.json").write_text(json.dumps(startup, indent=2) + "\n")
                if payload.get("success") is True:
                    require(payload["result"]["host_connected"] is True, "daemon status succeeded without a connected host")
                    break
                require(payload.get("error", {}).get("code") in ("ConnectionRefusedError", "Starting", "TimeoutError", "ConnectionResetError")
                        and time.monotonic() - started < 180, "daemon startup failed or timed out")
                time.sleep(1)
            trace = DetailingTrace(trace_path)
            gate.record["native_call_proofs"] = trace.proofs
            run(gate, trace, args.drawing_template)
            gate.record["native_call_proofs"] = trace.proofs
            gate.record["trace_prefix"] = dict(size_bytes=trace_path.stat().st_size,
                sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest())
        except BaseException as exc:
            gate.record.update(state="failed", success=False, error=dict(type=type(exc).__name__, message=str(exc)))
        finally:
            gate.cleaning_up = True
            gate.cleanup()
            if daemon is not None and daemon.poll() is None:
                try:
                    gate.record["daemon_stop"] = gate.command("daemon", "stop")
                    daemon.wait(timeout=30)
                    require(daemon.returncode == 0, "owned daemon did not exit cleanly")
                except Exception as exc:
                    gate.record["cleanup_errors"].append(dict(stage="daemon-stop", error=str(exc)))
            if gate.record["cleanup_errors"] or gate.checkpoint_error is not None:
                gate.record["success"] = False
            gate.checkpoint("public-detailing-final")
    return 0 if gate.record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
