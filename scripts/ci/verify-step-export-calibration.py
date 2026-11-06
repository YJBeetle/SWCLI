"""Manual internal STEP calibration, separate from public acceptance.

One owned invisible host, no CAD rollback/retry/host replacement. Each native
call has a 600-second watchdog; the complete group has an 1800-second deadline.
The normal public revision allowlist stays empty until reviewed acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_box_part_windows_with_handle, create_part_windows_with_handle
from swcli.hosts.windows_sketches import _features
from swcli.hosts.windows_step_export import read_step_constants, step_host_scope, verify_step_output
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location(
    "_step_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked


def check_box(document):
    measured = measure_part_windows(document=document)
    checked(measured["ok"], "native box geometry unavailable")
    metrics = measured["metrics"]
    checked(metrics["solid_body_count"] == 1, "box solid count differs")
    for key, expected in (("volume_mm3", 12000), ("surface_area_mm2", 3800)):
        checked(math.isclose(metrics[key], expected, rel_tol=1e-7, abs_tol=1e-5),
                "box analytic geometry mismatch: " + key)
    return measured


def read_wireframe(document):
    checked(not tuple(document.GetBodies2(0, False) or ()), "wireframe imported as a solid")
    lengths = []
    for feature in _features(document):
        if _com_value(feature, "GetTypeName2") not in ("ProfileFeature", "3DProfileFeature"):
            continue
        sketch = _com_value(feature, "GetSpecificFeature2")
        for segment in tuple(_com_value(sketch, "GetSketchSegments") or ()):
            length = float(_com_value(segment, "GetLength")) * 1000
            checked(math.isfinite(length) and length > 0, "invalid imported wireframe segment")
            lengths.append(length)
    checked(len(lengths) >= 12, "box wireframe must contain at least its twelve edges")
    # Box edge perimeter is 4*(40+30+10)=320mm. Included source rectangle adds
    # 2*(40+30)=140mm; verify exact profile below in the case runner.
    return dict(segment_count=len(lengths), lengths_mm=sorted(lengths), total_length_mm=sum(lengths))


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind):
    import pythoncom
    from win32com.client import VARIANT
    protocol, geometry = profile_kind.split(":")
    name = protocol + "-" + geometry
    source = output / (name + "-source.SLDPRT")
    made, document = call("create-" + name, lambda: create_box_part_windows_with_handle(
        str(source), app=app, width_mm=40, height_mm=30, depth_mm=10))
    live["document"] = document
    case.update(protocol=protocol, geometry=geometry, creation=made)
    checked(made["ok"] and document is not None, "box creation failed")
    case["source_geometry"] = call("measure-source", lambda: check_box(document))
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    registry = DocumentRegistry(app)
    entry = registry.register(document)
    lease = registry.acquire_lease(entry, session_id="step-calibration", ttl_seconds=1800)
    front_result, foreground = call("create-foreground", lambda: create_part_windows_with_handle(app=app))
    checked(front_result["ok"] and foreground is not None, "foreground fixture creation failed")
    front_entry = registry.register(foreground)
    registry.set_current(front_entry, session_id="step-calibration")
    target = output / (name + ".step")
    parameters = dict(output=str(target), step_protocol=protocol, step_geometry=geometry, strict=True)
    context = dict(documents=registry, session_id="step-calibration", document_id=entry.document_id,
                   expected_update_stamp=_com_value(document, "GetUpdateStamp"), lease_id=lease["lease_id"])
    # Verify the public/default path cannot use this internal calibration scope.
    with step_host_scope(app, isolated=True):
        denied = call("public-fail-closed", lambda: execute_operation(app, "document.export", parameters, **context))
    case["public_gate"] = denied
    validate_operation_result("document.export", denied)
    checked(not denied["ok"] and denied["error"]["type"] == "StepCalibrationRequired" and not target.exists(),
            "uncalibrated public write was not blocked")
    with step_host_scope(app, isolated=True, calibration=True):
        exported = call("internal-export-" + name, lambda: execute_operation(app, "document.export", parameters, **context))
    case["internal_export"] = exported
    validate_operation_result("document.export", exported)
    checked(exported["ok"], "STEP export failed: " + str(exported))
    checked(not exported["document"]["active"] and not exported["document"]["current"],
            "background export changed source identity/current/foreground")
    checked(_com_value(app, "GetProcessID") == report["host"]["process_id"], "owned host changed")
    call("close-foreground", lambda: app.CloseDoc(_com_value(foreground, "GetTitle")))
    checked(exported["step_preferences"]["before"] == exported["step_preferences"]["after"]
            and exported["step_preferences"]["restored"], "STEP preferences leaked")
    case["actual_step"] = verify_step_output(target, protocol, geometry)
    case["step_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    checked(hashlib.sha256(source.read_bytes()).hexdigest() == source_digest,
            "STEP export changed native source bytes")
    call("close-source", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = document = None
    reopened, document = call("reopen-source-readonly", lambda: open_windows_document_with_handle(
        str(source), read_only=True, app=app))
    live["document"] = document
    case["source_reopen"] = reopened
    checked(reopened["ok"] and reopened["api_errors"] == reopened["api_warnings"] == 0,
            "saved source reopen failed")
    case["reopened_source_geometry"] = call("measure-reopened-source", lambda: check_box(document))
    checked(not _com_value(document, "GetSaveFlag"), "reopened source observation mutated source")
    call("close-reopened-source", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = document = None
    verify_imported_geometry(app, target, output, name, geometry, call, case, live)


def verify_reopened_geometry(before, after, geometry):
    """Compare physical geometry, keeping analytic bounds and exact topology."""
    if geometry == "solid-surface":
        checked(before.keys() == after.keys(), "geometry observation schema changed")
        checked({k:v for k,v in before.items() if k not in ("metrics", "bodies")} ==
                {k:v for k,v in after.items() if k not in ("metrics", "bodies")},
                "geometry observation method/context changed")
        checked(before["metrics"]["solid_body_count"] == after["metrics"]["solid_body_count"] == 1,
                "solid topology changed after native save/reopen")
        checked(len(before["bodies"]) == len(after["bodies"]) == 1,
                "solid body observation count changed")
        pairs = [(before["metrics"], after["metrics"]), (before["bodies"][0], after["bodies"][0])]
        checked(before["bodies"][0]["index"] == after["bodies"][0]["index"] == 0,
                "solid body identity changed")
        for first, second in pairs:
            for key, expected in (("volume_mm3", 12000), ("surface_area_mm2", 3800)):
                for value in (first[key], second[key]):
                    checked(math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-7, abs_tol=1e-5),
                            "analytic box geometry differs: " + key)
                checked(math.isclose(first[key], second[key], rel_tol=1e-7, abs_tol=1e-5),
                        "box geometry differs after native save/reopen: " + key)
            for axis, expected in (("x", 0), ("y", 0), ("z", 5)):
                for value in (first["centroid_mm"][axis], second["centroid_mm"][axis]):
                    checked(math.isfinite(value) and math.isclose(value, expected, rel_tol=0, abs_tol=1e-9),
                            "analytic box centroid differs: " + axis)
                checked(math.isclose(first["centroid_mm"][axis], second["centroid_mm"][axis], rel_tol=0, abs_tol=1e-9),
                        "box centroid differs after native save/reopen: " + axis)
    else:
        checked(before["segment_count"] == after["segment_count"] >= 12,
                "wireframe topology changed after native save/reopen")
        checked(len(before["lengths_mm"]) == len(after["lengths_mm"]) == before["segment_count"],
                "wireframe segment observation count changed")
        for first, second in zip(before["lengths_mm"], after["lengths_mm"]):
            checked(math.isfinite(first) and math.isfinite(second) and first > 0 and second > 0
                    and math.isclose(first, second, rel_tol=0, abs_tol=1e-9),
                    "wireframe segment differs after native save/reopen")
        expected = 320 if geometry == "wireframe" else 460
        for value in (before["total_length_mm"], after["total_length_mm"]):
            checked(math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-7, abs_tol=1e-5),
                    "analytic wireframe length differs after native save/reopen")


def verify_imported_geometry(app, target, output, name, geometry, call, case, live):
    import pythoncom
    from win32com.client import VARIANT
    original_step_digest = hashlib.sha256(target.read_bytes()).hexdigest()
    imported_data = call("GetImportFileData", lambda: app.GetImportFileData(str(target)))
    checked(imported_data is not None, "STEP import data interface is unavailable")
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    document = call("LoadFile4", lambda: app.LoadFile4(str(target), "r", imported_data, errors))
    live["document"] = document
    case["step_import_errors"] = errors.value
    checked(document is not None and errors.value == 0, "STEP geometry readback failed")
    if geometry == "solid-surface":
        case["imported_geometry"] = call("measure-imported-step", lambda: check_box(document))
    else:
        case["imported_geometry"] = call("read-imported-wireframe", lambda: read_wireframe(document))
        expected = 320 if geometry == "wireframe" else 460
        checked(math.isclose(case["imported_geometry"]["total_length_mm"], expected, rel_tol=1e-7, abs_tol=1e-5),
                "wireframe/sketch analytic length differs")
    imported_native = output / (name + "-imported.SLDPRT")
    case["imported_save"] = call("save-imported-native", lambda: save_as_native_windows(str(imported_native), document=document))
    checked(case["imported_save"]["ok"], "imported geometry save failed")
    native_digest = hashlib.sha256(imported_native.read_bytes()).hexdigest()
    call("close-import", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = document = None
    opened, document = call("reopen-imported-native", lambda: open_windows_document_with_handle(
        str(imported_native), read_only=True, app=app))
    live["document"] = document
    case["imported_reopen"] = opened
    checked(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0, "imported native reopen failed")
    case["reopened_imported_geometry"] = call("verify-reopened-import", lambda:
        check_box(document) if geometry == "solid-surface" else read_wireframe(document))
    verify_reopened_geometry(case["imported_geometry"], case["reopened_imported_geometry"], geometry)
    checked(not _com_value(document, "GetSaveFlag"), "read-only imported observation changed save state")
    checked(hashlib.sha256(imported_native.read_bytes()).hexdigest() == native_digest, "read-only reopen changed native bytes")
    checked(hashlib.sha256(target.read_bytes()).hexdigest() == original_step_digest, "readback changed STEP bytes")
    case["imported_native_sha256"] = native_digest
    call("close-reopened-import", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = None
    checked(_com_value(app, "GetDocumentCount") == 0, "documents leaked between STEP cases")
    case["success"] = True


def readback_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind):
    source_report = json.loads((output / "source-public-report.json").read_text(encoding="utf-8"))
    row = source_report["outputs"][int(profile_kind)]
    target = Path(row["path"])
    checked(hashlib.sha256(target.read_bytes()).hexdigest() == row["sha256"], "public STEP digest mismatch")
    case.update(public_output=row, actual_step=verify_step_output(target, row["protocol"], row["geometry"]))
    verify_imported_geometry(app, target, output, target.stem, row["geometry"], call, case, live)


def worker(args):
    # The existing harness covers major calls in trace.jsonl. Add a separate
    # flushed watchdog boundary around every _com_value observation as well,
    # including calls made outside a native_call wrapper.
    import swcli.hosts.windows as windows
    original_com_value = windows._com_value
    def bounded_com_value(obj, name):
        with (args.output_dir / "observation-trace.jsonl").open("a", encoding="utf-8", buffering=1) as stream:
            stream.write(json.dumps(dict(call=name, phase="begin", time=time.time())) + "\n")
            try:
                value = original_com_value(obj, name)
            except BaseException:
                stream.write(json.dumps(dict(call=name, phase="error", time=time.time())) + "\n")
                raise
            stream.write(json.dumps(dict(call=name, phase="end", time=time.time())) + "\n")
            return value
    # Imported functions retain the same windows module global; aliases used
    # here and in the harness are assigned explicitly. No CAD retry is added.
    windows._com_value = bounded_com_value
    globals()["_com_value"] = bounded_com_value
    harness._com_value = bounded_com_value
    harness.read_constants = lambda pythoncom, path: read_step_constants(path)
    if args.export_report is not None:
        public = json.loads(args.export_report.read_text(encoding="utf-8"))
        checked(public["success"] and len(public["outputs"]) == 8, "public export group is incomplete")
        (args.output_dir / "source-public-report.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
        return harness.run(args.output_dir, args.swconst, False, case_runner=readback_case,
            case_plan=[(str(index), "front", False) for index in range(len(public["outputs"]))],
            diagnostic_case="step-public-output-readback")
    return harness.run(args.output_dir, args.swconst, False, case_runner=calibrate_case,
        case_plan=[(protocol + ":" + geometry, "front", False)
                   for protocol in ("ap203", "ap214")
                   for geometry in ("solid-surface", "wireframe", "wireframe-sketches")],
        diagnostic_case="step-export-internal-calibration")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--export-report", type=Path, help="validate actual files from a completed public group, without exporting")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    if args.worker:
        return worker(args)
    checked(args.swconst.is_file(), "installed official type library is required")
    args.output_dir.mkdir()
    (args.output_dir / "input-identity.json").write_text(json.dumps(dict(
        source_commit=os.environ.get("GITHUB_SHA"),
        swconst_path=str(args.swconst.resolve()),
        swconst_sha256=hashlib.sha256(args.swconst.read_bytes()).hexdigest())) + "\n", encoding="utf-8")
    started = time.monotonic()
    with (args.output_dir / "worker.stdout.log").open("wb") as stdout, (args.output_dir / "worker.stderr.log").open("wb") as stderr:
        extra = ["--export-report", str(args.export_report.resolve())] if args.export_report is not None else []
        process = subprocess.Popen([sys.executable, "-I", __file__, "--worker", "--output-dir", str(args.output_dir),
                                    "--swconst", str(args.swconst.resolve()), *extra], stdout=stdout, stderr=stderr)
        while process.poll() is None:
            time.sleep(0.25)
            active = None
            for filename in ("trace.jsonl", "observation-trace.jsonl"):
                trace = args.output_dir / filename
                rows = []
                if trace.exists():
                    for line in trace.read_text(encoding="utf-8").splitlines():
                        try:
                            rows.append(json.loads(line))
                        except ValueError:
                            pass  # A trace can be read between partial writes.
                latest = rows[-1] if rows else None
                if latest and latest.get("phase") == "begin" and (active is None or latest["time"] < active["time"]):
                    active = latest
            timed_out = (time.monotonic() - started >= 1800 or
                         active and time.time() - active["time"] >= 600)
            if timed_out:
                (args.output_dir / "timeout.json").write_text(json.dumps(dict(
                    success=False, reason="native-600s-or-group-1800s", active=active)) + "\n")
                process.kill()
                process.wait()
                return 124
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
