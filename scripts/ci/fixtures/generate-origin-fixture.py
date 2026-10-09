"""Regenerate the SW 2025 native rejection fixture, never a public CLI backend.

Run with Windows Python/pywin32 while no SOLIDWORKS instance is running:
    python generate-origin-fixture.py ABSOLUTE_NEW_OUTPUT.SLDPRT
The fixture intentionally uses UI inference to create a real origin relation.
The normal adapter disables inference; zero coordinates alone are not a fixture.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
import pythoncom
import win32com.client

from swcli.daemon.server import acquire_resident_app
from swcli.hosts.windows import _com_value, wait_windows_host_ready
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_native_files import save_as_part_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_rectangle_center import observe_rectangle_center
from swcli.hosts.windows_sketches import _features, _rectangle_verification, _standard_plane


def verify(app, document):
    feature = next(f for f in _features(document) if _com_value(f, "GetTypeName2") == "ProfileFeature")
    sketch = _com_value(feature, "GetSpecificFeature2")
    geometry = _rectangle_verification(sketch, {"min_x": -20, "max_x": 20, "min_y": -15, "max_y": 15})
    assert geometry["passed"], geometry
    points = tuple(_com_value(sketch, "GetSketchPoints2"))
    center = next(p for p in points if int(_com_value(p, "Type")) == 1 and
                  all(abs(float(_com_value(p, axis))) < 1e-12 for axis in ("X", "Y", "Z")))
    relations = [{"type": _com_value(r, "GetRelationType"),
                  "entity_types": list(_com_value(r, "GetEntitiesType"))}
                 for r in _com_value(center, "GetRelations")]
    assert sum(r["type"] == 9 and sorted(r["entity_types"]) == [2, 2] for r in relations) == 1, relations
    assert sum(r["type"] == 9 and sorted(r["entity_types"]) == [2, 3] for r in relations) == 2, relations
    try:
        observe_rectangle_center(app, sketch)
    except Exception as error:
        assert error.code == "UnsupportedCenterConstraint", str(error)
    else:
        raise AssertionError("fixture does not exercise the native relation refusal")
    return {"geometry": geometry, "center_relations": relations}


def main():
    output = Path(sys.argv[1]).resolve()
    assert output.is_absolute() and not output.exists() and output.parent.is_dir()
    pythoncom.CoInitialize()
    app = None
    inference = command = None
    document = None
    try:
        app, owned = acquire_resident_app(win32com.client, visible=True)
        assert owned
        wait_windows_host_ready(app, timeout_seconds=150)
        inference = app.GetUserPreferenceToggle(249)
        command = app.CommandInProgress
        app.CommandInProgress = True
        app.SetUserPreferenceToggle(249, True)
        assert app.GetUserPreferenceToggle(249) is True
        created, document = create_part_windows_with_handle(app=app)
        assert created["ok"], created
        plane = _standard_plane(document, "front")
        document.ClearSelection2(True)
        assert plane.Select2(False, 0)
        manager = _com_value(document, "SketchManager")
        manager.InsertSketch(True)
        manager.AddToDB = False
        manager.CreateCenterRectangle(0, 0, 0, .020, .015, 0)
        manager.InsertSketch(True)
        document.ClearSelection2(True)
        before = verify(app, document)
        saved = save_as_part_windows(str(output), document=document)
        assert saved["ok"], saved
        app.CloseDoc(_com_value(document, "GetTitle"))
        document = None
        opened, document = open_windows_document_with_handle(str(output), app=app, read_only=True)
        assert opened["ok"], opened
        after = verify(app, document)
        assert before == after, (before, after)
        print(json.dumps({"output": str(output), "revision": _com_value(app, "RevisionNumber"),
                          "before_save": before, "after_reopen": after}, indent=2))
    finally:
        if app is not None:
            if document is not None:
                app.CloseDoc(_com_value(document, "GetTitle"))
            if inference is not None:
                app.SetUserPreferenceToggle(249, inference)
                assert app.GetUserPreferenceToggle(249) == inference
            if command is not None:
                app.CommandInProgress = command
            app.ExitApp()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
