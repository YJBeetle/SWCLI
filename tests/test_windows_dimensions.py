import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_dimensions as dimensions


class DiameterCreationTests(unittest.TestCase):
    def setUp(self):
        self.radius = 0.005
        self.arc = SimpleNamespace(
            ConstructionGeometry=False,
            GetType=lambda: 1,
            IsCircle=lambda: 1,
            GetRadius=lambda: self.radius,
            GetCenterPoint2=lambda: SimpleNamespace(X=0.003, Y=0.004, Z=0.0),
            Select4=mock.Mock(return_value=True),
        )
        self.sketch = SimpleNamespace(
            GetSketchSegments=lambda: (self.arc,),
            GetConstrainedStatus=lambda: 2,
        )
        self.feature = SimpleNamespace(
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda: self.sketch,
            GetOwnerFeature=lambda: None,
            GetNextFeature=lambda: None,
            GetFirstDisplayDimension=lambda: None,
            Select2=mock.Mock(return_value=True),
        )
        self.manager = SimpleNamespace(ActiveSketch=None)
        self.manager.InsertSketch = mock.Mock(side_effect=self.exit_edit)
        self.dimension = SimpleNamespace(
            DrivenState=2,
            ReadOnly=False,
            FullName="D1@renamed-sketch@part.Part",
            GetSystemValue2=lambda name: self.radius * 2,
            SetSystemValue3=mock.Mock(side_effect=self.set_value),
        )
        self.edit_call = mock.Mock(side_effect=self.enter_edit)
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            SketchManager=self.manager,
            ClearSelection2=mock.Mock(),
            EditSketch=lambda: self.edit_call(),
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="Default")
            ),
            AddDiameterDimension2=mock.Mock(
                return_value=SimpleNamespace(GetDimension2=lambda index: self.dimension)
            ),
        )
        self.preference = True
        self.app = SimpleNamespace(
            IsSame=lambda a, b: int(a is b),
            GetUserPreferenceToggle=lambda flag: self.preference,
            SetUserPreferenceToggle=mock.Mock(side_effect=self.set_preference),
        )
        self.patchers = [
            mock.patch.object(
                dimensions, "_variant", side_effect=lambda kind, value: (kind, value)
            ),
            mock.patch.object(
                dimensions, "_annotation_location", return_value=(0.01, 0.02, 0.0)
            ),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def enter_edit(self):
        self.manager.ActiveSketch = self.sketch

    def exit_edit(self, update):
        self.manager.ActiveSketch = None

    def set_value(self, value, configuration, names):
        self.radius = value / 2
        return 0

    def set_preference(self, flag, value):
        self.preference = value
        return True

    def call(self, diameter=16):
        return dimensions.create_circle_diameter_windows_with_handle(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature,
            diameter_mm=diameter,
        )

    def test_actual_driving_value_geometry_and_exact_handle_with_cleanup(self):
        result, handle = self.call()
        self.assertTrue(result["ok"], result)
        self.assertIs(handle, self.dimension)
        self.assertEqual(result["dimension"]["value"], 16)
        self.assertEqual(result["dimension"]["configuration"], "Default")
        self.assertTrue(result["geometry_verification"]["passed"])
        self.dimension.SetSystemValue3.assert_called_once_with(
            0.016, 1, ("empty", None)
        )
        self.arc.Select4.assert_called_once_with(False, ("dispatch", None))
        self.assertTrue(self.preference)
        self.assertIsNone(self.manager.ActiveSketch)

    def test_invalid_input_does_not_select_or_edit(self):
        for value in (0, -1, True, None, "16", math.nan, math.inf, 5e-324, 10**1000):
            with self.subTest(value=str(value)[:20]):
                result, handle = self.call(value)
                self.assertEqual(result["error"]["type"], "InvalidArgument")
                self.assertIsNone(handle)
        self.document.ClearSelection2.assert_not_called()
        self.edit_call.assert_not_called()

    def test_non_part_existing_edit_and_stale_or_consumed_sketch_are_rejected(self):
        for setup, expected in (
            (
                lambda: setattr(self.document, "GetType", lambda: 2),
                "UnsupportedDocumentType",
            ),
            (
                lambda: setattr(self.manager, "ActiveSketch", object()),
                "SketchEditInProgress",
            ),
            (
                lambda: setattr(self.document, "FirstFeature", lambda: None),
                "SketchUnavailable",
            ),
            (
                lambda: setattr(self.feature, "GetOwnerFeature", lambda: object()),
                "SketchUnavailable",
            ),
        ):
            with self.subTest(expected=expected):
                self.setUp()
                setup()
                result, _ = self.call()
                self.assertEqual(result["error"]["type"], expected)
                self.document.ClearSelection2.assert_not_called()

    def test_partial_construction_multiple_or_already_dimensioned_profiles_are_rejected(
        self,
    ):
        for setup, expected in (
            (
                lambda: setattr(self.arc, "IsCircle", lambda: 0),
                "UnsupportedDimensionProfile",
            ),
            (
                lambda: setattr(self.arc, "ConstructionGeometry", True),
                "UnsupportedDimensionProfile",
            ),
            (
                lambda: setattr(
                    self.sketch, "GetSketchSegments", lambda: (self.arc, self.arc)
                ),
                "UnsupportedDimensionProfile",
            ),
            (
                lambda: setattr(
                    self.feature, "GetFirstDisplayDimension", lambda: object()
                ),
                "SketchAlreadyDimensioned",
            ),
        ):
            with self.subTest(expected=expected):
                self.setUp()
                setup()
                result, _ = self.call()
                self.assertEqual(result["error"]["type"], expected)
                self.edit_call.assert_not_called()

    def test_selection_failure_does_not_change_preference(self):
        self.arc.Select4.return_value = False
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "SketchSelectionFailed")
        self.assertIsNone(handle)
        self.assertIsNone(self.manager.ActiveSketch)
        self.app.SetUserPreferenceToggle.assert_not_called()

    def test_creation_failure_restores_preference_and_exits_our_edit(self):
        self.document.AddDiameterDimension2.side_effect = RuntimeError(
            "creation failed"
        )
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertIsNone(handle)
        self.assertTrue(self.preference)
        self.assertIsNone(self.manager.ActiveSketch)

    def test_driven_or_read_only_dimension_is_not_overridden(self):
        for field, value in (("DrivenState", 1), ("ReadOnly", True)):
            with self.subTest(field=field):
                self.setUp()
                setattr(self.dimension, field, value)
                result, handle = self.call()
                self.assertEqual(result["error"]["type"], "DimensionNotDriving")
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_not_called()
                self.assertIsNone(self.manager.ActiveSketch)
                self.assertTrue(self.preference)

    def test_native_set_failure_retains_partial_handle_and_native_code(self):
        self.dimension.SetSystemValue3.side_effect = None
        self.dimension.SetSystemValue3.return_value = 3
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "DimensionSetFailed")
        self.assertEqual(result["native_status"], 3)
        self.assertIs(handle, self.dimension)
        self.assertIsNone(self.manager.ActiveSketch)

    def test_false_success_value_and_geometry_are_checked_independently(self):
        self.dimension.GetSystemValue2 = lambda name: 0.020
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "DimensionVerificationFailed")
        self.assertIs(handle, self.dimension)
        self.setUp()
        self.dimension.SetSystemValue3.side_effect = lambda *args: 0
        self.dimension.GetSystemValue2 = lambda name: 0.016
        result, _ = self.call()
        self.assertEqual(result["error"]["type"], "DimensionVerificationFailed")
        self.assertFalse(result["geometry_verification"]["passed"])

    def test_nonfinite_native_value_is_not_leaked_to_wire_json(self):
        self.dimension.GetSystemValue2 = lambda name: math.nan
        result, _ = self.call()
        self.assertEqual(result["error"]["type"], "DimensionVerificationFailed")
        self.assertIsNone(result["dimension"]["value"])

    def test_preference_restoration_failure_reports_warning(self):
        def restore_failure(flag, value):
            if value:
                raise RuntimeError("cannot restore")
            self.preference = value
            return True

        self.app.SetUserPreferenceToggle.side_effect = restore_failure
        result, _ = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["warnings"][0]["code"], "dimension-preference-restore-failed"
        )

    def test_rejected_prompt_suppression_never_creates_a_modal_dimension(self):
        self.app.SetUserPreferenceToggle.side_effect = None
        self.app.SetUserPreferenceToggle.return_value = False
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertIsNone(handle)
        self.document.AddDiameterDimension2.assert_not_called()
        self.assertIsNone(self.manager.ActiveSketch)

    def test_silent_preference_restore_failure_is_reported(self):
        def restore_rejected(flag, value):
            if value:
                return False
            self.preference = False
            return True

        self.app.SetUserPreferenceToggle.side_effect = restore_rejected
        result, _ = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["warnings"][0]["code"], "dimension-preference-restore-failed"
        )

    def test_void_native_setter_is_verified_by_preference_readback(self):
        def native_void(flag, value):
            self.preference = value

        self.app.SetUserPreferenceToggle.side_effect = native_void
        result, _ = self.call()
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.preference)

    def test_cleanup_does_not_close_another_active_sketch(self):
        unrelated = object()
        self.edit_call.side_effect = lambda: setattr(
            self.manager, "ActiveSketch", unrelated
        )
        result, _ = self.call()
        self.assertFalse(result["ok"])
        self.assertIs(self.manager.ActiveSketch, unrelated)
        self.manager.InsertSketch.assert_not_called()
        self.assertTrue(result["editing"])
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")

    def test_cleanup_checks_that_the_owned_edit_really_closed(self):
        self.document.AddDiameterDimension2.side_effect = RuntimeError(
            "creation failed"
        )
        self.manager.InsertSketch.side_effect = None
        result, _ = self.call()
        self.assertTrue(result["editing"])
        self.assertIs(self.manager.ActiveSketch, self.sketch)
        self.assertTrue(self.preference)
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")


if __name__ == "__main__":
    unittest.main()
