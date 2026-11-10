"""Diagnostic owned two-configuration getter fixture; prepend within one combined full.

Preparation writes only our generated part. Read windows never select a
configuration, set a dimension, rebuild or save. This is not public acceptance.
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

from swcli.hosts.windows import _com_value
from swcli.hosts.windows_configurations import active_configuration_name
from swcli.hosts.windows_custom_properties import _state
from swcli.hosts.windows_dimensions import _descriptor, create_circle_diameter_windows_with_handle, _SPECIFY_CONFIGURATION, _diameter_circle_verification
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_sketches import create_circle_sketch_windows_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.native_trace import native_call, trace_native_request

spec = importlib.util.spec_from_file_location("_getter_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
require = harness.checked


def read_constants(pythoncom, path):
    wanted = {"swSpecifyConfiguration", "swSetValue_InSpecificConfigurations", "swDimensionParamTypeDoubleLinear",
              "swObjectNotSame", "swObjectSame", "swObjectUnsupported"}
    library = pythoncom.LoadTypeLib(str(path))
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        if info.GetTypeAttr().typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(info.GetTypeAttr().cVars):
            item = info.GetVarDesc(offset)
            name = info.GetDocumentation(item[0])[0]
            if name in wanted:
                require(name not in found and type(item.value) is int, "ambiguous native configuration enum")
                found[name] = item.value
    require(set(found) == wanted and found["swSpecifyConfiguration"] == _SPECIFY_CONFIGURATION
            and found["swDimensionParamTypeDoubleLinear"] == 0
            and (found["swObjectNotSame"], found["swObjectSame"], found["swObjectUnsupported"]) == (0, 1, 2),
            "installed swSpecifyConfiguration differs from the getter")
    return found


def same(app, first, second, record, role, *, persist=None):
    row = dict(role=role, attempted=True)
    record.setdefault("identity_checks", []).append(row)
    try:
        status = native_call("getter-identity", "ISldWorks.IsSame", lambda: app.IsSame(first, second))
    except Exception as error:
        row["exception"] = dict(type=type(error).__name__, message=str(error))
        if persist is not None:
            try:
                persist()
            except Exception as persistence_error:
                row["persistence_exception"] = dict(type=type(persistence_error).__name__, message=str(persistence_error))
        raise
    row["return_type"] = type(status).__name__
    row["return_value"] = json_value(status)
    row["equality"] = ({0: "not-same", 1: "same", 2: "unsupported"}.get(status, "unknown")
                       if type(status) is int else "invalid-type")
    if persist is not None:
        persist()
    require(type(status) is int and status in (0, 1), "native identity is unreadable or unsupported")
    return status == 1


def configuration_object(document):
    return _com_value(_com_value(document, "ConfigurationManager"), "ActiveConfiguration")


def state(document):
    return dict(metadata=list(_state(document)), path=_com_value(document, "GetPathName"),
                title=_com_value(document, "GetTitle"), readonly=_com_value(document, "IsOpenedReadOnly"))


def json_value(value):
    if type(value) in (tuple, list):
        return [json_value(v) for v in value]
    if type(value) in (int, float) and not isinstance(value, bool):
        try:
            if math.isfinite(value): return value
        except OverflowError: pass
    if value is None or type(value) in (str, bool): return value
    return {"type": type(value).__name__, "repr": repr(value)[:100]}


class CapturedDimension:
    """Forward the original getter once; retain actual return shape without re-query."""
    def __init__(self, dimension, record):
        self.dimension, self.record = dimension, record
    def __getattr__(self, name):
        return getattr(self.dimension, name)
    def GetSystemValue3(self, which, config_names):
        calls = self.record.setdefault("get3_calls", [])
        row = dict(which=which, config_names=config_names, config_names_type=type(config_names).__name__)
        calls.append(row)
        value = self.dimension.GetSystemValue3(which, config_names)
        row.update(return_type=type(value).__name__,
                   count=len(value) if type(value) in (tuple, list) else None,
                   values=json_value(value))
        return value


def observe_current(app, document, dimension, configuration, expected_mm, record, *, request_id, expected_native_name, persist=None):
    record.update(request_id=request_id, expected_configuration=configuration, expected_mm=expected_mm)
    with trace_native_request(request_id, "diagnostic.getter-current-configuration"):
        before_config = configuration_object(document)
        foreground = _com_value(app, "ActiveDoc")
        record["before"] = state(document)
        require(active_configuration_name(document) == configuration, "preparation did not select the intended current configuration")
        record["dimension_name"] = _com_value(dimension, "Name")
        require(isinstance(record["dimension_name"], str) and record["dimension_name"]
                and expected_native_name.startswith(record["dimension_name"] + "@"), "dimension Name/FullName mismatch")
        record["dimension_native_type"] = _com_value(dimension, "GetType")
        require(type(record["dimension_native_type"]) is int and record["dimension_native_type"] == 0,
                "fixture dimension is not the existing length profile")
        descriptor = _descriptor(document, CapturedDimension(dimension, record))
        record["descriptor"] = descriptor
        calls = record["get3_calls"]
        require(len(calls) == 1 and calls[0]["which"] == _SPECIFY_CONFIGURATION
                and calls[0]["config_names_type"] == "str" and calls[0]["config_names"] == configuration
                and calls[0]["count"] == 1, "Get3 did not query exactly the current single BSTR once")
        require(descriptor["configuration"] == configuration and descriptor["unit"] == "millimeter"
                and math.isclose(descriptor["value"], expected_mm, rel_tol=0, abs_tol=1e-6)
                and descriptor["driven_state"] == 2 and descriptor["read_only"] is False
                and descriptor["native_name"] == expected_native_name, "native getter value/metadata mismatch")
        record["after"] = state(document)
        record["same_configuration_object"] = same(
            app, before_config, configuration_object(document), record, "read-window-configuration", persist=persist)
        record["same_foreground_object"] = same(
            app, foreground, _com_value(app, "ActiveDoc"), record, "read-window-foreground", persist=persist)
        require(record["before"] == record["after"] and record["same_configuration_object"]
                and record["same_foreground_object"], "read changed config identity/state/foreground")
        record["success"] = True


def preparation_edit_state(document):
    try:
        manager = _com_value(document, "SketchManager")
        require(manager is not None, "sketch manager is unavailable")
        return dict(status="observed", active_sketch=_com_value(manager, "ActiveSketch") is not None)
    except Exception as error:
        return dict(status="unknown", error=dict(type=type(error).__name__, message=str(error)))


def fixture_configuration_names(document, expected_names, record, key):
    names = _com_value(document, "GetConfigurationNames")
    record[key] = json_value(names)
    require(type(names) in (tuple, list) and len(names) == 2
            and all(isinstance(name, str) and bool(name.strip()) for name in names)
            and set(names) == set(expected_names), "fixture configuration set changed")


def select_fixture_configuration(app, document, name, call, record, *, expected_names, persist=None):
    # Fixture preparation BETWEEN read windows. A failed Show is never recovered
    # by reading its resulting state. Different configuration objects are not
    # compared across a switch; document and stable current identities must match.
    record["target"] = name
    record["show_attempted"] = False
    record["expected_names"] = json_value(expected_names)
    require(type(expected_names) in (tuple, list) and len(expected_names) == 2
            and all(isinstance(item, str) and bool(item.strip()) for item in expected_names)
            and len(set(expected_names)) == 2 and name in expected_names, "invalid expected fixture configurations")
    record["before_edit_state"] = preparation_edit_state(document)
    before = configuration_object(document)
    before_name = _com_value(before, "Name")
    record["before_name"] = before_name
    require(isinstance(before_name, str) and bool(before_name.strip()), "fixture current configuration is unreadable")
    fixture_configuration_names(document, expected_names, record, "before_configuration_names")
    require(before_name in expected_names, "fixture current configuration is outside the expected set")
    foreground = _com_value(app, "ActiveDoc")
    record["same_document_before"] = same(
        app, document, foreground, record, "prepared-document-vs-foreground", persist=persist)
    require(record["same_document_before"], "fixture foreground document differs")
    record["skipped_already_current"] = before_name == name
    if before_name != name:
        record["show_attempted"] = True
        try:
            status = call("prepare-select-" + name, lambda: document.ShowConfiguration2(name))
        except Exception as error:
            record["show_exception"] = dict(type=type(error).__name__, message=str(error))
            raise
        record["show_return_type"] = type(status).__name__
        record["show_return_value"] = json_value(status)
        require(status is True, "fixture configuration selection failed")
    after = configuration_object(document)
    record["after_name"] = _com_value(after, "Name")
    require(record["after_name"] == name, "fixture selected another configuration")
    fixture_configuration_names(document, expected_names, record, "after_configuration_names")
    record["after_edit_state"] = preparation_edit_state(document)
    record["same_document_after"] = same(
        app, foreground, _com_value(app, "ActiveDoc"), record, "foreground-across-preparation", persist=persist)
    require(record["same_document_after"], "fixture preparation changed foreground document")
    record["same_active_object"] = same(
        app, after, configuration_object(document), record, "stable-current-configuration", persist=persist)
    require(record["same_active_object"], "fixture selected an unstable configuration")
    if record["skipped_already_current"]:
        record["same_before_after_object"] = same(
            app, before, after, record, "unchanged-current-configuration", persist=persist)
        require(record["same_before_after_object"], "fixture current configuration identity changed without selection")
    record["success"] = True


def rebuild_fixture(document, label, call, record):
    record["attempted"] = True
    try:
        status = call("prepare-rebuild-" + label, lambda: _com_value(document, "EditRebuild3"))
    except Exception as error:
        record["exception"] = dict(type=type(error).__name__, message=str(error))
        raise
    record.update(return_type=type(status).__name__, return_value=json_value(status))
    require(status is True, label + " rebuild failed")
    record["success"] = True


def seed_fixture_configuration(dimension, value_m, which, name, call, record, *, persist=None):
    import pythoncom
    from win32com.client import VARIANT
    record["attempted"] = False
    record["value_m"] = value_m
    record["which"] = which
    record["target"] = name
    variant_type = pythoncom.VT_ARRAY | pythoncom.VT_BSTR
    argument = VARIANT(variant_type, (name,))
    record["argument_type"] = type(argument).__name__
    record["variant_type"] = argument.varianttype
    record["config_names"] = json_value(argument.value)
    require(type(argument.varianttype) is int and argument.varianttype == variant_type
            and type(argument.value) in (tuple, list) and tuple(argument.value) == (name,),
            "fixture seed requires exactly one explicit BSTR array")
    record["attempted"] = True
    try:
        status = call("prepare-B-value", lambda: dimension.SetSystemValue3(value_m, which, argument))
    except Exception as error:
        record["exception"] = dict(type=type(error).__name__, message=str(error))
        if persist is not None:
            try:
                persist()
            except Exception as persistence_error:
                record["persistence_exception"] = dict(type=type(persistence_error).__name__, message=str(persistence_error))
        raise
    record["return_type"] = type(status).__name__
    record["return_value"] = json_value(status)
    if persist is not None:
        persist()
    require(type(status) is int and status == 0, "B seed write failed")
    record["success"] = True


def observe_fixture_geometry(app, document, sketch_name, configuration, expected_diameter_mm, record, *,
                             request_id, persist=None, source_path=None, expected_sha256=None):
    record["request_id"] = request_id
    record["expected_configuration"] = configuration
    record["expected_diameter_mm"] = expected_diameter_mm
    if source_path is not None:
        record["source_sha256_before"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        require(record["source_sha256_before"] == expected_sha256, "geometry proof source bytes changed")
    with trace_native_request(request_id, "diagnostic.getter-fixture-geometry"):
        before_config = configuration_object(document)
        foreground = _com_value(app, "ActiveDoc")
        record["before"] = state(document)
        record["before_edit_state"] = preparation_edit_state(document)
        require(record["before"]["metadata"][0] == 1 and type(record["before"]["readonly"]) is bool,
                "geometry proof requires an observable part context")
        require(record["before_edit_state"] == dict(status="observed", active_sketch=False), "geometry proof requires a finished sketch")
        require(record["before"]["metadata"][3] == configuration, "geometry proof has another current configuration")
        record["same_document_before"] = same(
            app, document, foreground, record, "geometry-bound-document", persist=persist)
        require(record["same_document_before"], "geometry proof has another foreground document")
        feature = native_call("fixture-geometry", "IModelDoc2.FeatureByName", lambda: document.FeatureByName(sketch_name))
        require(feature is not None, "geometry proof sketch feature is missing")
        record["feature_name"] = _com_value(feature, "Name")
        record["feature_type"] = _com_value(feature, "GetTypeName2")
        require(record["feature_name"] == sketch_name and record["feature_type"] == "ProfileFeature",
                "geometry proof sketch feature differs")
        sketch = _com_value(feature, "GetSpecificFeature2")
        require(sketch is not None, "geometry proof native sketch is missing")
        record["geometry"] = _diameter_circle_verification(sketch, expected_diameter_mm / 2, 0., 0.)
        if persist is not None:
            persist()
        require(record["geometry"]["passed"] is True, "fixture independent circle geometry mismatch")
        record["after"] = state(document)
        record["after_edit_state"] = preparation_edit_state(document)
        record["same_configuration_object"] = same(
            app, before_config, configuration_object(document), record, "geometry-current-configuration", persist=persist)
        record["same_foreground_object"] = same(
            app, foreground, _com_value(app, "ActiveDoc"), record, "geometry-foreground", persist=persist)
        require(record["before"] == record["after"] and record["before_edit_state"] == record["after_edit_state"]
                and record["same_configuration_object"] and record["same_foreground_object"],
                "geometry proof changed state/configuration/foreground")
    if source_path is not None:
        record["source_sha256_after"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        require(record["source_sha256_after"] == expected_sha256, "geometry proof changed saved bytes")
    record["success"] = True


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind):
    import pythoncom
    case.update(preparation_only=True, public_acceptance=False, observations=[])
    report["source_commit"] = os.environ.get("GITHUB_SHA")
    report["native_call_worker_pid"] = os.getpid()
    def persist():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    case["swconst_sha256"] = hashlib.sha256(SWCONST.read_bytes()).hexdigest()
    enums = case["configuration_constants"] = call("read-configuration-enums", lambda: read_constants(pythoncom, SWCONST))
    made, document = call("prepare-part", lambda: create_part_windows_with_handle(app=app))
    live["document"] = document
    require(made["ok"] and document is not None, "part fixture creation failed")
    original_name = active_configuration_name(document)
    case["configuration_A"] = original_name
    preparation = case.setdefault("configuration_preparation", [])
    rebuilds = case.setdefault("rebuild_preparation", [])
    geometry_proofs = case.setdefault("geometry_proofs", [])
    def select(name, phase):
        record = dict(phase=phase)
        preparation.append(record)
        select_fixture_configuration(app, document, name, call, record,
                                     expected_names=(original_name, "Getter_B"), persist=persist)
    def rebuild(label):
        record = dict(label=label)
        rebuilds.append(record)
        rebuild_fixture(document, label, call, record)
    def geometry(name, expected, phase, source_path=None, expected_sha256=None):
        record = dict(phase=phase)
        geometry_proofs.append(record)
        call("prove-circle-" + phase, lambda: observe_fixture_geometry(
            app, document, case["sketch_name"], name, expected, record,
            request_id="getter-fixture-geometry-" + phase, persist=persist,
            source_path=source_path, expected_sha256=expected_sha256))
    require(original_name != "Getter_B", "fixture initial configuration collides with B")
    circle, sketch = call("prepare-circle", lambda: create_circle_sketch_windows_with_handle(
        app=app, document=document, plane="front", radius_mm=8))
    case["circle_creation"] = circle
    require(circle["ok"] and sketch is not None, "circle fixture failed")
    case["sketch_name"] = _com_value(sketch, "Name")
    require(isinstance(case["sketch_name"], str) and bool(case["sketch_name"].strip()), "fixture sketch name is unreadable")
    created, dimension = call("prepare-driving-diameter", lambda: create_circle_diameter_windows_with_handle(
        app=app, document=document, sketch_feature=sketch, diameter_mm=16))
    case["diameter_creation"] = created
    require(created["ok"] and dimension is not None, "driving fixture failed")
    case["unsaved_native_name"] = _com_value(dimension, "FullName")
    case["after_dimension_creation_edit_state"] = preparation_edit_state(document)
    geometry(original_name, 16., "initial-A")
    manager = _com_value(document, "ConfigurationManager")
    second_name = "Getter_B"
    added = call("prepare-second-configuration", lambda: manager.AddConfiguration2(
        second_name, "getter fixture", "", 0, "", "diagnostic only", True))
    require(added is not None and _com_value(added, "Name") == second_name, "second configuration creation failed")
    select(second_name, "seed-B")
    seed_fixture_configuration(dimension, .020, enums["swSetValue_InSpecificConfigurations"], second_name,
                               call, case.setdefault("B_seed", {}), persist=persist)
    rebuild("B")
    geometry(second_name, 20., "seed-B")
    names = _com_value(document, "GetConfigurationNames")
    require(isinstance(names, (tuple, list)) and len(names) == 2 and set(names) == {original_name, second_name},
            "fixture must have exactly two configurations")
    select(original_name, "rebuild-A")
    rebuild("A")
    geometry(original_name, 16., "seed-A")
    case.update(configuration_A=original_name, configuration_B=second_name,
                preparation_complete_edit_state=preparation_edit_state(document))
    path = output / "two-configurations.SLDPRT"
    case["save"] = call("prepare-save-native", lambda: save_as_native_windows(str(path), document=document))
    require(case["save"]["ok"] and case["save"]["api_saved"] and case["save"]["save_errors"] == 0
            and case["save"]["save_warnings"] == 0, "modern native fixture save failed")
    case["native_name"] = native_name = _com_value(dimension, "FullName")
    require(isinstance(native_name, str) and native_name, "saved dimension name is unreadable")
    case["saved_sha256"] = digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for phase in ("saved", "reopened-readonly"):
        if phase == "reopened-readonly":
            call("close-saved", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
            live["document"] = None
            opened, document = call("reopen-readonly", lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
            live["document"] = document
            case["reopen"] = opened
            require(opened["ok"] and opened["read_only"] is True and opened["api_errors"] == opened["api_warnings"] == 0
                    and _com_value(document, "GetSaveFlag") is False, "readonly reopen failed")
        for label, name, expected in (("A", original_name, 16.), ("B", second_name, 20.)):
            select(name, phase + "-" + label)
            geometry(name, expected, phase + "-" + label, path, digest)
            dimension = call("bind-existing-dimension-" + phase + label, lambda: document.Parameter(native_name))
            require(dimension is not None and _com_value(dimension, "FullName") == native_name, "exact dimension name binding failed")
            row = dict(phase=phase, label=label)
            case["observations"].append(row)
            call("observe-" + phase + label, lambda: observe_current(app, document, dimension, name, expected, row,
                 request_id="getters-" + phase + "-" + label, expected_native_name=native_name, persist=persist))
            require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "observation changed saved bytes")
    case["final_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    require(_com_value(app, "GetProcessID") == report["host"]["process_id"], "fixture host changed")
    call("close-readonly", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = None
    require(_com_value(app, "GetDocumentCount") == 0, "fixture document remains")
    case["success"] = True


def deadline_reason(records, elapsed, now, started):
    if elapsed >= 1800: return "group exceeded 1800 seconds"
    boundary = next((r["time"] for r in reversed(records) if "time" in r), started)
    if now - boundary >= 600: return "native boundary exceeded 600 seconds"
    return None


def audit_read_trace(path, observations, worker_pid):
    records = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
               if line.startswith('{')]
    records = [r for r in records if r.get("event") == "swcli.native-call"]
    expected = {"getters-" + phase + "-" + label
                for phase in ("saved", "reopened-readonly") for label in ("A", "B")}
    require(len(observations) == 4 and {r["request_id"] for r in observations} == expected,
            "four distinct saved/reopened A/B observations are required")
    allowed = {"diagnostic.getter-current-configuration", "ConfigurationManager", "ActiveConfiguration", "Name",
               "ActiveDoc", "GetType", "GetUpdateStamp", "GetSaveFlag", "GetPathName", "GetTitle",
               "IsOpenedReadOnly", "DrivenState", "ReadOnly", "FullName", "IDimension.GetSystemValue3", "ISldWorks.IsSame"}
    proof = []
    for observation in observations:
        rows = [r for r in records if r["request_id"] == observation["request_id"]]
        require(rows and all(r["worker_pid"] == worker_pid
                and r["operation"] == "diagnostic.getter-current-configuration" for r in rows),
                "read trace worker/request correlation mismatch")
        begins = [(r["sequence"], r["call"]) for r in rows if r["phase"] == "begin"]
        ends = [(r["sequence"], r["call"]) for r in rows if r["phase"] == "end"]
        require(sorted(begins) == sorted(ends) and len(set(begins)) == len(begins)
                and all(r["phase"] in ("begin", "end") for r in rows), "read trace failed or incomplete")
        calls = [call for _, call in begins]
        require(set(calls) <= allowed and calls.count("IDimension.GetSystemValue3") == 1
                and calls.count("ISldWorks.IsSame") == 2, "read window contains mutation/unknown/missing native calls")
        triples = sum(calls[i:i+3] == ["ConfigurationManager", "ActiveConfiguration", "Name"] for i in range(len(calls)-2))
        require(triples >= 2, "read trace lacks modern current configuration before/after evidence")
        proof.append(dict(request_id=observation["request_id"], calls=calls, worker_pid=worker_pid))
    return proof


def audit_geometry_trace(path, observations, worker_pid):
    phases = {"initial-A", "seed-B", "seed-A", "saved-A", "saved-B", "reopened-readonly-A", "reopened-readonly-B"}
    expected = {"getter-fixture-geometry-" + phase for phase in phases}
    require(len(observations) == 7 and {row["request_id"] for row in observations} == expected
            and all(row.get("success") is True for row in observations), "seven independent circle proofs are required")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.startswith('{')]
    allowed = {"diagnostic.getter-fixture-geometry", "ConfigurationManager", "ActiveConfiguration", "Name", "ActiveDoc",
               "GetType", "GetUpdateStamp", "GetSaveFlag", "GetPathName", "GetTitle", "IsOpenedReadOnly", "ISldWorks.IsSame",
               "IModelDoc2.FeatureByName", "GetTypeName2", "GetSpecificFeature2", "GetSketchSegments", "ConstructionGeometry",
               "IsCircle", "GetCenterPoint2", "X", "Y", "Z", "GetRadius", "SketchManager", "ActiveSketch"}
    proof = []
    for observation in observations:
        rows = [r for r in records if r.get("event") == "swcli.native-call" and r.get("request_id") == observation["request_id"]]
        require(rows and all(r["worker_pid"] == worker_pid and r["operation"] == "diagnostic.getter-fixture-geometry" for r in rows),
                "geometry trace worker/request correlation mismatch")
        begins = [(r["sequence"], r["call"]) for r in rows if r["phase"] == "begin"]
        ends = [(r["sequence"], r["call"]) for r in rows if r["phase"] == "end"]
        require(sorted(begins) == sorted(ends) and len(set(begins)) == len(begins)
                and all(r["phase"] in ("begin", "end") for r in rows), "geometry trace failed or incomplete")
        calls = [name for _, name in begins]
        require(set(calls) <= allowed and calls.count("GetRadius") == 1
                and calls.count("GetSketchSegments") == 1 and calls.count("IModelDoc2.FeatureByName") == 1
                and calls.count("ISldWorks.IsSame") == 3, "geometry proof contains getter/mutation/unknown/missing native calls")
        proof.append(dict(request_id=observation["request_id"], calls=calls, worker_pid=worker_pid))
    return proof


def supervise(args):
    args.output_dir.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-I", str(Path(__file__).resolve()), "--worker",
               "--output-dir", str(args.output_dir), "--swconst", str(args.swconst)]
    started, wall = time.monotonic(), time.time()
    failure = None
    proof = []
    geometry_proof = []
    with (args.output_dir / "worker.stdout.log").open("w") as out, (args.output_dir / "worker.stderr.log").open("w") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err,
                                   env={**os.environ, "SWCLI_TRACE_NATIVE_CALLS": "1"})
        try:
            while process.poll() is None:
                records = []
                trace = args.output_dir / "trace.jsonl"
                if trace.exists():
                    for line in trace.read_text().splitlines(keepends=True):
                        if line.endswith("\n"): records.append(json.loads(line))
                failure = deadline_reason(records, time.monotonic()-started, time.time(), wall)
                if failure: break
                time.sleep(.25)
            if process.returncode == 0 and failure is None:
                report = json.loads((args.output_dir / "report.json").read_text())
                require(report["success"] is True and not report["cleanup_errors"], "owned fixture cleanup failed")
                proof = audit_read_trace(args.output_dir / "worker.stderr.log", report["cases"][0]["observations"], process.pid)
                geometry_proof = audit_geometry_trace(args.output_dir / "worker.stderr.log", report["cases"][0]["geometry_proofs"], process.pid)
        except Exception as error:
            failure = str(error)
        finally:
            if process.poll() is None:
                # Stop only this Python worker, never kill/restart a CAD host.
                process.terminate()
                try: process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    failure = (failure or "worker failed") + "; Python worker termination unconfirmed"
    record = dict(success=process.returncode == 0 and failure is None, worker_exit=process.returncode,
                  failure=failure, cleanup_proven=failure is None and process.returncode == 0,
                  read_trace_proof=proof, geometry_trace_proof=geometry_proof, native_timeout_seconds=600, group_timeout_seconds=1800,
                  full_acceptance_eligible=False)
    (args.output_dir / "supervisor.json").write_text(json.dumps(record, indent=2) + "\n")
    return 0 if record["success"] else 1


def main(argv=None):
    global SWCONST
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true", "only disposable Windows CI may prepare this fixture")
    SWCONST = args.swconst.resolve()
    require(SWCONST.is_file(), "official installed swconst is required")
    if not args.worker: return supervise(args)
    return harness.run(args.output_dir.resolve(), SWCONST, False, case_runner=calibrate_case,
                       case_plan=[("part", "front", False)], diagnostic_case="two-configuration-getter-observation")


if __name__ == "__main__":
    raise SystemExit(main())
