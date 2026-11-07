"""Single-configuration, two-component standard mates on the owning COM worker.

The first component must be fixed; the second must float. Never float, suppress,
change configuration, save, retry a failed native write, or roll CAD back here.
"""

import hashlib
import math

from ..assembly_mates import PUBLIC_MATE_WRITES_CALIBRATED, CALIBRATED_WINDOWS_REVISIONS
from .windows import _com_value, _error, _describe_document
from .native_trace import native_call
from .windows_documents import _diagnose_features
from .windows_entity_geometry import _numbers, _direction
from .windows_entity_observation import _geometry
from .windows_entity_references import capture_verified_reference
from .windows_feature_inspection import _same
from .windows_feature_depth import _running_command, _empty_variant

# Official SW API enumerations, checked again from installed swconst.tlb by the
# owned native calibration before it can attempt a write.
KINDS = {"coincident": 0, "concentric": 1}
ALIGNMENTS = {"aligned": 0, "anti-aligned": 1}
DISTANCE_TOLERANCE_MM = 1e-5
DIRECTION_TOLERANCE = 1e-8


class MateError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, message, code="MateObservationUnavailable"):
    if not condition:
        raise MateError(code, message)


def value(native, member):
    return native_call("assembly-mates", member, lambda: _com_value(native, member))


def sequence(raw, label, limit):
    require(raw is None or isinstance(raw, (tuple, list)), label + " is not an array")
    result = list(raw or ())
    require(len(result) <= limit, label + " exceeds the bounded observation limit")
    return result


def integer(raw, label):
    require(type(raw) is int and raw >= 0, label + " is not a nonnegative integer")
    return raw


def boolean(raw, label):
    require(type(raw) is bool, label + " is not a native boolean")
    return raw


def text(raw, label):
    require(isinstance(raw, str) and bool(raw.strip()), label + " is unavailable")
    return raw


def configuration(document):
    names = sequence(value(document, "GetConfigurationNames"), "configurations", 1)
    require(len(names) == 1 and integer(value(document, "GetConfigurationCount"), "configuration count") == 1,
            "first-batch mates require exactly one configuration", "UnsupportedMateScope")
    active = text(value(value(document, "GetActiveConfiguration"), "Name"), "active configuration")
    require(names == [active], "active configuration differs from complete configuration list")
    return active


def guard(app, document, *, write=False):
    require(integer(value(document, "GetType"), "document type") == 2, "mates require an assembly", "UnsupportedDocumentType")
    require(value(value(document, "SketchManager"), "ActiveSketch") is None,
            "finish sketch editing first", "EditInProgress")
    require(_same(app, value(document, "GetEditTarget"), document),
            "finish in-context component editing first", "ComponentEditInProgress")
    root = value(document, "GetEditTargetComponent")
    require(root is None or boolean(value(root, "IsRoot"), "IsRoot"),
            "finish in-context component editing first", "ComponentEditInProgress")
    if write:
        require(_same(app, value(app, "ActiveDoc"), document), "target assembly is not active")
        for member, code in (("IsOpenedReadOnly", "DocumentReadOnly"), ("IsOpenedViewOnly", "DocumentViewOnly")):
            require(not boolean(value(document, member), member), "assembly is not writable", code)
        require(not _running_command(app)["ui_active"], "native command is in progress", "CommandInProgress")
        count = integer(value(document, "SelectionManager").GetSelectedObjectCount2(-1), "selection count")
        require(count == 0, "existing selection is not owned", "SelectionNotEmpty")


def transform(component):
    data = _numbers(value(value(component, "Transform2"), "ArrayData"), 16, "Transform2.ArrayData")
    require(math.isclose(data[12], 1, abs_tol=1e-12, rel_tol=0), "scaled components are unsupported")
    for start in (0, 3, 6):
        _direction(data[start:start + 3], "component rotation")
    rows = [data[i:i + 3] for i in (0, 3, 6)]
    require(all(abs(sum(a * b for a, b in zip(rows[i], rows[j]))) < 1e-10
                for i, j in ((0, 1), (0, 2), (1, 2))), "component rotation is not orthogonal")
    determinant = sum(rows[0][i] * (rows[1][(i+1)%3]*rows[2][(i+2)%3] -
                                  rows[1][(i+2)%3]*rows[2][(i+1)%3]) for i in range(3))
    require(math.isclose(determinant, 1, abs_tol=1e-10, rel_tol=0), "mirrored components are unsupported")
    return data


def mapped_vector(data, vector):
    return [sum(vector[j] * data[j * 3 + i] for j in range(3)) for i in range(3)]


def relation(first, second, kind):
    """Independent infinite-plane / cylinder-axis residuals in assembly mm."""
    points, directions = [], []
    for component, face in (first, second):
        params, matrix = face["parameters"], component["transform"]
        direction, point = (params[:3], params[3:6]) if kind == "coincident" else (params[3:6], params[:3])
        directions.append(mapped_vector(matrix, direction))
        points.append([a * 1000 + matrix[9 + i] * 1000 for i, a in enumerate(mapped_vector(matrix, point))])
    delta = [a - b for a, b in zip(*points)]
    dot = sum(a*b for a, b in zip(*directions))
    parallel = abs(1 - abs(dot))
    axial = sum(a*b for a, b in zip(delta, directions[0]))
    distance = abs(axial) if kind == "coincident" else math.sqrt(sum((delta[i] - axial * directions[0][i])**2 for i in range(3)))
    require(math.isfinite(distance) and math.isfinite(parallel), "mate residual overflowed")
    return dict(distance_mm=distance, parallel_error=parallel)


_INTERFACE_IIDS = {}
_OFFICIAL_LIBRARIES = {}


def _official_library(app):
    """Load the installed library beside this exact COM host's executable.

    Even an Automation object may legally report zero type-info entries. The
    host PID and OS process handle identify the owning installation; this never
    searches another installation or guesses a type-library GUID/IID.
    """
    from pathlib import Path
    import pythoncom
    import win32api
    import win32con
    import win32process
    pid = integer(value(app, "GetProcessID"), "host process ID")
    require(pid > 0, "native host process ID is unavailable")
    handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
    try:
        executable = Path(win32process.GetModuleFileNameEx(handle, 0))
    finally:
        handle.Close()
    require(executable.name.casefold() == "sldworks.exe", "host process image is not SOLIDWORKS")
    path = executable.with_name("sldworks.tlb")
    require(path.is_file(), "owning installation's official sldworks.tlb is unavailable")
    stat = path.stat()
    key = (pid, str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _OFFICIAL_LIBRARIES:
        _OFFICIAL_LIBRARIES[key] = native_call("assembly-mates", "LoadTypeLib(owning-installation)",
                                               lambda: pythoncom.LoadTypeLib(str(path)))
    return _OFFICIAL_LIBRARIES[key]


def _dispatch(native, interface, *, app):
    """Query the exact dual interface from this host installation's official library.

    A returned IDispatch can expose IEntity or IMateFeatureData rather than its
    face/mate-specific interface. Never infer additional members from a Python
    wrapper, or invent an IID when the installed official library lacks it.
    """
    import pythoncom
    from win32com.client import Dispatch
    # Load by exact owning installation, without GetTypeInfo on either a face
    # object or the application. Nested dispatch need not be self describing.
    library = _official_library(app)
    attributes = library.GetLibAttr()
    key = (str(attributes[0]), attributes[3], attributes[4], interface)
    if key not in _INTERFACE_IIDS:
        matches = []
        for index in range(library.GetTypeInfoCount()):
            info = native_call("assembly-mates", "TypeLib.GetTypeInfo", lambda: library.GetTypeInfo(index))
            if info.GetDocumentation(-1)[0] == interface:
                attr = info.GetTypeAttr()
                require(attr.typekind == pythoncom.TKIND_DISPATCH, "required interface is not Automation dispatch: " + interface)
                matches.append(attr.iid)
        require(len(matches) == 1, "official type library does not identify exactly one " + interface)
        _INTERFACE_IIDS[key] = matches[0]
    queried = native_call("assembly-mates", "QueryInterface." + interface,
                          lambda: native._oleobj_.QueryInterface(_INTERFACE_IIDS[key], pythoncom.IID_IDispatch))
    return Dispatch(queried)


def _face(app, assembly, source, component, native, index):
    entity = _dispatch(native, "IEntity", app=app)
    mapped = native_call(
        "assembly-mates",
        "Component2.GetCorrespondingEntity",
        lambda: component.GetCorrespondingEntity(entity),
    )
    require(mapped is not None, "native corresponding face is absent")
    mapped = _dispatch(mapped, "IFace2", app=app)
    owner = value(_dispatch(mapped, "IEntity", app=app), "GetComponent")
    require(owner is not None, "mapped face has no component in the selected assembly context")
    require(_same(app, owner, component), "mapped face does not belong to the exact component")
    original = _geometry(native)
    require(original["surface_kind"] in ("plane", "cylinder"), "only plane/cylinder fixtures are supported", "UnsupportedMateScope")
    require(_geometry(mapped) == original, "assembly-context face differs from the part geometry", "UnsupportedMateScope")
    surface = value(native, "GetSurface")
    kind = original["surface_kind"]
    params = _numbers(value(surface, "PlaneParams" if kind == "plane" else "CylinderParams"),
                      6 if kind == "plane" else 7, "surface parameters")
    reference = capture_verified_reference(app, value(assembly, "Extension"), mapped)
    return dict(index=index, surface_kind=kind, parameters=params,
                area_mm2=original["area_mm2"], sense=boolean(value(native, "FaceInSurfaceSense"), "face sense"),
                reference_sha256=hashlib.sha256(reference).hexdigest()), mapped


def _saved_external_part(path):
    from pathlib import Path
    source = Path(path)
    return source.suffix.casefold() == ".sldprt" and source.is_file() and source.stat().st_size > 0


def _component(app, assembly, component):
    source = value(component, "GetModelDoc2")
    require(source is not None and integer(value(source, "GetType"), "source document type") == 1, "component must be a loaded part", "UnsupportedMateScope")
    require(not boolean(value(component, "IsVirtual"), "component virtual flag"),
            "virtual components are outside the first-batch scope", "UnsupportedMateScope")
    state = integer(value(component, "GetSuppression2"), "component suppression")
    require(state in (2, 3), "component must be fully resolved", "ComponentSuppressedOrLightweight")
    cfg = text(value(component, "ReferencedConfiguration"), "component configuration")
    require(cfg == configuration(source), "loaded part configuration differs from component reference", "ConfigurationConflict")
    source_stamp = integer(value(source, "GetUpdateStamp"), "source update stamp")
    modified = boolean(value(source, "GetSaveFlag"), "source modified flag")
    require(not modified, "component part has unsaved modifications", "ComponentModified")
    require(value(value(source, "SketchManager"), "ActiveSketch") is None, "component sketch is being edited", "EditInProgress")
    path = text(value(component, "GetPathName"), "component path")
    require(_saved_external_part(path), "component must reference a nonempty saved external PRT",
            "ComponentFileUnavailable")
    require(path.casefold() == text(value(source, "GetPathName"), "source path").casefold(), "component source path differs")
    bodies = sequence(source.GetBodies2(0, False), "solid bodies", 1)
    require(len(bodies) == 1, "component must contain exactly one solid body", "UnsupportedMateScope")
    faces = sequence(value(bodies[0], "GetFaces"), "faces", 64)
    require(0 < len(faces) == integer(value(bodies[0], "GetFaceCount"), "face count"), "face traversal is incomplete")
    observed, bindings = [], []
    for index, native in enumerate(faces):
        require(_same(app, value(native, "GetBody"), bodies[0]), "face belongs to another body")
        row, mapped = _face(app, assembly, source, component, native, index)
        require(not any(_same(app, mapped, previous) for previous in bindings), "face traversal repeats native identity")
        require(row["reference_sha256"] not in {r["reference_sha256"] for r in observed}, "ambiguous face references")
        observed.append(row)
        bindings.append(mapped)
    require(source_stamp == value(source, "GetUpdateStamp") and value(source, "GetSaveFlag") is False,
            "part changed during face observation")
    row = dict(name=text(value(component, "Name2"), "component name"), path=path, configuration=cfg,
        native_id=integer(value(component, "GetID"), "component ID"), fixed=boolean(value(component, "IsFixed"), "fixed flag"),
        suppression=state, source_update_stamp=source_stamp, source_modified=modified,
        transform=transform(component), faces=observed)
    return row, bindings


def mate_features(document):
    """Only the first-batch standard mates in the native MateGroup folder."""
    feature, seen, mates = value(document, "FirstFeature"), set(), []
    while feature is not None:
        name = text(value(feature, "Name"), "feature name")
        require(name not in seen and len(seen) < 128, "feature traversal repeats or exceeds limit")
        seen.add(name)
        if value(feature, "GetTypeName2") == "MateGroup":
            sub = value(feature, "GetFirstSubFeature")
            while sub is not None:
                subname = text(value(sub, "Name"), "mate feature name")
                require(subname not in seen and len(mates) < 16, "mate traversal repeats or exceeds limit")
                seen.add(subname)
                require(value(sub, "GetTypeName2") in ("MateCoincident", "MateConcentric"),
                        "assembly contains a mate outside the first-batch scope", "UnsupportedMateScope")
                mates.append(sub)
                sub = value(sub, "GetNextSubFeature")
        feature = value(feature, "GetNextFeature")
    return mates


def feature_error(feature):
    import pythoncom
    from win32com.client import VARIANT
    warning = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, True)
    code = feature.GetErrorCode2(warning)
    return integer(code, "mate feature error code")


def observe_mate(app, document, feature, components, natives, bindings):
    mate = value(feature, "GetSpecificFeature2")
    require(mate is not None, "mate feature has no native IMate2")
    mate = _dispatch(mate, "IMate2", app=app)
    kind = integer(value(mate, "Type"), "mate type")
    alignment = integer(value(mate, "Alignment"), "mate alignment")
    require(kind in KINDS.values() and alignment in ALIGNMENTS.values(), "unsupported native mate definition")
    require(value(mate, "GetMateEntityCount") == 2, "mate must have exactly two entities")
    matches = []
    for i in range(2):
        entity = _dispatch(mate.MateEntity(i), "IMateEntity2", app=app)
        owner, reference = value(entity, "ReferenceComponent"), value(entity, "Reference")
        found = [(c, f) for c in range(2) for f in range(len(bindings[c]))
                 if _same(app, owner, natives[c]) and _same(app, reference, bindings[c][f])]
        require(len(found) == 1, "mate reference differs from bounded exact face identities")
        matches.append(found[0])
    require({c for c, _ in matches} == {0, 1}, "mate does not connect the two expected components")
    kind_name = next(key for key, code in KINDS.items() if code == kind)
    require(all(components[c]["faces"][f]["surface_kind"] == ("plane" if kind_name == "coincident" else "cylinder")
                for c, f in matches), "mate surface class differs")
    suppression = sequence(feature.IsSuppressed2(1, _empty_variant()), "mate suppression", 1)
    require(len(suppression) == 1 and type(suppression[0]) is bool, "mate suppression is unreadable")
    observed = dict(name=text(value(feature, "Name"), "mate name"), kind=kind_name,
        alignment=next(key for key, code in ALIGNMENTS.items() if code == alignment),
        error_code=feature_error(feature), suppressed=suppression[0],
        components=[components[c]["name"] for c, _ in matches],
        references=[components[c]["faces"][f]["reference_sha256"] for c, f in matches],
        **relation(*[(components[c], components[c]["faces"][f]) for c, f in matches], kind_name))
    if kind_name == "concentric":
        definition = _dispatch(value(feature, "GetDefinition"), "IConcentricMateFeatureData", app=app)
        observed["lock_rotation"] = boolean(value(definition, "LockRotation"), "concentric LockRotation")
    return observed


def snapshot(app, document, names):
    guard(app, document)
    require(isinstance(names, (list, tuple)) and len(names) == 2 and len(set(names)) == 2,
            "two distinct component names are required", "InvalidArgument")
    stamp = integer(value(document, "GetUpdateStamp"), "assembly update stamp")
    modified = boolean(value(document, "GetSaveFlag"), "assembly modified flag")
    cfg = configuration(document)
    natives = sequence(document.GetComponents(True), "top-level components", 2)
    require(integer(document.GetComponentCount(True), "top-level component count") == len(natives),
            "top-level component array is incomplete")
    require(len(natives) == 2, "first-batch mates require exactly two top-level components", "UnsupportedMateScope")
    ordered = []
    for name in names:
        matches = [c for c in natives if value(c, "Name2") == name]
        require(len(matches) == 1, "component does not belong uniquely to the selected assembly", "ComponentNotFound")
        ordered.append(matches[0])
    require(not _same(app, *ordered), "component names alias the same native object")
    components, bindings = [], []
    for native in ordered:
        row, faces = _component(app, document, native)
        components.append(row)
        bindings.append(faces)
    require(components[0]["fixed"] and not components[1]["fixed"],
            "first target must be fixed and second floating; no implicit float/fix", "ComponentFixedStateConflict")
    mates = [observe_mate(app, document, f, components, ordered, bindings) for f in mate_features(document)]
    require(stamp == value(document, "GetUpdateStamp") and modified is value(document, "GetSaveFlag")
            and cfg == configuration(document), "assembly changed during observation", "MateObservationChanged")
    return dict(title=text(value(document, "GetTitle"), "assembly title"), path=value(document, "GetPathName"),
        configuration=cfg, update_stamp=stamp, modified=modified, components=components, mates=mates), ordered, bindings


def read_mate_targets_windows(*, app, document, components):
    result = dict(ok=False, action="assembly.mate-targets")
    try:
        foreground = value(app, "ActiveDoc")
        result["snapshot"] = snapshot(app, document, components)[0]
        require(_same(app, foreground, value(app, "ActiveDoc")),
                "foreground document changed during mate target observation", "MateObservationChanged")
        result["document"] = _describe_document(document)
        result["ok"] = True
    except Exception as exc:
        result["error"] = dict(type=getattr(exc, "code", type(exc).__name__), message=str(exc))
        if not isinstance(exc, MateError):
            import traceback
            result["error"]["traceback"] = traceback.format_exc()
    return result


def _native_windows():
    import ctypes
    import sys
    if sys.platform != "win32":
        return False
    # Failure to load ntdll propagates and refuses writing. Unlike tray display,
    # an unavailable runtime probe must not default to calibrated native Windows.
    return getattr(ctypes.WinDLL("ntdll"), "wine_get_version", None) is None


def add_mate_windows(*, app, document, kind, alignment, targets, expected_value, _calibration=False):
    result = dict(ok=False, action="assembly.add-mate",
                  mutation=dict(attempted=False, creation_returned=False, may_have_changed=False), cleanup_errors=[])
    try:
        require(_calibration or PUBLIC_MATE_WRITES_CALIBRATED,
                "standard mate writes await native persistence and independent public acceptance",
                "MateWriteNotCalibrated")
        if not _calibration:
            require(_native_windows(), "standard mate writes are calibrated only on native Windows",
                    "MateRuntimeNotCalibrated")
            revision = value(app, "RevisionNumber")
            require(isinstance(revision, str) and revision in CALIBRATED_WINDOWS_REVISIONS,
                    "standard mate writes are not calibrated for this exact native revision",
                    "MateRuntimeNotCalibrated")
        require(kind in KINDS and alignment in ALIGNMENTS, "unsupported standard mate", "InvalidArgument")
        require(isinstance(targets, list) and len(targets) == 2, "exactly two targets required", "InvalidArgument")
        guard(app, document, write=True)
        before, natives, bindings = snapshot(app, document, [t["component"] for t in targets])
        result["before"] = before
        require(before == expected_value, "complete mate target snapshot changed", "MateValueConflict")
        existing = before["mates"]
        require(not existing or (len(existing) == 1 and existing[0]["kind"] == "coincident"
                and existing[0]["alignment"] == "aligned" and kind == "concentric" and alignment == "aligned"),
                "first batch supports a first mate, or aligned concentric after one aligned coincident",
                "UnsupportedMateScope")
        faces = []
        for c, target in enumerate(targets):
            i = target["face_index"]
            require(type(i) is int and 0 <= i < len(bindings[c]), "face index is outside the complete snapshot", "MateTargetNotFound")
            require(before["components"][c]["faces"][i]["surface_kind"] == ("plane" if kind == "coincident" else "cylinder"),
                    "target surface does not match requested mate", "MateSurfaceMismatch")
            faces.append(bindings[c][i])
        require(all(m["error_code"] == 0 and not m["suppressed"] and not m.get("lock_rotation", False) and
                    m["distance_mm"] <= DISTANCE_TOLERANCE_MM and m["parallel_error"] <= DIRECTION_TOLERANCE
                    for m in before["mates"]), "existing mate is not healthy", "MateSolveFailed")
        result["diagnostics_before"] = native_call("assembly-mates", "Assembly.root-diagnostics.before",
                                                   lambda: _diagnose_features(document, 128))
        require(result["diagnostics_before"]["healthy"] and not result["diagnostics_before"]["truncated"]
                and result["diagnostics_before"]["scanned_feature_count"] > 0,
                "assembly root feature diagnostics are not healthy", "MateSolveFailed")
        data = native_call("assembly-mates", "AssemblyDoc.CreateMateData", lambda: document.CreateMateData(KINDS[kind]))
        require(data is not None, "native mate definition is absent", "MateCreationFailed")
        data = _dispatch(data, "ICoincidentMateFeatureData" if kind == "coincident" else "IConcentricMateFeatureData", app=app)
        import pythoncom
        from win32com.client import VARIANT
        data.EntitiesToMate = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, faces)
        data.MateAlignment = ALIGNMENTS[alignment]
        if kind == "concentric":
            data.LockRotation = False
            require(value(data, "LockRotation") is False, "native lock rotation differs")
        require(value(data, "MateAlignment") == ALIGNMENTS[alignment], "native staged alignment differs")
        staged = sequence(value(data, "EntitiesToMate"), "staged mate entities", 2)
        require(len(staged) == 2 and all(_same(app, a, b) for a, b in zip(staged, faces)), "native staged entities differ")
        # Recheck full CAS immediately before the only mutating call.
        require(snapshot(app, document, [t["component"] for t in targets])[0] == before,
                "assembly changed before commit", "MateValueConflict")
        result["mutation"].update(attempted=True, may_have_changed=True)
        feature = native_call("assembly-mates", "AssemblyDoc.CreateMate", lambda: document.CreateMate(data))
        require(feature is not None, "CreateMate returned null; assembly may be modified", "MateCreationFailed")
        result["mutation"]["creation_returned"] = True
        require(native_call("assembly-mates", "ModelDoc2.EditRebuild3", lambda: value(document, "EditRebuild3")) is True,
                "native rebuild failed", "MateSolveFailed")
        after, after_natives, after_bindings = snapshot(app, document, [t["component"] for t in targets])
        result["snapshot"] = after
        made = observe_mate(app, document, feature, after["components"], after_natives, after_bindings)
        result["mate"] = made
        require(len(after["mates"]) == len(before["mates"]) + 1 and sum(m == made for m in after["mates"]) == 1,
                "native mate tree count or created feature differs", "MateVerificationFailed")
        require(made["kind"] == kind and made["alignment"] == alignment and
                made["references"] == [before["components"][c]["faces"][t["face_index"]]["reference_sha256"]
                                       for c, t in enumerate(targets)],
                "created mate definition differs from request", "MateVerificationFailed")
        require(all(after[key] == before[key] for key in ("title", "path", "configuration")),
                "assembly identity or configuration changed", "MateVerificationFailed")
        def definitions(rows):
            return [{key: value for key, value in row.items()
                     if key not in ("distance_mm", "parallel_error")} for row in rows]
        existing = [mate for mate in after["mates"] if mate["name"] != made["name"]]
        require(definitions(existing) == definitions(before["mates"]),
                "existing mate definitions changed", "MateVerificationFailed")
        require(after["components"][0] == before["components"][0], "fixed anchor changed", "MateVerificationFailed")
        for c in range(2):
            require({k:v for k,v in after["components"][c].items() if k != "transform"} ==
                    {k:v for k,v in before["components"][c].items() if k != "transform"},
                    "component identity, configuration or source geometry changed", "MateVerificationFailed")
        require(all(m["error_code"] == 0 and not m["suppressed"] and not m.get("lock_rotation", False) and m["distance_mm"] <= DISTANCE_TOLERANCE_MM
                    and m["parallel_error"] <= DIRECTION_TOLERANCE for m in after["mates"]),
                "mate solve/geometry verification failed", "MateSolveFailed")
        result["diagnostics"] = native_call("assembly-mates", "Assembly.root-diagnostics.after",
                                            lambda: _diagnose_features(document, 128))
        require(result["diagnostics"]["healthy"] and not result["diagnostics"]["truncated"]
                and result["diagnostics"]["scanned_feature_count"] > 0,
                "assembly root feature diagnostics failed after mating", "MateSolveFailed")
        require(value(value(document, "Extension"), "NeedsRebuild2") == 0, "assembly still needs rebuild", "MateSolveFailed")
        result["document"] = _describe_document(document)
        result["ok"] = True
    except Exception as exc:
        result["error"] = {**_error(exc), "type": getattr(exc, "code", type(exc).__name__)}
        if not isinstance(exc, MateError):
            import traceback
            result["error"]["traceback"] = traceback.format_exc()
    finally:
        if result["mutation"]["attempted"]:
            try:
                selection = value(document, "SelectionManager")
                count = integer(selection.GetSelectedObjectCount2(-1), "post-mate selection count")
                if count:
                    native_call("assembly-mates", "ModelDoc2.ClearSelection2", lambda: document.ClearSelection2(True))
                    require(selection.GetSelectedObjectCount2(-1) == 0, "owned mate selection cleanup failed")
            except Exception as exc:
                result["cleanup_errors"].append(dict(stage="owned-selection-cleanup", error=str(exc)))
                result["ok"] = False
                result.setdefault("error", dict(type="MateCleanupFailed", message=str(exc)))
    return result
