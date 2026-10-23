"""Portable calibration guards, not native drawing proof."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("drawing_calibration",
    Path(__file__).resolve().parents[1] / "scripts/ci/verify-drawing-calibration.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class DrawingCalibrationTests(unittest.TestCase):
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
                self.assertTrue(run.call_args.args[-1])
                with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                    gate.main(args)
                self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
