import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

from swcli.hosts import windows_documents


class WindowsDocumentTests(unittest.TestCase):
    def test_standard_view_ids_match_solidworks_enum(self):
        self.assertEqual(
            windows_documents.STANDARD_VIEW_IDS,
            {
                "front": 1,
                "back": 2,
                "left": 3,
                "right": 4,
                "top": 5,
                "bottom": 6,
                "isometric": 7,
                "trimetric": 8,
                "dimetric": 9,
            },
        )

    def test_document_type_is_case_insensitive(self):
        self.assertEqual(windows_documents._document_type(Path("part.SLDPRT")), 1)
        self.assertEqual(windows_documents._document_type(Path("assembly.sldasm")), 2)
        self.assertEqual(windows_documents._document_type(Path("drawing.SldDrw")), 3)

    def test_unknown_document_type_is_rejected(self):
        self.assertIsNone(windows_documents._document_type(Path("notes.txt")))

    def test_render_arguments_require_bmp_and_positive_dimensions(self):
        self.assertIsNone(
            windows_documents._validate_render_arguments(
                "view.BMP", 1024, 768, "isometric"
            )
        )
        self.assertEqual(
            windows_documents._validate_render_arguments(
                "view.png", 1024, 768, "current"
            )["type"],
            "InvalidArgument",
        )
        self.assertEqual(
            windows_documents._validate_render_arguments(
                "view.bmp", 0, 768, "current"
            )["type"],
            "InvalidArgument",
        )
        self.assertEqual(
            windows_documents._validate_render_arguments(
                "view.bmp", 1024, 768, "perspective"
            )["type"],
            "InvalidArgument",
        )

    def test_bmp_dimensions_are_parsed_from_header(self):
        header = bytearray(26)
        header[:2] = b"BM"
        header[18:22] = (1024).to_bytes(4, "little", signed=True)
        header[22:26] = (-768).to_bytes(4, "little", signed=True)

        self.assertEqual(
            windows_documents._parse_bmp_dimensions(bytes(header)),
            {"width": 1024, "height": 768},
        )
        self.assertIsNone(windows_documents._parse_bmp_dimensions(b"not-a-bitmap"))

    def test_export_formats_are_constrained_by_document_type(self):
        self.assertEqual(
            windows_documents._export_format(1, Path("part.STEP")), "STEP"
        )
        self.assertEqual(
            windows_documents._export_format(2, Path("assembly.stp")), "STP"
        )
        self.assertEqual(
            windows_documents._export_format(2, Path("assembly.glb")), "GLB"
        )
        self.assertEqual(
            windows_documents._export_format(3, Path("drawing.PDF")), "PDF"
        )
        self.assertEqual(
            windows_documents._export_format(3, Path("drawing.dwg")), "DWG"
        )
        self.assertIsNone(
            windows_documents._export_format(1, Path("part.pdf"))
        )
        self.assertIsNone(
            windows_documents._export_format(3, Path("drawing.step"))
        )

    def test_export_signatures_are_verified(self):
        self.assertTrue(
            windows_documents._export_signature_valid(
                "STEP", b"ISO-10303-21;\nHEADER;"
            )
        )
        self.assertTrue(
            windows_documents._export_signature_valid("PDF", b"%PDF-1.7")
        )
        self.assertTrue(
            windows_documents._export_signature_valid("DWG", b"AC1032")
        )
        self.assertTrue(
            windows_documents._export_signature_valid(
                "GLB", b"glTF\x02\x00\x00\x00\x10\x00\x00\x00"
            )
        )
        self.assertFalse(
            windows_documents._export_signature_valid("PDF", b"empty")
        )

    def test_save_status_bitmasks_are_named(self):
        self.assertEqual(
            windows_documents._bitmask_names(
                3, windows_documents._SAVE_ERRORS
            ),
            ["generic-save-error", "read-only-save-error"],
        )
        self.assertEqual(
            windows_documents._bitmask_names(
                2048, windows_documents._SAVE_WARNINGS
            ),
            ["xml-invalid"],
        )

    def test_permissive_export_reports_only_source_state_problems(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com.client = win32com_client

        class Document:
            class Extension:
                NeedsRebuild2 = 0

            Extension = Extension()

            def ClearSelection2(self, clear_all):
                self.clear_all = clear_all

            def SaveAs3(self, path, version, options):
                Path(path).write_bytes(b"%PDF-1.7\n")
                return 0

        app = mock.Mock(ActiveDoc=Document())
        before = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": False,
        }
        after = {**before, "modified": True}

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "drawing.PDF"
            with (
                mock.patch.object(windows_documents.sys, "platform", "win32"),
                mock.patch.dict(
                    "sys.modules",
                    {
                        "pythoncom": pythoncom,
                        "win32com": win32com,
                        "win32com.client": win32com_client,
                    },
                ),
                mock.patch.object(
                    windows_documents,
                    "_describe_document",
                    side_effect=[before, after],
                ),
            ):
                result = windows_documents.export_active_windows_document(
                    str(output), app=app
                )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["warnings"],
            [
                {
                    "code": "source-modified-by-export",
                    "message": "export changed the source document modified state",
                    "before": False,
                    "after": True,
                }
            ],
        )
        self.assertEqual(result["artifact"]["format"], "PDF")
        self.assertNotIn("document", result)
        self.assertNotIn("verification", result)
        pythoncom.CoInitialize.assert_not_called()
        pythoncom.CoUninitialize.assert_not_called()

    def test_strict_export_rejects_modified_source_before_export(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com.client = win32com_client

        class Extension:
            NeedsRebuild2 = 4

        class Document:
            SaveAs3 = mock.Mock()

        Document.Extension = Extension()

        before = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": True,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "drawing.PDF"
            with (
                mock.patch.object(windows_documents.sys, "platform", "win32"),
                mock.patch.dict(
                    "sys.modules",
                    {
                        "pythoncom": pythoncom,
                        "win32com": win32com,
                        "win32com.client": win32com_client,
                    },
                ),
                mock.patch.object(
                    windows_documents,
                    "_describe_document",
                    return_value=before,
                ),
            ):
                result = windows_documents.export_active_windows_document(
                    str(output), strict=True, app=mock.Mock(ActiveDoc=Document())
                )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "SourceNotClean")
        self.assertEqual(
            [item["code"] for item in result["error"]["violations"]],
            ["source-modified", "source-needs-rebuild"],
        )
        Document.SaveAs3.assert_not_called()

    def test_permissive_export_warns_when_source_is_not_clean(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com.client = win32com_client

        class Extension:
            NeedsRebuild2 = 4

        class Document:
            def ClearSelection2(self, clear_all):
                self.clear_all = clear_all

            def SaveAs3(self, path, version, options):
                Path(path).write_bytes(b"%PDF-1.7\n")
                return 0

        Document.Extension = Extension()
        description = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": True,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "drawing.PDF"
            with (
                mock.patch.object(windows_documents.sys, "platform", "win32"),
                mock.patch.dict(
                    "sys.modules",
                    {
                        "pythoncom": pythoncom,
                        "win32com": win32com,
                        "win32com.client": win32com_client,
                    },
                ),
                mock.patch.object(
                    windows_documents,
                    "_describe_document",
                    return_value=description,
                ),
            ):
                result = windows_documents.export_active_windows_document(
                    str(output), app=mock.Mock(ActiveDoc=Document())
                )

        self.assertTrue(result["ok"])
        self.assertEqual(
            [item["code"] for item in result["warnings"]],
            ["source-modified", "source-needs-rebuild"],
        )

    def test_strict_export_commits_verified_temporary_artifact(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com.client = win32com_client

        class Extension:
            NeedsRebuild2 = 0

        class Document:
            def ClearSelection2(self, clear_all):
                self.clear_all = clear_all

            def SaveAs3(self, path, version, options):
                self.export_path = Path(path)
                self.export_path.write_bytes(b"%PDF-1.7\n")
                return 0

        Document.Extension = Extension()

        document = Document()
        description = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": False,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "drawing.PDF"
            with (
                mock.patch.object(windows_documents.sys, "platform", "win32"),
                mock.patch.dict(
                    "sys.modules",
                    {
                        "pythoncom": pythoncom,
                        "win32com": win32com,
                        "win32com.client": win32com_client,
                    },
                ),
                mock.patch.object(
                    windows_documents,
                    "_describe_document",
                    return_value=description,
                ),
            ):
                result = windows_documents.export_active_windows_document(
                    str(output), strict=True, app=mock.Mock(ActiveDoc=document)
                )

            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes(), b"%PDF-1.7\n")
            self.assertNotEqual(document.export_path, output)
            self.assertFalse(document.export_path.exists())

        self.assertTrue(result["ok"])
        self.assertNotIn("warnings", result)

    def test_strict_export_preserves_existing_target_on_postcheck_failure(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com.client = win32com_client

        class Extension:
            NeedsRebuild2 = 0

        class Document:
            def ClearSelection2(self, clear_all):
                self.clear_all = clear_all

            def SaveAs3(self, path, version, options):
                self.export_path = Path(path)
                self.export_path.write_bytes(b"%PDF-1.7\nnew")
                return 0

        Document.Extension = Extension()

        document = Document()
        before = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": False,
        }
        after = {**before, "modified": True}

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "drawing.PDF"
            output.write_bytes(b"existing")
            with (
                mock.patch.object(windows_documents.sys, "platform", "win32"),
                mock.patch.dict(
                    "sys.modules",
                    {
                        "pythoncom": pythoncom,
                        "win32com": win32com,
                        "win32com.client": win32com_client,
                    },
                ),
                mock.patch.object(
                    windows_documents,
                    "_describe_document",
                    side_effect=[before, after],
                ),
            ):
                result = windows_documents.export_active_windows_document(
                    str(output),
                    strict=True,
                    overwrite=True,
                    app=mock.Mock(ActiveDoc=document),
                )

            self.assertEqual(output.read_bytes(), b"existing")
            self.assertFalse(document.export_path.exists())

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "SourceStateChanged")
        self.assertEqual(
            result["error"]["violations"][0]["code"],
            "source-modified-by-export",
        )

    def test_inspect_reports_save_and_rebuild_state(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com.client = win32com_client

        class Extension:
            NeedsRebuild2 = 2

        class Document:
            pass

        Document.Extension = Extension()

        description = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": True,
        }

        with (
            mock.patch.object(windows_documents.sys, "platform", "win32"),
            mock.patch.dict(
                "sys.modules",
                {
                    "pythoncom": pythoncom,
                    "win32com": win32com,
                    "win32com.client": win32com_client,
                },
            ),
            mock.patch.object(
                windows_documents,
                "_describe_document",
                return_value=description,
            ),
        ):
            result = windows_documents.inspect_active_windows_document(
                app=mock.Mock(ActiveDoc=Document())
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["document"]["modified"])
        self.assertEqual(result["needs_rebuild"], 2)
        pythoncom.CoInitialize.assert_not_called()
        pythoncom.CoUninitialize.assert_not_called()

    def test_save_reports_status_and_requires_clean_post_save_state(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.VT_BYREF = 0x4000
        pythoncom.VT_I4 = 3
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")

        class Variant:
            def __init__(self, variant_type, value):
                self.variant_type = variant_type
                self.value = value

        win32com_client.VARIANT = Variant
        win32com.client = win32com_client

        class Document:
            def Save3(self, options, errors, warnings):
                self.options = options
                return True

        document = Document()
        app = mock.Mock(ActiveDoc=document)
        before = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": True,
        }
        after = {**before, "modified": False}

        with (
            mock.patch.object(windows_documents.sys, "platform", "win32"),
            mock.patch.dict(
                "sys.modules",
                {
                    "pythoncom": pythoncom,
                    "win32com": win32com,
                    "win32com.client": win32com_client,
                },
            ),
            mock.patch.object(
                windows_documents,
                "_describe_document",
                side_effect=[before, after],
            ),
        ):
            result = windows_documents.save_active_windows_document(app=app)

        self.assertTrue(result["ok"])
        self.assertTrue(result["api_saved"])
        self.assertEqual(result["save_errors"], 0)
        self.assertEqual(result["save_error_names"], [])
        self.assertEqual(result["save_warnings"], 0)
        self.assertEqual(result["save_warning_names"], [])
        self.assertFalse(result["document_after"]["modified"])
        self.assertEqual(document.options, 1)
        pythoncom.CoInitialize.assert_not_called()
        pythoncom.CoUninitialize.assert_not_called()

    def test_save_failure_reports_named_error_and_warning_bits(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.VT_BYREF = 0x4000
        pythoncom.VT_I4 = 3
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")

        class Variant:
            def __init__(self, variant_type, value):
                self.variant_type = variant_type
                self.value = value

        win32com_client.VARIANT = Variant
        win32com.client = win32com_client

        class Document:
            def Save3(self, options, errors, warnings):
                errors.value = 1
                warnings.value = 2048
                return False

        before = {
            "title": "drawing",
            "path": "drawing.SLDDRW",
            "type": 3,
            "modified": True,
        }

        with (
            mock.patch.object(windows_documents.sys, "platform", "win32"),
            mock.patch.dict(
                "sys.modules",
                {
                    "pythoncom": pythoncom,
                    "win32com": win32com,
                    "win32com.client": win32com_client,
                },
            ),
            mock.patch.object(
                windows_documents,
                "_describe_document",
                side_effect=[before, before],
            ),
        ):
            result = windows_documents.save_active_windows_document(
                app=mock.Mock(ActiveDoc=Document())
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "SaveFailed")
        self.assertEqual(result["save_errors"], 1)
        self.assertEqual(result["save_error_names"], ["generic-save-error"])
        self.assertEqual(result["save_warnings"], 2048)
        self.assertEqual(result["save_warning_names"], ["xml-invalid"])
        self.assertTrue(result["document_after"]["modified"])
        pythoncom.CoInitialize.assert_not_called()
        pythoncom.CoUninitialize.assert_not_called()

    def test_operations_are_rejected_off_windows(self):
        with mock.patch.object(windows_documents.sys, "platform", "darwin"):
            opened = windows_documents.open_windows_document("part.SLDPRT")
            inspected = windows_documents.inspect_active_windows_document()
            closed = windows_documents.close_active_windows_document()
            saved = windows_documents.save_active_windows_document()
            diagnosed = windows_documents.diagnose_active_windows_document()
            exported = windows_documents.export_active_windows_document("model.step")
            rebuilt = windows_documents.rebuild_active_windows_document()
            rendered = windows_documents.render_active_windows_document("view.bmp")

        self.assertEqual(opened["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(inspected["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(closed["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(saved["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(diagnosed["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(exported["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(rebuilt["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(rendered["error"]["type"], "UnsupportedPlatform")

    def test_units_are_named_and_preserve_codes(self):
        class Document:
            GetUnits = (0, 1, 8, 2, 0)

        units = windows_documents._inspect_units(Document())
        self.assertEqual(units["length"], {"code": 0, "name": "millimeter"})
        self.assertEqual(units["significant_digits"], 2)

    def test_feature_traversal_is_bounded(self):
        class Feature:
            Visible = 1

            def __init__(self, name, next_feature=None):
                self.Name = name
                self.GetTypeName2 = "Extrusion"
                self.GetNextFeature = next_feature

        second = Feature("second")
        first = Feature("first", second)

        class Document:
            FirstFeature = first

        features = windows_documents._inspect_features(Document(), 1)
        self.assertEqual(features["count"], 1)
        self.assertTrue(features["truncated"])

    def test_body_inspection_includes_approximate_bounding_box(self):
        class Body:
            Name = "Boss-Extrude1"
            GetType = 0
            Visible = True
            GetFaceCount = 6
            GetEdgeCount = 12

            def GetBodyBox(self):
                return (-0.05, -0.025, 0.0, 0.05, 0.025, 0.02)

        class Document:
            GetType = 1

            def GetBodies2(self, body_type, visible_only):
                self.arguments = (body_type, visible_only)
                return (Body(),)

        document = Document()
        bodies = windows_documents._inspect_bodies(document)

        self.assertEqual(document.arguments, (-1, False))
        self.assertEqual(bodies["count"], 1)
        box = bodies["items"][0]["approximate_bounding_box"]
        self.assertEqual(box["size_mm"], {"x": 100.0, "y": 50.0, "z": 20.0})
        self.assertEqual(box["accuracy"], "approximate")


if __name__ == "__main__":
    unittest.main()
