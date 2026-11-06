"""Installed public CLI/daemon proof for the calibrated drawing Line Font subset."""
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
from swcli.document_line_font import LINE_FONT_FIELDS
from swcli.result_schemas import validate_operation_result
from swcli.sdk import Client
from swcli.mcp import DaemonBridge

spec = importlib.util.spec_from_file_location("_line_font_public_helpers", Path(__file__).with_name("verify-document-annotations.py"))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
require = helpers.require


OBSERVATION_CALLS = {
    "ActiveDoc", "ActiveDrawingView", "ActiveSketch", "Extension", "GetCurrentSheet",
    "GetDocuments", "GetEditSheet", "GetFirstView", "GetName", "GetName2", "GetPathName",
    "GetReferencedModelName", "GetSaveFlag", "GetSketch", "GetTemplateSketch", "GetTitle",
    "GetType", "GetUpdateStamp", "IsOpenedReadOnly", "IsOpenedViewOnly", "SketchManager",
    "RevisionNumber",
}


class LineFontSmoke(helpers.AnnotationSmoke):
    def health(self):
        runtime = self.command("daemon", "status")["result"]
        status = runtime["health"]
        require(runtime["daemon_running"] is True and runtime["daemon_reachable"] is True
                and runtime["daemon_state"] == "ready" and runtime["host_connected"] is True
                and status["host_connected"] is True and status["recovery_required"] is False,
                "public line font gate requires a connected, unreplaced host")
        require(type(status["host"]["process_id"]) is int, "native host PID unavailable")
        return status


class Trace:
    def __init__(self, path, gate):
        self.path, self.gate = path, gate
        self.seen = set()

    def verify(self, raw, operation, *, getters, setters):
        request = raw["request_id"]
        require(request not in self.seen, "request was reused")
        records = [json.loads(line) for line in self.path.read_text(encoding="utf-8-sig").splitlines()
                   if line.startswith('{"event": "swcli.native-call"')]
        rows = [row for row in records if row.get("request_id") == request]
        require(rows and all(row["operation"] == operation for row in rows), "native request trace is missing/misattributed")
        require(rows[0]["sequence"] == rows[-1]["sequence"] == 0
                and rows[0]["phase"] == "begin" and rows[-1]["phase"] in ("end", "error"), "operation boundary is incomplete")
        begins = Counter((row["sequence"], row["call"]) for row in rows if row["phase"] == "begin")
        ends = Counter((row["sequence"], row["call"]) for row in rows if row["phase"] in ("end", "error"))
        require(begins == ends and all(n == 1 for n in begins.values()), "native call boundaries repeat or are incomplete")
        calls = [row["call"] for row in rows if row["phase"] == "begin" and row["sequence"] != 0]
        require(all(call in OBSERVATION_CALLS | {"IModelDocExtension.GetUserPreferenceInteger",
                    "IModelDocExtension.SetUserPreferenceInteger", "IModelDoc2.SetSaveFlag"} for call in calls),
                "unexpected native method in public operation")
        observation_calls = [call for call in calls if call in OBSERVATION_CALLS]
        calls = [call for call in calls if call not in OBSERVATION_CALLS]
        getter = "IModelDocExtension.GetUserPreferenceInteger"
        setter = "IModelDocExtension.SetUserPreferenceInteger"
        require(calls.count(getter) == getters and calls.count(setter) == setters,
                "native integer getter/setter count differs")
        require(all(call in (getter, setter, "IModelDoc2.SetSaveFlag") for call in calls)
                and calls.count("IModelDoc2.SetSaveFlag") <= 1, "unexpected native mutation")
        expected = [getter] * 4
        if setters:
            expected += [setter] + [getter] * 4
            if "IModelDoc2.SetSaveFlag" in calls:
                expected.append("IModelDoc2.SetSaveFlag")
            expected += [getter] * 4
        if getters == 0:
            expected = []
        require(calls == expected, "native line font call ordering differs")
        require(len({row["worker_pid"] for row in rows}) == 1, "worker changed within request")
        self.seen.add(request)
        proof = dict(request_id=request, operation=operation, getters=getters, setters=setters, calls=calls, observation_calls=observation_calls)
        self.gate.record.setdefault("native_call_proofs", []).append(proof)

    def cli(self, operation, **counts):
        self.verify(self.gate.record["events"][-1]["result"], operation, **counts)


def run(gate, trace, template):
    gate.record.update(evidence_kind="installed-public-cli-daemon-gate", profile="document-line-font",
                       covers_full_modeling_suite=False, expected_version=__version__)
    health = gate.health()
    host = gate.record["host"] = health["host"]
    require(health["server_version"] == __version__ and host["owned_by_daemon"] is True
            and host["visible"] is False and host["shared_interactive"] is False, "host is not owned/hidden")
    gate.require_empty()
    created = gate.command("document", "create", "--type", "drawing", "--template", template, "--projection", "first-angle")
    document = created["document"]["document_id"]
    require(created["views"] == [] and created["document"]["type"] == 3, "fixture has unexpected drawing views")
    foreground = gate.create()
    gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=document)
    source = gate.record["source"] = helpers.save_copy(gate, document, "source.SLDDRW", "SLDDRW")

    def read(document):
        result = gate.command("document", "line-font", document=document)
        validate_operation_result("document.line-font", result)
        trace.cli("document.line-font", getters=4, setters=0)
        gate.background(result, document)
        return result

    current = gate.record["initial"] = read(document)
    require(current["document"]["modified"] is False, "saved source is dirty")
    targets = {field: 1 if value != 1 else 0 for field, value in current["options"].items()}
    gate.record["targets"] = targets
    first = next(iter(LINE_FONT_FIELDS))

    def edit(field, value, snapshot, *, error=None, session=None, stamp=None, readonly=False):
        args = ["document", "line-font-set", field, value, "--if-options", json.dumps(snapshot),
                "--if-update-stamp", current["document"]["update_stamp"] if stamp is None else stamp]
        if session:
            result = gate.command(*args, document=document, session=session, expected_error=error)
        else:
            result = gate.write(*args, document=document, expected_error=error)
        counts = (0 if error in ("DocumentLeaseConflict", "DocumentUpdateConflict") or readonly else
                  4 if error or value == snapshot[field] else 12)
        trace.cli("document.line-font-set", getters=counts, setters=int(counts == 12))
        if error:
            if "mutation" in result:
                require(result["mutation"] == dict(attempted=False, may_have_changed=False), "refusal attempted mutation")
        else:
            validate_operation_result("document.line-font-set", result)
            require(result["before"] == snapshot and result["options"] == {**snapshot, field: value}, "write changed an unrequested field")
            gate.background(result, document)
        return result

    gate.record["lease_refusal"] = edit(first, targets[first], current["options"], error="DocumentLeaseConflict", session=gate.session + "-contender")
    gate.record["stamp_refusal"] = edit(first, targets[first], current["options"], error="DocumentUpdateConflict", stamp=current["document"]["update_stamp"] + 1)
    for field, value in targets.items():
        stale = {**current["options"], "hidden_edges.weight": 99}
        conflict = edit(field, value, stale, error="DocumentLineFontConflict")
        unchanged = read(document)
        require(unchanged["options"] == current["options"] and unchanged["document"] == current["document"], "CAS refusal changed document/options")
        result = edit(field, value, current["options"])
        require(result["changed"] and result["document"]["modified"], "changed defaults are not dirty")
        gate.record.setdefault("writes", []).append(result)
        gate.record.setdefault("cas_refusals", []).append(conflict)
        current = result
        observed = read(document)
        require(observed["options"] == current["options"] and observed["document"] == current["document"], "write/read state differs")
    saved = gate.record["changed_save"] = helpers.save_copy(gate, document, "changed.SLDDRW", "SLDDRW")
    current = read(document)
    require(current["options"] == targets and not current["document"]["modified"], "save changed defaults or retained dirty state")
    for field, value in targets.items():
        same = edit(field, value, current["options"])
        require(not same["changed"] and same["document"] == current["document"], "noop changed state")
        gate.record.setdefault("noops", []).append(same)

    client = Client(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    sdk_read = client.document.line_font(document_id=document, expected_update_stamp=current["document"]["update_stamp"])
    require(sdk_read.result["options"] == targets and sdk_read.result["document"] == current["document"], "SDK read differs or changed state")
    trace.verify(sdk_read.raw, "document.line-font", getters=4, setters=0)
    sdk_same = client.document.line_font_set(field=first, value=targets[first], expected_options=targets,
        document_id=document, expected_update_stamp=current["document"]["update_stamp"], lease_id=gate.leases[document])
    require(sdk_same.result["ok"] and not sdk_same.result["changed"]
            and sdk_same.result["document"] == current["document"] and sdk_same.result["options"] == targets, "typed SDK noop failed or changed state")
    trace.verify(sdk_same.raw, "document.line-font-set", getters=4, setters=0)
    bridge = DaemonBridge(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    mcp = bridge.call("execute", dict(operation="document.line-font-set", parameters=dict(field=first,
        value=targets[first], expected_options=targets), document_id=document,
        expected_update_stamp=current["document"]["update_stamp"], lease_id=gate.leases[document]))
    require(mcp["success"] and mcp["result"]["ok"] and not mcp["result"]["changed"], "MCP bridge noop failed")
    validate_operation_result("document.line-font-set", mcp["result"])
    require(mcp["result"]["document"] == current["document"] and mcp["result"]["options"] == targets, "MCP noop changed state")
    trace.verify(mcp, "document.line-font-set", getters=4, setters=0)
    gate.record["sdk_mcp_contract"] = dict(sdk_read=dict(sdk_read.raw), sdk_noop=dict(sdk_same.raw), mcp_bridge_noop=mcp,
                                          mcp_scope="live bridge execute contract; not stdio transport")
    gate.close(document)
    gate.close(foreground)
    opened, fresh, foreground = helpers.open_background(gate, saved["host_path"], 3, read_only=True)
    require(fresh != document, "reopen reused retired ID")
    document = fresh
    current = gate.record["reopened"] = read(document)
    require(current["options"] == targets and not current["document"]["modified"], "changed defaults did not persist")
    gate.record["readonly_refusal"] = edit(first, 1-targets[first], current["options"], error="ValueError", readonly=True)
    require(read(document) == current, "readonly refusal changed state")
    require(hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() == source["sha256"]
            and hashlib.sha256(Path(saved["path"]).read_bytes()).hexdigest() == saved["sha256"], "source or saved copy bytes changed")
    gate.close(document)
    gate.close(foreground)
    gate.require_empty(after_case="line-font-public")
    require(gate.health()["host"] == host, "public gate replaced host")
    gate.record.update(success=True, state="completed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True)
    stdout_path, stderr_path = directory / "daemon.stdout.log", directory / "daemon.stderr.log"
    endpoint = "127.0.0.1:18495"
    gate = LineFontSmoke(directory=directory, host_directory=str(directory), endpoint=endpoint)
    gate.record_path = directory / "line-font-public.json"
    with stdout_path.open("w") as out, stderr_path.open("w") as err:
        daemon = subprocess.Popen([sys.executable, "-I", "-m", "swcli", "daemon", "serve", "--tray", "off", "--startup-timeout", "120"],
            stdout=out, stderr=err, env={**os.environ, "SWCLI_TRACE_NATIVE_CALLS": "1"})
        ready = False
        try:
            deadline = time.monotonic() + 180
            while '"action": "daemon.serve"' not in stdout_path.read_text():
                require(daemon.poll() is None and time.monotonic() < deadline, "owned daemon startup failed")
                time.sleep(0.2)
            ready = True
            run(gate, Trace(stderr_path, gate), str(args.drawing_template))
        except BaseException as exc:
            gate.record.update(success=False, state="failed", error=dict(type=type(exc).__name__, message=str(exc)))
            raise
        finally:
            if ready:
                gate.cleanup()
            try:
                require(ready, "own daemon never reported ready; stop is not sent to an unverified endpoint")
                stopped = subprocess.run([sys.executable, "-I", "-m", "swcli", "--endpoint", endpoint, "--request-timeout", "600",
                    "daemon", "stop", "--json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=610)
                gate.record["daemon_stop"] = dict(returncode=stopped.returncode, stdout=stopped.stdout.decode("utf-8"), stderr=stopped.stderr.decode("utf-8"))
                require(stopped.returncode == 0, "owned daemon stop failed")
                daemon.wait(timeout=30)
                gate.record["daemon_exit_code"] = daemon.returncode
                require(daemon.returncode == 0, "owned daemon exit failed")
            except Exception as exc:
                gate.record["cleanup_errors"].append(dict(stage="owned-daemon-stop", type=type(exc).__name__, message=str(exc)))
            gate.record["native_trace_sha256"] = hashlib.sha256(stderr_path.read_bytes()).hexdigest()
            if gate.record["cleanup_errors"]:
                gate.record.update(success=False, state="failed")
            gate.checkpoint("line-font-public-final")
    require(gate.checkpoint_error is None and gate.record["success"], "public gate, cleanup or evidence checkpoint failed")


if __name__ == "__main__":
    main()
