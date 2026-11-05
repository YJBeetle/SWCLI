"""Typed document annotation scalars preserve context and expose partial mutation."""

from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.cli import _typed_operation, build_parser, main
from swcli.daemon.documents import DocumentLeaseConflict, DocumentRegistry
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.document_annotations import ANNOTATION_FIELDS
from swcli.hosts import windows_document_annotations as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


class DocumentAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.native = {38: 1, 39: 3, 40: 1, 375: False, 113: 0.00635, 265: 1, 15: 4}
        self.modified = False
        self.configuration = SimpleNamespace(Name="Default")
        self.extension = SimpleNamespace()
        for kind in ("Integer", "Toggle", "Double"):
            setattr(self.extension, "GetUserPreference" + kind,
                    mock.Mock(side_effect=lambda preference, option: self.native[preference]))
            setattr(self.extension, "SetUserPreference" + kind,
                    mock.Mock(side_effect=self.apply))
        self.document = SimpleNamespace(
            GetType=lambda: 1, GetSaveFlag=lambda: self.modified, GetUpdateStamp=lambda: 7,
            GetActiveConfiguration=lambda: self.configuration, GetTitle=lambda: "Background",
            GetPathName=lambda: "", IsOpenedReadOnly=lambda: False, IsOpenedViewOnly=lambda: False,
            SketchManager=SimpleNamespace(ActiveSketch=None), Extension=self.extension,
            SetSaveFlag=mock.Mock(side_effect=lambda: setattr(self, "modified", True)),
        )
        self.foreground = SimpleNamespace(
            GetType=lambda: 1, GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 8,
            GetTitle=lambda: "Foreground", GetPathName=lambda: "",
        )
        self.app = SimpleNamespace(
            ActiveDoc=self.foreground, GetDocuments=lambda: (self.document, self.foreground),
            IsSame=lambda first, second: int(first is second), ActivateDoc3=mock.Mock(),
            SetUserPreferenceIntegerValue=mock.Mock(), SetUserPreferenceToggle=mock.Mock(),
            SetUserPreferenceDoubleValue=mock.Mock(),
        )
        self.documents = DocumentRegistry(self.app)
        self.entry = self.documents.register(self.document)
        foreground = self.documents.register(self.foreground)
        self.documents.set_current(foreground, session_id="reader")
        self.lease = self.documents.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)

    def apply(self, preference, option, value):
        self.native[preference] = value
        return True

    def operation(self, operation, parameters=None, *, session="writer", stamp=7):
        return execute_operation(
            self.app, operation, parameters or {}, documents=self.documents, session_id=session,
            document_id=self.entry.document_id, expected_update_stamp=stamp,
            lease_id=(self.lease["lease_id"] if operation.endswith("-set") and session == "writer" else None),
        )

    def edit(self, field, value, expected_value, **context):
        return self.operation("document.annotation-option-set",
                              dict(field=field, value=value, expected_value=expected_value), **context)

    def assert_no_setters(self):
        for kind in ("Integer", "Toggle", "Double"):
            getattr(self.extension, "SetUserPreference" + kind).assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.app.SetUserPreferenceIntegerValue.assert_not_called()
        self.app.SetUserPreferenceToggle.assert_not_called()
        self.app.SetUserPreferenceDoubleValue.assert_not_called()

    def test_read_is_document_specific_background_read_under_another_lease(self):
        result = self.operation("document.annotation-options", session="reader")
        validate_operation_result("document.annotation-options", result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["options"]["bent_leader.length_mm"], {"value": 6.35, "native_value": 0.00635})
        self.assertEqual(result["options"]["arrow.face_surface"], {"value": "dot", "native_value": 3})
        self.assertFalse(result["document"]["active"] or result["document"]["current"])
        self.extension.GetUserPreferenceInteger.assert_any_call(265, 100)
        self.extension.GetUserPreferenceInteger.assert_any_call(15, 100)
        self.extension.GetUserPreferenceDouble.assert_called_once_with(113, 0)
        self.extension.GetUserPreferenceToggle.assert_called_once_with(375, 0)
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.assert_no_setters()

    def test_native_preference_reads_are_inside_trace(self):
        calls = []
        with mock.patch.object(adapter, "native_call", side_effect=lambda stage, method, call: (calls.append((stage, method)), call())[1]):
            result = self.operation("document.annotation-options")
        self.assertTrue(result["ok"])
        self.assertEqual(len(calls), 7)
        self.assertTrue(all(stage == "document-annotations" for stage, _ in calls))

    def test_read_preserves_unknown_native_enum_without_enabling_its_setter(self):
        self.native[38] = 290
        result = self.operation("document.annotation-options")
        self.assertTrue(result["ok"], result)
        validate_operation_result("document.annotation-options", result)
        self.assertEqual(result["options"]["arrow.edge_vertex"], {"value": "other", "native_value": 290})
        self.assert_no_setters()

    def test_each_typed_field_uses_its_own_document_preference_and_preserves_other_fields(self):
        targets = [
            ("arrow.edge_vertex", "dot", "closed", "Integer", 38, 0, 3),
            ("arrow.face_surface", "closed", "dot", "Integer", 39, 0, 1),
            ("arrow.unattached", "none", "closed", "Integer", 40, 0, 10),
            ("bent_leader.enabled", True, False, "Toggle", 375, 0, True),
            ("bent_leader.length_mm", 10, 6.35, "Double", 113, 0, 0.010),
            ("zero.leading", "show", "standard", "Integer", 265, 100, 2),
            ("zero.trailing", "same_as_source", "remove_only_on_zero", "Integer", 15, 100, 5),
        ]
        for field, value, expected, kind, preference, option, native in targets:
            with self.subTest(field=field):
                self.setUp()
                before = dict(self.native)
                result = self.edit(field, value, expected)
                self.assertTrue(result["ok"], result)
                validate_operation_result("document.annotation-option-set", result)
                self.assertEqual(self.native, {**before, preference: native})
                self.assertTrue(result["changed"] and result["document"]["modified"])
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                getattr(self.extension, "SetUserPreference" + kind).assert_called_once_with(preference, option, native)
                self.document.SetSaveFlag.assert_called_once_with()
                self.assertIs(self.app.ActiveDoc, self.foreground)
                self.app.SetUserPreferenceIntegerValue.assert_not_called()

    def test_false_toggle_is_success_when_native_returns_true_and_reads_back_false(self):
        self.native[375] = True
        result = self.edit("bent_leader.enabled", False, True)
        self.assertTrue(result["ok"], result)
        self.extension.SetUserPreferenceToggle.assert_called_once_with(375, 0, False)
        self.assertFalse(result["options"]["bent_leader.enabled"]["value"])

    def test_equal_value_calls_no_setter_and_does_not_mark_dirty(self):
        for field, expected in (("arrow.edge_vertex", "closed"), ("bent_leader.enabled", False),
                                ("bent_leader.length_mm", 6.35), ("zero.trailing", "remove_only_on_zero")):
            with self.subTest(field=field):
                result = self.edit(field, expected, expected)
                self.assertTrue(result["ok"], result)
                validate_operation_result("document.annotation-option-set", result)
                self.assertFalse(result["changed"] or result["mutation"]["attempted"])
        self.assert_no_setters()

    def test_old_value_cas_detects_change_even_when_stamp_does_not_change(self):
        first = self.edit("zero.leading", "show", "standard")
        self.assertTrue(first["ok"], first)
        self.extension.SetUserPreferenceInteger.reset_mock()
        self.document.SetSaveFlag.reset_mock()
        result = self.edit("zero.leading", "remove", "standard")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "DocumentAnnotationConflict")
        self.assertFalse(result["mutation"]["attempted"])
        self.assert_no_setters()

    def test_lease_and_stamp_fail_before_any_getter_or_setter(self):
        with self.assertRaises(DocumentLeaseConflict):
            self.edit("zero.leading", "show", "standard", session="reader")
        with self.assertRaises(DocumentUpdateConflict):
            self.edit("zero.leading", "show", "standard", stamp=6)
        with self.assertRaises(DocumentUpdateConflict):
            self.operation("document.annotation-options", stamp=6)
        self.extension.GetUserPreferenceInteger.assert_not_called()
        self.assert_no_setters()

    def test_read_only_view_only_and_active_sketch_refuse_before_mutation(self):
        for flag in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with self.subTest(flag=flag), mock.patch.object(self.document, flag, return_value=True):
                result = self.edit("zero.leading", "show", "standard")
                self.assertFalse(result["ok"])
                self.assertFalse(result["mutation"]["attempted"])
        self.document.SketchManager.ActiveSketch = object()
        result = self.edit("zero.leading", "show", "standard")
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation"]["attempted"])
        self.assert_no_setters()

    def test_read_requires_exact_native_types(self):
        for preference, value in ((38, True), (375, 0), (113, float("nan")), (113, float("inf")), (113, 0), (15, "4")):
            with self.subTest(preference=preference, value=value):
                self.setUp()
                self.native[preference] = value
                result = self.operation("document.annotation-options")
                self.assertFalse(result["ok"], result)
                self.assertNotIn("options", result)
                self.assert_no_setters()

    def test_read_rejects_foreground_configuration_dirty_and_edit_drift(self):
        changes = [lambda: setattr(self.app, "ActiveDoc", self.document),
                   lambda: setattr(self.configuration, "Name", "Other"),
                   lambda: setattr(self, "modified", True),
                   lambda: setattr(self.document.SketchManager, "ActiveSketch", object())]
        for change in changes:
            with self.subTest(change=change):
                self.setUp()
                def read(preference, option):
                    change()
                    return self.native[preference]
                self.extension.GetUserPreferenceInteger.side_effect = read
                self.assertFalse(self.operation("document.annotation-options")["ok"])
                self.assert_no_setters()

    def test_false_exception_or_wrong_readback_is_single_call_and_partial_mutation(self):
        for effect in (lambda *args: False, lambda *args: True, RuntimeError("native failed")):
            with self.subTest(effect=effect):
                self.setUp()
                self.extension.SetUserPreferenceInteger.side_effect = effect
                result = self.edit("zero.leading", "show", "standard")
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceInteger.assert_called_once_with(265, 100, 2)
                self.document.SetSaveFlag.assert_not_called()

    def test_toggle_false_return_is_not_confused_with_requested_false_or_retried(self):
        self.native[375] = True
        def returned_false(preference, option, value):
            self.native[preference] = value
            return False
        self.extension.SetUserPreferenceToggle.side_effect = returned_false
        result = self.edit("bent_leader.enabled", False, True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["mutation"]["attempted"] and result["mutation"]["may_have_changed"])
        self.extension.SetUserPreferenceToggle.assert_called_once_with(375, 0, False)
        self.document.SetSaveFlag.assert_not_called()

    def test_changed_context_after_setter_fails_and_preserves_partial_mutation(self):
        for change in (lambda: setattr(self.app, "ActiveDoc", self.document),
                       lambda: setattr(self.configuration, "Name", "Other"),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", object())):
            with self.subTest(change=change):
                self.setUp()
                def apply(preference, option, value):
                    self.native[preference] = value
                    change()
                    return True
                self.extension.SetUserPreferenceInteger.side_effect = apply
                result = self.edit("zero.leading", "show", "standard")
                self.assertFalse(result["ok"])
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.extension.SetUserPreferenceInteger.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()

    def test_unrequested_field_drift_fails_without_rollback(self):
        def apply(preference, option, value):
            self.native[preference] = value
            self.native[39] = 1
            return True
        self.extension.SetUserPreferenceInteger.side_effect = apply
        result = self.edit("zero.leading", "show", "standard")
        self.assertFalse(result["ok"])
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.extension.SetUserPreferenceInteger.assert_called_once()
        self.document.SetSaveFlag.assert_not_called()

    def test_saveflag_failure_or_its_option_drift_stays_partial_mutation(self):
        for effect in (RuntimeError("mark dirty failed"), lambda: self.native.update({39: 1})):
            with self.subTest(effect=effect):
                self.setUp()
                self.document.SetSaveFlag.side_effect = effect
                result = self.edit("zero.leading", "show", "standard")
                self.assertFalse(result["ok"])
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.extension.SetUserPreferenceInteger.assert_called_once()
                self.document.SetSaveFlag.assert_called_once()

    def test_first_readback_cannot_clear_dirty_or_advance_stamp(self):
        for drift in ("dirty", "stamp"):
            with self.subTest(drift=drift):
                self.setUp()
                self.modified = True
                reads = 0
                def read(preference, option):
                    nonlocal reads
                    if preference == 38:
                        reads += 1
                        if reads == 2:
                            if drift == "dirty":
                                self.modified = False
                            else:
                                self.document.GetUpdateStamp = lambda: 99
                    return self.native[preference]
                self.extension.GetUserPreferenceInteger.side_effect = read
                result = self.edit("zero.leading", "show", "standard")
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceInteger.assert_called_once_with(265, 100, 2)
                self.document.SetSaveFlag.assert_not_called()

    def test_final_readback_cannot_create_sketch_clear_dirty_or_advance_stamp(self):
        for drift in ("sketch", "dirty", "stamp"):
            with self.subTest(drift=drift):
                self.setUp()
                reads = 0
                def read(preference, option):
                    nonlocal reads
                    if preference == 38:
                        reads += 1
                        if reads == 3:
                            if drift == "sketch":
                                self.document.SketchManager.ActiveSketch = object()
                            elif drift == "dirty":
                                self.modified = False
                            else:
                                self.document.GetUpdateStamp = lambda: 99
                    return self.native[preference]
                self.extension.GetUserPreferenceInteger.side_effect = read
                result = self.edit("zero.leading", "show", "standard")
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceInteger.assert_called_once_with(265, 100, 2)
                self.document.SetSaveFlag.assert_called_once_with()

    def test_setter_itself_may_advance_stamp_when_both_readbacks_preserve_it(self):
        def apply(preference, option, value):
            self.native[preference] = value
            self.document.GetUpdateStamp = lambda: 99
            return True
        self.extension.SetUserPreferenceInteger.side_effect = apply
        result = self.edit("zero.leading", "show", "standard")
        self.assertTrue(result["ok"], result)
        validate_operation_result("document.annotation-option-set", result)
        self.assertEqual(result["document"]["update_stamp"], 99)
        self.extension.SetUserPreferenceInteger.assert_called_once_with(265, 100, 2)
        self.document.SetSaveFlag.assert_called_once_with()

    def test_all_seven_fields_require_their_exact_type_and_calibrated_write_domain(self):
        invalid = [
            {"field": "font", "value": "Arial", "expected_value": "Arial"},
            {"field": "arrow.edge_vertex", "value": "none", "expected_value": "closed"},
            {"field": "arrow.unattached", "value": "dot", "expected_value": "closed"},
            {"field": "zero.leading", "value": 2, "expected_value": "standard"},
            {"field": "zero.trailing", "value": "obsolete", "expected_value": "show"},
            {"field": "bent_leader.enabled", "value": 1, "expected_value": False},
            {"field": "bent_leader.enabled", "value": True, "expected_value": "false"},
            *[{"field": "bent_leader.length_mm", "value": v, "expected_value": 6.35}
              for v in (True, 0, -1, float("nan"), float("inf"), 10**1000, 5e-324, "10")],
            {"field": "zero.leading", "value": "show"},
            {"field": "zero.leading", "value": "show", "expected_value": "standard", "configuration": "Default"},
        ]
        for parameters in invalid:
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                validate_operation_request("document.annotation-option-set", parameters)
        self.assertTrue(OPERATION_CATALOG["document.annotation-option-set"].lease_guarded)
        self.assertFalse(OPERATION_CATALOG["document.annotation-option-set"].temporary_activation)
        with self.assertRaises(ValueError):
            validate_operation_request("document.annotation-options", {}, lease_id=self.lease["lease_id"])
        self.assert_no_setters()

    def test_schema_requires_seven_complete_correctly_mapped_fields(self):
        original = self.operation("document.annotation-options")
        for change in (lambda opts: opts.pop("zero.leading"),
                       lambda opts: opts["arrow.edge_vertex"].update(native_value=3),
                       lambda opts: opts["bent_leader.enabled"].update(value=0),
                       lambda opts: opts.update(font="Arial")):
            result = deepcopy(original)
            change(result["options"])
            with self.subTest(result=result), self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.annotation-options", result)

    def test_schema_rejects_inconsistent_native_units_toggle_and_mutation_lifecycle(self):
        original = self.operation("document.annotation-options")
        for field, raw in (("bent_leader.length_mm", 0.010), ("bent_leader.enabled", True)):
            result = deepcopy(original)
            result["options"][field]["native_value"] = raw
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.annotation-options", result)
        edited = self.edit("zero.leading", "show", "standard")
        for change in (lambda r: r.update(changed=False),
                       lambda r: r["mutation"].update(attempted=False),
                       lambda r: r["document"].update(modified=False),
                       lambda r: r["options"]["arrow.face_surface"].update(value="closed", native_value=1)):
            result = deepcopy(edited)
            change(result)
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.annotation-option-set", result)

    def test_invalid_cli_scalar_is_usage_error_before_daemon_connection(self):
        for field, value in (("bent_leader.enabled", "0"), ("bent_leader.length_mm", "abc")):
            with self.subTest(field=field), mock.patch("swcli.cli.call_daemon") as call:
                error = StringIO()
                with redirect_stderr(error), self.assertRaises(SystemExit) as exited:
                    main(["document", "annotation-option-set", field, value, "--if-value", "true"])
                self.assertEqual(exited.exception.code, 2)
                self.assertNotIn("Traceback", error.getvalue())
                call.assert_not_called()

    def test_cli_converts_only_the_field_specific_scalar_and_passes_guards(self):
        for field, value, expected, typed, previous in (
            ("zero.leading", "show", "standard", "show", "standard"),
            ("bent_leader.enabled", "false", "true", False, True),
            ("bent_leader.length_mm", "10", "6.35", 10.0, 6.35),
        ):
            args = build_parser().parse_args([
                "document", "annotation-option-set", field, value, "--if-value", expected,
                "--document", self.entry.document_id, "--lease", self.lease["lease_id"], "--if-update-stamp", "7", "--json",
            ])
            self.assertEqual(_typed_operation(args), (
                "document.annotation-option-set", dict(field=field, value=typed, expected_value=previous),
                True, self.entry.document_id, 7, self.lease["lease_id"],
            ))
        args = build_parser().parse_args(["document", "annotation-option-set", "bent_leader.enabled", "0", "--if-value", "false"])
        with self.assertRaises(ValueError):
            _typed_operation(args)
        args = build_parser().parse_args(["document", "annotation-options", "--json"])
        self.assertEqual(_typed_operation(args), ("document.annotation-options", {}, True, None, None, None))


if __name__ == "__main__":
    unittest.main()
