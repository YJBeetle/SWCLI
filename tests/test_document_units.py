"""Document display units share native metadata guards without global preferences."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.cli import _typed_operation, build_parser
from swcli.daemon.documents import DocumentLeaseConflict, DocumentRegistry
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.hosts import windows_document_units as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


class DocumentUnitsTests(unittest.TestCase):
    def setUp(self):
        self.units = (0, 1, 8, 3, 0)
        self.modified = False
        self.configuration = SimpleNamespace(Name="Default")
        self.document = SimpleNamespace(
            GetType=lambda: 1, GetSaveFlag=lambda: self.modified,
            GetUpdateStamp=lambda: 7, ConfigurationManager=SimpleNamespace(ActiveConfiguration=self.configuration),
            GetTitle=lambda: "Background part", GetPathName=lambda: "",
            IsOpenedReadOnly=lambda: False, IsOpenedViewOnly=lambda: False,
            SketchManager=SimpleNamespace(ActiveSketch=None),
            GetUnits=mock.Mock(spec=(), side_effect=lambda: self.units),
            SetUnits=mock.Mock(side_effect=self.apply_units),
            SetSaveFlag=mock.Mock(side_effect=self.mark_modified),
        )
        self.foreground = SimpleNamespace(
            GetType=lambda: 1, GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 8,
            GetTitle=lambda: "Foreground", GetPathName=lambda: "",
        )
        self.app = SimpleNamespace(
            ActiveDoc=self.foreground,
            GetDocuments=lambda: (self.document, self.foreground),
            IsSame=lambda first, second: int(first is second), ActivateDoc3=mock.Mock(),
            SetUserPreferenceIntegerValue=mock.Mock(),
        )
        self.documents = DocumentRegistry(self.app)
        self.entry = self.documents.register(self.document)
        foreground_entry = self.documents.register(self.foreground)
        self.documents.set_current(foreground_entry, session_id="reader")
        self.lease = self.documents.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)

    def apply_units(self, *values):
        self.units = (*values[:4], int(values[4]))

    def mark_modified(self):
        self.modified = True

    def operation(self, name, values=None, *, session="writer", stamp=7, lease=None):
        return execute_operation(
            self.app, name, values or {}, documents=self.documents, session_id=session,
            document_id=self.entry.document_id, expected_update_stamp=stamp,
            lease_id=(self.lease["lease_id"] if name == "document.units-set" and session == "writer" and lease is None else lease),
        )

    def test_background_read_preserves_native_codes_and_state_under_another_lease(self):
        self.units = (7, 0, 8, 5, -1)
        result = self.operation("document.units", session="reader")
        validate_operation_result("document.units", result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["units"], {
            "length_unit": "other", "decimal_places": 5,
            "native_units": {"length_unit": 7, "fraction_base": 0, "fraction_value": 8,
                             "significant_digits": 5, "round_to_fraction": -1},
        })
        self.assertFalse(result["document"]["active"] or result["document"]["current"])
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.document.SetUnits.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.app.SetUserPreferenceIntegerValue.assert_not_called()

    def test_property_shaped_get_units_is_read_inside_the_native_trace(self):
        self.document.GetUnits = (0, 1, 8, 2, 0)
        calls = []
        def trace(stage, method, read):
            calls.append((stage, method))
            return read()
        with mock.patch.object(adapter, "native_call", side_effect=trace):
            result = self.operation("document.units", session="reader")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["units"]["decimal_places"], 2)
        self.assertEqual(calls, [("document-units", "IModelDoc2.GetUnits")])

    def test_write_sets_document_only_then_reads_back_and_marks_modified(self):
        result = self.operation("document.units-set", {"length_unit": "inch", "decimal_places": 4})
        validate_operation_result("document.units-set", result)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["changed"] and result["document"]["modified"])
        self.assertEqual(result["before"]["length_unit"], "mm")
        self.assertEqual(result["units"]["length_unit"], "inch")
        self.assertEqual(result["units"]["decimal_places"], 4)
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.document.SetUnits.assert_called_once_with(3, 1, 8, 4, False)
        self.document.SetSaveFlag.assert_called_once_with()
        self.app.SetUserPreferenceIntegerValue.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.foreground)

    def test_omitted_length_or_precision_preserves_the_corresponding_value(self):
        for values, expected in (({"length_unit": "inch"}, (3, 1, 8, 3, False)),
                                 ({"decimal_places": 0}, (0, 1, 8, 0, False)),
                                 ({"decimal_places": 8}, (0, 1, 8, 8, False))):
            with self.subTest(values=values):
                self.units = (0, 1, 8, 3, 0)
                self.document.SetUnits.reset_mock()
                result = self.operation("document.units-set", values)
                self.assertTrue(result["ok"], result)
                self.document.SetUnits.assert_called_once_with(*expected)

    def test_equal_units_do_not_invoke_native_setter_or_mark_dirty(self):
        result = self.operation("document.units-set", {"length_unit": "mm", "decimal_places": 3})
        validate_operation_result("document.units-set", result)
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"] or result["mutation"]["attempted"])
        self.document.SetUnits.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()

    def test_equal_units_preserve_unrequested_native_format_fields(self):
        self.units = (0, 0, 0, 3, 0)
        result = self.operation("document.units-set", {"length_unit": "mm", "decimal_places": 3})
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["changed"])
        self.assertEqual(result["units"]["native_units"]["fraction_base"], 0)
        self.document.SetUnits.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()

    def test_lease_and_stale_stamp_refuse_before_native_access(self):
        with self.assertRaises(DocumentLeaseConflict):
            self.operation("document.units-set", {"length_unit": "inch"}, session="reader")
        with self.assertRaises(DocumentUpdateConflict):
            self.operation("document.units-set", {"length_unit": "inch"}, stamp=6)
        with self.assertRaises(DocumentUpdateConflict):
            self.operation("document.units", session="reader", stamp=6)
        self.document.GetUnits.assert_not_called()
        self.document.SetUnits.assert_not_called()

    def test_read_only_and_view_only_edits_refuse_before_native_access(self):
        for flag in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with self.subTest(flag=flag), mock.patch.object(self.document, flag, return_value=True):
                result = self.operation("document.units-set", {"length_unit": "inch"})
                self.assertFalse(result["ok"])
                self.assertFalse(result["mutation"]["attempted"])
        self.document.GetUnits.assert_not_called()
        self.document.SetUnits.assert_not_called()

    def test_unreadable_native_tuple_is_rejected(self):
        for units in (None, (), (0, 1, 0, 3), (False, 1, 0, 3, False),
                      (0, 1, 0, 3.0, False), (0, 1, 0, 3, False), (32768, 1, 8, 3, 0), (0, 1, 8, -32769, 0)):
            with self.subTest(units=units):
                self.units = units
                result = self.operation("document.units", session="reader")
                self.assertFalse(result["ok"])
                self.assertNotIn("units", result)
        self.document.SetUnits.assert_not_called()

    def test_unproved_fraction_profile_refuses_without_mutation(self):
        for units in ((3, 2, 16, 3, -1), (3, 1, 16, 3, 0), (7, 1, 0, 3, 0), (0, 0, 0, 3, 0)):
            with self.subTest(units=units):
                self.units = units
                result = self.operation("document.units-set", {"decimal_places": 4})
                self.assertFalse(result["ok"])
                self.assertFalse(result["mutation"]["attempted"])
        self.document.SetUnits.assert_not_called()

    def test_hosted_decimal_zero_denominator_is_preserved_for_changes_and_noop(self):
        for request, expected in (
            ({"length_unit": "inch"}, (3, 1, 0, 2, False)),
            ({"decimal_places": 0}, (0, 1, 0, 0, False)),
            ({"decimal_places": 8}, (0, 1, 0, 8, False)),
        ):
            with self.subTest(request=request):
                self.units = (0, 1, 0, 2, 0)
                self.modified = False
                self.document.SetUnits.reset_mock()
                self.document.SetSaveFlag.reset_mock()
                result = self.operation("document.units-set", request)
                self.assertTrue(result["ok"], result)
                self.assertTrue(result["changed"])
                self.document.SetUnits.assert_called_once_with(*expected)
                self.assertEqual(result["units"]["native_units"]["fraction_value"], 0)
                self.document.SetUnits.reset_mock()
                self.document.SetSaveFlag.reset_mock()
                noop = self.operation("document.units-set", request)
                self.assertTrue(noop["ok"], noop)
                self.assertFalse(noop["changed"])
                self.document.SetUnits.assert_not_called()
                self.document.SetSaveFlag.assert_not_called()

    def test_native_zero_denominator_normalization_is_a_partial_failure_not_equivalent(self):
        self.units = (0, 1, 0, 2, 0)
        self.document.SetUnits.side_effect = lambda *values: self.apply_units(
            values[0], values[1], 8, values[3], values[4])
        result = self.operation("document.units-set", {"length_unit": "inch"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.document.SetUnits.assert_called_once_with(3, 1, 0, 2, False)
        self.document.SetSaveFlag.assert_not_called()

    def test_native_failure_or_readback_mismatch_never_retries_or_rolls_back(self):
        for failure in (RuntimeError("setter failed"), None):
            with self.subTest(failure=failure):
                self.document.SetUnits = mock.Mock(side_effect=failure)
                result = self.operation("document.units-set", {"length_unit": "inch"})
                self.assertFalse(result["ok"])
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.document.SetUnits.assert_called_once_with(3, 1, 8, 3, False)

    def test_readback_cannot_clear_an_existing_dirty_flag(self):
        self.modified = True
        reads = 0

        def read():
            nonlocal reads
            reads += 1
            if reads == 2:
                self.modified = False
            return self.units

        self.document.GetUnits = mock.Mock(spec=(), side_effect=read)
        result = self.operation("document.units-set", {"length_unit": "inch"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.document.SetUnits.assert_called_once_with(3, 1, 8, 3, False)
        self.document.SetSaveFlag.assert_not_called()
        self.assertEqual(self.document.GetUnits.call_count, 2)

    def test_readback_cannot_change_the_update_stamp(self):
        self.modified = True
        stamp = 7
        reads = 0

        def read():
            nonlocal reads, stamp
            reads += 1
            if reads == 2:
                stamp = 99
            return self.units

        self.document.GetUpdateStamp = lambda: stamp
        self.document.GetUnits = mock.Mock(spec=(), side_effect=read)
        result = self.operation("document.units-set", {"length_unit": "inch"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.document.SetUnits.assert_called_once_with(3, 1, 8, 3, False)
        self.document.SetSaveFlag.assert_not_called()
        self.assertEqual(self.document.GetUnits.call_count, 2)

    def test_setter_can_change_stamp_before_a_stable_readback(self):
        stamp = 7

        def set_units(*values):
            nonlocal stamp
            self.apply_units(*values)
            stamp = 99

        self.document.GetUpdateStamp = lambda: stamp
        self.document.SetUnits.side_effect = set_units
        result = self.operation("document.units-set", {"length_unit": "inch"})
        validate_operation_result("document.units-set", result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["document"]["update_stamp"], 99)
        self.assertTrue(result["document"]["modified"])
        self.document.SetUnits.assert_called_once_with(3, 1, 8, 3, False)
        self.document.SetSaveFlag.assert_called_once_with()

    def test_read_rejects_foreground_or_configuration_drift(self):
        for change in (lambda: setattr(self.app, "ActiveDoc", self.document),
                       lambda: setattr(self.configuration, "Name", "Other")):
            with self.subTest(change=change):
                self.app.ActiveDoc = self.foreground
                self.configuration.Name = "Default"
                def read():
                    change()
                    return self.units
                self.document.GetUnits = mock.Mock(spec=(), side_effect=read)
                result = self.operation("document.units", session="reader")
                self.assertFalse(result["ok"])
        self.document.SetUnits.assert_not_called()

    def test_write_refuses_an_active_sketch_without_exiting_it(self):
        edit = object()
        self.document.SketchManager.ActiveSketch = edit
        result = self.operation("document.units-set", {"length_unit": "inch"})
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation"]["attempted"])
        self.assertIs(self.document.SketchManager.ActiveSketch, edit)
        self.document.SetUnits.assert_not_called()

    def test_read_preserves_existing_edit_identity_and_rejects_changed_edit(self):
        edit = object()
        self.document.SketchManager.ActiveSketch = edit
        result = self.operation("document.units", session="reader")
        self.assertTrue(result["ok"], result)
        self.assertIs(self.document.SketchManager.ActiveSketch, edit)

        def read():
            self.document.SketchManager.ActiveSketch = object()
            return self.units

        self.document.GetUnits = mock.Mock(spec=(), side_effect=read)
        result = self.operation("document.units", session="reader")
        self.assertFalse(result["ok"])
        self.document.SetUnits.assert_not_called()

    def test_expected_option_values_refuse_before_any_native_setter(self):
        for expected in ({"expected_length_unit": "inch"}, {"expected_decimal_places": 2}):
            with self.subTest(expected=expected):
                result = self.operation("document.units-set", {"length_unit": "inch", **expected})
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["type"], "DocumentUnitsConflict")
                self.assertFalse(result["mutation"]["attempted"])
        self.document.SetUnits.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()

    def test_expected_values_detect_prior_units_edit_when_stamp_is_unchanged(self):
        first = self.operation("document.units-set", {"length_unit": "inch", "decimal_places": 4})
        self.assertTrue(first["ok"], first)
        self.document.SetUnits.reset_mock()
        self.document.SetSaveFlag.reset_mock()
        result = self.operation("document.units-set", {
            "length_unit": "mm", "expected_length_unit": "mm", "expected_decimal_places": 3,
        })
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "DocumentUnitsConflict")
        self.document.SetUnits.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()

    def test_dirty_flag_native_call_cannot_silently_change_edit_identity(self):
        def mark_modified():
            self.modified = True
            self.document.SketchManager.ActiveSketch = object()
        self.document.SetSaveFlag.side_effect = mark_modified
        result = self.operation("document.units-set", {"length_unit": "inch"})
        self.assertFalse(result["ok"])
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.document.SetUnits.assert_called_once()
        self.document.SetSaveFlag.assert_called_once()

    def test_contract_only_accepts_explicit_document_length_options(self):
        for values in ({}, {"decimal_places": True}, {"decimal_places": -1},
                       {"decimal_places": 9}, {"length_unit": "meter"},
                       {"length_unit": "mm", "unit_system": "MMGS"},
                       {"expected_length_unit": "mm"},
                       {"length_unit": "inch", "expected_decimal_places": True}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_operation_request("document.units-set", values)
        self.assertFalse(OPERATION_CATALOG["document.units"].lease_guarded)
        self.assertTrue(OPERATION_CATALOG["document.units-set"].lease_guarded)
        self.assertFalse(OPERATION_CATALOG["document.units-set"].temporary_activation)
        with self.assertRaises(ValueError):
            validate_operation_request("document.units", {}, lease_id=self.lease["lease_id"])

    def test_strict_result_schema_rejects_incomplete_or_mistyped_native_units(self):
        original = self.operation("document.units", session="reader")
        validate_operation_result("document.units", original)
        for mutation in (lambda units: units["native_units"].pop("fraction_base"),
                         lambda units: units["native_units"].update(round_to_fraction=False),
                         lambda units: units.update(units_system="MMGS")):
            result = deepcopy(original)
            mutation(result["units"])
            with self.subTest(result=result), self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.units", result)

    def test_cli_maps_unit_precision_and_document_guards(self):
        args = build_parser().parse_args([
            "document", "units-set", "--length-unit", "inch", "--decimal-places", "4",
            "--document", self.entry.document_id, "--if-update-stamp", "7", "--lease", self.lease["lease_id"],
            "--if-length-unit", "mm", "--if-decimal-places", "3", "--json",
        ])
        self.assertEqual(_typed_operation(args), (
            "document.units-set", {"length_unit": "inch", "decimal_places": 4,
                                   "expected_length_unit": "mm", "expected_decimal_places": 3}, True,
            self.entry.document_id, 7, self.lease["lease_id"],
        ))
        args = build_parser().parse_args(["document", "units", "--document", self.entry.document_id, "--json"])
        self.assertEqual(_typed_operation(args), ("document.units", {}, True, self.entry.document_id, None, None))
