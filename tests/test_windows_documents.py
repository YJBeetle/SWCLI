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

    def test_export_can_explicitly_accept_only_modified_flag_change(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com.client = win32com_client

        class Document:
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
                    str(output), allow_source_modification=True, app=app
                )

        self.assertTrue(result["ok"])
        self.assertTrue(result["source_modified_by_export"])
        self.assertEqual(result["artifact"]["format"], "PDF")
        pythoncom.CoInitialize.assert_not_called()
        pythoncom.CoUninitialize.assert_not_called()

    def test_operations_are_rejected_off_windows(self):
        with mock.patch.object(windows_documents.sys, "platform", "darwin"):
            opened = windows_documents.open_windows_document("part.SLDPRT")
            inspected = windows_documents.inspect_active_windows_document()
            closed = windows_documents.close_active_windows_document()
            diagnosed = windows_documents.diagnose_active_windows_document()
            exported = windows_documents.export_active_windows_document("model.step")
            rebuilt = windows_documents.rebuild_active_windows_document()
            rendered = windows_documents.render_active_windows_document("view.bmp")

        self.assertEqual(opened["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(inspected["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(closed["error"]["type"], "UnsupportedPlatform")
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
