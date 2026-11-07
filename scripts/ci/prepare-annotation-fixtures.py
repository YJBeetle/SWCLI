"""Prepare owned native inputs for public annotation verification, without editing annotation preferences."""

import argparse
import hashlib
import importlib.util
import math
import sys
from pathlib import Path

from swcli.hosts.windows import _com_value
from swcli.hosts.windows_assemblies import create_assembly_windows_with_handle
from swcli.hosts.windows_documents import open_windows_document_with_handle, _inspect_configurations
from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle

spec = importlib.util.spec_from_file_location(
    "_annotation_fixture_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py")
)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.drawing_checks import empty_drawing_configurations

KINDS = {"part": (1, "SLDPRT"), "assembly": (2, "SLDASM"), "drawing": (3, "SLDDRW")}


def part_geometry(document, call):
    measured = call("measure-annotation-part", lambda: measure_part_windows(document=document))
    checked(measured["ok"], "annotation part measurement failed")
    harness.verify_geometry(measured["metrics"], 10, cut=False)
    return measured["metrics"]


def prepare_case(app, output, constants, plane, reverse, call, case, report, live,
                 *, profile_kind, drawing_template):
    kind, suffix = KINDS[profile_kind]
    case.update(kind=profile_kind, document_type=kind, preparation_only=True, success=False)
    if profile_kind == "drawing":
        made, document = call("create-annotation-drawing", lambda: create_drawing_windows_with_handle(
            app=app, template=str(drawing_template), projection="first-angle"))
    else:
        creator = create_part_windows_with_handle if kind == 1 else create_assembly_windows_with_handle
        made, document = call("create-annotation-" + profile_kind, lambda: creator(app=app))
    live["document"] = document
    case["creation"] = made
    checked(made["ok"] and document is not None and _com_value(document, "GetType") == kind,
            "annotation fixture creation failed or returned the wrong document type")
    if kind == 1:
        rectangle, sketch = call("create-annotation-box-profile", lambda: create_rectangle_sketch_windows_with_handle(
            app=app, document=document, plane="front", width_mm=40, height_mm=30))
        case["profile"] = rectangle
        checked(rectangle["ok"] and sketch is not None and not rectangle.get("warnings"),
                "annotation box profile creation or restoration failed")
        boss, feature = call("create-annotation-box", lambda: extrude_sketch_windows_with_handle(
            app=app, document=document, sketch_feature=sketch, depth_mm=10))
        case["boss"] = boss
        checked(boss["ok"] and feature is not None and not boss.get("warnings"),
                "annotation box creation or restoration failed")
        case["geometry"] = part_geometry(document, call)
        sketch = feature = None
    if kind == 3:
        checked(made["views"] == [] and made["template"]["path"] == str(drawing_template),
                "annotation drawing must use its explicit template without model references")
        case["drawing_template"] = str(drawing_template)
        case["model_references"] = []
        case["configurations_before"] = call("read-drawing-empty-configurations-before",
                                             lambda: _inspect_configurations(document))
        empty_drawing_configurations(case["configurations_before"])
    path = output / ("annotations." + suffix)
    case["path"] = str(path)
    case["save"] = call("save-annotation-fixture", lambda: save_as_native_windows(str(path), document=document))
    saved = case["save"]
    checked(saved["ok"] and saved["api_saved"] and saved["save_errors"] == 0
            and saved["save_warnings"] == 0 and not saved["document"]["modified"]
            and path.is_file() and path.stat().st_size >= 512,
            "annotation fixture did not save cleanly")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    case["file_size_bytes"] = path.stat().st_size
    title = _com_value(document, "GetTitle")
    live["document"] = document = None
    call("close-annotation-fixture", lambda: app.CloseDoc(title))
    checked(_com_value(app, "GetDocumentCount") == 0, "saved annotation fixture remains open")
    opened, document = call("reopen-annotation-fixture-readonly", lambda: open_windows_document_with_handle(
        str(path), app=app, read_only=True))
    live["document"] = document
    case["reopen"] = opened
    checked(opened["ok"] and opened["api_errors"] == opened["api_warnings"] == 0
            and opened["read_only"] is True and document is not None
            and _com_value(document, "GetType") == kind and not _com_value(document, "GetSaveFlag"),
            "annotation fixture did not reopen read-only and cleanly with its original type")
    if kind == 3:
        case["configurations_reopened"] = call("read-drawing-empty-configurations-reopened",
                                               lambda: _inspect_configurations(document))
        empty_drawing_configurations(case["configurations_reopened"])
    if kind == 1:
        case["geometry_reopened"] = part_geometry(document, call)
        for key in ("volume_mm3", "surface_area_mm2"):
            checked(math.isclose(case["geometry"][key], case["geometry_reopened"][key], rel_tol=1e-9, abs_tol=1e-6),
                    "annotation part geometry changed after reopening")
        checked(all(math.isclose(case["geometry"]["centroid_mm"][axis], case["geometry_reopened"]["centroid_mm"][axis],
                                 rel_tol=0, abs_tol=1e-6) for axis in ("x", "y", "z")),
                "annotation part centroid changed after reopening")
    checked(hashlib.sha256(path.read_bytes()).hexdigest() == digest and not _com_value(document, "GetSaveFlag"),
            "annotation fixture readback changed its file or modified flag")
    case["file_sha256"] = digest
    title = _com_value(document, "GetTitle")
    live["document"] = document = None
    call("close-reopened-annotation-fixture", lambda: app.CloseDoc(title))
    checked(_com_value(app, "GetDocumentCount") == 0, "reopened annotation fixture remains open")
    checked(_com_value(app, "GetProcessID") == report["host"]["process_id"], "annotation fixture preparation changed host")
    case["success"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    args = parser.parse_args(argv)
    checked(args.swconst.is_file(), "official swconst type library is required")
    checked(args.drawing_template.is_file() and not args.drawing_template.is_symlink()
            and args.drawing_template.suffix.lower() == ".drwdot" and args.drawing_template.stat().st_size > 0,
            "an explicit regular nonempty drawing template is required")
    args.output_dir.mkdir()

    def case_runner(*arguments, **keywords):
        return prepare_case(*arguments, **keywords, drawing_template=args.drawing_template.resolve())

    return harness.run(
        args.output_dir.resolve(), args.swconst.resolve(), False,
        case_runner=case_runner,
        case_plan=[(kind, "front", False) for kind in KINDS],
        diagnostic_case="document-annotations-fixture-preparation",
    )


if __name__ == "__main__":
    raise SystemExit(main())
