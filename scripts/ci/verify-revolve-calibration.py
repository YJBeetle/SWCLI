"""Manual internal candidate calibration; never public acceptance or a release gate.

One owned host, no CAD retries or host replacement. Each native/case boundary
has 600s, and the process group has 1800s. Failures retain the first report.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from itertools import count
import time
import traceback

from swcli.daemon.server import acquire_resident_app
from swcli.hosts.native_trace import trace_native_request
from swcli.hosts.windows import _com_value, wait_windows_host_ready
from swcli.hosts.windows_documents import open_windows_document_with_handle, _diagnose_features
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_revolves import _calibrate_revolve_windows_with_handle, observe_revolve_definition
from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle, create_circle_sketch_windows_with_handle, _features
from swcli.hosts.windows_rectangle_profiles import observe_rectangle_profile
from swcli.revolve_geometry import verify_cylinder_metrics


def checked(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_type_libraries(pythoncom, swconst, sldworks):
    wanted = {"swEndCondBlind", "swThinWallOneDirection", "swRevolveTypeOneDirection", "swSelSKETCHSEGS"}
    enums = {}
    library = pythoncom.LoadTypeLib(str(swconst))
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attr = info.GetTypeAttr()
        if attr.typekind == pythoncom.TKIND_ENUM:
            for offset in range(attr.cVars):
                desc = info.GetVarDesc(offset)
                name = info.GetDocumentation(desc[0])[0]
                if name in wanted:
                    checked(name not in enums, "duplicate enum: " + name)
                    enums[name] = desc.value
    checked(set(enums) == wanted, "official swconst lacks required enums")
    members = {}
    library = pythoncom.LoadTypeLib(str(sldworks))
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        name = info.GetDocumentation(-1)[0]
        if name not in ("IFeatureManager", "IRevolveFeatureData2"):
            continue
        methods = {}
        for offset in range(info.GetTypeAttr().cFuncs):
            names = list(info.GetNames(info.GetFuncDesc(offset)[0]))
            if names:
                methods[names[0]] = names[1:]
        members[name] = methods
    checked(len(members.get("IFeatureManager", {}).get("FeatureRevolve2", [])) == 20,
            "official FeatureRevolve2 signature must expose exactly 20 parameters")
    required = {"AccessSelections", "ReleaseSelectionAccess", "GetAxisType", "Axis", "Type",
                "GetRevolutionAngle", "ReverseDirection", "IsBossFeature", "IsThinFeature", "Merge", "GetContoursCount"}
    checked(required <= set(members.get("IRevolveFeatureData2", {})), "official revolve definition members are missing")
    return dict(constants=enums, interfaces=members,
                libraries={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (swconst, sldworks)})


def run(output, swconst, sldworks):
    report = dict(success=False, kind="internal-native-calibration", public_acceptance=False,
                  public_write_gate="closed", cases=[], cleanup_errors=[], native_timeout_seconds=600,
                  group_timeout_seconds=1800, source_commit=os.environ.get("GITHUB_SHA"))
    app = document = pythoncom = process = None
    initialized = owned = False
    request_sequence = count(1)
    os.environ["SWCLI_TRACE_NATIVE_CALLS"] = "1"
    with (output / "trace.jsonl").open("w", encoding="utf-8", buffering=1) as trace:
        def call(name, function):
            trace.write(json.dumps(dict(call=name, phase="begin", time=time.time())) + "\n")
            def timeout():
                (output / "native-timeout.json").write_text(json.dumps(dict(call=name, seconds=600)), encoding="utf-8")
                os._exit(124)
            timer = threading.Timer(600, timeout)
            timer.daemon = True
            timer.start()
            try:
                value = function()
            except BaseException as exc:
                trace.write(json.dumps(dict(call=name, phase="error", error=str(exc), time=time.time())) + "\n")
                raise
            finally:
                timer.cancel()
            trace.write(json.dumps(dict(call=name, phase="end", time=time.time())) + "\n")
            return value

        def persist():
            (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")

        def new_rectangle(plane, bounds):
            nonlocal document
            made, document = call("create-part", lambda: create_part_windows_with_handle(app=app))
            checked(made["ok"] and document is not None, "new independent part failed: " + str(made))
            x0, y0, x1, y1 = bounds
            made, sketch = call("create-rectangle", lambda: create_rectangle_sketch_windows_with_handle(
                app=app, document=document, plane=plane, width_mm=x1-x0, height_mm=y1-y0,
                center_x_mm=(x0+x1)/2, center_y_mm=(y0+y1)/2))
            checked(made["ok"] and sketch is not None, "rectangle fixture failed: " + str(made))
            return sketch

        def candidate(sketch, bounds, axis=None):
            def invoke():
                with trace_native_request("revolve-" + str(next(request_sequence)), "feature.revolve.internal"):
                    return _calibrate_revolve_windows_with_handle(
                        app=app, document=document, sketch_feature=sketch, expected_profile_mm=bounds,
                        axis_mm=axis or [0,bounds[1],0,bounds[3]], angle_deg=360, constants=report["typelib"]["constants"])
            return call("candidate-revolve", invoke)

        def close():
            nonlocal document
            call("close-owned-document", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
            checked(not tuple(_com_value(app, "GetDocuments") or ()), "owned document did not close; stop before next case")
            document = None

        try:
            import pythoncom
            import win32com.client as client
            import win32api
            import win32con
            import win32event
            pythoncom.CoInitialize()
            initialized = True
            report["typelib"] = call("official-type-libraries", lambda: read_type_libraries(pythoncom, swconst, sldworks))
            app, owned = call("acquire-owned-host", lambda: acquire_resident_app(client, visible=False))
            checked(owned, "must never attach to another host")
            call("wait-ready", lambda: wait_windows_host_ready(app, timeout_seconds=120))
            report["host"] = dict(revision=_com_value(app, "RevisionNumber"), process_id=_com_value(app, "GetProcessID"))
            process = win32api.OpenProcess(win32con.SYNCHRONIZE, False, report["host"]["process_id"])
            for plane, bounds in (("front", [0,-5,10,15]), ("top", [0,3,7,21]), ("right", [0,-14,4,10])):
                case = dict(name=plane+"-cylinder", success=False)
                report["cases"].append(case)
                persist()
                sketch = new_rectangle(plane, bounds)
                case["creation"], feature = candidate(sketch, bounds)
                persist()
                checked(case["creation"]["ok"] and feature is not None, "candidate creation failed: " + str(case["creation"]))
                path = output / (plane + ".SLDPRT")
                case["save"] = call("save-native", lambda: save_as_native_windows(str(path), document=document))
                checked(case["save"]["ok"], "save native failed")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                case.update(file_sha256=digest, file_size_bytes=path.stat().st_size)
                close()
                opened, document = call("reopen-native", lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
                case["reopen"] = opened
                checked(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0 and document is not None,
                        "saved native reopen failed")
                features = [f for f in _features(document) if _com_value(f, "GetTypeName2") == "Revolution"]
                checked(len(features) == 1, "reopened file lacks exactly one native editable revolution")
                # Find the absorbed sketch through the feature's subfeature tree,
                # and prove profile geometry before reading back the exact axis.
                sub = _com_value(features[0], "GetFirstSubFeature")
                sketches = []
                for _ in range(100):
                    if sub is None:
                        break
                    if _com_value(sub, "GetTypeName2") == "ProfileFeature":
                        sketches.append(sub)
                    sub = _com_value(sub, "GetNextSubFeature")
                else:
                    raise RuntimeError("reopened feature traversal exceeded limit")
                checked(len(sketches) == 1, "reopened revolve must own exactly one profile")
                profile = observe_rectangle_profile(_com_value(sketches[0], "GetSpecificFeature2"))
                checked(all(abs(a-b) <= 1e-6 for a,b in zip(profile.bounds_mm,bounds)), "saved profile differs")
                case["reopened_definition"] = {}
                call("reopened-definition", lambda: observe_revolve_definition(app, document, features[0], profile.left_edge,
                     report["typelib"]["constants"], case["reopened_definition"]))
                measured = call("reopened-measure", lambda: measure_part_windows(document=document))
                checked(measured["ok"], "reopened geometry unavailable")
                case["reopened_metrics"] = measured["metrics"]
                verify_cylinder_metrics(measured["metrics"], case["creation"]["expected_metrics"])
                case["reopened_diagnostics"] = _diagnose_features(document, 500)
                checked(case["reopened_diagnostics"]["healthy"] and not case["reopened_diagnostics"]["truncated"],
                        "saved reopen diagnostics unhealthy")
                case["reopened_state"] = dict(read_only=_com_value(document,"IsOpenedReadOnly"),
                    modified=_com_value(document,"GetSaveFlag"),
                    editing=_com_value(_com_value(document,"SketchManager"),"ActiveSketch") is not None,
                    selected=_com_value(document,"SelectionManager").GetSelectedObjectCount2(-1),
                    foreground_same=app.IsSame(_com_value(app,"ActiveDoc"),document))
                checked(case["reopened_state"] == dict(read_only=True, modified=False, editing=False, selected=0, foreground_same=1),
                        "read-only reopened state was not preserved")
                checked(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "read-only reopen altered saved bytes")
                case["success"] = True
                persist()
                close()
            # Live illegal profile crosses the requested axis: CAS must fail
            # before selection or native creation, without inventing rollback.
            sketch = new_rectangle("front", [-5,-5,5,15])
            before = (_com_value(document,"GetUpdateStamp"), _com_value(document,"GetSaveFlag"))
            rejected, feature = candidate(sketch, [0,-5,10,15])
            report["axis_crossing_rejection"] = rejected
            checked(not rejected["ok"] and rejected["error"]["type"] == "RevolveProfileConflict" and feature is None
                    and rejected["mutation"] == dict(attempted=False, creation_returned=False, may_have_changed=False)
                    and before == (_com_value(document,"GetUpdateStamp"), _com_value(document,"GetSaveFlag")),
                    "axis-crossing profile was not rejected unchanged")
            close()
            made, document = call("create-invalid-profile-part", lambda: create_part_windows_with_handle(app=app))
            checked(made["ok"] and document is not None, "invalid-profile fixture part failed")
            made, sketch = call("create-invalid-circle-profile", lambda: create_circle_sketch_windows_with_handle(
                app=app, document=document, plane="front", radius_mm=5, center_x_mm=5, center_y_mm=5))
            checked(made["ok"], "invalid-profile fixture circle failed")
            before = (_com_value(document,"GetUpdateStamp"), _com_value(document,"GetSaveFlag"))
            rejected, feature = candidate(sketch, [0,-5,10,15])
            report["nonrectangle_rejection"] = rejected
            checked(not rejected["ok"] and rejected["error"]["type"] == "UnsupportedDimensionProfile" and feature is None
                    and not any(rejected["mutation"].values())
                    and before == (_com_value(document,"GetUpdateStamp"), _com_value(document,"GetSaveFlag")),
                    "nonrectangle rejection changed native state")
            close()
            # Generate two separated native solids using already-supported
            # rectangle extrusion, then reject before any revolve mutation.
            sketch = new_rectangle("front", [0,-5,10,15])
            for index, center in enumerate((5,35)):
                if index:
                    made, sketch = call("second-profile", lambda: create_rectangle_sketch_windows_with_handle(
                        app=app, document=document, plane="front", width_mm=10, height_mm=20, center_x_mm=center, center_y_mm=5))
                    checked(made["ok"], "second body profile failed")
                made, _ = call("fixture-extrude", lambda: extrude_sketch_windows_with_handle(
                    app=app, document=document, sketch_feature=sketch, depth_mm=10, merge=False))
                checked(made["ok"], "multibody fixture extrusion failed")
            checked(len(document.GetBodies2(0,False)) == 2, "negative fixture is not multibody")
            made, sketch = call("unabsorbed-profile", lambda: create_rectangle_sketch_windows_with_handle(
                app=app, document=document, plane="front", width_mm=10, height_mm=20, center_x_mm=5, center_y_mm=5))
            checked(made["ok"], "multibody rejection profile failed")
            before = (_com_value(document,"GetUpdateStamp"), _com_value(document,"GetSaveFlag"))
            rejected, feature = candidate(sketch, [0,-5,10,15])
            report["multibody_rejection"] = rejected
            checked(not rejected["ok"] and rejected["error"]["type"] == "UnsupportedRevolveBodyScope" and feature is None
                    and not any(rejected["mutation"].values())
                    and before == (_com_value(document,"GetUpdateStamp"), _com_value(document,"GetSaveFlag")),
                    "multibody rejection changed native state")
            close()
            report["success"] = True
        except BaseException as exc:
            report["failure"] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        finally:
            for name, function, enabled in (
                ("CloseDoc", lambda: app.CloseDoc(_com_value(document, "GetTitle")), document is not None),
                ("ExitApp", lambda: _com_value(app,"ExitApp"), owned),
                ("WaitOwnedProcess", lambda: checked(win32event.WaitForSingleObject(process,10000)==win32event.WAIT_OBJECT_0,
                                                     "owned host did not exit"), process is not None),
                ("CloseHandle", lambda: process.Close(), process is not None),
                ("CoUninitialize", lambda: pythoncom.CoUninitialize(), initialized)):
                if enabled:
                    try:
                        call(name, function)
                    except Exception as exc:
                        report["cleanup_errors"].append(dict(stage=name,error=str(exc)))
    report["success"] = report["success"] and not report["cleanup_errors"]
    persist()
    return 0 if report["success"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--sldworks", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.swconst.is_file() or not args.sldworks.is_file():
        parser.error("both official installed type libraries are required")
    if args.worker:
        return run(args.output_dir, args.swconst, args.sldworks)
    args.output_dir.mkdir()  # New persistent evidence; never overwrite a run.
    command = [sys.executable, "-I", str(Path(__file__).resolve()), "--worker", "--output-dir", str(args.output_dir.resolve()),
               "--swconst", str(args.swconst.resolve()), "--sldworks", str(args.sldworks.resolve())]
    with (args.output_dir/"stdout.log").open("w") as stdout, (args.output_dir/"stderr.log").open("w") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        try:
            return child.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            (args.output_dir/"group-timeout.json").write_text(json.dumps(dict(seconds=1800)), encoding="utf-8")
            return 124


if __name__ == "__main__":
    raise SystemExit(main())
