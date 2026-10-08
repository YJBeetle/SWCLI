"""Internal rectangle creation: exact geometry, partial evidence and cleanup."""

import json
import math
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_rectangle_dimensions as rectangles


class RectangleDimensionTests(unittest.TestCase):
    def setUp(self):
        self.width, self.height, self.center = 40, 30, [3, 4]
        self.preserve_center = True
        self.update_geometry = True
        self.preference = True
        self.native_values = {"width": 0.04, "height": 0.03}
        self.created_displays = []
        self.edges = []
        for index in range(4):
            self.edges.append(
                SimpleNamespace(
                    ConstructionGeometry=False,
                    GetType=lambda: 0,
                    GetStartPoint2=lambda i=index: self.point(i),
                    GetEndPoint2=lambda i=index: self.point((i + 1) % 4),
                    Select4=mock.Mock(return_value=True),
                )
            )
        self.segments = self.edges + [SimpleNamespace(ConstructionGeometry=True)] * 2
        self.sketch = SimpleNamespace(
            GetSketchSegments=lambda: self.segments,
            GetConstrainedStatus=lambda: 3,
        )
        self.feature = SimpleNamespace(
            GetID=lambda: 17,
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda: self.sketch,
            GetOwnerFeature=lambda: None,
            GetNextFeature=lambda: None,
            GetFirstSubFeature=lambda: None,
            GetNextSubFeature=lambda: None,
            Select2=mock.Mock(return_value=True),
            GetFirstDisplayDimension=lambda: (
                self.created_displays[0] if self.created_displays else None
            ),
            GetNextDisplayDimension=lambda display: self.next_display(display),
        )
        self.manager = SimpleNamespace(ActiveSketch=None)
        self.manager.InsertSketch = mock.Mock(side_effect=self.exit_edit)
        self.native = {}
        self.displays = {}
        for kind, display_type in (("width", 11), ("height", 12)):
            self.native[kind] = SimpleNamespace(
                DrivenState=2,
                ReadOnly=0,
                FullName=f"{kind}@renamed@part",
                GetType=lambda: 0,
                GetFeatureOwner=lambda: self.feature,
                IsDesignTableDimension=lambda: False,
                GetSystemValue2=lambda config, k=kind: self.native_values[k],
                SetSystemValue3=mock.Mock(
                    side_effect=lambda value, config, names, k=kind: self.set_value(
                        k, value
                    )
                ),
            )
            self.displays[kind] = SimpleNamespace(
                Type2=display_type,
                GetDimension2=lambda index, k=kind: self.native[k],
            )
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            SketchManager=self.manager,
            ClearSelection2=mock.Mock(),
            EditSketch=mock.Mock(spec=(), side_effect=self.enter_edit),
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="Default")
            ),
            GetEquationMgr=lambda: SimpleNamespace(GetCount=lambda: 0),
            AddHorizontalDimension2=mock.Mock(
                side_effect=lambda *xyz: self.create("width")
            ),
            AddVerticalDimension2=mock.Mock(
                side_effect=lambda *xyz: self.create("height")
            ),
        )
        self.app = SimpleNamespace(
            IsSame=mock.Mock(side_effect=lambda first, second: int(first is second)),
            GetUserPreferenceToggle=mock.Mock(side_effect=lambda flag: self.preference),
            SetUserPreferenceToggle=mock.Mock(side_effect=self.set_preference),
        )
        for name, value in (
            ("_variant", lambda kind, value: (kind, value)),
            ("_annotation_location", lambda *args: (0.05, 0.04, 0.0)),
        ):
            patcher = mock.patch.object(rectangles, name, side_effect=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def point(self, index):
        x_sign, y_sign = ((-1, -1), (1, -1), (1, 1), (-1, 1))[index]
        return SimpleNamespace(
            X=(self.center[0] + x_sign * self.width / 2) / 1000,
            Y=(self.center[1] + y_sign * self.height / 2) / 1000,
            Z=0,
        )

    def enter_edit(self):
        self.manager.ActiveSketch = self.sketch

    def exit_edit(self, update):
        self.manager.ActiveSketch = None

    def set_preference(self, flag, value):
        self.preference = value
        return None  # Native late binding commonly returns void on success.

    def next_display(self, display):
        index = self.created_displays.index(display) + 1
        return (
            self.created_displays[index] if index < len(self.created_displays) else None
        )

    def create(self, kind):
        self.created_displays.append(self.displays[kind])
        return self.displays[kind]

    def set_value(self, kind, value):
        self.native_values[kind] = value
        if self.update_geometry:
            attribute, axis = ("width", 0) if kind == "width" else ("height", 1)
            previous = getattr(self, attribute)
            setattr(self, attribute, value * 1000)
            if not self.preserve_center:
                self.center[axis] += (value * 1000 - previous) / 2
        return 0

    def call(self, width=50, height=35):
        return rectangles.create_rectangle_dimensions_windows_with_handles(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature,
            width_mm=width,
            height_mm=height,
        )

    def assert_failed(self, result, code):
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], code, result)
        json.dumps(result, allow_nan=False)

    def test_exact_pair_native_roles_geometry_and_cleanup(self):
        result, handles = self.call()
        self.assertTrue(result["ok"], result)
        for kind, value in (("width", 0.05), ("height", 0.035)):
            self.assertIs(handles[kind], self.native[kind])
            self.assertEqual(result["dimensions"][kind]["kind"], kind)
            self.native[kind].SetSystemValue3.assert_called_once_with(
                value, 1, ("empty", None)
            )
        self.assertEqual(result["native_status"], {"width": 0, "height": 0})
        self.assertTrue(result["geometry_verification"]["center_preserved"])
        self.assertEqual(
            result["geometry_verification"]["actual"]["center_mm"],
            {"x": 3, "y": 4, "z": 0},
        )
        self.edges[0].Select4.assert_called_once_with(False, ("dispatch", None))
        self.edges[3].Select4.assert_called_once_with(False, ("dispatch", None))
        self.assertIsNone(self.manager.ActiveSketch)
        self.assertTrue(self.preference)
        self.assertEqual(
            self.app.SetUserPreferenceToggle.call_args_list,
            [mock.call(10, False), mock.call(10, True)],
        )
        self.assertNotIn("warnings", result)
        self.assertFalse(hasattr(self.document, "SketchAddConstraints"))
        json.dumps(result, allow_nan=False)

    def test_unanchored_current_sizes_do_not_require_an_added_constraint(self):
        self.preserve_center = False
        result, _ = self.call(40, 30)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.center, [3, 4])

    def test_width_center_drift_fails_before_height_without_implicit_fix_or_retry(self):
        self.preserve_center = False
        result, handles = self.call()
        self.assert_failed(result, "DimensionVerificationFailed")
        self.assertTrue(result["steps"]["width"]["size_matched"])
        self.assertFalse(result["steps"]["width"]["center_preserved"])
        self.assertEqual(set(handles), {"width"})
        self.document.AddHorizontalDimension2.assert_called_once()
        self.document.AddVerticalDimension2.assert_not_called()
        self.assertTrue(result["modification_may_have_happened"])
        self.assertIsNone(self.manager.ActiveSketch)

    def test_second_creation_failure_preserves_first_exact_handle(self):
        self.document.AddVerticalDimension2.return_value = None
        self.document.AddVerticalDimension2.side_effect = None
        result, handles = self.call()
        self.assert_failed(result, "DimensionCreationFailed")
        self.assertEqual(set(handles), {"width"})
        self.assertIs(handles["width"], self.native["width"])
        self.assertEqual(result["dimensions"]["width"]["value"], 50)
        self.assertTrue(result["modification_may_have_happened"])
        self.assertIsNone(self.manager.ActiveSketch)
        self.assertTrue(self.preference)

    def test_height_center_drift_retains_both_exact_handles(self):
        self.preserve_center = False
        result, handles = self.call(40, 35)
        self.assert_failed(result, "DimensionVerificationFailed")
        self.assertTrue(result["steps"]["width"]["passed"])
        self.assertTrue(result["steps"]["height"]["size_matched"])
        self.assertFalse(result["steps"]["height"]["center_preserved"])
        self.assertEqual(set(handles), {"width", "height"})
        self.native["height"].SetSystemValue3.assert_called_once()

    def test_native_unsupported_dimension_pairs_use_exact_com_identity(self):
        tokens = {id(dimension): object() for dimension in self.native.values()}

        def compare(first, second):
            if id(first) in tokens and id(second) in tokens and first is not second:
                return 2
            return int(first is second)

        self.app.IsSame.side_effect = compare
        with mock.patch(
            "swcli.hosts.windows_dimension_identity._query_iunknown",
            side_effect=lambda dimension: tokens[id(dimension)],
        ) as query:
            result, _ = self.call()
        self.assertTrue(result["ok"], result)
        self.assertGreaterEqual(query.call_count, 2)

    def test_successful_width_set_cannot_change_the_other_size(self):
        def changed(value, config, names):
            self.height += 1
            return self.set_value("width", value)

        self.native["width"].SetSystemValue3.side_effect = changed
        result, handles = self.call()
        self.assert_failed(result, "DimensionVerificationFailed")
        self.assertTrue(result["steps"]["width"]["center_preserved"])
        self.assertFalse(result["steps"]["width"]["size_matched"])
        self.assertEqual(set(handles), {"width"})
        self.document.AddVerticalDimension2.assert_not_called()

    def test_post_set_control_and_ownership_are_rechecked(self):
        for member, value, expected in (
            ("ReadOnly", True, "DimensionVerificationFailed"),
            ("DrivenState", 1, "DimensionVerificationFailed"),
            ("GetFeatureOwner", lambda: object(), "DimensionVerificationFailed"),
            ("IsDesignTableDimension", lambda: True, "DimensionExternallyControlled"),
        ):
            with self.subTest(member=member):
                self.setUp()

                def changed(length, config, names):
                    status = self.set_value("width", length)
                    setattr(self.native["width"], member, value)
                    return status

                self.native["width"].SetSystemValue3.side_effect = changed
                result, handles = self.call()
                self.assert_failed(result, expected)
                self.assertEqual(set(handles), {"width"})
                self.document.AddVerticalDimension2.assert_not_called()

    def test_invalid_native_length_metadata_preserves_partial_evidence(self):
        for value in (None, True, False, "0.04", math.nan, math.inf, 0, -1):
            with self.subTest(value=value):
                self.setUp()
                self.native["width"].GetSystemValue2 = lambda config: value
                result, handles = self.call()
                self.assert_failed(result, "DimensionObservationUnavailable")
                self.assertIs(handles["width"], self.native["width"])
                self.native["width"].SetSystemValue3.assert_not_called()

    def test_final_owner_and_value_are_verified_after_exit(self):
        def exit_changed(update):
            self.manager.ActiveSketch = None
            self.native_values["width"] = 0.051

        self.manager.InsertSketch.side_effect = exit_changed
        result, handles = self.call()
        self.assert_failed(result, "DimensionVerificationFailed")
        self.assertEqual(set(handles), {"width", "height"})
        self.assertTrue(result["geometry_verification"]["passed"])

    def test_invalid_input_refuses_before_native_reads_or_selection(self):
        for value in (
            0,
            -1,
            True,
            None,
            "40",
            math.nan,
            math.inf,
            5e-324,
            10**1000,
            1e20,
            1e-6,
            2e-6,
        ):
            for axis in (0, 1):
                with self.subTest(value=str(value)[:20], axis=axis):
                    args = [40, 30]
                    args[axis] = value
                    result, handles = self.call(*args)
                    self.assert_failed(result, "InvalidArgument")
                    self.assertEqual(handles, {})
        self.document.ClearSelection2.assert_not_called()
        self.app.IsSame.assert_not_called()

    def test_existing_dimension_refuses_before_edit_or_prompt_change(self):
        self.created_displays = [self.displays["width"]]
        result, handles = self.call()
        self.assert_failed(result, "SketchAlreadyDimensioned")
        self.assertEqual(handles, {})
        self.document.EditSketch.assert_not_called()
        self.app.SetUserPreferenceToggle.assert_not_called()

    def test_non_part_existing_edit_and_consumed_profile_are_refused(self):
        for setup, code in (
            (
                lambda: setattr(self.document, "GetType", lambda: 2),
                "UnsupportedDocumentType",
            ),
            (
                lambda: setattr(self.manager, "ActiveSketch", object()),
                "SketchEditInProgress",
            ),
            (
                lambda: setattr(self.feature, "GetOwnerFeature", lambda: object()),
                "SketchUnavailable",
            ),
        ):
            with self.subTest(code=code):
                self.setUp()
                setup()
                result, handles = self.call()
                self.assert_failed(result, code)
                self.assertEqual(handles, {})
                self.document.EditSketch.assert_not_called()

    def test_topology_and_metadata_failure_do_not_enter_edit(self):
        self.segments = self.edges[:3]
        result, _ = self.call()
        self.assert_failed(result, "UnsupportedDimensionProfile")
        self.document.EditSketch.assert_not_called()
        self.segments = self.edges
        self.edges[0].ConstructionGeometry = 0
        result, _ = self.call()
        self.assert_failed(result, "DimensionObservationUnavailable")
        self.document.EditSketch.assert_not_called()

    def test_selected_axis_is_geometric_not_segment_order(self):
        self.segments = [self.edges[2], self.edges[0], self.edges[3], self.edges[1]]
        result, _ = self.call()
        self.assertTrue(result["ok"], result)
        self.edges[0].Select4.assert_called_once()
        self.edges[3].Select4.assert_called_once()
        self.edges[1].Select4.assert_not_called()
        self.edges[2].Select4.assert_not_called()

    def test_wrong_display_role_parameter_type_or_owner_retains_unverified_handle(self):
        for setup, code in (
            (
                lambda: setattr(self.displays["width"], "Type2", 12),
                "DimensionVerificationFailed",
            ),
            (
                lambda: setattr(self.native["width"], "GetType", lambda: 1),
                "DimensionVerificationFailed",
            ),
            (
                lambda: setattr(
                    self.native["width"], "GetFeatureOwner", lambda: object()
                ),
                "DimensionVerificationFailed",
            ),
            (
                lambda: setattr(self.displays["width"], "Type2", True),
                "DimensionObservationUnavailable",
            ),
        ):
            with self.subTest(code=code):
                self.setUp()
                setup()
                result, handles = self.call()
                self.assert_failed(result, code)
                self.assertIs(handles["width"], self.native["width"])
                self.native["width"].SetSystemValue3.assert_not_called()

    def test_driven_read_only_design_table_and_equation_controls_refuse_set(self):
        for setup, code in (
            (
                lambda: setattr(self.native["width"], "DrivenState", 1),
                "DimensionNotDriving",
            ),
            (
                lambda: setattr(self.native["width"], "ReadOnly", -1),
                "DimensionNotDriving",
            ),
            (
                lambda: setattr(
                    self.native["width"], "IsDesignTableDimension", lambda: True
                ),
                "DimensionExternallyControlled",
            ),
            (
                lambda: setattr(
                    self.document,
                    "GetEquationMgr",
                    lambda: SimpleNamespace(
                        GetCount=lambda: 1, Equation=lambda i: '"width@renamed" = 0.04'
                    ),
                ),
                "DimensionExternallyControlled",
            ),
        ):
            with self.subTest(code=code):
                self.setUp()
                setup()
                result, handles = self.call()
                self.assert_failed(result, code)
                self.assertEqual(set(handles), {"width"})
                self.native["width"].SetSystemValue3.assert_not_called()

    def test_false_success_value_or_geometry_is_not_accepted(self):
        self.update_geometry = False
        result, _ = self.call()
        self.assert_failed(result, "DimensionVerificationFailed")
        self.assertEqual(result["dimensions"]["width"]["value"], 50)
        self.document.AddVerticalDimension2.assert_not_called()

    def test_native_status_is_not_truthiness_or_integer_coerced(self):
        for value in (None, True, False, "0", 0.0, 0.9, 1):
            with self.subTest(value=value):
                self.setUp()
                self.native["width"].SetSystemValue3.side_effect = None
                self.native["width"].SetSystemValue3.return_value = value
                result, _ = self.call()
                self.assert_failed(
                    result,
                    (
                        "DimensionSetFailed"
                        if value == 1 and type(value) is int
                        else "DimensionObservationUnavailable"
                    ),
                )
                self.document.AddVerticalDimension2.assert_not_called()

    def test_missing_native_parameter_reports_possible_mutation_without_fabricating_handle(
        self,
    ):
        self.displays["width"].GetDimension2 = lambda i: None
        result, handles = self.call()
        self.assert_failed(result, "DimensionObservationUnavailable")
        self.assertEqual(handles, {})
        self.assertTrue(result["modification_may_have_happened"])

    def test_no_two_roles_for_the_same_native_parameter(self):
        self.displays["height"].GetDimension2 = lambda i: self.native["width"]
        result, handles = self.call()
        self.assert_failed(result, "DimensionVerificationFailed")
        self.assertEqual(set(handles), {"width", "height"})
        self.native["height"].SetSystemValue3.assert_not_called()

    def test_configuration_change_stops_second_mutation(self):
        def changed(value, config, names):
            self.document.ConfigurationManager.ActiveConfiguration.Name = "Other"
            return self.set_value("width", value)

        self.native["width"].SetSystemValue3.side_effect = changed
        result, _ = self.call()
        self.assert_failed(result, "DimensionObservationUnavailable")
        self.document.AddVerticalDimension2.assert_not_called()

    def test_exit_geometry_is_rechecked_and_partial_handles_survive(self):
        def exit_changed(update):
            self.manager.ActiveSketch = None
            self.center[0] += 1

        self.manager.InsertSketch.side_effect = exit_changed
        result, handles = self.call()
        self.assert_failed(result, "DimensionVerificationFailed")
        self.assertEqual(set(handles), {"width", "height"})
        self.assertFalse(result["geometry_verification"]["center_preserved"])

    def test_final_constraint_metadata_is_strict(self):
        self.sketch.GetConstrainedStatus = lambda: 3.0
        result, handles = self.call()
        self.assert_failed(result, "DimensionObservationUnavailable")
        self.assertEqual(set(handles), {"width", "height"})

    def test_owned_edit_cleanup_does_not_close_a_foreign_sketch_or_mask_error(self):
        foreign = object()

        def failed(*args):
            self.manager.ActiveSketch = foreign
            raise RuntimeError("primary native failure")

        self.native["width"].SetSystemValue3.side_effect = failed
        result, _ = self.call()
        self.assert_failed(result, "RuntimeError")
        self.assertEqual(result["error"]["message"], "primary native failure")
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")
        self.assertIs(self.manager.ActiveSketch, foreign)
        self.manager.InsertSketch.assert_not_called()

    def test_cleanup_failure_cannot_return_success(self):
        self.document.ClearSelection2.side_effect = [
            None,
            None,
            None,
            RuntimeError("selection stuck"),
        ]
        result, handles = self.call()
        self.assert_failed(result, "DimensionCleanupFailed")
        self.assertEqual(set(handles), {"width", "height"})
        self.assertEqual(result["warnings"][0]["code"], "selection-cleanup-failed")

    def test_unknown_prompt_refuses_before_edit(self):
        self.app.GetUserPreferenceToggle.side_effect = lambda flag: 1
        result, _ = self.call()
        self.assert_failed(result, "DimensionObservationUnavailable")
        self.document.EditSketch.assert_not_called()

    def test_failed_prompt_suppression_does_not_create_dimensions(self):
        self.app.SetUserPreferenceToggle.side_effect = None
        result, _ = self.call()
        self.assert_failed(result, "DimensionCreationFailed")
        self.document.AddHorizontalDimension2.assert_not_called()
        self.assertIsNone(self.manager.ActiveSketch)

    def test_prompt_restore_failure_fails_completed_creation(self):
        def set_prompt(flag, value):
            if value is False:
                self.preference = False

        self.app.SetUserPreferenceToggle.side_effect = set_prompt
        result, handles = self.call()
        self.assert_failed(result, "DimensionCleanupFailed")
        self.assertEqual(set(handles), {"width", "height"})
        self.assertEqual(
            result["warnings"][0]["code"], "dimension-preference-restore-failed"
        )

    def test_annotation_failure_exits_own_edit_without_claiming_size_mutation(self):
        with mock.patch.object(
            rectangles,
            "_annotation_location",
            side_effect=RuntimeError("bad transform"),
        ):
            result, handles = self.call()
        self.assert_failed(result, "RuntimeError")
        self.assertEqual(handles, {})
        self.assertNotIn("modification_may_have_happened", result)
        self.assertIsNone(self.manager.ActiveSketch)
        self.assertTrue(self.preference)


if __name__ == "__main__":
    unittest.main()
