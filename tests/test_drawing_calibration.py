"""Portable calibration guards, not native drawing proof."""
import copy
import importlib.util
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("drawing_calibration",
    Path(__file__).resolve().parents[1] / "scripts/ci/verify-drawing-calibration.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class DrawingCalibrationTests(unittest.TestCase):
    def test_projection_preserves_every_other_property(self):
        properties = [6, 12, 1, 1, 1, .297, .21, 1]
        self.assertEqual(gate.projection_arguments(properties, "third-angle"),
                         (6, 12, 1, 1, False, .297, .21, True))
        before = dict(name="Sheet1", template="original.slddrt", properties=properties)
        after = copy.deepcopy(before)
        after["properties"][4] = False
        gate.check_projection_change(before, after, "third-angle")
        for index in (0, 1, 2, 3, 5, 6, 7):
            changed = copy.deepcopy(after)
            changed["properties"][index] += 1
            with self.subTest(index=index), self.assertRaises(RuntimeError):
                gate.check_projection_change(before, changed, "third-angle")
        after["template"] = "replaced.slddrt"
        with self.assertRaises(RuntimeError):
            gate.check_projection_change(before, after, "third-angle")

    def test_raw_dispatch_is_wrapped_but_existing_wrapper_is_preserved(self):
        raw = object()
        wrapped = SimpleNamespace(_oleobj_=object())
        client = ModuleType("win32com.client")
        client.Dispatch = mock.Mock(return_value=wrapped)
        package = ModuleType("win32com")
        package.client = client
        with mock.patch.dict("sys.modules", {"win32com": package, "win32com.client": client}):
            self.assertIs(gate.dispatch_view(raw), wrapped)
            self.assertIs(gate.dispatch_view(wrapped), wrapped)
            client.Dispatch.assert_called_once_with(raw)

    def test_observe_requires_documented_sheet_first_and_model_references(self):
        sheet = SimpleNamespace(GetName="Sheet1", GetProperties2=[6, 12, 1, 1, 1, .297, .21, 1], GetTemplateName="format")
        pseudo = SimpleNamespace(GetReferencedModelName="", GetName2="Sheet1")
        unknown = SimpleNamespace(GetReferencedModelName="")
        drawing = SimpleNamespace(GetCurrentSheet=sheet, GetViews=((pseudo, unknown),))
        with mock.patch.object(gate, "dispatch_view", side_effect=lambda value: value):
            with self.assertRaisesRegex(RuntimeError, "cannot classify"):
                gate.observe(drawing, lambda name, function: function(), {}, "before")
            drawing.GetViews = ((SimpleNamespace(GetReferencedModelName="wrong"),),)
            with self.assertRaisesRegex(RuntimeError, "pseudo-view"):
                gate.observe(drawing, lambda name, function: function(), {}, "before")

    def snapshot(self):
        view = dict(source="C:\\fixture.SLDPRT", configuration="Default", position=[0.1, 0.1, 0],
                    outline=[0.01, 0.01, 0.1, 0.1], scale=[1, 2], transform=[1, 0, 0])
        return dict(group_sizes=[4], views=[copy.deepcopy(view) for _ in range(3)])

    def test_exact_three_model_views_and_reference(self):
        gate.verify_views(self.snapshot(), "c:/fixture.sldprt", "Default")
        for field, value in (("source", "C:\\other.SLDPRT"), ("configuration", "Other"),
                             ("outline", [0, 0, 0, 0]), ("position", [float("nan")]),
                             ("scale", [0, 1]), ("transform", [])):
            snapshot = self.snapshot()
            snapshot["views"][0][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                gate.verify_views(snapshot, "C:\\fixture.SLDPRT", "Default")

    def test_sheet_pseudo_view_not_counted_as_model(self):
        snapshot = self.snapshot()
        snapshot["views"].pop()
        with self.assertRaisesRegex(RuntimeError, "exactly three"):
            gate.verify_views(snapshot, "C:\\fixture.SLDPRT", "Default")
        snapshot = self.snapshot()
        snapshot["group_sizes"] = [4, 1]
        with self.assertRaisesRegex(RuntimeError, "one sheet"):
            gate.verify_views(snapshot, "C:\\fixture.SLDPRT", "Default")

    def test_fresh_directory_and_explicit_drwdot_before_com(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template = root / "official.DRWDOT"
            template.write_bytes(b"test")
            library = root / "swconst.tlb"
            library.write_bytes(b"test")
            with mock.patch.object(gate, "run", return_value=0) as run:
                args = ["--template", str(template), "--swconst", str(library), "--output-dir", str(root / "new")]
                self.assertEqual(gate.main(args), 0)
                self.assertTrue(run.call_args.args[3])
                self.assertEqual(run.call_args.args[5:], ("part", False))
                with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                    gate.main(args)
                self.assertEqual(run.call_count, 1)

    def test_assembly_and_strict_exports_are_explicit_options(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template = root / "official.drwdot"
            template.write_bytes(b"test")
            library = root / "swconst.tlb"
            library.write_bytes(b"test")
            with mock.patch.object(gate, "run", return_value=0) as run:
                gate.main(["--template", str(template), "--swconst", str(library),
                    "--output-dir", str(root / "new"), "--source-kind", "assembly",
                    "--exports", "--projection", "third-angle"])
                self.assertEqual(run.call_args.args[4:], ("third-angle", "assembly", True))


if __name__ == "__main__":
    unittest.main()
