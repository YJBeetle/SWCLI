"""Owned selection access is internal, fail-closed and always released."""

from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest import mock

from swcli.hosts import windows_feature_selections as selections


class Variant:
    def __init__(self, variant_type, value):
        self.variant_type, self.value = variant_type, value


class SelectionScopeTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            sys.modules,
            {
                "pythoncom": SimpleNamespace(VT_BYREF=16384, VT_DISPATCH=9, VT_I4=3),
                "win32com": SimpleNamespace(),
                "win32com.client": SimpleNamespace(VARIANT=Variant),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.stamp, self.modified = 17, False
        self.configuration = SimpleNamespace(Name="Default")
        self.extension = SimpleNamespace(NeedsRebuild2=0)
        self.bodies = []
        self.body = SimpleNamespace(
            identity=object(), GetType=lambda: 0, IsSheetMetal=False
        )
        self.document = SimpleNamespace(
            identity=object(),
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=self.configuration
            ),
            SketchManager=SimpleNamespace(ActiveSketch=None),
            GetSaveFlag=lambda: self.modified,
            GetUpdateStamp=lambda: self.stamp,
            GetBodies2=mock.Mock(side_effect=lambda *args: self.bodies),
            Extension=self.extension,
            EditRebuild3=mock.Mock(),
            ClearSelection2=mock.Mock(),
        )
        self.app = SimpleNamespace(
            ActiveDoc=self.document,
            IsSame=lambda a, b: int(a.identity is b.identity),
            ActivateDoc3=mock.Mock(),
        )
        self.feature = SimpleNamespace(
            ModifyDefinition=mock.Mock(), Select2=mock.Mock()
        )
        self.definition = self.make_definition()
        self.fresh = self.make_definition()
        self.preflight = {
            "ok": True,
            "feature": {"kind": "boss-extrude", "native_id": 1},
            "definition": {"depth_mm": 20},
            "controls": {"equation_count": 0},
            "profile": {"area_mm2": 5000},
            "body": {"solid_body_count": 1},
        }
        self.post = deepcopy(self.preflight)
        self.guard = self.patch(
            "prepare_profiled_extrusion_depth_edit_windows_with_definition",
            side_effect=lambda **kw: (
                (deepcopy(self.preflight), self.definition)
                if self.guard.call_count == 1
                else (deepcopy(self.post), self.fresh)
            ),
        )
        self.metrics = {
            "solid_body_count": 1,
            "volume_mm3": 100000,
            "surface_area_mm2": 16000,
            "centroid_mm": {"x": 10, "y": 20, "z": 10},
        }
        self.measure = self.patch(
            "measure_part_windows",
            side_effect=lambda **kw: {"ok": True, "metrics": deepcopy(self.metrics)},
        )
        self.diagnose = self.patch(
            "_diagnose_features", return_value={"healthy": True, "truncated": False}
        )

    def patch(self, member, **options):
        patcher = mock.patch.object(selections, member, **options)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def make_definition(self):
        def direction(ref1, type1, ref2, type2):
            self.assertEqual([ref1.variant_type, ref2.variant_type], [16393, 16393])
            self.assertEqual([type1.variant_type, type2.variant_type], [16387, 16387])
            self.assertEqual([type1.value, type2.value], [-2147483648] * 2)
            type1.value = type2.value = -1
            return -1

        return SimpleNamespace(
            GetDirectionReference=mock.Mock(side_effect=direction),
            GetContoursCount=0,
            GetFeatureScopeBodiesCount=0,
            FeatureScopeBodies=None,
            FeatureScope=True,
            AutoSelect=True,
            Merge=True,
            LinkToThickness=False,
            NormalCut=False,
            FlipSideToCut=False,
            AccessSelections=mock.Mock(return_value=True),
            ReleaseSelectionAccess=mock.Mock(side_effect=self.release),
            SetDepth=mock.Mock(),
            SetDirectionReference=mock.Mock(),
        )

    def release(self):
        self.stamp += 2

    def observe(self):
        result = selections.observe_extrusion_selection_scope_windows_with_definition(
            app=self.app, document=self.document, feature=self.feature
        )
        self.app.ActivateDoc3.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.document.ClearSelection2.assert_not_called()
        self.feature.ModifyDefinition.assert_not_called()
        self.feature.Select2.assert_not_called()
        for definition in (self.definition, self.fresh):
            definition.SetDepth.assert_not_called()
            definition.SetDirectionReference.assert_not_called()
        self.fresh.AccessSelections.assert_not_called()
        self.fresh.ReleaseSelectionAccess.assert_not_called()
        return result

    def refused(self, code, *, attempted=True):
        result, fresh = self.observe()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], code, result)
        self.assertIsNone(fresh)
        self.assertEqual(self.definition.AccessSelections.call_count, int(attempted))
        self.assertEqual(
            self.definition.ReleaseSelectionAccess.call_count, int(attempted)
        )
        return result

    def test_exact_access_release_returns_fresh_definition_and_reports_stamp_change(
        self,
    ):
        result, fresh = self.observe()
        self.assertTrue(result["ok"], result)
        self.assertIs(fresh, self.fresh)
        self.assertEqual(
            result["selection_access"],
            dict.fromkeys(
                (
                    "attempted",
                    "acquired",
                    "release_attempted",
                    "released",
                    "state_restored",
                ),
                True,
            ),
        )
        self.assertTrue(result["observation"]["update_stamp_changed"])
        self.assertEqual(result["scope"]["rollback_solid_body_count"], 0)
        self.assertEqual(result["scope"]["affected_scope"], "merged-boss")
        self.assertEqual(result["direction_after"], result["scope"]["direction"])
        self.definition.AccessSelections.assert_called_once()
        args = self.definition.AccessSelections.call_args.args
        self.assertIs(args[0], self.document)
        self.assertEqual((args[1].variant_type, args[1].value), (9, None))
        self.definition.ReleaseSelectionAccess.assert_called_once()
        self.document.GetBodies2.assert_called_once_with(-1, False)
        self.fresh.GetDirectionReference.assert_called_once()

    def test_failed_or_missing_preflight_definition_never_enters_selection_access(self):
        self.preflight = {
            "ok": False,
            "error": {"type": "Protected", "message": "stop"},
        }
        self.refused("Protected", attempted=False)
        self.guard.side_effect = None
        self.guard.return_value = ({"ok": True}, None)
        self.refused("FeatureSelectionScopeUnavailable", attempted=False)

    def test_background_document_is_not_implicitly_activated(self):
        self.app.ActiveDoc = SimpleNamespace(identity=object())
        self.refused("DocumentNotActive", attempted=False)

    def test_preexisting_unhealthy_rebuild_state_does_not_enter_access(self):
        self.extension.NeedsRebuild2 = 1
        self.refused("ModelInvalid", attempted=False)

    def test_intervening_edit_before_access_is_not_absorbed_into_its_stamp_change(self):
        def changed(*args):
            self.stamp += 1
            return {"healthy": True, "truncated": False}

        self.diagnose.side_effect = changed
        self.refused("FeatureObservationUnavailable", attempted=False)

    def test_stamp_change_during_final_readback_is_not_a_legitimate_access_delta(self):
        original = self.fresh.GetDirectionReference.side_effect

        def changed(*args):
            self.stamp += 1
            return original(*args)

        self.fresh.GetDirectionReference.side_effect = changed
        self.refused("FeatureSelectionStateNotRestored")

    def test_false_access_is_released_and_never_retried(self):
        self.definition.AccessSelections.return_value = False
        result = self.refused("FeatureSelectionAccessFailed")
        self.assertFalse(result["selection_access"]["acquired"])
        self.assertTrue(result["selection_access"]["released"])

    def test_throwing_access_can_be_partial_and_is_released_once(self):
        self.definition.AccessSelections.side_effect = RuntimeError("partial access")
        self.refused("RuntimeError")

    def test_nonboolean_access_is_not_coerced_and_is_released(self):
        self.definition.AccessSelections.return_value = 1
        self.refused("FeatureObservationUnavailable")

    def test_first_failure_survives_release_and_restoration_failures(self):
        self.definition.GetContoursCount = 1
        self.definition.ReleaseSelectionAccess.side_effect = RuntimeError(
            "release failed"
        )
        self.post["profile"] = {}
        result = self.refused("UnsupportedDepthContours")
        self.assertEqual(
            [w["code"] for w in result["warnings"]],
            [
                "feature-selection-release-failed",
                "feature-selection-restoration-failed",
            ],
        )
        self.assertFalse(result["selection_access"]["state_restored"])

    def test_release_failure_never_returns_a_usable_definition(self):
        self.definition.ReleaseSelectionAccess.side_effect = RuntimeError(
            "release failed"
        )
        result = self.refused("RuntimeError")
        self.assertFalse(result["selection_access"]["state_restored"])

    def test_negative_contour_count_is_not_treated_as_zero(self):
        self.definition.GetContoursCount = -1
        self.refused("FeatureSelectionScopeUnavailable")

    def test_explicit_contour_count_is_not_supported(self):
        self.definition.GetContoursCount = 1
        self.refused("UnsupportedDepthContours")

    def test_scope_count_array_must_agree(self):
        self.definition.GetFeatureScopeBodiesCount = 1
        self.refused("FeatureSelectionScopeUnavailable")

    def test_invalid_body_array_is_not_treated_as_empty(self):
        self.bodies = (None,)
        self.refused("FeatureSelectionScopeUnavailable")

    def test_multiple_or_surface_rollback_bodies_are_not_supported(self):
        self.bodies = [self.body, self.body]
        self.refused("UnsupportedDepthBodyScope")

    def test_rollback_surface_is_not_ignored(self):
        self.bodies = [self.body]
        self.body.GetType = lambda: 1
        self.refused("UnsupportedDepthBodyScope")

    def test_rollback_sheet_metal_is_not_normalized(self):
        self.bodies = [self.body]
        self.body.IsSheetMetal = True
        self.refused("UnsupportedDepthBodyScope")

    def test_nonmerged_boss_is_not_normalized(self):
        self.definition.Merge = False
        self.refused("UnsupportedDepthBodyScope")

    def test_boss_merge_and_thickness_link_are_not_normalized(self):
        self.definition.LinkToThickness = True
        self.refused("UnsupportedDepthDefinition")

    def cut(self):
        self.preflight["feature"]["kind"] = "cut-extrude"
        self.post = deepcopy(self.preflight)
        self.bodies = [self.body]
        self.definition.FeatureScopeBodies = [self.body]
        self.definition.GetFeatureScopeBodiesCount = 1

    def test_cut_requires_exact_selected_live_rollback_solid(self):
        self.cut()
        result, _ = self.observe()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["scope"]["affected_scope"], "single-rollback-solid")

    def test_foreign_cut_body_is_not_resolved_by_name_or_count(self):
        self.cut()
        self.definition.FeatureScopeBodies = [SimpleNamespace(identity=object())]
        self.refused("FeatureSelectionScopeUnavailable")

    def test_cut_all_body_scope_still_requires_one_rollback_solid(self):
        self.cut()
        self.definition.FeatureScope = False
        self.definition.GetFeatureScopeBodiesCount = 0
        self.definition.FeatureScopeBodies = None
        result, _ = self.observe()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["scope"]["affected_scope"], "all-rollback-solids")

    def test_cut_cannot_treat_null_body_array_as_one_live_body(self):
        self.cut()
        self.bodies = None
        self.refused("UnsupportedDepthBodyScope")

    def test_cut_normal_or_flip_side_flag_is_not_normalized(self):
        self.cut()
        self.definition.NormalCut = True
        self.refused("UnsupportedDepthDefinition")

    def test_modified_state_or_foreground_drift_fails_restoration(self):
        def changed():
            self.release()
            self.modified = True

        self.definition.ReleaseSelectionAccess.side_effect = changed
        self.refused("FeatureSelectionStateNotRestored")

    def test_foreground_identity_drift_fails_even_when_it_remains_present(self):
        def changed():
            self.release()
            self.app.ActiveDoc = SimpleNamespace(identity=object())

        self.definition.ReleaseSelectionAccess.side_effect = changed
        self.refused("FeatureSelectionStateNotRestored")

    def test_postrelease_incomplete_diagnostics_never_grant_edit_permission(self):
        self.diagnose.side_effect = [
            {"healthy": True, "truncated": False},
            {"healthy": True, "truncated": True},
        ]
        self.refused("ModelInvalid")

    def test_fresh_profile_and_independent_geometry_must_be_restored(self):
        self.post["profile"]["area_mm2"] = 6000
        self.refused("FeatureSelectionStateNotRestored")

    def test_fresh_geometry_change_does_not_pass_on_unchanged_flags(self):
        changed = deepcopy(self.metrics)
        changed["volume_mm3"] += 1
        self.measure.side_effect = [
            {"ok": True, "metrics": self.metrics},
            {"ok": True, "metrics": changed},
        ]
        self.refused("FeatureSelectionStateNotRestored")

    def test_fresh_direction_is_checked_even_if_depth_flags_and_geometry_match(self):
        self.fresh.GetDirectionReference.side_effect = lambda *args: 1
        self.refused("UnsupportedDepthDirection")

    def test_missing_fresh_definition_fails_closed_after_release(self):
        self.guard.side_effect = [
            (self.preflight, self.definition),
            ({"ok": True}, None),
        ]
        self.refused("FeatureSelectionStateNotRestored")

    def test_unwritten_unknown_and_contradictory_direction_outputs_fail_closed(self):
        cases = [
            (-1, [-2147483648, -2147483648], [None, None]),
            (-1, [-1, -1], [object(), None]),
            (0, [-1, -1], [None, None]),
            (-2, [-1, -1], [None, None]),
            (-1, [4, -1], [None, None]),
            (False, [-1, -1], [None, None]),
        ]
        for count, types, refs in cases:
            with self.subTest(count=count, types=types):

                def direction(ref1, type1, ref2, type2):
                    ref1.value, ref2.value = refs
                    type1.value, type2.value = types
                    return count

                self.definition.GetDirectionReference.side_effect = direction
                with self.assertRaises(selections._FeatureError):
                    selections._direction(self.definition)

    def test_explicit_direction_counts_never_grant_edit_permission(self):
        for count in (1, 2):
            with self.subTest(count=count):
                self.definition.GetDirectionReference.side_effect = lambda *args: count
                with self.assertRaises(selections._FeatureError) as exc:
                    selections._direction(self.definition)
                self.assertEqual(exc.exception.code, "UnsupportedDepthDirection")


if __name__ == "__main__":
    unittest.main()
