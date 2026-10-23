"""Explicit-template, single-sheet standard drawings on the owning STA thread.

Native evidence is retained on failure; insertion is never retried or rolled back.
Geometry evidence uses native sheet meters, not pixel positions.
"""
import ntpath
from pathlib import Path

from .drawing_geometry import numbers, require, standard_layout
from .native_trace import native_call
from .windows import _com_value, _describe_document, _error
from .windows_documents import _diagnose_features


def _get(obj, name):
    return native_call("drawing", name, lambda: _com_value(obj, name))


def _dispatch(obj):
    if hasattr(obj, "_oleobj_"):
        return obj
    import win32com.client
    return win32com.client.Dispatch(obj)


def _sheet(document):
    sheet = _get(document, "GetCurrentSheet")
    properties = list(_get(sheet, "GetProperties2"))
    require(len(properties) == 8, "invalid sheet properties length")
    # Native flags may be BOOLs; normalize only those, never arbitrary values.
    for index in (4, 7):
        require(properties[index] in (0, 1, False, True), "invalid sheet flag")
        properties[index] = int(properties[index])
    numbers(properties, 8, "sheet properties")
    require(properties[0] == 6 and min(properties[2:4]) > 0
            and min(properties[5:7]) > 0, "only calibrated A4 sheets are supported")
    path = _get(sheet, "GetTemplateName")
    return sheet, dict(name=_get(sheet, "GetName"), properties=properties, unit="meter",
        format_path=path, format_available=bool(path and Path(path).is_file()),
        projection="first-angle" if properties[4] else "third-angle")


def _observe(document, result):
    _, result["sheet"] = _sheet(document)
    groups = _get(document, "GetViews")
    require(len(groups) == 1, "drawing must contain exactly one sheet")
    group = groups[0]
    require(1 <= len(group) <= 33, "invalid or excessive view count")
    result["views"] = []
    for index, raw in enumerate(group):
        view = _dispatch(raw)
        path = _get(view, "GetReferencedModelName")
        if index == 0:
            require(not path, "sheet pseudo-view references a model")
            continue
        require(bool(path), "non-sheet view lacks model reference")
        record = dict(name=_get(view, "GetName2"), path=path, unit="meter", coordinate_system="sheet",
            configuration=_get(view, "ReferencedConfiguration"),
            position=list(_get(view, "Position")), outline=list(_get(view, "GetOutline")),
            scale=list(_get(view, "ScaleRatio")),
            transform=list(_get(_get(view, "ModelToViewTransform"), "ArrayData")))
        for key, count in (("position", 2), ("outline", 4), ("scale", 2), ("transform", 16)):
            numbers(record[key], count, "view " + key)
        result["views"].append(record)


def _empty_target(document, result):
    require(_get(document, "GetType") == 3, "target must be a drawing")
    require(_get(document, "IsOpenedReadOnly") is False and
            _get(document, "IsOpenedViewOnly") is False, "drawing is not writable")
    require(_get(document, "GetEditSheet") is True, "drawing must be in sheet, not format editing mode")
    _observe(document, result)
    require(not result["views"], "drawing already contains model views")


def _active(app, document):
    active = _get(app, "ActiveDoc")
    require(active is not None and native_call("drawing", "IsSame(active)",
            lambda: app.IsSame(active, document)) == 1, "target drawing is not active")


def _source(document):
    state = dict(path=_get(document, "GetPathName"), type=_get(document, "GetType"),
        modified=_get(document, "GetSaveFlag"), update_stamp=_get(document, "GetUpdateStamp"),
        needs_rebuild=_get(_get(document, "Extension"), "NeedsRebuild2"),
        configuration=_get(_get(_get(document, "ConfigurationManager"), "ActiveConfiguration"), "Name"))
    require(state["type"] in (1, 2), "source must be part or assembly")
    require(type(state["modified"]) is bool and type(state["needs_rebuild"]) is int
            and type(state["update_stamp"]) is int, "source state unavailable")
    return state


def _healthy(document):
    diagnostics = _diagnose_features(document, 500)
    require(diagnostics["healthy"] and not diagnostics["truncated"], "document diagnostics not clean or incomplete")
    return diagnostics


def create_drawing_windows_with_handle(*, app, template, projection):
    result = dict(ok=False, action="document.create", cleanup_errors=[])
    document = None
    try:
        require(projection in ("first-angle", "third-angle"), "explicit projection required")
        path = Path(template).expanduser().resolve()
        require(path.suffix.casefold() == ".drwdot" and path.is_file() and path.stat().st_size > 0,
                "template must be an existing nonempty DRWDOT")
        result["template"] = dict(ok=True, path=str(path), source="explicit")
        document = native_call("drawing-create", "NewDocument", lambda: app.NewDocument(str(path), 6, 0.0, 0.0))
        require(document is not None, "NewDocument returned null")
        result["created"] = True
        result["document"] = _describe_document(document)
        _active(app, document)
        _empty_target(document, result)
        before = result["sheet"]
        sheet, _ = _sheet(document)
        args = list(before["properties"])
        args[0], args[1], args[7] = int(args[0]), int(args[1]), bool(args[7])
        args[4] = projection == "first-angle"
        native_call("drawing-create", "SetProperties2", lambda: sheet.SetProperties2(*args))
        require(native_call("drawing-create", "ForceRebuild3", lambda: document.ForceRebuild3(False)) is True,
                "projection rebuild failed")
        _observe(document, result)
        expected = dict(before, properties=args, projection=projection)
        require(result["sheet"] == expected, "projection changed unrelated sheet settings")
        result["diagnostics"] = _healthy(document)
        if before["format_path"] and not before["format_available"]:
            result["warnings"] = [dict(code="DrawingFormatUnavailable", message="embedded format path is unavailable; retained unchanged")]
        result["ok"] = True
    except Exception as error:
        result["error"] = _error(error)
    return result, document


def insert_standard_views_windows(*, app, document, source_document, configuration):
    result = dict(ok=False, action="drawing.standard-views", cleanup_errors=[],
        mutation=dict(attempted=False, may_have_changed=False),
        verification=dict(passed=False, source_unchanged=False, layout_verified=False))
    before = None
    try:
        _active(app, document)
        _empty_target(document, result)
        before = _source(source_document)
        result["source"] = before
        require(before["path"] and Path(before["path"]).is_file(), "source must be saved and present")
        require(not before["modified"] and before["needs_rebuild"] == 0, "source must be clean and rebuilt")
        require(bool(configuration) and configuration == before["configuration"], "configuration must match saved active configuration")
        require(_get(_get(source_document, "SketchManager"), "ActiveSketch") is None,
                "source sketch edit in progress")
        _healthy(source_document)
        method = "Create1stAngleViews2" if result["sheet"]["projection"] == "first-angle" else "Create3rdAngleViews2"
        result["mutation"] = dict(attempted=True, may_have_changed=True)
        require(native_call("drawing-insert", method, lambda: getattr(document, method)(before["path"])) is True,
                "standard view insertion failed; do not retry")
        result["rebuilt"] = _get(document, "EditRebuild3")
        require(result["rebuilt"] is True, "drawing rebuild failed")
        _observe(document, result)
        require(len(result["views"]) == 3, "expected exactly three model views")
        normalize = lambda p: ntpath.normcase(ntpath.normpath(p))
        for view in result["views"]:
            require(normalize(view["path"]) == normalize(before["path"]) and view["configuration"] == configuration,
                    "view source/configuration mismatch")
        standard_layout(result, result["sheet"]["projection"])
        for view in result["views"]:
            matrix = view["transform"][:9]
            view["role"] = ("front" if all(abs(a-b) <= 1e-9 for a,b in zip(matrix, [1, 0, 0, 0, 1, 0, 0, 0, 1])) else
                "top" if abs(matrix[0]-1) < 1e-9 else
                "left" if result["sheet"]["projection"] == "first-angle" else "right")
        result["verification"]["layout_verified"] = True
        result["diagnostics"] = _healthy(document)
        result["ok"] = True
    except Exception as error:
        result["error"] = _error(error)
    finally:
        if before is not None:
            try:
                after = _source(source_document)
                require(before == after, "drawing operation changed source state")
                result["verification"]["source_unchanged"] = True
            except Exception as error:
                result.setdefault("error", _error(error))
                result["ok"] = False
        if result["mutation"]["attempted"] and not result["ok"]:
            try:
                _observe(document, result)
            except Exception as error:
                result["cleanup_errors"].append(dict(stage="observe-partial-drawing", error=_error(error)))
        result["verification"]["passed"] = result["ok"]
    return result
