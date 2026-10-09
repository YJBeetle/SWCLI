"""Depth preflight refuses unsafe/unknown controls without native mutation."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts.windows_feature_depth import (
    _running_command,
    prepare_extrusion_depth_edit_windows_with_definition,
)


class FeatureDepthPreflightTests(unittest.TestCase):
    def setUp(self):
        self.definition = SimpleNamespace(
            GetDepth=mock.Mock(spec=[], return_value=0.02),
            GetEndCondition=mock.Mock(spec=[], return_value=0),
            ReverseDirection=False,
            BothDirections=False,
            IsThinFeature=mock.Mock(spec=[], return_value=False),
            FromType=0,
            GetDraftWhileExtruding=mock.Mock(spec=[], return_value=False),
            Merge=True,
            FeatureScope=True,
            AccessSelections=mock.Mock(),
            SetDepth=mock.Mock(),
            ReleaseSelectionAccess=mock.Mock(),
        )
        self.feature = SimpleNamespace(
            identity=object(),
            Name="native boss",
            GetID=lambda: 1,
            GetTypeName2=lambda: "Extrusion",
            GetDefinition=lambda: self.definition,
            GetNextFeature=lambda: None,
            GetFirstSubFeature=lambda: None,
            GetNextSubFeature=lambda: None,
            IsFrozen=mock.Mock(spec=[], return_value=False),
            IsRolledBack=mock.Mock(spec=[], return_value=False),
            IsSuppressed2=mock.Mock(return_value=(False,)),
            ModifyDefinition=mock.Mock(),
            Select2=mock.Mock(),
        )
        self.configuration = SimpleNamespace(Name="Default")
        self.equations = SimpleNamespace(GetCount=mock.Mock(spec=[], return_value=0))
        self.extension = SimpleNamespace(
            HasDesignTable=mock.Mock(spec=[], return_value=False)
        )
        self.sketches = SimpleNamespace(ActiveSketch=None)
        self.stamp, self.modified = 17, False
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            GetUpdateStamp=lambda: self.stamp,
            GetSaveFlag=lambda: self.modified,
            FirstFeature=lambda: self.feature,
            SketchManager=self.sketches,
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=self.configuration
            ),
            GetConfigurationNames=mock.Mock(spec=[], return_value=("Default",)),
            GetConfigurationCount=mock.Mock(spec=[], return_value=1),
            GetEquationMgr=lambda: self.equations,
            Extension=self.extension,
            IsOpenedReadOnly=mock.Mock(spec=[], return_value=False),
            IsOpenedViewOnly=mock.Mock(spec=[], return_value=False),
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(),
        )
        self.foreground = SimpleNamespace(identity=object())
        self.app = SimpleNamespace(
            ActiveDoc=self.foreground,
            IsSame=lambda a, b: int(a.identity is b.identity),
            ActivateDoc3=mock.Mock(),
        )
        self.empty = object()
        self.variant_patch = mock.patch(
            "swcli.hosts.windows_feature_depth._empty_variant", return_value=self.empty
        )
        self.variant_patch.start()
        self.addCleanup(self.variant_patch.stop)
        self.command_patch = mock.patch(
            "swcli.hosts.windows_feature_depth._running_command",
            return_value={"command_id": 0, "title": "", "ui_active": False},
        )
        self.command = self.command_patch.start()
        self.addCleanup(self.command_patch.stop)

    def tearDown(self):
        self.app.ActivateDoc3.assert_not_called()
        self.document.ClearSelection2.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.feature.Select2.assert_not_called()
        self.feature.ModifyDefinition.assert_not_called()
        self.definition.AccessSelections.assert_not_called()
        self.definition.SetDepth.assert_not_called()
        self.definition.ReleaseSelectionAccess.assert_not_called()

    def prepare(self, **values):
        return prepare_extrusion_depth_edit_windows_with_definition(
            app=self.app,
            document=self.document,
            feature=values.get("feature", self.feature),
        )

    def refused(self, error_type):
        result, definition = self.prepare()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], error_type, result)
        self.assertIsNone(definition)
        self.assertNotIn("definition", result)
        self.assertNotIn("controls", result)

    def test_success_returns_exact_definition_without_granting_public_write(self):
        result, definition = self.prepare()
        self.assertTrue(result["ok"], result)
        self.assertIs(definition, self.definition)
        self.assertEqual(result["controls"]["configurations"], ["Default"])
        self.assertEqual(result["controls"]["equation_count"], 0)
        self.assertFalse(result["controls"]["has_design_table"])
        self.assertTrue(result["observation"]["unchanged"])
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.feature.IsSuppressed2.assert_has_calls([mock.call(1, self.empty)] * 2)
        self.assertEqual(self.command.call_count, 2)

    def test_cross_document_or_deleted_feature_never_yields_a_definition(self):
        foreign = deepcopy(self.feature)
        foreign.identity = object()
        result, definition = self.prepare(feature=foreign)
        self.assertEqual(result["error"]["type"], "FeatureUnavailable")
        self.assertIsNone(definition)
        self.command.assert_not_called()

    def test_part_only_and_existing_sketch_edits_are_rejected(self):
        self.document.GetType = lambda: 2
        self.refused("UnsupportedDocumentType")
        self.document.GetType = lambda: 1
        self.sketches.ActiveSketch = SimpleNamespace(identity=object())
        self.refused("SketchEditInProgress")

    def test_read_only_or_view_only_parts_are_not_made_writable(self):
        for member in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            with self.subTest(member=member):
                method = getattr(self.document, member)
                method.return_value = True
                self.refused("DocumentNotWritable")
                method.return_value = False

    def test_any_active_native_command_is_not_cancelled_or_overridden(self):
        self.command.return_value = {
            "command_id": 1,
            "title": "Extrude",
            "ui_active": True,
        }
        self.refused("NativeCommandInProgress")

    def test_suppression_freeze_and_rollback_are_not_overridden(self):
        for member, value in (
            ("IsSuppressed2", (True,)),
            ("IsFrozen", True),
            ("IsRolledBack", True),
        ):
            with self.subTest(member=member):
                method = getattr(self.feature, member)
                old = method.return_value
                method.return_value = value
                self.refused("FeatureProtectedState")
                method.return_value = old

    def test_any_equations_or_design_table_are_conservatively_refused(self):
        self.equations.GetCount.return_value = 1
        self.refused("FeatureControlScopeUnsupported")
        self.equations.GetCount.return_value = 0
        self.extension.HasDesignTable.return_value = True
        self.refused("FeatureControlScopeUnsupported")

    def test_multi_configuration_parts_are_not_silently_edited_everywhere(self):
        self.document.GetConfigurationNames.return_value = ("Default", "Other")
        self.document.GetConfigurationCount.return_value = 2
        self.refused("FeatureConfigurationScopeUnsupported")

    def test_single_direction_solid_blind_definition_is_required(self):
        for member, value in (
            ("GetDepth", 0),
            ("GetEndCondition", 1),
            ("BothDirections", True),
            ("IsThinFeature", True),
            ("FromType", 1),
        ):
            with self.subTest(member=member):
                old = getattr(self.definition, member)
                if callable(old):
                    previous = old.return_value
                    old.return_value = value
                else:
                    setattr(self.definition, member, value)
                self.refused("UnsupportedDepthDefinition")
                if callable(old):
                    old.return_value = previous
                else:
                    setattr(self.definition, member, old)
        for values in ((True, False), (False, True)):
            self.definition.GetDraftWhileExtruding.side_effect = list(values)
            self.refused("UnsupportedDepthDefinition")

    def test_unreadable_native_flags_are_not_coerced_to_booleans(self):
        for method in (
            self.document.IsOpenedReadOnly,
            self.document.IsOpenedViewOnly,
            self.extension.HasDesignTable,
            self.feature.IsFrozen,
            self.feature.IsRolledBack,
        ):
            for value in (None, 0, 1, "false", "true", object()):
                method.return_value = value
                self.refused("FeatureObservationUnavailable")
            method.return_value = False

    def test_suppression_requires_one_native_boolean_in_current_configuration(self):
        for value in (None, False, (), (False, False), (0,), ("false",)):
            self.feature.IsSuppressed2.return_value = value
            self.refused("FeatureObservationUnavailable")

    def test_equation_manager_and_count_must_be_observable(self):
        for value in (-1, True, "0", None, 10001):
            self.equations.GetCount.return_value = value
            self.refused("FeatureObservationUnavailable")
        self.equations = None
        self.refused("FeatureObservationUnavailable")

    def test_complete_configuration_names_and_strict_count_are_required(self):
        for count, names in (
            (True, ("Default",)),
            (0, ()),
            (1, None),
            (1, "Default"),
            (1, ("Other",)),
            (2, ("Default",)),
            (2, ("Default", "Default")),
            (1, ("",)),
            (1, (None,)),
        ):
            self.document.GetConfigurationCount.return_value = count
            self.document.GetConfigurationNames.return_value = names
            self.refused("FeatureObservationUnavailable")

    def test_changed_definition_or_controls_never_publish_usable_preflight(self):
        self.definition.GetDepth.side_effect = [0.02, 0.03]
        self.refused("FeatureObservationUnavailable")
        self.definition.GetDepth.side_effect = None
        self.feature.IsFrozen.side_effect = [False, True]
        self.refused("FeatureObservationUnavailable")

    def test_changed_stamp_is_detected(self):
        def change_stamp(*args):
            self.stamp += 1
            return (False,)

        self.feature.IsSuppressed2.side_effect = change_stamp
        self.refused("FeatureObservationUnavailable")

    def test_changed_foreground_or_configuration_is_detected(self):
        for change in ("foreground", "configuration"):
            with self.subTest(change=change):
                self.app.ActiveDoc = self.foreground
                self.configuration.Name = "Default"

                def mutate(*args):
                    if change == "foreground":
                        self.app.ActiveDoc = SimpleNamespace(identity=object())
                    else:
                        self.configuration.Name = "Other"
                    return (False,)

                self.feature.IsSuppressed2.side_effect = mutate
                self.refused("FeatureObservationUnavailable")

    def test_cut_uses_same_guard_and_keeps_native_direction_and_scope(self):
        self.feature.GetTypeName2 = lambda: "ICE"
        self.feature.GetTypeName = lambda: "Cut"
        self.definition.ReverseDirection = True
        result, definition = self.prepare()
        self.assertTrue(result["ok"], result)
        self.assertIs(definition, self.definition)
        self.assertEqual(result["feature"]["kind"], "cut-extrude")
        self.assertTrue(result["definition"]["reverse_direction"])
        self.assertTrue(result["definition"]["feature_scope"])

    def test_native_exception_is_not_a_false_positive_and_keeps_first_error(self):
        self.feature.IsSuppressed2.side_effect = RuntimeError("suppression unavailable")
        self.document.GetUpdateStamp = mock.Mock(
            spec=[], side_effect=[17, 17, 17, RuntimeError("postflight unavailable")]
        )
        result, definition = self.prepare()
        self.assertEqual(result["error"]["message"], "suppression unavailable")
        self.assertEqual(
            result["warnings"][0]["code"], "feature-observation-state-check-failed"
        )
        self.assertIsNone(definition)


class RunningCommandBindingTests(unittest.TestCase):
    def running(self, values):
        class Variant:
            def __init__(self, kind, value):
                self.value = value

        app = SimpleNamespace(
            GetRunningCommandInfo=lambda *args: [
                setattr(v, "value", value) for v, value in zip(args, values)
            ]
        )
        modules = {
            "pythoncom": SimpleNamespace(
                VT_BYREF=0x4000, VT_I4=3, VT_BSTR=8, VT_BOOL=11
            ),
            "win32com.client": SimpleNamespace(VARIANT=Variant),
        }
        with mock.patch.dict("sys.modules", modules):
            return _running_command(app)

    def test_explicit_native_outputs_are_read_without_truthiness(self):
        self.assertEqual(
            self.running([0, "", False]),
            {"command_id": 0, "title": "", "ui_active": False},
        )
        self.assertTrue(self.running([42, "Extrude", True])["ui_active"])

    def test_bad_command_outputs_fail_closed(self):
        for values in (
            [True, "", False],
            [0, None, True],
            [0, "", 0],
            [0, "", "false"],
        ):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                self.running(values)

    def test_unwritten_native_outputs_are_not_idle_proof(self):
        with self.assertRaises(RuntimeError):
            self.running([])

    def test_idle_requires_explicit_false_even_when_native_title_is_unwritten(self):
        idle = self.running([-3, "__swcli_command_output_unset__", False])
        self.assertEqual(idle, {"command_id": -3, "title": None, "ui_active": False})
        with self.assertRaises(RuntimeError):
            self.running([-3, "__swcli_command_output_unset__", True])


if __name__ == "__main__":
    unittest.main()
