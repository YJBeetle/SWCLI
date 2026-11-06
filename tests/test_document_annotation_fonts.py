"""Portable guard tests; these mocks do not establish native font behavior."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.operation_schemas import OPERATION_CATALOG

from swcli.document_annotation_fonts import (
    ANNOTATION_FONT_MEMBERS, annotation_font_native_normalizations, annotation_font_snapshot,
)
from swcli.hosts import windows_document_annotation_fonts as adapter


class TextFormat:
    def __init__(self, native, on_write=None):
        object.__setattr__(self, "native", dict(native))
        object.__setattr__(self, "writes", [])
        object.__setattr__(self, "on_write", on_write)

    def __getattr__(self, member):
        if member == "IsHeightSpecifiedInPts":
            return lambda: self.native[member]
        return self.native[member]

    def __setattr__(self, member, value):
        self.writes.append((member, value))
        self.native[member] = value
        if member == "CharHeight":
            self.native.update(IsHeightSpecifiedInPts=False, CharHeightInPts=int(value * 72 / 0.0254))
        elif member == "CharHeightInPts":
            self.native.update(IsHeightSpecifiedInPts=True, CharHeight=value * 0.0254 / 72)
        if self.on_write:
            self.on_write(member, value)


class DocumentAnnotationFontTests(unittest.TestCase):
    def setUp(self):
        self.native = dict(
            TypeFaceName="汉仪长仿宋体", CharHeight=0.0035, CharHeightInPts=12,
            IsHeightSpecifiedInPts=False, Bold=False, Italic=False, Underline=False,
            Strikeout=False, BackWards=False, UpsideDown=False, Vertical=False,
            WidthFactor=1.0, CharSpacingFactor=1.0, Escapement=0.0,
            LineSpacing=0.0015, LineLength=0.0, ObliqueAngle=0.0,
        )
        self.modified, self.stamp = False, 7
        self.objects = []
        self.read_effect = None
        self.property_effect = None
        self.live = False
        self.extension = SimpleNamespace(
            GetUserPreferenceTextFormat=mock.Mock(side_effect=self.get_font),
            SetUserPreferenceTextFormat=mock.Mock(side_effect=self.commit),
        )
        self.configuration = SimpleNamespace(Name="Default")
        self.document = SimpleNamespace(
            GetType=lambda: 1, GetSaveFlag=lambda: self.modified, GetUpdateStamp=lambda: self.stamp,
            GetActiveConfiguration=lambda: self.configuration,
            IsOpenedReadOnly=lambda: False, IsOpenedViewOnly=lambda: False,
            SketchManager=SimpleNamespace(ActiveSketch=None), Extension=self.extension,
            SetSaveFlag=mock.Mock(side_effect=lambda: setattr(self, "modified", True)),
        )
        self.foreground = object()
        self.app = SimpleNamespace(ActiveDoc=self.foreground,
                                   IsSame=lambda first, second: int(first is second),
                                   ActivateDoc3=mock.Mock())
        self.expected = annotation_font_snapshot(self.native)

    def get_font(self, preference, option):
        self.assertEqual((preference, option), (19, 0))
        if self.read_effect:
            self.read_effect()
        def changed(member, value):
            if self.live:
                self.native.update(font.native)
            if self.property_effect:
                self.property_effect(member, value)
        font = TextFormat(self.native, changed)
        self.objects.append(font)
        return font

    def commit(self, preference, option, font):
        self.assertEqual((preference, option), (19, 0))
        self.native.update(font.native)
        return True

    def edit(self, field="bold", value=True, expected_font=None):
        return adapter.set_document_annotation_font_windows(
            app=self.app, document=self.document, field=field, value=value,
            expected_font=self.expected if expected_font is None else expected_font,
        )

    def assert_no_writes(self):
        self.assertTrue(all(not font.writes for font in self.objects))
        self.extension.SetUserPreferenceTextFormat.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()

    def drawing_context(self):
        self.sheet_sketch, self.template_sketch = object(), object()
        self.sheet = SimpleNamespace(GetName=lambda: "Sheet1", GetTemplateSketch=lambda: self.template_sketch)
        self.view = SimpleNamespace(GetName2=lambda: "Sheet1", GetSketch=lambda: self.sheet_sketch,
                                    GetReferencedModelName=lambda: "")
        self.document.GetType = lambda: 3
        self.document.GetCurrentSheet = lambda: self.sheet
        self.document.GetFirstView = lambda: self.view
        self.document.GetEditSheet = lambda: True
        self.document.ActiveDrawingView = None
        self.document.SketchManager.ActiveSketch = self.sheet_sketch

    def test_registered_font_operations_keep_selected_document_and_write_guards(self):
        read = OPERATION_CATALOG["document.annotation-font"]
        write = OPERATION_CATALOG["document.annotation-font-set"]
        self.assertTrue(read.selected_document and write.selected_document)
        self.assertFalse(read.lease_guarded or read.temporary_activation or write.temporary_activation)
        self.assertTrue(write.lease_guarded)
        self.assertEqual(read.parameters["x-swcli-context"]["lease_id"], "forbidden")
        self.assertEqual(write.parameters["x-swcli-context"]["expected_update_stamp"], "required")
        self.assertEqual(set(write.parameters["properties"]), {"field", "value", "expected_font"})
        self.assertEqual(set(write.parameters["required"]), {"field", "value", "expected_font"})

    def test_read_full_snapshot_keeps_background_document_clean(self):
        result = adapter.read_document_annotation_font_windows(app=self.app, document=self.document)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["font"], self.expected)
        self.assertEqual(result["native_font"], self.native)
        self.assertEqual(len(result["font"]), 17)
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.assert_no_writes()

    def test_each_field_sets_only_requested_native_property_once(self):
        for field, value in (("typeface", "Arial"), ("height_mm", 5.0), ("height_points", 16),
                             ("bold", True), ("italic", True), ("underline", True), ("strikeout", True)):
            with self.subTest(field=field):
                self.setUp()
                result = self.edit(field, value)
                self.assertTrue(result["ok"], result)
                self.assertTrue(result["changed"])
                native_value = value / 1000.0 if field == "height_mm" else value
                self.assertEqual(self.objects[0].writes, [(ANNOTATION_FONT_MEMBERS[field], native_value)])
                self.assertTrue(all(not font.writes for font in self.objects[1:]))
                self.extension.SetUserPreferenceTextFormat.assert_called_once_with(19, 0, self.objects[0])
                self.document.SetSaveFlag.assert_called_once_with()
                self.assertIs(self.app.ActiveDoc, self.foreground)

    def test_false_boolean_write_is_a_real_change(self):
        self.native["Bold"] = True
        self.expected = annotation_font_snapshot(self.native)
        result = self.edit("bold", False)
        self.assertTrue(result["ok"], result)
        self.assertIs(result["font"]["bold"], False)
        self.assertEqual(self.objects[0].writes, [("Bold", False)])

    def test_equal_value_is_zero_write_and_does_not_mark_dirty(self):
        for field, value in (("typeface", self.expected["typeface"]), ("height_mm", 3.5), ("bold", False)):
            with self.subTest(field=field):
                self.setUp()
                result = self.edit(field, value)
                self.assertTrue(result["ok"], result)
                self.assertFalse(result["changed"])
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assertEqual(result["native_normalizations"], [])
                self.assert_no_writes()

    def test_equal_alternate_height_switches_mode_explicitly(self):
        result = self.edit("height_points", 12)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["font"]["height_mode"], "points")
        self.assertTrue(result["changed"])
        self.assertEqual(self.objects[0].writes, [("CharHeightInPts", 12)])

    def test_full_snapshot_cas_rejects_unrequested_and_tiny_numeric_drift(self):
        for member, value in (("WidthFactor", 1.1), ("Italic", True), ("CharHeight", 0.003500000000000001)):
            with self.subTest(member=member):
                self.setUp()
                self.native[member] = value
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error"]["type"], "DocumentAnnotationFontConflict")
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assert_no_writes()

    def test_cas_conflict_is_checked_before_noop(self):
        self.native["Italic"] = True
        result = self.edit("bold", False)
        self.assertFalse(result["ok"], result)
        self.assert_no_writes()

    def test_malformed_expected_snapshots_refuse_before_native_reads(self):
        bad = []
        missing = dict(self.expected)
        missing.pop("line_length")
        bad.extend((missing, {**self.expected, "extra": 1}, {**self.expected, "height_mm": True},
                    {**self.expected, "height_points": 12.0}, {**self.expected, "bold": 0},
                    {**self.expected, "height_mode": False}, {**self.expected, "width_factor": float("nan")},
                    {**self.expected, "escapement": float("inf")}, {**self.expected, "line_length": 10 ** 1000}))
        for expected in bad:
            with self.subTest(expected=expected):
                result = self.edit(expected_font=expected)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.extension.GetUserPreferenceTextFormat.assert_not_called()
                self.assert_no_writes()

    def test_wrong_typed_or_nonfinite_native_members_fail_read(self):
        for member, value in (("Bold", 1), ("IsHeightSpecifiedInPts", 1), ("CharHeight", True),
                              ("CharHeight", float("inf")), ("WidthFactor", float("nan")),
                              ("CharHeightInPts", 12.0), ("TypeFaceName", None)):
            with self.subTest(member=member):
                self.setUp()
                self.native[member] = value
                result = adapter.read_document_annotation_font_windows(app=self.app, document=self.document)
                self.assertFalse(result["ok"], result)
                self.assert_no_writes()

    def test_invalid_values_fail_before_native_reads(self):
        for field, value in (("height_mm", 0), ("height_mm", 5e-324), ("height_mm", True),
                             ("height_mm", float("nan")), ("height_points", 12.5), ("height_points", True),
                             ("height_points", 2147483648), ("height_mode", "points"),
                             ("bold", 1), ("typeface", ""), ("typeface", " Arial"),
                             ("typeface", "Arial\x00"), ("width_factor", 2)):
            with self.subTest(field=field, value=value):
                result = self.edit(field, value)
                self.assertFalse(result["ok"], result)
                self.extension.GetUserPreferenceTextFormat.assert_not_called()
                self.assert_no_writes()

    def test_readonly_and_viewonly_fail_before_native_font_reads(self):
        for member in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with self.subTest(member=member):
                self.setUp()
                setattr(self.document, member, lambda: True)
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.extension.GetUserPreferenceTextFormat.assert_not_called()
                self.assert_no_writes()

    def test_active_model_sketch_refuses_change_but_allows_noop(self):
        self.document.SketchManager.ActiveSketch = object()
        self.assertFalse(self.edit()["ok"])
        self.assertTrue(self.edit("bold", False)["ok"])
        self.assert_no_writes()

    def test_normal_drawing_and_formatless_sheet_accept_change(self):
        for formatless in (False, True):
            with self.subTest(formatless=formatless):
                self.setUp()
                self.drawing_context()
                if formatless:
                    self.template_sketch = None
                result = self.edit()
                self.assertTrue(result["ok"], result)

    def test_drawing_format_view_or_foreign_sketch_refuses_before_assignment(self):
        for defect in (lambda: setattr(self.document, "GetEditSheet", lambda: False),
                       lambda: setattr(self.document, "ActiveDrawingView", object()),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", object()),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", self.template_sketch)):
            with self.subTest(defect=defect):
                self.setUp()
                self.drawing_context()
                defect()
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assert_no_writes()

    def test_read_phase_state_or_foreground_drift_refuses_without_repair(self):
        for drift in (lambda: setattr(self, "modified", True), lambda: setattr(self, "stamp", 8),
                      lambda: setattr(self.app, "ActiveDoc", object()),
                      lambda: setattr(self.document.SketchManager, "ActiveSketch", object())):
            with self.subTest(drift=drift):
                self.setUp()
                self.read_effect = drift
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assert_no_writes()

    def test_live_property_assignment_failure_reports_partial_mutation_before_commit(self):
        self.live = True
        self.property_effect = mock.Mock(side_effect=RuntimeError("property failure"))
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertTrue(self.native["Bold"])
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.assertEqual(self.objects[0].writes, [("Bold", True)])
        self.extension.SetUserPreferenceTextFormat.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()

    def test_property_assignment_context_drift_stops_before_document_setter(self):
        for drift in (lambda: setattr(self.configuration, "Name", "Other"),
                      lambda: setattr(self.app, "ActiveDoc", object()),
                      lambda: setattr(self.document.SketchManager, "ActiveSketch", object())):
            with self.subTest(drift=drift):
                self.setUp()
                self.live = True
                self.property_effect = lambda member, value: drift()
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertTrue(self.native["Bold"])
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceTextFormat.assert_not_called()
                self.document.SetSaveFlag.assert_not_called()

    def test_live_property_assignment_can_advance_native_dirty_and_stamp(self):
        self.live = True
        def update_state(member, value):
            self.modified = True
            self.stamp = 8
        self.property_effect = update_state
        result = self.edit()
        self.assertTrue(result["ok"], result)
        self.document.SetSaveFlag.assert_not_called()
        self.extension.SetUserPreferenceTextFormat.assert_called_once()

    def test_native_setter_false_nonbool_or_exception_never_retries_or_rolls_back(self):
        for returned in (False, 1, RuntimeError("commit failure")):
            with self.subTest(returned=returned):
                self.setUp()
                self.live = True
                self.extension.SetUserPreferenceTextFormat.side_effect = returned if isinstance(returned, Exception) else None
                self.extension.SetUserPreferenceTextFormat.return_value = returned
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertTrue(self.native["Bold"])
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.assertEqual(self.objects[0].writes, [("Bold", True)])
                self.extension.SetUserPreferenceTextFormat.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()

    def test_unrequested_font_change_is_reported_with_observation(self):
        def commit(*args):
            self.commit(*args)
            self.native["WidthFactor"] = 2.0
            return True
        self.extension.SetUserPreferenceTextFormat.side_effect = commit
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["observed_font"]["width_factor"], 2.0)
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.extension.SetUserPreferenceTextFormat.assert_called_once()
        self.document.SetSaveFlag.assert_not_called()

    def test_lost_target_or_height_mode_is_failure(self):
        for field, value in (("bold", True), ("height_points", 12)):
            with self.subTest(field=field):
                self.setUp()
                self.extension.SetUserPreferenceTextFormat.side_effect = None
                self.extension.SetUserPreferenceTextFormat.return_value = True
                result = self.edit(field, value)
                self.assertFalse(result["ok"], result)
                self.document.SetSaveFlag.assert_not_called()

    def test_readback_state_drift_cannot_be_repaired_by_mark_dirty(self):
        def read_effect():
            if self.extension.GetUserPreferenceTextFormat.call_count == 2:
                self.modified = True
        self.read_effect = read_effect
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.document.SetSaveFlag.assert_not_called()
        self.extension.SetUserPreferenceTextFormat.assert_called_once()

    def test_final_read_drift_fails_after_at_most_one_dirty_call(self):
        def read_effect():
            if self.extension.GetUserPreferenceTextFormat.call_count == 3:
                self.modified = False
        self.read_effect = read_effect
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.document.SetSaveFlag.assert_called_once()
        self.assertFalse(self.modified)

    def test_native_trace_has_flat_explicit_font_boundaries(self):
        calls = []
        def traced(stage, method, call):
            calls.append((stage, method))
            return call()
        with mock.patch.object(adapter, "native_call", side_effect=traced):
            result = self.edit()
        self.assertTrue(result["ok"], result)
        stage = "document-annotation-font"
        self.assertEqual(calls[:18], [(stage, "IModelDocExtension.GetUserPreferenceTextFormat")] + [
            (stage, "ITextFormat." + member + ("" if member == "IsHeightSpecifiedInPts" else ".get"))
            for member in ANNOTATION_FONT_MEMBERS.values()
        ])
        self.assertEqual(calls[18:20], [(stage, "ITextFormat.Bold.set"),
                                       (stage, "IModelDocExtension.SetUserPreferenceTextFormat")])
        self.assertEqual(len(calls), 56)

    def test_review_readonly_or_viewonly_transition_during_pre_read_refuses_assignment(self):
        for member in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with self.subTest(member=member):
                self.setUp()
                self.read_effect = lambda: setattr(self.document, member, lambda: True)
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assert_no_writes()

    def test_review_readonly_transition_after_live_property_stops_final_setter(self):
        self.live = True
        self.property_effect = lambda member, value: setattr(self.document, "IsOpenedReadOnly", lambda: True)
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
        self.assertTrue(self.native["Bold"])
        self.extension.SetUserPreferenceTextFormat.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()

    def test_review_initial_state_getter_cannot_replace_foreground_baseline(self):
        self.document.GetSaveFlag = lambda: (setattr(self.app, "ActiveDoc", self.document), self.modified)[1]
        result = adapter.read_document_annotation_font_windows(app=self.app, document=self.document)
        self.assertFalse(result["ok"], result)
        self.assert_no_writes()

    def test_review_initial_state_getter_cannot_clear_sketch_before_edit_baseline(self):
        initial_sketch = object()
        self.document.SketchManager.ActiveSketch = initial_sketch
        self.document.GetSaveFlag = lambda: (setattr(self.document.SketchManager, "ActiveSketch", None), self.modified)[1]
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
        self.assert_no_writes()

    def test_mm_mode_typeface_change_records_inactive_point_normalization(self):
        # Exact shape of the failed fonts-r1 observation, replayed offline.
        def commit(*args):
            self.commit(*args)
            self.native["CharHeightInPts"] = 14
            return True
        self.extension.SetUserPreferenceTextFormat.side_effect = commit
        result = self.edit("typeface", "Arial")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["native_normalizations"], [{
            "member": "CharHeightInPts", "before": 12, "after": 14,
            "reason": "inactive-height-representation",
        }])
        self.assertEqual(result["native_font"]["CharHeight"], 0.0035)
        self.assertIs(result["native_font"]["IsHeightSpecifiedInPts"], False)
        self.assertEqual(self.objects[0].writes, [("TypeFaceName", "Arial")])
        self.extension.SetUserPreferenceTextFormat.assert_called_once()
        self.document.SetSaveFlag.assert_called_once()

    def test_points_mode_style_change_records_inactive_meter_normalization(self):
        # A synthetic counterpart checks the contract, not native behavior.
        self.native.update(IsHeightSpecifiedInPts=True, CharHeightInPts=14)
        self.expected = annotation_font_snapshot(self.native)
        def commit(*args):
            self.commit(*args)
            self.native["CharHeight"] = 0.0037
            return True
        self.extension.SetUserPreferenceTextFormat.side_effect = commit
        result = self.edit("bold", True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["native_normalizations"], [{
            "member": "CharHeight", "before": 0.0035, "after": 0.0037,
            "reason": "inactive-height-representation",
        }])
        self.assertEqual(result["native_font"]["CharHeightInPts"], 14)
        self.assertIs(result["native_font"]["IsHeightSpecifiedInPts"], True)
        self.assertEqual(self.objects[0].writes, [("Bold", True)])

    def test_normalization_never_allows_active_mode_or_other_native_member_drift(self):
        for member in self.native.keys() - {"TypeFaceName", "CharHeightInPts"}:
            with self.subTest(member=member):
                self.setUp()
                old = self.native[member]
                changed = not old if type(old) is bool else old + 0.25
                def commit(*args):
                    self.commit(*args)
                    self.native.update(CharHeightInPts=14)
                    self.native[member] = changed
                    return True
                self.extension.SetUserPreferenceTextFormat.side_effect = commit
                result = self.edit("typeface", "Arial")
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.extension.SetUserPreferenceTextFormat.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()

    def test_points_mode_active_point_change_or_mode_flip_is_rejected(self):
        for member, value in (("CharHeightInPts", 15), ("IsHeightSpecifiedInPts", False)):
            with self.subTest(member=member):
                self.setUp()
                self.native.update(IsHeightSpecifiedInPts=True, CharHeightInPts=14)
                self.expected = annotation_font_snapshot(self.native)
                def commit(*args):
                    self.commit(*args)
                    self.native["CharHeight"] = 0.0037
                    self.native[member] = value
                    return True
                self.extension.SetUserPreferenceTextFormat.side_effect = commit
                result = self.edit("bold", True)
                self.assertFalse(result["ok"], result)
                self.document.SetSaveFlag.assert_not_called()

    def test_active_native_height_change_rejects_even_when_mm_rounding_hides_it(self):
        self.native["CharHeight"] = 0.003500000000000012
        self.expected = annotation_font_snapshot(self.native)
        def commit(*args):
            self.commit(*args)
            self.native["CharHeight"] = 0.0035000000000000126
            self.native["CharHeightInPts"] = 14
            return True
        self.extension.SetUserPreferenceTextFormat.side_effect = commit
        result = self.edit("bold", True)
        self.assertEqual(self.expected["height_mm"], result["observed_font"]["height_mm"])
        self.assertFalse(result["ok"], result)
        self.document.SetSaveFlag.assert_not_called()

    def test_stale_inactive_height_cas_refuses_change_and_noop_without_writing(self):
        for target in (True, False):
            with self.subTest(target=target):
                self.setUp()
                self.native["CharHeightInPts"] = 14
                result = self.edit("bold", target)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error"]["type"], "DocumentAnnotationFontConflict")
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assert_no_writes()

    def test_normalization_is_frozen_after_first_successful_native_readback(self):
        def commit(*args):
            self.commit(*args)
            self.native["CharHeightInPts"] = 14
            return True
        def change_during_final_get():
            if self.extension.GetUserPreferenceTextFormat.call_count == 3:
                self.native["CharHeightInPts"] = 15
        self.extension.SetUserPreferenceTextFormat.side_effect = commit
        self.read_effect = change_during_final_get
        result = self.edit("typeface", "Arial")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["native_normalizations"][0]["after"], 14)
        self.extension.SetUserPreferenceTextFormat.assert_called_once()
        self.document.SetSaveFlag.assert_called_once()

    def test_shared_native_effect_helper_accepts_detached_height_probe_old_mode(self):
        for member in ("CharHeight", "CharHeightInPts"):
            with self.subTest(member=member):
                self.assertEqual(annotation_font_native_normalizations(self.native, dict(self.native), member), [])

    def test_shared_native_effect_helper_rejects_invalid_inactive_type_and_finiteness(self):
        for mode, member, value in ((False, "CharHeightInPts", True),
                                    (False, "CharHeightInPts", 14.0),
                                    (True, "CharHeight", float("nan")),
                                    (True, "CharHeight", True)):
            with self.subTest(mode=mode, member=member, value=value):
                before = {**self.native, "IsHeightSpecifiedInPts": mode}
                after = {**before, "TypeFaceName": "Arial", member: value}
                with self.assertRaises(ValueError):
                    annotation_font_native_normalizations(before, after, "TypeFaceName")

    def test_changed_nonheight_field_without_normalization_returns_empty_array(self):
        result = self.edit("bold", True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["native_normalizations"], [])


if __name__ == "__main__":
    unittest.main()
