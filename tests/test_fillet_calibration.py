"""Portable guard tests; these do not substitute for installed native calibration."""

import importlib.util
from collections import namedtuple
import json
import math
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-fillet-calibration.py"
spec = importlib.util.spec_from_file_location("fillet_calibration", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class FilletCalibrationTests(unittest.TestCase):
    def test_constants_are_read_from_type_library_not_assumed(self):
        descriptor = namedtuple("Descriptor", "memid value")
        names = ("swFmFillet", "swConstRadiusFillet", "swFeatureFilletCircular")
        values = (11, 22, 33)  # Deliberately not the installed native values.
        info = SimpleNamespace(GetTypeAttr=lambda: SimpleNamespace(typekind=0, cVars=3),
            GetVarDesc=lambda index: descriptor(index, values[index]),
            GetDocumentation=lambda index: (names[index],))
        library = SimpleNamespace(GetTypeInfoCount=lambda: 1, GetTypeInfo=lambda index: info)
        com = SimpleNamespace(TKIND_ENUM=0, LoadTypeLib=mock.Mock(return_value=library))
        self.assertEqual(gate.read_constants(com, Path("official.tlb")), dict(zip(names, values)))
        com.LoadTypeLib.assert_called_once_with("official.tlb")
        info.GetTypeAttr = lambda: SimpleNamespace(typekind=0, cVars=2)
        with self.assertRaisesRegex(RuntimeError, "lacks required enums"):
            gate.read_constants(com, Path("official.tlb"))

    def test_known_convex_volume(self):
        removed = (1 - math.pi / 4) * 4 * 10
        result = gate.verify_geometry(12000, 12000 - removed, 1, 10)
        self.assertAlmostEqual(result["removed_mm3"], removed)
        for args in ((12000, 12000, 1, 10), (12000, 12000-removed, 2, 10),
                     (12000, float("nan"), 1, 10), (11000, 11000-removed, 1, 10),
                     (12000, 12000-removed, 1, 0)):
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                gate.verify_geometry(*args)

    def test_existing_directory_and_missing_library_are_rejected_before_com(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "swconst.tlb"
            library.write_bytes(b"test-owned-placeholder")
            marker = root / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")
            with mock.patch.object(gate, "run") as run, mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit):
                    gate.main(["--output-dir", str(root), "--swconst", str(library)])
                with self.assertRaises(SystemExit):
                    gate.main(["--output-dir", str(root/"new"), "--swconst", str(root/"absent")])
                run.assert_not_called()
            self.assertEqual(marker.read_text(), "preserve")
            self.assertFalse((root / "new").exists())

    def test_fresh_directory_defaults_to_hidden(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "swconst.tlb"
            library.touch()
            with mock.patch.object(gate, "run", return_value=0) as run:
                self.assertEqual(gate.main(["--output-dir", str(root/"new"),
                                           "--swconst", str(library)]), 0)
            self.assertTrue((root / "new").is_dir())
            self.assertFalse(run.call_args.args[2])

    def test_existing_selection_rejected_before_any_target_or_creation(self):
        selection = SimpleNamespace(GetSelectedObjectCount2=mock.Mock(return_value=1))
        document = SimpleNamespace(SelectionManager=selection, GetBodies2=mock.Mock())
        call = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "selection is not owned"):
            gate.calibrate(None, document, {}, None, None, call, {})
        document.GetBodies2.assert_not_called()
        call.assert_not_called()

    def test_first_failure_survives_cleanup_failure_without_retry(self):
        com = ModuleType("pythoncom")
        com.CoInitialize, com.CoUninitialize = mock.Mock(), mock.Mock()
        package, client = ModuleType("win32com"), ModuleType("win32com.client")
        package.client = client
        document = SimpleNamespace(GetTitle="fixture.SLDPRT")
        exit_app = mock.Mock()
        app = SimpleNamespace(RevisionNumber="33.5.0", GetProcessID=123,
            CloseDoc=mock.Mock(side_effect=RuntimeError("close failed")), ExitApp=lambda: exit_app())
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict("sys.modules",
                {"pythoncom": com, "win32com": package, "win32com.client": client}), \
                mock.patch.object(gate, "read_constants", return_value={}), \
                mock.patch.object(gate, "acquire_resident_app", return_value=(app, True)) as acquire, \
                mock.patch.object(gate, "wait_windows_host_ready"), \
                mock.patch.object(gate, "create_box_part_windows_with_handle",
                                  return_value=({"ok": True}, document)) as create, \
                mock.patch.object(gate, "calibrate", side_effect=RuntimeError("first native failure")) as calibrate:
            self.assertEqual(gate.run(Path(temporary), Path("official.tlb"), False), 1)
            report = json.loads((Path(temporary) / "report.json").read_text())
            self.assertEqual(report["failure"]["message"], "first native failure")
            self.assertEqual(report["cleanup_errors"], [{"stage": "CloseDoc", "error": "close failed"}])
            acquire.assert_called_once_with(client, visible=False)
            create.assert_called_once()
            calibrate.assert_called_once()
            exit_app.assert_called_once()
            com.CoUninitialize.assert_called_once()
            self.assertFalse(report["success"])


if __name__ == "__main__":
    unittest.main()
