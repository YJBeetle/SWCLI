"""Opt-in owned native topology calibration. Not public acceptance evidence.

Generated single-body fixtures only; exact APIs/type libraries, no retry,
preference changes, arbitrary model edits, or host replacement between cases.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import threading

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_documents import open_windows_document_with_handle, save_active_windows_document
from swcli.hosts.windows_entity_references import _resolve_native
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle, create_circle_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.result_schemas import validate_operation_result
from swcli.topology_references import decode_reference, _unb64

spec = importlib.util.spec_from_file_location("_topology_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked
NATIVE_TIMEOUT = 600
TYPE_LIBRARY_PATH = None
ENUMS = {"swPersistReferencedObject_Ok": 0, "swPersistReferencedObject_Invalid": 1,
         "swPersistReferencedObject_Suppressed": 2, "swPersistReferencedObject_Deleted": 4,
         "swDelete_Absorbed": 2, "swEndCondBlind": 0, "swEndCondThroughAll": 1,
         "swThisConfiguration": 1}


def read_constants(pythoncom, path):
    library = pythoncom.LoadTypeLib(str(path))
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attributes.cVars):
            descriptor = info.GetVarDesc(offset)
            name = info.GetDocumentation(descriptor[0])[0]
            if name in ENUMS:
                checked(name not in found, "duplicate enum in official swconst")
                found[name] = descriptor.value
    checked(found == ENUMS, "official swconst differs from documented reference/deletion enums: " + repr(found))
    return found


def type_library_evidence(path):
    import pythoncom
    # Load the official installed file directly. SOLIDWORKS' running IDispatch
    # can expose no ITypeInfo; this is not a failed-CAD-call fallback/retry.
    path = Path(path)
    library = pythoncom.LoadTypeLib(str(path))
    wanted = {"GetPersistReference3": 1, "GetObjectByPersistReference3": 2, "DeleteSelection2": 1}
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        if info.GetDocumentation(-1)[0] != "IModelDocExtension":
            continue
        for offset in range(info.GetTypeAttr().cFuncs):
            descriptor = info.GetFuncDesc(offset)
            names = tuple(info.GetNames(descriptor[0]))
            if names and names[0] in wanted:
                found[names[0]] = {"names": names, "descriptor": repr(tuple(descriptor)),
                                   "argument_count": len(descriptor[2])}
    checked(set(found) == set(wanted) and all(found[name]["argument_count"] == count
            for name, count in wanted.items()), "official IModelDocExtension signatures differ: " + repr(found))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "library": library.GetDocumentation(-1), "attributes": repr(tuple(library.GetLibAttr())),
            "methods": found}


def save_owned_document(app, document):
    """Keep the existing host/STA; never enter the helper's ROT/COM owner path."""
    return save_active_windows_document(app=app, document=document)


def verify_deleted_fixture_state(entity, status, constants):
    """Exact SW2025 SP5 owned-hole observation, not a generic nonzero allowance.

    Run 42273663491 observed Invalid=1/NULL after deleting the generated cut.
    It did not observe the Deleted=4 native enumerator; do not claim that state.
    """
    checked(type(status) is int and status == constants["swPersistReferencedObject_Invalid"]
            and entity is None, "deleted owned cylinder must read back exact Invalid=1 and NULL")


def notch_split_faces(faces):
    """Identify the generated box's original +Y plane, excluding the notch back.

    Both the original y=15 side and the notch's y=9 back face have +Y normals.
    Plane offset identifies the owned fixture side; it never resolves a stored
    reference or substitutes geometry for native identity.
    """
    matches = []
    for face in faces:
        if face["surface_kind"] != "plane":
            continue
        plane = face["surface_geometry"]["plane"]
        if (all(abs(a - b) < 1e-9 for a, b in zip(plane["outward_normal"], (0, 1, 0)))
                and abs(plane["point_mm"][1] - 15) < 1e-5):
            matches.append(face)
    checked(len(matches) == 2, "notch must split the positive-Y side into exactly two faces")
    checked(all(abs(face["area_mm2"] - 170) < 1e-5 for face in matches),
            "notch split side faces must each retain 170 mm2")
    return matches


def calibrate_case(app, output, constants, plane, reverse, original_call, case, report, live, *, profile_kind):
    def call(name, function):
        # A hung native call leaves the flushed original harness report/trace.
        # This process exits once; no retry or replacement host is started.
        timer = threading.Timer(NATIVE_TIMEOUT, lambda: os._exit(124))
        timer.daemon = True; timer.start()
        try:
            return original_call(name, function)
        finally:
            timer.cancel()
    case.update(profile_kind=profile_kind, success=False, native_timeout_seconds=600)
    if "type_library" not in report:
        report["type_library"] = call("read-official-api-signatures", lambda: type_library_evidence(TYPE_LIBRARY_PATH))
    made, document = call("create-part", lambda: create_part_windows_with_handle(app=app))
    live["document"] = document
    checked(made["ok"] and document is not None, "part creation failed")
    rectangle, sketch = call("create-base-sketch", lambda: create_rectangle_sketch_windows_with_handle(
        app=app, document=document, plane="front", width_mm=40, height_mm=30))
    checked(rectangle["ok"], "base profile failed")
    boss_result, boss = call("create-base-boss", lambda: extrude_sketch_windows_with_handle(
        app=app, document=document, sketch_feature=sketch, depth_mm=10))
    checked(boss_result["ok"] and boss is not None, "base extrusion failed")
    path = output / (profile_kind + ".SLDPRT")
    case["save_initial"] = call("save-initial-part", lambda: save_as_native_windows(str(path), document=document))
    checked(case["save_initial"]["ok"], "initial native save failed")
    registry = DocumentRegistry(app)
    entry = registry.register(document)

    def operation(name, values, *, good=True):
        result = call(name, lambda: execute_operation(app, name, values, documents=registry,
                      document_id=entry.document_id, session_id="topology-calibration"))
        case.setdefault("operations", []).append(result)
        validate_operation_result(name, result)
        checked(result["ok"] is good, "unexpected topology operation result: " + str(result))
        return result

    references = {}
    for kind in ("face", "edge"):
        listed = operation("entity.list", {"kind": kind})
        # Enumeration ordinal is only used to choose an arbitrary fixture entity,
        # never to resolve it again. Persistent identity proves each subsequent use.
        captured = operation("entity.reference-create", {"kind": kind,
                              "entity_id": listed["entities"][0]["entity_id"]})
        references[kind] = captured["reference"]
        operation("entity.reference-resolve", {"reference": references[kind]})
    checked(call("rebuild-unchanged-fixture", lambda: _com_value(document, "EditRebuild3")), "rebuild failed")
    for ref in references.values():
        operation("entity.reference-resolve", {"reference": ref})
    case["save_before_reopen"] = call("save-before-reopen", lambda: save_owned_document(app, document))
    checked(case["save_before_reopen"]["ok"], "save before reopen failed")
    before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    title = _com_value(document, "GetTitle")
    boss = sketch = None
    registry.forget(entry.document_id)
    document = live["document"] = None
    call("close-before-reopen", lambda: app.CloseDoc(title))
    opened, document = call("reopen-native-file", lambda: open_windows_document_with_handle(str(path), app=app))
    live["document"] = document
    case["reopen"] = opened
    checked(opened["ok"] and opened["api_errors"] == 0, "native reopen failed")
    registry = DocumentRegistry(app); entry = registry.register(document)
    for ref in references.values():
        operation("entity.reference-resolve", {"reference": ref})
    checked(hashlib.sha256(path.read_bytes()).hexdigest() == before_hash and not _com_value(document, "GetSaveFlag"),
            "reference reads changed saved file or modified flag")
    case["initial_file_sha256"] = before_hash
    # Hole creates a deletable cylindrical face. Notch splits the positive-Y
    # planar side into two faces while retaining exactly one solid body.
    if profile_kind == "hole":
        profile_result, profile = call("create-hole-profile", lambda: create_circle_sketch_windows_with_handle(
            app=app, document=document, plane="front", radius_mm=3))
    else:
        profile_result, profile = call("create-notch-profile", lambda: create_rectangle_sketch_windows_with_handle(
            app=app, document=document, plane="front", width_mm=6, height_mm=12, center_y_mm=15))
    checked(profile_result["ok"] and profile is not None, "cut profile creation failed")
    cut = harness.create_cut(document, profile, constants, False, call, report)
    checked(call("rebuild-topology-mutation", lambda: _com_value(document, "EditRebuild3")), "cut rebuild failed")
    measure = call("measure-cut", lambda: measure_part_windows(document=document))
    case["mutated_metrics"] = measure
    checked(measure["ok"] and measure["metrics"]["solid_body_count"] == 1, "cut must retain one solid")
    expected = (40 * 30 - (3.141592653589793 * 3**2 if profile_kind == "hole" else 36)) * 10
    checked(abs(measure["metrics"]["volume_mm3"] - expected) < 1e-5, "actual cut output volume differs")
    rejected = operation("entity.reference-resolve", {"reference": references["face"]}, good=False)
    checked(rejected["error"]["type"] in ("PersistentReferenceTopologyChanged", "PersistentReferenceNativeState"),
            "topology mutation did not fail through exact identity checks")
    listed = operation("entity.list", {"kind": "face"})
    if profile_kind == "hole":
        candidates = [face for face in listed["entities"] if face["surface_kind"] == "cylinder"]
        checked(len(candidates) == 1, "hole requires one exact cylindrical face")
    else:
        candidates = notch_split_faces(listed["entities"])
    mutated = [operation("entity.reference-create", {"kind": "face", "entity_id": face["entity_id"]})
               for face in candidates]
    saved = call("save-mutated-content", lambda: save_owned_document(app, document))
    checked(saved["ok"], "mutated native content save failed")
    copy = output / (profile_kind + "-mutated-content.SLDPRT")
    shutil.copyfile(path, copy)
    case["mutated_file_sha256"] = hashlib.sha256(copy.read_bytes()).hexdigest()
    if profile_kind == "hole":
        payload = decode_reference(mutated[0]["reference"])
        raw = _unb64(payload["faces"][payload["target_index"]])
        before_entity, before_status = call("read-cylinder-native-state-before-deletion",
            lambda: _resolve_native(_com_value(document, "Extension"), raw))
        case["predelete_native_state"] = {"status": before_status, "object_present": before_entity is not None}
        checked(type(before_status) is int and before_status == constants["swPersistReferencedObject_Ok"]
                and before_entity is not None, "saved cylinder reference was not OK before deletion")
        # Verify the same native reference is still live after saving, before the
        # one owned deletion. Invalid bytes alone would not prove invalidation.
        before_list = operation("entity.list", {"kind": "face"})
        before_candidates = [face for face in before_list["entities"] if face["surface_kind"] == "cylinder"]
        checked(len(before_candidates) == 1, "saved fixture lost its unique cylinder before deletion")
        before_binding = entry.entities.resolve(before_candidates[0]["entity_id"], kind="face",
            configuration=before_list["observation"]["after"]["configuration"],
            update_stamp=before_list["observation"]["after"]["update_stamp"])
        identity = call("verify-cylinder-native-identity-before-deletion",
            lambda: app.IsSame(before_entity, before_binding.binding.face))
        case["predelete_native_state"] = {"status": before_status,
            "object_present": before_entity is not None, "identity_same": identity}
        checked(type(before_status) is int and before_status == constants["swPersistReferencedObject_Ok"]
                and before_entity is not None and type(identity) is int and identity == 1,
                "saved cylinder reference was not exact OK before deletion")
    checked(call("select-owned-cut-for-deletion", lambda: cut.Select2(False, 0)), "owned cut selection failed")
    case["mutation"] = {"attempted": True, "may_have_changed": True}
    checked(call("delete-owned-cut-and-profile", lambda: _com_value(document, "Extension").DeleteSelection2(
        constants["swDelete_Absorbed"])), "native cut deletion failed; no retry")
    document.ClearSelection2(True)
    checked(call("rebuild-merged-topology", lambda: _com_value(document, "EditRebuild3")), "delete rebuild failed")
    if profile_kind == "hole":
        payload = decode_reference(mutated[0]["reference"])
        raw = _unb64(payload["faces"][payload["target_index"]])
        resolved, status = call("read-deleted-cylinder-native-state", lambda: _resolve_native(_com_value(document, "Extension"), raw))
        case["deleted_native_state"] = {"status": status, "object_present": resolved is not None,
            "native_state_name": "swPersistReferencedObject_Invalid"}
        verify_deleted_fixture_state(resolved, status, constants)
        report["unobserved_native_states"] = ["swPersistReferencedObject_Deleted", "swPersistReferencedObject_Suppressed"]
    for ref in mutated:
        operation("entity.reference-resolve", {"reference": ref["reference"]}, good=False)
    measure = call("measure-merged-box", lambda: measure_part_windows(document=document))
    case["merged_metrics"] = measure
    checked(measure["ok"] and measure["metrics"]["solid_body_count"] == 1
            and abs(measure["metrics"]["volume_mm3"] - 12000) < 1e-5, "deleted cut did not restore actual box content")
    saved = call("save-deleted-content", lambda: save_owned_document(app, document))
    checked(saved["ok"], "deleted native content save failed")
    title = _com_value(document, "GetTitle")
    cut = profile = None
    registry.forget(entry.document_id)
    document = live["document"] = None
    call("close-merged-file", lambda: app.CloseDoc(title))
    opened, document = call("reopen-merged-file-readonly", lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
    live["document"] = document
    checked(opened["ok"] and opened["api_errors"] == 0, "merged file reopen failed")
    registry = DocumentRegistry(app); entry = registry.register(document)
    for ref in mutated:
        operation("entity.reference-resolve", {"reference": ref["reference"]}, good=False)
    measured = call("measure-reopened-merged-file", lambda: measure_part_windows(document=document))
    case["reopened_metrics"] = measured
    checked(measured["ok"] and abs(measured["metrics"]["volume_mm3"] - 12000) < 1e-5,
            "reopened actual output content differs")
    checked(not _com_value(document, "GetSaveFlag"), "readonly reference checks modified reopened output")
    case["final_file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    call("close-case", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = None
    checked(_com_value(app, "GetDocumentCount") == 0, "calibration leaked documents")
    case["success"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--sldworks", type=Path, help="official sldworks.tlb; defaults to swconst.tlb sibling")
    args = parser.parse_args(argv)
    checked(args.swconst.is_file(), "official swconst type library is required")
    sldworks = args.sldworks or args.swconst.with_name("sldworks.tlb")
    checked(sldworks.is_file(), "official installed sldworks.tlb is required")
    global TYPE_LIBRARY_PATH
    TYPE_LIBRARY_PATH = sldworks.resolve()
    args.output_dir.mkdir()
    harness.read_constants = read_constants
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False,
        case_runner=calibrate_case, case_plan=[("hole", "front", False), ("notch", "front", False)],
        diagnostic_case="topology-references-internal-calibration")


if __name__ == "__main__":
    raise SystemExit(main())
