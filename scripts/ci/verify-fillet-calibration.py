"""Opt-in internal native calibration, not a public SWCLI modeling operation.

Run with the installed Windows Python (also under Wine). Own one new host and
fixture; never attach, retry a CAD operation, or change a host preference.
"""

import argparse
import json
import math
from pathlib import Path
import sys
import time
import traceback

from swcli.daemon.server import acquire_resident_app
from swcli.hosts.windows import _com_value, wait_windows_host_ready
from swcli.hosts.windows_documents import _diagnose_features
from swcli.hosts.windows_parts import create_box_part_windows_with_handle
from swcli.hosts.windows_entity_references import capture_verified_reference


def checked(condition, message):
    if not condition:
        raise RuntimeError(message)


def capture_process(pid):
    import win32api
    import win32con
    checked(type(pid) is int and pid > 0, "owned host process ID is invalid")
    return win32api.OpenProcess(win32con.SYNCHRONIZE, False, pid)


def wait_process(handle):
    import win32event
    status = win32event.WaitForSingleObject(handle, 10000)
    checked(status == win32event.WAIT_OBJECT_0, "owned host exit was not confirmed within 10 seconds")


def radius_matches(value):
    return math.isclose(value, 0.002, rel_tol=0, abs_tol=1e-12)


def verify_geometry(before, after, body_count, length_mm):
    checked(math.isfinite(length_mm) and length_mm > 0, "fixture edge length must be positive and finite")
    expected = (1 - math.pi / 4) * 2**2 * length_mm
    checked(body_count == 1 and all(math.isfinite(x) for x in (before, after)),
            "fillet must leave one solid with finite volume")
    checked(math.isclose(before, 12000, rel_tol=1e-8), "fixture volume is not 12000 mm3")
    checked(math.isclose(before - after, expected, rel_tol=1e-7, abs_tol=1e-5),
            "removed volume differs from the convex straight-edge fixture")
    return dict(before_mm3=before, after_mm3=after, removed_mm3=before-after,
                expected_removed_mm3=expected, body_count=body_count)


def read_constants(pythoncom, path):
    library = pythoncom.LoadTypeLib(str(path))
    wanted = {"swFmFillet", "swConstRadiusFillet", "swFeatureFilletCircular"}
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attributes.cVars):
            descriptor = info.GetVarDesc(offset)
            name = info.GetDocumentation(descriptor[0])[0]
            if name in wanted:
                found[name] = descriptor.value
    checked(set(found) == wanted, "official swconst type library lacks required enums")
    return found


def calibrate(app, document, constants, client, pythoncom, call, report):
    selection = _com_value(document, "SelectionManager")
    checked(selection.GetSelectedObjectCount2(-1) == 0, "existing selection is not owned")
    bodies = tuple(document.GetBodies2(0, False) or ())
    checked(len(bodies) == 1, "fixture must contain one solid")
    before = bodies[0].GetMassProperties(1.0)[3] * 1e9
    candidates = []
    for edge in _com_value(bodies[0], "GetEdges"):
        start = tuple(_com_value(_com_value(edge, "GetStartVertex"), "GetPoint"))
        end = tuple(_com_value(_com_value(edge, "GetEndVertex"), "GetPoint"))
        if math.isclose(math.dist(start, end) * 1000, 10, abs_tol=1e-6):
            candidates.append((edge, start, end))
    checked(len(candidates) == 4, "fixture does not have four known 10 mm edges")
    edge, start, end = min(candidates, key=lambda item: (item[1], item[2]))
    extension = _com_value(document, "Extension")
    reference = call("capture-target-reference", lambda: capture_verified_reference(app, extension, edge))
    checked(bool(reference), "target persistent reference is empty")
    report["target"] = dict(start_m=start, end_m=end, length_mm=10,
                            persistent_reference=reference.hex())
    select_data = _com_value(selection, "CreateSelectData")
    select_data.Mark = 1
    checked(call("Edge.Select4.mark1", lambda: edge.Select4(False, select_data)),
            "exact edge selection failed")
    checked(selection.GetSelectedObjectCount2(-1) == 1 and
            capture_verified_reference(app, extension, selection.GetSelectedObject6(1, 1)) == reference,
            "marked selection did not round-trip the exact target")
    manager = _com_value(document, "FeatureManager")
    definition = call("CreateDefinition", lambda: manager.CreateDefinition(constants["swFmFillet"]))
    checked(definition is not None, "CreateDefinition returned null")
    checked(call("Initialize", lambda: definition.Initialize(constants["swConstRadiusFillet"])),
            "constant-radius initialization failed")
    for name, value in (("ConicTypeForCrossSectionProfile", constants["swFeatureFilletCircular"]),
                        ("DefaultRadius", 0.002), ("PropagateToTangentFaces", False)):
        call("set." + name, lambda n=name, v=value: setattr(definition, n, v))
        actual = _com_value(definition, name)
        checked(radius_matches(actual) if name == "DefaultRadius" else actual == value,
                "creation setting did not round-trip: " + name)
    feature = call("CreateFeature", lambda: manager.CreateFeature(definition))
    checked(feature is not None, "CreateFeature returned null; do not retry")
    report["feature"] = dict(name=_com_value(feature, "Name"), kind=_com_value(feature, "GetTypeName2"))
    checked(report["feature"]["kind"] == "Fillet", "created feature is not a fillet")
    document.ClearSelection2(True)
    data = call("GetDefinition", lambda: _com_value(feature, "GetDefinition"))
    # Access can throw after partial acquisition: always attempt its release.
    try:
        null = client.VARIANT(pythoncom.VT_DISPATCH, None)
        checked(call("AccessSelections", lambda: data.AccessSelections(document, null)),
                "selection access was refused")
        targets = tuple(_com_value(data, "Edges") or ())
        report["readback"] = dict(edge_count=len(targets), radius_m=_com_value(data, "DefaultRadius"),
            profile=_com_value(data, "ConicTypeForCrossSectionProfile"),
            tangent_propagation=_com_value(data, "PropagateToTangentFaces"))
        checked(len(targets) == 1 and capture_verified_reference(app, extension, targets[0]) == reference,
                "created fillet target differs from the exact original edge")
        checked(radius_matches(report["readback"]["radius_m"]) and
            report["readback"]["profile"] == constants["swFeatureFilletCircular"] and
            report["readback"]["tangent_propagation"] is False,
            "created fillet settings differ from requested settings")
    finally:
        try:
            call("ReleaseSelectionAccess", lambda: _com_value(data, "ReleaseSelectionAccess"))
        except Exception as error:
            report["cleanup_errors"].append(dict(stage="ReleaseSelectionAccess", error=str(error)))
    checked(not report["cleanup_errors"], "selection access restoration failed")
    document.ClearSelection2(True)
    checked(call("EditRebuild3", lambda: _com_value(document, "EditRebuild3")), "rebuild failed")
    diagnostics = call("diagnose", lambda: _diagnose_features(document, 200))
    report["diagnostics"] = diagnostics
    checked(diagnostics["healthy"] and not diagnostics["truncated"], "incomplete or unhealthy diagnostics")
    bodies = tuple(document.GetBodies2(0, False) or ())
    after = bodies[0].GetMassProperties(1.0)[3] * 1e9 if bodies else float("nan")
    report["geometry"] = verify_geometry(before, after, len(bodies), 10)
    checked(selection.GetSelectedObjectCount2(-1) == 0, "owned selection was not cleared")


def run(output, swconst, visible):
    report = dict(success=False, cleanup_errors=[])
    app = document = pythoncom = process_handle = None
    initialized = owned = False
    with (output / "trace.jsonl").open("w", encoding="utf-8", buffering=1) as trace:
        def call(name, function):
            trace.write(json.dumps(dict(call=name, phase="begin", time=time.time())) + "\n")
            try:
                value = function()
            except BaseException as error:
                trace.write(json.dumps(dict(call=name, phase="error", error=str(error))) + "\n")
                raise
            trace.write(json.dumps(dict(call=name, phase="end", time=time.time())) + "\n")
            return value
        try:
            import pythoncom
            import win32com.client as client
            pythoncom.CoInitialize()
            initialized = True
            report["constants"] = call("read-official-swconst", lambda: read_constants(pythoncom, swconst))
            app, owned = call("acquire-owned-host", lambda: acquire_resident_app(client, visible=visible))
            checked(owned, "calibration must never attach to an existing host")
            call("wait-ready", lambda: wait_windows_host_ready(app, timeout_seconds=120))
            report["host"] = dict(revision=_com_value(app, "RevisionNumber"),
                                  process_id=_com_value(app, "GetProcessID"), visible=visible)
            process_handle = call("capture-owned-process", lambda: capture_process(report["host"]["process_id"]))
            result, document = call("create-independent-box", lambda: create_box_part_windows_with_handle(
                str(output / "fixture.SLDPRT"), width_mm=40, height_mm=30, depth_mm=10, app=app))
            report["fixture"] = result
            checked(result["ok"] and document is not None, "independent box creation failed")
            calibrate(app, document, report["constants"], client, pythoncom, call, report)
            report["success"] = True
        except BaseException as error:
            report["failure"] = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
        finally:
            for name, function in (("CloseDoc", lambda: app.CloseDoc(_com_value(document, "GetTitle"))),
                                   ("ExitApp", lambda: _com_value(app, "ExitApp")),
                                   ("WaitForOwnedProcess", lambda: wait_process(process_handle)),
                                   ("CloseProcessHandle", lambda: process_handle.Close()),
                                   ("CoUninitialize", lambda: pythoncom.CoUninitialize())):
                if (name == "CloseDoc" and document is None or name == "ExitApp" and not owned
                        or name in ("WaitForOwnedProcess", "CloseProcessHandle") and process_handle is None
                        or name == "CoUninitialize" and not initialized):
                    continue
                try:
                    call(name, function)
                except Exception as error:
                    report["cleanup_errors"].append(dict(stage=name, error=str(error)))
    report["success"] = report["success"] and not report["cleanup_errors"]
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0 if report["success"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True, help="official installed swconst.tlb")
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args(argv)
    if not args.swconst.is_file():
        parser.error("--swconst must name an existing official type library")
    try:
        args.output_dir.mkdir()  # Never reuse or overwrite another test's evidence.
    except OSError as error:
        parser.error("--output-dir must be new, with an existing parent: " + str(error))
    return run(args.output_dir.resolve(), args.swconst.resolve(), args.visible)


if __name__ == "__main__":
    raise SystemExit(main())
