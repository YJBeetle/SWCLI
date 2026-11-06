"""Internal table-default calibration on one owned host; not public acceptance.

The harness stops at the first failure. No setter retry, rollback, attachment or
host replacement. The Windows wrapper enforces 600s calls / 1800s group budget.
"""

import argparse
from copy import deepcopy
from functools import partial
import hashlib
import importlib.util
import json
from pathlib import Path

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon import operations
from swcli.document_tables import TABLE_FIELDS
from swcli.hosts import windows_document_tables as adapter
from swcli.hosts.native_trace import trace_native_request
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_documents import open_windows_document_with_handle, _diagnose_features
from swcli.hosts.windows_feature_inspection import _same
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location("_table_owned_fixtures", Path(__file__).with_name("prepare-annotation-fixtures.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
harness, checked = fixtures.harness, fixtures.checked


def record_geometry_check(output, case, field, actual):
    """Persist both operands before the unchanged exact-geometry assertion."""
    before = case["geometry_reopened"]
    row = dict(field=field, before=before, after=actual, exact_equal=actual == before)
    case.setdefault("geometry_checks", []).append(row)
    with (output / "geometry-observations.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, allow_nan=False) + "\n")
        stream.flush()
    checked(actual == before, "table scalar write changed analytic fixture geometry")


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live,
                   *, profile_kind, drawing_template, swconst):
    fixtures.prepare_case(app, output, constants, plane, reverse, call, case, report, live,
                          profile_kind=profile_kind, drawing_template=drawing_template)
    case.update(success=False, preparation_only=False, internal_calibration_only=True, writes=[])
    path = Path(case["path"])
    opened, document = call("open-table-fixture-writable", lambda: open_windows_document_with_handle(str(path), app=app))
    live["document"] = document
    case["writable_open"] = opened
    checked(opened["ok"] and not opened["api_errors"] and not opened["api_warnings"] and document is not None,
            "table fixture did not open cleanly for writing")
    kind = fixtures.KINDS[profile_kind][0]
    native_constants = call("resolve-table-enums-from-host", lambda: adapter._constants(app))
    official = call("resolve-table-enums-from-explicit-official-library", lambda: adapter._read_constants(swconst))
    checked(native_constants == official, "runtime table constants differ from the installed official library")
    case["table_constants"] = official
    peer_result, peer = call("create-foreground-peer", lambda: create_part_windows_with_handle(app=app))
    checked(peer_result["ok"] and peer is not None and _same(app, _com_value(app, "ActiveDoc"), peer)
            and not _same(app, document, peer), "table calibration requires the fixture in the background")
    peer_title = _com_value(peer, "GetTitle")
    registry = DocumentRegistry(app)
    entry = registry.register(document)
    registry.register(peer)
    session = "internal-table-calibration"
    lease = registry.acquire_lease(entry, session_id=session, ttl_seconds=1800)["lease_id"]

    def execute(name, values=None, *, reader=False):
        descriptor = registry.describe(entry, session_id=session)
        result = operations.execute_operation(app, name, values or {}, documents=registry,
            session_id="table-observer" if reader else session, document_id=entry.document_id,
            expected_update_stamp=descriptor["update_stamp"], lease_id=lease if name.endswith("-set") else None)
        validate_operation_result(name, result)
        return result

    original = call("read-public-table-defaults", lambda: execute("document.table-options", reader=True))
    case["original"] = original
    checked(original["ok"], "public table read failed")
    checked(all(("unavailable" in original["options"][field]) == (kind not in spec["types"])
                for field, spec in TABLE_FIELDS.items()), "table applicability differs from documented types")
    field = "bom.box_border"
    blocked = call("verify-public-table-write-is-closed", lambda: execute("document.table-option-set",
        dict(field=field, value="thick", expected_options=original["options"])))
    case["public_write_gate"] = blocked
    checked(not blocked["ok"] and blocked["error"]["type"] == "DocumentTableCalibrationRequired"
            and blocked["mutation"] == dict(attempted=False, may_have_changed=False), "uncalibrated public write was not blocked")
    initial_health = call("observe-table-feature-health", lambda: _diagnose_features(document, 500))
    checked(initial_health["healthy"] and not initial_health["truncated"], "fixture feature health is not clean")
    case["feature_health"] = initial_health
    previous_handler = operations.set_document_table_option_windows
    # Only this non-public diagnostic process can enter the candidate adapter.
    operations.set_document_table_option_windows = partial(adapter._edit_table_option, calibration=True)
    try:
        current = original["options"]
        for field, spec in TABLE_FIELDS.items():
            if kind not in spec["types"]:
                unsupported = call("reject-unavailable-table-default", lambda field=field: execute("document.table-option-set",
                    dict(field=field, value="thick", expected_options=current)))
                checked(not unsupported["ok"] and unsupported["mutation"] == dict(attempted=False, may_have_changed=False),
                        "non-drawing general-table write was not rejected")
                continue
            value = not current[field]["value"] if spec["kind"] == "Toggle" else (
                "normal" if current[field]["value"] != "normal" else "thick")
            expected = deepcopy(current)
            changed = call("internal-table-write:" + field, lambda: execute("document.table-option-set",
                dict(field=field, value=value, expected_options=expected)))
            case["writes"].append(changed)
            checked(changed["ok"] and changed["changed"] and changed["document"]["modified"]
                    and changed["mutation"] == dict(attempted=True, may_have_changed=True), "table scalar write failed")
            current = changed["options"]
            checked(current[field]["value"] == value and all(current[key] == expected[key] for key in TABLE_FIELDS if key != field),
                    "table scalar write changed an unrelated default")
            noop = call("internal-table-noop:" + field, lambda: execute("document.table-option-set",
                dict(field=field, value=value, expected_options=current)))
            case.setdefault("noops", []).append(noop)
            checked(noop["ok"] and not noop["changed"] and noop["mutation"] == dict(attempted=False, may_have_changed=False),
                    "table no-op attempted a mutation")
            conflict = call("reject-stale-complete-table-snapshot:" + field, lambda: execute("document.table-option-set",
                dict(field=field, value=value, expected_options=expected)))
            case.setdefault("conflicts", []).append(conflict)
            checked(not conflict["ok"] and conflict["error"]["type"] == "DocumentTableConflict"
                    and conflict["mutation"] == dict(attempted=False, may_have_changed=False), "full table CAS did not reject drift")
            if kind == 1:
                measured = fixtures.part_geometry(document, call)
                record_geometry_check(output, case, field, measured)
            checked(call("verify-table-feature-health", lambda: _diagnose_features(document, 500)) == initial_health,
                    "table scalar write changed feature health or feature count")
        case["final_options"] = current
        saved_path = output / ("table-defaults." + fixtures.KINDS[profile_kind][1])
        case["saved_path"] = str(saved_path)
        saved = call("save-table-defaults", lambda: save_as_native_windows(str(saved_path), document=document))
        case["save_defaults"] = saved
        path = saved_path
        checked(saved["ok"] and saved["api_saved"] and saved["save_errors"] == 0
                and saved["save_warnings"] is None and not _com_value(document, "GetSaveFlag"), "table defaults did not save cleanly")
    finally:
        operations.set_document_table_option_windows = previous_handler
        # Close only the generated peer. The owned harness cleans up the target/host.
        peer = None
        call("close-table-foreground-peer", lambda: app.CloseDoc(peer_title))
    title = _com_value(document, "GetTitle")
    live["document"] = document = None
    call("close-saved-table-fixture", lambda: app.CloseDoc(title))
    checked(_com_value(app, "GetDocumentCount") == 0, "table fixture or peer remains open")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    reopened, document = call("reopen-table-defaults-readonly", lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
    live["document"] = document
    checked(reopened["ok"] and reopened["api_errors"] == reopened["api_warnings"] == 0
            and reopened["read_only"] is True and document is not None, "saved table defaults did not reopen read-only")
    readback = call("read-persisted-table-defaults", lambda: adapter.read_document_table_options_windows(app=app, document=document))
    case["persisted"] = readback
    checked(readback["ok"] and readback["options"] == case["final_options"], "table defaults did not persist after reopening")
    denied = call("reject-readonly-internal-table-write", lambda: adapter._edit_table_option(app=app, document=document,
        field="bom.box_border", value="thin", expected_options=case["final_options"], calibration=True))
    case["readonly_rejection"] = denied
    checked(not denied["ok"] and denied["mutation"] == dict(attempted=False, may_have_changed=False), "read-only write was not blocked")
    if kind == 1:
        reopened_geometry = fixtures.part_geometry(document, call)
        record_geometry_check(output, case, "saved-reopen", reopened_geometry)
    checked(hashlib.sha256(path.read_bytes()).hexdigest() == digest and not _com_value(document, "GetSaveFlag"),
            "read-only table readback altered the file or modified state")
    case["persisted_sha256"] = digest
    title = _com_value(document, "GetTitle")
    live["document"] = document = None
    call("close-readonly-table-fixture", lambda: app.CloseDoc(title))
    checked(_com_value(app, "GetDocumentCount") == 0, "read-only table fixture remains open")
    checked(_com_value(app, "GetProcessID") == report["host"]["process_id"], "table calibration changed host")
    case["success"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    parser.add_argument("--document-types", nargs="+", choices=tuple(fixtures.KINDS), default=list(fixtures.KINDS))
    args = parser.parse_args(argv)
    checked(args.swconst.is_file(), "official swconst type library is required")
    checked(args.drawing_template.is_file() and args.drawing_template.suffix.lower() == ".drwdot", "explicit drawing template is required")
    checked(len(args.document_types) == len(set(args.document_types)), "duplicate document type in calibration plan")
    selected = [kind for kind in fixtures.KINDS if kind in args.document_types]
    args.output_dir.mkdir()
    def runner(*arguments, **keywords):
        arguments[7]["requested_document_types"] = [fixtures.KINDS[kind][0] for kind in selected]
        return calibrate_case(*arguments, **keywords, drawing_template=args.drawing_template.resolve(), swconst=args.swconst.resolve())
    with trace_native_request("table-defaults-calibration", "internal.table-defaults"):
        return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False, case_runner=runner,
            case_plan=[(kind, "front", False) for kind in selected], diagnostic_case="document-table-defaults-internal")


if __name__ == "__main__":
    raise SystemExit(main())
