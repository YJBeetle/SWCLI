"""Internal owned Windows calibration; NOT public CLI acceptance.

One host, first failure stops, no API retry, no automatic rollback or restart.
The external runner enforces native=600s and group=1800s.
"""

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import os
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
from swcli.font_scope_candidates import NEXT_FONT_SCOPES
from swcli.font_scope_evidence import LinkedFontJournal
from swcli.hosts.windows_font_scope_candidates import read_guarded_linked_font_defaults

spec = importlib.util.spec_from_file_location("_font_scope_fixtures", Path(__file__).with_name("prepare-annotation-fixtures.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
harness = fixtures.harness
require = harness.checked

_geometry_spec = importlib.util.spec_from_file_location("_font_scope_geometry_gate", Path(__file__).with_name("verify-document-annotations.py"))
_geometry_support = importlib.util.module_from_spec(_geometry_spec)
_geometry_spec.loader.exec_module(_geometry_support)
same_geometry = _geometry_support.same_geometry

# verify-modeling.py has set up the local gate_support path under python -I.
from gate_support import font_inheritance, font_worker_process


def close(app, document, call):
    title = _com_value(document, "GetTitle")
    call("close-generated-document", lambda: app.CloseDoc(title))


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind, drawing_template, selected_scopes=WRITABLE_FONT_SCOPES, candidate_setter=None,
                   inheritance_input=None):
    require(selected_scopes and all(scope in WRITABLE_FONT_SCOPES for scope in selected_scopes), "invalid calibration scopes")
    candidate_setter = candidate_setter or adapter._calibrate_set_document_font_scope
    case["selected_scopes"] = list(selected_scopes)
    witness_scope = selected_scopes[0] if inheritance_input is not None else None
    if inheritance_input is None:
        fixtures.prepare_case(app, output, constants, plane, reverse, call,
                              case.setdefault("fixture", {}), report, live,
                              profile_kind=profile_kind, drawing_template=drawing_template)
        source = Path(case["fixture"]["path"])
    else:
        path, digest = inheritance_input
        source = call("stage-hashed-inheritance-drawing", lambda: font_inheritance.stage_drawing(path, digest, output))
        case["fixture"] = dict(path=str(source), input_sha256=digest)
        case["inheritance_witness"] = dict(scope=witness_scope, success=False, observations=[])
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

    if profile_kind == "part":
        case["geometry_before"] = fixtures.part_geometry(document, call)
        same_geometry(case["fixture"]["geometry_reopened"], case["geometry_before"])
    current = case["initial"] = read()
    probe_scope = selected_scopes[0] if tuple(selected_scopes) != WRITABLE_FONT_SCOPES else "tables"
    parameters = dict(scope=probe_scope, field="bold", value=not current["fonts"][probe_scope]["bold"], expected_fonts=current["fonts"])
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
    journal = (LinkedFontJournal(output / ("linked-fonts-" + profile_kind + ".jsonl"),
        kind=profile_kind, source_head=os.environ.get("GITHUB_SHA"))
        if candidate_setter is adapter._calibrate_next_document_font_scope and selected_scopes == ("tables",) else None)

    def linked_readback(current, boundary):
        if candidate_setter is not adapter._calibrate_next_document_font_scope or selected_scopes != ("tables",):
            return
        journal.begin(boundary, mutation=current.get("mutation", {"attempted": False, "may_have_changed": False}))
        observed = call("read-linked-table-fonts." + boundary,
            lambda: read_guarded_linked_font_defaults(app=app, document=document, constants=constants,
                scope="tables", on_font=journal.observe))
        unchanged = read()
        require(unchanged["fonts"] == current["fonts"] and unchanged["document"] == current["document"],
                "linked font observations changed document defaults or state")
        durable = journal.complete()
        case.setdefault("linked_font_observations", []).append(
            {"boundary": boundary, "durable_journal": str(journal.path), "values": observed,
             "before": durable["before"], "after": durable["after"], "changes": durable["changes"],
             "inheritance_acceptance": False})

    linked_readback(current, "initial")

    def observe_inheritance(current, boundary, *, baseline=None):
        if witness_scope is None:
            return
        observed = call("read-drawing-inheritance." + boundary,
            lambda: font_inheritance.read_drawing(app, document, constants, witness_scope))
        default = current["fonts"][witness_scope]
        evidence = case["inheritance_witness"]["observations"]
        row = dict(boundary=boundary, objects=observed, scope_default=default, checked=False)
        evidence.append(row)
        if witness_scope == "tables":
            # A General table and its cells use the type-specific default.
            row["general_default"] = case["linked_font_observations"][-1]["after"]["general"]
            default = row["general_default"]["font"]
        if baseline is not None:
            require(_com_value(document, "IsOpenedReadOnly") is True,
                    "persisted inheritance witness requires a native read-only document")
            if witness_scope == "tables":
                require(font_inheritance.effective(default) == font_inheritance.effective(row["scope_default"]),
                        "General table default did not follow the total table font")
        unchanged = read()
        require(unchanged["fonts"] == current["fonts"] and unchanged["document"] == current["document"],
                "inheritance observation changed guarded document state")
        font_inheritance.verify_observation(witness_scope, observed, default, baseline)
        row["checked"] = True
        return observed

    baseline = observe_inheritance(current, "baseline")

    def reopen_background(path, mode, *, read_only):
        reopened, target = call("reopen-font-" + mode, lambda: open_windows_document_with_handle(
            str(path), app=app, read_only=read_only))
        live["document"] = target
        require(reopened["ok"] and reopened["api_errors"] == reopened["api_warnings"] == 0
                and reopened["read_only"] is read_only and not _com_value(target, "GetSaveFlag"),
                "font copy did not reopen with exact clean access mode")
        # Setup only. The document font operation itself does not activate.
        import pythoncom
        from win32com.client import VARIANT
        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        # swDontRebuildActiveDoc = 1. The default option can prompt.
        call("restore-generated-foreground",
             lambda: app.ActivateDoc3(_com_value(foreground, "GetTitle"), False, 1, errors))
        require(errors.value == 0, "failed to restore generated foreground")
        registry.sync()
        reopened_entry = registry.register(target)
        return target, reopened_entry, registry.acquire_lease(
            reopened_entry, session_id="font-scopes-calibration", ttl_seconds=1800)

    def next_noop(current, scope, field, value):
        if candidate_setter is not adapter._calibrate_next_document_font_scope:
            return
        linked_readback(current, "changed-" + field)
        same = operation("document.font-scope-set", dict(scope=scope, field=field, value=value,
            expected_fonts=current["fonts"]), stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
        case.setdefault("same_values", []).append(same)
        require(same["ok"] and same["changed"] is False
                and same["mutation"] == {"attempted": False, "may_have_changed": False}
                and same["fonts"] == current["fonts"] and same["document"] == current["document"],
                "next same-value write changed a font or document state")

    case["writes"] = []
    with patch.object(operations, "set_document_font_scope_windows", candidate_setter):
        for scope in selected_scopes:
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
                next_noop(current, scope, field, value)
                observed = read()
                require(observed["fonts"] == current["fonts"] and observed["document"] == current["document"], "post-edit observation changed state")
                current = observed
        case["millimeter_fonts"] = current["fonts"]
        if profile_kind == "part":
            case["geometry_changed"] = fixtures.part_geometry(document, call)
            same_geometry(case["geometry_before"], case["geometry_changed"])
        for mode in ("millimeters", "points"):
            if mode == "points":
                for scope in selected_scopes:
                    value = 14 if current["fonts"][scope]["height_points"] != 14 else 16
                    row = operation("document.font-scope-set", dict(scope=scope, field="height_points", value=value, expected_fonts=current["fonts"]),
                        stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
                    case["writes"].append(row)
                    require(row["ok"] and row["changed"], "points font edit failed: " + str(row.get("error")))
                    current = row
                    next_noop(current, scope, "height_points", value)
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
            document, entry, lease = reopen_background(
                path, mode, read_only=witness_scope is not None or mode == "points")
            current = read()
            require(current["fonts"] == expected, "complete font snapshots did not persist after reopen")
            require(all(current["fonts"][scope]["height_mode"] == mode for scope in selected_scopes), "font unit mode was lost")
            if profile_kind == "part":
                measured = case["geometry_reopened_" + mode] = fixtures.part_geometry(document, call)
                same_geometry(case["geometry_before"], measured)
            linked_readback(current, "reopened-" + mode)
            observe_inheritance(current, "reopened-" + mode, baseline=baseline)
            case["reopened_" + mode] = current
            case["sha256_" + mode] = digest
            if mode == "points":
                refused = operation("document.font-scope-set", dict(scope=probe_scope, field="bold", value=not current["fonts"][probe_scope]["bold"], expected_fonts=current["fonts"]),
                    stamp=current["document"]["update_stamp"], lease_id=lease["lease_id"])
                require(not refused["ok"] and refused["error"]["type"] == "ValueError"
                        and refused["mutation"] == {"attempted": False, "may_have_changed": False}, "read-only font edit reached mutation")
                require(read() == current, "read-only refusal changed font or document state")
            require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "font readback changed the saved file")
            if witness_scope is not None and mode == "millimeters":
                close(app, document, call)
                live["document"] = None
                document, entry, lease = reopen_background(path, "millimeters-write-continuation", read_only=False)
                current = read()
                require(current["fonts"] == expected, "writable continuation changed persisted fonts")
    require(hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, "font calibration changed its source fixture")
    close(app, document, call)
    live["document"] = None
    close(app, foreground, call)
    require(_com_value(app, "GetDocumentCount") == 0, "font case left generated documents open")
    if witness_scope is not None:
        input_path, input_digest = inheritance_input
        require(font_inheritance.file_digest(input_path) == input_digest, "original inheritance input bytes changed")
        for mode in ("millimeters", "points"):
            saved_path = output / ("changed-fonts-" + mode + source.suffix)
            require(font_inheritance.file_digest(saved_path) == case["sha256_" + mode],
                    "saved inheritance output bytes changed after observation")
        case["inheritance_witness"]["success"] = True
        case["inheritance_status"] = "bounded internal drawing witness passed; public writes remain closed"
    else:
        case["inheritance_status"] = "per-object inheritance not calibrated; public writes remain closed"
    case.update(kind=profile_kind, success=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--swconst", required=True, type=Path)
    parser.add_argument("--drawing-template", required=True, type=Path)
    parser.add_argument("--scope", choices=NEXT_FONT_SCOPES, help="probe only one next candidate; public writes remain closed")
    parser.add_argument("--inheritance-drawing", type=Path)
    parser.add_argument("--inheritance-sha256")
    font_worker_process.add_worker_options(parser)
    args = parser.parse_args(argv)
    supervision = font_worker_process.verify_worker_launch(args, parser)
    if args.supervision_probe:
        font_worker_process.write_worker_output(args.output_dir, supervision)
        return 0
    font_inheritance.validate_drawing_input(args.scope, args.inheritance_drawing, args.inheritance_sha256)
    require(args.swconst.is_file() and args.drawing_template.is_file(), "official swconst and drawing template required")
    font_worker_process.write_worker_output(args.output_dir, supervision)
    original_reader = harness.read_constants
    def read_constants(pythoncom, path):
        return {**original_reader(pythoncom, path), **adapter.read_font_constants(pythoncom, path, candidate_scope=args.scope,
                    witness_enum=font_inheritance.ENUM[args.scope] if args.inheritance_drawing is not None else None)}
    harness.read_constants = read_constants
    def runner(app, output, constants, *arguments, **keywords):
        if args.scope is not None:
            require(adapter._native_windows_runtime() and _com_value(app, "RevisionNumber") == "33.5.0",
                    "next calibration requires native Windows SOLIDWORKS 33.5.0")
        inheritance_input = (args.inheritance_drawing, args.inheritance_sha256) if (
            args.inheritance_drawing is not None and keywords["profile_kind"] == "drawing") else None
        with patch.object(adapter, "_installed_constants", lambda: constants):
            return calibrate_case(app, output, constants, *arguments, **keywords, drawing_template=args.drawing_template,
                selected_scopes=(args.scope,) if args.scope else WRITABLE_FONT_SCOPES,
                candidate_setter=adapter._calibrate_next_document_font_scope if args.scope else None,
                inheritance_input=inheritance_input)
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False, case_runner=runner,
                       case_plan=[(kind, "front", False) for kind in fixtures.KINDS], diagnostic_case="font-scopes-next-" + args.scope if args.scope else "font-scopes-internal-calibration")


if __name__ == "__main__":
    raise SystemExit(main())
