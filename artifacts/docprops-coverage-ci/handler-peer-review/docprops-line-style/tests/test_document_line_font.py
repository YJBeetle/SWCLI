"""Portable protection and failure proofs, not native acceptance."""
import unittest
from unittest import mock
import test_document_annotations as fixtures
from swcli.hosts import windows_document_line_font as adapter
from swcli.document_line_font import LINE_FONT_FIELDS, validate_edit
from swcli.daemon.documents import DocumentLeaseConflict
from swcli.daemon.operations import DocumentUpdateConflict
from swcli.operation_schemas import validate_operation_request
from swcli.result_schemas import validate_operation_result
from swcli.cli import build_parser, _typed_operation


class LineFontTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.DocumentAnnotationTests()
        self.fx.setUp()
        self.fx.drawing_context()
        self.ids = dict(zip(LINE_FONT_FIELDS.values(), (101, 102, 103, 104)))
        self.ids["swDetailingNoOptionSpecified"] = 0
        self.fx.native = {101: 0, 102: 1, 103: 1, 104: 0}
        patch = mock.patch.object(adapter, "_constants", return_value=self.ids)
        patch.start()
        self.addCleanup(patch.stop)
        self.before = dict(zip(LINE_FONT_FIELDS, (0, 1, 1, 0)))

    def edit(self, **kw):
        return adapter.set_document_line_font_windows(
            app=self.fx.app, document=self.fx.document, field="visible_edges.style", value=1,
            expected_options=kw.pop("expected_options", self.before), **kw)

    def test_read_background_preserves_state_and_full_snapshot(self):
        result = self.fx.operation("document.line-font")
        self.assertTrue(result["ok"], result)
        validate_operation_result("document.line-font", result)
        self.assertEqual(result["options"], self.before)
        self.fx.assert_no_setters()

    def test_uncalibrated_revision_is_closed_and_protocol_cannot_accept_bypass(self):
        result = self.fx.operation("document.line-font-set", dict(field="visible_edges.style", value=1,
                                                                  expected_options=self.before))
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], "DocumentLineFontUncalibrated")
        self.assertEqual(result["mutation"], dict(attempted=False, may_have_changed=False))
        validate_operation_result("document.line-font-set", result)
        with self.assertRaises(ValueError):
            validate_operation_request("document.line-font-set", dict(field="visible_edges.style", value=1,
                expected_options=self.before, _internal_calibration=True))
        self.fx.assert_no_setters()

    def test_public_exact_calibrated_conversion_is_allowed(self):
        self.fx.app.RevisionNumber = "33.5.0"
        result = self.fx.operation("document.line-font-set", dict(field="visible_edges.style", value=1,
                                                                  expected_options=self.before))
        self.assertTrue(result["ok"], result)
        validate_operation_result("document.line-font-set", result)
        self.fx.extension.SetUserPreferenceInteger.assert_called_once_with(101, 0, 1)

    def test_uncalibrated_reverse_conversion_stays_closed(self):
        self.fx.app.RevisionNumber = "33.5.0"
        self.fx.native[101] = 1
        result = adapter.set_document_line_font_windows(app=self.fx.app, document=self.fx.document,
            field="visible_edges.style", value=0, expected_options={**self.before, "visible_edges.style": 1})
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], "DocumentLineFontUncalibrated")
        self.fx.assert_no_setters()

    def test_lease_and_stamp_guard_before_native_read(self):
        params = dict(field="visible_edges.style", value=1, expected_options=self.before)
        with self.assertRaises(DocumentLeaseConflict):
            self.fx.operation("document.line-font-set", params, session="reader")
        with self.assertRaises(DocumentUpdateConflict):
            self.fx.operation("document.line-font-set", params, stamp=6)
        self.fx.extension.GetUserPreferenceInteger.assert_not_called()

    def test_complete_cas_includes_unrequested_values(self):
        stale = {**self.before, "hidden_edges.weight": 2}
        result = self.edit(expected_options=stale, _internal_calibration=True)
        self.assertEqual(result["error"]["type"], "DocumentLineFontConflict")
        self.fx.assert_no_setters()

    def test_internal_single_setter_and_noop(self):
        result = self.edit(_internal_calibration=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["options"], {**self.before, "visible_edges.style": 1})
        self.fx.extension.SetUserPreferenceInteger.assert_called_once_with(101, 0, 1)
        self.fx.extension.SetUserPreferenceInteger.reset_mock()
        same = self.edit(expected_options=result["options"], _internal_calibration=True)
        self.assertTrue(same["ok"] and not same["changed"])
        self.fx.extension.SetUserPreferenceInteger.assert_not_called()
        self.fx.app.ActivateDoc3.assert_not_called()
        self.fx.app.SetUserPreferenceIntegerValue.assert_not_called()

    def test_failure_does_not_retry_or_rollback(self):
        for effect in (False, True, RuntimeError("failed")):
            with self.subTest(effect=effect):
                self.fx.extension.SetUserPreferenceInteger.reset_mock()
                self.fx.extension.SetUserPreferenceInteger.side_effect = None
                self.fx.extension.SetUserPreferenceInteger.return_value = effect
                if isinstance(effect, Exception):
                    self.fx.extension.SetUserPreferenceInteger.side_effect = effect
                result = self.edit(_internal_calibration=True)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
                self.fx.extension.SetUserPreferenceInteger.assert_called_once()
                self.fx.document.SetSaveFlag.assert_not_called()

    def test_scope_readonly_and_edit_context_fail_closed(self):
        for attribute, value in (("GetType", lambda: 1), ("IsOpenedReadOnly", lambda: True),
                                  ("IsOpenedViewOnly", lambda: True), ("GetEditSheet", lambda: False)):
            with self.subTest(attribute=attribute), mock.patch.object(self.fx.document, attribute, value):
                result = self.edit(_internal_calibration=True)
                self.assertFalse(result["ok"], result)
                self.fx.assert_no_setters()

    def test_unrequested_drift_and_dirty_failure_are_partial_mutations(self):
        def apply(pref, option, value):
            self.fx.native[pref] = value
            self.fx.native[104] = 2
            return True
        self.fx.extension.SetUserPreferenceInteger.side_effect = apply
        result = self.edit(_internal_calibration=True)
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.fx.extension.SetUserPreferenceInteger.assert_called_once()
        self.fx.document.SetSaveFlag.assert_not_called()

    def test_getter_context_drift_fails_observation(self):
        def read(pref, option):
            self.fx.app.ActiveDoc = self.fx.document
            return self.fx.native[pref]
        self.fx.extension.GetUserPreferenceInteger.side_effect = read
        result = self.fx.operation("document.line-font")
        self.assertFalse(result["ok"], result)
        self.fx.assert_no_setters()

    def test_strict_native_and_snapshot_values(self):
        for value in (True, 0.0, "0", None):
            self.fx.native[101] = value
            self.assertFalse(self.fx.operation("document.line-font")["ok"])
        for snapshot in ({}, {**self.before, "visible_edges.style": True}, {**self.before, "extra": 1}):
            with self.assertRaises(ValueError):
                validate_edit("visible_edges.style", 1, snapshot)
        for value in (7, -1, True, 10):
            with self.assertRaises(ValueError):
                validate_edit("visible_edges.style", value, self.before)

    def test_context_drift_after_setter_reports_partial(self):
        def apply(pref, option, value):
            self.fx.native[pref] = value
            self.fx.document.ActiveDrawingView = object()
            return True
        self.fx.extension.SetUserPreferenceInteger.side_effect = apply
        result = self.edit(_internal_calibration=True)
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.fx.extension.SetUserPreferenceInteger.assert_called_once()
        self.fx.document.SetSaveFlag.assert_not_called()

    def test_cli_full_snapshot(self):
        import json
        args = build_parser().parse_args(["document", "line-font-set", "visible_edges.style", "1",
                                          "--if-options", json.dumps(self.before), "--json"])
        self.assertEqual(_typed_operation(args)[1], dict(field="visible_edges.style", value=1,
                                                       expected_options=self.before))
