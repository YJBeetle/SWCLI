"""The read path preserves native values, document selection and write guards."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.cli import _typed_operation, build_parser
from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.hosts import windows_custom_properties as adapter
from swcli.result_schemas import validate_operation_result


class DocumentPropertiesTests(unittest.TestCase):
    def setUp(self):
        self.manager = SimpleNamespace(
            Count=2,
            GetNames=lambda: ("中文名称", "Drawing No"),
            GetType2=mock.Mock(return_value=30),
        )
        self.configuration = SimpleNamespace(Name="Default")
        self.manager_for = mock.Mock(return_value=self.manager)
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            GetSaveFlag=lambda: False,
            GetUpdateStamp=lambda: 7,
            GetActiveConfiguration=lambda: self.configuration,
            GetTitle=lambda: "Part",
            GetPathName=lambda: "",
            Extension=SimpleNamespace(CustomPropertyManager=self.manager_for),
        )
        self.foreground = SimpleNamespace(
            GetType=lambda: 1, GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 8,
            GetTitle=lambda: "Foreground", GetPathName=lambda: "",
        )
        self.app = SimpleNamespace(
            ActiveDoc=self.foreground,
            GetDocuments=lambda: (self.document, self.foreground),
            IsSame=lambda first, second: int(first is second),
            ActivateDoc3=mock.Mock(),
        )
        self.documents = DocumentRegistry(self.app)
        self.entry = self.documents.register(self.document)
        foreground_entry = self.documents.register(self.foreground)
        self.documents.set_current(foreground_entry, session_id="reader")
        self.documents.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)

    def run_properties(self, parameters, stamp=7):
        return execute_operation(
            self.app, "document.properties", parameters, documents=self.documents,
            session_id="reader", document_id=self.entry.document_id,
            expected_update_stamp=stamp,
        )

    def test_listing_preserves_empty_and_cached_values_in_background(self):
        replies = [(2, "", "", True, False), (0, "$PRP:\"Number\"", "42", False, True)]
        with mock.patch.object(adapter, "_get_value", side_effect=replies) as read:
            result = self.run_properties({})
        validate_operation_result("document.properties", result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["scope"], "document")
        self.assertIsNone(result["requested_name"])
        first, second = result["properties"]
        self.assertEqual((first["name"], first["raw_value"], first["evaluated_value"]), ("中文名称", "", ""))
        self.assertEqual((second["raw_value"], second["evaluated_value"]), ('$PRP:"Number"', "42"))
        self.assertEqual(second["resolution"], "cached")
        self.assertFalse(second["was_resolved"])
        self.assertTrue(second["linked"])
        self.assertEqual(read.call_args_list, [
            mock.call(self.manager, "中文名称"), mock.call(self.manager, "Drawing No"),
        ])
        self.manager_for.assert_called_once_with("")
        self.assertFalse(result["document"]["active"] or result["document"]["current"])
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.app.ActivateDoc3.assert_not_called()

    def test_missing_name_does_not_become_an_empty_value(self):
        with mock.patch.object(adapter, "_get_value", return_value=(1, None, None, False, False)):
            result = self.run_properties({"name": "Missing"})
        validate_operation_result("document.properties", result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["requested_name"], "Missing")
        self.assertEqual(result["properties"], [])
        self.manager.GetType2.assert_not_called()

    def test_list_refuses_missing_row_or_unreadable_outputs(self):
        for response in ((1, None, None, False, False), (2, None, "", True, False)):
            with self.subTest(response=response):
                with mock.patch.object(adapter, "_get_value", return_value=response):
                    result = self.run_properties({})
                self.assertFalse(result["ok"])
                self.assertNotIn("properties", result)

    def test_configuration_change_cannot_report_success(self):
        def changed(*args):
            self.configuration.Name = "Other"
            return (2, "", "", True, False)

        with mock.patch.object(adapter, "_get_value", side_effect=changed):
            result = self.run_properties({"name": "Drawing No"})
        self.assertFalse(result["ok"])
        self.assertIn("document state", result["error"]["message"])

    def test_stale_stamp_refuses_before_native_property_lookup(self):
        with self.assertRaises(DocumentUpdateConflict):
            self.run_properties({}, stamp=6)
        self.manager_for.assert_not_called()

    def test_cli_maps_name_document_and_stamp(self):
        args = build_parser().parse_args([
            "document", "properties", "--name", "Drawing No",
            "--document", self.entry.document_id, "--if-update-stamp", "7", "--json",
        ])
        self.assertEqual(_typed_operation(args), (
            "document.properties", {"name": "Drawing No"}, True, self.entry.document_id, 7, None,
        ))
