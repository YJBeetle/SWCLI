"""Strict internal feature reads never select, roll back or edit a native model."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts.windows_feature_inspection import (
    inspect_extrusion_feature_windows,
    list_extrusion_features_windows_with_handles,
)


def definition():
    return SimpleNamespace(
        GetDepth=mock.Mock(spec=[], return_value=0.02),
        GetEndCondition=mock.Mock(spec=[], return_value=0),
        ReverseDirection=False,
        BothDirections=False,
        IsThinFeature=mock.Mock(spec=[], return_value=False),
        FromType=0,
        GetDraftWhileExtruding=mock.Mock(spec=[], return_value=False),
        Merge=True,
        FeatureScope=False,
        AccessSelections=mock.Mock(),
        SetDepth=mock.Mock(),
        ReleaseSelectionAccess=mock.Mock(),
    )


class Feature:
    def __init__(self, native_id, kind="Boss", *, identity=None):
        self.identity = object() if identity is None else identity
        self.native_id = native_id
        self.kind = kind
        self.Name = "renamed native feature"
        self.next = self.sub = self.next_sub = None
        self.definition = definition()
        self.GetDefinition = mock.Mock(spec=[], side_effect=lambda: self.definition)
        self.GetTypeName = mock.Mock(spec=[], return_value="Boss")
        self.Select2 = mock.Mock()
        self.ModifyDefinition = mock.Mock()

    def GetID(self):
        return self.native_id

    def GetTypeName2(self):
        return self.kind

    def GetNextFeature(self):
        return self.next

    def GetFirstSubFeature(self):
        return self.sub

    def GetNextSubFeature(self):
        return self.next_sub


class FeatureInspectionTests(unittest.TestCase):
    def setUp(self):
        self.feature = Feature(1)
        self.configuration = SimpleNamespace(Name="Default")
        self.manager = SimpleNamespace(ActiveSketch=None)
        self.modified, self.stamp = False, 17
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            GetUpdateStamp=lambda: self.stamp,
            GetSaveFlag=lambda: self.modified,
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=self.configuration
            ),
            SketchManager=self.manager,
            FirstFeature=lambda: self.feature,
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(),
        )
        # Deliberately observe a background document.
        self.other = SimpleNamespace(identity=object())
        self.app = SimpleNamespace(
            ActiveDoc=self.other,
            IsSame=mock.Mock(side_effect=lambda a, b: int(a.identity is b.identity)),
            ActivateDoc3=mock.Mock(),
        )

    def inspect(self, feature=None):
        return inspect_extrusion_feature_windows(
            app=self.app,
            document=self.document,
            feature=self.feature if feature is None else feature,
        )

    def list(self, **values):
        return list_extrusion_features_windows_with_handles(
            app=self.app,
            document=self.document,
            **values,
        )

    def assert_nonmutating(self):
        self.app.ActivateDoc3.assert_not_called()
        self.document.ClearSelection2.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.feature.Select2.assert_not_called()
        self.feature.ModifyDefinition.assert_not_called()
        self.feature.definition.AccessSelections.assert_not_called()
        self.feature.definition.SetDepth.assert_not_called()
        self.feature.definition.ReleaseSelectionAccess.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.other)

    def test_reads_exact_boss_definition_in_mm_on_background_document(self):
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["feature"]["kind"], "boss-extrude")
        self.assertEqual(
            result["definition"],
            {
                "depth_mm": 20.0,
                "end_condition": 0,
                "reverse_direction": False,
                "both_directions": False,
                "thin": False,
                "from_type": 0,
                "forward_draft": False,
                "reverse_draft": False,
                "merge": True,
            },
        )
        self.assertEqual(
            result["observation"]["before"], result["observation"]["after"]
        )
        self.assertTrue(result["observation"]["unchanged"])
        self.feature.definition.GetDepth.assert_called_once_with(True)
        self.feature.GetTypeName.assert_not_called()
        self.assert_nonmutating()

    def test_cut_reports_native_direction_and_scope_without_boss_merge(self):
        self.feature.kind = "Cut"
        self.feature.definition.ReverseDirection = True
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["feature"]["kind"], "cut-extrude")
        self.assertTrue(result["definition"]["reverse_direction"])
        self.assertFalse(result["definition"]["feature_scope"])
        self.assertNotIn("merge", result["definition"])
        self.assert_nonmutating()

    def test_instant3d_uses_documented_underlying_type_not_feature_name(self):
        self.feature.kind = "ICE"
        self.feature.GetTypeName.return_value = "Cut"
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["feature"]["type"], "ICE")
        self.assertEqual(result["feature"]["native_type"], "Cut")
        self.feature.GetTypeName.assert_called_once_with()
        self.assert_nonmutating()

    def test_list_is_complete_with_explicit_scope_and_exact_handles(self):
        sketch, cut = Feature(2, "ProfileFeature"), Feature(3, "Cut")
        self.feature.sub = sketch
        self.feature.next = cut
        result, handles = self.list()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["scope"], "part-extrusions")
        self.assertEqual(result["count"], 2)
        self.assertEqual(handles, [self.feature, cut])
        self.assertEqual(
            [d["kind"] for d in result["features"]], ["boss-extrude", "cut-extrude"]
        )
        self.assertNotIn("feature_id", result["features"][0])
        self.feature.GetDefinition.assert_not_called()
        cut.GetDefinition.assert_not_called()
        self.assert_nonmutating()

    def test_duplicate_observation_is_deduplicated_by_native_identity(self):
        wrapper = Feature(1, identity=self.feature.identity)
        owner = Feature(2, "Imported")
        self.feature.next = owner
        owner.sub = wrapper
        result, handles = self.list()
        self.assertTrue(result["ok"], result)
        self.assertEqual(handles, [self.feature])

    def test_empty_supported_scope_is_not_an_empty_feature_tree_claim(self):
        self.feature.kind = "ProfileFeature"
        result, handles = self.list()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["scope"], "part-extrusions")
        self.assertEqual(handles, [])

    def test_limits_and_invalid_inputs_never_publish_a_partial_list(self):
        self.feature.next = Feature(2, "Cut")
        result, handles = self.list(max_features=1)
        self.assertEqual(result["error"]["type"], "FeatureListLimitExceeded")
        self.assertNotIn("features", result)
        self.assertEqual(handles, [])
        for value in (0, -1, True, 1.5, "2"):
            with self.subTest(value=value):
                result, handles = self.list(max_features=value)
                self.assertEqual(result["error"]["type"], "InvalidArgument")
                self.assertEqual(handles, [])

    def test_later_cycles_and_id_conflicts_cannot_be_hidden_by_early_target_match(self):
        self.feature.next = Feature(2)
        self.feature.next.next = self.feature.next
        self.assertEqual(self.inspect()["error"]["type"], "FeatureTraversalCycle")
        self.feature.next = Feature(1)
        self.assertEqual(self.inspect()["error"]["type"], "FeatureIdConflict")
        self.feature.GetDefinition.assert_not_called()

    def test_exact_membership_rejects_deleted_and_cross_document_wrappers(self):
        for feature in (Feature(1), Feature(999)):
            with self.subTest(feature=feature):
                result = self.inspect(feature)
                self.assertEqual(result["error"]["type"], "FeatureUnavailable")
                self.assertNotIn("definition", result)
        self.feature.GetDefinition.assert_not_called()

    def test_read_observes_nonblind_and_thin_flags_without_granting_edit_eligibility(
        self,
    ):
        self.feature.definition.GetEndCondition.return_value = 1
        self.feature.definition.GetDepth.return_value = 0
        self.feature.definition.IsThinFeature.return_value = True
        self.feature.definition.BothDirections = True
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["definition"]["depth_mm"], 0)
        self.assertTrue(result["definition"]["thin"])
        self.assertNotIn("editable", result)
        self.assert_nonmutating()

    def test_unsupported_types_and_non_parts_do_not_read_or_edit_definition(self):
        for kind in ("BossThin", "Revolution", "ProfileFeature", "Imported"):
            self.feature.kind = kind
            self.assertEqual(self.inspect()["error"]["type"], "UnsupportedFeatureType")
        self.document.GetType = lambda: 2
        self.assertEqual(self.inspect()["error"]["type"], "UnsupportedDocumentType")
        self.feature.GetDefinition.assert_not_called()
        self.assert_nonmutating()

    def test_missing_and_nonfinite_definition_never_echoes_requested_depth(self):
        self.feature.GetDefinition.return_value = None
        self.feature.GetDefinition.side_effect = None
        self.assertEqual(
            self.inspect()["error"]["type"], "FeatureObservationUnavailable"
        )
        self.feature.GetDefinition.return_value = self.feature.definition
        for value in (None, True, "0.02", -0.01, float("nan"), float("inf"), 1e308):
            self.feature.definition.GetDepth.return_value = value
            with self.subTest(value=value):
                result = self.inspect()
                self.assertEqual(
                    result["error"]["type"], "FeatureObservationUnavailable"
                )
                self.assertNotIn("definition", result)

    def test_invalid_native_flags_and_parameters_fail_closed(self):
        for name, value in (
            ("BothDirections", 1),
            ("Merge", None),
            ("FromType", True),
            ("ReverseDirection", "false"),
        ):
            original = getattr(self.feature.definition, name)
            setattr(self.feature.definition, name, value)
            with self.subTest(name=name):
                self.assertEqual(
                    self.inspect()["error"]["type"], "FeatureObservationUnavailable"
                )
            setattr(self.feature.definition, name, original)

    def test_unobservable_preflight_state_never_reads_definition(self):
        for attr, value in (("stamp", None), ("modified", 0)):
            original = getattr(self, attr)
            setattr(self, attr, value)
            self.assertEqual(
                self.inspect()["error"]["type"], "FeatureObservationUnavailable"
            )
            setattr(self, attr, original)
        self.configuration.Name = ""
        self.assertEqual(
            self.inspect()["error"]["type"], "FeatureObservationUnavailable"
        )
        self.feature.GetDefinition.assert_not_called()

    def test_stamp_modified_configuration_and_foreground_drift_reject_results(self):
        for mutate in (
            lambda: setattr(self, "stamp", 18),
            lambda: setattr(self, "modified", True),
            lambda: setattr(self.configuration, "Name", "Other"),
            lambda: setattr(self.app, "ActiveDoc", SimpleNamespace(identity=object())),
            lambda: setattr(
                self.manager, "ActiveSketch", SimpleNamespace(identity=object())
            ),
        ):
            self.setUp()
            self.feature.definition.GetDepth.side_effect = lambda direction: (
                mutate(),
                0.02,
            )[1]
            result = self.inspect()
            self.assertEqual(result["error"]["type"], "FeatureObservationUnavailable")
            self.assertFalse(result["observation"]["unchanged"])
            self.assertNotIn("definition", result)

    def test_same_edit_wrapper_is_preserved_but_replacement_at_same_stamp_is_rejected(
        self,
    ):
        edit = SimpleNamespace(identity=object())
        self.manager.ActiveSketch = edit
        self.assertTrue(self.inspect()["ok"])
        self.feature.definition.GetDepth.side_effect = lambda direction: (
            setattr(self.manager, "ActiveSketch", SimpleNamespace(identity=object())),
            0.02,
        )[1]
        self.assertFalse(self.inspect()["ok"])

    def test_postflight_failure_keeps_first_native_error_with_state_warning(self):
        def fail(direction):
            self.stamp = None
            raise RuntimeError("original native failure")

        self.feature.definition.GetDepth.side_effect = fail
        result = self.inspect()
        self.assertEqual(result["error"]["message"], "original native failure")
        self.assertEqual(
            result["warnings"][0]["code"], "feature-observation-state-check-failed"
        )
        self.assertNotIn("definition", result)

    def test_invalid_identity_status_is_not_truthiness(self):
        self.app.IsSame.side_effect = None
        for value in (True, 2, "1", None):
            self.app.IsSame.return_value = value
            with self.subTest(value=value):
                self.assertEqual(
                    self.inspect()["error"]["type"], "FeatureObservationUnavailable"
                )
        self.feature.GetDefinition.assert_not_called()


if __name__ == "__main__":
    unittest.main()
