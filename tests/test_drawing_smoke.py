"""Portable drawing gate sequencing tests, not native SOLIDWORKS proof."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-drawings.py"
spec = importlib.util.spec_from_file_location("drawing_smoke_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class DrawingSmokeTests(unittest.TestCase):
    def smoke(self, directory):
        result = gate.DrawingSmoke(directory=Path(directory), host_directory="C:\\test",
                                   endpoint="127.0.0.1:18495")
        result.checkpoint = mock.Mock()
        return result

    def test_public_case_sequences_guards_before_one_insertion_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            smoke = self.smoke(directory)
            structure = {"configurations": {"active": "Default"}, "features": {
                "count": 1, "truncated": False,
                "items": [{"name": "Sheet1", "type": "Sheet"}]}}
            source = {"document": {"modified": False}, "needs_rebuild": 0,
                      "structure": structure}
            smoke.clean_source = mock.Mock(return_value=source)
            smoke.create = mock.Mock(side_effect=["part", "blocker"])
            smoke.rectangle = mock.Mock(return_value={"sketch": {"sketch_id": "sketch"}})
            smoke.feature = mock.Mock()
            def save(document, name):
                path = Path(directory) / name
                path.write_bytes(b"x" * 512)
                return path
            smoke.save_native = mock.Mock(side_effect=save)
            def command(*args, **kwargs):
                if args[:3] == ("document", "lease", "acquire"):
                    return {"lease": {"lease_id": "token"}}
                if args[:2] == ("document", "inspect"):
                    return {"document": {"document_id": "blocker", "active": True,
                                         "modified": False, "update_stamp": 5},
                            "structure": structure}
                if args[:2] == ("document", "create"):
                    return {"document": {"document_id": "drawing", "type": 3},
                            "views": [], "sheet": {"projection": "first-angle"}}
                if args[:2] == ("document", "open"):
                    return {"document": {"document_id": "reopened"}}
                if args[:2] == ("document", "diagnose"):
                    return {"diagnostics": {"healthy": True}, "needs_rebuild": 0}
                if args[:2] == ("document", "list"):
                    return {"documents": [{"document_id": "part"}]}
                return {}
            smoke.command = mock.Mock(side_effect=command)
            def write(*args, **kwargs):
                if kwargs.get("expected_error"):
                    return {"mutation": {"attempted": False},
                            "error": {"message": "drawing already contains model views"}}
                return {"verification": {"passed": True, "source_unchanged": True},
                        "sheet": {"projection": "first-angle"}, "views": [1,2,3]}
            smoke.write = mock.Mock(side_effect=write)
            smoke.close = mock.Mock()
            smoke.background = mock.Mock()
            with mock.patch.object(gate.base, "export_file_valid", return_value=True):
                smoke.drawing_case("part", "first-angle", "C:\\a4.DRWDOT")
            self.assertEqual([item["stage"] for item in smoke.record["source_lifecycle"]],
                             ["part-first-angle.before-drawing-close",
                              "part-first-angle.after-drawing-close",
                              "part-first-angle.after-drawing-reopen"])
            self.assertTrue(all(item["source_document_id"] == "part"
                                for item in smoke.record["source_lifecycle"]))
            guards = [call.kwargs.get("expected_error") for call in smoke.command.call_args_list
                      if call.args[:2] == ("drawing", "standard-views")]
            self.assertEqual(guards, ["DocumentLeaseConflict", "DocumentUpdateConflict",
                                      "DocumentLeaseConflict"])
            insertions = [call for call in smoke.write.call_args_list
                          if call.args[:2] == ("drawing", "standard-views")
                          and not call.kwargs.get("expected_error")]
            self.assertEqual(len(insertions), 1)
            self.assertIn("--if-update-stamp", insertions[0].args)
            exports = [call for call in smoke.write.call_args_list
                       if call.args[:2] == ("document", "export")]
            self.assertEqual(len(exports), 2)
            self.assertTrue(all("--strict" in call.args and call.kwargs["document"] == "reopened"
                                for call in exports))
            self.assertEqual(smoke.record["cases"], ["part-first-angle"])

    def test_projection_cases_and_same_host(self):
        with tempfile.TemporaryDirectory() as directory:
            smoke = self.smoke(directory)
            smoke.health = mock.Mock(return_value={"host": {"process_id": 4}})
            smoke.command = mock.Mock()
            smoke.require_empty = mock.Mock()
            smoke.drawing_case = mock.Mock()
            smoke.run_drawings("C:\\a4.DRWDOT")
            self.assertEqual(smoke.drawing_case.call_args_list, [
                mock.call("part", "first-angle", "C:\\a4.DRWDOT"),
                mock.call("assembly", "third-angle", "C:\\a4.DRWDOT")])
            self.assertIn("not exposed", smoke.record["persistence_scope"])
            smoke.command.assert_called_once_with("capabilities", "--full")

    def test_first_failure_has_no_retry_or_next_case(self):
        with tempfile.TemporaryDirectory() as directory:
            smoke = self.smoke(directory)
            smoke.health = mock.Mock(return_value={"host": {"process_id": 4}})
            smoke.command = mock.Mock()
            smoke.require_empty = mock.Mock()
            smoke.drawing_case = mock.Mock(side_effect=RuntimeError("first native failure"))
            with self.assertRaisesRegex(RuntimeError, "first native failure"):
                smoke.run_drawings("C:\\a4.DRWDOT")
            self.assertEqual(smoke.drawing_case.call_count, 1)

    def test_replaced_host_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            smoke = self.smoke(directory)
            smoke.health = mock.Mock(side_effect=[{"host": {"process_id": 4}},
                                                  {"host": {"process_id": 5}}])
            smoke.command = mock.Mock()
            smoke.require_empty = mock.Mock()
            smoke.drawing_case = mock.Mock()
            with self.assertRaisesRegex(RuntimeError, "replaced"):
                smoke.run_drawings("C:\\a4.DRWDOT")

    def test_signature_excludes_ephemeral_ids_but_preserves_tree(self):
        original = {"configurations": {"active": "Default"}, "features": {
            "count": 1, "truncated": False, "items": [
                {"name": "Sheet1", "type": "Sheet", "feature_id": "old"}]}}
        fresh = {**original, "features": {**original["features"], "items": [
            {"name": "Sheet1", "type": "Sheet", "feature_id": "new"}]}}
        self.assertEqual(gate.DrawingSmoke.structure_signature(original),
                         gate.DrawingSmoke.structure_signature(fresh))
        fresh["features"]["truncated"] = True
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            gate.DrawingSmoke.structure_signature(fresh)

    def test_template_required_before_any_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(gate.DrawingSmoke, "command") as command:
                with self.assertRaises(SystemExit):
                    gate.main(["--output-dir", directory])
                command.assert_not_called()

    def test_old_record_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drawings.json"
            path.write_text("old evidence")
            with mock.patch.object(gate.DrawingSmoke, "command") as command:
                with self.assertRaises(FileExistsError):
                    gate.main(["--output-dir", directory, "--host-output-dir", "C:\\test",
                               "--drawing-template", "C:\\a4.DRWDOT"])
                command.assert_not_called()
            self.assertEqual(path.read_text(), "old evidence")


if __name__ == "__main__":
    unittest.main()
