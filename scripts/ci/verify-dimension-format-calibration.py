"""Opt-in owned-host internal calibration; never public acceptance evidence.

A parent supervises one worker: 600 seconds per traced operation, 1800 seconds
for the group. Stop at the first failure. No CAD retry, rollback or host restart.
"""

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict, _with_document
from swcli.document_dimension_format import DIMENSION_FORMAT_FIELDS, POSITIONS
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_custom_properties import _state
from swcli.hosts.windows_dimension_format import set_dimension_format_windows
from swcli.hosts.windows_document_annotations import _read_options
from swcli.hosts.windows_document_units import _read_units
from swcli.hosts.windows_assemblies import create_assembly_windows_with_handle
from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location("_dimension_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked
box_spec = importlib.util.spec_from_file_location("_dimension_box_oracle", Path(__file__).with_name("gate_support") / "dimension_box.py")
box = importlib.util.module_from_spec(box_spec)
box_spec.loader.exec_module(box)
observe_native = box.observe_native
KINDS = {"part": (1, "SLDPRT"), "assembly": (2, "SLDASM"), "drawing": (3, "SLDDRW")}


def constants(pythoncom, path):
    wanted = {entry[key] for entry in DIMENSION_FORMAT_FIELDS.values() for key in ("symbol", "option_symbol")}
    wanted.update("swDualDimensionsOn" + name.title() for name in POSITIONS)
    found = {}
    library = pythoncom.LoadTypeLib(str(path))
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attrs = info.GetTypeAttr()
        if attrs.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attrs.cVars):
            descriptor = info.GetVarDesc(offset)
            name = info.GetDocumentation(descriptor[0])[0]
            if name in wanted:
                checked(name not in found, "duplicate official display constant")
                found[name] = descriptor.value
    checked(set(found) == wanted, "official type library lacks display constants")
    for entry in DIMENSION_FORMAT_FIELDS.values():
        checked(found[entry["symbol"]] == entry["preference"] and found[entry["option_symbol"]] == entry["option"],
                "display preference/option mapping differs from installed official type library")
    for name, value in POSITIONS.items():
        checked(found["swDualDimensionsOn" + name.title()] == value, "dual position enum mapping differs")
    return found


def geometry(document, samples):
    result = measure_part_windows(document=document)
    checked(result["ok"], "part measurement failed")
    sample = dict(native_metrics=result["metrics"], boundary_observation={})
    samples.append(sample)
    if len(samples) > 1:
        box.verify_native_pair(samples[0]["native_metrics"], result["metrics"])
    harness.verify_geometry(result["metrics"], 10, cut=False)
    return observe_native(document, result["metrics"], sample["boundary_observation"])


def calibrate(app, output, const, plane, reverse, call, case, report, live, *, profile_kind, template):
    kind, suffix = KINDS[profile_kind]
    case.update(kind=profile_kind, success=False, internal_calibration_only=True, writes=[])
    creator = create_part_windows_with_handle if kind == 1 else create_assembly_windows_with_handle
    created, doc = call("create-" + profile_kind, lambda: create_drawing_windows_with_handle(
        app=app, template=str(template), projection="first-angle") if kind == 3 else creator(app=app))
    live["document"] = doc
    case["creation"] = created
    checked(created["ok"] and doc is not None, "fixture creation failed")
    if kind == 1:
        sketch_result, sketch = call("rectangle", lambda: create_rectangle_sketch_windows_with_handle(
            app=app, document=doc, plane="front", width_mm=40, height_mm=30))
        case["profile"] = sketch_result
        checked(sketch_result["ok"] and not sketch_result.get("warnings"), "profile creation failed")
        boss, feature = call("extrude", lambda: extrude_sketch_windows_with_handle(
            app=app, document=doc, sketch_feature=sketch, depth_mm=10))
        case["boss"] = boss
        checked(boss["ok"] and not boss.get("warnings"), "fixture extrusion failed")
        case["geometry_before_save"] = call("geometry-before-save", lambda: geometry(doc, case.setdefault("geometry_native_samples", [])))
        sketch = feature = None
    source = output / ("source." + suffix)
    case["save_source"] = call("save-source", lambda: save_as_native_windows(str(source), document=doc))
    checked(case["save_source"]["ok"] and not _com_value(doc, "GetSaveFlag"), "source save failed")
    source_hash = case["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    foreground = None
    try:
        made, foreground = call("create-foreground", lambda: create_part_windows_with_handle(app=app))
        checked(made["ok"] and foreground is not None, "foreground fixture failed")
        registry = DocumentRegistry(app)
        entry = registry.register(doc)
        front = registry.register(foreground)
        registry.set_current(front, session_id="display-reader")
        lease = registry.acquire_lease(entry, session_id="display-writer", ttl_seconds=1800)
        def read():
            result = execute_operation(app, "document.dimension-format", {}, documents=registry,
                document_id=entry.document_id, session_id="display-reader", expected_update_stamp=_com_value(doc, "GetUpdateStamp"))
            validate_operation_result("document.dimension-format", result)
            checked(result["ok"], "display read failed: " + str(result))
            if foreground is not None:
                checked(not result["document"]["active"] and not result["document"]["current"], "background read changed selection")
            return result
        initial = case["initial"] = call("initial-read", read)
        guards = dict(document_id=entry.document_id, expected_update_stamp=initial["document"]["update_stamp"],
                      lease_id=lease["lease_id"], session_id="display-writer", documents=registry)
        target = dict(field="dual_display", value=not initial["format"]["dual_display"], expected_format=initial["format"])
        for label, changes, error_type in (("wrong-lease", {"lease_id": "l-deadbeef"}, DocumentLeaseConflict),
                ("stale-stamp", {"expected_update_stamp": guards["expected_update_stamp"] + 1}, DocumentUpdateConflict)):
            try:
                call(label, lambda: execute_operation(app, "document.dimension-format-set", target, **{**guards, **changes}))
            except error_type:
                case[label] = error_type.__name__
            else:
                raise RuntimeError(label + " did not refuse")
        closed = case["public_write_closed"] = call("public-write-closed", lambda: execute_operation(
            app, "document.dimension-format-set", target, **guards))
        validate_operation_result("document.dimension-format-set", closed)
        checked(not closed["ok"] and closed["error"]["type"] == "DimensionFormatNotCalibrated"
                and not closed["mutation"]["attempted"], "uncalibrated public write was not closed")
        if kind == 1:
            # Both sides must observe the saved background document. The old
            # baseline preceded SaveAs and the foreground transition.
            control_state = case["geometry_control_state_before"] = _state(doc)
            case["geometry_before"] = call("geometry-saved-background-before", lambda: geometry(doc, case.setdefault("geometry_native_samples", [])))
            case["geometry_control"] = call("geometry-no-write-control", lambda: geometry(doc, case.setdefault("geometry_native_samples", [])))
            checked(case["geometry_control"] == case["geometry_before"],
                    "no-write exact box boundary control changed; no display setter attempted")
            case["geometry_control_state_after"] = _state(doc)
            checked(case["geometry_control_state_after"] == control_state,
                    "no-write geometry observation changed saved background document state")
        protected = case["protected_before"] = dict(units=_read_units(doc), annotations=_read_options(doc))
        application = lambda: dict(dual_display=app.GetUserPreferenceToggle(43),
                                  parentheses=app.GetUserPreferenceToggle(48), position=app.GetUserPreferenceIntegerValue(14))
        case["application_before"] = call("application-before", application)
        current = initial
        plan = [("dual_display", True), ("dual_position", "top"), ("dual_position", "bottom"),
                ("dual_position", "left"), ("dual_position", "right"), ("parentheses", True),
                ("parentheses", False), ("dual_display", False)]
        for field, value in plan:
            registry.require_lease(entry, session_id="display-writer", lease_id=lease["lease_id"])
            checked(_com_value(doc, "GetUpdateStamp") == current["document"]["update_stamp"], "calibration update stamp changed")
            evidence = dict(field=field, value=value)
            case["writes"].append(evidence)
            raw = call("internal-set-" + field, lambda: set_dimension_format_windows(
                app=app, document=doc, field=field, value=value, expected_format=current["format"], _calibration=True))
            evidence["result"] = raw
            current = _with_document(raw, registry, entry, session_id="display-writer")
            validate_operation_result("document.dimension-format-set", current)
            checked(current["ok"], "internal display setter failed: " + str(current))
            expected = POSITIONS[value] if field == "dual_position" else value
            checked(current["format"][field] == expected and _com_value(app, "GetProcessID") == report["host"]["process_id"],
                    "native display value or owned host changed")
        stale = deepcopy(current["format"])
        stale["parentheses"] = not stale["parentheses"]
        refusal = case["complete_cas_refusal"] = call("complete-cas", lambda: set_dimension_format_windows(
            app=app, document=doc, field="dual_display", value=True, expected_format=stale, _calibration=True))
        checked(not refusal["ok"] and refusal["error"]["type"] == "DocumentDimensionFormatConflict"
                and not refusal["mutation"]["attempted"], "complete-value CAS did not refuse")
        case["protected_after"] = dict(units=_read_units(doc), annotations=_read_options(doc))
        checked(case["protected_after"] == protected and call("application-after", application) == case["application_before"],
                "display writes changed units, zero/annotation or application preferences")
        if kind == 1:
            case["geometry_after"] = call("geometry-after", lambda: geometry(doc, case.setdefault("geometry_native_samples", [])))
            checked(case["geometry_after"] == case["geometry_before"], "display writes changed geometry")
    finally:
        if foreground is not None:
            call("close-foreground", lambda: app.CloseDoc(_com_value(foreground, "GetTitle")))
            foreground = None
    saved_path = output / ("saved." + suffix)
    case["save_copy"] = call("save-copy", lambda: save_as_native_windows(str(saved_path), document=doc))
    checked(case["save_copy"]["ok"] and not _com_value(doc, "GetSaveFlag"), "display save-copy failed")
    digest = hashlib.sha256(saved_path.read_bytes()).hexdigest()
    clean = call("clean-read", read)
    case["same_value"] = call("same-value", lambda: execute_operation(app, "document.dimension-format-set",
        dict(field="dual_display", value=clean["format"]["dual_display"], expected_format=clean["format"]),
        **{**guards, "expected_update_stamp": clean["document"]["update_stamp"]}))
    checked(case["same_value"]["ok"] and not case["same_value"]["changed"] and _state(doc)[2] is False, "same-value call dirtied clean file")
    title = _com_value(doc, "GetTitle")
    live["document"] = doc = None
    call("close-saved", lambda: app.CloseDoc(title))
    opened, doc = call("reopen-readonly", lambda: open_windows_document_with_handle(str(saved_path), app=app, read_only=True))
    live["document"] = doc
    case["reopen"] = opened
    checked(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0, "saved display file reopen failed")
    registry = DocumentRegistry(app)
    entry = registry.register(doc)
    observed = case["reopened_format"] = call("reopened-read", read)
    checked(observed["format"] == current["format"] and not observed["document"]["modified"], "display settings did not persist")
    refused = case["readonly_refusal"] = call("readonly-refusal", lambda: set_dimension_format_windows(
        app=app, document=doc, field="dual_display", value=True, expected_format=observed["format"], _calibration=True))
    checked(not refused["ok"] and not refused["mutation"]["attempted"] and refused["error"]["type"] == "ValueError", "readonly display write reached setter")
    if kind == 1:
        checked(call("reopened-geometry", lambda: geometry(doc, case.setdefault("geometry_native_samples", []))) == case["geometry_before"], "reopened geometry changed")
    checked(hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
            and hashlib.sha256(saved_path.read_bytes()).hexdigest() == digest and not _com_value(doc, "GetSaveFlag"),
            "display calibration changed source or readonly saved bytes/state")
    case.update(source_sha256=source_hash, saved_sha256=digest)
    title = _com_value(doc, "GetTitle")
    live["document"] = doc = None
    call("close-reopened", lambda: app.CloseDoc(title))
    checked(_com_value(app, "GetDocumentCount") == 0, "calibration left documents open")
    case["success"] = True


def deadline_reason(records, *, elapsed, now, started):
    if elapsed > 1800:
        return "group exceeded 1800 seconds"
    pending = records[-1] if records and records[-1].get("phase") == "begin" else None
    # Inactivity also covers native helpers between explicit harness boundaries.
    last_time = next((row["time"] for row in reversed(records) if "time" in row), started)
    if now - last_time > 600:
        return "native operation exceeded 600 seconds: " + (pending["call"] if pending else "untraced native helper")
    return None


def supervise(args):
    args.output_dir.mkdir()
    command = [sys.executable, "-I", str(Path(__file__).resolve()), "--worker", "--output-dir", str(args.output_dir),
               "--swconst", str(args.swconst), "--drawing-template", str(args.drawing_template)]
    started = time.monotonic()
    started_wall = time.time()
    failure = None
    with (args.output_dir / "worker.stdout.log").open("w") as out, (args.output_dir / "worker.stderr.log").open("w") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err)
        while process.poll() is None:
            records = []
            path = args.output_dir / "trace.jsonl"
            if path.is_file():
                for line in path.read_text().splitlines():
                    try: records.append(json.loads(line))
                    except ValueError: pass  # A currently written line is not a native retry.
            failure = deadline_reason(records, elapsed=time.monotonic() - started,
                                      now=time.time(), started=started_wall)
            if failure:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, capture_output=True)
                process.wait(timeout=30)
                break
            time.sleep(1)
    record = dict(success=process.returncode == 0 and failure is None, worker_exit=process.returncode,
                  failure=failure, native_timeout_seconds=600, group_timeout_seconds=1800,
                  full_acceptance_eligible=False, source_commit=__import__("os").environ.get("GITHUB_SHA"))
    (args.output_dir / "supervisor.json").write_text(json.dumps(record, indent=2) + "\n")
    return 0 if record["success"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--swconst", required=True, type=Path)
    parser.add_argument("--drawing-template", required=True, type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    checked(args.swconst.is_file() and args.drawing_template.is_file(), "explicit official constants/template required")
    if not args.worker:
        return supervise(args)
    original = harness.read_constants
    def read_constants(pythoncom, path):
        return {**original(pythoncom, path), **constants(pythoncom, path)}
    harness.read_constants = read_constants
    def case_runner(*values, **keywords):
        return calibrate(*values, **keywords, template=args.drawing_template)
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False, case_runner=case_runner,
        case_plan=[(kind, "front", False) for kind in KINDS], diagnostic_case="document-dimension-format-internal-calibration")


if __name__ == "__main__":
    raise SystemExit(main())
