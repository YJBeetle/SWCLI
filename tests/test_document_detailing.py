"""Drawing defaults: strict full CAS, lease, context drift and partial writes."""

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentLeaseConflict, DocumentRegistry
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.document_detailing import DETAILING_FIELDS
from swcli.hosts import windows_document_detailing as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


class DetailingTests(unittest.TestCase):
    def setUp(self):
        self.modified = False
        self.fields = tuple(DETAILING_FIELDS)
        # Deliberately arbitrary portable IDs. Native IDs must come from swconst.
        self.constants = dict(zip(DETAILING_FIELDS.values(), (901, 902)))
        self.constants["swDetailingNoOptionSpecified"] = 0
        self.native = {901: False, 902: True}
        self.extension = SimpleNamespace(GetUserPreferenceToggle=mock.Mock(side_effect=lambda pref, opt: self.native[pref]),
                                         SetUserPreferenceToggle=mock.Mock(side_effect=self.apply))
        sketch, template = object(), object()
        self.document = SimpleNamespace(
            GetType=lambda: 3, GetSaveFlag=lambda: self.modified, GetUpdateStamp=lambda: 7,
            GetTitle=lambda: "Background", GetPathName=lambda: "",
            IsOpenedReadOnly=lambda: False, IsOpenedViewOnly=lambda: False,
            SketchManager=SimpleNamespace(ActiveSketch=sketch), Extension=self.extension,
            GetCurrentSheet=lambda: self.sheet, GetFirstView=lambda: self.view,
            GetEditSheet=lambda: True, ActiveDrawingView=None,
            SetSaveFlag=mock.Mock(side_effect=lambda: setattr(self, "modified", True)),
        )
        self.sheet = SimpleNamespace(GetName=lambda: "Sheet1", GetTemplateSketch=lambda: template)
        self.view = SimpleNamespace(GetName2=lambda: "Sheet1", GetSketch=lambda: sketch,
                                    GetReferencedModelName=lambda: "")
        self.foreground = SimpleNamespace(GetType=lambda: 1, GetSaveFlag=lambda: False,
            GetUpdateStamp=lambda: 8, GetTitle=lambda: "Foreground", GetPathName=lambda: "",
            ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")))
        self.app = SimpleNamespace(ActiveDoc=self.foreground, GetDocuments=lambda: (self.document, self.foreground),
            IsSame=lambda a, b: int(a is b), ActivateDoc3=mock.Mock(), RevisionNumber=lambda: "test-revision")
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        front = self.registry.register(self.foreground)
        self.registry.set_current(front, session_id="writer")
        self.lease = self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)
        self.patches = [mock.patch.object(adapter, "_constants", return_value=self.constants),
                        mock.patch.object(adapter, "_native_windows", return_value=True),
                        mock.patch.object(adapter, "CALIBRATED_REVISIONS", frozenset({"test-revision"}))]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def apply(self, pref, option, value):
        self.native[pref] = value
        return True

    def options(self):
        return dict(zip(self.fields, (self.native[901], self.native[902])))

    def call(self, operation="document.detailing-options", parameters=None, **context):
        return execute_operation(self.app, operation, parameters or {}, documents=self.registry,
            session_id=context.pop("session_id", "writer"), document_id=self.entry.document_id,
            expected_update_stamp=context.pop("expected_update_stamp", 7),
            lease_id=context.pop("lease_id", self.lease["lease_id"] if operation.endswith("-set") else None),
            **context)

    def edit(self, field=None, value=True, expected=None, **context):
        return self.call("document.detailing-option-set", {
            "field": field or self.fields[0], "value": value,
            "expected_options": self.options() if expected is None else expected}, **context)

    def assert_untouched(self):
        self.extension.SetUserPreferenceToggle.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()

    def test_background_read_write_false_and_noop(self):
        observed = self.call()
        self.assertTrue(observed["ok"], observed)
        validate_operation_result("document.detailing-options", observed)
        self.assert_untouched()
        for value in (True, False):
            result = self.edit(value=value)
            self.assertTrue(result["ok"], result)
            self.assertTrue(result["changed"])
            self.assertFalse(result["document"]["active"])
            self.assertFalse(result["document"]["current"])
            validate_operation_result("document.detailing-option-set", result)
        self.assertEqual(self.extension.SetUserPreferenceToggle.call_args_list,
                         [mock.call(901, 0, True), mock.call(901, 0, False)])
        self.assertEqual(self.document.SetSaveFlag.call_count, 1)
        self.extension.SetUserPreferenceToggle.reset_mock()
        self.document.SetSaveFlag.reset_mock()
        same = self.edit(value=False)
        self.assertTrue(same["ok"], same)
        self.assertFalse(same["changed"])
        validate_operation_result("document.detailing-option-set", same)
        self.assert_untouched()

    def test_other_field_cas_conflict_and_unobserved_revision_fail_closed(self):
        expected = self.options()
        self.native[902] = False
        result = self.edit(expected=expected)
        self.assertFalse(result["ok"], result)
        self.assert_untouched()
        with mock.patch.object(adapter, "CALIBRATED_REVISIONS", frozenset()):
            result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertIn("lack native calibration", result["error"]["message"])
        self.assert_untouched()

    def test_wine_or_unknown_runtime_cannot_use_native_windows_evidence(self):
        with mock.patch.object(adapter, "_native_windows", return_value=False):
            result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
        self.assert_untouched()

    def test_native_setter_partial_failure_never_retries_or_rolls_back(self):
        def fail(pref, option, value):
            self.native[pref] = value
            return False
        self.extension.SetUserPreferenceToggle.side_effect = fail
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.assertTrue(self.native[901])
        self.extension.SetUserPreferenceToggle.assert_called_once()
        self.document.SetSaveFlag.assert_not_called()
        validate_operation_result("document.detailing-option-set", result)

    def test_final_descriptor_failure_preserves_partial_mutation_receipt(self):
        with mock.patch("swcli.daemon.operations._with_document", side_effect=RuntimeError("descriptor unavailable")):
            result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.assertTrue(self.native[901])
        self.extension.SetUserPreferenceToggle.assert_called_once()
        validate_operation_result("document.detailing-option-set", result)

    def test_wrong_readback_or_neighbor_change_are_partial_failures(self):
        for setter in (lambda *args: True,
                       lambda pref, option, value: (self.native.update({901: value, 902: False}) or True)):
            self.native = {901: False, 902: True}
            self.extension.SetUserPreferenceToggle.reset_mock(side_effect=True)
            self.extension.SetUserPreferenceToggle.side_effect = setter
            result = self.edit()
            self.assertFalse(result["ok"], result)
            self.assertTrue(result["mutation"]["may_have_changed"])
            self.extension.SetUserPreferenceToggle.assert_called_once()

    def test_invalid_document_and_edit_modes_block_before_setter(self):
        defects = (
            (self.document, "GetType", lambda: 1),
            (self.document, "IsOpenedReadOnly", lambda: True),
            (self.document, "IsOpenedViewOnly", lambda: True),
            (self.document, "GetEditSheet", lambda: False),
            (self.document, "ActiveDrawingView", object()),
            (self.document.SketchManager, "ActiveSketch", object()),
            (self.document.SketchManager, "ActiveSketch", None),
            (self.view, "GetReferencedModelName", lambda: "foreign.SLDPRT"),
            (self.document, "GetCurrentSheet", lambda: None),
        )
        for target, key, value in defects:
            with self.subTest(key=key), mock.patch.object(target, key, value):
                result = adapter.set_document_detailing_option_windows(
                    app=self.app, document=self.document, field=self.fields[0], value=True,
                    expected_options=self.options())
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["mutation"]["attempted"])
                self.assert_untouched()

    def test_drift_during_read_or_setter_is_detected(self):
        original = self.extension.GetUserPreferenceToggle.side_effect
        def drift(pref, opt):
            self.document.GetPathName = lambda: "changed.SLDDRW"
            return original(pref, opt)
        self.extension.GetUserPreferenceToggle.side_effect = drift
        result = self.call()
        self.assertFalse(result["ok"], result)
        self.assert_untouched()
        self.extension.GetUserPreferenceToggle.side_effect = original
        self.document.GetPathName = lambda: ""
        def setter(pref, opt, value):
            self.document.GetEditSheet = lambda: False
            return self.apply(pref, opt, value)
        self.extension.SetUserPreferenceToggle.side_effect = setter
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["mutation"]["may_have_changed"])

    def test_foreground_drift_is_detected(self):
        original = self.extension.GetUserPreferenceToggle.side_effect
        def drift(pref, opt):
            self.foreground.GetSaveFlag = lambda: True
            return original(pref, opt)
        self.extension.GetUserPreferenceToggle.side_effect = drift
        result = self.call()
        self.assertFalse(result["ok"], result)
        self.assert_untouched()

    def test_dirty_mark_cannot_change_identity_or_foreground(self):
        def mark():
            self.modified = True
            self.document.GetPathName = lambda: "renamed.SLDDRW"
        self.document.SetSaveFlag.side_effect = mark
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.document.SetSaveFlag.assert_called_once()

    def test_lease_stamp_and_complete_snapshot_contracts(self):
        with self.assertRaises(DocumentUpdateConflict):
            self.edit(expected_update_stamp=6)
        with self.assertRaises(DocumentLeaseConflict):
            self.edit(session_id="other")
        params = {"field": self.fields[0], "value": True, "expected_options": self.options()}
        base = dict(document_id=self.entry.document_id, expected_update_stamp=7, lease_id=self.lease["lease_id"])
        for key in base:
            missing = {**base, key: None}
            with self.assertRaises(ValueError):
                validate_operation_request("document.detailing-option-set", params, **missing)
        for bad in ({}, {self.fields[0]: False}, {**self.options(), "foreign": False},
                    {**self.options(), self.fields[0]: 0}):
            with self.assertRaises(ValueError):
                validate_operation_request("document.detailing-option-set", {**params, "expected_options": bad}, **base)
        self.assertTrue(OPERATION_CATALOG["document.detailing-option-set"].lease_guarded)
        self.assertFalse(OPERATION_CATALOG["document.detailing-option-set"].temporary_activation)
        self.assert_untouched()

    def test_cli_full_snapshot_and_result_semantics(self):
        args = build_parser().parse_args(["document", "detailing-option-set", self.fields[0], "true",
             "--if-options", json.dumps(self.options()), "--document", self.entry.document_id,
             "--if-update-stamp", "7", "--lease", self.lease["lease_id"], "--json"])
        operation = _typed_operation(args)
        self.assertEqual(operation[0], "document.detailing-option-set")
        self.assertEqual(operation[1]["expected_options"], self.options())
        result = self.edit()
        self.assertTrue(result["ok"], result)
        invalid = deepcopy(result)
        invalid["options"][self.fields[1]] = False
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.detailing-option-set", invalid)


if __name__ == "__main__":
    unittest.main()
