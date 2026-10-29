"""Opt-in native through-all cut calibration; not a public modeling API.

Own one new host and twelve generated fixtures. No attachment, CAD retries,
preference changes or host replacement between cases. A failure stops the plan.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import traceback

from swcli.daemon.server import acquire_resident_app
from swcli.hosts.windows import _com_value, wait_windows_host_ready
from swcli.hosts.windows_documents import _diagnose_features, open_windows_document_with_handle
from swcli.hosts.windows_feature_depth_edits import _empty_variant
from swcli.hosts.windows_feature_inspection import _same, _types
from swcli.hosts.windows_feature_selections import _null_dispatch
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_sketches import (
    _features, create_circle_sketch_windows_with_handle,
    create_rectangle_sketch_windows_with_handle,
)


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
    checked(win32event.WaitForSingleObject(handle, 10000) == win32event.WAIT_OBJECT_0,
            "owned host exit was not confirmed within 10 seconds")


def read_constants(pythoncom, path):
    library = pythoncom.LoadTypeLib(str(path))
    wanted = {"swEndCondBlind", "swEndCondThroughAll", "swThisConfiguration"}
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
                checked(name not in found, "duplicate required enum in official type library")
                found[name] = descriptor.value
    checked(set(found) == wanted, "official swconst type library lacks required enums")
    return found


def verify_geometry(metrics, thickness_mm, *, cut, profile_kind="circle"):
    """Independent analytic box/cylindrical-through-hole volume and area."""
    checked(math.isfinite(thickness_mm) and thickness_mm > 0, "invalid fixture thickness")
    checked(profile_kind in ("circle", "rectangle"), "unknown calibration profile")
    profile_area, perimeter = ((math.pi * 3**2, 2 * math.pi * 3)
                               if profile_kind == "circle" else (6 * 4, 2 * (6 + 4)))
    volume = (40 * 30 - (profile_area if cut else 0)) * thickness_mm
    area = 2 * (40 * 30 - (profile_area if cut else 0)) + 2 * (40 + 30) * thickness_mm
    if cut:
        area += perimeter * thickness_mm
    checked(metrics["solid_body_count"] == 1, "fixture must leave exactly one solid")
    for key, expected in (("volume_mm3", volume), ("surface_area_mm2", area)):
        actual = metrics[key]
        checked(math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-5),
                "analytic through-hole fixture mismatch: " + key)
    return dict(expected_volume_mm3=volume, expected_surface_area_mm2=area,
                thickness_mm=thickness_mm, metrics=metrics)


def observe(document, feature, constants, reverse, call, evidence=None):
    # Bind the report snapshot before reading/validating so failed readback is
    # inspectable too. A failure must not erase the very fields it rejected.
    result = {} if evidence is None else evidence
    checked(_types(feature)[1] == "Cut", "returned native feature is not a cut")
    data = call("Cut.GetDefinition", lambda: _com_value(feature, "GetDefinition"))
    checked(data is not None, "cut definition is unavailable")
    for name, function in (
        ("end_condition", lambda: data.GetEndCondition(True)),
        ("native_reverse_direction", lambda: _com_value(data, "ReverseDirection")),
        ("both_directions", lambda: _com_value(data, "BothDirections")),
        ("thin", lambda: _com_value(data, "IsThinFeature")),
        ("feature_scope", lambda: _com_value(data, "FeatureScope")),
        ("from_type", lambda: _com_value(data, "FromType")),
        ("forward_draft", lambda: data.GetDraftWhileExtruding(True)),
    ):
        result[name] = call("Cut.read." + name, function)
    result["expected_settings"] = dict(end_condition=constants["swEndCondThroughAll"],
        native_reverse_direction=not reverse, both_directions=False, thin=False,
        feature_scope=False, from_type=0, forward_draft=False)
    checked(type(result["end_condition"]) is int and
            result["end_condition"] == constants["swEndCondThroughAll"],
            "native cut did not retain the through-all end condition")
    checked(result["native_reverse_direction"] is (not reverse)
            and result["both_directions"] is False and result["thin"] is False
            and result["feature_scope"] is False and result["from_type"] == 0
            and result["forward_draft"] is False,
            "native cut direction/start/solid/scope settings differ from the fixture")
    checked(call("Document.GetSelectedObjectCount2",
                 lambda: _com_value(document, "SelectionManager").GetSelectedObjectCount2(-1)) == 0,
            "calibration left an owned selection")
    diagnostics = call("Document.diagnose", lambda: _diagnose_features(document, 200))
    checked(diagnostics["healthy"] and not diagnostics["truncated"],
            "unhealthy or incomplete native rebuild diagnostics")
    checked(_com_value(_com_value(document, "Extension"), "NeedsRebuild2") == 0,
            "fixture still needs rebuild")
    result["diagnostics"] = diagnostics
    return result


def create_cut(document, profile, constants, reverse, call, report):
    selection = _com_value(document, "SelectionManager")
    checked(selection.GetSelectedObjectCount2(-1) == 0, "existing selection is not owned")
    selected = attempted = False
    try:
        selected = True
        checked(call("Profile.Select2", lambda: profile.Select2(False, 0)), "exact sketch selection failed")
        attempted = True
        feature = call("FeatureManager.FeatureCut4.through-all", lambda:
            _com_value(document, "FeatureManager").FeatureCut4(
                True, False, not reverse,
                constants["swEndCondThroughAll"], constants["swEndCondBlind"],
                0.001, 0.0,  # Deliberately shorter than either fixture thickness.
                False, False, False, False, 0.0, 0.0,
                False, False, False, False, False,
                # UseFeatScope=False and UseAutoSelect=False. Native SW2025
                # can otherwise normalize automatic selection to scoped bodies.
                False, False, False, False, False, 0, 0.0, False, False))
        checked(feature is not None, "FeatureCut4 returned null; no retry")
        attempted = False
        return feature
    finally:
        if attempted:
            try:
                call("Document.SetPickMode", lambda: document.SetPickMode())
            except Exception as error:
                report["cleanup_errors"].append(dict(stage="SetPickMode", error=str(error)))
        if selected:
            try:
                call("Document.ClearSelection2", lambda: document.ClearSelection2(True))
            except Exception as error:
                report["cleanup_errors"].append(dict(stage="ClearSelection2", error=str(error)))


def require_catalog(app, expected_documents, call, label):
    """Require the exact retained catalog; never hide unrelated open documents."""
    count = call(label + ".count", lambda: _com_value(app, "GetDocumentCount"))
    checked(type(count) is int and count == len(expected_documents),
            "closing generated fixture changed the retained document count")
    actual = tuple(call(label + ".documents", lambda: _com_value(app, "GetDocuments")) or ())
    checked(len(actual) == len(expected_documents), "native document catalog is incomplete")
    checked(all(sum(_same(app, found, expected) for found in actual) == 1
                for expected in expected_documents)
            and all(sum(_same(app, found, expected) for expected in expected_documents) == 1
                    for found in actual),
            "closing generated fixture changed a retained document identity")


def grow_fixture_boss(document, boss, constants, call, evidence):
    """Test-only edit of our generated boss; cleanup is part of the proof."""
    checked(_com_value(document, "SelectionManager").GetSelectedObjectCount2(-1) == 0,
            "fixture growth must not clear an existing selection")
    data = call("Boss.GetDefinition", lambda: _com_value(boss, "GetDefinition"))
    call("Boss.SetDepth.25mm", lambda: data.SetDepth(True, 0.025))
    checked(math.isclose(data.GetDepth(True), 0.025, abs_tol=1e-12, rel_tol=0), "boss staging failed")
    checked(call("Boss.SetChangeToConfigurations", lambda:
                 data.SetChangeToConfigurations(constants["swThisConfiguration"], _empty_variant())),
            "current-configuration scope was refused")
    checked(call("Boss.ModifyDefinition", lambda: boss.ModifyDefinition(data, document, _null_dispatch())),
            "boss thickness commit failed")
    checked(call("rebuild-grown-part", lambda: _com_value(document, "EditRebuild3")), "grown part rebuild failed")
    checked(math.isclose(_com_value(boss, "GetDefinition").GetDepth(True), 0.025,
                         abs_tol=1e-12, rel_tol=0), "committed boss thickness differs")
    evidence["selection_count_before_owned_cleanup"] = call("Boss.selection-after-edit",
        lambda: _com_value(document, "SelectionManager").GetSelectedObjectCount2(-1))
    call("Boss.ClearSelection2.after-owned-edit", lambda: document.ClearSelection2(True))
    checked(_com_value(document, "SelectionManager").GetSelectedObjectCount2(-1) == 0,
            "owned fixture growth selection cleanup failed")


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live,
                   retained_documents=(), profile_kind="circle"):
    checked(profile_kind in ("circle", "rectangle"), "unknown calibration profile")
    case.update(plane=plane, reverse=reverse, success=False, ignored_depth_argument_mm=1,
                ignored_depth_is_not_a_travel_measurement=True, profile_kind=profile_kind)
    result, document = call("create-part", lambda: create_part_windows_with_handle(app=app))
    live["document"] = document
    case["creation"] = result
    checked(result["ok"] and document is not None, "part creation failed")
    rectangle, sketch = call("rectangle", lambda: create_rectangle_sketch_windows_with_handle(
        app=app, document=document, plane=plane, width_mm=40, height_mm=30))
    checked(rectangle["ok"] and sketch is not None and not rectangle.get("warnings"),
            "rectangle creation/restoration failed")
    boss_result, boss = call("boss", lambda: extrude_sketch_windows_with_handle(
        app=app, document=document, sketch_feature=sketch, depth_mm=10, reverse=reverse))
    case["boss"] = boss_result
    checked(boss_result["ok"] and boss is not None and not boss_result.get("warnings"),
            "boss creation/restoration failed")
    measure = call("measure-box", lambda: measure_part_windows(document=document))
    checked(measure["ok"], "box measurement failed")
    case["box"] = verify_geometry(measure["metrics"], 10, cut=False)
    if profile_kind == "circle":
        profile_result, profile = call("circle", lambda: create_circle_sketch_windows_with_handle(
            app=app, document=document, plane=plane, radius_mm=3))
    else:
        profile_result, profile = call("slot-rectangle", lambda: create_rectangle_sketch_windows_with_handle(
            app=app, document=document, plane=plane, width_mm=6, height_mm=4))
    checked(profile_result["ok"] and profile is not None and not profile_result.get("warnings"),
            "cut profile creation/restoration failed")
    cut = create_cut(document, profile, constants, reverse, call, report)
    case["cut_created"] = True
    case["cut_feature"] = dict(native_id=_com_value(cut, "GetID"),
                               name=str(_com_value(cut, "Name")), kind=_types(cut)[1])
    checked(not report["cleanup_errors"], "cut creation cleanup failed")
    checked(call("rebuild-cut", lambda: _com_value(document, "EditRebuild3")), "cut rebuild failed")
    observe(document, cut, constants, reverse, call, case.setdefault("initial_definition", {}))
    measured = call("measure-through-hole", lambda: measure_part_windows(document=document))
    checked(measured["ok"], "through-hole measurement failed")
    case["initial_geometry"] = verify_geometry(measured["metrics"], 10, cut=True, profile_kind=profile_kind)

    # Test-only direct definition edit on our exact generated boss; not a new
    # public depth setter or permission to edit arbitrary upstream features.
    grow_fixture_boss(document, boss, constants, call, case.setdefault("fixture_growth", {}))
    observe(document, cut, constants, reverse, call, case.setdefault("grown_definition", {}))
    measured = call("measure-grown-through-hole", lambda: measure_part_windows(document=document))
    checked(measured["ok"], "grown part measurement failed")
    case["grown_geometry"] = verify_geometry(measured["metrics"], 25, cut=True, profile_kind=profile_kind)
    path = output / (plane + ("-reverse" if reverse else "-forward")
                     + ("-rectangle" if profile_kind == "rectangle" else "") + ".SLDPRT")
    saved = call("native-save-as", lambda: save_as_native_windows(str(path), document=document))
    case["save"] = saved
    checked(saved["ok"] and not saved.get("warnings"), "native save failed")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    title = _com_value(document, "GetTitle")
    # Release fixture references before closing, then independently rediscover
    # the only cut from the freshly opened generated file, never its old name.
    cut = boss = profile = sketch = None
    document = live["document"] = None
    call("close-before-reopen", lambda: app.CloseDoc(title))
    require_catalog(app, retained_documents, call, "catalog-after-close")
    reopened, document = call("native-readonly-reopen", lambda:
        open_windows_document_with_handle(str(path), read_only=True, app=app))
    live["document"] = document
    case["reopen"] = reopened
    checked(reopened["ok"] and document is not None and reopened["api_errors"] == 0,
            "native read-only reopen failed")
    candidates = [f for f in _features(document) if _types(f)[1] == "Cut"]
    checked(len(candidates) == 1, "reopened fixture does not contain exactly one cut")
    observe(document, candidates[0], constants, reverse, call,
            case.setdefault("reopened_definition", {}))
    measured = call("measure-reopened-through-hole", lambda: measure_part_windows(document=document))
    checked(measured["ok"], "reopened part measurement failed")
    case["reopened_geometry"] = verify_geometry(measured["metrics"], 25, cut=True, profile_kind=profile_kind)
    checked(not _com_value(document, "GetSaveFlag"), "read-only observations modified reopened fixture")
    case["file_sha256"] = digest
    checked(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "read-only reopen changed fixture bytes")
    title = _com_value(document, "GetTitle")
    candidates = document = live["document"] = None
    call("close-reopened-fixture", lambda: app.CloseDoc(title))
    require_catalog(app, retained_documents, call, "catalog-after-case")
    case["success"] = True


def run(output, swconst, visible):
    report = dict(success=False, diagnostic_case="through-all-calibration",
                  full_acceptance_eligible=False, cases=[], cleanup_errors=[])
    app = process_handle = pythoncom = None
    live = {"document": None}
    initialized = owned = False
    with (output / "trace.jsonl").open("w", encoding="utf-8", buffering=1) as trace:
        def persist():
            (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        def call(name, function):
            trace.write(json.dumps(dict(call=name, phase="begin", time=time.time())) + "\n")
            persist()
            try:
                result = function()
            except BaseException as error:
                trace.write(json.dumps(dict(call=name, phase="error", error=str(error))) + "\n")
                raise
            trace.write(json.dumps(dict(call=name, phase="end", time=time.time())) + "\n")
            return result

        try:
            import pythoncom
            import win32com.client as client
            pythoncom.CoInitialize()
            initialized = True
            constants = report["constants"] = call("read-official-swconst", lambda: read_constants(pythoncom, swconst))
            app, owned = call("acquire-owned-host", lambda: acquire_resident_app(client, visible=visible))
            checked(owned, "calibration must never attach to an existing host")
            call("wait-ready", lambda: wait_windows_host_ready(app, timeout_seconds=120))
            report["host"] = dict(process_id=_com_value(app, "GetProcessID"),
                                  revision=_com_value(app, "RevisionNumber"), visible=visible)
            process_handle = call("capture-owned-process", lambda: capture_process(report["host"]["process_id"]))
            checked(_com_value(app, "GetDocumentCount") == 0, "owned calibration host is not empty")
            for profile_kind in ("circle", "rectangle"):
                for plane in ("front", "top", "right"):
                    for reverse in (False, True):
                        case = {}
                        report["cases"].append(case)
                        calibrate_case(app, output, constants, plane, reverse, call, case, report, live,
                                       profile_kind=profile_kind)
            checked(_com_value(app, "GetProcessID") == report["host"]["process_id"], "host changed during calibration")
            report["success"] = True
        except BaseException as error:
            report["failure"] = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
        finally:
            for name, function, needed in (
                ("CloseDoc", lambda: app.CloseDoc(_com_value(live["document"], "GetTitle")), owned and live["document"] is not None),
                ("ExitApp", lambda: _com_value(app, "ExitApp"), owned),
                ("WaitForOwnedProcess", lambda: wait_process(process_handle), process_handle is not None),
                ("CloseProcessHandle", lambda: process_handle.Close(), process_handle is not None),
                ("CoUninitialize", lambda: pythoncom.CoUninitialize(), initialized),
            ):
                if needed:
                    try:
                        call(name, function)
                    except Exception as error:
                        report["cleanup_errors"].append(dict(stage=name, error=str(error)))
    report["success"] = report["success"] and not report["cleanup_errors"]
    persist()
    return 0 if report["success"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args(argv)
    if not args.swconst.is_file():
        parser.error("--swconst must name an existing official type library")
    try:
        args.output_dir.mkdir()
    except OSError as error:
        parser.error("--output-dir must be new, with an existing parent: " + str(error))
    return run(args.output_dir.resolve(), args.swconst.resolve(), args.visible)


if __name__ == "__main__":
    raise SystemExit(main())
