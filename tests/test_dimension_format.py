"""Dimension display guards, native behavior, and public fail-closed boundary."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from jsonschema import Draft202012Validator
import test_document_annotations as annotation_tests
from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentLeaseConflict
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.daemon import server
from swcli.hosts import windows_dimension_format as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid


class DimensionFormatTests(unittest.TestCase):
    def setUp(self):
        fixture = annotation_tests.DocumentAnnotationTests()
        fixture.setUp()
        self.__dict__.update(fixture.__dict__)
        self.fixture = fixture
        self.app.RevisionNumber = "uncalibrated-test"
        self.foreground.GetActiveConfiguration = lambda: SimpleNamespace(Name="Default")
        self.foreground.Extension = SimpleNamespace()
        self.native.update({43: False, 14: 1, 48: False})
        self.document.GetUnits = lambda: (0, 1, 0, 2, 0)
        self.before = {"dual_display": False, "dual_position": 1, "parentheses": False}

    def public(self, write=False, values=None, **context):
        defaults = dict(document_id=self.entry.document_id, expected_update_stamp=7,
                        lease_id=self.lease["lease_id"] if write else None)
        defaults.update(context)
        return execute_operation(self.app, "document.dimension-format" + ("-set" if write else ""),
                                 values or {}, documents=self.documents, session_id="writer", **defaults)

    def values(self, field="dual_display", value=True):
        return dict(field=field, value=value, expected_format=deepcopy(self.before))

    def edit(self, **values):
        parameters = self.values()
        parameters.update(values)
        return adapter.set_dimension_format_windows(app=self.app, document=self.document,
                                                    _calibration=True, **parameters)

    def test_background_read_retains_raw_unknown_position_and_never_sets(self):
        self.native[14] = 456
        result = self.public()
        self.assertTrue(result["ok"], result)
        validate_operation_result("document.dimension-format", result)
        self.assertEqual(result["format"], {**self.before, "dual_position": 456})
        self.assertFalse(result["document"]["active"])
        self.fixture.assert_no_setters()

    def test_required_context_prevents_unleased_or_stale_writes_before_native_reads(self):
        for context in (dict(document_id=None), dict(expected_update_stamp=None), dict(lease_id=None)):
            with self.subTest(context=context), self.assertRaises(ValueError):
                self.public(True, self.values(), **context)
        with self.assertRaises(DocumentLeaseConflict):
            self.public(True, self.values(), lease_id="l-deadbeef")
        with self.assertRaises(DocumentUpdateConflict):
            self.public(True, self.values(), expected_update_stamp=6)
        self.extension.GetUserPreferenceInteger.assert_not_called()
        self.extension.GetUserPreferenceToggle.assert_not_called()
        self.fixture.assert_no_setters()

    def test_public_mutation_is_closed_but_same_value_is_a_clean_noop(self):
        result = self.public(True, self.values())
        validate_operation_result("document.dimension-format-set", result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "DimensionFormatNotCalibrated")
        self.assertFalse(result["mutation"]["attempted"])
        same = self.public(True, self.values(value=False))
        validate_operation_result("document.dimension-format-set", same)
        self.assertTrue(same["ok"], same)
        self.assertFalse(same["changed"])
        self.fixture.assert_no_setters()

    def test_private_write_uses_only_mapped_document_setter(self):
        for field, value, args in (("dual_display", True, (43, 200, True)),
                                   ("dual_position", "bottom", (14, 200, 4)),
                                   ("parentheses", True, (48, 0, True))):
            with self.subTest(field=field):
                self.setUp()
                result = self.edit(field=field, value=value)
                self.assertTrue(result["ok"], result)
                method = self.extension.SetUserPreferenceInteger if field == "dual_position" else self.extension.SetUserPreferenceToggle
                method.assert_called_once_with(*args)
                self.assertEqual(result["before"], self.before)
                self.assertEqual(result["format"], {**self.before, field: args[-1]})
                self.assertTrue(result["changed"])
                self.assertTrue(self.fixture.modified)
                self.app.ActivateDoc3.assert_not_called()
                self.app.SetUserPreferenceToggle.assert_not_called()
                self.app.SetUserPreferenceIntegerValue.assert_not_called()

    def test_complete_cas_checks_an_unrequested_field_even_at_same_stamp(self):
        self.native[48] = True
        result = self.edit()
        self.assertEqual(result["error"]["type"], "DocumentDimensionFormatConflict")
        self.assertFalse(result["mutation"]["attempted"])
        self.fixture.assert_no_setters()

    def test_native_failure_false_and_mismatch_are_partial_without_retry_or_rollback(self):
        for behavior in (RuntimeError("first failure"), False, True):
            with self.subTest(behavior=behavior):
                self.setUp()
                self.extension.SetUserPreferenceToggle.side_effect = behavior if isinstance(behavior, Exception) else lambda *a: behavior
                result = self.edit()
                self.assertFalse(result["ok"])
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceToggle.assert_called_once_with(43, 200, True)
                self.document.SetSaveFlag.assert_not_called()

    def test_unrequested_display_units_or_zero_mutations_are_rejected(self):
        for damage in (lambda: self.native.update({48: True}),
                       lambda: setattr(self.document, "GetUnits", lambda: (3, 1, 0, 2, 0)),
                       lambda: self.native.update({265: 2})):
            with self.subTest(damage=damage):
                self.setUp()
                def apply(*args):
                    self.fixture.apply(*args)
                    damage()
                    return True
                self.extension.SetUserPreferenceToggle.side_effect = apply
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.extension.SetUserPreferenceToggle.assert_called_once()

    def test_readonly_sketch_and_identity_drift_refuse(self):
        for mutate in (lambda: setattr(self.document, "IsOpenedReadOnly", lambda: True),
                       lambda: setattr(self.document, "IsOpenedViewOnly", lambda: True),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", object())):
            with self.subTest(mutate=mutate):
                self.setUp(); mutate()
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["mutation"]["attempted"])
                self.fixture.assert_no_setters()
        self.setUp()
        original = self.extension.GetUserPreferenceToggle.side_effect
        def drift(*args):
            self.document.GetPathName = lambda: "changed.SLDPRT"
            return original(*args)
        self.extension.GetUserPreferenceToggle.side_effect = drift
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["mutation"]["attempted"])

    def test_unreadable_identity_refuses_before_native_preference_access(self):
        for member, value in (("GetTitle", None), ("GetTitle", ""), ("GetPathName", None)):
            with self.subTest(member=member, value=value):
                self.setUp()
                setattr(self.document, member, lambda value=value: value)
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["mutation"]["attempted"])
                self.extension.GetUserPreferenceToggle.assert_not_called()
                self.extension.GetUserPreferenceInteger.assert_not_called()
                self.fixture.assert_no_setters()

    def test_dirty_marking_cannot_change_native_values_or_hide_read_state_mutation(self):
        for damage in (lambda: self.native.update({48: True}),
                       lambda: setattr(self.document, "GetUpdateStamp", lambda: 88),
                       lambda: setattr(self.fixture, "modified", False)):
            with self.subTest(damage=damage):
                self.setUp()
                calls = 0
                original = adapter._read_format
                def read(document):
                    nonlocal calls
                    calls += 1
                    if calls == 4: damage()
                    return original(document)
                with mock.patch.object(adapter, "_read_format", side_effect=read):
                    result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["attempted"])
                self.document.SetSaveFlag.assert_called_once()

    def test_foreground_state_and_identity_drift_are_partial_failures(self):
        for member, replacement in (("GetUpdateStamp", lambda: 99999),
                                    ("GetSaveFlag", lambda: True),
                                    ("GetTitle", lambda: "Peer changed"),
                                    ("GetPathName", lambda: "C:\\peer-changed.SLDPRT"),
                                    ("GetActiveConfiguration", lambda: SimpleNamespace(Name="Other")),
                                    ("Extension", object())):
            with self.subTest(member=member):
                self.setUp()
                def apply(*args):
                    self.fixture.apply(*args)
                    setattr(self.foreground, member, replacement)
                    return True
                self.extension.SetUserPreferenceToggle.side_effect = apply
                result = self.edit()
                validate_operation_result("document.dimension-format-set", result)
                self.assertFalse(result["ok"], result)
                self.assertIn("foreground document", result["error"]["message"])
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceToggle.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()
                self.assertIs(getattr(self.foreground, member), replacement)

    def test_foreground_drift_during_read_noop_and_dirty_marking_is_rejected(self):
        for stage in ("read", "noop", "dirty"):
            with self.subTest(stage=stage):
                self.setUp()
                def damage():
                    self.foreground.GetSaveFlag = lambda: True
                if stage == "dirty":
                    def mark():
                        self.fixture.modified = True
                        damage()
                    self.document.SetSaveFlag.side_effect = mark
                    result = self.edit()
                else:
                    original = self.extension.GetUserPreferenceToggle.side_effect
                    def read(*args):
                        damage()
                        return original(*args)
                    self.extension.GetUserPreferenceToggle.side_effect = read
                    result = self.public() if stage == "read" else self.edit(value=False)
                self.assertFalse(result["ok"], result)
                self.assertTrue(self.foreground.GetSaveFlag())
                if stage == "dirty":
                    self.assertTrue(result["mutation"]["may_have_changed"])
                    self.extension.SetUserPreferenceToggle.assert_called_once()
                    self.document.SetSaveFlag.assert_called_once()
                else:
                    self.fixture.assert_no_setters()

    def test_active_target_write_and_no_foreground_write_remain_supported(self):
        for active in ("target", "none"):
            with self.subTest(active=active):
                self.setUp()
                self.app.ActiveDoc = self.document if active == "target" else None
                result = self.edit()
                self.assertTrue(result["ok"], result)
                self.document.SetSaveFlag.assert_called_once()

    def test_handler_preserves_receipt_when_final_document_observation_fails(self):
        for failure in ("postflight", "native", "cas"):
            with self.subTest(failure=failure):
                self.setUp()
                if failure == "native":
                    self.extension.SetUserPreferenceToggle.side_effect = RuntimeError("first native failure")
                if failure == "cas":
                    self.native[48] = True
                original_describe = self.documents.describe
                observations = 0
                def observe(*args, **kwargs):
                    nonlocal observations
                    observations += 1
                    if observations == 2:
                        raise RuntimeError("postflight failed")
                    return original_describe(*args, **kwargs)
                with mock.patch.object(adapter, "CALIBRATED_DOCUMENT_TYPES", frozenset({1})), \
                        mock.patch.object(adapter, "CALIBRATED_HOST_REVISIONS", frozenset({"33.test"})), \
                        mock.patch.object(adapter, "_native_windows", return_value=True), \
                        mock.patch.object(self.documents, "describe", side_effect=observe) as describe:
                    self.app.RevisionNumber = "33.test"
                    result = self.public(True, self.values())
                validate_operation_result("document.dimension-format-set", result)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": failure != "cas", "may_have_changed": failure != "cas"})
                self.assertEqual(result["error"]["message"], "first native failure" if failure == "native" else
                                 "dimension display snapshot no longer matches expected_format" if failure == "cas" else "postflight failed")
                self.assertEqual(result["warnings"][0]["code"], "DocumentObservationFailed")
                self.assertEqual(result["before"], {**self.before, "parentheses": failure == "cas"})
                if failure == "postflight":
                    self.assertEqual(result["format"], {**self.before, "dual_display": True})
                    self.assertTrue(result["native_return"])
                    self.assertTrue(result["changed"])
                self.assertEqual(describe.call_count, 2)
                self.assertEqual(self.extension.SetUserPreferenceToggle.call_count, 0 if failure == "cas" else 1)

    def test_worker_returns_handler_partial_receipt_after_postflight_failure(self):
        for failure in ("postflight", "native", "cas"):
            with self.subTest(failure=failure):
                self.setUp()
                self.app.RevisionNumber = "33.test"
                self.app.GetProcessID = lambda: 1234
                if failure == "native":
                    self.extension.SetUserPreferenceToggle.side_effect = RuntimeError("first native failure")
                pythoncom, com_client, responses = mock.Mock(), mock.Mock(), mock.Mock()
                if failure == "cas":
                    self.native[48] = True
                original_describe = self.documents.describe
                observations = 0
                def observe(*args, **kwargs):
                    nonlocal observations
                    observations += 1
                    if observations == 2:
                        raise RuntimeError("postflight failed")
                    return original_describe(*args, **kwargs)
                request = dict(request_id="partial-receipt", operation="document.dimension-format-set",
                               parameters=self.values(), session_id="writer", document_id=self.entry.document_id,
                               expected_update_stamp=7, lease_id=self.lease["lease_id"])
                with mock.patch.dict("sys.modules", {"pythoncom": pythoncom,
                            "win32com": mock.Mock(client=com_client), "win32com.client": com_client}), \
                        mock.patch.object(server, "acquire_resident_app", return_value=(self.app, False)), \
                        mock.patch.object(server, "wait_windows_host_ready", return_value=0), \
                        mock.patch.object(server, "DocumentRegistry", return_value=self.documents), \
                        mock.patch.object(server, "_describe_app", return_value={}), \
                        mock.patch.object(server, "_wait_for_worker_request", side_effect=[request, None]), \
                        mock.patch.object(adapter, "CALIBRATED_DOCUMENT_TYPES", frozenset({1})), \
                        mock.patch.object(adapter, "CALIBRATED_HOST_REVISIONS", frozenset({"33.test"})), \
                        mock.patch.object(adapter, "_native_windows", return_value=True), \
                        mock.patch.object(self.documents, "describe", side_effect=observe) as describe:
                    server._worker_main(mock.Mock(), responses, mock.Mock(), True, 120, True)
                responses.put.assert_called_once()
                response = responses.put.call_args.args[0]
                self.assertFalse(response["success"], response)
                self.assertEqual(response["error"]["message"], "first native failure" if failure == "native" else
                                 "dimension display snapshot no longer matches expected_format" if failure == "cas" else "postflight failed")
                self.assertEqual(response["result"]["mutation"], {"attempted": failure != "cas", "may_have_changed": failure != "cas"})
                validate_operation_result(request["operation"], response["result"])
                self.assertEqual(describe.call_count, 2)
                self.assertEqual(self.extension.SetUserPreferenceToggle.call_count, 0 if failure == "cas" else 1)
                pythoncom.CoUninitialize.assert_called_once()

    def test_request_contract_rejects_incomplete_native_snapshot_and_wrong_value_type(self):
        spec = OPERATION_CATALOG["document.dimension-format-set"]
        self.assertTrue(spec.lease_guarded)
        self.assertFalse(spec.temporary_activation)
        for change in (dict(value=1), dict(field="zero.leading"), dict(expected_format={}),
                       dict(expected_format={**self.before, "dual_position": True}),
                       dict(_calibration=True)):
            values = {**self.values(), **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_operation_request("document.dimension-format-set", values, document_id=self.entry.document_id,
                                           expected_update_stamp=7, lease_id=self.lease["lease_id"])
            self.assertFalse(Draft202012Validator(spec.parameters).is_valid(values))

    def test_drawing_normal_sheet_and_unsafe_edit_modes(self):
        self.fixture.drawing_context()
        result = self.edit()
        self.assertTrue(result["ok"], result)
        for damage in (lambda: setattr(self.fixture, "edit_sheet", False),
                       lambda: setattr(self.document, "ActiveDrawingView", object()),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", self.fixture.template_sketch)):
            with self.subTest(damage=damage):
                self.setUp()
                self.fixture.drawing_context()
                damage()
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["mutation"]["attempted"])
                self.fixture.assert_no_setters()

    def test_public_write_requires_exact_calibrated_host_revision(self):
        self.app.RevisionNumber = "33.test"
        with mock.patch.object(adapter, "CALIBRATED_DOCUMENT_TYPES", frozenset({1})), \
                mock.patch.object(adapter, "CALIBRATED_HOST_REVISIONS", frozenset({"33.test"})), \
                mock.patch.object(adapter, "_native_windows", return_value=True):
            result = self.public(True, self.values())
            self.assertTrue(result["ok"], result)
            self.extension.SetUserPreferenceToggle.assert_called_once_with(43, 200, True)
        self.setUp()
        self.app.RevisionNumber = "34.0"
        with mock.patch.object(adapter, "CALIBRATED_DOCUMENT_TYPES", frozenset({1})), \
                mock.patch.object(adapter, "CALIBRATED_HOST_REVISIONS", frozenset({"33.test"})):
            result = self.public(True, self.values())
        self.assertEqual(result["error"]["type"], "DimensionFormatNotCalibrated")
        self.fixture.assert_no_setters()

    def test_native_windows_detection_fails_closed_for_wine_and_load_errors(self):
        from types import SimpleNamespace
        with mock.patch.object(adapter.sys, "platform", "win32"), \
                mock.patch.object(adapter.ctypes, "WinDLL", create=True, return_value=SimpleNamespace()):
            self.assertTrue(adapter._native_windows())
        with mock.patch.object(adapter.sys, "platform", "win32"), \
                mock.patch.object(adapter.ctypes, "WinDLL", create=True, return_value=SimpleNamespace(wine_get_version=object())):
            self.assertFalse(adapter._native_windows())
        with mock.patch.object(adapter.sys, "platform", "win32"), \
                mock.patch.object(adapter.ctypes, "WinDLL", create=True, side_effect=OSError("unavailable")):
            self.assertFalse(adapter._native_windows())

    def test_native_windows_evidence_does_not_enable_wine_or_unknown_platform(self):
        self.app.RevisionNumber = "33.test"
        with mock.patch.object(adapter, "CALIBRATED_DOCUMENT_TYPES", frozenset({1})), \
                mock.patch.object(adapter, "CALIBRATED_HOST_REVISIONS", frozenset({"33.test"})), \
                mock.patch.object(adapter, "_native_windows", return_value=False):
            result = self.public(True, self.values())
        self.assertEqual(result["error"]["type"], "DimensionFormatNotCalibrated")
        self.fixture.assert_no_setters()

    def test_unknown_native_position_is_readable_but_cannot_be_mutated(self):
        self.native[14] = 999
        result = self.edit(expected_format={**self.before, "dual_position": 999})
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], "ValueError")
        self.assertFalse(result["mutation"]["attempted"])
        self.fixture.assert_no_setters()

    def test_native_setter_cannot_clear_preexisting_dirty_state(self):
        self.fixture.modified = True
        def clear_dirty(*args):
            self.fixture.apply(*args)
            self.fixture.modified = False
            return True
        self.extension.SetUserPreferenceToggle.side_effect = clear_dirty
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertIn("cleared an existing dirty", result["error"]["message"])
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.document.SetSaveFlag.assert_not_called()
        self.extension.SetUserPreferenceToggle.assert_called_once()

    def test_result_contract_rejects_falsified_mutation_lifecycle(self):
        result = self.public(True, self.values(value=False))
        for change in (dict(changed=True), dict(mutation={"attempted": True, "may_have_changed": True}),
                       dict(format={**self.before, "parentheses": True})):
            with self.subTest(change=change), self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.dimension-format-set", {**result, **change})

    def test_cli_parses_snapshot_and_false_exactly(self):
        args = build_parser().parse_args(["document", "dimension-format-set", "parentheses", "false",
            "--if-format", json.dumps(self.before), "--document", self.entry.document_id,
            "--if-update-stamp", "7", "--lease", self.lease["lease_id"], "--json"])
        result = _typed_operation(args)
        self.assertEqual(result[0], "document.dimension-format-set")
        self.assertEqual(result[1], self.values(field="parentheses", value=False))
        result = self.public()
        result["format"]["dual_display"] = 1
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.dimension-format", result)


if __name__ == "__main__":
    unittest.main()
