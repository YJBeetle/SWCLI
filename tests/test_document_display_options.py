"""Portable guards with read-r1 exported IDs; mocks are not native write proof."""

from math import inf, nextafter
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.operation_schemas import OPERATION_CATALOG

from swcli.document_display_options import (
    DISPLAY_FIELDS, VIRTUAL_SHARP_STYLES, resolve_display_preference_ids, validate_display_value,
)
from swcli.hosts import windows_document_display_options as adapter


class DocumentDisplayOptionsTests(unittest.TestCase):
    def setUp(self):
        # IDs are installed swconst exports; values below are mock test data.
        self.ids = {spec["symbol"]: spec["preference"] for spec in DISPLAY_FIELDS.values()}
        values = (False, 0.005, 5, 1, 2, 0x112233, 0x445566, 0x778899, 50, False)
        self.native = dict(zip(self.ids.values(), values))
        self.modified, self.stamp = False, 7
        self.configuration = SimpleNamespace(Name="Default")
        self.extension = SimpleNamespace()
        for kind in ("Integer", "Toggle", "Double"):
            setattr(self.extension, "GetUserPreference" + kind, mock.Mock(side_effect=self.read))
            setattr(self.extension, "SetUserPreference" + kind, mock.Mock(side_effect=self.apply))
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
                                   ActivateDoc3=mock.Mock(), SetUserPreferenceIntegerValue=mock.Mock(),
                                   SetUserPreferenceDoubleValue=mock.Mock(), SetUserPreferenceToggle=mock.Mock())
        self.reads = 0
        self.read_effect = None

    def read(self, preference, option):
        self.assertEqual(option, 0)
        self.reads += 1
        if self.read_effect:
            self.read_effect()
        return self.native[preference]

    def apply(self, preference, option, value):
        self.assertEqual(option, 0)
        self.native[preference] = value
        return True

    def observe(self):
        return adapter.read_document_display_options_windows(
            app=self.app, document=self.document, _preference_ids=self.ids)

    def edit(self, field="grid.display", value=True, expected_value=False):
        return adapter.set_document_display_option_windows(
            app=self.app, document=self.document, field=field, value=value,
            expected_value=expected_value, _preference_ids=self.ids,
        )

    def assert_no_setters(self):
        for kind in ("Integer", "Double", "Toggle"):
            getattr(self.extension, "SetUserPreference" + kind).assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.app.SetUserPreferenceIntegerValue.assert_not_called()
        self.app.SetUserPreferenceDoubleValue.assert_not_called()
        self.app.SetUserPreferenceToggle.assert_not_called()

    def assert_no_preference_reads(self):
        for kind in ("Integer", "Double", "Toggle"):
            getattr(self.extension, "GetUserPreference" + kind).assert_not_called()

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

    def test_registered_display_operations_keep_selected_document_and_write_guards(self):
        read = OPERATION_CATALOG["document.display-options"]
        write = OPERATION_CATALOG["document.display-option-set"]
        self.assertTrue(read.selected_document and write.selected_document)
        self.assertFalse(read.lease_guarded or read.temporary_activation or write.temporary_activation)
        self.assertTrue(write.lease_guarded)
        self.assertEqual(read.parameters["x-swcli-context"]["lease_id"], "forbidden")
        self.assertEqual(write.parameters["x-swcli-context"]["expected_update_stamp"], "required")
        self.assertEqual(set(write.parameters["properties"]), {"field", "value", "expected_value"})
        self.assertEqual(set(write.parameters["required"]), {"field", "value", "expected_value"})

    def test_catalog_is_ordered_exact_ten_symbols_with_read_r1_exported_ids(self):
        self.assertEqual([spec["symbol"] for spec in DISPLAY_FIELDS.values()], [
            "swGridDisplay", "swGridMajorSpacing", "swGridMinorLinesPerMajor", "swSnapPointsPerMinor",
            "swDetailingVirtualSharpStyle", "swPlaneDisplayFrontFaceColor", "swPlaneDisplayBackFaceColor",
            "swPlaneDisplayIntersectionLineColor", "swPlaneDisplayTransparency", "swPlaneDisplayShowIntersections",
        ])
        self.assertEqual([spec["preference"] for spec in DISPLAY_FIELDS.values()],
                         [57, 30, 42, 43, 41, 145, 146, 148, 147, 138])
        self.assertTrue(all(spec["option"] == 0 for spec in DISPLAY_FIELDS.values()))
        self.assertNotIn("swGridDisplayDashed", self.ids)
        self.assertNotIn("swGridAutomaticScaling", self.ids)

    def test_unconfigured_ids_fail_closed_before_preference_reads_or_setters(self):
        unconfigured = {field: {**spec, "preference": None} for field, spec in DISPLAY_FIELDS.items()}
        with mock.patch.dict(DISPLAY_FIELDS, unconfigured, clear=True):
            result = adapter.read_document_display_options_windows(app=self.app, document=self.document)
            self.assertFalse(result["ok"], result)
            result = adapter.set_document_display_option_windows(
                app=self.app, document=self.document, field="grid.display", value=True, expected_value=False)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
        self.assert_no_preference_reads()
        self.assert_no_setters()

    def test_default_ids_read_read_r1_profile_with_meter_conversion_and_document_scope(self):
        # Offline replay of raw read-r1 observations; no COM/native execution.
        observed_raw = (False, 0.1, 4, 1, 3, 33023, 16512, 0, 95, True)
        for kind in (1, 2, 3):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == 3:
                    self.drawing_context()
                else:
                    self.document.GetType = lambda: kind
                self.native = dict(zip(self.ids.values(), observed_raw))
                result = adapter.read_document_display_options_windows(app=self.app, document=self.document)
                self.assertTrue(result["ok"], result)
                self.assertEqual(len(result["options"]), 5 if kind == 3 else 10)
                self.assertEqual(result["options"]["grid.major_spacing_mm"], {"value": 100.0, "native_value": 0.1})
                self.assertEqual(result["options"]["virtual_sharp.style"], {"value": "witness", "native_value": 3})
                if kind != 3:
                    self.assertEqual(result["options"]["plane.front_face_color"], {"value": 33023, "native_value": 33023})
                self.assert_no_setters()

    def test_mapping_requires_exact_symbols_int32_and_nonaliased_native_fields(self):
        missing = dict(self.ids)
        missing.pop("swGridDisplay")
        invalid = [missing, {**self.ids, "arbitraryPreference": 123},
                   {**self.ids, "swGridDisplay": None}, {**self.ids, "swGridDisplay": True},
                   {**self.ids, "swGridDisplay": -1}, {**self.ids, "swGridDisplay": 2147483648},
                   {**self.ids, "swGridDisplay": 1.0},
                   {**self.ids, "swGridMinorLinesPerMajor": self.ids["swSnapPointsPerMinor"]}]
        for ids in invalid:
            with self.subTest(ids=ids):
                self.ids = ids
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assert_no_preference_reads()
                self.assert_no_setters()

    def test_separate_api_families_can_share_same_numeric_id(self):
        ids = dict(self.ids)
        ids["swGridDisplay"] = ids["swGridMajorSpacing"]
        self.assertEqual(resolve_display_preference_ids(ids), ids)

    def test_read_part_and_assembly_full_ten_fields_without_activation(self):
        for kind in (1, 2):
            with self.subTest(kind=kind):
                self.setUp()
                self.document.GetType = lambda: kind
                result = self.observe()
                self.assertTrue(result["ok"], result)
                self.assertEqual(list(result["options"]), list(DISPLAY_FIELDS))
                self.assertEqual(result["options"]["grid.major_spacing_mm"], {"value": 5.0, "native_value": 0.005})
                self.assertEqual(result["options"]["virtual_sharp.style"], {"value": "star", "native_value": 2})
                self.assertEqual(result["options"]["plane.front_face_color"], {"value": 0x112233, "native_value": 0x112233})
                self.assertEqual(self.reads, 10)
                self.assertIs(self.app.ActiveDoc, self.foreground)
                self.assert_no_setters()

    def test_drawing_read_has_only_five_nonplane_fields(self):
        self.drawing_context()
        result = self.observe()
        self.assertTrue(result["ok"], result)
        self.assertEqual(list(result["options"]), list(DISPLAY_FIELDS)[:5])
        self.assertEqual(self.reads, 5)
        self.assert_no_setters()

    def test_drawing_plane_write_and_noop_refuse_before_preference_reads(self):
        self.drawing_context()
        for field in list(DISPLAY_FIELDS)[5:]:
            with self.subTest(field=field):
                spec = DISPLAY_FIELDS[field]
                initial = self.native[self.ids[spec["symbol"]]]
                result = self.edit(field, initial, initial)
                self.assertFalse(result["ok"], result)
                self.assert_no_preference_reads()
                self.assert_no_setters()

    def test_each_field_uses_only_its_own_document_setter_and_preserves_others(self):
        changes = (
            ("grid.display", True, False, True),
            ("grid.major_spacing_mm", 10, 5.0, 0.010),
            ("grid.minor_lines_per_major", 10, 5, 10),
            ("grid.snap_points_per_minor", 2, 1, 2),
            ("virtual_sharp.style", "dot", "star", 4),
            ("plane.front_face_color", 0x010203, 0x112233, 0x010203),
            ("plane.back_face_color", 0x010203, 0x445566, 0x010203),
            ("plane.intersection_line_color", 0x010203, 0x778899, 0x010203),
            ("plane.transparency", 0, 50, 0),
            ("plane.show_intersections", True, False, True),
        )
        for field, value, expected, native_value in changes:
            with self.subTest(field=field):
                self.setUp()
                before = dict(self.native)
                result = self.edit(field, value, expected)
                self.assertTrue(result["ok"], result)
                spec = DISPLAY_FIELDS[field]
                preference = self.ids[spec["symbol"]]
                self.assertEqual(self.native, {**before, preference: native_value})
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.assertTrue(result["changed"])
                getattr(self.extension, "SetUserPreference" + spec["kind"]).assert_called_once_with(preference, 0, native_value)
                self.document.SetSaveFlag.assert_called_once_with()
                self.assertEqual(self.reads, 30)
                self.assertIs(self.app.ActiveDoc, self.foreground)

    def test_all_virtual_sharp_enum_candidates_and_boolean_both_directions(self):
        preference = self.ids["swDetailingVirtualSharpStyle"]
        for name, native in VIRTUAL_SHARP_STYLES.items():
            with self.subTest(name=name):
                self.setUp()
                initial_name = "plus" if name == "none" else "none"
                self.native[preference] = VIRTUAL_SHARP_STYLES[initial_name]
                result = self.edit("virtual_sharp.style", name, initial_name)
                self.assertTrue(result["ok"], result)
                self.assertEqual(self.native[preference], native)
        for field in ("grid.display", "plane.show_intersections"):
            with self.subTest(field=field):
                self.setUp()
                self.native[self.ids[DISPLAY_FIELDS[field]["symbol"]]] = True
                result = self.edit(field, False, True)
                self.assertTrue(result["ok"], result)
                self.assertIs(result["options"][field]["value"], False)

    def test_color_and_transparency_candidate_boundaries(self):
        for field, targets in (("plane.front_face_color", (0, 0xFFFFFF)), ("plane.transparency", (0, 100))):
            for value in targets:
                with self.subTest(field=field, value=value):
                    self.setUp()
                    spec = DISPLAY_FIELDS[field]
                    initial = self.native[self.ids[spec["symbol"]]]
                    result = self.edit(field, value, initial)
                    self.assertTrue(result["ok"], result)

    def test_same_values_do_not_write_or_mark_dirty(self):
        observed = self.observe()["options"]
        for field, row in observed.items():
            with self.subTest(field=field):
                result = self.edit(field, row["value"], row["value"])
                self.assertTrue(result["ok"], result)
                self.assertFalse(result["changed"])
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assert_no_setters()

    def test_target_cas_conflict_stops_before_setter_even_if_target_is_noop(self):
        for value in (True, False):
            with self.subTest(value=value):
                result = self.edit("grid.display", value, True)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error"]["type"], "DocumentDisplayConflict")
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assert_no_setters()

    def test_one_ulp_stale_spacing_cas_refuses_change_and_noop_without_setters(self):
        for target in (10.0, 5.0):
            with self.subTest(target=target):
                self.setUp()
                result = self.edit("grid.major_spacing_mm", target, nextafter(5.0, inf))
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error"]["type"], "DocumentDisplayConflict")
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assertEqual(self.native[self.ids["swGridMajorSpacing"]], 0.005)
                self.assert_no_setters()

    def test_spacing_cas_accepts_equal_json_int_and_float_values(self):
        result = self.edit("grid.major_spacing_mm", 10.0, 5)
        self.assertTrue(result["ok"], result)
        self.extension.SetUserPreferenceDouble.assert_called_once_with(self.ids["swGridMajorSpacing"], 0, 0.01)

    def test_target_same_value_keeps_float_representation_tolerance(self):
        result = self.edit("grid.major_spacing_mm", nextafter(5.0, inf), 5.0)
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["changed"])
        self.assert_no_setters()

    def test_unknown_enum_and_out_of_candidate_integer_ranges_are_observed_raw(self):
        self.native[self.ids["swDetailingVirtualSharpStyle"]] = 99
        self.native[self.ids["swPlaneDisplayFrontFaceColor"]] = -1
        result = self.observe()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["options"]["virtual_sharp.style"], {"value": "other", "native_value": 99})
        self.assertEqual(result["options"]["plane.front_face_color"], {"value": -1, "native_value": -1})
        self.assert_no_setters()
        result = self.edit("virtual_sharp.style", "dot", "other")
        self.assertFalse(result["ok"], result)
        self.assert_no_setters()

    def test_readonly_native_integer_can_be_cas_prevalue_without_becoming_writable(self):
        self.native[self.ids["swPlaneDisplayFrontFaceColor"]] = -1
        result = self.edit("plane.front_face_color", 0, -1)
        self.assertTrue(result["ok"], result)
        with self.assertRaises(ValueError):
            validate_display_value("plane.front_face_color", -1)

    def test_invalid_values_types_finiteness_and_arbitrary_fields_refuse_before_reads(self):
        cases = (
            ("grid.display", 1, False), ("grid.major_spacing_mm", True, 5),
            ("grid.major_spacing_mm", 0, 5), ("grid.major_spacing_mm", 5e-324, 5),
            ("grid.major_spacing_mm", float("inf"), 5), ("grid.major_spacing_mm", 10 ** 1000, 5),
            ("grid.major_spacing_mm", 5, float("nan")), ("grid.minor_lines_per_major", 1.0, 5),
            ("grid.minor_lines_per_major", 0, 5), ("grid.snap_points_per_minor", 2147483648, 1),
            ("virtual_sharp.style", 4, "star"), ("virtual_sharp.style", "other", "star"),
            ("plane.front_face_color", -1, 0), ("plane.front_face_color", 0x1000000, 0),
            ("plane.front_face_color", True, 0), ("plane.transparency", 101, 50),
            ("plane.transparency", 50, True), ("plane.show_intersections", None, False),
            ("swGridDisplayDashed", True, False), ("arbitraryPreference", 1, 0),
        )
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                result = self.edit(field, value, expected)
                self.assertFalse(result["ok"], result)
                self.assert_no_preference_reads()
                self.assert_no_setters()

    def test_native_wrong_types_nonfinite_and_outside_int32_fail_reads(self):
        cases = (("swGridDisplay", 1), ("swGridMajorSpacing", True), ("swGridMajorSpacing", 0),
                 ("swGridMajorSpacing", float("inf")), ("swGridMajorSpacing", 10 ** 1000),
                 ("swGridMajorSpacing", 1.7976931348623157e308), ("swGridMinorLinesPerMajor", 5.0),
                 ("swDetailingVirtualSharpStyle", True), ("swPlaneDisplayFrontFaceColor", 2147483648))
        for symbol, raw in cases:
            with self.subTest(symbol=symbol):
                self.setUp()
                self.native[self.ids[symbol]] = raw
                result = self.observe()
                self.assertFalse(result["ok"], result)
                self.assert_no_setters()

    def test_readonly_or_viewonly_refuses_before_preference_reads(self):
        for member in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with self.subTest(member=member):
                self.setUp()
                setattr(self.document, member, lambda: True)
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assert_no_preference_reads()
                self.assert_no_setters()

    def test_no_active_model_sketch_required_for_change_but_not_noop(self):
        self.document.SketchManager.ActiveSketch = object()
        self.assertFalse(self.edit()["ok"])
        self.assertTrue(self.edit("grid.display", False, False)["ok"])
        self.assert_no_setters()

    def test_normal_drawing_or_formatless_sheet_can_write_nonplane_candidate(self):
        for formatless in (False, True):
            with self.subTest(formatless=formatless):
                self.setUp()
                self.drawing_context()
                if formatless:
                    self.template_sketch = None
                result = self.edit()
                self.assertTrue(result["ok"], result)
                self.assertEqual(self.reads, 15)
                self.assertEqual(len(result["options"]), 5)

    def test_drawing_format_view_foreign_or_missing_sketch_refuses_before_setter(self):
        for defect in (lambda: setattr(self.document, "GetEditSheet", lambda: False),
                       lambda: setattr(self.document, "ActiveDrawingView", object()),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", object()),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", None),
                       lambda: setattr(self.document.SketchManager, "ActiveSketch", self.template_sketch)):
            with self.subTest(defect=defect):
                self.setUp()
                self.drawing_context()
                defect()
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assert_no_setters()

    def test_pre_read_state_context_or_foreground_drift_is_not_repaired(self):
        for drift in (lambda: setattr(self, "modified", True), lambda: setattr(self, "stamp", 8),
                      lambda: setattr(self.configuration, "Name", "Other"),
                      lambda: setattr(self.app, "ActiveDoc", object()),
                      lambda: setattr(self.document.SketchManager, "ActiveSketch", object())):
            with self.subTest(drift=drift):
                self.setUp()
                self.read_effect = drift
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assert_no_setters()

    def test_native_setter_failure_is_single_attempt_with_partial_mutation(self):
        for failure in (False, 1, RuntimeError("setter failed")):
            with self.subTest(failure=failure):
                self.setUp()
                setter = self.extension.SetUserPreferenceToggle
                def fail(preference, option, value):
                    self.native[preference] = value
                    if isinstance(failure, Exception):
                        raise failure
                    return failure
                setter.side_effect = fail
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.assertIs(self.native[self.ids["swGridDisplay"]], True)
                setter.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()

    def test_lost_target_and_unrequested_field_mutation_fail_without_mark_dirty(self):
        for unrequested in (False, True):
            with self.subTest(unrequested=unrequested):
                self.setUp()
                def apply(preference, option, value):
                    if unrequested:
                        self.native[preference] = value
                        self.native[self.ids["swPlaneDisplayTransparency"]] = 75
                    return True
                self.extension.SetUserPreferenceToggle.side_effect = apply
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertIn("observed_options", result)
                self.extension.SetUserPreferenceToggle.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()

    def test_readback_and_final_read_state_drift_are_not_silently_repaired(self):
        for phase in (2, 3):
            for drift in (lambda: setattr(self, "modified", not self.modified),
                          lambda: setattr(self, "stamp", self.stamp + 1),
                          lambda: setattr(self.document.SketchManager, "ActiveSketch", object())):
                with self.subTest(phase=phase, drift=drift):
                    self.setUp()
                    def read_effect():
                        if self.reads == 10 * (phase - 1) + 1:
                            drift()
                    self.read_effect = read_effect
                    result = self.edit()
                    self.assertFalse(result["ok"], result)
                    self.extension.SetUserPreferenceToggle.assert_called_once()
                    self.assertEqual(self.document.SetSaveFlag.call_count, int(phase == 3))

    def test_native_setter_may_advance_stamp_and_dirty(self):
        def apply(preference, option, value):
            self.apply(preference, option, value)
            self.stamp += 1
            self.modified = True
            return True
        self.extension.SetUserPreferenceToggle.side_effect = apply
        result = self.edit()
        self.assertTrue(result["ok"], result)
        self.document.SetSaveFlag.assert_not_called()

    def test_trace_records_exact_ordered_read_write_read_read_phases(self):
        calls = []
        def traced(stage, method, call):
            calls.append((stage, method))
            return call()
        with mock.patch.object(adapter, "native_call", side_effect=traced):
            result = self.edit()
        self.assertTrue(result["ok"], result)
        read_phase = [("document-display-options", "IModelDocExtension.GetUserPreference" + spec["kind"])
                      for spec in DISPLAY_FIELDS.values()]
        self.assertEqual(calls, read_phase + [("document-display-options", "IModelDocExtension.SetUserPreferenceToggle")]
                         + read_phase + read_phase)

    def test_review_readonly_or_viewonly_transition_during_pre_read_refuses_setter(self):
        for member in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with self.subTest(member=member):
                self.setUp()
                self.read_effect = lambda: setattr(self.document, member, lambda: True)
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
                self.assert_no_setters()

    def test_review_initial_state_getter_cannot_replace_foreground_baseline(self):
        self.document.GetSaveFlag = lambda: (setattr(self.app, "ActiveDoc", self.document), self.modified)[1]
        result = self.observe()
        self.assertFalse(result["ok"], result)
        self.assert_no_setters()

    def test_review_initial_state_getter_cannot_clear_sketch_before_edit_baseline(self):
        self.document.SketchManager.ActiveSketch = object()
        self.document.GetSaveFlag = lambda: (setattr(self.document.SketchManager, "ActiveSketch", None), self.modified)[1]
        result = self.edit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
        self.assert_no_setters()


if __name__ == "__main__":
    unittest.main()
