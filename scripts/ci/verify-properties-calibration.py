"""Owned native fixture proof for a15 property reads, followed by the existing full gate."""

import argparse
import hashlib
import importlib.util
from pathlib import Path

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_assemblies import create_assembly_windows_with_handle
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_custom_properties import _state
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location(
    "_properties_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py")
)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked

FIXTURE = {
    "Chinese Name": (30, "测试零件"),
    "English Name": (30, "Property fixture"),
    "Drawing No": (30, ""),
    "Quantity": (3, "42"),
    "Approved": (11, "Yes"),
}


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind):
    creator = create_part_windows_with_handle if profile_kind == "part" else create_assembly_windows_with_handle
    made, document = call("create-properties-fixture", lambda: creator(app=app))
    live["document"] = document
    case.update(kind=profile_kind, creation=made)
    checked(made["ok"] and document is not None, "fixture creation failed")
    extension = _com_value(document, "Extension")
    manager = call("document-property-manager", lambda: extension.CustomPropertyManager(""))
    for name, (type_code, value) in FIXTURE.items():
        status = call("seed-document-property-" + name, lambda: manager.Add3(name, type_code, value, 0))
        checked(status == 0 and type(status) is int, "fixture property creation failed")
    configuration = _com_value(_com_value(document, "GetActiveConfiguration"), "Name")
    scoped = extension.CustomPropertyManager(configuration)
    checked(call("seed-configuration-shadow", lambda: scoped.Add3("Drawing No", 30, "configuration-only", 0)) == 0,
            "configuration shadow fixture failed")
    foreground = None
    try:
        foreground_result, foreground = call("create-foreground", lambda: create_part_windows_with_handle(app=app))
        checked(foreground_result["ok"] and foreground is not None, "foreground creation failed")
        registry = DocumentRegistry(app)
        entry = registry.register(document)
        front = registry.register(foreground)
        registry.set_current(front, session_id="properties-reader")
        registry.acquire_lease(entry, session_id="fixture-writer", ttl_seconds=600)

        def read(name=None):
            result = execute_operation(
                app, "document.properties", {} if name is None else {"name": name},
                documents=registry, session_id="properties-reader", document_id=entry.document_id,
                expected_update_stamp=_com_value(document, "GetUpdateStamp"),
            )
            validate_operation_result("document.properties", result)
            checked(result["ok"], "property read failed: " + str(result))
            checked(not result["document"]["active"] and not result["document"]["current"],
                    "background property read changed document selection")
            return result

        before = _state(document)
        case["listing"] = call("list-properties", read)
        rows = {row["name"]: row for row in case["listing"]["properties"]}
        checked(set(rows) == set(FIXTURE), "document listing leaked or lost fixture properties")
        for name, (type_code, value) in FIXTURE.items():
            row = rows[name]
            checked(row["raw_value"] == value and row["type_code"] == type_code,
                    "native property text/type differs from fixture")
            case.setdefault("lookups", {})[name] = call("lookup-" + name, lambda: read(name))
            checked(case["lookups"][name]["properties"] == [row], "lookup/list mismatch")
        checked(rows["Drawing No"]["evaluated_value"] == "", "empty property was lost")
        case["missing"] = call("lookup-missing", lambda: read("Absent property"))
        checked(case["missing"]["properties"] == [], "missing property became present")
        case["state_before"], case["state_after"] = before, _state(document)
        checked(before == case["state_after"], "reads modified fixture state")
        checked(_com_value(app, "GetProcessID") == report["host"]["process_id"], "owned host changed")
    finally:
        if foreground is not None:
            call("close-foreground", lambda: app.CloseDoc(_com_value(foreground, "GetTitle")))

    path = output / ("properties." + ("SLDPRT" if profile_kind == "part" else "SLDASM"))
    case["save"] = call("save-properties", lambda: save_as_native_windows(str(path), document=document))
    checked(case["save"]["ok"], "native property fixture save failed")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    call("close-properties-fixture", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = document = None
    opened, document = call("reopen-properties-readonly", lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
    live["document"] = document
    case["reopen"] = opened
    checked(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0, "fixture reopen failed")
    registry = DocumentRegistry(app)
    entry = registry.register(document)
    reopened = call("read-reopened-properties", lambda: execute_operation(
        app, "document.properties", {}, documents=registry,
        session_id="properties-reader", document_id=entry.document_id,
    ))
    case["reopened_properties"] = reopened
    validate_operation_result("document.properties", reopened)
    checked(reopened["ok"] and reopened["properties"] == case["listing"]["properties"],
            "saved/reopened properties differ")
    checked(not _com_value(document, "GetSaveFlag") and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            "readonly property observation changed saved file/state")
    case["file_sha256"] = digest
    call("close-reopened-properties", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = None
    checked(_com_value(app, "GetDocumentCount") == 0, "fixture documents remain")
    case["success"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    args = parser.parse_args(argv)
    checked(args.swconst.is_file(), "official swconst type library is required")
    args.output_dir.mkdir()
    return harness.run(
        args.output_dir.resolve(), args.swconst.resolve(), False,
        case_runner=calibrate_case, case_plan=[("part", "front", False), ("assembly", "front", False)],
        diagnostic_case="document-properties-calibration",
    )


if __name__ == "__main__":
    raise SystemExit(main())
