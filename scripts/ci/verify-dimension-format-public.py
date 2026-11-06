"""Installed public CLI/daemon acceptance of calibrated dimension display fields.

Prepared fixtures only. No COM calls, host restart, failed API retry or rollback.
Native traces are joined to each CLI request; source and saved bytes are hashed.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import time

from swcli import __version__
from swcli.document_dimension_format import POSITIONS
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location("_dimension_public_annotations", Path(__file__).with_name("verify-document-annotations.py"))
annotations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(annotations)
require = annotations.require


class DimensionSmoke(annotations.AnnotationSmoke):
    def command(self, *arguments, **keywords):
        if not self.cleaning_up:
            remaining = 1800 - (time.monotonic() - self.group_started) - 15
            require(remaining > 0, "dimension display group exceeded 1800 seconds")
            keywords["timeout_seconds"] = min(600, remaining, keywords.get("timeout_seconds", 600))
        return super().command(*arguments, **keywords)


class DimensionTrace(annotations.NativeTrace):
    def verify(self, gate, *, setters, mark_dirty=None):
        event = gate.record["events"][-1]
        request = event["result"].get("request_id")
        require(isinstance(request, str) and request and request not in self.verified_requests, "missing or repeated public request identity")
        rows = []
        for line in self.path.read_text(encoding="utf-8-sig").splitlines():
            try: row = json.loads(line)
            except ValueError:
                require('"swcli.native-call"' not in line, "malformed native trace")
                continue
            if isinstance(row, dict) and row.get("event") == "swcli.native-call" and row.get("request_id") == request: rows.append(row)
        require(rows, "public dimension request has no native trace")
        operation = "document." + event["command"][event["command"].index("document") + 1]
        require(all(row["operation"] == operation and row["worker_pid"] == rows[0]["worker_pid"] for row in rows), "native trace worker/operation changed")
        require(type(rows[0]["worker_pid"]) is int and rows[0]["worker_pid"] > 0, "native worker identity missing")
        begins = Counter((r["sequence"], r["call"]) for r in rows if r["phase"] == "begin")
        ends = Counter((r["sequence"], r["call"]) for r in rows if r["phase"] in ("end", "error"))
        require(begins == ends and begins[(0, operation)] == 1 and all(n == 1 for n in begins.values()), "native call was missing, repeated or unfinished")
        require(rows[0]["sequence"] == rows[-1]["sequence"] == 0 and rows[0]["phase"] == "begin"
                and rows[-1]["phase"] in ("end", "error"), "native operation does not enclose its calls")
        if hasattr(self, "worker_pid"):
            require(self.worker_pid == rows[0]["worker_pid"], "public group replaced its owning worker")
        self.worker_pid = rows[0]["worker_pid"]
        calls = rows[1:-1]
        require(len(calls) % 2 == 0, "native call boundaries incomplete")
        for sequence, (begin, end) in enumerate(zip(calls[::2], calls[1::2]), 1):
            require(begin["sequence"] == end["sequence"] == sequence and begin["phase"] == "begin"
                    and end["phase"] in ("end", "error") and begin["call"] == end["call"], "native call ordering invalid")
        changes = [r for r in rows if r["phase"] == "begin" and r["call"].startswith("IModelDocExtension.SetUserPreference")]
        dirty = [r for r in rows if r["phase"] == "begin" and r["call"] == "IModelDoc2.SetSaveFlag"]
        cycle = ["IModelDocExtension.GetUserPreferenceToggle", "IModelDocExtension.GetUserPreferenceInteger", "IModelDocExtension.GetUserPreferenceToggle"]
        reads = [r["call"] for r in rows if r["phase"] == "begin" and r["stage"] == "document-dimension-format"
                 and r["call"].startswith("IModelDocExtension.GetUserPreference")]
        response = event["result"]
        count = 4 if setters else 1 if response.get("ok") or response.get("error", {}).get("type") == "DocumentDimensionFormatConflict" or operation == "document.dimension-format" else 0
        require(reads == cycle * count and len(changes) == setters and len(dirty) <= 1
                and (mark_dirty is None or len(dirty) == mark_dirty), "native read/set/dirty lifecycle differs from public receipt")
        require(not any(r["call"].startswith("ISldWorks.SetUserPreference") for r in rows), "public edit reached a global preference setter")
        if response.get("ok"): require(not any(r["phase"] == "error" for r in rows), "successful request has native error")
        self.verified_requests.add(request)
        proof = dict(request_id=request, operation=operation, worker_pid=rows[0]["worker_pid"],
                     native_setter_calls=len(changes), native_format_getters=len(reads), set_save_flag_calls=len(dirty))
        gate.record.setdefault("native_call_proofs", []).append(proof)
        return proof


def read(gate, document, trace, *, session=None):
    result = gate.command("document", "dimension-format", document=document, session=session)
    validate_operation_result("document.dimension-format", result)
    trace.verify(gate, setters=0, mark_dirty=0)
    gate.background(result, document)
    return result


def edit(gate, document, before, field, value, trace, *, expected=None, error=None, session=None, stamp=None):
    arguments = ["document", "dimension-format-set", field, annotations.scalar_argument(value),
                 "--if-format", json.dumps(before["format"] if expected is None else expected, separators=(",", ":")),
                 "--if-update-stamp", before["document"]["update_stamp"] if stamp is None else stamp]
    if session is None:
        result = gate.write(*arguments, document=document, expected_error=error)
    else:
        result = gate.command(*arguments, document=document, session=session, expected_error=error, lease="l-deadbeef")
    validate_operation_result("document.dimension-format-set", result)
    desired = POSITIONS[value] if field == "dual_position" else value
    changed = not error and desired != before["format"][field]
    proof = trace.verify(gate, setters=int(changed), mark_dirty=0 if not changed else None)
    if error:
        if error in ("DocumentDimensionFormatConflict", "ValueError"):
            require(result["mutation"] == {"attempted": False, "may_have_changed": False}, "refused public request reached native setter")
    else:
        require(result["before"] == before["format"] and result["format"] == {**before["format"], field: desired}
                and result["changed"] is changed, "public setter changed an unrequested field or lost its snapshot")
        if not changed: require(result["document"] == before["document"], "same-value request changed native state")
        gate.background(result, document)
    return {"result": result, "native_trace": proof}


def protected(gate, document):
    return {"units": gate.command("document", "units", document=document)["units"],
            "annotations": gate.command("document", "annotation-options", document=document)["options"]}


def run(gate, fixtures, trace):
    gate.record.update(profile="document-dimension-format", evidence_kind="installed-public-cli-daemon-gate",
                       covers_full_modeling_suite=False, dimension_cases=[], source_commit=os.environ.get("GITHUB_SHA"))
    prepared_path = fixtures / "report.json"
    prepared_bytes = prepared_path.read_bytes()
    prepared = json.loads(prepared_bytes)
    require(prepared.get("success") is True and prepared.get("cleanup_errors") == []
            and prepared.get("diagnostic_case") == "document-annotations-fixture-preparation"
            and len(prepared.get("cases", [])) == 3 and all(row.get("success") is True for row in prepared["cases"]),
            "public fixtures lack completed independent preparation evidence")
    preparation = {row["document_type"]: row for row in prepared["cases"]}
    require(set(preparation) == {1, 2, 3}, "public fixture evidence lacks an exact document type")
    gate.record["fixture_report_sha256"] = hashlib.sha256(prepared_bytes).hexdigest()
    health = gate.health()
    host = gate.record["host"] = health["host"]
    require(health["server_version"] == __version__ and host["owned_by_daemon"] is True
            and host["shared_interactive"] is False and host["visible"] is False, "wrong public daemon/host")
    gate.require_empty()
    info = gate.command("capabilities", "--full")
    gate.record["capabilities"] = info
    for name in ("document.dimension-format", "document.dimension-format-set"):
        require(name in info["operations"] and name in info["operation_schemas"]
                and name in info["operation_result_schemas"], "public discovery lacks dimension format contracts")
    require(info["operation_schemas"]["document.dimension-format-set"]["x-swcli-context"]
            == {"document_id": "required", "expected_update_stamp": "required", "lease_id": "required"},
            "public discovery lost mandatory native write guards")
    for suffix, kind in (("SLDPRT", 1), ("SLDASM", 2), ("SLDDRW", 3)):
        source = fixtures / ("annotations." + suffix)
        require(source.is_file(), "prepared public fixture missing")
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        require(source_hash == preparation[kind]["file_sha256"], "prepared fixture bytes changed before public gate")
        opened, document, foreground = annotations.open_background(gate, str(source), kind)
        case = dict(format=suffix, open=opened, source_sha256=source_hash, writes=[])
        gate.record["dimension_cases"].append(case)
        gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=document)
        initial = case["initial"] = read(gate, document, trace, session=gate.session + "-reader")
        before_protected = case["protected_before"] = protected(gate, document)
        if kind == 1: case["geometry_before"] = annotations.geometry(gate, document)
        case["lease_refusal"] = edit(gate, document, initial, "dual_display", True, trace,
                                     session=gate.session + "-contender", error="DocumentLeaseConflict")
        case["stamp_refusal"] = edit(gate, document, initial, "dual_display", True, trace,
                                     stamp=initial["document"]["update_stamp"] + 1, error="DocumentUpdateConflict")
        wrong = {**initial["format"], "parentheses": not initial["format"]["parentheses"]}
        case["complete_cas_refusal"] = edit(gate, document, initial, "dual_display", True, trace,
                                            expected=wrong, error="DocumentDimensionFormatConflict")
        untouched = read(gate, document, trace)
        require(untouched["format"] == initial["format"] and untouched["document"] == initial["document"], "refused public edits changed native state")
        current = initial
        for field, value in (("dual_display", not initial["format"]["dual_display"]),
                ("dual_display", initial["format"]["dual_display"]), ("dual_display", True),
                ("dual_position", "top"), ("dual_position", "bottom"), ("dual_position", "left"),
                ("dual_position", "right"), ("parentheses", not initial["format"]["parentheses"]),
                ("parentheses", initial["format"]["parentheses"]), ("parentheses", False), ("dual_display", False)):
            row = edit(gate, document, current, field, value, trace)
            case["writes"].append(row)
            current = row["result"]
        case["protected_after"] = protected(gate, document)
        require(case["protected_after"] == before_protected, "public edits changed units or annotation/zero fields")
        if kind == 1:
            case["geometry_after"] = annotations.geometry(gate, document)
            annotations.same_geometry(case["geometry_before"], case["geometry_after"])
        saved = case["save_copy"] = annotations.save_copy(gate, document, "saved-dimension-format." + suffix, suffix)
        clean = read(gate, document, trace)
        case["same_value"] = edit(gate, document, clean, "dual_display", False, trace)
        require(case["same_value"]["result"]["document"]["modified"] is False, "same-value request dirtied saved copy")
        gate.close(document); gate.close(foreground)
        reopened, fresh, foreground = annotations.open_background(gate, saved["host_path"], kind, read_only=True)
        case["reopen"] = reopened
        require(fresh != document, "public reopen reused a stale handle")
        observed = case["reopened_format"] = read(gate, fresh, trace)
        require(observed["format"] == current["format"], "public settings did not persist after save/reopen")
        gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=fresh)
        case["readonly_refusal"] = edit(gate, fresh, observed, "dual_display", True, trace, error="ValueError")
        final = read(gate, fresh, trace)
        require(final["document"] == observed["document"] and final["format"] == observed["format"]
                and hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
                and hashlib.sha256(Path(saved["path"]).read_bytes()).hexdigest() == saved["sha256"], "readonly observation changed state or file bytes")
        if kind == 1: annotations.same_geometry(case["geometry_before"], annotations.geometry(gate, fresh))
        gate.close(fresh); gate.close(foreground)
        gate.require_empty(after_case="dimension-format-" + suffix)
        case["success"] = True
        gate.checkpoint("dimension-format-" + suffix + "-verified")
    gate.record["host_after"] = gate.health()["host"]
    require(gate.record["host_after"] == host, "public gate replaced its owned host")
    gate.record.update(state="completed", success=True, elapsed_seconds=time.monotonic() - gate.group_started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--fixture-dir", required=True, type=Path)
    parser.add_argument("--native-trace", required=True, type=Path)
    args = parser.parse_args(argv)
    require(args.native_trace.is_file(), "native trace-enabled public daemon required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gate = DimensionSmoke(directory=args.output_dir, host_directory=str(args.output_dir),
                          endpoint=os.environ.get("SWCLI_ENDPOINT", annotations.modeling.DEFAULT_ENDPOINT))
    trace = DimensionTrace(args.native_trace)
    gate.record_path = args.output_dir / "dimension-format-public.json"
    with gate.record_path.open("x") as stream: json.dump(gate.record, stream)
    try: run(gate, args.fixture_dir, trace)
    except BaseException as error:
        gate.record.update(state="failed", success=False, error=dict(type=type(error).__name__, message=str(error)))
        raise
    finally:
        gate.cleanup()
        if gate.record["cleanup_errors"] or gate.checkpoint_error: gate.record.update(state="failed", success=False)
        try: gate.record["native_trace_snapshot"] = trace.snapshot()
        except Exception as error:
            gate.record.update(state="failed", success=False)
            gate.checkpoint_error = gate.checkpoint_error or error
        gate.checkpoint("dimension-format-public-final")
    require(gate.record["success"] and not gate.record["cleanup_errors"] and gate.checkpoint_error is None, "public dimension gate did not finish cleanly")


if __name__ == "__main__": main()
