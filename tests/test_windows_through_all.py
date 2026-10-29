"""Through-all eligibility, retained native evidence and result contract."""
import copy
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_cuts as cuts
from swcli.result_schemas import validate_operation_result, OperationResultInvalid
import test_windows_cuts as blind_fixture


class ThroughAllTests(unittest.TestCase):
    def setUp(self):
        blind_fixture.CutExtrusionTests.setUp(self)
        self.body = SimpleNamespace(GetType=lambda: 0)
        self.document.GetBodies2 = mock.Mock(return_value=(self.body,))
        self.document.SelectionManager = SimpleNamespace(GetSelectedObjectCount2=lambda mark: 0)
        self.document.Extension = SimpleNamespace(NeedsRebuild2=0)
        arc = SimpleNamespace(
            ConstructionGeometry=False, GetType=lambda: 1, IsCircle=lambda: 1,
            GetCenterPoint2=lambda: SimpleNamespace(X=0., Y=0., Z=0.),
            GetRadius=lambda: .003,
        )
        self.profile = SimpleNamespace(Is3D=False, GetSketchSegments=lambda: (arc,))
        self.sketch.GetSpecificFeature2 = lambda: self.profile
        self.created.GetTypeName = lambda: "Cut"
        self.definition.GetEndCondition = lambda forward: 1
        self.definition.GetDepth = mock.Mock(side_effect=AssertionError("unused depth read"))
        self.definition.IsThinFeature = False
        self.definition.FeatureScope = False
        self.definition.FromType = 0
        self.definition.GetDraftWhileExtruding = lambda forward: False

    def run_cut(self, **values):
        return cuts.cut_extrude_sketch_windows_with_handle(
            app=self.app, document=self.document, sketch_feature=self.sketch,
            end_condition="through-all", **values)

    def result(self):
        result, handle = self.run_cut()
        self.assertTrue(result["ok"], result)
        self.assertIs(handle, self.created)
        result["sketch_id"] = "s-ab12cd"
        result["feature"]["feature_id"] = "f-ab12cd"
        result["document"] = dict(title="Part1", path="", type=1, modified=True, update_stamp=0)
        validate_operation_result("feature.cut-extrude", result)
        return result

    def test_native_termination_and_scope_do_not_depend_on_unused_depth(self):
        result = self.result()
        args = self.manager.FeatureCut4.call_args.args
        self.assertEqual(args[3], 1)
        self.assertEqual(args[5], .001)
        self.assertEqual(args[18:20], (False, False))
        self.assertIsNone(result["depth_mm"])
        self.assertIsNone(result["geometry_verification"]["actual_depth_mm"])
        self.definition.GetDepth.assert_not_called()
        self.document.GetBodies2.assert_has_calls([mock.call(-1, False), mock.call(-1, False)])

    def test_reverse_uses_existing_normalized_direction(self):
        self.definition.ReverseDirection = False
        result, _ = self.run_cut(reverse=True)
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.manager.FeatureCut4.call_args.args[2])
        self.assertTrue(result["geometry_verification"]["actual_reverse"])

    def test_explicit_depth_is_refused_before_any_cad_access(self):
        for value in (None, 0, 1, True):
            result, handle = self.run_cut(depth_mm=value)
            self.assertEqual(result["error"]["type"], "InvalidArgument")
            self.assertIsNone(handle)
        self.measure.assert_not_called()
        self.document.GetBodies2.assert_not_called()
        self.manager.FeatureCut4.assert_not_called()

    def test_existing_selection_is_not_cleared_or_consumed(self):
        self.document.SelectionManager.GetSelectedObjectCount2 = lambda mark: 1
        result, _ = self.run_cut()
        self.assertEqual(result["error"]["type"], "UnsupportedCutScope")
        self.document.ClearSelection2.assert_not_called()
        self.measure.assert_not_called()
        self.manager.FeatureCut4.assert_not_called()

    def test_multi_body_empty_or_surface_targets_are_refused_before_selection(self):
        for bodies in (None, (), (self.body, self.body), (SimpleNamespace(GetType=lambda: 1),)):
            self.document.GetBodies2.return_value = bodies
            result, _ = self.run_cut()
            self.assertEqual(result["error"]["type"], "UnsupportedCutScope")
        self.document.ClearSelection2.assert_not_called()
        self.measure.assert_not_called()
        self.manager.FeatureCut4.assert_not_called()

    def test_3d_open_arc_extra_circle_or_unreadable_profile_never_mutates(self):
        original = self.profile.GetSketchSegments()
        for is3d, segments in ((True, original), (False, None), (False, ()),
                               (False, original * 2), (False, original * 65)):
            self.profile.Is3D = is3d
            self.profile.GetSketchSegments = lambda: segments
            result, _ = self.run_cut()
            self.assertFalse(result["ok"], result)
        self.profile.Is3D = False
        self.profile.GetSketchSegments = lambda: original
        original[0].IsCircle = lambda: 0
        self.assertFalse(self.run_cut()[0]["ok"])
        self.document.ClearSelection2.assert_not_called()
        self.measure.assert_not_called()
        self.manager.FeatureCut4.assert_not_called()

    def test_native_wrong_scope_or_draft_retains_feature_and_readbacks(self):
        for field in ("FeatureScope", "IsThinFeature", "FromType", "GetDraftWhileExtruding"):
            with self.subTest(field=field):
                self.setUp()
                setattr(self.definition, field, (lambda forward: True) if field.startswith("Get") else 1 if field == "FromType" else True)
                result, handle = self.run_cut()
                self.assertEqual(result["error"]["type"], "CutVerificationFailed")
                self.assertFalse(result["geometry_verification"]["passed"])
                self.assertIs(handle, self.created)
                self.assertIn("through_all_settings", result)
                self.document.SetPickMode.assert_not_called()

    def test_readback_exception_never_retries_or_cancels_created_feature(self):
        self.definition.GetDraftWhileExtruding = mock.Mock(side_effect=RuntimeError("readback unavailable"))
        result, handle = self.run_cut()
        self.assertFalse(result["ok"])
        self.assertEqual(result["through_all_settings"], dict(thin=False, feature_scope=False, from_type=0))
        self.assertIs(handle, self.created)
        self.manager.FeatureCut4.assert_called_once()
        self.document.SetPickMode.assert_not_called()

    def test_truncated_diagnostics_or_pending_rebuild_never_claim_success(self):
        self.diagnose.return_value["truncated"] = True
        result, handle = self.run_cut()
        self.assertEqual(result["error"]["type"], "ModelInvalid")
        self.assertIs(handle, self.created)
        self.setUp()
        self.document.Extension.NeedsRebuild2 = 1
        self.assertEqual(self.run_cut()[0]["error"]["type"], "CutVerificationFailed")

    def test_cleanup_failure_keeps_created_feature_but_cannot_claim_success(self):
        self.document.ClearSelection2.side_effect = [None, RuntimeError("clear failed")]
        result, handle = self.run_cut()
        self.assertEqual(result["error"]["type"], "SelectionCleanupFailed")
        self.assertIs(handle, self.created)
        self.document.SetPickMode.assert_not_called()
        self.manager.FeatureCut4.assert_called_once()

    def test_native_boolean_ambiguity_and_wrong_feature_kind_do_not_pass(self):
        for member, value in (("ReverseDirection", 1), ("BothDirections", 0),
                              ("IsThinFeature", 0), ("FeatureScope", 0), ("FromType", False)):
            with self.subTest(member=member):
                self.setUp()
                setattr(self.definition, member, value)
                result, handle = self.run_cut()
                self.assertFalse(result["ok"])
                self.assertIs(handle, self.created)
                self.manager.FeatureCut4.assert_called_once()
        self.setUp()
        self.created.GetTypeName = lambda: "Boss"
        result, handle = self.run_cut()
        self.assertFalse(result["ok"])
        self.assertIs(handle, self.created)

    def test_success_contract_rejects_invented_travel_or_unverified_settings(self):
        result = self.result()
        changes = [
            lambda r: r.update(depth_mm=1),
            lambda r: r.pop("end_condition"),
            lambda r: r.pop("through_all_settings"),
            lambda r: r["geometry_verification"].update(actual_depth_mm=1),
            lambda r: r["geometry_verification"].update(end_condition=0),
            lambda r: r["geometry_verification"].update(absolute_depth_tolerance_mm=1e-6),
            lambda r: r["through_all_settings"].update(feature_scope=True),
            lambda r: r["through_all_settings"].update(needs_rebuild=1),
            lambda r: r["measurement_after"].update(solid_body_count=2),
            lambda r: r["diagnostics"].update(truncated=True),
        ]
        for change in changes:
            invalid = copy.deepcopy(result); change(invalid)
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.cut-extrude", invalid)
