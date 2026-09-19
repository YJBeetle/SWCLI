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

        self.assertEqual(opened["error"]["type"], "UnsupportedPlatform")
        self.assertEqual(inspected["error"]["type"], "UnsupportedPlatform")


if __name__ == "__main__":
    unittest.main()
