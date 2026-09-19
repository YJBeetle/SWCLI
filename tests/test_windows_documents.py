import unittest
from pathlib import Path
from unittest import mock

from swcli.hosts import windows_documents


class WindowsDocumentTests(unittest.TestCase):
    def test_document_type_is_case_insensitive(self):
        self.assertEqual(windows_documents._document_type(Path("part.SLDPRT")), 1)
        self.assertEqual(windows_documents._document_type(Path("assembly.sldasm")), 2)
        self.assertEqual(windows_documents._document_type(Path("drawing.SldDrw")), 3)

    def test_unknown_document_type_is_rejected(self):
        self.assertIsNone(windows_documents._document_type(Path("notes.txt")))

    def test_operations_are_rejected_off_windows(self):
        with mock.patch.object(windows_documents.sys, "platform", "darwin"):
            opened = windows_documents.open_windows_document("part.SLDPRT")
            inspected = windows_documents.inspect_active_windows_document()
            closed = windows_documents.close_active_windows_document()
            diagnosed = windows_documents.diagnose_active_windows_document()
            rebuilt = windows_documents.rebuild_active_windows_document()

        self.assertEqual(opened["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(inspected["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(closed["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(diagnosed["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(rebuilt["error"]["type"], "UnsupportedPlatform")

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


if __name__ == "__main__":
    unittest.main()
