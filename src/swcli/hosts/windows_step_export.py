"""Scoped STEP preferences; no public COM entry point or uncalibrated writes."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re

from .native_trace import native_call
from .windows import _com_value
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state

STEP_PROTOCOLS = {"ap203": 203, "ap214": 214}
STEP_GEOMETRIES = {
    "solid-surface": "swAcisOutputAsSolidAndSurface",
    "wireframe": "swAcisOutputAs3DCurves",
    "wireframe-sketches": "swAcisOutputAs3DCurves_IncludeSketchEnts",
}
# Filled only after recorded native and public acceptance. Internal calibration
# uses an explicitly scoped capability, never a protocol/environment parameter.
VALIDATED_REVISIONS = frozenset()
_HOST_SCOPE = ContextVar("swcli_step_host_scope", default=None)


class StepExportError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@contextmanager
def step_host_scope(app, *, isolated, calibration=False):
    """Worker-owned capability. Request parameters cannot establish ownership."""
    token = _HOST_SCOPE.set((app, calibration) if isolated else None)
    try:
        yield
    finally:
        _HOST_SCOPE.reset(token)


def read_step_constants(path=None):
    """Resolve symbols from the installed official library, never guessed IDs."""
    import pythoncom
    path = Path(path or r"C:\Program Files\SOLIDWORKS\swconst.tlb")
    if not path.is_file():
        raise StepExportError("StepTypeLibraryUnavailable", "installed swconst.tlb is required")
    wanted = {
        "swUserPreferenceIntegerValue_e": {"swStepAP", "swStepExportPreference"},
        "swAcisOutputGeometryPreference_e": set(STEP_GEOMETRIES.values()),
    }
    found = {}
    library = pythoncom.LoadTypeLib(str(path))
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        names = wanted.get(info.GetDocumentation(-1)[0], set())
        if attributes.typekind != pythoncom.TKIND_ENUM or not names:
            continue
        for offset in range(attributes.cVars):
            descriptor = info.GetVarDesc(offset)
            name = info.GetDocumentation(descriptor[0])[0]
            if name in names:
                if name in found or type(descriptor.value) is not int:
                    raise StepExportError("StepTypeLibraryUnavailable", "ambiguous STEP enum")
                found[name] = descriptor.value
    if set(found) != set().union(*wanted.values()):
        raise StepExportError("StepTypeLibraryUnavailable", "installed STEP enums are incomplete")
    return found


def validate_step_options(output, protocol, geometry):
    if protocol is None and geometry is None:
        return False
    if (not isinstance(protocol, str) or not isinstance(geometry, str)
            or Path(output).suffix.lower() not in (".step", ".stp")
            or protocol not in STEP_PROTOCOLS or geometry not in STEP_GEOMETRIES):
        raise StepExportError("InvalidStepOptions", "STEP/STP requires both a supported protocol and geometry")
    return True


def _snapshot(app, keys):
    values = {}
    for name, key in keys.items():
        value = native_call("step-export", "ISldWorks.GetUserPreferenceIntegerValue." + name,
                            lambda: app.GetUserPreferenceIntegerValue(key))
        if type(value) is not int:
            raise StepExportError("StepPreferenceUnavailable", "STEP preference is unreadable: " + name)
        values[name] = value
    return values


@contextmanager
def step_preferences(app, document, protocol, geometry, result):
    if protocol is None and geometry is None:
        yield
        return
    scope = _HOST_SCOPE.get()
    if scope is None or scope[0] is not app or _com_value(app, "Visible") is not False:
        raise StepExportError("StepIsolationRequired", "STEP options require a daemon-owned invisible host")
    revision = str(_com_value(app, "RevisionNumber"))
    if not scope[1] and revision not in VALIDATED_REVISIONS:
        raise StepExportError("StepCalibrationRequired", "STEP option writes await native/public calibration for this revision")
    _require_writable(document)
    state = _state(document)
    if state[0] != 1:
        raise StepExportError("StepDocumentUnsupported", "STEP options currently support parts only")
    if _com_value(_com_value(document, "SketchManager"), "ActiveSketch") is not None:
        raise StepExportError("StepEditingUnsupported", "finish the active sketch before STEP export")
    foreground = _com_value(app, "ActiveDoc")
    constants = read_step_constants()
    keys = {name: constants[name] for name in ("swStepAP", "swStepExportPreference")}
    before = _snapshot(app, keys)
    desired = {"swStepAP": STEP_PROTOCOLS[protocol],
               "swStepExportPreference": constants[STEP_GEOMETRIES[geometry]]}
    result["step_preferences"] = {"before": before, "requested": desired, "restored": False}
    if (before["swStepAP"] not in STEP_PROTOCOLS.values()
            or before["swStepExportPreference"] not in {constants[name] for name in STEP_GEOMETRIES.values()}):
        raise StepExportError("StepPreferenceUnsupported", "original STEP preferences are outside the safely restorable profile")
    # Compare the entire snapshot immediately before entering the mutation scope.
    _verify_metadata_state(app, document, state, foreground, changed=False)
    if _snapshot(app, keys) != before:
        raise StepExportError("StepPreferenceConflict", "STEP preferences changed before export")
    attempted = []
    business_error = None
    try:
        for name, key in keys.items():
            if before[name] == desired[name]:
                continue
            attempted.append(name)  # Setter can mutate before throwing.
            result["mutation"] = {"attempted": True, "may_have_changed": True}
            accepted = native_call("step-export", "ISldWorks.SetUserPreferenceIntegerValue." + name,
                                  lambda: app.SetUserPreferenceIntegerValue(key, desired[name]))
            if accepted is not True:
                raise StepExportError("StepPreferenceRejected", "STEP preference setter rejected " + name)
            observed = _snapshot(app, keys)
            expected = {**before, **{n: desired[n] for n in attempted}}
            if observed != expected:
                raise StepExportError("StepPreferenceReadbackFailed", "STEP preference did not round-trip")
        _verify_metadata_state(app, document, state, foreground, changed=False)
        yield
        if not result.get("error"):
            _verify_metadata_state(app, document, state, foreground, changed=False)
            if _snapshot(app, keys) != desired:
                raise StepExportError("StepPreferenceReadbackFailed", "STEP preferences changed during native export")
    except BaseException as exc:
        business_error = exc
        raise
    finally:
        failures = []
        for name in reversed(attempted):
            try:
                accepted = native_call("step-export", "ISldWorks.SetUserPreferenceIntegerValue.restore." + name,
                                      lambda: app.SetUserPreferenceIntegerValue(keys[name], before[name]))
                if accepted is not True:
                    raise RuntimeError("restore setter rejected " + name)
            except Exception as exc:
                failures.append({"preference": name, "type": type(exc).__name__, "message": str(exc)})
        try:
            restored = _snapshot(app, keys)
            result["step_preferences"]["after"] = restored
            if restored != before:
                raise RuntimeError("complete STEP preference restore did not round-trip")
        except Exception as exc:
            failures.append({"type": type(exc).__name__, "message": str(exc)})
        if failures:
            result["preference_restore_errors"] = failures
            if business_error is None and not result.get("error"):
                raise StepExportError("StepPreferenceRestoreFailed", "STEP preferences could not be restored; output was not published")
        else:
            result["step_preferences"]["restored"] = True


def verify_step_output(path, protocol, geometry):
    """Check actual Part 21 schema, termination and requested entity family."""
    text = path.read_text(encoding="ascii", errors="strict")
    schema = re.search(r"FILE_SCHEMA\s*\(\s*\((.*?)\)\s*\)\s*;", text, re.S | re.I)
    marker = "CONFIG_CONTROL_DESIGN" if protocol == "ap203" else "AUTOMOTIVE_DESIGN"
    if (not text.startswith("ISO-10303-21;") or not text.rstrip().endswith("END-ISO-10303-21;")
            or schema is None or marker not in schema[1].upper()):
        raise StepExportError("StepOutputMismatch", "STEP file schema does not match the requested protocol")
    entities = set(re.findall(r"#\d+\s*=\s*([A-Z][A-Z0-9_]*)\s*\(", text))
    expected = ({"MANIFOLD_SOLID_BREP", "SHELL_BASED_SURFACE_MODEL"} if geometry == "solid-surface"
                else {"GEOMETRIC_CURVE_SET", "GEOMETRIC_SET", "EDGE_BASED_WIREFRAME_MODEL"})
    if not entities.intersection(expected):
        raise StepExportError("StepOutputMismatch", "STEP file lacks the requested geometry entity family")
    if geometry != "solid-surface" and "MANIFOLD_SOLID_BREP" in entities:
        raise StepExportError("StepOutputMismatch", "wireframe STEP unexpectedly contains solid bodies")
    return {"protocol": protocol, "geometry": geometry, "file_schema": schema[1],
            "entity_types": sorted(entities)}
