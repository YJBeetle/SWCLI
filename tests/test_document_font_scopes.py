"""Portable guard evidence only; mocks cannot prove native font behavior."""
from copy import deepcopy
from contextlib import nullcontext, redirect_stderr
import json
import os
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.daemon import operations
from swcli.document_font_scopes import FONT_SCOPES, font_scopes_schema, validate_font_scopes
from swcli.font_snapshot import FONT_MEMBERS, font_snapshot
from swcli.hosts import windows_document_font_scopes as adapter
from swcli.hosts.native_trace import trace_native_request
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid


class Format:
    def __init__(self, native, changed=None):
        self.__dict__.update(native=deepcopy(native), changed=changed, writes=[])

    def __getattr__(self, name):
        if name == "IsHeightSpecifiedInPts":
            return lambda: self.native[name]
        return self.native[name]

    def __setattr__(self, name, value):
        self.writes.append((name, value))
        self.native[name] = value
        if name == "CharHeight":
            self.native.update(IsHeightSpecifiedInPts=False, CharHeightInPts=round(value * 72 / 0.0254))
        elif name == "CharHeightInPts":
            self.native.update(IsHeightSpecifiedInPts=True, CharHeight=value * 0.0254 / 72)
        if self.changed:
            self.changed(self)


class FontScopeTests(unittest.TestCase):
    def setUp(self):
        # Synthetic IDs deliberately differ from SOLIDWORKS; they prove the
        # adapter uses resolved symbols including the nonzero dimension option.
        self.constants = {name: i + 100 for i, name in enumerate(sorted({n for pair in FONT_SCOPES.values() for n in pair}))}
        self.pairs = {tuple(self.constants[name] for name in pair): scope for scope, pair in FONT_SCOPES.items()}
        base = dict(TypeFaceName="Arial", CharHeight=0.003, CharHeightInPts=8, IsHeightSpecifiedInPts=False,
                    Bold=False, Italic=False, Underline=False, Strikeout=False, BackWards=False,
                    UpsideDown=False, Vertical=False, WidthFactor=1.0, CharSpacingFactor=1.0,
                    Escapement=0.0, LineSpacing=1.0, LineLength=0.0, ObliqueAngle=0.0)
        self.native = {scope: deepcopy(base) for scope in FONT_SCOPES}
        self.objects, self.live = [], False
        self.modified, self.stamp = False, 7
        self.configuration = SimpleNamespace(Name="Default")
        self.extension = SimpleNamespace(GetUserPreferenceTextFormat=Mock(side_effect=self.get_font),
                                         SetUserPreferenceTextFormat=Mock(side_effect=self.commit))
        self.document = SimpleNamespace(GetType=lambda: 1, GetSaveFlag=lambda: self.modified,
            GetUpdateStamp=lambda: self.stamp, GetActiveConfiguration=lambda: self.configuration,
            GetTitle=lambda: "Background", GetPathName=lambda: "", IsOpenedReadOnly=lambda: False,
            IsOpenedViewOnly=lambda: False, SketchManager=SimpleNamespace(ActiveSketch=None),
            Extension=self.extension, SetSaveFlag=Mock(side_effect=lambda: setattr(self, "modified", True)))
        self.front = SimpleNamespace(GetType=lambda: 1, GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 1,
                                     GetTitle=lambda: "Foreground", GetPathName=lambda: "",
                                     GetActiveConfiguration=lambda: SimpleNamespace(Name="ForegroundDefault"),
                                     SketchManager=SimpleNamespace(ActiveSketch=None),
                                     IsOpenedReadOnly=lambda: False, IsOpenedViewOnly=lambda: False)
        self.app = SimpleNamespace(ActiveDoc=self.front, GetDocuments=lambda: (self.document, self.front),
                                   IsSame=lambda a, b: int(a is b), ActivateDoc3=Mock())
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.registry.set_current(self.registry.register(self.front), session_id="writer")
        self.lease = self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)
        self.constant_patch = patch.object(adapter, "_installed_constants", lambda: self.constants)
        self.constant_patch.start()
        self.addCleanup(self.constant_patch.stop)

    def get_font(self, preference, option):
        scope = self.pairs[preference, option]
        def changed(font):
            if self.live:
                self.native[scope].update(font.native)
                self.modified = True
                self.stamp += 1
        font = Format(self.native[scope], changed)
        self.objects.append(font)
        return font

    def commit(self, preference, option, font):
        self.native[self.pairs[preference, option]].update(font.native)
        return True

    def fonts(self):
        return {scope: font_snapshot(native) for scope, native in self.native.items()}

    def operation(self, name, parameters=None, *, internal=False, stamp=None, session="writer", token=True):
        with patch.object(operations, "set_document_font_scope_windows", adapter._calibrate_set_document_font_scope) if internal else nullcontext():
            return operations.execute_operation(self.app, name, parameters or {}, documents=self.registry,
                document_id=self.entry.document_id, session_id=session,
                expected_update_stamp=self.stamp if stamp is None and name.endswith("-set") else stamp,
                lease_id=self.lease["lease_id"] if name.endswith("-set") and token else None)

    def edit(self, *, scope="notes", field="bold", value=True, expected=None, **kwargs):
        return self.operation("document.font-scope-set", dict(scope=scope, field=field, value=value,
            expected_fonts=self.fonts() if expected is None else expected), **kwargs)

    def assert_no_mutation(self):
        self.assertFalse(any(font.writes for font in self.objects))
        self.extension.SetUserPreferenceTextFormat.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()

    def test_all_scopes_complete_snapshots_and_symbolic_option_routing(self):
        result = self.operation("document.font-scopes")
        validate_operation_result("document.font-scopes", result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["fonts"], self.fonts())
        self.assertEqual([call.args for call in self.extension.GetUserPreferenceTextFormat.call_args_list], list(self.pairs))
        self.assertTrue(all(len(font) == 17 for font in result["fonts"].values()))
        self.assertFalse(result["document"]["active"])
        self.assert_no_mutation()

    def test_public_setter_cannot_be_enabled_by_protocol(self):
        result = self.edit()
        validate_operation_result("document.font-scope-set", result)
        self.assertEqual(result["error"]["type"], "DocumentFontScopeNotCalibrated")
        self.assertEqual(result["mutation"], dict(attempted=False, may_have_changed=False))
        self.extension.GetUserPreferenceTextFormat.assert_not_called()
        self.assert_no_mutation()
        with self.assertRaises(ValueError):
            validate_operation_request("document.font-scope-set", dict(scope="notes", field="bold", value=True,
                expected_fonts=self.fonts(), calibration=True))

    def test_catalog_requires_explicit_document_stamp_lease_without_activation(self):
        spec = OPERATION_CATALOG["document.font-scope-set"]
        self.assertTrue(spec.lease_guarded)
        self.assertFalse(spec.temporary_activation)
        self.assertEqual(set(spec.parameters["required"]), {"scope", "field", "value", "expected_fonts"})
        self.assertEqual(spec.parameters["x-swcli-context"], dict(document_id="required", expected_update_stamp="required", lease_id="required"))

    def test_native_runtime_probe_closes_wine_and_unknown_loader_failures(self):
        with patch.object(adapter.sys, "platform", "win32"):
            with patch.object(adapter.ctypes, "WinDLL", create=True, return_value=SimpleNamespace()):
                self.assertTrue(adapter._native_windows_runtime())
            with patch.object(adapter.ctypes, "WinDLL", create=True, return_value=SimpleNamespace(wine_get_version=object())):
                self.assertFalse(adapter._native_windows_runtime())
            with patch.object(adapter.ctypes, "WinDLL", create=True, side_effect=OSError("unknown runtime")):
                self.assertFalse(adapter._native_windows_runtime())

    def test_post_write_descriptor_failure_preserves_mutation_and_first_error(self):
        original = self.registry.describe
        count = [0]
        def describe(*args, **kwargs):
            count[0] += 1
            if count[0] == 2:
                raise RuntimeError("final descriptor failed")
            return original(*args, **kwargs)
        self.app.RevisionNumber = lambda: "33.5.0"
        with patch.object(adapter, "_native_windows_runtime", return_value=True), \
                patch.object(self.registry, "describe", side_effect=describe):
            result = self.edit()
        self.assertFalse(result["ok"])
        self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
        self.assertEqual(result["error"]["message"], "final descriptor failed")
        self.assertTrue(self.native["notes"]["Bold"])
        self.assertTrue(self.modified)
        self.extension.SetUserPreferenceTextFormat.assert_called_once()
        validate_operation_result("document.font-scope-set", result)
        # A later metadata problem must preserve an earlier native rejection.
        self.setUp()
        self.extension.SetUserPreferenceTextFormat.side_effect = RuntimeError("first native failure")
        original = self.registry.describe
        count[0] = 0
        def fail_again(*args, **kwargs):
            count[0] += 1
            if count[0] == 2:
                raise RuntimeError("secondary metadata failure")
            return original(*args, **kwargs)
        with patch.object(self.registry, "describe", side_effect=fail_again):
            result = self.edit(internal=True)
        self.assertEqual(result["error"]["message"], "first native failure")
        self.assertEqual(result["warnings"][0]["message"], "secondary metadata failure")
        self.assertTrue(result["mutation"]["may_have_changed"])

    def test_other_foreground_state_and_identity_changes_reject_success_without_rollback(self):
        changes = (("GetSaveFlag", lambda: True), ("GetTitle", lambda: "Changed foreground"),
                   ("GetUpdateStamp", lambda: 99), ("GetPathName", lambda: "changed.SLDPRT"),
                   ("GetActiveConfiguration", lambda: SimpleNamespace(Name="Other")),
                   ("IsOpenedReadOnly", lambda: True))
        for name, changed in changes:
            with self.subTest(name=name):
                self.setUp()
                original = self.commit
                def commit(*args):
                    returned = original(*args)
                    setattr(self.front, name, changed)
                    return returned
                self.extension.SetUserPreferenceTextFormat.side_effect = commit
                result = self.edit(internal=True)
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.assertTrue(self.native["notes"]["Bold"])
                self.assertEqual(getattr(self.front, name)(), changed())
                self.app.ActivateDoc3.assert_not_called()
                self.extension.SetUserPreferenceTextFormat.assert_called_once()

    def test_foreground_change_during_read_or_noop_is_not_silent_success(self):
        original = self.get_font
        def getter(*args):
            font = original(*args)
            self.front.GetSaveFlag = lambda: True
            return font
        self.extension.GetUserPreferenceTextFormat.side_effect = getter
        result = self.operation("document.font-scopes")
        self.assertFalse(result["ok"])
        self.assert_no_mutation()
        self.front.GetSaveFlag = lambda: False
        result = self.edit(value=False, internal=True)
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation"]["attempted"])
        self.assert_no_mutation()

    def test_active_target_is_allowed_to_change_its_own_dirty_flag(self):
        self.app.ActiveDoc = self.document
        result = self.edit(internal=True)
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.modified)

    def test_public_notes_profile_uses_the_guarded_native_implementation(self):
        self.app.RevisionNumber = lambda: "33.5.0"
        with patch.object(adapter, "_native_windows_runtime", return_value=True):
            result = self.edit()
        self.assertTrue(result["ok"], result)
        validate_operation_result("document.font-scope-set", result)
        self.extension.SetUserPreferenceTextFormat.assert_called_once()
        profiles = OPERATION_CATALOG["document.font-scope-set"].parameters["x-swcli-font-write-profiles"]
        self.assertEqual(set(profiles), {"notes"})
        self.assertEqual(profiles["notes"]["solidworks_revision"], "33.5.0")
        self.assertEqual(profiles["notes"]["document_types"], [1, 2, 3])

    def test_unproved_scopes_revisions_and_runtimes_remain_closed(self):
        for scope, revision, native in (("dimensions", "33.5.0", True), ("tables", "33.5.0", True),
                                        ("notes", "33.4.0", True), ("notes", "34.0.0", True),
                                        ("notes", "33.5.0", False)):
            self.app.RevisionNumber = lambda: revision
            with patch.object(adapter, "_native_windows_runtime", return_value=native):
                result = self.edit(scope=scope)
            self.assertEqual(result["error"]["type"], "DocumentFontScopeNotCalibrated")
            self.assertEqual(result["mutation"], dict(attempted=False, may_have_changed=False))
        self.extension.GetUserPreferenceTextFormat.assert_not_called()
        self.assert_no_mutation()

    def test_capability_profile_schema_rejects_wider_scope_revision_or_unknown_fields(self):
        from jsonschema import Draft202012Validator, ValidationError
        from swcli.protocol import load_schema
        schema = load_schema('capabilities')['properties']['operation_schemas']['additionalProperties']
        validator = Draft202012Validator(schema)
        original = deepcopy(OPERATION_CATALOG['document.font-scope-set'].parameters)
        validator.validate(original)
        for mutate in (lambda profile: profile.update(tables=deepcopy(profile['notes'])),
                       lambda profile: profile['notes'].update(solidworks_revision='34.0.0'),
                       lambda profile: profile['notes'].update(arbitrary_com='SetAnything'),
                       lambda profile: profile['notes'].update(fields=['DeleteAllObjects'])):
            candidate = deepcopy(original)
            mutate(candidate['x-swcli-font-write-profiles'])
            with self.assertRaises(ValidationError):
                validator.validate(candidate)

    def test_internal_setters_target_each_scope_and_keep_other_native_snapshots(self):
        for scope in ("dimensions", "notes", "tables"):
            with self.subTest(scope=scope):
                before = deepcopy(self.native)
                result = self.edit(scope=scope, internal=True)
                validate_operation_result("document.font-scope-set", result)
                self.assertTrue(result["ok"], result)
                self.assertTrue(result["changed"])
                self.assertTrue(result["document"]["modified"])
                self.assertEqual(result["fonts"][scope]["bold"], True)
                self.assertEqual(self.extension.SetUserPreferenceTextFormat.call_args.args[:2],
                                 tuple(self.constants[name] for name in FONT_SCOPES[scope]))
                for other in FONT_SCOPES:
                    if other != scope:
                        self.assertEqual(self.native[other], before[other])
        self.app.ActivateDoc3.assert_not_called()

    def test_mm_and_integer_points_select_exactly_one_native_member_and_mode(self):
        for field, value, mode, member in (("height_points", 14, "points", "CharHeightInPts"),
                                           ("height_mm", 3.5, "millimeters", "CharHeight")):
            result = self.edit(field=field, value=value, internal=True)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["fonts"]["notes"]["height_mode"], mode)
            self.assertEqual(self.extension.SetUserPreferenceTextFormat.call_args.args[2].writes,
                             [(member, value / 1000 if field == "height_mm" else value)])

    def test_live_assignment_records_mutation_before_error_and_never_retries(self):
        def fail(font):
            self.native["notes"].update(font.native)
            raise RuntimeError("native property assignment failed after mutation")
        original = self.get_font
        def get(*args):
            font = original(*args)
            if self.pairs[args] == "notes":
                font.__dict__["changed"] = fail
            return font
        self.extension.GetUserPreferenceTextFormat.side_effect = get
        result = self.edit(internal=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
        self.assertEqual(sum(len(font.writes) for font in self.objects), 1)
        self.extension.SetUserPreferenceTextFormat.assert_not_called()

    def test_full_cas_rejects_stale_readonly_or_other_scope_fields_before_assignment(self):
        for scope, field in (("notes", "width_factor"), ("annotations", "bold"), ("tables", "height_mode")):
            expected = self.fonts()
            expected[scope][field] = 2.0 if field == "width_factor" else True if field == "bold" else "points"
            result = self.edit(expected=expected, internal=True)
            self.assertEqual(result["error"]["type"], "DocumentFontScopeConflict")
            self.assert_no_mutation()

    def test_native_false_exception_or_wrong_value_is_partial_and_not_retried(self):
        for outcome in (False, RuntimeError("native error"), True):
            with self.subTest(outcome=outcome):
                self.extension.SetUserPreferenceTextFormat.reset_mock()
                self.extension.SetUserPreferenceTextFormat.side_effect = outcome if isinstance(outcome, Exception) else None
                self.extension.SetUserPreferenceTextFormat.return_value = outcome
                result = self.edit(internal=True)
                self.assertFalse(result["ok"])
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.extension.SetUserPreferenceTextFormat.assert_called_once()

    def test_non_target_scope_drift_fails_with_observation(self):
        def commit(*args):
            result = self.commit(*args)
            self.native["annotations"]["Bold"] = True
            return result
        self.extension.SetUserPreferenceTextFormat.side_effect = commit
        result = self.edit(internal=True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["observed_fonts"]["annotations"]["bold"])
        self.assertTrue(result["mutation"]["attempted"])
        self.extension.SetUserPreferenceTextFormat.assert_called_once()

    def test_noop_keeps_state_but_changed_unit_mode_is_not_noop(self):
        before = self.operation("document.font-scopes")
        result = self.edit(value=False, internal=True)
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"])
        self.assertEqual(result["document"], before["document"])
        self.assert_no_mutation()
        self.native["notes"]["IsHeightSpecifiedInPts"] = True
        result = self.edit(field="height_mm", value=3.0, internal=True)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["changed"])
        self.assertEqual(result["fonts"]["notes"]["height_mode"], "millimeters")

    def test_writable_flags_and_model_sketch_are_checked(self):
        for flag in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with patch.object(self.document, flag, lambda: True):
                result = self.edit(internal=True)
                self.assertEqual(result["error"]["type"], "ValueError")
        self.document.SketchManager.ActiveSketch = object()
        result = self.edit(internal=True)
        self.assertEqual(result["error"]["type"], "ValueError")
        self.assert_no_mutation()

    def test_bad_field_scope_value_or_incomplete_cas_rejected_before_native(self):
        for args in (dict(scope="arbitrary_com"), dict(scope="annotations"), dict(field="width_factor"),
                     dict(value=1), dict(field="height_points", value=3.5), dict(field="typeface", value=" A "),
                     dict(field="height_mm", value=float("nan")), dict(expected={} )):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.edit(**args, internal=True)
        self.assert_no_mutation()

    def test_stamp_and_session_lease_refuse_before_adapter(self):
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.edit(internal=True, stamp=8)
        with self.assertRaises(DocumentLeaseConflict):
            self.edit(internal=True, session="contender")
        with self.assertRaises(ValueError):
            self.edit(internal=True, token=False)
        self.extension.GetUserPreferenceTextFormat.assert_not_called()
        self.assert_no_mutation()

    def test_read_detects_dirty_foreground_or_document_identity_drift(self):
        for effect in (lambda: setattr(self, "modified", True),
                       lambda: setattr(self.app, "ActiveDoc", self.document),
                       lambda: setattr(self.document, "GetPathName", lambda: "changed.SLDPRT")):
            original = self.get_font
            def get(*args):
                value = original(*args)
                effect()
                return value
            self.extension.GetUserPreferenceTextFormat.side_effect = get
            result = self.operation("document.font-scopes")
            self.assertFalse(result["ok"])
            self.modified = False
            self.app.ActiveDoc = self.front
            self.document.GetPathName = lambda: ""
        self.assert_no_mutation()

    def test_invalid_native_member_fails_closed(self):
        self.native["tables"]["WidthFactor"] = float("inf")
        result = self.operation("document.font-scopes")
        self.assertFalse(result["ok"])
        self.assert_no_mutation()

    def test_result_schema_rejects_incomplete_and_nonfinite_snapshots(self):
        result = self.operation("document.font-scopes")
        del result["fonts"]["annotations"]["vertical"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.font-scopes", result)
        result = self.operation("document.font-scopes")
        result["fonts"]["notes"]["width_factor"] = float("inf")
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.font-scopes", result)

    def test_drawing_sheet_context_allows_only_the_normal_sheet(self):
        sheet_sketch, template_sketch = object(), object()
        self.document.GetType = lambda: 3
        self.document.GetCurrentSheet = lambda: SimpleNamespace(GetName=lambda: "Sheet1", GetTemplateSketch=lambda: template_sketch)
        view = SimpleNamespace(GetName2=lambda: "Sheet1", GetSketch=lambda: sheet_sketch, GetReferencedModelName=lambda: "")
        sheet = self.document.GetCurrentSheet()
        self.document.GetCurrentSheet = lambda: sheet
        self.document.GetFirstView = lambda: view
        self.document.GetEditSheet = lambda: True
        self.document.ActiveDrawingView = None
        self.document.SketchManager.ActiveSketch = sheet_sketch
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.registry.set_current(self.registry.register(self.front), session_id="writer")
        self.lease = self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)
        result = self.edit(internal=True)
        self.assertTrue(result["ok"], result)
        for mutate in (lambda: setattr(self.document, "GetEditSheet", lambda: False),
                       lambda: setattr(self.document, "ActiveDrawingView", object()),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", template_sketch)):
            self.extension.SetUserPreferenceTextFormat.reset_mock()
            self.document.GetEditSheet = lambda: True
            self.document.ActiveDrawingView = None
            self.document.SketchManager.ActiveSketch = sheet_sketch
            mutate()
            result = self.edit(value=False, internal=True)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], "ValueError")
            self.assertFalse(result["mutation"]["attempted"])
            self.extension.SetUserPreferenceTextFormat.assert_not_called()

    def test_result_semantics_reject_forged_success_receipts(self):
        original = self.edit(internal=True)
        for mutate in (lambda row: row.update(changed=False),
                       lambda row: row["mutation"].update(attempted=False),
                       lambda row: row["fonts"]["annotations"].update(italic=True),
                       lambda row: row["fonts"]["notes"].update(width_factor=2.0),
                       lambda row: row["document"].update(modified=False)):
            result = deepcopy(original)
            mutate(result)
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.font-scope-set", result)

    def test_native_trace_captures_exactly_one_property_and_document_setter(self):
        stream = StringIO()
        with patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), redirect_stderr(stream):
            with trace_native_request("font-scopes-portable-proof", "document.font-scope-set"):
                result = self.edit(internal=True)
        self.assertTrue(result["ok"], result)
        records = [json.loads(line) for line in stream.getvalue().splitlines()]
        calls = [row["call"] for row in records if row["phase"] == "begin" and row["stage"] == "document-font-scopes"]
        self.assertEqual(calls.count("ITextFormat.Bold.set"), 1)
        self.assertEqual(calls.count("IModelDocExtension.SetUserPreferenceTextFormat"), 1)
        self.assertEqual(calls.count("IModelDocExtension.GetUserPreferenceTextFormat"), 12)
        self.assertFalse(any("arguments" in row or "result" in row for row in records))

    def test_cli_maps_json_scalars_and_complete_cas(self):
        args = build_parser().parse_args(["document", "font-scope-set", "notes", "bold", "true", "--if-fonts",
            json.dumps(self.fonts()), "--document", self.entry.document_id, "--if-update-stamp", "7", "--lease", self.lease["lease_id"], "--json"])
        name, params, as_json, document, stamp, lease = _typed_operation(args)
        self.assertEqual(name, "document.font-scope-set")
        self.assertIs(params["value"], True)
        self.assertEqual(params["expected_fonts"], self.fonts())
        self.assertEqual(stamp, 7)


if __name__ == "__main__":
    unittest.main()
