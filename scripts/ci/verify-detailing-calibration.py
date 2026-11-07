"""Internal drawing-default calibration. No public acceptance or retry eligibility."""

import argparse
import hashlib
import importlib.util
from pathlib import Path

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation
from swcli.document_detailing import DETAILING_FIELDS
from swcli.hosts.windows import _com_value
from swcli.hosts import windows_document_detailing as adapter
from swcli.hosts.windows_custom_properties import _state
from swcli.hosts.windows_document_annotations import read_document_annotation_options_windows
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_drawings import create_drawing_windows_with_handle, _dispatch
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location("_detailing_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked


def layout(document):
    sheets = _com_value(document, "GetSheetNames")
    views = _com_value(document, "GetViews")
    checked(isinstance(sheets, (tuple, list)) and len(sheets) == 1, "fixture must retain one sheet")
    checked(isinstance(views, (tuple, list)) and len(views) == 1, "fixture sheet views are unavailable")
    checked(isinstance(views[0], (tuple, list)) and len(views[0]) == 1, "fixture acquired model views")
    sheet = _com_value(document, "GetCurrentSheet")
    properties = _com_value(sheet, "GetProperties2")
    checked(isinstance(properties, (tuple, list)) and len(properties) == 8, "sheet properties unavailable")
    return {"sheets": list(sheets), "view_names": [_com_value(_dispatch(view), "GetName2") for view in views[0]],
            "view_models": [_com_value(_dispatch(view), "GetReferencedModelName") for view in views[0]],
            "sheet_properties": list(properties)}


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind, template):
    made, document = call("create-detailing-drawing", lambda: create_drawing_windows_with_handle(
        app=app, template=str(template), projection="first-angle"))
    live["document"] = document
    case.update(creation=made, internal_calibration=True, public_acceptance=False, writes=[])
    checked(made["ok"] and document is not None and made["views"] == [], "empty drawing fixture creation failed")
    case["official_constants"] = call("resolve-detailing-official-enums", lambda: adapter._constants(app))
    expected_constants = adapter._load_constants(str(report["official_swconst_path"]))
    checked(case["official_constants"] == expected_constants, "host and supplied official swconst differ")
    case["layout_before"] = call("observe-empty-drawing-layout", lambda: layout(document))
    case["annotations_before"] = call("observe-unrelated-annotation-scalars", lambda:
        read_document_annotation_options_windows(app=app, document=document))
    checked(case["annotations_before"]["ok"], "unrelated annotation baseline failed")
    foreground = None
    try:
        made_front, foreground = call("create-detailing-foreground", lambda: create_part_windows_with_handle(app=app))
        checked(made_front["ok"] and foreground is not None, "foreground fixture creation failed")
        registry = DocumentRegistry(app)
        entry, front = registry.register(document), registry.register(foreground)
        registry.set_current(front, session_id="detailing-calibration")
        lease = registry.acquire_lease(entry, session_id="detailing-calibration", ttl_seconds=1800)

        def activate_foreground():
            import pythoncom
            from win32com.client import VARIANT
            errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            activated = app.ActivateDoc3(_com_value(foreground, "GetTitle"), False, 1, errors)
            checked(activated is not None and errors.value == 0 and registry.is_active(front),
                    "fixture foreground activation failed")

        def read():
            result = execute_operation(app, "document.detailing-options", {}, documents=registry,
                document_id=entry.document_id, session_id="detailing-calibration",
                expected_update_stamp=_com_value(document, "GetUpdateStamp"))
            validate_operation_result("document.detailing-options", result)
            checked(result["ok"] and not result["document"]["active"] and not result["document"]["current"],
                    "public background read failed or changed foreground/current")
            return result

        before_state = _state(document)
        case["initial"] = call("public-background-detailing-read", read)
        checked(_state(document) == before_state, "public read changed drawing state")
        current = case["initial"]["options"]
        # Enable only this owned internal run's exact revision, with no wire/env
        # bypass. The shipped allowlist stays empty until retained proof exists.
        original_allowlist = adapter.CALIBRATED_REVISIONS
        adapter.CALIBRATED_REVISIONS = frozenset({_com_value(app, "RevisionNumber")})
        try:
            for field in DETAILING_FIELDS:
                # Force both true and false and save/reopen each result. No CAD
                # failure recovery, rollback or host replacement is permitted.
                for value in (not current[field], current[field]):
                    evidence = {"field": field, "value": value, "before": current}
                    case["writes"].append(evidence)
                    stamp = _com_value(document, "GetUpdateStamp")
                    result = call("internal-detailing-write-" + field + "-" + str(value), lambda:
                        execute_operation(app, "document.detailing-option-set",
                            {"field": field, "value": value, "expected_options": current},
                            documents=registry, document_id=entry.document_id,
                            session_id="detailing-calibration", expected_update_stamp=stamp, lease_id=lease["lease_id"]))
                    evidence["write"] = result
                    validate_operation_result("document.detailing-option-set", result)
                    checked(result["ok"] and result["changed"] and result["mutation"]["attempted"],
                            "internal detailing write failed: " + str(result))
                    current = result["options"]
                    checked(call("verify-drawing-layout-after-write", lambda: layout(document)) == case["layout_before"],
                            "detailing default changed sheets/views/projection")
                    other = call("verify-unrelated-annotation-scalars", lambda:
                        read_document_annotation_options_windows(app=app, document=document))
                    checked(other["ok"] and other["options"] == case["annotations_before"]["options"],
                            "detailing default changed unrelated annotation scalars")
                    noop = call("internal-detailing-noop", lambda:
                        execute_operation(app, "document.detailing-option-set",
                            {"field": field, "value": value, "expected_options": current},
                            documents=registry, document_id=entry.document_id, session_id="detailing-calibration",
                            expected_update_stamp=_com_value(document, "GetUpdateStamp"), lease_id=lease["lease_id"]))
                    evidence["noop"] = noop
                    validate_operation_result("document.detailing-option-set", noop)
                    checked(noop["ok"] and not noop["changed"] and not noop["mutation"]["attempted"], "no-op mutated")
                    # Save the background drawing, close it, and reopen read-only
                    # while retaining the same foreground and owned host.
                    path = output / ("detailing-" + str(len(case["writes"])) + ".SLDDRW")
                    saved = call("save-detailing-drawing", lambda: save_as_native_windows(str(path), document=document))
                    evidence["save"] = saved
                    checked(saved["ok"] and saved["api_saved"] and saved["save_errors"] == 0
                            and saved["save_warnings"] == 0 and not saved["document"]["modified"]
                            and path.is_file() and path.stat().st_size >= 512, "drawing did not save cleanly")
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    title = _com_value(document, "GetTitle")
                    call("release-detailing-lease", lambda: registry.release_lease(
                        lease["lease_id"], session_id="detailing-calibration"))
                    call("close-saved-detailing-drawing", lambda: app.CloseDoc(title))
                    live["document"] = document = None
                    reopened, document = call("reopen-detailing-readonly", lambda:
                        open_windows_document_with_handle(str(path), app=app, read_only=True))
                    live["document"] = document
                    evidence["reopen"] = reopened
                    checked(reopened["ok"] and reopened["api_errors"] == reopened["api_warnings"] == 0
                            and reopened["read_only"] is True and not _com_value(document, "GetSaveFlag"),
                            "saved drawing did not reopen read-only and cleanly")
                    entry = registry.register(document)
                    call("prepare-background-readback", activate_foreground)
                    evidence["reopened_options"] = call("read-reopened-detailing", read)
                    readonly_lease = registry.acquire_lease(entry, session_id="detailing-calibration", ttl_seconds=1800)
                    refused = call("verify-readonly-write-refusal", lambda:
                        execute_operation(app, "document.detailing-option-set",
                            {"field": field, "value": not value, "expected_options": current},
                            documents=registry, document_id=entry.document_id, session_id="detailing-calibration",
                            expected_update_stamp=_com_value(document, "GetUpdateStamp"),
                            lease_id=readonly_lease["lease_id"]))
                    evidence["readonly_refusal"] = refused
                    validate_operation_result("document.detailing-option-set", refused)
                    checked(not refused["ok"] and refused["mutation"] ==
                            {"attempted": False, "may_have_changed": False}, "read-only write was attempted")
                    registry.release_lease(readonly_lease["lease_id"], session_id="detailing-calibration")
                    checked(evidence["reopened_options"]["options"] == current, "saved detailing values did not persist")
                    checked(call("verify-reopened-layout", lambda: layout(document)) == case["layout_before"],
                            "saved drawing layout changed")
                    checked(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "readback changed saved drawing bytes")
                    evidence["sha256"] = digest
                    title = _com_value(document, "GetTitle")
                    call("close-readonly-detailing-drawing", lambda: app.CloseDoc(title))
                    live["document"] = document = None
                    opened, document = call("reopen-detailing-writable", lambda:
                        open_windows_document_with_handle(str(path), app=app, read_only=False))
                    live["document"] = document
                    checked(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0
                            and not opened["read_only"], "writable fixture reopen failed")
                    entry = registry.register(document)
                    call("prepare-background-write", activate_foreground)
                    lease = registry.acquire_lease(entry, session_id="detailing-calibration", ttl_seconds=1800)
        finally:
            adapter.CALIBRATED_REVISIONS = original_allowlist
        case["success"] = True
    finally:
        if foreground is not None:
            call("close-detailing-foreground", lambda: app.CloseDoc(_com_value(foreground, "GetTitle")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    args = parser.parse_args()
    checked(args.swconst.is_file() and args.drawing_template.is_file(), "official constants and drawing template required")
    args.output_dir.mkdir()
    def runner(*arguments, **keywords):
        report = arguments[7]
        report["official_swconst_path"] = str(args.swconst.resolve())
        return calibrate_case(*arguments, **keywords, template=args.drawing_template.resolve())
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False,
        case_runner=runner, case_plan=[("drawing", "front", False)], diagnostic_case="document-detailing-internal-calibration")


if __name__ == "__main__":
    raise SystemExit(main())
