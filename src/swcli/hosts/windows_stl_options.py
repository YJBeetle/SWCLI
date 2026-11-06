"""Qualified isolated-runner STL preference transaction.

A daemon-owned instance alone does not isolate per-user global preferences.
Ordinary/shared hosts remain closed; public tuples require audited data and
an explicit disposable native Windows runner mode.
"""
from contextlib import contextmanager
import csv
import io
import math
import os
from pathlib import Path
import subprocess
from .native_trace import native_call
from .windows import _com_value

_HOST = None
_MODE = None
_POISONED = False
_CONSTANTS = None
PREFERENCES = {
    "swSTLQuality": "IntegerValue", "swExportStlUnits": "IntegerValue",
    "swSTLDeviation": "DoubleValue", "swSTLAngleTolerance": "DoubleValue",
    "swSTLBinaryFormat": "Toggle", "swSTLComponentsIntoOneFile": "Toggle",
    "swSTLShowInfoOnSave": "Toggle", "swSTLPreview": "Toggle",
}
UNIT_NAMES = {"mm": "swMM", "cm": "swCM", "m": "swMETER", "inch": "swINCHES", "foot": "swFEET"}

class StlOptionsError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def configure_calibration_host(app, *, owned):
    """Worker-only registration; no protocol parameter can assert isolation."""
    global _HOST, _MODE
    _HOST = _MODE = None
    if not owned or os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_OS") != "Windows":
        return
    internal = os.environ.get("SWCLI_STL_CALIBRATION") == "1"
    public = os.environ.get("SWCLI_STL_EXCLUSIVE_RUNNER") == "1"
    if internal == public:  # Neither mode or ambiguous double opt-in.
        return
    _HOST = app
    _MODE = "internal-calibration" if internal else "public-isolated"


def read_constants(path):
    import pythoncom
    wanted = set(PREFERENCES) | set(UNIT_NAMES.values()) | {"swSTLQuality_Custom"}
    library = pythoncom.LoadTypeLib(str(path))
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attr = info.GetTypeAttr()
        if attr.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attr.cVars):
            desc = info.GetVarDesc(offset)
            name = info.GetDocumentation(desc[0])[0]
            if name in wanted:
                if name in found:
                    raise StlOptionsError("StlConstantsUnavailable", "duplicate native enum: " + name)
                found[name] = desc.value
    if set(found) != wanted or any(type(value) is not int for value in found.values()):
        raise StlOptionsError("StlConstantsUnavailable", "installed swconst.tlb lacks exact required enums")
    return found


def constants():
    global _CONSTANTS
    if _CONSTANTS is None:
        path = Path(os.environ.get("SWCLI_STL_SWCONST", ""))
        if not path.is_file():
            raise StlOptionsError("StlConstantsUnavailable", "explicit installed swconst.tlb is required")
        _CONSTANTS = read_constants(path)
    return _CONSTANTS


def require_isolation(app):
    if _HOST is not app or _POISONED:
        raise StlOptionsError("StlOptionsNotCalibrated", "ordinary public writes are disabled; STL options require an explicitly qualified isolated Windows runner worker")
    # Detect even non-ROT instances in other sessions. Never terminate them.
    probe = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, check=True, timeout=10)
    rows = list(csv.reader(io.StringIO(probe.stdout)))
    pids = [int(row[1]) for row in rows if len(row) >= 2 and row[0].casefold() == "sldworks.exe"]
    pid = _com_value(app, "GetProcessID")
    visible = _com_value(app, "Visible")
    if type(pid) is not int or pid <= 0 or pids != [pid] or visible is not False:
        raise StlOptionsError("StlIsolationUnavailable", "exactly one owned hidden SOLIDWORKS process is required")


def qualify_public_profile(app, options, document_type, codes):
    """Only retained-output-qualified exact tuples may enter public writes.

    Until the independently audited qualification module exists, public mode
    remains closed even on an explicit disposable isolated runner.
    """
    if _MODE != "public-isolated":
        return None
    try:
        from ..stl_calibrated_profiles import QUALIFICATION, PROFILES, NATIVE_ENUMS
    except ImportError as exc:
        raise StlOptionsError("StlOptionsNotCalibrated", "no independently audited STL qualification is installed") from exc
    if document_type != 1:
        raise StlOptionsError("StlDocumentKindUncalibrated", "public STL options are qualified only for parts")
    names = [name for name, candidate in PROFILES.items() if options == candidate]
    if len(names) != 1:
        raise StlOptionsError("StlOptionsProfileUncalibrated", "this exact STL option tuple has not passed native qualification")
    if _com_value(app, "RevisionNumber") != QUALIFICATION["solidworks_revision"] or codes != NATIVE_ENUMS:
        raise StlOptionsError("StlNativeVersionUncalibrated", "installed native revision/enum vector differs from qualified evidence")
    return names[0]


def _read(app, name, codes):
    kind = PREFERENCES[name]
    value = native_call("stl-preferences-read", "ISldWorks.GetUserPreference" + kind + "." + name,
                        lambda: getattr(app, "GetUserPreference" + kind)(codes[name]))
    expected = bool if kind == "Toggle" else int if kind == "IntegerValue" else float
    if (type(value) is not expected or (expected is float and not math.isfinite(value))):
        raise StlOptionsError("ExportPreferenceUnavailable", "invalid native preference: " + name)
    return value


def _write(app, name, value, codes):
    kind = PREFERENCES[name]
    status = native_call("stl-preferences-write", "ISldWorks.SetUserPreference" + kind + "." + name,
                         lambda: getattr(app, "SetUserPreference" + kind)(codes[name], value))
    # ISldWorks.SetUserPreferenceToggle is void (unlike the integer/double
    # setters). pywin32 must return None; successful setting is established by
    # exact full-vector readback below, never by truth-testing this void result.
    if (kind == "Toggle" and status is not None) or (kind != "Toggle" and status is not True):
        raise StlOptionsError("ExportPreferenceRejected", "unexpected native setter return: " + name)
    return status


@contextmanager
def stl_preferences(app, options, evidence, *, document_type=1):
    """Snapshot all coupled values, set/read once, export once, restore/verify.

    Cleanup never replaces the first exception or native SaveAs return code.
    A restore failure poisons this worker for subsequent STL option requests.
    """
    global _POISONED
    require_isolation(app)
    import win32api
    import win32event
    mutex = win32event.CreateMutex(None, False, "Global\\SWCLI.STL.ExportPreferences")
    held = False
    try:
        status = win32event.WaitForSingleObject(mutex, 0)
        if status not in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED):
            raise StlOptionsError("StlIsolationUnavailable", "another STL preference transaction owns the mutex")
        held = True
        if status == win32event.WAIT_ABANDONED:
            _POISONED = True
            raise StlOptionsError("StlIsolationUnavailable", "previous STL transaction abandoned unknown global preferences")
        require_isolation(app)
        codes = constants()
        profile = qualify_public_profile(app, options, document_type, codes)
        before = {name: _read(app, name, codes) for name in PREFERENCES}
        wanted = dict(before)
        wanted.update(swSTLQuality=codes["swSTLQuality_Custom"],
                      swExportStlUnits=codes[UNIT_NAMES[options["unit"]]],
                      swSTLDeviation=float(options["deviation_mm"]) / 1000.0,
                      swSTLAngleTolerance=math.radians(options["angle_degrees"]),
                      swSTLBinaryFormat=options["encoding"] == "binary",
                      swSTLComponentsIntoOneFile=True, swSTLShowInfoOnSave=False, swSTLPreview=False)
        evidence.update(execution_mode=_MODE or "internal-calibration",
                        before=before, requested=wanted, constants=codes, mutation_attempted=False,
                        restored=False, cleanup_errors=[], setter_returns=[], setter_snapshots=[])
        if profile is not None:
            evidence["calibrated_profile"] = profile
        # Full-vector compare-and-set before any global preference mutation.
        if {name: _read(app, name, codes) for name in PREFERENCES} != before:
            raise StlOptionsError("ExportPreferenceConflict", "STL preference vector changed before mutation")
        try:
            for name, value in wanted.items():
                evidence["mutation_attempted"] = True
                status = _write(app, name, value, codes)
                evidence["setter_returns"].append({"phase": "set", "preference": name,
                                                   "return_type": type(status).__name__, "value": status})
                evidence["setter_snapshots"].append({"after_preference": name,
                    "values": {field: _read(app, field, codes) for field in PREFERENCES}})
            evidence["readback"] = {name: _read(app, name, codes) for name in PREFERENCES}
            if evidence["readback"] != wanted:
                raise StlOptionsError("ExportPreferenceReadbackFailed", "STL preferences did not retain the exact requested values")
            yield
        finally:
            # Quality first: restoring it may normalize tolerance values. Then
            # restore the original doubles, and verify the full vector at end.
            for name, value in before.items():
                try:
                    status = _write(app, name, value, codes)
                    evidence["setter_returns"].append({"phase": "restore", "preference": name,
                                                       "return_type": type(status).__name__, "value": status})
                except Exception as exc:
                    evidence["cleanup_errors"].append({"preference": name, "error": str(exc)})
            try:
                evidence["after"] = {name: _read(app, name, codes) for name in PREFERENCES}
                evidence["restored"] = evidence["after"] == before and not evidence["cleanup_errors"]
            except Exception as exc:
                evidence["cleanup_errors"].append({"preference": "readback", "error": str(exc)})
            if not evidence["restored"]:
                _POISONED = True
    finally:
        for stage, cleanup in (("mutex-release", lambda: win32event.ReleaseMutex(mutex) if held else None),
                               ("mutex-close", lambda: win32api.CloseHandle(mutex))):
            try:
                cleanup()
            except Exception as exc:
                evidence.setdefault("cleanup_errors", []).append({"preference": stage, "error": str(exc)})
                evidence["restored"] = False
                _POISONED = True
