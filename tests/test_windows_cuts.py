import copy
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_cuts as cuts
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


class CutExtrusionTests(unittest.TestCase):
    def setUp(self):
        self.sketch = SimpleNamespace(
            GetTypeName2=lambda: "ProfileFeature",
            GetNextFeature=lambda: None,
            GetOwnerFeature=lambda: None,
            Select2=mock.Mock(return_value=True),
        )
        self.definition = SimpleNamespace(
            GetDepth=lambda forward: 0.02,
            ReverseDirection=True,
            GetEndCondition=lambda forward: 0,
            BothDirections=False,
        )
        self.created = SimpleNamespace(
            Name="native-cut",
            GetTypeName2=lambda: "ICE",
            GetDefinition=lambda: self.definition,
        )
        self.manager = SimpleNamespace(FeatureCut4=mock.Mock(return_value=self.created))
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.sketch,
            SketchManager=SimpleNamespace(ActiveSketch=None),
            FeatureManager=self.manager,
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(spec=[], return_value=True),
            SetPickMode=mock.Mock(spec=[], return_value=None),
        )
        self.app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
        self.before = {
            "solid_body_count": 1,
            "volume_mm3": 100000,
            "surface_area_mm2": 16000,
            "centroid_mm": {"x": 0, "y": 0, "z": 10},
        }
        self.after = {**self.before, "volume_mm3": 99000}
        self.measure = mock.patch.object(
            cuts,
            "measure_part_windows",
            side_effect=[
                {"ok": True, "metrics": self.before},
                {"ok": True, "metrics": self.after},
            ],
        ).start()
        self.diagnose = mock.patch.object(
            cuts,
            "_diagnose_features",
            return_value={
                "healthy": True,
                "issues": [],
                "issue_count": 0,
                "scanned_feature_count": 5,
                "truncated": False,
                "limit": 500,
            },
        ).start()
        self.bodies = mock.patch.object(
            cuts,
            "_inspect_bodies",
            return_value={"applicable": True, "count": 1, "items": []},
        ).start()
        self.addCleanup(mock.patch.stopall)

    def cut(self, **values):
        return cuts.cut_extrude_sketch_windows(
            app=self.app,
            document=self.document,
            sketch_feature=self.sketch,
            **{"depth_mm": 20, **values},
        )

    def test_scalar_native_call_inverts_cut_default_and_affects_all_solids(self):
        result = self.cut()
        self.assertTrue(result["ok"], result)
        args = self.manager.FeatureCut4.call_args.args
        self.assertEqual(len(args), 27)
        self.assertEqual(args[:7], (True, False, True, 0, 0, 0.02, 0))
        self.assertEqual(args[17:23], (False, False, True, False, False, False))
        self.assertEqual(result["affected_scope"], "all-solid-bodies")
        self.assertEqual(result["geometry_verification"]["volume_removed_mm3"], 1000)
        self.assertFalse(result["geometry_verification"]["actual_reverse"])
        self.assertTrue(result["geometry_verification"]["native_reverse_direction"])
        self.document.ClearSelection2.assert_has_calls(
            [mock.call(True), mock.call(True)]
        )
        self.document.SetPickMode.assert_not_called()

    def test_reverse_consistently_means_against_sketch_normal(self):
        self.definition.ReverseDirection = False
        result = self.cut(reverse=True)
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.manager.FeatureCut4.call_args.args[2])
        self.assertTrue(result["geometry_verification"]["actual_reverse"])

    def test_nonfinite_depth_existing_edit_and_absorbed_sketch_do_not_mutate(self):
        for depth in (0, -1, math.inf, math.nan, 5e-324):
            self.assertEqual(
                self.cut(depth_mm=depth)["error"]["type"], "InvalidArgument"
            )
        self.document.SketchManager.ActiveSketch = object()
        self.assertEqual(self.cut()["error"]["type"], "SketchEditInProgress")
        self.document.SketchManager.ActiveSketch = None
        self.sketch.GetOwnerFeature = lambda: object()
        self.assertEqual(self.cut()["error"]["type"], "SketchUnavailable")
        self.measure.assert_not_called()
        self.manager.FeatureCut4.assert_not_called()
        self.document.SetPickMode.assert_not_called()

    def test_missing_before_measurement_or_failed_selection_prevents_cut(self):
        self.measure.side_effect = None
        self.measure.return_value = {
            "ok": False,
            "error": {"type": "NoSolidBodies", "message": "empty"},
        }
        self.assertEqual(self.cut()["error"]["type"], "NoSolidBodies")
        self.document.ClearSelection2.assert_not_called()
        self.measure.return_value = {"ok": True, "metrics": self.before}
        self.sketch.Select2.return_value = False
        self.assertEqual(self.cut()["error"]["type"], "SketchSelectionFailed")
        self.manager.FeatureCut4.assert_not_called()
        self.document.SetPickMode.assert_not_called()

    def test_rejected_cut_finishes_native_command_before_selection_cleanup(self):
        calls = []
        state = {"command": -3}

        def native_cut(*arguments):
            calls.append("cut")
            state["command"] = 10
            return None

        def finish():
            calls.append("pick")
            state["command"] = -3
            # SetPickMode is void, not a boolean success API.
            return None

        self.manager.FeatureCut4.side_effect = native_cut
        self.document.SetPickMode.side_effect = finish
        self.document.ClearSelection2.side_effect = lambda value: calls.append("clear")
        result = self.cut()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "CutExtrusionFailed")
        self.assertEqual(state["command"], -3)
        self.assertEqual(calls, ["clear", "cut", "pick", "clear"])
        self.assertNotIn("warnings", result)
        self.manager.FeatureCut4.assert_called_once()
        self.measure.assert_called_once()
        self.document.EditRebuild3.assert_not_called()

    def test_cut_and_both_cleanup_failures_preserve_the_primary_error(self):
        self.manager.FeatureCut4.side_effect = RuntimeError("native cut failed")
        self.document.SetPickMode.side_effect = OSError("cannot finish cut command")
        self.document.ClearSelection2.side_effect = [None, OSError("cannot clear selection")]
        result = self.cut()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["message"], "native cut failed")
        self.assertEqual(
            [item["code"] for item in result["warnings"]],
            ["cut-command-cleanup-failed", "selection-cleanup-failed"],
        )
        self.document.SetPickMode.assert_called_once_with()
        self.manager.FeatureCut4.assert_called_once()

    def test_failed_feature_manager_lookup_does_not_cancel_a_native_command(self):
        class MissingManager:
            @property
            def FeatureManager(inner):
                raise RuntimeError("manager unavailable")

            def __getattr__(inner, name):
                return getattr(self.document, name)

        result = cuts.cut_extrude_sketch_windows(
            app=self.app, document=MissingManager(), sketch_feature=self.sketch, depth_mm=20
        )
        self.assertEqual(result["error"]["message"], "manager unavailable")
        self.document.SetPickMode.assert_not_called()

    def test_created_cut_with_later_verification_error_is_not_cancelled(self):
        self.document.EditRebuild3.return_value = False
        self.assertEqual(self.cut()["error"]["type"], "ModelInvalid")
        self.document.SetPickMode.assert_not_called()

    def test_no_created_feature_or_unhealthy_rebuild_never_claims_success(self):
        self.manager.FeatureCut4.return_value = None
        self.assertEqual(self.cut()["error"]["type"], "CutExtrusionFailed")
        self.measure.side_effect = [{"ok": True, "metrics": self.before}]
        self.manager.FeatureCut4.return_value = self.created
        self.document.EditRebuild3.return_value = False
        self.assertEqual(self.cut()["error"]["type"], "ModelInvalid")

    def test_unchanged_increased_tiny_volume_or_wrong_definition_is_rejected(self):
        for volume, direction, end, both in (
            (100000, True, 0, False),
            (101000, True, 0, False),
            (99999.9999999, True, 0, False),
            (99000, False, 0, False),
            (99000, True, 1, False),
            (99000, True, 0, True),
        ):
            self.measure.side_effect = [
                {"ok": True, "metrics": self.before},
                {"ok": True, "metrics": {**self.after, "volume_mm3": volume}},
            ]
            self.definition.ReverseDirection = direction
            self.definition.GetEndCondition = lambda forward: end
            self.definition.BothDirections = both
            result = self.cut()
            self.assertEqual(result["error"]["type"], "CutVerificationFailed")
            self.assertFalse(result["geometry_verification"]["passed"])

    def test_after_measurement_failure_preserves_partial_before_evidence(self):
        self.measure.side_effect = [
            {"ok": True, "metrics": self.before},
            {
                "ok": False,
                "error": {"type": "MeasurementUnavailable", "message": "failed"},
            },
        ]
        result = self.cut()
        self.assertFalse(result["ok"])
        self.assertEqual(result["measurement_before"], self.before)
        self.assertIn("feature", result)

    def test_native_exception_and_selection_cleanup_warning_remain_structured(self):
        self.manager.FeatureCut4.side_effect = RuntimeError("native cut failed")
        self.document.ClearSelection2.side_effect = [
            None,
            OSError("cannot clear selection"),
        ]
        result = self.cut()
        self.assertEqual(result["error"]["message"], "native cut failed")
        self.assertEqual(result["warnings"][0]["code"], "selection-cleanup-failed")

    def test_success_schema_requires_actual_removal_and_healthy_native_result(self):
        result = self.cut()
        result["sketch_id"] = "s-ab12cd"
        result["document"] = {
            "title": "Part1",
            "path": "",
            "type": 1,
            "modified": True,
            "update_stamp": 0,
        }
        validate_operation_result("feature.cut-extrude", result)
        for field, value in (
            ("volume_removed_mm3", 0),
            ("end_condition", 1),
            ("both_directions", True),
        ):
            invalid = copy.deepcopy(result)
            invalid["geometry_verification"][field] = value
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.cut-extrude", invalid)
