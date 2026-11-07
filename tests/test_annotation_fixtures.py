"""Owned annotation inputs must retain three native types and fail before acceptance."""

import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/prepare-annotation-fixtures.py"
spec = importlib.util.spec_from_file_location("annotation_fixture_test", SCRIPT)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class AnnotationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.template = self.output / "explicit.drwdot"
        self.template.write_bytes(b"owned template")
        self.documents = []
        self.calls = []
        self.app = SimpleNamespace(GetDocumentCount=lambda: len(self.documents), GetProcessID=lambda: 7300,
                                   CloseDoc=self.close)
        self.live = {"document": None}
        self.report = {"host": {"process_id": 7300}}
        self.case = {}

    def document(self, kind):
        document = SimpleNamespace(GetType=lambda: kind, GetSaveFlag=lambda: False,
                                   GetTitle=lambda: "generated-" + str(kind))
        self.documents.append(document)
        return document

    def close(self, title):
        self.documents[:] = [d for d in self.documents if d.GetTitle() != title]

    def save(self, path, *, document):
        Path(path).write_bytes(b"owned native file" * 40)
        return {"ok": True, "api_saved": True, "save_errors": 0, "save_warnings": 0,
                "document": {"modified": False}}

    def reopen(self, path, *, app, read_only):
        kind = {".SLDPRT": 1, ".SLDASM": 2, ".SLDDRW": 3}[Path(path).suffix]
        return {"ok": True, "api_errors": 0, "api_warnings": 0, "read_only": read_only}, self.document(kind)

    def invoke(self, name, function):
        self.calls.append(name)
        return function()

    def prepare(self, kind, *, save=None, reopen=None, measure=None):
        metrics = {"solid_body_count": 1, "volume_mm3": 12000, "surface_area_mm2": 3800,
                   "centroid_mm": {"x": 20, "y": 15, "z": 5}}
        with (mock.patch.object(fixture, "create_part_windows_with_handle",
                                side_effect=lambda **kw: ({"ok": True}, self.document(1))),
              mock.patch.object(fixture, "create_assembly_windows_with_handle",
                                side_effect=lambda **kw: ({"ok": True}, self.document(2))),
              mock.patch.object(fixture, "create_drawing_windows_with_handle", side_effect=lambda **kw: (
                  {"ok": True, "views": [], "template": {"path": kw["template"]}}, self.document(3))) as drawing,
              mock.patch.object(fixture, "create_rectangle_sketch_windows_with_handle",
                                return_value=({"ok": True}, object())),
              mock.patch.object(fixture, "extrude_sketch_windows_with_handle",
                                return_value=({"ok": True}, object())),
              mock.patch.object(fixture, "measure_part_windows", side_effect=measure,
                                return_value={"ok": True, "metrics": metrics}),
              mock.patch.object(fixture, "save_as_native_windows", side_effect=save or self.save),
              mock.patch.object(fixture, "open_windows_document_with_handle", side_effect=reopen or self.reopen)):
            fixture.prepare_case(self.app, self.output, {}, "front", False, self.invoke, self.case,
                                 self.report, self.live, profile_kind=kind, drawing_template=self.template)
            if kind == "drawing":
                drawing.assert_called_once_with(app=self.app, template=str(self.template), projection="first-angle")

    def test_three_types_save_reopen_hash_and_cleanup_without_annotation_setters(self):
        for kind, (native_type, suffix) in fixture.KINDS.items():
            with self.subTest(kind=kind):
                self.case = {}
                self.calls = []
                self.prepare(kind)
                path = self.output / ("annotations." + suffix)
                self.assertTrue(path.is_file())
                self.assertEqual(self.case["document_type"], native_type)
                self.assertTrue(self.case["success"] and self.case["preparation_only"])
                self.assertEqual(self.case["file_sha256"], fixture.hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertIsNone(self.live["document"])
                self.assertEqual(self.documents, [])
                if kind == "part":
                    self.assertEqual(self.case["geometry"], self.case["geometry_reopened"])
                if kind == "drawing":
                    self.assertEqual(self.case["model_references"], [])
                self.assertFalse(any("annotation-option" in name or "SetUserPreference" in name for name in self.calls))

    def test_bad_part_geometry_stops_before_save_without_an_api_retry(self):
        with self.assertRaisesRegex(RuntimeError, "exactly one solid"):
            self.prepare("part", measure=lambda **kw: {"ok": True, "metrics": {"solid_body_count": 2}})
        self.assertNotIn("save-annotation-fixture", self.calls)
        self.assertEqual(self.calls.count("create-annotation-box"), 1)
        self.assertIsNotNone(self.live["document"])
        self.assertFalse(self.case["success"])

    def test_save_failure_retains_the_first_failure_and_never_reopens(self):
        with self.assertRaisesRegex(RuntimeError, "save cleanly"):
            self.prepare("assembly", save=lambda *args, **kw: {"ok": False})
        self.assertEqual(self.calls.count("save-annotation-fixture"), 1)
        self.assertNotIn("reopen-annotation-fixture-readonly", self.calls)
        self.assertFalse(self.case["success"])

    def test_reopen_byte_mutation_cannot_publish_success(self):
        def changed(path, **kwargs):
            Path(path).write_bytes(b"changed native file" * 40)
            return self.reopen(path, **kwargs)
        with self.assertRaisesRegex(RuntimeError, "changed its file"):
            self.prepare("drawing", reopen=changed)
        self.assertFalse(self.case["success"])
        self.assertEqual(self.calls.count("reopen-annotation-fixture-readonly"), 1)

    def test_main_requires_explicit_template_and_preserves_existing_evidence(self):
        constants = self.output / "swconst.tlb"
        constants.write_bytes(b"official test path")
        target = self.output / "evidence"
        arguments = ["--output-dir", str(target), "--swconst", str(constants),
                     "--drawing-template", str(self.template)]
        with mock.patch.object(fixture.harness, "run", return_value=0) as run:
            self.assertEqual(fixture.main(arguments), 0)
            self.assertEqual(run.call_args.kwargs["case_plan"],
                             [(kind, "front", False) for kind in ("part", "assembly", "drawing")])
            self.assertEqual(run.call_args.kwargs["diagnostic_case"], "document-annotations-fixture-preparation")
            self.assertIs(run.call_args.args[2], False)
        (target / "report.json").write_text("original")
        with mock.patch.object(fixture.harness, "run") as run:
            with self.assertRaises(FileExistsError):
                fixture.main(arguments)
            run.assert_not_called()
        self.assertEqual((target / "report.json").read_text(), "original")


if __name__ == "__main__":
    unittest.main()
