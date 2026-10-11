from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_documents as documents
from swcli.result_schemas import ARTIFACT
from test_export_validation import amf, archive, binary_stl, glb, three_mf_members


class WindowsMeshExportTests(unittest.TestCase):
    def export(self, format, payload, *, document_type=1, strict=False, save_error=0,
               preference=False, restore_failure=False, native_failure=False,
               unavailable=False, enable_rejected=False):
        self.preference = preference
        self.saved = []
        self.preference_writes = []

        def get_preference(flag):
            self.assertEqual(flag, documents._STL_COMPONENTS_INTO_ONE_FILE)
            return None if unavailable else self.preference

        def set_preference(flag, value):
            self.preference_writes.append(value)
            if restore_failure and value is False:
                raise RuntimeError("restore failed")
            if not (enable_rejected and value is True):
                self.preference = value
            return True

        def save(path, version, options):
            self.saved.append(Path(path))
            if format == "STL" and document_type == 2:
                self.assertTrue(self.preference)
            if native_failure:
                raise RuntimeError("native save failed")
            Path(path).write_bytes(payload)
            return save_error

        document = SimpleNamespace(Extension=SimpleNamespace(NeedsRebuild2=0),
                                   ClearSelection2=mock.Mock(), SaveAs3=save)
        app = SimpleNamespace(ActiveDoc=document, GetUserPreferenceToggle=get_preference,
                              SetUserPreferenceToggle=set_preference)
        description = {"title": "fixture", "path": "fixture.SLDPRT",
                       "type": document_type, "modified": False}
        win32com = ModuleType("win32com")
        win32com.client = ModuleType("win32com.client")
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            output = Path(folder) / ("fixture." + format)
            output.write_bytes(b"previous valid artifact")
            stack.enter_context(mock.patch.object(documents.sys, "platform", "win32"))
            stack.enter_context(mock.patch.dict("sys.modules", {
                "pythoncom": ModuleType("pythoncom"), "win32com": win32com,
                "win32com.client": win32com.client,
            }))
            stack.enter_context(mock.patch.object(documents, "_describe_document", return_value=description))
            result = documents.export_active_windows_document(
                str(output), overwrite=True, strict=strict, app=app
            )
            self.output = output.read_bytes()
            self.residue = sorted(path.name for path in Path(folder).iterdir())
            self.assertEqual(self.residue, [output.name])
            for temporary in self.saved:
                self.assertNotEqual(temporary, output)
                self.assertFalse(temporary.exists())
        return result

    def test_all_mesh_formats_for_parts_and_assemblies(self):
        for kind in (1, 2):
            for format, payload in (("STL", binary_stl()), ("3MF", archive(three_mf_members())),
                                    ("AMF", amf()), ("GLB", glb())):
                for strict in (False, True):
                    with self.subTest(kind=kind, format=format, strict=strict):
                        result = self.export(format, payload, document_type=kind, strict=strict)
                        self.assertTrue(result["ok"], result)
                        self.assertEqual(result["artifact"]["format"], format)
                        self.assertEqual(result["artifact"]["size_bytes"], len(payload))
                        self.assertEqual(self.output, payload)
                        self.assertNotIn("warnings", result)
                        self.assertFalse(self.preference)

    def test_corrupted_outputs_do_not_replace_target_in_either_mode(self):
        for format in ("STL", "3MF", "AMF", "GLB"):
            for strict in (False, True):
                result = self.export(format, b"damaged output", strict=strict)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["type"], "ExportVerificationFailed")
                self.assertEqual(self.output, b"previous valid artifact")

    def test_assembly_stl_preference_is_scoped_and_already_enabled_is_untouched(self):
        result = self.export("STL", binary_stl(), document_type=2)
        self.assertTrue(result["ok"])
        self.assertEqual(self.preference_writes, [True, False])
        result = self.export("STL", binary_stl(), document_type=2, preference=True)
        self.assertTrue(result["ok"])
        self.assertEqual(self.preference_writes, [])
        self.assertTrue(self.preference)

    def test_stl_restores_preference_after_native_error_and_exception(self):
        for kwargs, error in (({"save_error": 1}, "ExportFailed"),
                              ({"native_failure": True}, "RuntimeError")):
            result = self.export("STL", binary_stl(), document_type=2, **kwargs)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], error)
            self.assertFalse(self.preference)
            self.assertEqual(self.output, b"previous valid artifact")

    def test_stl_restore_failure_prevents_publishing_verified_output(self):
        result = self.export("STL", binary_stl(), document_type=2, restore_failure=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "ExportPreferenceRestoreFailed")
        self.assertEqual(self.output, b"previous valid artifact")

    def test_unobservable_or_rejected_single_file_preference_prevents_save(self):
        for kwargs in ({"unavailable": True}, {"enable_rejected": True}):
            result = self.export("STL", binary_stl(), document_type=2, **kwargs)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], "ExportPreferenceUnavailable")
            self.assertEqual(self.saved, [])
            self.assertFalse(self.preference)

    def test_drawings_and_obj_remain_constrained(self):
        for extension in ("STL", "3MF", "AMF", "GLB"):
            self.assertIsNone(documents._export_format(3, Path("drawing." + extension)))
        for kind in (1, 2, 3):
            self.assertIsNone(documents._export_format(kind, Path("fixture.OBJ")))

    def test_artifact_schema_includes_existing_stp_and_new_formats(self):
        self.assertEqual(set(ARTIFACT["properties"]["format"]["enum"]),
                         {"STEP", "STP", "STL", "3MF", "AMF", "GLB", "PDF", "DWG"})
