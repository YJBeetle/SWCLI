"""Durable direction singleton and finite per-plane matrix protocol."""
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
PLANES = {
    "front": tuple(IDENTITY),
    "top": (1,0,0,0,0,1,0,-1,0,0,0,0,1,0,0,0),
    "right": (0,0,1,0,1,0,-1,0,0,0,0,0,1,0,0,0),
}
MATRIX_ANGLES = (90, 45, 180, 270)


def case_name(case):
    return f"{case['plane']}-direction-{case['angle_deg']}"


def plane_plan(plane):
    require(plane in PLANES, "unknown matrix plane")
    return [dict(deepcopy(CASE), plane=plane, angle_deg=angle) for angle in MATRIX_ANGLES]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class NativeReceiptError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require_native_ok(receipt, stage):
    if receipt.get("ok") is True:
        return
    error = receipt.get("error") or {}
    raise NativeReceiptError(error.get("type") or "DirectionNativeReceiptFailed",
                             error.get("message") or f"{stage} did not report success")


def require_clean_reopen(receipt):
    require_native_ok(receipt, "read-only reopen")
    for member in ("api_errors", "api_warnings"):
        value = receipt.get(member)
        require(type(value) is int and value == 0,
                f"read-only reopen returned {member}={value!r}")


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


def matches_plane_frame(transform, plane):
    return (len(transform)==16 and all(type(a) in (int,float) and math.isfinite(a) and
            math.isclose(a,b,rel_tol=0,abs_tol=1e-12) for a,b in zip(transform,PLANES[plane])))


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
    require(matches_plane_frame(creation["model_to_sketch_transform"], case["plane"]), "direction creation frame differs from preregistered plane")
    expected = sector_expectation(case["bounds_mm"], PLANES[case["plane"]], case["angle_deg"], rotation_sign=case["rotation_sign"])
    verify_sector_metrics(creation["expected_metrics"], expected)
    verify_sector_metrics(creation["metrics"], expected)
    return expected


def validate_reopened(observed, saved, creation, case, expected, configuration):
    require_clean_reopen(observed["reopen"])
    require(observed["feature_count"] == 1 and observed["profile_count"] == 1 and
            observed["body_count"] == 1, "reopened direction feature/profile/body count differs")
    require(len(observed["bounds_mm"]) == 4 and all(math.isclose(a,b,rel_tol=0,abs_tol=1e-6)
            for a,b in zip(observed["bounds_mm"],case["bounds_mm"])), "saved direction profile differs")
    require(matches_plane_frame(observed["model_to_sketch_transform"], case["plane"]), "saved direction frame differs")
    require(points_match(observed["axis_points_mm"],creation["candidate"]["axis_points_mm"]), "saved ordered axis differs")
    validate_definition(observed["definition"],case,observed["axis_points_mm"])
    measurement = observed["measurement"]
    require_native_ok(measurement, "reopened direction measurement")
    verify_sector_metrics(measurement["metrics"], expected)
    require(observed["diagnostics"]["healthy"] is True and observed["diagnostics"]["truncated"] is False,
            "reopened direction diagnostics unhealthy or incomplete")
    require(observed["state"] == dict(read_only=True, modified=False, editing=False, selected=0,
            foreground_same=1, configurations=[configuration], active_configuration=configuration),
            "read-only direction reopen state differs")
    require(observed["file_sha256"] == saved["file_sha256"], "read-only reopen changed native file bytes")


def _run_case(backend, evidence, report, case_report):
    case = deepcopy(case_report["case"])

    def checkpoint(name, operation):
        def invoke():
            case_report[name] = operation()
            return case_report[name]
        value = evidence.call(name, invoke)
        evidence.save(report)
        return value

    checkpoint("fixture", lambda: backend.fixture(deepcopy(case)))

    def create():
        creation, retained = backend.create(deepcopy(case))
        case_report["creation"] = creation
        case_report["feature_handle_retained"] = retained

    evidence.call("create-once", create)
    evidence.save(report)
    creation = case_report["creation"]
    expected = validate_creation(creation, case_report["feature_handle_retained"], case)
    saved = checkpoint("saved", lambda: backend.save(case))
    require_native_ok(saved["save"], "save direction model")
    require(saved["file_size_bytes"] > 0, "saved direction model is empty")
    evidence.call("close-before-reopen", backend.close)
    reopened = case_report["reopened"] = {}
    evidence.call("reopen-read-only", lambda: backend.reopen(saved, creation, deepcopy(case), reopened))
    evidence.save(report)
    validate_reopened(reopened, saved, creation, case, expected, case_report["fixture"]["configuration"])
    evidence.call("close-read-only", backend.close)


def run_direction(backend, evidence, source_commit, *, matrix_plane=None):
    matrix = matrix_plane is not None
    report = dict(success=False,
        profile="internal-revolve-direction-plane-v1" if matrix else "internal-revolve-direction-only-v1",
        source_commit=source_commit, public_acceptance=False, full_acceptance_eligible=False,
        public_write_gate="closed", matrix_enabled=matrix, native_timeout_seconds=600,
        group_timeout_seconds=1800, cleanup_errors=[], evidence_errors=[])
    if matrix:
        plan = plane_plan(matrix_plane)
        report.update(matrix_plane=matrix_plane, planned_cases=plan, cases=[])
    else:
        report["case"] = deepcopy(CASE)
    case_report = report
    backend.call = evidence.call

    def start():
        report["host"] = backend.start()

    try:
        evidence.save(report)  # Preregister the full plan before acquiring the host.
        evidence.call("host", start)
        evidence.save(report)
        if matrix:
            for case in plan:
                case_report = dict(case=deepcopy(case), success=False)
                report["cases"].append(case_report)
                evidence.save(report)
                evidence.call(case_name(case), lambda: _run_case(backend, evidence, report, case_report))
                case_report["success"] = True
                evidence.save(report)
        else:
            evidence.call("direction-case", lambda: _run_case(backend, evidence, report, case_report))
        report["success"] = True
    except BaseException as error:
        primary = case_report.get("creation", {}).get("error")
        failure = dict(primary) if primary else dict(type=getattr(error, "code", type(error).__name__), message=str(error))
        failure["boundary_evidence_error"] = getattr(error, "boundary_evidence_error", None)
        report["failure"] = failure
        if matrix and case_report is not report:
            report["failed_case"] = case_name(case_report["case"])
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
            evidence.save(report)
        except BaseException as error:
            report["success"] = False
            report["evidence_errors"].append(dict(stage="final-checkpoint", error=str(error)))
    return report
