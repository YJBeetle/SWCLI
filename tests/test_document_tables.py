"""Table CAS, native partial mutation, applicability and public write gate."""

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest import mock

from jsonschema import Draft202012Validator
from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.document_tables import TABLE_FIELDS, TABLE_OPTIONS_SCHEMA
from swcli.hosts import windows_document_tables as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid


class DocumentTableTests(unittest.TestCase):
    def setUp(self):
        self.constants = {spec["symbol"]: index for index, spec in enumerate(TABLE_FIELDS.values(), 200)}
        self.constants["swDetailingNoOptionSpecified"] = 0
        self.native = {200: False, 201: 1, 202: 0, 203: 1, 204: 0}
        self.modified, self.stamp, self.kind, self.title, self.path = False, 7, 1, "Target", ""
        self.configuration = SimpleNamespace(Name="Default")
        self.extension = SimpleNamespace()
        for kind in ("Integer", "Toggle"):
            setattr(self.extension, "GetUserPreference" + kind,
                    mock.Mock(side_effect=lambda preference, option: self.native[preference]))
            setattr(self.extension, "SetUserPreference" + kind, mock.Mock(side_effect=self.apply))
        self.document = SimpleNamespace(
            GetType=lambda: self.kind, GetTitle=lambda: self.title, GetPathName=lambda: self.path,
            GetSaveFlag=lambda: self.modified, GetUpdateStamp=lambda: self.stamp,
            GetActiveConfiguration=lambda: self.configuration, IsOpenedReadOnly=lambda: False,
            IsOpenedViewOnly=lambda: False, SketchManager=SimpleNamespace(ActiveSketch=None),
            Extension=self.extension, SetSaveFlag=mock.Mock(side_effect=lambda: setattr(self, "modified", True)))
        self.foreground_modified = False
        self.foreground = SimpleNamespace(GetType=lambda: 1, GetTitle=lambda: "Peer", GetPathName=lambda: "",
            GetSaveFlag=lambda: self.foreground_modified, GetUpdateStamp=lambda: 8,
            GetActiveConfiguration=lambda: SimpleNamespace(Name="Default"))
        self.app = SimpleNamespace(ActiveDoc=self.foreground, GetDocuments=lambda: (self.document, self.foreground),
            IsSame=lambda first, second: int(first is second), RevisionNumber=lambda: "33.5.0",
            ActivateDoc3=mock.Mock(), SetUserPreferenceToggle=mock.Mock(), SetUserPreferenceIntegerValue=mock.Mock())
        self.constants_patch = mock.patch.object(adapter, "_constants", return_value=self.constants)
        self.constants_patch.start()
        self.addCleanup(self.constants_patch.stop)
        self.register()

    def register(self):
        self.documents = DocumentRegistry(self.app)
        self.entry = self.documents.register(self.document)
        self.documents.set_current(self.documents.register(self.foreground), session_id="reader")
        self.lease = self.documents.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)["lease_id"]

    def apply(self, preference, option, value):
        self.native[preference] = value
        return True

    def read(self):
        result = execute_operation(self.app, "document.table-options", {}, documents=self.documents,
                                   session_id="reader", document_id=self.entry.document_id, expected_update_stamp=self.stamp)
        validate_operation_result("document.table-options", result)
        return result

    def edit(self, field="bom.box_border", value="thick", expected=None, *, calibrated=True, session="writer", stamp=7, lease=None):
        if expected is None:
            expected = adapter._read_options(self.document, self.constants)
        with mock.patch.object(adapter, "_CALIBRATED_PROFILES", {("33.5.0", self.kind)} if calibrated else set()):
            result = execute_operation(self.app, "document.table-option-set",
                dict(field=field, value=value, expected_options=expected), documents=self.documents,
                session_id=session, document_id=self.entry.document_id, expected_update_stamp=stamp,
                lease_id=self.lease if lease is None else lease)
        validate_operation_result("document.table-option-set", result)
        return result

    def no_setters(self):
        self.extension.SetUserPreferenceInteger.assert_not_called()
        self.extension.SetUserPreferenceToggle.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.app.SetUserPreferenceToggle.assert_not_called()
        self.app.SetUserPreferenceIntegerValue.assert_not_called()

    def drawing(self):
        self.kind = 3
        self.sheet_sketch, self.template_sketch = object(), object()
        sheet = SimpleNamespace(GetName=lambda: "Sheet1", GetTemplateSketch=lambda: self.template_sketch)
        view = SimpleNamespace(GetName2=lambda: "Sheet1", GetReferencedModelName=lambda: "",
                               GetSketch=lambda: self.sheet_sketch)
        self.document.GetCurrentSheet = lambda: sheet
        self.document.GetFirstView = lambda: view
        self.document.GetEditSheet = lambda: True
        self.document.ActiveDrawingView = None
        self.document.SketchManager.ActiveSketch = self.sheet_sketch
        self.register()

    def test_reads_background_without_activation_and_skips_general_on_models(self):
        for kind in (1, 2):
            self.kind = kind
            self.register()
            result = self.read()
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["options"]["general.box_border"], {"unavailable": "document_type"})
            self.extension.GetUserPreferenceInteger.assert_any_call(201, 0)
            self.assertFalse(any(call.args[0] in (203, 204) for call in self.extension.GetUserPreferenceInteger.call_args_list))
        self.no_setters()

    def test_public_gate_is_closed_and_not_request_bypassable(self):
        result = self.edit(calibrated=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "DocumentTableCalibrationRequired")
        self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
        self.no_setters()
        values = dict(field="bom.box_border", value="thick", expected_options={})
        for key in ("calibration", "allow_uncalibrated", "force"):
            with self.assertRaises(ValueError):
                validate_operation_request("document.table-option-set", {**values, key: True})

    def test_all_field_roundtrips_noop_and_document_applicability(self):
        self.drawing()
        for field, spec in TABLE_FIELDS.items():
            with self.subTest(field=field):
                value = True if spec["kind"] == "Toggle" else "thick"
                result = self.edit(field, value)
                self.assertTrue(result["ok"], result)
                self.assertTrue(result["changed"])
                method = getattr(self.extension, "SetUserPreference" + spec["kind"])
                method.assert_called_with(self.constants[spec["symbol"]], 0, True if spec["kind"] == "Toggle" else 2)
                count = method.call_count
                same = self.edit(field, value)
                self.assertTrue(same["ok"], same)
                self.assertFalse(same["changed"])
                self.assertEqual(method.call_count, count)
        self.app.ActivateDoc3.assert_not_called()

    def test_full_snapshot_cas_rejects_unrequested_drift_and_raw_unknown_change(self):
        expected = self.read()["options"]
        self.native[202] = 777
        result = self.edit(expected=expected)
        self.assertEqual(result["error"]["type"], "DocumentTableConflict")
        expected = self.read()["options"]
        self.assertEqual(expected["bom.grid_border"], {"value": "other", "native_value": 777})
        self.native[202] = 778
        result = self.edit(expected=expected)
        self.assertEqual(result["error"]["type"], "DocumentTableConflict")
        self.no_setters()

    def test_write_requires_explicit_identity_stamp_and_owning_lease(self):
        values = dict(field="bom.box_border", value="thick", expected_options=self.read()["options"])
        context = dict(document_id=self.entry.document_id, expected_update_stamp=7, lease_id=self.lease)
        for key in context:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_operation_request("document.table-option-set", values, **{k: v for k, v in context.items() if k != key})
        with self.assertRaises(DocumentUpdateConflict):
            self.edit(stamp=6)
        with self.assertRaises(DocumentLeaseConflict):
            self.edit(session="reader")
        self.no_setters()

    def test_readonly_viewonly_sketch_and_unsupported_type_reject_before_setter(self):
        for attribute in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            original = getattr(self.document, attribute)
            setattr(self.document, attribute, lambda: True)
            self.assertFalse(self.edit()["ok"])
            setattr(self.document, attribute, original)
        self.document.SketchManager.ActiveSketch = object()
        self.assertFalse(self.edit()["ok"])
        self.document.SketchManager.ActiveSketch = None
        self.assertFalse(self.edit("general.box_border", "thick")["ok"])
        self.no_setters()

    def test_false_exception_and_side_effects_preserve_partial_mutation_without_retry(self):
        for failure in ("false", "exception", "collateral", "identity", "foreground", "state", "type"):
            with self.subTest(failure=failure):
                self.setUp()
                def apply(preference, option, value):
                    self.native[preference] = value
                    if failure == "false":
                        return False
                    if failure == "exception":
                        raise RuntimeError("injected setter failure")
                    if failure == "collateral":
                        self.native[202] = 2
                    if failure == "identity":
                        self.path = "C:/changed.SLDPRT"
                    if failure == "foreground":
                        self.app.ActiveDoc = self.document
                    if failure == "state":
                        self.foreground_modified = True
                    if failure == "type":
                        self.kind = 2
                    return True
                self.extension.SetUserPreferenceInteger.side_effect = apply
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceInteger.assert_called_once_with(201, 0, 2)
                self.extension.SetUserPreferenceToggle.assert_not_called()
                self.document.SetSaveFlag.assert_not_called()
                # A partial failure is not repaired by a rollback setter.
                self.assertEqual(self.native[201], 2)
                if failure == "false":
                    self.assertIs(result["native_returned"], False)

    def test_observation_side_effects_fail_closed(self):
        for side_effect in ("dirty", "stamp", "close", "peer"):
            with self.subTest(side_effect=side_effect):
                self.setUp()
                def getter(preference, option):
                    if side_effect == "dirty": self.modified = True
                    if side_effect == "stamp": self.stamp = 8
                    if side_effect == "close": self.app.GetDocuments = lambda: (self.foreground,)
                    if side_effect == "peer": self.foreground_modified = True
                    return self.native[preference]
                self.extension.GetUserPreferenceInteger.side_effect = getter
                self.assertFalse(self.read()["ok"])
                self.no_setters()

    def test_malformed_or_inconsistent_snapshot_rejected_by_schema_and_runtime(self):
        original = self.read()["options"]
        for change in ("missing", "extra", "inconsistent", "bool_as_int"):
            value = deepcopy(original)
            if change == "missing": del value["bom.grid_border"]
            if change == "extra": value["extra"] = {}
            if change == "inconsistent": value["bom.box_border"]["value"] = "thin"
            if change == "bool_as_int": value["bom.box_border"]["native_value"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.edit(expected=value)
        self.no_setters()
        self.assertTrue(Draft202012Validator(TABLE_OPTIONS_SCHEMA).is_valid(original))

    def test_cli_and_catalog_preserve_complete_snapshot(self):
        snapshot = self.read()["options"]
        args = build_parser().parse_args(["document", "table-option-set", "bom.box_border", "thick",
            "--document", self.entry.document_id, "--if-update-stamp", "7", "--lease", self.lease,
            "--if-options-json", json.dumps(snapshot), "--json"])
        operation, values, as_json, document_id, stamp, lease = _typed_operation(args)
        self.assertEqual(operation, "document.table-option-set")
        self.assertEqual(values["expected_options"], snapshot)
        validate_operation_request(operation, values, document_id=document_id, expected_update_stamp=stamp, lease_id=lease)
        self.assertTrue(as_json)
        self.assertTrue(OPERATION_CATALOG[operation].lease_guarded)
        self.assertFalse(OPERATION_CATALOG[operation].temporary_activation)

    def test_result_rejects_false_applicability_and_lifecycle_claims(self):
        observed = self.read()
        observed["options"]["general.box_border"] = {"value": "thin", "native_value": 0}
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.table-options", observed)
        result = self.edit()
        result["mutation"]["attempted"] = False
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.table-option-set", result)


if __name__ == "__main__":
    unittest.main()
