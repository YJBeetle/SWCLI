import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_native_files as native
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


class NativeSaveTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.output = (Path(self.scratch.name) / "part.SLDPRT").resolve()
        self.document = self.Document()

    class Document:
        def __init__(self):
            self.path, self.title, self.modified = "", "Part1", True
            self.kind = 1
            self.SketchManager = SimpleNamespace(ActiveSketch=None)
            self.ClearSelection2 = mock.Mock()
            self.content = bytes.fromhex("a4af291e00000004") + bytes(1024)
            self.save_error = 0
            self.saved_calls = []

        def GetTitle(self):
            return self.title

        def GetPathName(self):
            return self.path

        def GetSaveFlag(self):
            return self.modified

        def GetType(self):
            return self.kind

        def GetUpdateStamp(self):
            return 0

        def SaveAs3(self, path, version, options):
            self.saved_calls.append((path, version, options))
            Path(path).write_bytes(self.content)
            self.path, self.title, self.modified = path, Path(path).name, False
            return self.save_error

    def save(self):
        return native.save_as_part_windows(str(self.output), document=self.document)

    def test_unsaved_part_adopts_new_filename_and_reports_native_file_evidence(self):
        result = self.save()
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.document.saved_calls, [(str(self.output), 0, 1)])
        self.assertEqual(result["document_before"]["path"], "")
        self.assertEqual(result["document"]["path"], str(self.output))
        self.assertFalse(result["document"]["modified"])
        self.assertEqual(result["save_errors"], 0)
        self.assertIsNone(result["save_warnings"])
        self.assertEqual(result["artifact"]["size_bytes"], 1032)
        validate_operation_result("document.save-as", result)

    def test_existing_file_and_current_filename_are_never_overwritten(self):
        self.output.write_bytes(b"precious native source")
        self.assertEqual(self.save()["error"]["type"], "OutputExists")
        self.document.path = str(self.output)
        self.assertEqual(self.save()["error"]["type"], "OutputExists")
        self.assertEqual(self.output.read_bytes(), b"precious native source")
        self.assertEqual(self.document.saved_calls, [])

    def test_bad_extension_missing_parent_non_part_and_existing_edit_do_not_save(self):
        self.output = self.output.with_suffix(".STEP")
        self.assertEqual(self.save()["error"]["type"], "InvalidArgument")
        self.output = self.output.parent / "missing" / "part.SLDPRT"
        self.assertEqual(self.save()["error"]["type"], "ParentDirectoryNotFound")
        self.output = self.output.parent.parent / "part.SLDPRT"
        self.document.kind = 2
        self.assertEqual(self.save()["error"]["type"], "UnsupportedDocumentType")
        self.document.kind = 1
        existing = object()
        self.document.SketchManager.ActiveSketch = existing
        self.assertEqual(self.save()["error"]["type"], "SketchEditInProgress")
        self.assertIs(self.document.SketchManager.ActiveSketch, existing)
        self.assertEqual(self.document.saved_calls, [])
        self.assertFalse(self.output.exists())

    def test_exclusive_reservation_preserves_a_competing_new_target(self):
        original_open = Path.open

        def raced_open(path, mode="r", *args, **kwargs):
            if mode == "xb":
                path.write_bytes(b"another writer")
            return original_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", new=raced_open):
            result = self.save()
        self.assertEqual(result["error"]["type"], "OutputExists")
        self.assertEqual(self.output.read_bytes(), b"another writer")
        self.assertEqual(self.document.saved_calls, [])

    def test_native_error_empty_or_truncated_file_remove_new_invalid_output(self):
        for content, code, expected in (
            (b"broken", 1, "SaveFailed"),
            (b"", 0, "NativeSaveVerificationFailed"),
            (bytes(8), 0, "NativeSaveVerificationFailed"),
        ):
            with self.subTest(expected=expected):
                self.document.content, self.document.save_error = content, code
                result = self.save()
                self.assertEqual(result["error"]["type"], expected)
                self.assertFalse(self.output.exists())
                validate_operation_result("document.save-as", result)

    def test_native_exception_removes_reserved_placeholder(self):
        self.document.SaveAs3 = mock.Mock(
            side_effect=RuntimeError("native save failed")
        )
        self.assertEqual(self.save()["error"]["message"], "native save failed")
        self.assertFalse(self.output.exists())

    def test_post_save_modified_or_wrong_path_preserves_valid_file_but_fails(self):
        original = self.document.SaveAs3

        def modified_save(*args):
            code = original(*args)
            self.document.modified = True
            return code

        self.document.SaveAs3 = modified_save
        result = self.save()
        self.assertEqual(result["error"]["type"], "DocumentStillModified")
        self.assertTrue(self.output.exists())
        self.output.unlink()

        def wrong_path(*args):
            code = original(*args)
            self.document.path = "another.SLDPRT"
            return code

        self.document.SaveAs3 = wrong_path
        self.assertEqual(self.save()["error"]["type"], "NativeSavePathMismatch")
        self.assertTrue(self.output.exists())

    def test_cleanup_failure_is_reported_without_hiding_native_failure(self):
        self.document.content = b"broken"
        with mock.patch.object(Path, "unlink", side_effect=OSError("cannot delete")):
            result = self.save()
        self.assertEqual(result["error"]["type"], "NativeSaveVerificationFailed")
        self.assertEqual(result["warnings"][0]["code"], "native-output-cleanup-failed")

    def test_success_schema_does_not_accept_false_save_or_invalid_artifact(self):
        result = self.save()
        for key in (
            "api_saved",
            "save_errors",
            "document",
            "file_verification",
            "artifact",
        ):
            invalid = copy.deepcopy(result)
            if key == "api_saved":
                invalid[key] = False
            elif key == "save_errors":
                invalid[key] = 1
            elif key == "document":
                invalid[key]["modified"] = True
            elif key == "file_verification":
                invalid[key]["minimum_size_valid"] = False
            else:
                invalid[key]["size_bytes"] = 8
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.save-as", invalid)
