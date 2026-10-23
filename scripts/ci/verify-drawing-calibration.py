"""Opt-in native drawing observation; no public operation or sheet-setting changes.

Use Windows Python with installed SWCLI. The output directory must be new.
The template's actual projection selects the one standard-three-view call.
"""

import argparse
import hashlib
import json
import math
import ntpath
from pathlib import Path
import time
import traceback

from swcli.daemon.server import acquire_resident_app
from swcli.hosts.windows import _com_value, wait_windows_host_ready
from swcli.hosts.windows_parts import create_box_part_windows_with_handle
from swcli.hosts.windows_documents import open_windows_document_with_handle


def checked(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_paper_constant(com, path):
    library = com.LoadTypeLib(str(path))
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind == com.TKIND_ENUM:
            for offset in range(attributes.cVars):
                descriptor = info.GetVarDesc(offset)
                if info.GetDocumentation(descriptor[0])[0] == "swDwgPaperA4size":
                    return descriptor.value
    raise RuntimeError("official library lacks swDwgPaperA4size")


def normalized(path):
    return ntpath.normcase(ntpath.normpath(path))


def dispatch_view(view):
    """GetViews SAFEARRAY elements can be raw PyIDispatch rather than CDispatch."""
    if hasattr(view, "_oleobj_"):
        return view
    import win32com.client
    return win32com.client.Dispatch(view)


def view_record(view):
    return dict(name=_com_value(view, "GetName2"),
        source=_com_value(view, "GetReferencedModelName"),
        configuration=_com_value(view, "ReferencedConfiguration"),
        position=list(_com_value(view, "Position")),
        outline=list(_com_value(view, "GetOutline")),
        scale=list(_com_value(view, "ScaleRatio")),
        transform=list(_com_value(_com_value(view, "ModelToViewTransform"), "ArrayData")))


def source_state(part):
    return dict(path=_com_value(part, "GetPathName"), modified=_com_value(part, "GetSaveFlag"),
        update_stamp=_com_value(part, "GetUpdateStamp"),
        configuration=_com_value(_com_value(_com_value(part, "ConfigurationManager"), "ActiveConfiguration"), "Name"))


def projection_arguments(properties, projection):
    checked(len(properties) == 8 and all(math.isfinite(x) for x in properties), "unrecognized sheet properties")
    checked(projection in ("first-angle", "third-angle"), "invalid projection")
    return (int(properties[0]), int(properties[1]), properties[2], properties[3],
            projection == "first-angle", properties[5], properties[6], bool(properties[7]))


def check_projection_change(before, after, projection):
    checked(before["template"] == after["template"] and before["name"] == after["name"],
            "projection setting changed sheet name or format path")
    expected = list(before["properties"])
    expected[4] = projection == "first-angle"
    checked(after["properties"] == expected, "projection setting changed unrelated sheet properties")


def observe(drawing, call, report, label):
    snapshot = report.setdefault(label, {})
    sheet = call(label + ".GetCurrentSheet", lambda: _com_value(drawing, "GetCurrentSheet"))
    snapshot["sheet"] = dict(name=call(label + ".sheet.GetName", lambda: _com_value(sheet, "GetName")),
        properties=call(label + ".sheet.GetProperties2", lambda: list(_com_value(sheet, "GetProperties2"))),
        template=call(label + ".sheet.GetTemplateName", lambda: _com_value(sheet, "GetTemplateName")))
    snapshot["sheet"]["template_exists"] = Path(snapshot["sheet"]["template"]).is_file()
    groups = call(label + ".GetViews", lambda: _com_value(drawing, "GetViews"))
    snapshot["group_sizes"] = [len(group) for group in groups]
    snapshot["sheet_pseudo_views"] = []
    snapshot["views"] = []
    for group in groups:
        checked(bool(group), "sheet view array is empty")
        for index, raw_view in enumerate(group):
            view = dispatch_view(raw_view)
            source = call(label + ".view.source", lambda v=view: _com_value(v, "GetReferencedModelName"))
            if index == 0:
                checked(not source, "first sheet pseudo-view unexpectedly references a model")
                snapshot["sheet_pseudo_views"].append(dict(source=source,
                    name=call(label + ".pseudo.GetName2", lambda v=view: _com_value(v, "GetName2"))))
                continue
            checked(bool(source), "non-sheet view has no model reference; cannot classify")
            snapshot["views"].append(call(label + ".view.record", lambda v=view: view_record(v)))
    return snapshot


def verify_views(snapshot, source, configuration):
    checked(len(snapshot["group_sizes"]) == 1, "expected exactly one sheet")
    checked(len(snapshot["views"]) == 3, "expected exactly three model views, excluding sheet pseudo-view")
    for view in snapshot["views"]:
        checked(normalized(view["source"]) == normalized(source), "view source differs from generated fixture")
        checked(view["configuration"] == configuration, "view configuration differs from saved fixture")
        for key in ("position", "outline", "scale", "transform"):
            checked(bool(view[key]) and all(math.isfinite(x) for x in view[key]), "invalid view " + key)
        checked(len(view["outline"]) == 4 and view["outline"][2] > view["outline"][0]
                and view["outline"][3] > view["outline"][1], "degenerate view outline")
        checked(len(view["scale"]) == 2 and min(view["scale"]) > 0, "invalid view scale")


def run(output, template, swconst, visible, projection=None):
    report = dict(success=False, cleanup_errors=[], template=str(template),
                  template_sha256=hashlib.sha256(template.read_bytes()).hexdigest())
    app = com = process = None
    owned = initialized = False
    documents = []
    def checkpoint():
        (output / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    with (output / "trace.jsonl").open("w", encoding="utf-8", buffering=1) as trace:
        def call(name, function):
            trace.write(json.dumps(dict(call=name, phase="begin", time=time.time())) + "\n")
            checkpoint()
            try:
                result = function()
            except BaseException as error:
                trace.write(json.dumps(dict(call=name, phase="error", error=str(error))) + "\n")
                raise
            trace.write(json.dumps(dict(call=name, phase="end", time=time.time())) + "\n")
            checkpoint()
            return result
        try:
            import pythoncom as com
            import win32com.client as client
            import win32api
            import win32con
            import win32event
            com.CoInitialize()
            initialized = True
            paper = call("read-paper-enum", lambda: read_paper_constant(com, swconst))
            report["new_document_arguments"] = dict(paper=paper, width=0, height=0)
            app, owned = call("acquire-owned-host", lambda: acquire_resident_app(client, visible=visible))
            checked(owned, "refuse shared host")
            call("wait-ready", lambda: wait_windows_host_ready(app, timeout_seconds=120))
            report["host"] = dict(pid=_com_value(app, "GetProcessID"), revision=_com_value(app, "RevisionNumber"))
            process = win32api.OpenProcess(win32con.SYNCHRONIZE, False, report["host"]["pid"])
            source = str(output / "fixture.SLDPRT")
            result, part = call("create-saved-box", lambda: create_box_part_windows_with_handle(
                source, width_mm=40, height_mm=30, depth_mm=10, app=app))
            if part is not None:
                documents.append(part)
            report["fixture"] = result
            checked(result["ok"] and part is not None, "box creation failed")
            checked(not _com_value(part, "GetSaveFlag"), "source fixture is not saved clean")
            report["source_before"] = call("source.before", lambda: source_state(part))
            configuration = report["source_before"]["configuration"]
            drawing = call("NewDocument", lambda: app.NewDocument(str(template), paper, 0.0, 0.0))
            checked(drawing is not None, "drawing creation returned null")
            documents.append(drawing)
            checked(_com_value(drawing, "GetType") == 3, "template did not create drawing")
            before = observe(drawing, call, report, "before")
            checked(len(before["group_sizes"]) == 1 and not before["views"], "template must have one empty sheet")
            if projection is not None:
                sheet = _com_value(drawing, "GetCurrentSheet")
                arguments = projection_arguments(before["sheet"]["properties"], projection)
                call("sheet.SetProperties2", lambda: sheet.SetProperties2(*arguments))
                call("ForceRebuild3.projection", lambda: drawing.ForceRebuild3(False))
                configured = observe(drawing, call, report, "configured")
                check_projection_change(before["sheet"], configured["sheet"], projection)
                before = configured
            properties = before["sheet"]["properties"]
            checked(len(properties) >= 7 and properties[4] in (0, 1, False, True), "unrecognized sheet properties")
            report["projection"] = "first-angle" if properties[4] else "third-angle"
            method = "Create1stAngleViews2" if properties[4] else "Create3rdAngleViews2"
            checked(call(method, lambda: getattr(drawing, method)(source)), "standard view insertion failed; do not retry")
            checked(call("EditRebuild3", lambda: _com_value(drawing, "EditRebuild3")), "drawing rebuild failed")
            after = observe(drawing, call, report, "after")
            verify_views(after, source, configuration)
            checked(not _com_value(part, "GetSaveFlag"), "view insertion modified source fixture")
            report["source_after_insertion"] = call("source.after-insertion", lambda: source_state(part))
            checked(report["source_before"] == report["source_after_insertion"], "view insertion changed source state")
            saved = output / "fixture.SLDDRW"
            checked(call("SaveAs3", lambda: drawing.SaveAs3(str(saved), 0, 1)) == 0 and saved.is_file()
                    and saved.stat().st_size > 0, "native drawing save failed")
            call("CloseDrawing", lambda: app.CloseDoc(_com_value(drawing, "GetTitle")))
            documents.remove(drawing)
            result, reopened = call("OpenDrawing", lambda: open_windows_document_with_handle(str(saved), app=app))
            report["reopen"] = result
            if reopened is not None:
                documents.append(reopened)
            checked(result["ok"] and reopened is not None, "drawing reopen failed")
            verify_views(observe(reopened, call, report, "reopened"), source, configuration)
            report["source_after_reopen"] = call("source.after-reopen", lambda: source_state(part))
            checked(report["source_before"] == report["source_after_reopen"], "drawing save/reopen changed source state")
            report["validation_scope"] = "native observation and reference/configuration persistence; direction/layout validation pending"
            report["success"] = True
        except BaseException as error:
            report["failure"] = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
        finally:
            cleanup = [("CloseDoc", lambda d=d: app.CloseDoc(_com_value(d, "GetTitle"))) for d in reversed(documents)]
            if owned:
                cleanup.append(("ExitApp", lambda: _com_value(app, "ExitApp")))
            if process is not None:
                cleanup.extend([("WaitOwnedProcess", lambda: checked(win32event.WaitForSingleObject(process, 10000)
                    == win32event.WAIT_OBJECT_0, "owned process exit not confirmed")), ("CloseHandle", process.Close)])
            if initialized:
                cleanup.append(("CoUninitialize", com.CoUninitialize))
            for name, function in cleanup:
                try:
                    call(name, function)
                except Exception as error:
                    report["cleanup_errors"].append(dict(stage=name, message=str(error)))
    report["success"] = report["success"] and not report["cleanup_errors"]
    checkpoint()
    return 0 if report["success"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--hidden", action="store_true", help="default is visible")
    parser.add_argument("--projection", choices=("first-angle", "third-angle"),
                        help="set only sheet projection, then read back every sheet property; omitted observes template")
    args = parser.parse_args(argv)
    if args.template.suffix.lower() != ".drwdot" or not args.template.is_file() or not args.template.stat().st_size:
        parser.error("--template must be an existing nonempty DRWDOT")
    if not args.swconst.is_file():
        parser.error("--swconst must exist")
    try:
        args.output_dir.mkdir()
    except OSError as error:
        parser.error("--output-dir must be new: " + str(error))
    return run(args.output_dir.resolve(), args.template.resolve(), args.swconst.resolve(), not args.hidden, args.projection)


if __name__ == "__main__":
    raise SystemExit(main())
