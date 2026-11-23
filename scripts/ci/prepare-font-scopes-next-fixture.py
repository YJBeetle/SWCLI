"""Prepare owned synthetic drawing fixtures under the font watchdog."""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import sys

from swcli.hosts import windows_document_font_scopes as fonts
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
from swcli.hosts.windows_feature_selections import _same
from swcli.hosts.windows_font_scope_candidates import read_guarded_linked_font_defaults
from swcli.hosts.windows_native_files import save_as_native_windows

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support import font_inheritance as witness
from gate_support import font_worker_process

spec = importlib.util.spec_from_file_location(
    "_owned_font_fixture_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
require = witness.require
CELL_TEXT = ("Fixture inherited", "Fixture local")
LOCAL_FACE = "Courier New"
LOCAL_POINTS = 20
# Official swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft.
TOP_LEFT = 1


def cell_text(table, call, *, put=False):
    import pythoncom

    dispatch = table._oleobj_
    member = call("Text2.GetIDsOfNames", lambda: dispatch.GetIDsOfNames("Text2"))
    values = []
    for column, label in enumerate(CELL_TEXT):
        if put:
            call("Text2.put", lambda: dispatch.Invoke(
                member, 0, pythoncom.DISPATCH_PROPERTYPUT, False, 0, column, False, label))
        value = call("Text2.get", lambda: dispatch.Invoke(
            member, 0, pythoncom.DISPATCH_PROPERTYGET, True, 0, column, False))
        require(value == label, "synthetic General table cell text differs")
        values.append(value)
    return values


def seed_table(document, constants, call):
    table = call("IDrawingDoc.InsertTableAnnotation2", lambda: document.InsertTableAnnotation2(
        False, 0.05, 0.12, TOP_LEFT, "", 1, 2))
    require(table is not None and _com_value(table, "Type") == constants[witness.ENUM["tables"]]
            and (_com_value(table, "RowCount"), _com_value(table, "ColumnCount")) == (1, 2),
            "insert did not produce one 1x2 General table")
    cell_text(table, call, put=True)
    table_inherits = call("ITableAnnotation.GetUseDocTextFormat", lambda: _com_value(table, "GetUseDocTextFormat"))
    require(type(table_inherits) is bool, "table document font flag is unreadable")
    if not table_inherits:
        current = call("ITableAnnotation.GetTextFormat", lambda: _com_value(table, "GetTextFormat"))
        require(current is not None, "General table font is missing")
        require(call("ITableAnnotation.SetTextFormat.document", lambda: table.SetTextFormat(True, current)) is True,
                "could not enable the document font for the General table")
    left_inherits = call("ITableAnnotation.GetCellUseDocTextFormat.left", lambda: table.GetCellUseDocTextFormat(0, 0))
    require(type(left_inherits) is bool, "left cell document font flag is unreadable")
    if not left_inherits:
        current = call("ITableAnnotation.GetCellTextFormat.left", lambda: table.GetCellTextFormat(0, 0))
        require(current is not None, "left cell font is missing")
        require(call("ITableAnnotation.SetCellTextFormat.document", lambda: table.SetCellTextFormat(0, 0, True, current)) is True,
                "could not enable the document font for the left cell")
    current = call("ITableAnnotation.GetCellTextFormat.right", lambda: table.GetCellTextFormat(0, 1))
    require(current is not None, "right cell font is missing")
    require(call("ITableAnnotation.SetCellTextFormat.local", lambda: table.SetCellTextFormat(0, 1, False, current)) is True,
            "could not establish a local right cell font")
    require(call("ITableAnnotation.GetCellUseDocTextFormat.right", lambda: table.GetCellUseDocTextFormat(0, 1)) is False,
            "right cell font is still inherited")
    local = call("ITableAnnotation.GetCellTextFormat.local", lambda: table.GetCellTextFormat(0, 1))
    require(local is not None, "local right cell font is missing")
    call("ITextFormat.TypeFaceName.local", lambda: setattr(local, "TypeFaceName", LOCAL_FACE))
    call("ITextFormat.CharHeightInPts.local", lambda: setattr(local, "CharHeightInPts", LOCAL_POINTS))
    require(call("ITableAnnotation.SetCellTextFormat.local-commit", lambda: table.SetCellTextFormat(0, 1, False, local)) is True,
            "could not persist the local right cell font")


def inspect_fixture(app, document, constants, scope, call, *, generated=False):
    observed = call("read-guarded-drawing-inheritance", lambda: witness.read_drawing(
        app, document, constants, scope, expected_open_documents=1))
    _, defaults, native = call("read-four-native-defaults", lambda: fonts._read_fonts(document, constants))
    record = dict(objects=observed, defaults=defaults, native_defaults=native)
    default = defaults[scope]
    if scope == "tables":
        linked = call("read-linked-table-defaults", lambda: read_guarded_linked_font_defaults(
            app=app, document=document, constants=constants, scope="tables"))
        record["linked_defaults"] = linked
        default = linked["fonts"]["general"]
        require(witness.effective(default) == witness.effective(defaults[scope]),
                "GB fixture requires matching total and General table defaults")
        view = _com_value(document, "GetFirstView")
        table = witness.general_table(view, constants[witness.ENUM["tables"]])
        record["cell_text"] = cell_text(table, call)
        if generated:
            local = observed["local"]["font"]
            require((local["typeface"], local["height_mode"], local["height_points"])
                    == (LOCAL_FACE, "points", LOCAL_POINTS), "synthetic local right cell font did not round-trip")
    witness.verify_observation(scope, observed, default)
    return record


def close(app, document, live, call):
    title = call("read-fixture-title", lambda: _com_value(document, "GetTitle"))
    call("close-owned-font-fixture", lambda: app.CloseDoc(title))
    live["document"] = None
    require(_com_value(app, "GetDocumentCount") == 0, "owned font fixture did not close")


def read_saved(app, path, digest, constants, scope, call, case, live, *, generated):
    require(witness.file_digest(path) == digest, "fixture digest differs before read-only open")
    opened, document = call("open-fixture-read-only", lambda: open_windows_document_with_handle(
        str(path), app=app, read_only=True))
    live["document"] = document
    case["reopen"] = opened
    require(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0
            and opened["read_only"] is True and document is not None
            and _com_value(document, "IsOpenedReadOnly") is True
            and _com_value(document, "GetSaveFlag") is False
            and Path(_com_value(document, "GetPathName")).resolve() == path.resolve(),
            "fixture did not reopen read-only at the exact clean path")
    case["reopened_observation"] = inspect_fixture(app, document, constants, scope, call, generated=generated)
    require(_com_value(document, "GetSaveFlag") is False, "observation dirtied a read-only fixture")
    close(app, document, live, call)
    require(witness.file_digest(path) == digest, "read-only fixture bytes changed")


def run_case(app, output, constants, call, case, live, *, scope, template, manual):
    require(_com_value(app, "RevisionNumber") == "33.5.0", "fixture generation requires SOLIDWORKS 33.5.0")
    case.update(scope=scope, success=False, preparation_only=True, public_acceptance=False,
                inheritance_acceptance=False, source_head=os.environ.get("GITHUB_SHA"))
    generated = manual is None
    case["source_kind"] = "generated-GB-table" if generated else "synthetic-manual-copy"
    case["save_attempted"] = False
    case["save_verified"] = False
    if generated:
        require(scope == "tables", "dimensions requires a self-built manual drawing")
        path = output / "font-tables-fixture.SLDDRW"
        require(not path.exists(), "fixture output is not fresh")
        made, document = call("create-GB-drawing", lambda: create_drawing_windows_with_handle(
            app=app, template=str(template), projection="first-angle"))
        live["document"] = document
        case["creation"] = made
        require(made["ok"] and document is not None and made["views"] == []
                and made["template"]["path"] == str(template)
                and _com_value(document, "GetType") == 3 and not _com_value(document, "GetPathName")
                and _com_value(app, "GetDocumentCount") == 1
                and _same(app, _com_value(app, "ActiveDoc"), document), "GB drawing is not a newly created owned document")
        _, _, initial_native = call("read-initial-native-defaults", lambda: fonts._read_fonts(document, constants))
        initial_linked = call("read-initial-linked-table-defaults", lambda: read_guarded_linked_font_defaults(
            app=app, document=document, constants=constants, scope="tables"))
        seed_table(document, constants, call)
        before_save = case["before_save_observation"] = inspect_fixture(
            app, document, constants, scope, call, generated=True)
        require(before_save["native_defaults"] == initial_native
                and before_save["linked_defaults"] == initial_linked, "table seeding changed a document default")
        case["save_attempted"] = True
        saved = case["save"] = call("save-fixture-copy", lambda: save_as_native_windows(str(path), document=document))
        require(saved["ok"] and saved["api_saved"] is True and saved["save_errors"] == 0
                and saved["save_warnings"] == 0 and saved["document"]["modified"] is False
                and Path(saved["document"]["path"]).resolve() == path.resolve()
                and path.is_file() and path.stat().st_size >= 512, "native fixture save did not produce a clean file")
        case["save_verified"] = True
        digest = witness.file_digest(path)
        close(app, document, live, call)
    else:
        original, digest = manual
        path = call("stage-synthetic-manual-input", lambda: witness.stage_drawing(original, digest, output))
        case["manual_input_sha256"] = digest
    case.update(path=str(path), file_sha256=digest, size_bytes=path.stat().st_size)
    read_saved(app, path, digest, constants, scope, call, case, live, generated=generated)
    if generated:
        require(case["reopened_observation"] == before_save, "table fixture did not preserve full saved baseline")
    else:
        require(witness.file_digest(original) == digest, "manual source bytes changed")
    case["success"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    parser.add_argument("--scope", choices=tuple(witness.ENUM), required=True)
    parser.add_argument("--inheritance-drawing", type=Path, help="self-built synthetic input for read-only staging")
    parser.add_argument("--inheritance-sha256")
    font_worker_process.add_worker_options(parser)
    args = parser.parse_args(argv)
    supervision = font_worker_process.verify_worker_launch(args, parser)
    if args.supervision_probe:
        font_worker_process.write_worker_output(args.output_dir, supervision)
        return 0
    require(re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) is not None,
            "use the font watchdog with an exact source commit")
    witness.validate_drawing_input(args.scope, args.inheritance_drawing, args.inheritance_sha256)
    manual = None if args.inheritance_drawing is None else (args.inheritance_drawing, args.inheritance_sha256)
    require(args.scope == "tables" or manual is not None, "dimensions requires a self-built manual drawing")
    require(args.swconst.is_file() and args.drawing_template.is_file()
            and args.drawing_template.resolve().name.casefold() == "gb.drwdot"
            and not args.drawing_template.is_symlink(), "installed GB.drwdot and official swconst are required")
    require(fonts._native_windows_runtime(), "fixture preparation requires native Windows")
    font_worker_process.write_worker_output(args.output_dir, supervision)
    original = harness.read_constants

    def constants(pythoncom, path):
        return {**original(pythoncom, path), **fonts.read_font_constants(
            pythoncom, path, candidate_scope=args.scope, witness_enum=witness.ENUM[args.scope])}

    def runner(app, output, enum, plane, reverse, call, case, report, live, *, profile_kind):
        return run_case(app, output, enum, call, case, live, scope=args.scope,
                        template=args.drawing_template.resolve(), manual=manual)

    harness.read_constants = constants
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False, case_runner=runner,
                       case_plan=[("drawing", "front", False)], diagnostic_case="next-font-fixture-" + args.scope)


if __name__ == "__main__":
    raise SystemExit(main())
