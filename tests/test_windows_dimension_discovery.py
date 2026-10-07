"""Portable proof of read-only, exact-owner diameter discovery boundaries."""

import json
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_dimension_discovery as discovery


class Native:
    def __init__(self, *, identity=None):
        self.identity = identity if identity is not None else object()


class Feature(Native):
    def __init__(self, native_id, *, sketch=None, identity=None):
        super().__init__(identity=identity)
        self.native_id, self.sketch = native_id, sketch
        self.next_root = self.next_sub = self.subfeature = self.first_display = None
        self.id_reads = 0

    @property
    def Name(self):
        raise AssertionError("feature names must not locate an exact native profile")

    def GetID(self):
        self.id_reads += 1
        return self.native_id

    def GetTypeName2(self):
        return "ProfileFeature" if self.sketch is not None else "BossExtrude"

    def GetSpecificFeature2(self):
        return self.sketch

    def GetNextFeature(self):
        return self.next_root

    def GetFirstSubFeature(self):
        return self.subfeature

    def GetNextSubFeature(self):
        return self.next_sub

    def GetFirstDisplayDimension(self):
        return self.first_display

    def GetNextDisplayDimension(self, display):
        return display.next


class Dimension(Native):
    def __init__(self, owner, *, identity=None):
        super().__init__(identity=identity)
        self.owner = owner
        self.value = 0.02
        self.kind = 0
        self.DrivenState = 2
        self.ReadOnly = False
        self.FullName = "D1@renamed-sketch@part.Part"
        self.table_controlled = False
        self.GetSystemValue2 = mock.Mock(side_effect=lambda name: self.value)
        self.SetSystemValue3 = mock.Mock(side_effect=AssertionError("must not set"))

    def GetType(self):
        return self.kind

    def GetFeatureOwner(self):
        return self.owner

    def IsDesignTableDimension(self):
        return self.table_controlled


class Display(Native):
    def __init__(self, dimension, *, kind=6, identity=None):
        super().__init__(identity=identity)
        self.dimension = dimension
        self.Type2 = kind
        self.next = None
        self.GetDimension2 = mock.Mock(side_effect=self.get_dimension)

    def get_dimension(self, index):
        if index != 0:
            raise AssertionError("a circle diameter has one native dimension")
        return self.dimension


class ComError(Exception):
    def __init__(self, hresult):
        self.hresult = hresult
        super().__init__(hresult)


class CircleDiameterDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.radius = 0.01
        self.arc = SimpleNamespace(
            ConstructionGeometry=False,
            GetType=lambda: 1,
            IsCircle=lambda: 1,
            GetRadius=lambda: self.radius,
            GetCenterPoint2=lambda: SimpleNamespace(X=0.003, Y=0.004, Z=0),
        )
        self.sketch = Native()
        self.sketch.GetSketchSegments = lambda: (self.arc,)
        self.sketch.GetConstrainedStatus = lambda: 2
        self.feature = Feature(73, sketch=self.sketch)
        self.dimension = Dimension(self.feature)
        self.display = Display(self.dimension)
        self.feature.first_display = self.display
        self.configuration = SimpleNamespace(Name="Current")
        self.manager = SimpleNamespace(ActiveSketch=None)
        self.equations = []
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            GetUpdateStamp=lambda: 147,
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=self.configuration
            ),
            SketchManager=self.manager,
            GetEquationMgr=lambda: SimpleNamespace(
                GetCount=lambda: len(self.equations),
                Equation=lambda index: self.equations[index],
            ),
            modified=False,
            read_only=True,
        )
        self.foreground = Native()
        self.app = SimpleNamespace(
            ActiveDoc=self.foreground,
            IsSame=mock.Mock(side_effect=lambda a, b: int(a.identity is b.identity)),
        )
        self.mutations = [self.dimension.SetSystemValue3]
        for obj, methods in (
            (self.app, ("ActivateDoc3", "SetUserPreferenceToggle")),
            (
                self.document,
                (
                    "ClearSelection2",
                    "EditSketch",
                    "EditRebuild3",
                    "SetUserPreferenceToggle",
                    "ShowFeatureDimensions",
                ),
            ),
            (self.manager, ("InsertSketch",)),
            (self.feature, ("Select2",)),
            (self.arc, ("Select4",)),
        ):
            for method in methods:
                mutation = mock.Mock(side_effect=AssertionError(f"must not {method}"))
                setattr(obj, method, mutation)
                self.mutations.append(mutation)

    def call(self, feature=None):
        result, native = discovery.discover_circle_diameter_windows_with_handle(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature if feature is None else feature,
        )
        json.dumps(result, allow_nan=False)
        for mutation in self.mutations:
            mutation.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.assertFalse(self.document.modified)
        self.assertTrue(self.document.read_only)
        return result, native

    def assert_failure(self, expected=None, feature=None):
        result, handle = self.call(feature)
        self.assertFalse(result["ok"], result)
        self.assertIsNone(handle)
        if expected is not None:
            self.assertEqual(result["error"]["type"], expected, result)
        return result

    def test_exact_current_configuration_diameter_is_observed_without_mutation(self):
        result, native = self.call()
        self.assertTrue(result["ok"], result)
        self.assertIs(native, self.dimension)
        self.assertEqual(result["dimension"]["value"], 20)
        self.assertEqual(result["dimension"]["configuration"], "Current")
        self.assertEqual(result["dimension"]["native_name"], self.dimension.FullName)
        self.assertTrue(result["geometry_verification"]["passed"])
        self.assertEqual(result["constraint_status"], 2)
        self.assertFalse(result["editing"])
        self.assertFalse(result["equation_control"]["controlled"])
        self.assertFalse(result["design_table_controlled"])
        self.assertTrue(result["observation"]["unchanged"])
        self.assertEqual(
            result["observation"]["before"], result["observation"]["after"]
        )
        self.dimension.GetSystemValue2.assert_called_once_with("Current")

    def test_absorbed_profile_under_another_root_is_supported(self):
        parent = Feature(99)
        parent.subfeature = self.feature
        self.document.FirstFeature = lambda: parent
        wrapper = Feature(73, sketch=self.sketch, identity=self.feature.identity)
        result, native = self.call(wrapper)
        self.assertTrue(result["ok"], result)
        self.assertIs(native, self.dimension)
        self.assertGreater(parent.id_reads, 0)

    def test_duplicate_presentations_of_same_native_parameter_return_one_handle(self):
        wrapper = Dimension(self.feature, identity=self.dimension.identity)
        self.display.next = Display(wrapper)
        result, native = self.call()
        self.assertTrue(result["ok"], result)
        self.assertIs(native, self.dimension)
        self.dimension.GetSystemValue2.assert_called_once()
        wrapper.GetSystemValue2.assert_not_called()

    def test_distinct_native_parameters_with_same_name_are_ambiguous(self):
        second = Dimension(self.feature)
        second.FullName = self.dimension.FullName
        self.display.next = Display(second)
        self.assert_failure("DimensionAmbiguous")

    def test_hidden_or_unloaded_null_chain_does_not_claim_absent_dimensions(self):
        self.feature.first_display = None
        result = self.assert_failure("DimensionObservationUnavailable")
        self.assertIn("hidden or unloaded persisted", result["error"]["message"])
        self.assertNotIn("dimension", result)
        self.dimension.GetSystemValue2.assert_not_called()

    def test_nonempty_complete_chain_without_diameter_is_only_observed_not_found(self):
        self.display.Type2 = 5
        result = self.assert_failure("DimensionNotFound")
        self.assertIn("observable", result["error"]["message"])
        self.assertIn("persisted", result["error"]["message"])
        self.display.GetDimension2.assert_not_called()

    def test_unsupported_or_absent_native_parameter_is_not_discovered(self):
        for kind in (1, None, True, 0.5, "0"):
            with self.subTest(kind=kind):
                self.dimension.kind = kind
                self.assert_failure("DimensionObservationUnavailable")
        self.display.dimension = None
        self.assert_failure("DimensionObservationUnavailable")

    def test_missing_or_mismatched_exact_owner_is_rejected(self):
        for owner in (None, Feature(73, sketch=self.sketch)):
            with self.subTest(owner=owner):
                self.dimension.owner = owner
                self.assert_failure("DimensionVerificationFailed")

    def test_invalid_or_nonmatching_value_is_rejected_without_native_handle(self):
        for value in (0, -0.02, 0.01, 0.021, math.nan, math.inf):
            with self.subTest(value=value):
                self.dimension.value = value
                self.assert_failure("DimensionVerificationFailed")

    def test_busy_and_unreadable_native_value_fail_closed(self):
        for error in (ComError(0x80010001), RuntimeError("unreadable value")):
            with self.subTest(error=error):
                self.dimension.GetSystemValue2.side_effect = error
                self.assert_failure(type(error).__name__)

    def test_unsupported_circle_or_nonpart_does_not_publish_handle(self):
        for member, value in (
            ("ConstructionGeometry", True),
            ("IsCircle", lambda: 0),
            ("GetType", lambda: 0),
        ):
            with self.subTest(member=member):
                original = getattr(self.arc, member)
                setattr(self.arc, member, value)
                self.assert_failure("UnsupportedDimensionProfile")
                setattr(self.arc, member, original)
        self.sketch.GetSketchSegments = lambda: (self.arc, self.arc)
        self.assert_failure("UnsupportedDimensionProfile")
        self.document.GetType = lambda: 2
        self.assert_failure("UnsupportedDocumentType")

    def test_exact_native_feature_not_its_id_or_name_selects_target(self):
        wrapper = Feature(73, sketch=self.sketch)
        self.assert_failure("SketchUnavailable", wrapper)
        absent = Feature(999, sketch=self.sketch)
        self.assert_failure("SketchUnavailable", absent)
        self.feature.GetTypeName2 = lambda: "3DProfileFeature"
        self.assert_failure("SketchUnavailable")

    def test_matching_early_profile_does_not_hide_later_feature_cycle(self):
        later = Feature(99)
        self.feature.next_root = later
        later.next_root = later
        self.assert_failure("SketchTraversalCycle")
        self.dimension.GetSystemValue2.assert_not_called()

    def test_complete_feature_scan_rejects_later_duplicate_native_id_conflict(self):
        self.feature.next_root = Feature(73)
        self.assert_failure("SketchFeatureIdConflict")
        self.dimension.GetSystemValue2.assert_not_called()

    def test_later_unreadable_feature_is_not_skipped_after_target_match(self):
        later = Feature(99)
        read = mock.Mock(side_effect=RuntimeError("later feature"))
        later.GetNextFeature = lambda: read()
        self.feature.next_root = later
        result = self.assert_failure("RuntimeError")
        self.assertEqual(result["error"]["message"], "later feature")
        read.assert_called_once()
        self.dimension.GetSystemValue2.assert_not_called()

    def test_display_cycle_or_limit_is_not_partial_success(self):
        self.display.next = self.display
        self.assert_failure("DimensionObservationUnavailable")
        self.dimension.GetSystemValue2.assert_not_called()
        self.display.next = Display(self.dimension)
        self.display.next.next = Display(self.dimension)
        with mock.patch.object(discovery, "_DISPLAY_LIMIT", 2):
            self.assert_failure("DimensionObservationUnavailable")
        self.dimension.GetSystemValue2.assert_not_called()

    def test_unreadable_later_display_is_not_skipped_after_valid_candidate(self):
        self.display.next = Display(self.dimension)
        self.feature.GetNextDisplayDimension = mock.Mock(
            side_effect=[self.display.next, RuntimeError("later display")]
        )
        self.assert_failure("RuntimeError")
        self.dimension.GetSystemValue2.assert_not_called()

    def test_busy_unknown_and_invalid_identity_results_are_not_success(self):
        for error in (ComError(0x80010001), ComError(0x80004005)):
            with self.subTest(error=error):
                self.app.IsSame.side_effect = error
                self.assert_failure("ComError")
        self.app.IsSame.side_effect = None
        for value in (-1, 2, None, True, 1.5, "1"):
            with self.subTest(value=value):
                self.app.IsSame.return_value = value
                self.assert_failure("DimensionObservationUnavailable")

    def test_unreadable_display_type_and_constraint_status_fail_closed(self):
        self.display.Type2 = None
        self.assert_failure("DimensionObservationUnavailable")
        self.display.Type2 = 6
        self.sketch.GetConstrainedStatus = lambda: True
        self.assert_failure("DimensionObservationUnavailable")

    def test_changed_stamp_or_configuration_withholds_otherwise_valid_handle(self):
        read = mock.Mock(side_effect=[147, 148])
        self.document.GetUpdateStamp = lambda: read()
        result = self.assert_failure("DimensionObservationUnavailable")
        self.assertFalse(result["observation"]["unchanged"])
        self.assertIn("dimension", result)
        self.assertEqual(read.call_count, 2)
        self.document.GetUpdateStamp = lambda: 147

        def changed_config(name):
            self.configuration.Name = "Other"
            return self.dimension.value

        self.dimension.GetSystemValue2.side_effect = changed_config
        result = self.assert_failure("DimensionObservationUnavailable")
        self.assertEqual(result["observation"]["before"]["configuration"], "Current")
        self.assertEqual(result["observation"]["after"]["configuration"], "Other")

    def test_existing_edit_remains_readonly_but_replaced_edit_object_is_rejected(self):
        old_edit = Native()
        self.manager.ActiveSketch = old_edit
        result, native = self.call()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["editing"])
        self.assertIs(native, self.dimension)
        self.assertIs(self.manager.ActiveSketch, old_edit)

        def replaced_edit(name):
            self.manager.ActiveSketch = Native()
            return self.dimension.value

        self.dimension.GetSystemValue2.side_effect = replaced_edit
        result = self.assert_failure("DimensionObservationUnavailable")
        self.assertTrue(result["observation"]["before"]["editing"])
        self.assertTrue(result["observation"]["after"]["editing"])
        self.assertFalse(result["observation"]["unchanged"])

    def test_entering_edit_during_discovery_is_rejected_without_exiting_that_edit(self):
        def entered_edit(name):
            self.manager.ActiveSketch = self.sketch
            return self.dimension.value

        self.dimension.GetSystemValue2.side_effect = entered_edit
        self.assert_failure("DimensionObservationUnavailable")
        self.assertIs(self.manager.ActiveSketch, self.sketch)

    def test_invalid_before_stamp_and_failed_after_check_do_not_fake_stability(self):
        for value in (None, True, 1.5, "147"):
            with self.subTest(value=value):
                self.document.GetUpdateStamp = lambda: value
                self.assert_failure("DimensionObservationUnavailable")
        self.feature.first_display = None
        read = mock.Mock(side_effect=[147, ComError(0x80010001)])
        self.document.GetUpdateStamp = lambda: read()
        result = self.assert_failure("DimensionObservationUnavailable")
        self.assertIn("display chain is empty", result["error"]["message"])
        self.assertEqual(
            result["warnings"][0]["code"], "dimension-discovery-state-check-failed"
        )
        self.assertFalse(result["observation"]["unchanged"])

    def test_equation_design_table_and_driven_readonly_state_is_only_observed(self):
        self.dimension.DrivenState = 1
        self.dimension.ReadOnly = True
        self.dimension.table_controlled = True
        self.equations = ['"D1@renamed-sketch" = 20mm']
        result, native = self.call()
        self.assertTrue(result["ok"], result)
        self.assertIs(native, self.dimension)
        self.assertEqual(result["dimension"]["driven_state"], 1)
        self.assertTrue(result["dimension"]["read_only"])
        self.assertTrue(result["design_table_controlled"])
        self.assertEqual(
            result["equation_control"], {"controlled": True, "equation_indices": [0]}
        )

    def test_native_readonly_integer_boolean_binding_is_observed_precisely(self):
        for value, expected in ((0, False), (1, True), (-1, True)):
            with self.subTest(value=value):
                self.dimension.ReadOnly = value
                result, native = self.call()
                self.assertTrue(result["ok"], result)
                self.assertIs(native, self.dimension)
                self.assertIs(result["dimension"]["read_only"], expected)

    def test_unreadable_control_metadata_is_not_coerced_into_normal_status(self):
        for member, values in (
            ("ReadOnly", (None, 2, -2, 0.0, 1.0, "false")),
            ("DrivenState", (None, True, 2.9, "2", 3)),
            ("FullName", (None, 0, "", " ")),
            ("table_controlled", (None, 0, 1, "false")),
        ):
            original = getattr(self.dimension, member)
            for value in values:
                with self.subTest(member=member, value=value):
                    setattr(self.dimension, member, value)
                    self.assert_failure("DimensionObservationUnavailable")
            setattr(self.dimension, member, original)

    def test_documented_unknown_driven_enum_is_not_claimed_to_be_driving(self):
        self.dimension.DrivenState = 0
        result, native = self.call()
        self.assertTrue(result["ok"], result)
        self.assertIs(native, self.dimension)
        self.assertEqual(result["dimension"]["driven_state"], 0)

    def test_configuration_aba_cannot_publish_another_configuration_observation(self):
        def other_configuration_display():
            self.configuration.Name = "Other"
            return self.display

        def restore_configuration(name):
            self.configuration.Name = "Current"
            return self.dimension.value

        self.feature.GetFirstDisplayDimension = other_configuration_display
        self.dimension.GetSystemValue2.side_effect = restore_configuration
        result = self.assert_failure("DimensionObservationUnavailable")
        self.assertIn("initial current configuration", result["error"]["message"])
        self.assertEqual(result["observation"]["before"]["configuration"], "Current")
        self.assertEqual(result["observation"]["after"]["configuration"], "Current")
        self.assertFalse(result["observation"]["configuration_matched"])
        self.assertFalse(result["observation"]["unchanged"])
        self.dimension.GetSystemValue2.assert_called_once_with("Other")

    def test_nonnumeric_diameter_value_is_not_coerced_to_length(self):
        for value in (None, True, "0.02"):
            with self.subTest(value=value):
                self.dimension.value = value
                self.assert_failure("DimensionObservationUnavailable")

    def test_geometry_change_cannot_hide_behind_unchanged_stamp(self):
        def changed_circle(name):
            self.radius = 0.009
            return self.dimension.value

        self.dimension.GetSystemValue2.side_effect = changed_circle
        result = self.assert_failure("DimensionVerificationFailed")
        self.assertFalse(result["geometry_verification"]["passed"])


if __name__ == "__main__":
    unittest.main()
