"""Durable, single-hypothesis direction protocol; injectable without native CAD."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import threading
import time

from swcli.revolve_geometry import sector_expectation, verify_sector_metrics

CASE = dict(plane="front", bounds_mm=[0,-5,10,15], axis_mm=[0,-5,0,15],
            angle_deg=90, axis_direction=1, rotation_sign=-1)
IDENTITY = [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def json_ready(value):
    if isinstance(value, float) and not math.isfinite(value):
        return dict(nonfinite_float=repr(value))
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_ready(item) for item in value]
    return value


def durable(path, value):
    """Each checkpoint is flushed before the next business operation."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(json_ready(value), ensure_ascii=True, allow_nan=False, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Evidence:
    def __init__(self, output):
        self.output = Path(output)
        self.sequence = 0
        self.errors = []

    def save(self, report):
        durable(self.output / "report.json", report)

    def event(self, value):
        with (self.output / "boundaries.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def call(self, name, function, *, required=True):
        self.sequence += 1
        event = dict(sequence=self.sequence, call=name, time=time.time())
        try:
            self.event(dict(event, phase="begin"))
        except BaseException as error:
            if required: raise
            self.errors.append(dict(stage=name+":begin",error=str(error)))
        def timeout():
            try:
                durable(self.output / "native-timeout.json", dict(event, seconds=600))
            finally:
                os._exit(124)
        timer = threading.Timer(600, timeout)
        timer.daemon = True
        timer.start()
        try:
            value = function()
        except BaseException as error:
            try:
                self.event(dict(event, phase="error", error_type=type(error).__name__, error=str(error)))
            except BaseException as evidence_error:
                error.boundary_evidence_error = str(evidence_error)
            raise
        finally:
            timer.cancel()
        try:
            self.event(dict(event, phase="end", time=time.time()))
        except BaseException as error:
            if required: raise
            self.errors.append(dict(stage=name+":end",error=str(error)))
        return value


def points_match(actual, expected):
    return (isinstance(actual,(list,tuple)) and isinstance(expected,(list,tuple)) and
            len(actual)==len(expected)==2 and all(len(p)==len(q)==3 and all(
                type(a) in (int,float) and math.isfinite(a) and math.isclose(a,b,rel_tol=0,abs_tol=1e-6)
                for a,b in zip(p,q)) for p,q in zip(actual,expected)))


def front_frame(transform):
    return (len(transform)==16 and all(type(a) in (int,float) and math.isfinite(a) and
            math.isclose(a,b,rel_tol=0,abs_tol=1e-12) for a,b in zip(transform,IDENTITY)))


def validate_definition(definition, case, points):
    require(type(definition["angle_rad"]) in (int,float) and math.isfinite(definition["angle_rad"]) and
            math.isclose(definition["angle_rad"],math.radians(case["angle_deg"]),rel_tol=0,abs_tol=1e-12),
            "direction definition angle differs")
    for key,value in dict(reverse=False,kind=0,boss=True,thin=False,merge=True,axis_type=10,
                          contour_count=0,axis_matches=True).items():
        require(type(definition[key]) is type(value) and definition[key]==value,"direction definition differs: "+key)
    require(definition["cleanup_errors"]==[] and points_match(definition["axis_points_mm"],points),
            "direction definition axis/cleanup differs")


def validate_creation(creation, retained, case):
    require(creation.get("ok") is True and retained is True, "direction creation failed or exact handle lost")
    require(creation.get("mutation") == dict(attempted=True, creation_returned=True, may_have_changed=True),
            "direction creation lacks complete mutation receipt")
    require(creation["candidate"]["rotation_sign"] == case["rotation_sign"] and
            creation["candidate"]["axis_direction"] == case["axis_direction"], "direction hypothesis changed")
    require(creation["angle_deg"] == case["angle_deg"] and creation["axis_mm"] == case["axis_mm"] and
            creation["expected_profile_mm"] == case["bounds_mm"], "direction creation intent differs")
    require(creation["verified"] is True and creation["cleanup_errors"]==[] and
            creation["feature"]["type"]=="Revolution" and bool(creation["feature"]["name"]), "direction creation evidence incomplete")
    require(creation["diagnostics"]["healthy"] is True and creation["diagnostics"]["truncated"] is False,
            "direction creation diagnostics incomplete")
    points=[(0,case["axis_mm"][1],0),(0,case["axis_mm"][3],0)]
    require(points_match(creation["candidate"]["axis_points_mm"],points),"ordered axis differs from preregistered +Y")
    validate_definition(creation["definition"],case,points)
    require(front_frame(creation["model_to_sketch_transform"]), "direction singleton requires front origin frame")
    expected = sector_expectation(case["bounds_mm"], IDENTITY, case["angle_deg"], rotation_sign=case["rotation_sign"])
    verify_sector_metrics(creation["expected_metrics"], expected)
    verify_sector_metrics(creation["metrics"], expected)
    return expected


def validate_reopened(observed, saved, creation, case, expected, configuration):
    require(observed["reopen"]["ok"] is True and observed["reopen"]["api_errors"] == 0 and
            observed["reopen"]["api_warnings"] == 0, "saved direction reopen failed")
    require(observed["feature_count"] == 1 and observed["profile_count"] == 1 and
            observed["body_count"] == 1, "reopened direction feature/profile/body count differs")
    require(len(observed["bounds_mm"]) == 4 and all(math.isclose(a,b,rel_tol=0,abs_tol=1e-6)
            for a,b in zip(observed["bounds_mm"],case["bounds_mm"])), "saved direction profile differs")
    require(front_frame(observed["model_to_sketch_transform"]), "saved direction frame differs")
    require(points_match(observed["axis_points_mm"],creation["candidate"]["axis_points_mm"]), "saved ordered axis differs")
    validate_definition(observed["definition"],case,observed["axis_points_mm"])
    verify_sector_metrics(observed["measurement"]["metrics"], expected)
    require(observed["measurement"]["ok"] is True, "reopened direction measurement unavailable")
    require(observed["diagnostics"]["healthy"] is True and observed["diagnostics"]["truncated"] is False,
            "reopened direction diagnostics unhealthy or incomplete")
    require(observed["state"] == dict(read_only=True, modified=False, editing=False, selected=0,
            foreground_same=1, configurations=[configuration], active_configuration=configuration),
            "read-only direction reopen state differs")
    require(observed["file_sha256"] == saved["file_sha256"], "read-only reopen changed native file bytes")


def run_direction(backend, evidence, source_commit):
    report = dict(success=False, profile="internal-revolve-direction-only-v1", source_commit=source_commit,
        public_acceptance=False, full_acceptance_eligible=False, public_write_gate="closed",
        matrix_enabled=False, native_timeout_seconds=600, group_timeout_seconds=1800,
        case=deepcopy(CASE), cleanup_errors=[], evidence_errors=[])
    backend.call = evidence.call
    def save():
        evidence.save(report)
    def observe(name, function):
        def invoke():
            report[name] = function()
            return report[name]
        result = evidence.call(name, invoke)
        save()
        return result
    try:
        save()  # Preregister exactly one hypothesis before any host acquisition.
        observe("host", backend.start)
        def case_flow():
            observe("fixture", lambda: backend.fixture(deepcopy(report["case"])))
            def create():
                creation, retained = backend.create(deepcopy(report["case"]))
                report["creation"] = creation
                report["feature_handle_retained"] = retained
            evidence.call("create-once", create)
            save()  # Retain actual response, even on failure, before assertions.
            expected = validate_creation(report["creation"], report["feature_handle_retained"], report["case"])
            saved = observe("saved", backend.save)
            require(saved["save"]["ok"] is True and saved["file_size_bytes"] > 0, "save direction model failed")
            evidence.call("close-before-reopen", backend.close)
            report["reopened"] = {}
            evidence.call("reopen-read-only", lambda: backend.reopen(saved, report["creation"], deepcopy(report["case"]), report["reopened"]))
            save()  # Complete observed data precedes every reopen oracle.
            validate_reopened(report["reopened"], saved, report["creation"], report["case"], expected, report["fixture"]["configuration"])
            evidence.call("close-read-only", backend.close)
        evidence.call("direction-case", case_flow)
        report["success"] = True
    except BaseException as error:
        primary = report.get("creation",{}).get("error")
        report["failure"] = dict(primary) if primary else dict(type=getattr(error,"code",type(error).__name__),message=str(error))
        report["failure"]["boundary_evidence_error"] = getattr(error,"boundary_evidence_error",None)
    finally:
        try:
            report["cleanup_errors"].extend(evidence.call("owned-cleanup", backend.cleanup, required=False))
        except BaseException as error:
            report["cleanup_errors"].append(dict(stage="owned-cleanup", error=str(error)))
        report["owned_cleanup_completed"] = not report["cleanup_errors"]
        if report["cleanup_errors"] and "failure" not in report:
            report["failure"] = dict(type="DirectionCleanupFailed",message=report["cleanup_errors"][0]["error"])
        report["evidence_errors"].extend(evidence.errors)
        report["success"] = report["success"] and not report["cleanup_errors"] and not report["evidence_errors"]
        try:
            save()
        except BaseException as error:
            report["success"] = False
            report["evidence_errors"].append(dict(stage="final-checkpoint", error=str(error)))
    return report
