"""Explicit fixed-center creation, no implicit constraints or recovery claims."""

import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_rectangle_constraints as constraints
from swcli.hosts import windows_dimensions
import test_windows_rectangle_center as center_fixtures


class RectangleCenterFixTests(unittest.TestCase):
    point = center_fixtures.RectangleCenterTests.point
    line = center_fixtures.RectangleCenterTests.line
    relation = center_fixtures.RectangleCenterTests.relation

    def setUp(self):
        center_fixtures.RectangleCenterTests.setUp(self)
        self.feature.GetOwnerFeature = lambda: None
        self.feature.Select2 = mock.Mock(return_value=True)
        self.sketch.GetConstrainedStatus = lambda: 2
        self.manager.InsertSketch = mock.Mock(side_effect=self.exit_edit)
        self.document.ClearSelection2 = mock.Mock()
        self.document.EditSketch = mock.Mock(spec=(), side_effect=self.enter_edit)
        self.created = self.relation(17, [2], [self.point(0, 3, 4)])
        self.native_manager = SimpleNamespace(
            AddRelation=mock.Mock(side_effect=self.add_relation)
        )
        self.sketch.RelationManager = self.native_manager
        patcher = mock.patch.object(
            constraints, "_variant", side_effect=lambda kind, value: (kind, value)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def enter_edit(self):
        self.manager.ActiveSketch = self.sketch

    def exit_edit(self, update):
        self.manager.ActiveSketch = None

    def add_relation(self, entities, kind):
        self.relations.append(self.created)
        return self.created

    def call(self):
        return constraints.fix_rectangle_center_windows_with_handle(
            app=self.app, document=self.document, sketch_feature=self.feature
        )

    def assert_failed(self, result, code):
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["type"], code, result)
        json.dumps(result, allow_nan=False)

    def test_exact_point_dispatch_array_relation_and_geometry_verified_after_exit(self):
        result, relation = self.call()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["created"])
        self.assertIs(relation, self.created)
        self.native_manager.AddRelation.assert_called_once_with(
            ("dispatch-array", (self.center,)), 17
        )
        self.assertTrue(result["center"]["fixed"])
        self.assertTrue(result["center"]["attached_to_both_diagonals"])
        self.assertTrue(result["geometry_verification"]["passed"])
        self.assertIsNone(self.manager.ActiveSketch)
        self.assertFalse(result["editing"])
        self.manager.InsertSketch.assert_called_once_with(True)
        self.assertFalse(hasattr(self.app, "SetUserPreferenceToggle"))
        self.assertFalse(hasattr(self.document, "SketchAddConstraints"))
        json.dumps(result, allow_nan=False)

    def test_native_variant_flags_preserve_scalar_types_and_add_dispatch_array(self):
        variant = mock.Mock(return_value="variant")
        native = SimpleNamespace(VT_DISPATCH=9, VT_EMPTY=0, VT_ARRAY=8192, VT_R8=5)
        with mock.patch.dict(
            "sys.modules",
            {
                "pythoncom": native,
                "win32com": SimpleNamespace(),
                "win32com.client": SimpleNamespace(VARIANT=variant),
            },
        ):
            for kind, flag, value in (
                ("dispatch", 9, None),
                ("empty", 0, None),
                ("double-array", 8197, (0.0,)),
                ("dispatch-array", 8201, (self.center,)),
            ):
                self.assertEqual(windows_dimensions._variant(kind, value), "variant")
                variant.assert_called_with(flag, value)

    def test_variant_failure_prevents_native_mutation_and_closes_owned_edit(self):
        constraints._variant.side_effect = RuntimeError("variant")
        result, relation = self.call()
        self.assert_failed(result, "RuntimeError")
        self.assertIsNone(relation)
        self.native_manager.AddRelation.assert_not_called()
        self.assertIsNone(self.manager.ActiveSketch)
        self.assertNotIn("modification_may_have_happened", result)

    def test_existing_verified_fix_is_read_only_noop_not_duplicate(self):
        self.relations.append(self.created)
        self.sketch.GetConstrainedStatus = lambda: 3
        result, relation = self.call()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["created"])
        self.assertIs(relation, self.created)
        self.document.ClearSelection2.assert_not_called()
        self.document.EditSketch.assert_not_called()
        self.native_manager.AddRelation.assert_not_called()

    def test_part_only_existing_edit_and_absorbed_profile_refuse_before_selection(self):
        for field, code in (
            ("type", "UnsupportedDocumentType"),
            ("edit", "SketchEditInProgress"),
            ("absorbed", "SketchUnavailable"),
        ):
            with self.subTest(field=field):
                self.setUp()
                if field == "type":
                    self.document.GetType = lambda: 2
                elif field == "edit":
                    self.manager.ActiveSketch = SimpleNamespace()
                else:
                    self.feature.GetOwnerFeature = lambda: SimpleNamespace()
                result, relation = self.call()
                self.assert_failed(result, code)
                self.assertIsNone(relation)
                self.document.EditSketch.assert_not_called()
                self.document.ClearSelection2.assert_not_called()
                self.native_manager.AddRelation.assert_not_called()

    def test_additional_origin_relation_refuses_before_any_mutation(self):
        self.relations.append(
            self.relation(9, [2, 2], [self.center, self.point(20, 0, 0)])
        )
        result, relation = self.call()
        self.assert_failed(result, "UnsupportedCenterConstraint")
        self.assertIsNone(relation)
        self.document.EditSketch.assert_not_called()
        self.native_manager.AddRelation.assert_not_called()
        self.assertNotIn("modification_may_have_happened", result)

    def test_existing_invalid_unknown_or_disabled_solver_is_not_silent_success(self):
        for status in (1, 4, 5, 6, 7, 0, 8, True, 2.0, "2", None):
            with self.subTest(status=status):
                self.sketch.GetConstrainedStatus = lambda: status
                result, relation = self.call()
                self.assert_failed(
                    result,
                    (
                        "UnsupportedCenterConstraint"
                        if type(status) is int
                        else "ConstraintObservationUnavailable"
                    ),
                )
                self.assertIsNone(relation)
                self.native_manager.AddRelation.assert_not_called()

    def test_fully_constrained_unfixed_profile_is_not_given_redundant_constraint(self):
        self.sketch.GetConstrainedStatus = lambda: 3
        result, _ = self.call()
        self.assert_failed(result, "UnsupportedCenterConstraint")
        self.native_manager.AddRelation.assert_not_called()

    def test_changing_preflight_state_refuses_before_edit(self):
        self.document.GetUpdateStamp = mock.Mock(spec=(), side_effect=[17, 18])
        result, _ = self.call()
        self.assert_failed(result, "ConstraintObservationUnavailable")
        self.document.EditSketch.assert_not_called()

    def test_selection_failure_cleans_selection_without_native_creation(self):
        self.feature.Select2.return_value = False
        result, _ = self.call()
        self.assert_failed(result, "SketchSelectionFailed")
        self.native_manager.AddRelation.assert_not_called()
        self.document.ClearSelection2.assert_has_calls(
            [mock.call(True), mock.call(True)]
        )

    def test_wrong_edit_is_not_closed_during_cleanup(self):
        self.document.EditSketch.side_effect = lambda: setattr(
            self.manager, "ActiveSketch", SimpleNamespace()
        )
        result, _ = self.call()
        self.assert_failed(result, "SketchUnavailable")
        self.manager.InsertSketch.assert_not_called()
        self.native_manager.AddRelation.assert_not_called()
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")

    def test_native_exception_may_have_mutated_no_retry_and_owned_edit_exits(self):
        def failed(*args):
            self.relations.append(self.created)
            raise RuntimeError("native relation failure")

        self.native_manager.AddRelation.side_effect = failed
        result, relation = self.call()
        self.assert_failed(result, "RuntimeError")
        self.assertTrue(result["modification_may_have_happened"])
        self.assertIsNone(relation)
        self.assertIsNone(self.manager.ActiveSketch)
        self.native_manager.AddRelation.assert_called_once()
        self.assertEqual(len(self.relations), 3)

    def test_null_return_is_failure_even_when_native_relation_was_added(self):
        def missing(*args):
            self.relations.append(self.created)
            return None

        self.native_manager.AddRelation.side_effect = missing
        result, relation = self.call()
        self.assert_failed(result, "ConstraintCreationFailed")
        self.assertTrue(result["modification_may_have_happened"])
        self.assertIsNone(relation)

    def test_wrong_returned_relation_or_absent_point_readback_retains_exact_evidence(
        self,
    ):
        self.created.GetRelationType = lambda: 9
        result, relation = self.call()
        self.assertFalse(result["ok"])
        self.assertIs(relation, self.created)
        self.assertTrue(result["modification_may_have_happened"])
        self.setUp()
        self.native_manager.AddRelation.side_effect = lambda *args: self.created
        result, relation = self.call()
        self.assert_failed(result, "ConstraintVerificationFailed")
        self.assertIs(relation, self.created)

    def test_foreign_fixed_point_with_same_id_is_rejected(self):
        foreign = self.point(0, 3, 4)
        foreign.GetSketch = lambda: SimpleNamespace()
        self.created.GetEntities = lambda: [foreign]
        result, relation = self.call()
        self.assert_failed(result, "ConstraintObservationUnavailable")
        self.assertIs(relation, self.created)

    def test_post_add_unknown_or_overconstrained_solver_cannot_pass(self):
        def overconstrained(*args):
            self.sketch.GetConstrainedStatus = lambda: 4
            return self.add_relation(*args)

        self.native_manager.AddRelation.side_effect = overconstrained
        result, relation = self.call()
        self.assert_failed(result, "ConstraintVerificationFailed")
        self.assertIs(relation, self.created)
        self.assertTrue(result["modification_may_have_happened"])

    def test_configuration_change_cannot_be_hidden_by_relation_success(self):
        def changed(*args):
            self.document.ConfigurationManager.ActiveConfiguration.Name = "Other"
            return self.add_relation(*args)

        self.native_manager.AddRelation.side_effect = changed
        result, _ = self.call()
        self.assert_failed(result, "ConstraintVerificationFailed")
        self.assertTrue(result["modification_may_have_happened"])

    def test_point_drift_or_topology_replacement_cannot_pass(self):
        for changed in ("point", "diagonal"):
            with self.subTest(changed=changed):
                self.setUp()

                def corrupt(*args):
                    if changed == "point":
                        self.center.X += 0.001
                    else:
                        self.diagonals[0].GetID = lambda: (25, 26)
                    return self.add_relation(*args)

                self.native_manager.AddRelation.side_effect = corrupt
                result, _ = self.call()
                self.assertFalse(result["ok"])
                self.assertTrue(result["modification_may_have_happened"])

    def test_relation_lost_or_suppressed_after_exit_cannot_pass(self):
        for mode in ("lost", "suppressed"):
            with self.subTest(mode=mode):
                self.setUp()

                def exit_changed(update):
                    self.exit_edit(update)
                    if mode == "lost":
                        self.relations.remove(self.created)
                    else:
                        self.created.Suppressed = True

                self.manager.InsertSketch.side_effect = exit_changed
                result, relation = self.call()
                self.assertFalse(result["ok"])
                self.assertIs(relation, self.created)
                self.assertTrue(result["modification_may_have_happened"])

    def test_failed_exit_retains_primary_error_when_cleanup_cannot_exit(self):
        self.manager.InsertSketch.side_effect = [RuntimeError("exit"), None]
        result, relation = self.call()
        self.assert_failed(result, "RuntimeError")
        self.assertIs(relation, self.created)
        self.assertTrue(result["modification_may_have_happened"])
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")

    def test_failed_exit_stays_failure_even_when_owned_cleanup_succeeds(self):
        calls = 0

        def exit_twice(update):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("exit")
            self.exit_edit(update)

        self.manager.InsertSketch.side_effect = exit_twice
        result, relation = self.call()
        self.assert_failed(result, "RuntimeError")
        self.assertIs(relation, self.created)
        self.assertIsNone(self.manager.ActiveSketch)
        self.assertNotIn("warnings", result)

    def test_foreign_edit_after_creation_is_not_closed(self):
        def replaced(*args):
            self.manager.ActiveSketch = SimpleNamespace()
            raise RuntimeError("other edit")

        self.native_manager.AddRelation.side_effect = replaced
        result, _ = self.call()
        self.assert_failed(result, "RuntimeError")
        self.manager.InsertSketch.assert_not_called()
        self.assertTrue(result["editing"])

    def test_successful_native_creation_cannot_close_a_new_foreign_edit(self):
        def replaced(*args):
            relation = self.add_relation(*args)
            self.manager.ActiveSketch = SimpleNamespace()
            return relation

        self.native_manager.AddRelation.side_effect = replaced
        result, relation = self.call()
        self.assert_failed(result, "ConstraintVerificationFailed")
        self.assertIs(relation, self.created)
        self.manager.InsertSketch.assert_not_called()
        self.assertTrue(result["editing"])
        self.assertTrue(result["modification_may_have_happened"])

    def test_cleanup_failure_invalidates_success_and_keeps_partial_handle(self):
        self.document.ClearSelection2.side_effect = [None, RuntimeError("selection")]
        result, relation = self.call()
        self.assert_failed(result, "ConstraintCleanupFailed")
        self.assertIs(relation, self.created)
        self.assertTrue(result["modification_may_have_happened"])
        self.assertEqual(result["warnings"][0]["code"], "selection-cleanup-failed")

    def test_primary_error_is_retained_when_selection_cleanup_also_fails(self):
        self.native_manager.AddRelation.side_effect = RuntimeError("primary")
        self.document.ClearSelection2.side_effect = [None, RuntimeError("cleanup")]
        result, _ = self.call()
        self.assert_failed(result, "RuntimeError")
        self.assertEqual(result["error"]["message"], "primary")
        self.assertEqual(result["warnings"][0]["message"], "cleanup")


if __name__ == "__main__":
    unittest.main()
