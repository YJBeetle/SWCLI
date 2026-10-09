"""Exact depth-profile/final-body guards never perform CAD mutations."""

from copy import deepcopy
import math
from types import SimpleNamespace
import unittest
from unittest import mock

import test_windows_feature_depth as preflight_tests
from test_windows_rectangle_profiles import line, point
from swcli.hosts.windows_feature_depth_profiles import (
    prepare_profiled_extrusion_depth_edit_windows_with_definition,
)


class DepthProfileGuardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = preflight_tests.FeatureDepthPreflightTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.app, self.document, self.feature = (
            self.fixture.app,
            self.fixture.document,
            self.fixture.feature,
        )
        self.corners = [point(-40, -25), point(60, -25), point(60, 25), point(-40, 25)]
        self.segments = [
            line(self.corners[i], self.corners[(i + 1) % 4]) for i in range(4)
        ]
        self.transform = SimpleNamespace(
            ArrayData=[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        )
        self.sketch = SimpleNamespace(
            GetSketchSegments=lambda: self.segments,
            ModelToSketchTransform=self.transform,
        )
        self.profile = SimpleNamespace(
            identity=object(),
            GetID=lambda: 2,
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda: self.sketch,
            GetOwnerFeature=lambda: self.feature,
            GetNextSubFeature=lambda: None,
            GetFirstSubFeature=lambda: None,
        )
        self.plane = SimpleNamespace(
            identity=object(),
            GetID=lambda: 3,
            GetTypeName2=lambda: "RefPlane",
            GetNextFeature=lambda: None,
            GetFirstSubFeature=lambda: None,
        )
        self.feature.GetFirstSubFeature = lambda: self.profile
        self.feature.GetNextFeature = lambda: self.plane
        self.parents = [self.profile, self.plane]
        self.feature.GetParents = lambda: self.parents
        self.body = SimpleNamespace(GetType=lambda: 0, IsSheetMetal=lambda: False)
        self.bodies = [self.body]
        self.document.GetBodies2 = mock.Mock(side_effect=lambda *args: self.bodies)

    def prepare(self):
        return prepare_profiled_extrusion_depth_edit_windows_with_definition(
            app=self.app, document=self.document, feature=self.feature
        )

    def refused(self, code):
        result, definition = self.prepare()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], code, result)
        self.assertIsNone(definition)
        for key in ("profile", "body", "definition", "controls"):
            self.assertNotIn(key, result)

    def test_rectangle_retains_exact_profile_parent_area_and_transform(self):
        result, definition = self.prepare()
        self.assertTrue(result["ok"], result)
        self.assertIs(definition, self.fixture.definition)
        self.assertEqual(result["profile"]["native_profile_id"], 2)
        self.assertEqual(result["profile"]["native_parent_ids"], [2, 3])
        self.assertEqual(result["profile"]["geometry"]["area_mm2"], 5000)
        self.assertEqual(
            result["profile"]["geometry"]["center_mm"], {"x": 10, "y": 0, "z": 0}
        )
        self.assertEqual(
            result["profile"]["model_to_sketch_transform"], self.transform.ArrayData
        )
        self.assertEqual(
            result["body"],
            {"scope": "final-part-bodies", "solid_body_count": 1, "sheet_metal": False},
        )
        self.assertTrue(result["observation"]["unchanged"])
        self.assertEqual(
            self.document.GetBodies2.call_args_list, [mock.call(-1, False)] * 2
        )

    def test_circle_and_native_cut_flags_are_retained(self):
        self.feature.GetTypeName2 = lambda: "Cut"
        self.segments = [
            SimpleNamespace(
                ConstructionGeometry=False,
                GetType=lambda: 1,
                IsCircle=lambda: 1,
                GetRadius=lambda: 0.003,
                GetCenterPoint2=lambda: point(10, 20),
            )
        ]
        result, definition = self.prepare()
        self.assertTrue(result["ok"], result)
        self.assertIs(definition, self.fixture.definition)
        self.assertEqual(result["profile"]["geometry"]["kind"], "circle")
        self.assertAlmostEqual(result["profile"]["geometry"]["area_mm2"], math.pi * 9)
        self.assertTrue(result["definition"]["feature_scope"])

    def test_parent_array_must_be_complete_bounded_and_nonnull(self):
        for value in (None, (), "parents", {}, (None,), [self.profile] * 1001):
            with self.subTest(value=str(value)[:40]):
                self.parents = value
                self.refused("FeatureObservationUnavailable")

    def test_duplicate_or_foreign_parent_cannot_grant_profile_ownership(self):
        self.parents = [self.profile, self.profile]
        self.refused("FeatureProfileUnavailable")
        foreign = deepcopy(self.profile)
        foreign.identity = object()
        self.parents = [foreign, self.plane]
        self.refused("FeatureProfileUnavailable")
        foreign.GetID = lambda: 123
        self.refused("FeatureProfileUnavailable")

    def test_exactly_one_direct_absorbed_profile_is_required(self):
        self.parents = [self.plane]
        self.refused("UnsupportedDepthProfile")
        self.parents = [self.profile, self.plane]
        self.profile.GetOwnerFeature = lambda: self.plane
        self.refused("FeatureProfileUnavailable")
        self.profile.GetOwnerFeature = lambda: self.feature
        self.profile.GetSpecificFeature2 = lambda: None
        self.refused("FeatureProfileUnavailable")

    def test_two_distinct_live_profile_parents_are_not_ambiguously_chosen(self):
        second = deepcopy(self.profile)
        second.identity = object()
        second.GetID = lambda: 4
        self.profile.GetNextSubFeature = lambda: second
        self.parents = [self.profile, second, self.plane]
        self.refused("UnsupportedDepthProfile")

    def test_missing_extra_surface_multibody_and_sheet_metal_are_refused(self):
        for value, code in (
            (None, "FeatureObservationUnavailable"),
            ([], "FeatureObservationUnavailable"),
            ([None], "FeatureObservationUnavailable"),
            ([self.body, self.body], "UnsupportedDepthBodyScope"),
        ):
            self.bodies = value
            self.refused(code)
        self.bodies = [self.body]
        self.body.GetType = lambda: 1
        self.refused("UnsupportedDepthBodyScope")
        self.body.GetType = lambda: 0
        self.body.IsSheetMetal = lambda: True
        self.refused("UnsupportedDepthBodyScope")

    def test_body_type_and_sheet_metal_flags_are_not_truthiness_coerced(self):
        for value in (None, True, "0", 0.0):
            self.body.GetType = lambda: value
            self.refused("FeatureObservationUnavailable")
        self.body.GetType = lambda: 0
        for value in (None, 0, "false"):
            self.body.IsSheetMetal = lambda: value
            self.refused("FeatureObservationUnavailable")

    def test_unknown_open_duplicate_and_nonplanar_profiles_are_refused(self):
        original = self.segments[:]
        self.segments = original[:3]
        self.refused("UnsupportedDepthProfile")
        self.segments = [original[0], original[1], original[2], original[0]]
        self.refused("UnsupportedDepthProfile")
        self.segments = original
        self.corners[0].Z = 0.01
        self.refused("UnsupportedDepthProfile")

    def test_invalid_profile_collections_and_transforms_are_not_published(self):
        for value in (None, (), "segments", [None], self.segments * 17):
            self.sketch.GetSketchSegments = lambda: value
            self.refused("FeatureObservationUnavailable")
        self.sketch.GetSketchSegments = lambda: self.segments
        original = self.transform.ArrayData
        for value in (None, [], [0] * 15, [False] * 16, ["1"] * 16, [math.nan] * 16):
            self.transform.ArrayData = value
            self.refused("FeatureObservationUnavailable")
        self.transform.ArrayData = original

    def test_changed_profile_geometry_or_transform_never_returns_definition(self):
        for what in ("geometry", "transform"):
            with self.subTest(what=what):
                for corner, x in zip(self.corners, (-0.04, 0.06, 0.06, -0.04)):
                    corner.X = x
                self.transform.ArrayData[9] = 0
                calls = 0

                def change(*args):
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        if what == "geometry":
                            for corner in self.corners:
                                corner.X += 0.01
                        else:
                            self.transform.ArrayData[9] = 0.01
                    return self.bodies

                self.document.GetBodies2.side_effect = change
                self.refused("FeatureObservationUnavailable")

    def test_control_changes_and_state_changes_remain_fail_closed(self):
        def mutate(*args):
            self.fixture.equations.GetCount.return_value = 1
            self.fixture.stamp += 1
            return self.bodies

        self.document.GetBodies2.side_effect = mutate
        result, definition = self.prepare()
        self.assertIsNone(definition)
        self.assertEqual(result["error"]["type"], "FeatureControlScopeUnsupported")
        self.assertFalse(result["observation"]["unchanged"])
        self.assertTrue(result["warnings"])

    def test_preliminary_failure_is_preserved_before_any_scope_reads(self):
        self.fixture.definition.BothDirections = True
        self.refused("UnsupportedDepthDefinition")
        self.document.GetBodies2.assert_not_called()


if __name__ == "__main__":
    unittest.main()
