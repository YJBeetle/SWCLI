"""Read-only internal rectangle inspection never borrows diameter semantics."""

import json
import math
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_linear_dimensions as linear


class Native:
    def __init__(self, identity=None):
        self.identity = identity if identity is not None else object()


class RectangleInspectionTests(unittest.TestCase):
    def setUp(self):
        self.feature, self.sketch = Native(), Native()
        self.width, self.height = 40, 30
        self.sketch.GetSketchSegments = lambda: tuple(self.edge(i) for i in range(4))
        self.sketch.GetConstrainedStatus = lambda: 3
        self.feature.GetID = lambda: 17
        self.feature.GetTypeName2 = lambda: "ProfileFeature"
        self.feature.GetSpecificFeature2 = lambda: self.sketch
        self.feature.GetNextFeature = self.feature.GetFirstSubFeature = lambda: None
        self.feature.GetNextSubFeature = lambda: None
        self.parameters, self.displays = {}, []
        for kind, native_type, value in (("width", 11, 0.04), ("height", 12, 0.03)):
            native = Native()
            native.GetFeatureOwner = lambda: self.feature
            native.GetType = lambda: 0
            native.DrivenState, native.ReadOnly = 2, 0
            native.FullName = f"{kind}@renamed-sketch@part.Part"
            native.value = value
            native.GetSystemValue2 = mock.Mock(
                side_effect=lambda config, n=native: n.value
            )
            native.IsDesignTableDimension = lambda: False
            self.parameters[kind] = native
            self.displays.append(self.display(native, native_type))
        self.feature.GetFirstDisplayDimension = lambda: (
            self.displays[0] if self.displays else None
        )
        self.feature.GetNextDisplayDimension = lambda d: self.next_display(d)
        self.config = SimpleNamespace(Name="Current")
        self.stamp, self.equations = 10, []
        self.manager = SimpleNamespace(ActiveSketch=None)
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            GetUpdateStamp=lambda: self.stamp,
            ConfigurationManager=SimpleNamespace(ActiveConfiguration=self.config),
            SketchManager=self.manager,
            GetEquationMgr=lambda: SimpleNamespace(
                GetCount=lambda: len(self.equations),
                Equation=lambda i: self.equations[i],
            ),
        )
        self.foreground = object()
        self.app = SimpleNamespace(
            ActiveDoc=self.foreground,
            IsSame=mock.Mock(side_effect=lambda a, b: int(a.identity is b.identity)),
        )
        self.mutations = []
        for obj, methods in (
            (self.app, ("ActivateDoc3", "SetUserPreferenceToggle")),
            (
                self.document,
                (
                    "ClearSelection2",
                    "EditSketch",
                    "EditRebuild3",
                    "ShowFeatureDimensions",
                ),
            ),
            (self.manager, ("InsertSketch",)),
            (self.feature, ("Select2",)),
            *((n, ("SetSystemValue3",)) for n in self.parameters.values()),
        ):
            for name in methods:
                setter = mock.Mock(side_effect=AssertionError(f"must not {name}"))
                setattr(obj, name, setter)
                self.mutations.append(setter)

    def point(self, index):
        x, y = ((-1, -1), (1, -1), (1, 1), (-1, 1))[index]
        return SimpleNamespace(
            X=(3 + x * self.width / 2) / 1000, Y=(4 + y * self.height / 2) / 1000, Z=0
        )

    def edge(self, index):
        return SimpleNamespace(
            ConstructionGeometry=False,
            GetType=lambda: 0,
            GetStartPoint2=lambda: self.point(index),
            GetEndPoint2=lambda: self.point((index + 1) % 4),
        )

    def display(self, native, native_type):
        display = Native()
        display.Type2 = native_type
        display.GetDimension2 = lambda index: native
        return display

    def next_display(self, display):
        index = self.displays.index(display) + 1
        return self.displays[index] if index < len(self.displays) else None

    def call(self, kind="width", *, dimension=None, feature=None):
        result = linear.inspect_rectangle_dimension_windows(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature if feature is None else feature,
            dimension=(
                self.parameters["width" if kind not in ("width", "height") else kind]
                if dimension is None
                else dimension
            ),
            kind=kind,
        )
        json.dumps(result, allow_nan=False)
        for mutation in self.mutations:
            mutation.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.foreground)
        return result

    def failed(self, code, **kwargs):
        result = self.call(**kwargs)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], code, result)
        return result

    def test_width_height_use_explicit_native_role_and_independent_rectangle_geometry(
        self,
    ):
        for kind, value in (("width", 40), ("height", 30)):
            result = self.call(kind)
            self.assertTrue(result["ok"], result)
            self.assertEqual(
                (result["dimension"]["kind"], result["dimension"]["value"]),
                (kind, value),
            )
            self.assertTrue(result["geometry_verification"]["passed"])
            self.assertEqual(
                result["geometry_verification"]["actual_center_mm"],
                {"x": 3, "y": 4, "z": 0},
            )
            self.assertEqual(
                result["observation"]["before"], result["observation"]["after"]
            )
            self.assertTrue(result["observation"]["unchanged"])
            self.assertFalse(result["editing"])
            self.parameters[kind].GetSystemValue2.assert_called_once_with("Current")

    def test_invalid_role_is_rejected_before_reading_com(self):
        with mock.patch.object(linear, "_integer") as read:
            for kind in ("diameter", "radius", None, True, [], ""):
                self.failed("InvalidArgument", kind=kind)
            read.assert_not_called()

    def test_nonpart_and_absent_native_dimension_are_rejected(self):
        self.document.GetType = lambda: 2
        self.failed("UnsupportedDocumentType")
        self.document.GetType = lambda: 1
        result = linear.inspect_rectangle_dimension_windows(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature,
            dimension=None,
            kind="width",
        )
        self.assertEqual(result["error"]["type"], "DimensionUnavailable")

    def test_absorbed_profile_is_resolved_without_activation(self):
        boss = Native()
        boss.GetID, boss.GetTypeName2 = lambda: 27, lambda: "BossExtrude"
        boss.GetFirstSubFeature = lambda: self.feature
        boss.GetNextFeature = boss.GetNextSubFeature = lambda: None
        self.document.FirstFeature = lambda: boss
        self.assertTrue(self.call()["ok"])

    def test_stale_feature_or_wrong_owner_never_returns_success(self):
        self.failed("SketchUnavailable", feature=SimpleNamespace(GetID=lambda: 999))
        other = Native()
        self.parameters["width"].GetFeatureOwner = lambda: other
        self.failed("DimensionUnavailable")

    def test_exact_native_wrapper_identity_not_python_identity_selects_parameter(self):
        wrapper = Native(identity=self.parameters["width"].identity)
        self.displays[0].GetDimension2 = lambda index: wrapper
        self.assertTrue(self.call()["ok"])

    def test_native_unsupported_comparison_uses_canonical_identity_only_for_dimensions(
        self,
    ):
        original = self.app.IsSame.side_effect
        native_parameters = tuple(self.parameters.values())
        self.app.IsSame.side_effect = lambda a, b: (
            2 if a in native_parameters and b in native_parameters else original(a, b)
        )
        with mock.patch(
            "swcli.hosts.windows_dimension_identity._query_iunknown",
            side_effect=lambda n: n.identity,
        ):
            self.assertTrue(self.call()["ok"])

    def test_qi_failure_does_not_hide_unavailable_identity(self):
        original = self.app.IsSame.side_effect
        self.app.IsSame.side_effect = lambda a, b: (
            2 if b is self.parameters["width"] else original(a, b)
        )
        with mock.patch(
            "swcli.hosts.windows_dimension_identity._query_iunknown",
            side_effect=RuntimeError("QI unavailable"),
        ):
            self.failed("DimensionObservationUnavailable")

    def test_native_parameter_and_display_types_are_strict(self):
        for value in (1, None, True, 0.0, "0"):
            self.parameters["width"].GetType = lambda v=value: v
            self.failed(
                "DimensionVerificationFailed"
                if value == 1 and not isinstance(value, bool)
                else "DimensionObservationUnavailable"
            )
        self.parameters["width"].GetType = lambda: 0
        for value in (12, 6, None, True, 11.0, "11"):
            self.displays[0].Type2 = value
            self.failed(
                "DimensionVerificationFailed"
                if type(value) is int
                else "DimensionObservationUnavailable"
            )

    def test_empty_chain_or_removed_exact_native_parameter_never_guesses_by_value(self):
        self.displays = []
        self.failed("DimensionObservationUnavailable")
        unrelated = Native()
        self.displays = [self.display(unrelated, 11)]
        self.failed("DimensionUnavailable")

    def test_later_cycle_is_not_hidden_by_first_matching_display(self):
        self.feature.GetNextDisplayDimension = lambda d: self.displays[0]
        self.failed("DimensionObservationUnavailable")

    def test_later_unreadable_parameter_is_not_hidden_by_first_match(self):
        self.displays[1].GetDimension2 = lambda index: None
        self.failed("DimensionObservationUnavailable")

    def test_duplicate_same_role_presentations_are_observed_but_conflicting_roles_fail(
        self,
    ):
        self.displays.append(self.display(self.parameters["width"], 11))
        self.assertTrue(self.call()["ok"])
        self.displays[-1].Type2 = 12
        self.failed("DimensionVerificationFailed")

    def test_geometry_mismatch_is_reported_without_fixing_parameter_or_profile(self):
        self.parameters["width"].value = 0.05
        result = self.call()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["geometry_verification"]["passed"])
        self.assertEqual(result["geometry_verification"]["actual_width_mm"], 40)
        self.assertEqual(result["dimension"]["value"], 50)

    def test_nonrectangle_topology_fails_instead_of_accepting_only_bounds(self):
        self.sketch.GetSketchSegments = lambda: tuple(self.edge(0) for _ in range(4))
        self.failed("UnsupportedDimensionProfile")

    def test_driven_readonly_equation_and_table_controls_are_observed_not_overwritten(
        self,
    ):
        self.parameters["width"].DrivenState = 1
        self.parameters["width"].ReadOnly = 1
        self.parameters["width"].IsDesignTableDimension = lambda: True
        self.equations = ['"width@renamed-sketch" = 40']
        result = self.call()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["dimension"]["driven_state"], 1)
        self.assertTrue(result["dimension"]["read_only"])
        self.assertTrue(result["equation_control"]["controlled"])
        self.assertTrue(result["design_table_controlled"])

    def test_invalid_native_control_metadata_is_not_coerced_to_writable(self):
        for name, value in (
            ("ReadOnly", None),
            ("ReadOnly", "0"),
            ("DrivenState", True),
            ("DrivenState", 3),
        ):
            native = self.parameters["width"]
            old = getattr(native, name)
            setattr(native, name, value)
            self.failed("DimensionObservationUnavailable")
            setattr(native, name, old)
        self.parameters["width"].IsDesignTableDimension = lambda: 0
        self.failed("DimensionObservationUnavailable")

    def test_nonfinite_or_nonpositive_parameter_values_cannot_be_successful_reads(self):
        for value in (None, True, "0.04", 0, -1, math.nan, math.inf, 10**1000):
            self.parameters["width"].value = value
            self.failed("DimensionObservationUnavailable")

    def test_state_stamp_configuration_and_edit_changes_are_fail_closed(self):
        for change in ("stamp", "configuration", "editing"):
            with self.subTest(change=change):
                self.setUp()

                def value(config):
                    if change == "stamp":
                        self.stamp += 1
                    if change == "configuration":
                        self.config.Name = "Other"
                    if change == "editing":
                        self.manager.ActiveSketch = Native()
                    return 0.04

                self.parameters["width"].GetSystemValue2.side_effect = value
                result = self.failed("DimensionObservationUnavailable")
                self.assertFalse(result["observation"]["unchanged"])

    def test_existing_edit_is_observed_without_closing_it_and_switched_edit_is_rejected(
        self,
    ):
        self.manager.ActiveSketch = self.sketch
        result = self.call()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["editing"])

        def value(config):
            self.manager.ActiveSketch = Native()
            return 0.04

        self.parameters["width"].GetSystemValue2.side_effect = value
        self.failed("DimensionObservationUnavailable")

    def test_final_state_check_preserves_primary_failure_with_warning(self):
        self.parameters["width"].GetFeatureOwner = lambda: None
        self.document.GetUpdateStamp = mock.Mock(
            spec=(), side_effect=[10, RuntimeError("lost stamp")]
        )
        result = self.failed("DimensionUnavailable")
        self.assertEqual(
            result["warnings"][0]["code"], "dimension-inspect-state-check-failed"
        )

    def test_invalid_stamp_and_constraint_metadata_are_not_truncated_or_coerced(self):
        self.document.GetUpdateStamp = lambda: 1.5
        self.failed("DimensionObservationUnavailable")
        self.document.GetUpdateStamp = lambda: 10
        self.sketch.GetConstrainedStatus = lambda: True
        self.failed("DimensionObservationUnavailable")


if __name__ == "__main__":
    unittest.main()
