"""Depth edits verify exact scope/staging/readback, not just COM success."""

from copy import deepcopy
from types import SimpleNamespace
import math
import unittest
from unittest import mock

from swcli.hosts import windows_feature_depth_edits as edits


class FeatureDepthEditTests(unittest.TestCase):
    def setUp(self):
        self.depth, self.staged, self.stamp, self.modified = 20.0, 20.0, 17, False
        self.document = SimpleNamespace(
            identity=object(),
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="Default")
            ),
            SketchManager=SimpleNamespace(ActiveSketch=None),
            GetSaveFlag=lambda: self.modified,
            GetUpdateStamp=lambda: self.stamp,
            EditRebuild3=mock.Mock(spec=[], return_value=True),
            ClearSelection2=mock.Mock(),
        )
        self.app = SimpleNamespace(
            ActiveDoc=self.document,
            IsSame=lambda a, b: int(a.identity is b.identity),
            ActivateDoc3=mock.Mock(),
        )
        self.definition = SimpleNamespace(
            SetDepth=mock.Mock(side_effect=self.stage),
            GetDepth=mock.Mock(side_effect=lambda forward: self.staged / 1000),
            SetChangeToConfigurations=mock.Mock(return_value=True),
            AccessSelections=mock.Mock(),
            ReleaseSelectionAccess=mock.Mock(),
        )
        self.feature = SimpleNamespace(
            ModifyDefinition=mock.Mock(side_effect=self.commit), Select2=mock.Mock()
        )
        self.template = {
            "ok": True,
            "feature": {"kind": "boss-extrude", "name": "exact boss"},
            "definition": {"depth_mm": 20.0, "reverse_direction": False},
            "controls": {"configuration": "Default", "equation_count": 0},
            "profile": {"geometry": {"area_mm2": 5000}},
            "body": {"solid_body_count": 1},
            "scope": {"affected_scope": "merged-boss", "selected_contour_count": 0},
        }
        self.scope = self.patch(
            "observe_extrusion_selection_scope_windows_with_definition",
            side_effect=self.observe_scope,
        )
        self.guard = self.patch(
            "prepare_profiled_extrusion_depth_edit_windows_with_definition",
            side_effect=lambda **kw: (self.payload(), self.definition),
        )
        self.measurement = self.patch(
            "_measurement", side_effect=lambda *args: self.metrics()
        )
        self.empty, self.null = object(), object()
        self.patch("_empty_variant", return_value=self.empty)
        self.patch("_null_dispatch", return_value=self.null)

    def patch(self, member, **options):
        patcher = mock.patch.object(edits, member, **options)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def state(self):
        return edits._state(self.app, self.document)[0]

    def metrics(self):
        return {
            "solid_body_count": 1,
            "volume_mm3": self.depth * 5000,
            "surface_area_mm2": 16000,
            "centroid_mm": {"x": 10, "y": 20, "z": self.depth / 2},
        }

    def payload(self):
        result = deepcopy(self.template)
        result["definition"]["depth_mm"] = self.depth
        result["observation"] = {"after": self.state()}
        result["measurement_after"] = self.metrics()
        return result

    def observe_scope(self, **kwargs):
        self.assertEqual(
            kwargs,
            {"app": self.app, "document": self.document, "feature": self.feature},
        )
        before = self.state()
        self.stamp += 2
        result = self.payload()
        result["observation"]["before"] = before
        return result, self.definition

    def stage(self, forward, depth_m):
        self.assertIs(forward, True)
        self.staged = depth_m * 1000

    def commit(self, definition, document, component):
        self.assertIs(definition, self.definition)
        self.assertIs(document, self.document)
        self.assertIs(component, self.null)
        self.depth = self.staged
        self.stamp += 1
        self.modified = True
        return True

    def set_depth(self, value=25):
        result = edits.set_extrusion_depth_windows(
            app=self.app, document=self.document, feature=self.feature, depth_mm=value
        )
        self.app.ActivateDoc3.assert_not_called()
        self.document.ClearSelection2.assert_not_called()
        self.feature.Select2.assert_not_called()
        # The writer never owns active selection access while staging/committing;
        # the separate tested observer is solely responsible for access/release.
        self.definition.AccessSelections.assert_not_called()
        self.definition.ReleaseSelectionAccess.assert_not_called()
        return result

    def refused(self, code, *, staging=False, committing=False):
        result = self.set_depth()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], code, result)
        self.assertEqual(self.definition.SetDepth.call_count, int(staging))
        self.assertEqual(self.feature.ModifyDefinition.call_count, int(committing))
        self.assertEqual(result["modification_may_have_happened"], staging)
        return result

    def test_success_requires_current_config_exact_commit_and_full_post_scope(self):
        result = self.set_depth()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["depth_changed"])
        self.assertEqual(result["definition_after"]["depth_mm"], 25)
        self.assertEqual(result["measurement_before"]["volume_mm3"], 100000)
        self.assertEqual(result["measurement_after"]["volume_mm3"], 125000)
        self.assertEqual(self.scope.call_count, 2)
        self.definition.SetDepth.assert_called_once_with(True, 0.025)
        self.definition.SetChangeToConfigurations.assert_called_once_with(1, self.empty)
        self.feature.ModifyDefinition.assert_called_once()
        self.document.EditRebuild3.assert_called_once_with()
        self.assertTrue(result["final_state"]["modified"])

    def test_equal_depth_still_observes_scope_but_never_sets_or_rebuilds(self):
        result = self.set_depth(20)
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["depth_changed"])
        self.assertEqual(result["final_state"]["update_stamp"], 19)
        self.assertFalse(result["final_state"]["modified"])
        self.assertEqual(self.scope.call_count, 1)
        self.definition.SetDepth.assert_not_called()
        self.feature.ModifyDefinition.assert_not_called()
        self.document.EditRebuild3.assert_not_called()

    def test_invalid_unresolvable_and_unrepresentable_depth_never_reads_or_mutates(
        self,
    ):
        for value in (
            None,
            False,
            "25",
            -1,
            0,
            1e-7,
            math.inf,
            math.nan,
            1e300,
            10**1000,
        ):
            with self.subTest(value=str(value)[:20]):
                result = self.set_depth(value)
                self.assertEqual(result["error"]["type"], "InvalidArgument", result)
                self.assertFalse(result["modification_may_have_happened"])
                self.scope.assert_not_called()
                self.definition.SetDepth.assert_not_called()

    def test_scope_failure_preserves_nested_release_evidence_without_staging(self):
        self.scope.side_effect = None
        self.scope.return_value = (
            {
                "ok": False,
                "error": {
                    "type": "FeatureSelectionStateNotRestored",
                    "message": "release failed",
                },
                "warnings": [{"code": "release-failed"}],
            },
            None,
        )
        result = self.refused("FeatureSelectionStateNotRestored")
        self.assertIn("warnings", result["preflight"])

    def test_missing_definition_never_stages(self):
        self.scope.side_effect = lambda **kw: (self.payload(), None)
        self.refused("FeatureObservationUnavailable")

    def test_intervening_change_after_scope_preflight_never_stages(self):
        def changed(**kw):
            result, data = self.observe_scope(**kw)
            self.stamp += 1
            return result, data

        self.scope.side_effect = changed
        self.refused("FeatureObservationUnavailable")

    def test_staging_throw_is_not_retried_or_reported_as_no_modification(self):
        self.definition.SetDepth.side_effect = RuntimeError("staging error")
        result = self.refused("RuntimeError", staging=True)
        self.assertIsNone(result["depth_changed"])

    def test_wrong_private_data_readback_prevents_commit(self):
        self.definition.GetDepth.side_effect = None
        self.definition.GetDepth.return_value = 0.02
        self.refused("FeatureDepthStagingFailed", staging=True)

    def test_private_readback_must_be_finite_numeric_not_boolean(self):
        for value in (True, None, "0.025", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.definition.GetDepth.side_effect = None
                self.definition.GetDepth.return_value = value
                self.definition.SetDepth.reset_mock()
                self.refused("FeatureDepthStagingFailed", staging=True)

    def test_configuration_scope_throw_is_not_retried(self):
        self.definition.SetChangeToConfigurations.side_effect = RuntimeError(
            "scope failed"
        )
        self.refused("RuntimeError", staging=True)
        self.definition.SetChangeToConfigurations.assert_called_once()

    def test_live_precommit_guard_failure_preserves_original_error(self):
        self.guard.side_effect = None
        self.guard.return_value = (
            {
                "ok": False,
                "error": {"type": "ModelInvalid", "message": "live model invalid"},
            },
            None,
        )
        result = self.refused("ModelInvalid", staging=True)
        self.assertEqual(result["error"]["message"], "live model invalid")

    def test_configuration_scope_rejection_prevents_commit(self):
        self.definition.SetChangeToConfigurations.return_value = False
        self.refused("FeatureConfigurationScopeFailed", staging=True)

    def test_configuration_scope_status_is_strict_boolean(self):
        self.definition.SetChangeToConfigurations.return_value = 1
        self.refused("FeatureObservationUnavailable", staging=True)

    def test_staging_live_definition_change_prevents_commit(self):
        def changed(forward, value):
            self.stage(forward, value)
            self.depth = self.staged

        self.definition.SetDepth.side_effect = changed
        self.refused("FeatureDepthStagingChangedModel", staging=True)

    def test_staging_geometry_change_prevents_commit(self):
        value = self.metrics()
        value["volume_mm3"] += 1
        self.measurement.side_effect = None
        self.measurement.return_value = value
        self.refused("FeatureDepthStagingChangedModel", staging=True)

    def test_external_stamp_change_before_commit_is_not_ignored(self):
        def changed(*args):
            self.stamp += 1
            return self.metrics()

        self.measurement.side_effect = changed
        self.refused("FeatureObservationUnavailable", staging=True)

    def test_false_commit_can_have_modified_and_is_not_retried_or_undone(self):
        def changed(*args):
            self.commit(*args)
            return False

        self.feature.ModifyDefinition.side_effect = changed
        result = self.refused("FeatureDepthSetFailed", staging=True, committing=True)
        self.assertTrue(result["final_state"]["modified"])
        self.assertIsNone(result["depth_changed"])
        self.document.EditRebuild3.assert_not_called()

    def test_throwing_commit_retains_partial_mutation_evidence(self):
        def changed(*args):
            self.commit(*args)
            raise RuntimeError("commit error")

        self.feature.ModifyDefinition.side_effect = changed
        self.refused("RuntimeError", staging=True, committing=True)

    def test_commit_status_is_strict_boolean(self):
        self.feature.ModifyDefinition.side_effect = None
        self.feature.ModifyDefinition.return_value = 1
        self.refused("FeatureObservationUnavailable", staging=True, committing=True)

    def test_rebuild_failure_does_not_undo_committed_depth(self):
        self.document.EditRebuild3.return_value = False
        result = self.refused("ModelInvalid", staging=True, committing=True)
        self.assertTrue(result["mutation"]["committed"])
        self.assertEqual(self.depth, 25)

    def test_rebuild_status_is_not_truthiness_coerced(self):
        self.document.EditRebuild3.return_value = 1
        self.refused("FeatureObservationUnavailable", staging=True, committing=True)

    def test_postflight_failure_preserves_owned_release_record(self):
        def observed(**kw):
            result, data = self.observe_scope(**kw)
            if self.scope.call_count == 2:
                result["ok"] = False
                result["error"] = {"type": "ModelInvalid", "message": "bad model"}
            return result, data

        self.scope.side_effect = observed
        self.refused("ModelInvalid", staging=True, committing=True)

    def test_successful_com_commit_with_wrong_depth_fails_verification(self):
        def changed(data, doc, component):
            self.staged = 24
            return self.commit(data, doc, component)

        self.feature.ModifyDefinition.side_effect = changed
        self.refused("FeatureDepthVerificationFailed", staging=True, committing=True)

    def test_nondepth_direction_change_is_not_hidden_by_matching_depth(self):
        def changed(*args):
            self.template["definition"]["reverse_direction"] = True
            return self.commit(*args)

        self.feature.ModifyDefinition.side_effect = changed
        self.refused("FeatureDepthVerificationFailed", staging=True, committing=True)

    def test_profile_scope_and_control_changes_fail_verification(self):
        def changed(*args):
            self.template["scope"]["selected_contour_count"] = 1
            return self.commit(*args)

        self.feature.ModifyDefinition.side_effect = changed
        self.refused("FeatureDepthVerificationFailed", staging=True, committing=True)

    def test_postflight_profile_body_and_controls_each_must_match(self):
        for key in ("profile", "body", "controls", "feature"):
            with self.subTest(key=key):
                baseline = deepcopy(self.template)
                self.depth, self.staged = 20.0, 20.0
                self.definition.SetDepth.reset_mock()
                self.feature.ModifyDefinition.reset_mock()

                def changed(*args):
                    self.template[key]["unexpected"] = True
                    return self.commit(*args)

                self.feature.ModifyDefinition.side_effect = changed
                self.refused(
                    "FeatureDepthVerificationFailed", staging=True, committing=True
                )
                self.template = baseline

    def test_foreground_change_before_commit_never_commits(self):
        def staged(*args):
            self.stage(*args)
            self.app.ActiveDoc = SimpleNamespace(identity=object())

        self.definition.SetDepth.side_effect = staged
        self.refused("FeatureObservationUnavailable", staging=True)

    def test_equal_depth_final_stamp_drift_is_not_accepted(self):
        original = edits._state
        checks = 0

        def observed(*args):
            nonlocal checks
            checks += 1
            # Scope uses two reads, writer's state and stable check use two;
            # the final independent state read must detect this later change.
            if checks == 5:
                self.stamp += 1
            return original(*args)

        self.patch("_state", side_effect=observed)
        result = self.set_depth(20)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], "FeatureDepthVerificationFailed")
        self.assertFalse(result["modification_may_have_happened"])
        self.definition.SetDepth.assert_not_called()

    def test_final_stamp_drift_after_verified_commit_is_not_accepted(self):
        original = edits._state
        postflight_reads = 0

        def observed(*args):
            nonlocal postflight_reads
            if self.scope.call_count == 2:
                postflight_reads += 1
                if postflight_reads == 4:
                    self.stamp += 1
            return original(*args)

        self.patch("_state", side_effect=observed)
        self.refused("FeatureDepthVerificationFailed", staging=True, committing=True)

    def test_original_error_survives_failed_final_state_read(self):
        self.definition.SetDepth.side_effect = RuntimeError("first error")
        original = self.document.GetUpdateStamp
        self.document.GetUpdateStamp = lambda: (
            (_ for _ in ()).throw(RuntimeError("final state failed"))
            if self.definition.SetDepth.called
            else original()
        )
        result = self.refused("RuntimeError", staging=True)
        self.assertEqual(result["error"]["message"], "first error")
        self.assertEqual(
            result["warnings"][0]["code"], "feature-depth-final-state-unavailable"
        )


if __name__ == "__main__":
    unittest.main()
