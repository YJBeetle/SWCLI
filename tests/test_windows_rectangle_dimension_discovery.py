"""Observable rectangle recovery is read-only, exact-owner and fail-closed."""

import json
import unittest
from unittest import mock

from swcli.hosts import windows_rectangle_dimension_discovery as discovery
from test_windows_linear_dimensions import Native, RectangleNativeFixture


class RectangleDiscoveryTests(RectangleNativeFixture, unittest.TestCase):
    def call(self):
        result, handles = discovery.discover_rectangle_dimensions_windows_with_handles(
            app=self.app, document=self.document, sketch_feature=self.feature
        )
        json.dumps(result, allow_nan=False)
        for mutation in self.mutations:
            mutation.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.foreground)
        if not result["ok"]:
            self.assertEqual(handles, {})
        return result, handles

    def failed(self, code):
        result, _ = self.call()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], code, result)
        return result

    def test_pair_uses_native_axis_roles_and_geometry_not_names_or_order(self):
        self.displays.reverse()
        for parameter in self.parameters.values():
            parameter.FullName = "diagnostic-only"
        result, handles = self.call()
        self.assertTrue(result["ok"], result)
        for kind, expected in (("width", 40), ("height", 30)):
            self.assertIs(handles[kind], self.parameters[kind])
            self.assertEqual(result["dimensions"][kind]["value"], expected)
            self.assertEqual(result["inspections"][kind]["dimension"]["kind"], kind)
        self.assertTrue(result["observation"]["unchanged"])
        self.assertTrue(result["geometry_verification"]["passed"])

    def test_absorbed_profile_read_does_not_activate_or_edit(self):
        boss = Native()
        boss.GetID, boss.GetTypeName2 = lambda: 27, lambda: "BossExtrude"
        boss.GetFirstSubFeature = lambda: self.feature
        boss.GetNextFeature = boss.GetNextSubFeature = lambda: None
        self.document.FirstFeature = lambda: boss
        self.assertTrue(self.call()[0]["ok"])

    def test_native_duplicate_presentations_deduplicate_but_not_conflicting_roles(self):
        self.displays.append(self.display(self.parameters["width"], 11))
        self.assertTrue(self.call()[0]["ok"])
        self.displays[1] = self.display(self.parameters["width"], 12)
        self.failed("DimensionVerificationFailed")

    def test_same_values_never_disambiguate_two_native_width_parameters(self):
        duplicate = Native()
        duplicate.GetFeatureOwner = lambda: self.feature
        duplicate.GetType = lambda: 0
        self.displays.append(self.display(duplicate, 11))
        self.failed("DimensionAmbiguous")

    def test_empty_or_incomplete_chain_does_not_claim_absent_saved_dimensions(self):
        self.displays = []
        result = self.failed("DimensionObservationUnavailable")
        self.assertIn("empty", result["error"]["message"])
        self.displays = [self.display(self.parameters["width"], 11)]
        result = self.failed("DimensionNotFound")
        self.assertIn("hidden", result["error"]["message"])

    def test_wrong_owner_type_unreadable_chain_and_later_cycle_fail(self):
        for fault, code in (
            ("owner", "DimensionVerificationFailed"),
            ("length", "DimensionVerificationFailed"),
            ("missing", "DimensionObservationUnavailable"),
            ("metadata", "DimensionObservationUnavailable"),
            ("cycle", "DimensionObservationUnavailable"),
        ):
            with self.subTest(fault=fault):
                self.setUp()
                if fault == "owner":
                    self.parameters["height"].GetFeatureOwner = lambda: Native()
                elif fault == "length":
                    self.parameters["height"].GetType = lambda: 1
                elif fault == "missing":
                    self.displays[1].GetDimension2 = lambda index: None
                elif fault == "metadata":
                    self.displays[1].Type2 = True
                else:
                    self.feature.GetNextDisplayDimension = (
                        lambda display: self.displays[0]
                    )
                self.failed(code)

    def test_read_only_driven_equation_and_design_table_controls_are_observed(self):
        width = self.parameters["width"]
        width.ReadOnly, width.DrivenState = 1, 1
        width.IsDesignTableDimension = lambda: True
        self.equations = [f'"{width.FullName}" = 40']
        self.manager.ActiveSketch = self.sketch
        result, _ = self.call()
        self.assertTrue(result["ok"], result)
        read = result["inspections"]["width"]
        self.assertTrue(read["dimension"]["read_only"])
        self.assertEqual(read["dimension"]["driven_state"], 1)
        self.assertTrue(read["equation_control"]["controlled"])
        self.assertTrue(read["design_table_controlled"])
        self.assertTrue(result["editing"])

    def test_geometry_mismatch_retains_evidence_but_no_handles(self):
        self.parameters["height"].value = 0.031
        result = self.failed("DimensionVerificationFailed")
        self.assertFalse(
            result["inspections"]["height"]["geometry_verification"]["passed"]
        )

    def test_configuration_stamp_edit_or_geometry_change_never_publishes_pair(self):
        for field in ("configuration", "stamp", "edit", "geometry"):
            with self.subTest(field=field):
                self.setUp()

                def change(config):
                    if field == "configuration":
                        self.config.Name = "Other"
                    elif field == "stamp":
                        self.stamp += 1
                    elif field == "edit":
                        self.manager.ActiveSketch = self.sketch
                    else:
                        self.center[0] += 1
                    return self.parameters["height"].value

                self.parameters["height"].GetSystemValue2.side_effect = change
                self.failed("DimensionObservationUnavailable")

    def test_nonpart_and_malformed_geometry_fail_before_dimension_selection(self):
        self.document.GetType = lambda: 2
        with mock.patch.object(discovery, "_pair") as pair:
            self.failed("UnsupportedDocumentType")
            pair.assert_not_called()
        self.document.GetType = lambda: 1
        self.sketch.GetSketchSegments = lambda: ()
        with mock.patch.object(discovery, "_pair") as pair:
            self.failed("UnsupportedDimensionProfile")
            pair.assert_not_called()


if __name__ == "__main__":
    unittest.main()
