import copy
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_features as features
from swcli.result_schemas import OperationResultInvalid, validate_operation_result

DIAGNOSTICS = {
    "healthy": True,
    "issues": [],
    "issue_count": 0,
    "scanned_feature_count": 4,
    "truncated": False,
    "limit": 500,
}
BODIES = {
    "applicable": True,
    "count": 1,
    "items": [
        {
            "name": "boss",
            "type": {"code": 0, "name": "solid"},
            "visible": True,
            "face_count": 6,
            "edge_count": 12,
            "approximate_bounding_box": None,
        }
    ],
}


class ExtrusionTests(unittest.TestCase):
    def setUp(self):
        self.sketch = SimpleNamespace(
            GetTypeName2=lambda: "ProfileFeature",
            GetNextFeature=lambda: None,
            GetOwnerFeature=lambda: None,
            Select2=mock.Mock(return_value=True),
        )
        self.definition = SimpleNamespace(
            GetDepth=mock.Mock(return_value=0.02),
            GetEndCondition=lambda forward: 0,
            ReverseDirection=False,
            Merge=True,
            BothDirections=False,
        )
        self.created = SimpleNamespace(
            Name="renamed-extrusion",
            GetTypeName2=lambda: "Boss",
            GetDefinition=lambda: self.definition,
        )
        self.manager = SimpleNamespace(
            FeatureExtrusion3=mock.Mock(return_value=self.created)
        )
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            SketchManager=SimpleNamespace(ActiveSketch=None),
            FirstFeature=lambda: self.sketch,
            FeatureManager=self.manager,
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(spec=[], return_value=True),
        )
        self.app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
        self.diagnose = mock.patch.object(
            features, "_diagnose_features", return_value=copy.deepcopy(DIAGNOSTICS)
        ).start()
        self.bodies = mock.patch.object(
            features, "_inspect_bodies", return_value=copy.deepcopy(BODIES)
        ).start()
        self.addCleanup(mock.patch.stopall)

    def extrude(self, **values):
        return features.extrude_sketch_windows(
            app=self.app,
            document=self.document,
            sketch_feature=self.sketch,
            **{"depth_mm": 20, **values},
        )

    def with_handle(self, **values):
        return features.extrude_sketch_windows_with_handle(
            app=self.app, document=self.document, sketch_feature=self.sketch,
            **{"depth_mm": 20, **values},
        )

    def test_exact_creation_handle_is_not_recovered_from_active_or_last_feature(self):
        self.app.ActiveDoc = object()
        self.document.FeatureByPositionReverse = mock.Mock()
        result, handle = self.with_handle()
        self.assertTrue(result["ok"], result)
        self.assertIs(handle, self.created)
        self.document.FeatureByPositionReverse.assert_not_called()

    def test_pre_creation_failures_never_invent_a_feature_handle(self):
        result, handle = self.with_handle(depth_mm=0)
        self.assertFalse(result["ok"])
        self.assertIsNone(handle)
        self.manager.FeatureExtrusion3.return_value = None
        result, handle = self.with_handle()
        self.assertEqual(result["error"]["type"], "ExtrusionFailed")
        self.assertIsNone(handle)

    def test_created_handle_and_primary_error_survive_verification_and_cleanup_failure(self):
        self.document.EditRebuild3.return_value = False
        self.document.ClearSelection2.side_effect = [None, RuntimeError("cleanup failed")]
        result, handle = self.with_handle()
        self.assertEqual(result["error"]["type"], "ModelInvalid")
        self.assertIs(handle, self.created)
        self.assertEqual(result["warnings"][0]["code"], "selection-cleanup-failed")

    def test_exact_registered_feature_and_explicit_parameters_are_used(self):
        result = self.extrude()
        self.assertTrue(result["ok"], result)
        self.sketch.Select2.assert_called_once_with(False, 0)
        args = self.manager.FeatureExtrusion3.call_args.args
        self.assertEqual(len(args), 23)
        self.assertEqual(args[:7], (True, False, False, 0, 0, 0.02, 0.0))
        self.assertEqual(args[17:20], (True, True, True))
        self.assertEqual(
            result["feature"], {"name": "renamed-extrusion", "type": "Boss"}
        )
        self.assertTrue(result["geometry_verification"]["passed"])
        self.document.ClearSelection2.assert_has_calls(
            [mock.call(True), mock.call(True)]
        )

    def test_reverse_and_separate_body_options_are_verified(self):
        self.definition.ReverseDirection = True
        self.definition.Merge = False
        result = self.extrude(reverse=True, merge=False)
        self.assertTrue(result["ok"], result)
        args = self.manager.FeatureExtrusion3.call_args.args
        self.assertTrue(args[2])
        self.assertFalse(args[17])

    def test_invalid_depth_does_not_mutate_native_selection(self):
        for value in (0, -1, float("nan"), float("inf"), 5e-324):
            with self.subTest(value=value):
                self.assertEqual(
                    self.extrude(depth_mm=value)["error"]["type"], "InvalidArgument"
                )
        self.document.ClearSelection2.assert_not_called()
        self.manager.FeatureExtrusion3.assert_not_called()

    def test_missing_consumed_or_wrong_kind_sketch_never_falls_back(self):
        self.document.FirstFeature = lambda: None
        self.assertEqual(self.extrude()["error"]["type"], "SketchUnavailable")
        unrelated = SimpleNamespace(GetNextFeature=lambda: None)
        self.document.FirstFeature = lambda: unrelated
        self.assertEqual(self.extrude()["error"]["type"], "SketchUnavailable")
        self.document.FirstFeature = lambda: self.sketch
        self.sketch.GetOwnerFeature = lambda: self.created
        self.assertEqual(self.extrude()["error"]["type"], "SketchUnavailable")
        self.sketch.GetOwnerFeature = lambda: None
        self.sketch.GetTypeName2 = lambda: "3DProfileFeature"
        self.assertEqual(self.extrude()["error"]["type"], "SketchUnavailable")
        self.document.ClearSelection2.assert_not_called()
        self.manager.FeatureExtrusion3.assert_not_called()

    def test_existing_edit_or_non_part_is_not_taken_over(self):
        existing = object()
        self.document.SketchManager.ActiveSketch = existing
        self.assertEqual(self.extrude()["error"]["type"], "SketchEditInProgress")
        self.assertIs(self.document.SketchManager.ActiveSketch, existing)
        self.document.GetType = lambda: 2
        self.assertEqual(self.extrude()["error"]["type"], "UnsupportedDocumentType")
        self.document.ClearSelection2.assert_not_called()

    def test_selection_null_return_and_native_error_clear_selections(self):
        self.sketch.Select2.return_value = False
        self.assertEqual(self.extrude()["error"]["type"], "SketchSelectionFailed")
        self.sketch.Select2.return_value = True
        self.manager.FeatureExtrusion3.return_value = None
        self.assertEqual(self.extrude()["error"]["type"], "ExtrusionFailed")
        self.manager.FeatureExtrusion3.side_effect = RuntimeError("COM failed")
        self.assertEqual(self.extrude()["error"]["message"], "COM failed")
        self.assertEqual(self.document.ClearSelection2.call_count, 6)
        self.document.EditRebuild3.assert_not_called()

    def test_failed_rebuild_or_diagnostics_preserve_created_feature_metadata(self):
        self.document.EditRebuild3.return_value = False
        result = self.extrude()
        self.assertEqual(result["error"]["type"], "ModelInvalid")
        self.assertEqual(result["feature"]["name"], self.created.Name)
        self.document.EditRebuild3.return_value = True
        self.diagnose.return_value["healthy"] = False
        self.assertEqual(self.extrude()["error"]["type"], "ModelInvalid")
        self.bodies.assert_not_called()

    def test_definition_and_solid_body_checks_are_not_input_echoes(self):
        for name, value in (
            ("ReverseDirection", True),
            ("Merge", False),
            ("BothDirections", True),
        ):
            with self.subTest(name=name):
                original = getattr(self.definition, name)
                setattr(self.definition, name, value)
                self.assertEqual(
                    self.extrude()["error"]["type"], "ExtrusionVerificationFailed"
                )
                setattr(self.definition, name, original)
        self.definition.GetDepth.return_value = 0.019
        self.assertEqual(self.extrude()["error"]["type"], "ExtrusionVerificationFailed")
        self.definition.GetDepth.return_value = 0.02
        self.definition.GetEndCondition = lambda forward: 1
        self.assertFalse(self.extrude()["geometry_verification"]["passed"])
        self.definition.GetEndCondition = lambda forward: 0
        self.bodies.return_value = {"applicable": True, "count": 0, "items": []}
        self.assertFalse(self.extrude()["geometry_verification"]["passed"])

    def test_nonfinite_native_depth_and_cleanup_failure_are_explicit(self):
        self.definition.GetDepth.return_value = float("nan")
        result = self.extrude()
        self.assertFalse(result["ok"])
        self.assertNotIn("geometry_verification", result)
        self.definition.GetDepth.return_value = 0.02
        self.document.ClearSelection2.side_effect = [None, RuntimeError("cannot clear")]
        result = self.extrude()
        self.assertTrue(result["ok"])
        self.assertEqual(result["warnings"][0]["code"], "selection-cleanup-failed")

    def test_success_contract_rejects_unverified_or_unrebuilt_results(self):
        result = self.extrude()
        result["sketch_id"] = "s-ab12cd"
        result["document"] = {
            "title": "Part1",
            "path": "",
            "type": 1,
            "modified": True,
            "update_stamp": 0,
        }
        validate_operation_result("feature.extrude", result)
        for key in ("rebuilt", "geometry_verification", "diagnostics"):
            invalid = copy.deepcopy(result)
            if key == "rebuilt":
                invalid[key] = False
            else:
                invalid[key][
                    "passed" if key == "geometry_verification" else "healthy"
                ] = False
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.extrude", invalid)
