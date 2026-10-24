"""Diagnostic order/coverage checks, not native SOLIDWORKS proof."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-modeling.py"
spec = importlib.util.spec_from_file_location("copy_probe_base", SCRIPT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class DrawingCopyProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "installed.SLDDRW"
        self.source.write_bytes(b"d" * 1024)
        self.work = self.root / "private"
        self.work.mkdir()
        self.smoke = base.ModelingSmoke(directory=self.root, host_directory="C:\\evidence",
                                        endpoint="127.0.0.1:18495", case_set="drawing-copy-first")
        self.smoke.checkpoint = Mock()
        self.smoke.close = Mock()

    def probe(self):
        self.smoke.drawing_copy_first(self.source, work_directory=self.work,
                                     host_work_directory="C:\\private")

    def test_only_private_copy_is_opened_once_and_never_saved(self):
        opened = {"document": {"document_id": "d-copy", "type": 3},
                  "read_only": False, "api_errors": 0, "api_warnings": 0}
        structure = {"features": {"count": 1, "truncated": False}}
        self.smoke.command = Mock(side_effect=[opened, {"structure": structure}])
        self.probe()
        calls = self.smoke.command.call_args_list
        self.assertEqual(calls[0].args, ("document", "open", "C:\\private\\drawing.SLDDRW"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1].args[:2], ("document", "inspect"))
        self.smoke.close.assert_called_once_with("d-copy")
        proof = self.smoke.record["drawing_copy_first"]
        self.assertFalse(proof["baseline_source_opened"])
        self.assertFalse(proof["save_attempted"])
        self.assertFalse(self.smoke.record["full_acceptance_eligible"])
        self.assertEqual(proof["source_sha256_before"], proof["copy_sha256_after"])

    def test_first_open_failure_does_not_retry_or_inspect(self):
        self.smoke.command = Mock(side_effect=RuntimeError("first native failure"))
        with self.assertRaisesRegex(RuntimeError, "first native failure"):
            self.probe()
        self.smoke.command.assert_called_once()
        self.smoke.close.assert_not_called()
        proof = self.smoke.record["drawing_copy_first"]
        self.assertEqual(proof["source_sha256_before"], proof["source_sha256_after"])

    def test_selected_probe_never_runs_normal_modeling_or_roundtrips(self):
        self.smoke.health = Mock(return_value={"host": {"process_id": 10}})
        self.smoke.command = Mock()
        self.smoke.require_empty = Mock()
        self.smoke.drawing_copy_first = Mock()
        with patch.object(self.smoke, "native_model") as native, \
                patch.object(self.smoke, "drawing_save_reopen") as roundtrip:
            self.smoke.run(sample_drawing="C:\\installed.SLDDRW", sample_drawing_local=self.source,
                           drawing_work_dir=self.work, host_drawing_work_dir="C:\\private")
        self.smoke.drawing_copy_first.assert_called_once()
        native.assert_not_called()
        roundtrip.assert_not_called()
        self.assertEqual(self.smoke.record["cases"], ["drawing-copy-first"])
        self.assertEqual(self.smoke.require_empty.call_count, 3)

    def test_existing_private_file_is_never_overwritten(self):
        target = self.work / "drawing.SLDDRW"
        target.write_bytes(b"existing")
        self.smoke.command = Mock()
        with self.assertRaises(FileExistsError):
            self.probe()
        self.assertEqual(target.read_bytes(), b"existing")
        self.smoke.command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
