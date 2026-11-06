"""Internal owned Windows calibration; NOT public CLI acceptance.

One host, first failure stops, no API retry, no automatic rollback or restart.
The external runner enforces native=600s and group=1800s.
"""

import argparse
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from swcli.hosts.native_trace import trace_native_request

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon import operations
from swcli.document_font_scopes import FONT_SCOPES, WRITABLE_FONT_SCOPES
from swcli.hosts import windows_document_font_scopes as adapter
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location("_font_scope_fixtures", Path(__file__).with_name("prepare-annotation-fixtures.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
harness = fixtures.harness
require = harness.checked


def close(app, document, call):
    title = _com_value(document, "GetTitle")
    call("close-generated-document", lambda: app.CloseDoc(title))


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind, drawing_template):
    # Prepared sources are native generated fixtures, with unchanged geometry
    # assertions inherited verbatim from the established annotation harness.
    fixtures.prepare_case(app, output, constants, plane, reverse, call,
                          case.setdefault("fixture", {}), report, live,
                          profile_kind=profile_kind, drawing_template=drawing_template)
    source = Path(case["fixture"]["path"])
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    opened, document = call("open-font-source", lambda: open_windows_document_with_handle(str(source), app=app))
    live["document"] = document
    require(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0, "font source open failed")
    front_result, foreground = call("create-font-foreground", lambda: create_part_windows_with_handle(app=app))
    require(front_result["ok"] and foreground is not None, "background font fixture requires a separate foreground")
    registry = DocumentRegistry(app)
    entry, front = registry.register(document), registry.register(foreground)
    registry.set_current(front, session_id="font-scopes-calibration")
    lease = registry.acquire_lease(entry, session_id="font-scopes-calibration", ttl_seconds=1800)

    def operation(name, parameters=None, *, stamp=None, session="font-scopes-calibration", lease_id=None):
        request_id = "font-scopes-" + uuid4().hex
        case.setdefault("requests", []).append({"request_id": request_id, "operation": name,
            "scope": (parameters or {}).get("scope"), "field": (parameters or {}).get("field")})
        with trace_native_request(request_id, name):
            result = call(name, lambda: operations.execute_operation(
                app, name, parameters or {}, documents=registry, session_id=session,
                document_id=entry.document_id, expected_update_stamp=stamp, lease_id=lease_id))
        validate_operation_result(name, result)
        require(result["document"]["active"] is False, "font operation activated background document")
        return result

    def read():
        result = operation("document.font-scopes")
        require(result["ok"], "font scope read failed: " + str(result.get("error")))
        return result

    current = case["initial"] = read()
    parameters = dict(scope="notes", field="bold", value=not current["fonts"]["notes"]["bold"], expected_fonts=current["fonts"])
    refused = case["public_write_refusal"] = operation("document.font-scope-set", parameters,
        stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
    require(not refused["ok"] and refused["error"]["type"] == "DocumentFontScopeNotCalibrated"
            and refused["mutation"] == {"attempted": False, "may_have_changed": False}, "public scoped write was not closed")
    unchanged = read()
    require(unchanged == current, "public refusal changed document state or fonts")
    case["guard_refusals"] = []
    for kind, stamp, session, token in (
        ("stamp", current["document"]["update_stamp"] + 1, "font-scopes-calibration", lease["lease_id"]),
        ("lease", current["document"]["update_stamp"], "font-scopes-contender", lease["lease_id"]),
    ):
        try:
            operation("document.font-scope-set", parameters, stamp=stamp, session=session, lease_id=token)
        except Exception as exc:
            expected = "DocumentUpdateConflict" if kind == "stamp" else "DocumentLeaseConflict"
            require(type(exc).__name__ == expected, "wrong guard refusal: " + type(exc).__name__)
            case["guard_refusals"].append({"guard": kind, "error_type": expected})
        else:
            raise RuntimeError("font write guard did not refuse")
    require(read() == current, "guard refusals changed document state")
    case["writes"] = []
    with patch.object(operations, "set_document_font_scope_windows", adapter._calibrate_set_document_font_scope):
        for scope in WRITABLE_FONT_SCOPES:
            targets = {"typeface": "Arial" if current["fonts"][scope]["typeface"] != "Arial" else "Times New Roman",
                       "bold": not current["fonts"][scope]["bold"], "italic": not current["fonts"][scope]["italic"],
                       "underline": not current["fonts"][scope]["underline"], "strikeout": not current["fonts"][scope]["strikeout"],
                       "height_mm": 3.5 if current["fonts"][scope]["height_mm"] != 3.5 else 4.0}
            for field, value in targets.items():
                stale = deepcopy(current["fonts"])
                stale["annotations"]["bold"] = not stale["annotations"]["bold"]
                conflict = operation("document.font-scope-set", dict(scope=scope, field=field, value=value, expected_fonts=stale),
                    stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
                require(not conflict["ok"] and conflict["error"]["type"] == "DocumentFontScopeConflict"
                        and conflict["mutation"] == {"attempted": False, "may_have_changed": False}, "full-scope CAS was not enforced")
                row = operation("document.font-scope-set", dict(scope=scope, field=field, value=value, expected_fonts=current["fonts"]),
                    stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
                case["writes"].append(row)
                require(row["ok"] and row["changed"] and row["document"]["modified"], "native font edit failed: " + str(row.get("error")))
                current = row
                observed = read()
                require(observed["fonts"] == current["fonts"] and observed["document"] == current["document"], "post-edit observation changed state")
                current = observed
        case["millimeter_fonts"] = current["fonts"]
        if profile_kind == "part":
            case["geometry_changed"] = fixtures.part_geometry(document, call)
            require(case["geometry_changed"] == case["fixture"]["geometry_reopened"], "font writes changed native geometry")
        for mode in ("millimeters", "points"):
            if mode == "points":
                for scope in WRITABLE_FONT_SCOPES:
                    value = 14 if current["fonts"][scope]["height_points"] != 14 else 16
                    row = operation("document.font-scope-set", dict(scope=scope, field="height_points", value=value, expected_fonts=current["fonts"]),
                        stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
                    case["writes"].append(row)
                    require(row["ok"] and row["changed"], "points font edit failed: " + str(row.get("error")))
                    current = row
            expected = deepcopy(current["fonts"])
            path = output / ("changed-fonts-" + mode + source.suffix)
            saved = call("save-font-" + mode, lambda: save_as_native_windows(str(path), document=document))
            case["save_" + mode] = saved
            require(saved["ok"] and saved["api_saved"] is True and saved["save_errors"] == 0
                    and saved["save_warnings"] is None and not saved["document"]["modified"]
                    and path.is_file() and path.stat().st_size >= 512, "font copy save failed")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            close(app, document, call)
            live["document"] = None
            reopened, document = call("reopen-font-" + mode, lambda: open_windows_document_with_handle(str(path), app=app, read_only=mode == "points"))
            live["document"] = document
            require(reopened["ok"] and reopened["api_errors"] == reopened["api_warnings"] == 0
                    and not _com_value(document, "GetSaveFlag"), "font copy did not reopen cleanly")
            # Open may change foreground; use the explicit activation only here,
            # outside font operations, and restore the same generated front.
            import pythoncom
            from win32com.client import VARIANT
            errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            call("restore-generated-foreground", lambda: app.ActivateDoc3(_com_value(foreground, "GetTitle"), False, 0, errors))
            require(errors.value == 0, "failed to restore generated foreground")
            registry.sync()
            entry = registry.register(document)
            lease = registry.acquire_lease(entry, session_id="font-scopes-calibration", ttl_seconds=1800)
            current = read()
            require(current["fonts"] == expected, "complete font snapshots did not persist after reopen")
            require(all(current["fonts"][scope]["height_mode"] == mode for scope in WRITABLE_FONT_SCOPES), "font unit mode was lost")
            case["reopened_" + mode] = current
            case["sha256_" + mode] = digest
            if mode == "points":
                refused = operation("document.font-scope-set", dict(scope="notes", field="bold", value=not current["fonts"]["notes"]["bold"], expected_fonts=current["fonts"]),
                    stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
                require(not refused["ok"] and refused["error"]["type"] == "ValueError"
                        and refused["mutation"] == {"attempted": False, "may_have_changed": False}, "read-only font edit reached mutation")
                require(read() == current, "read-only refusal changed font or document state")
            require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "font readback changed the saved file")
    require(hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, "font calibration changed its source fixture")
    close(app, document, call)
    live["document"] = None
    close(app, foreground, call)
    require(_com_value(app, "GetDocumentCount") == 0, "font case left generated documents open")
    case.update(kind=profile_kind, success=True, inheritance_status="per-object inheritance not calibrated; public writes remain closed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--swconst", required=True, type=Path)
    parser.add_argument("--drawing-template", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output_dir.mkdir()
    require(args.swconst.is_file() and args.drawing_template.is_file(), "official swconst and drawing template required")
    original_reader = harness.read_constants
    def read_constants(pythoncom, path):
        return {**original_reader(pythoncom, path), **adapter.read_font_constants(pythoncom, path)}
    harness.read_constants = read_constants
    def runner(app, output, constants, *arguments, **keywords):
        with patch.object(adapter, "_installed_constants", lambda: constants):
            return calibrate_case(app, output, constants, *arguments, **keywords, drawing_template=args.drawing_template)
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False, case_runner=runner,
                       case_plan=[(kind, "front", False) for kind in fixtures.KINDS], diagnostic_case="font-scopes-internal-calibration")


if __name__ == "__main__":
    raise SystemExit(main())
