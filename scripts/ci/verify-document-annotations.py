"""Installed public CLI gate for the seven bounded document annotation scalars.

Uses prepared native fixtures and a trace-enabled, already owned hidden daemon.
No COM access, host restart, API retry, or source-file save is performed here.
"""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PureWindowsPath
import time

from swcli import __version__
from swcli.document_annotations import ANNOTATION_FIELDS
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location(
    "_document_annotations_modeling", Path(__file__).with_name("verify-modeling.py")
)
modeling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modeling)
require = modeling.require
ARROW_FIELDS = tuple(field for field in ANNOTATION_FIELDS if field.startswith("arrow."))


class AnnotationSmoke(modeling.ModelingSmoke):
    def __init__(self, **arguments):
        super().__init__(request_timeout_seconds=600, depth_request_timeout_seconds=600, **arguments)
        self.group_started = time.monotonic()
        self.record["group_timeout_seconds"] = 1800

    def command(self, *arguments, **keywords):
        require(self.cleaning_up or time.monotonic() - self.group_started < 1800,
                "document annotation gate exceeded its 1800-second group budget")
        result = super().command(*arguments, **keywords)
        require(self.cleaning_up or time.monotonic() - self.group_started < 1800,
                "document annotation gate exceeded its 1800-second group budget")
        return result


class NativeTrace:
    def __init__(self, path):
        self.path = path
        self.verified_requests = set()

    def verify(self, gate, *, setters, mark_dirty=None):
        event = gate.record["events"][-1]
        request_id = event["result"].get("request_id")
        require(isinstance(request_id, str) and request_id
                and request_id not in self.verified_requests,
                "annotation native evidence needs a fresh CLI request ID")
        records = []
        for line in self.path.read_text(encoding="utf-8-sig").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                require('"swcli.native-call"' not in line, "malformed native trace evidence")
                continue
            if (isinstance(record, dict) and record.get("event") == "swcli.native-call"
                    and record.get("request_id") == request_id):
                records.append(record)
        require(records, "native trace does not contain the completed annotation request")
        operation = "document." + event["command"][event["command"].index("document") + 1]
        require(all(record.get("operation") == operation for record in records),
                "native trace request operation does not match the CLI command")
        begins = Counter((r["sequence"], r["call"]) for r in records if r["phase"] == "begin")
        terminals = Counter((r["sequence"], r["call"]) for r in records if r["phase"] in ("end", "error"))
        require(begins == terminals and begins[(0, operation)] == 1
                and all(count == 1 for count in begins.values()),
                "native annotation call boundaries are missing or repeated")
        require(records[0].get("sequence") == records[-1].get("sequence") == 0
                and records[0].get("call") == records[-1].get("call") == operation
                and records[0].get("phase") == "begin"
                and records[-1].get("phase") in ("end", "error"),
                "annotation operation trace does not enclose its native calls")
        worker_pid = records[0].get("worker_pid")
        require(type(worker_pid) is int and worker_pid > 0
                and all(record.get("worker_pid") == worker_pid for record in records),
                "annotation request trace changed its owning worker")
        calls = records[1:-1]
        require(len(calls) % 2 == 0, "annotation native trace has an incomplete call pair")
        for sequence, (begin, terminal) in enumerate(zip(calls[::2], calls[1::2]), 1):
            require(type(begin.get("sequence")) is int
                    and begin["sequence"] == terminal.get("sequence") == sequence
                    and begin.get("phase") == "begin" and terminal.get("phase") in ("end", "error")
                    and begin.get("call") == terminal.get("call"),
                    "annotation native trace call ordering is invalid")
        native_setters = [r for r in records if r["phase"] == "begin"
                          and r["call"].startswith("IModelDocExtension.SetUserPreference")]
        dirty_calls = [r for r in records if r["phase"] == "begin" and r["call"] == "IModelDoc2.SetSaveFlag"]
        getters = [r for r in records if r["phase"] == "begin"
                   and r["call"].startswith("IModelDocExtension.GetUserPreference")]
        response = event["result"]
        expected_getters = (7 if operation == "document.annotation-options" else 21 if setters else
                            7 if response.get("ok") is True
                            or response.get("error", {}).get("type") == "DocumentAnnotationConflict" else 0)
        require(len(getters) == expected_getters, "annotation native preference getter count is incomplete")
        require(len(native_setters) == setters and len(dirty_calls) <= 1
                and (mark_dirty is None or len(dirty_calls) == mark_dirty),
                "annotation setter or SetSaveFlag call count does not match its lifecycle")
        getter_cycle = ["IModelDocExtension.GetUserPreference" + spec["kind"]
                        for spec in ANNOTATION_FIELDS.values()]
        expected_calls = getter_cycle if expected_getters == 7 else []
        if setters:
            command = event["command"]
            field = command[command.index("annotation-option-set") + 1]
            expected_calls = (getter_cycle + ["IModelDocExtension.SetUserPreference" + ANNOTATION_FIELDS[field]["kind"]]
                              + getter_cycle + ["IModelDoc2.SetSaveFlag"] * len(dirty_calls) + getter_cycle)
        actual_calls = [r["call"] for r in records if r["phase"] == "begin"
                        and (r["call"].startswith("IModelDocExtension.GetUserPreference")
                             or r["call"].startswith("IModelDocExtension.SetUserPreference")
                             or r["call"] == "IModelDoc2.SetSaveFlag")]
        require(actual_calls == expected_calls, "annotation native preference read/write ordering is incomplete")
        require(not any(r["call"].startswith("ISldWorks.SetUserPreference") for r in records),
                "annotation operation called a global preference setter")
        if event["result"].get("ok") is True:
            require(not any(r["phase"] == "error" for r in records), "successful annotation request has a native trace error")
        self.verified_requests.add(request_id)
        proof = {"request_id": request_id, "operation": operation,
                 "native_setter_calls": len(native_setters), "native_getter_calls": len(getters),
                 "set_save_flag_calls": len(dirty_calls),
                 "setter_methods": [r["call"] for r in native_setters]}
        gate.record.setdefault("native_call_proofs", []).append(proof)
        return proof

    def snapshot(self):
        content = self.path.read_bytes()
        return {"path": str(self.path), "prefix_size_bytes": len(content),
                "prefix_sha256": hashlib.sha256(content).hexdigest(),
                "verified_request_count": len(self.verified_requests)}


def scalar_argument(value):
    return "true" if value is True else "false" if value is False else str(value)


def read_options(gate, document, trace, *, session=None):
    result = gate.command("document", "annotation-options", document=document, session=session)
    validate_operation_result("document.annotation-options", result)
    trace.verify(gate, setters=0, mark_dirty=0)
    gate.background(result, document)
    return result


def set_option(gate, document, before, field, value, trace):
    expected = before["options"][field]["value"]
    stamp = before["document"]["update_stamp"]
    require(type(stamp) is int, "annotation options require a native document update stamp")
    result = gate.write(
        "document", "annotation-option-set", field, scalar_argument(value),
        "--if-value", scalar_argument(expected), "--if-update-stamp", stamp,
        document=document,
    )
    validate_operation_result("document.annotation-option-set", result)
    changed = value != expected
    proof = trace.verify(gate, setters=int(changed), mark_dirty=0 if not changed else None)
    require(result["before"] == before["options"] and result["changed"] is changed
            and result["options"][field]["value"] == value
            and result["mutation"] == {"attempted": changed, "may_have_changed": changed}
            and all(result["options"][other] == before["options"][other]
                    for other in ANNOTATION_FIELDS if other != field),
            "annotation write did not read back exactly one requested field")
    gate.background(result, document)
    if changed:
        require(result["document"]["modified"] is True, "changed annotation option did not mark the document dirty")
    else:
        require(result["document"] == before["document"], "same-value annotation operation changed document state")
    return {"result": result, "native_trace": proof}


def refuse(gate, trace, document, before, field, value, *, error, expected=None, session=None, stamp=None):
    arguments = ["document", "annotation-option-set", field, scalar_argument(value),
                 "--if-value", scalar_argument(before["options"][field]["value"] if expected is None else expected)]
    if stamp is not None:
        arguments.extend(["--if-update-stamp", stamp])
    if session is None:
        result = gate.write(*arguments, document=document, expected_error=error)
    else:
        result = gate.command(*arguments, document=document, session=session, expected_error=error)
    proof = trace.verify(gate, setters=0, mark_dirty=0)
    if error in ("DocumentAnnotationConflict", "ValueError"):
        require(result["mutation"] == {"attempted": False, "may_have_changed": False},
                "refused annotation request reached native mutation")
    return {"result": result, "native_trace": proof}


def targets_for(options):
    targets = {}
    for field, spec in ANNOTATION_FIELDS.items():
        value = options[field]["value"]
        if spec["kind"] == "Toggle":
            targets[field] = not value
        elif spec["kind"] == "Double":
            targets[field] = 10.0 if not math.isclose(value, 10.0, rel_tol=0, abs_tol=1e-12) else 6.35
        else:
            require(value in spec["values"], "annotation fixture has an unrecognized initial enum profile: " + field)
            targets[field] = next(candidate for candidate in spec["writable"] if candidate != value)
    require(all(targets[field] != options[field]["value"] for field in ANNOTATION_FIELDS),
            "all seven annotation values must differ from their original values")
    return targets


def open_background(gate, host_path, kind, *, read_only=False):
    opened = gate.command("document", "open", host_path, *(("--read-only",) if read_only else ()))
    descriptor = opened["document"]
    require(opened["api_errors"] == opened["api_warnings"] == 0
            and opened["read_only"] is read_only and descriptor["type"] == kind
            and descriptor["modified"] is False
            and PureWindowsPath(descriptor["path"]) == PureWindowsPath(host_path),
            "annotation fixture did not open at its exact clean path and requested access mode")
    foreground = gate.create()
    return opened, descriptor["document_id"], foreground


def geometry(gate, document):
    result = gate.measure(document)
    gate.background(result, document)
    values = result["metrics"]
    require(values["solid_body_count"] == 1 and values["volume_mm3"] > 0 and values["surface_area_mm2"] > 0,
            "annotation part fixture must contain one measurable solid")
    return values


def same_geometry(before, after):
    require(before["solid_body_count"] == after["solid_body_count"]
            and math.isclose(before["volume_mm3"], after["volume_mm3"], rel_tol=1e-9, abs_tol=1e-6)
            and math.isclose(before["surface_area_mm2"], after["surface_area_mm2"], rel_tol=1e-9, abs_tol=1e-6)
            and all(math.isclose(before["centroid_mm"][axis], after["centroid_mm"][axis],
                                 rel_tol=0, abs_tol=1e-6) for axis in ("x", "y", "z")),
            "document annotation changes altered physical part geometry")


def save_copy(gate, document, filename, suffix):
    path = gate.directory / filename
    host_path = str(PureWindowsPath(gate.host_directory) / filename)
    require(not path.exists(), "annotation output already exists")
    result = gate.write("document", "save-as", host_path, document=document)
    require(result["api_saved"] is True and result["save_errors"] == 0 and result["save_warnings"] == 0
            and result["document"]["modified"] is False
            and PureWindowsPath(result["document"]["path"]) == PureWindowsPath(host_path)
            and path.is_file() and path.stat().st_size >= 512
            and result["artifact"]["format"] == suffix
            and PureWindowsPath(result["artifact"]["path"]) == PureWindowsPath(host_path)
            and result["artifact"]["size_bytes"] == path.stat().st_size,
            "edited annotation copy did not save cleanly to its distinct native path")
    gate.background(result, document)
    return {"result": result, "path": str(path), "host_path": host_path,
            "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def same_values(gate, trace, document, current):
    results = []
    for field in ANNOTATION_FIELDS:
        row = set_option(gate, document, current, field, current["options"][field]["value"], trace)
        results.append(row)
        current = row["result"]
    return results


def run(gate, fixtures, trace, *, host_fixtures=None):
    sources = [(suffix, kind, fixtures / ("annotations." + suffix))
               for suffix, kind in (("SLDPRT", 1), ("SLDASM", 2), ("SLDDRW", 3))]
    require(all(source.is_file() for _, _, source in sources), "all three prepared annotation fixtures are required")
    gate.record.update(profile="document-annotations", state="running", success=False, annotation_cases=[],
                       evidence_kind="installed-public-cli-gate", covers_full_modeling_suite=False,
                       expected_version=__version__)
    health = gate.health()
    gate.record["host"] = health["host"]
    require(health.get("server_version") == __version__, "annotation gate daemon version differs from the installed verifier")
    host = health["host"]
    require(host.get("owned_by_daemon") is True and host.get("visible") is False
            and host.get("shared_interactive") is False,
            "annotation gate requires an independently owned hidden host")
    gate.require_empty()
    for suffix, kind, source in sources:
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        host_path = str(PureWindowsPath(host_fixtures) / source.name) if host_fixtures else str(source)
        opened, document, foreground = open_background(gate, host_path, kind)
        case = {"format": suffix, "open": opened, "source_sha256": source_hash,
                "writes": [], "value_refusals": [], "stale_value_refusals": []}
        gate.record["annotation_cases"].append(case)
        baseline = gate.command("document", "inspect", document=document)["document"]
        require(baseline["modified"] is False, "prepared annotation fixture is no longer clean")
        gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=document)
        initial = case["initial"] = read_options(gate, document, trace, session=gate.session + "-reader")
        require(initial["document"] == baseline, "annotation read changed background document state")
        if kind == 1:
            case["geometry_initial"] = geometry(gate, document)
        targets = case["changed_values"] = targets_for(initial["options"])
        first_field = next(iter(ANNOTATION_FIELDS))
        case["lease_refusal"] = refuse(
            gate, trace, document, initial, first_field, targets[first_field],
            error="DocumentLeaseConflict", session=gate.session + "-contender")
        case["stamp_refusal"] = refuse(
            gate, trace, document, initial, first_field, targets[first_field],
            error="DocumentUpdateConflict", stamp=baseline["update_stamp"] + 1)
        current = initial
        for field, value in targets.items():
            case["value_refusals"].append(refuse(
                gate, trace, document, current, field, value,
                expected=value, error="DocumentAnnotationConflict"))
            unchanged = read_options(gate, document, trace)
            require(unchanged["document"] == current["document"] and unchanged["options"] == current["options"],
                    "annotation value conflict changed options or document state")
            row = set_option(gate, document, current, field, value, trace)
            previous = current["options"][field]["value"]
            current = row["result"]
            case["writes"].append(row)
            case["stale_value_refusals"].append(refuse(
                gate, trace, document, current, field, value, expected=previous,
                stamp=current["document"]["update_stamp"], error="DocumentAnnotationConflict"))
        require(all(current["options"][field]["value"] != initial["options"][field]["value"]
                    for field in ANNOTATION_FIELDS), "the primary saved copy must change all seven fields")
        if kind == 1:
            case["geometry_changed"] = geometry(gate, document)
            same_geometry(case["geometry_initial"], case["geometry_changed"])
        primary = case["primary_save"] = save_copy(gate, document, "changed-annotations." + suffix, suffix)
        clean = read_options(gate, document, trace)
        require(clean["options"] == current["options"] and clean["document"]["modified"] is False,
                "saving changed annotation values changed their options or retained dirty state")
        case["same_values"] = same_values(gate, trace, document, clean)
        gate.close(document)
        gate.close(foreground)
        opened, fresh, foreground = open_background(gate, primary["host_path"], kind, read_only=True)
        case["primary_reopen"] = opened
        require(fresh != document, "annotation read-only reopen reused a retired document ID")
        observed = case["primary_reopened_options"] = read_options(gate, fresh, trace)
        require(observed["options"] == current["options"], "changed annotation values did not persist after reopen")
        case["read_only_refusal"] = refuse(
            gate, trace, fresh, observed, first_field,
            next(value for value in ANNOTATION_FIELDS[first_field]["writable"]
                 if value != observed["options"][first_field]["value"]), error="ValueError")
        final = read_options(gate, fresh, trace)
        require(final["options"] == observed["options"] and final["document"] == observed["document"],
                "read-only annotation refusal changed values or document state")
        if kind == 1:
            case["geometry_reopened"] = geometry(gate, fresh)
            same_geometry(case["geometry_initial"], case["geometry_reopened"])
        gate.close(fresh)
        gate.close(foreground)
        opened, reverse_document, foreground = open_background(gate, primary["host_path"], kind)
        case["reverse_open"] = opened
        require(reverse_document not in (document, fresh), "writable annotation reopen reused an old ID")
        reverse = read_options(gate, reverse_document, trace)
        require(reverse["options"] == current["options"], "writable reopen lost the changed annotation options")
        gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=reverse_document)
        case["reverse_writes"] = []
        case["reverse_values"] = {}
        for field in ARROW_FIELDS:
            original = initial["options"][field]["value"]
            writable = ANNOTATION_FIELDS[field]["writable"]
            value = (original if original in writable else
                     next(candidate for candidate in writable if candidate != reverse["options"][field]["value"]))
            case["reverse_values"][field] = value
            row = set_option(gate, reverse_document, reverse, field, value, trace)
            case["reverse_writes"].append(row)
            reverse = row["result"]
        reversed_copy = case["reverse_save"] = save_copy(
            gate, reverse_document, "reverse-annotations." + suffix, suffix)
        gate.close(reverse_document)
        gate.close(foreground)
        opened, final_document, foreground = open_background(gate, reversed_copy["host_path"], kind, read_only=True)
        case["reverse_reopen"] = opened
        require(final_document not in (document, fresh, reverse_document), "reverse annotation reopen reused an old ID")
        reverse_observed = case["reverse_reopened_options"] = read_options(gate, final_document, trace)
        require(reverse_observed["options"] == reverse["options"], "reverse arrow values did not persist after reopen")
        case["reverse_read_only_refusal"] = refuse(
            gate, trace, final_document, reverse_observed, first_field, targets[first_field], error="ValueError")
        reverse_final = read_options(gate, final_document, trace)
        require(reverse_final["options"] == reverse_observed["options"]
                and reverse_final["document"] == reverse_observed["document"]
                and hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
                and hashlib.sha256(Path(primary["path"]).read_bytes()).hexdigest() == primary["sha256"]
                and hashlib.sha256(Path(reversed_copy["path"]).read_bytes()).hexdigest() == reversed_copy["sha256"],
                "annotation verification changed a source/copy file or read-only document state")
        if kind == 1:
            case["geometry_reverse_reopened"] = geometry(gate, final_document)
            same_geometry(case["geometry_initial"], case["geometry_reverse_reopened"])
        gate.close(final_document)
        gate.close(foreground)
        gate.require_empty(after_case="document-annotations-" + suffix)
        case["success"] = True
        gate.checkpoint("document-annotations-" + suffix + "-verified")
    gate.record["host_after"] = gate.health()["host"]
    require(gate.record["host_after"] == gate.record["host"], "annotation gate replaced its owned host")
    gate.record.update(state="completed", success=True,
                       elapsed_seconds=time.monotonic() - gate.group_started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--fixture-dir", required=True, type=Path)
    parser.add_argument("--native-trace", required=True, type=Path,
                        help="stderr file from daemon started with SWCLI_TRACE_NATIVE_CALLS=1")
    parser.add_argument("--endpoint", default=os.environ.get("SWCLI_ENDPOINT", modeling.DEFAULT_ENDPOINT))
    parser.add_argument("--host-fixture-dir", type=modeling.host_directory)
    parser.add_argument("--host-output-dir", type=modeling.host_directory)
    parser.add_argument("--cli-command", type=modeling.executable)
    args = parser.parse_args(argv)
    require(args.native_trace.is_file(), "a trace-enabled daemon stderr file is required")
    trace = NativeTrace(args.native_trace)
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    gate = AnnotationSmoke(directory=directory, host_directory=args.host_output_dir or str(directory),
                           cli=[args.cli_command] if args.cli_command else None, endpoint=args.endpoint)
    gate.record_path = directory / "document-annotations.json"
    with gate.record_path.open("x", encoding="utf-8") as stream:
        json.dump(gate.record, stream)
    try:
        run(gate, args.fixture_dir, trace, host_fixtures=args.host_fixture_dir)
    except BaseException as exc:
        gate.record.update(state="failed", success=False, error={"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        gate.cleanup()
        if gate.record["cleanup_errors"] or gate.checkpoint_error is not None:
            gate.record.update(state="failed", success=False)
        try:
            gate.record["native_trace_snapshot"] = trace.snapshot()
        except Exception as exc:
            gate.record.update(state="failed", success=False)
            gate.checkpoint_error = gate.checkpoint_error or exc
        gate.checkpoint("document-annotations-final")
    if gate.checkpoint_error is not None:
        raise gate.checkpoint_error
    require(not gate.record["cleanup_errors"], "annotation gate cleanup failed")


if __name__ == "__main__":
    main()
