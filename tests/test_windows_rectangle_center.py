"""Native owner/type/ID identity, exact attachment and read-only boundaries."""

import itertools
import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_rectangle_center as centers


class RectangleCenterTests(unittest.TestCase):
    def setUp(self):
        self.sketch = SimpleNamespace()
        self.app = SimpleNamespace(IsSame=lambda first, second: int(first is second))
        self.corners = [
            self.point(i + 1, x, y, kind=0)
            for i, (x, y) in enumerate(((-17, -11), (23, -11), (23, 19), (-17, 19)))
        ]
        self.center = self.point(0, 3, 4)
        self.points = [self.center, *self.corners]
        self.edges = [
            self.line(i + 1, self.corners[i], self.corners[(i + 1) % 4])
            for i in range(4)
        ]
        self.diagonals = [
            self.line(5, self.corners[0], self.corners[2], True),
            self.line(6, self.corners[1], self.corners[3], True),
        ]
        self.segments = self.edges + self.diagonals
        self.relations = [
            self.relation(9, [2, 3], [self.center, line]) for line in self.diagonals
        ]
        self.center.GetRelations = lambda: self.relations
        self.center.GetRelationsCount = lambda: len(self.relations)
        self.sketch.GetSketchSegments = lambda: self.segments
        self.sketch.GetSketchPoints2 = lambda: self.points
        self.feature = SimpleNamespace(
            GetID=lambda: 17,
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda: self.sketch,
            GetNextFeature=lambda: None,
            GetFirstSubFeature=lambda: None,
            GetNextSubFeature=lambda: None,
        )
        self.manager = SimpleNamespace(ActiveSketch=None)
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            GetUpdateStamp=lambda: 17,
            SketchManager=self.manager,
            FirstFeature=lambda: self.feature,
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="Default")
            ),
        )

    def point(self, identity, x, y, kind=1):
        return SimpleNamespace(
            X=x / 1000,
            Y=y / 1000,
            Z=0,
            Type=kind,
            GetID=lambda: (identity, identity + 1),
            GetSketch=lambda: self.sketch,
        )

    def line(self, identity, start, end, construction=False):
        return SimpleNamespace(
            GetID=lambda: (identity, identity + 1),
            GetSketch=lambda: self.sketch,
            ConstructionGeometry=construction,
            GetType=lambda: 0,
            GetStartPoint2=lambda: start,
            GetEndPoint2=lambda: end,
        )

    def relation(self, kind, types, entities):
        return SimpleNamespace(
            GetRelationType=lambda: kind,
            Suppressed=False,
            GetEntitiesCount=lambda: len(entities),
            GetEntitiesType=lambda: types,
            GetEntities=lambda: entities,
            GetDefinitionEntities2=lambda: entities,
        )

    def observe(self):
        return centers.observe_rectangle_center(self.app, self.sketch)

    def inspect(self):
        return centers.inspect_rectangle_center_windows(
            app=self.app, document=self.document, sketch_feature=self.feature
        )

    def assert_error(self, code):
        with self.assertRaises(centers._DimensionError) as caught:
            self.observe()
        self.assertEqual(caught.exception.code, code)

    def test_exact_unfixed_center_native_identity_and_serializable_evidence(self):
        center = self.observe()
        self.assertIs(center.point, self.center)
        self.assertIsNone(center.fixed_relation)
        self.assertEqual(center.point_id, (0, 1))
        evidence = center.evidence()
        self.assertTrue(evidence["attached_to_both_diagonals"])
        self.assertFalse(evidence["fixed"])
        self.assertEqual(evidence["geometry"]["center_mm"], {"x": 3, "y": 4, "z": 0})
        json.dumps(evidence, allow_nan=False)

    def test_same_typed_native_ids_in_other_wrappers_do_not_require_point_issame(self):
        point = self.point(0, 3, 4)
        lines = [
            self.line(5, self.corners[0], self.corners[2], True),
            self.line(6, self.corners[1], self.corners[3], True),
        ]
        self.assertEqual(self.app.IsSame(point, self.center), 0)
        self.relations = [self.relation(9, [3, 2], [line, point]) for line in lines]
        self.assertIs(self.observe().point, self.center)

    def test_entity_kind_scopes_ids_point_and_line_may_share_pair(self):
        self.diagonals[0].GetID = self.center.GetID
        self.assertEqual(len(self.observe().diagonals), 2)

    def test_shuffled_segments_points_relations_and_reversed_endpoints(self):
        for order in itertools.permutations(range(3)):
            self.segments = (
                [self.edges[i] for i in order] + [self.edges[3]] + self.diagonals[::-1]
            )
            self.points = self.points[::-1]
            self.relations = self.relations[::-1]
            self.assertEqual(self.observe().point_id, (0, 1))
        for line in self.segments:
            line.GetStartPoint2, line.GetEndPoint2 = (
                line.GetEndPoint2,
                line.GetStartPoint2,
            )
        self.assertEqual(self.observe().point_id, (0, 1))

    def test_one_exact_unsuppressed_fixed_point_is_observed(self):
        relation = self.relation(17, [2], [self.point(0, 3, 4)])
        self.relations.append(relation)
        self.assertIs(self.observe().fixed_relation, relation)
        self.assertTrue(self.observe().evidence()["fixed"])

    def test_no_diagonals_extra_construction_or_profile_is_outside_slice(self):
        for collection in (
            self.edges,
            self.segments + [self.diagonals[0]],
            self.segments + [self.edges[0]],
        ):
            with self.subTest(collection=collection):
                self.sketch.GetSketchSegments = lambda: collection
                self.assert_error(
                    "UnsupportedCenterConstraint"
                    if collection is self.edges
                    or len(collection) == 7
                    and collection[-1] is self.diagonals[0]
                    else "UnsupportedDimensionProfile"
                )

    def test_native_ids_are_exact_bounded_integer_pairs_not_coerced(self):
        for invalid in (
            None,
            True,
            (),
            (1,),
            (1, 2, 3),
            (True, 1),
            (0.0, 1),
            ("0", 1),
            (2**31, 1),
            (-(2**31) - 1, 1),
        ):
            with self.subTest(invalid=invalid):
                self.center.GetID = lambda: invalid
                self.assert_error("ConstraintObservationUnavailable")

    def test_all_entities_and_endpoint_wrappers_require_exact_sketch_owner(self):
        for entity in (self.center, self.corners[0], self.diagonals[0], self.edges[0]):
            with self.subTest(entity=entity):
                entity.GetSketch = lambda: SimpleNamespace()
                self.assert_error("ConstraintObservationUnavailable")
                entity.GetSketch = lambda: self.sketch

    def test_unsupported_owner_comparison_never_falls_back_to_ids(self):
        self.app.IsSame = lambda *args: 2
        self.assert_error("DimensionObservationUnavailable")

    def test_foreign_relation_points_cannot_reuse_local_ids(self):
        foreign = self.point(0, 3, 4)
        foreign.GetSketch = lambda: SimpleNamespace()
        self.relations[0].GetEntities = lambda: [foreign, self.diagonals[0]]
        self.assert_error("ConstraintObservationUnavailable")

    def test_native_corner_connectivity_not_coordinate_coincidence(self):
        fake = self.point(20, -17, -11, kind=0)
        self.edges[0].GetStartPoint2 = lambda: fake
        self.assert_error("UnsupportedCenterConstraint")

    def test_diagonal_endpoints_are_exact_corners_not_same_coordinates(self):
        fake = self.point(20, -17, -11, kind=0)
        self.diagonals[0].GetStartPoint2 = lambda: fake
        self.assert_error("UnsupportedCenterConstraint")

    def test_duplicate_line_or_corner_ids_are_not_accepted(self):
        self.diagonals[1].GetID = self.diagonals[0].GetID
        self.assert_error("ConstraintObservationUnavailable")
        self.setUp()
        self.corners[1].GetID = self.corners[0].GetID
        self.assert_error("ConstraintObservationUnavailable")

    def test_construction_sides_cannot_masquerade_as_diagonals(self):
        self.diagonals[0].GetEndPoint2 = lambda: self.corners[1]
        self.assert_error("UnsupportedCenterConstraint")

    def test_missing_duplicate_or_loose_center_points_are_not_repaired(self):
        loose = self.point(20, 3, 4)
        loose.GetRelations = lambda: []
        loose.GetRelationsCount = lambda: 0
        for points in (
            self.corners,
            [*self.points, self.point(20, 3, 4)],
            [loose, *self.corners],
        ):
            with self.subTest(points=points):
                self.points = points
                self.assert_error("UnsupportedCenterConstraint")

    def test_point_collection_coordinates_and_native_corner_ids_must_agree(self):
        self.points[1] = self.point(1, -16, -11, kind=0)
        self.assert_error("UnsupportedCenterConstraint")

    def test_missing_duplicate_or_wrong_diagonal_relations_are_not_attachment(self):
        for relations in (self.relations[:1], [self.relations[0]] * 2):
            with self.subTest(relations=relations):
                self.relations = relations
                self.assert_error("UnsupportedCenterConstraint")
        self.setUp()
        self.relations[0].GetEntities = lambda: [self.center, self.edges[0]]
        self.assert_error("UnsupportedCenterConstraint")

    def test_fixed_line_extra_fixed_or_fixed_wrong_point_is_not_center_fix(self):
        for relation in (
            self.relation(17, [3], [self.diagonals[0]]),
            self.relation(17, [2], [self.corners[0]]),
        ):
            with self.subTest(relation=relation):
                self.relations.append(relation)
                self.assert_error("UnsupportedCenterConstraint")
                self.relations.pop()
        self.relations += [self.relation(17, [2], [self.center])] * 2
        self.assert_error("UnsupportedCenterConstraint")

    def test_additional_origin_or_unknown_constraint_is_refused_not_overridden(self):
        for relation in (
            self.relation(9, [2, 2], [self.center, self.point(20, 0, 0)]),
            self.relation(12, [2, 3], [self.center, self.diagonals[0]]),
        ):
            with self.subTest(relation=relation):
                self.relations.append(relation)
                self.assert_error("UnsupportedCenterConstraint")
                self.relations.pop()

    def test_suppressed_relations_never_prove_attachment_or_fix(self):
        self.relations[0].Suppressed = True
        self.assert_error("UnsupportedCenterConstraint")
        self.relations[0].Suppressed = 0
        self.assert_error("ConstraintObservationUnavailable")

    def test_null_malformed_and_count_mismatched_relation_metadata(self):
        for member, invalid in (
            ("GetEntitiesCount", 1),
            ("GetEntitiesCount", True),
            ("GetEntities", None),
            ("GetEntities", [self.center, None]),
            ("GetEntitiesType", [True, 3]),
            ("GetDefinitionEntities2", [self.center]),
        ):
            with self.subTest(member=member, invalid=invalid):
                self.setUp()
                setattr(self.relations[0], member, lambda: invalid)
                self.assert_error("ConstraintObservationUnavailable")

    def test_relation_definition_and_internal_entities_must_match(self):
        self.relations[0].GetDefinitionEntities2 = lambda: [
            self.center,
            self.diagonals[1],
        ]
        self.assert_error("UnsupportedCenterConstraint")

    def test_collections_and_safety_limits_fail_closed(self):
        for member, invalid in (
            ("GetSketchPoints2", None),
            ("GetSketchPoints2", [self.center] * 65),
        ):
            with self.subTest(member=member):
                setattr(self.sketch, member, lambda: invalid)
                self.assert_error("ConstraintObservationUnavailable")
        self.setUp()
        self.center.GetRelationsCount = lambda: 7
        self.assert_error("ConstraintObservationUnavailable")

    def test_read_adapter_leaves_stamp_configuration_edit_and_native_calls_unchanged(
        self,
    ):
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["observation"]["unchanged"])
        self.assertFalse(hasattr(self.document, "ClearSelection2"))
        json.dumps(result, allow_nan=False)

    def test_read_adapter_detects_stamp_configuration_and_edit_changes(self):
        for field in ("stamp", "configuration", "edit"):
            with self.subTest(field=field):
                self.setUp()
                if field == "stamp":
                    self.document.GetUpdateStamp = mock.Mock(
                        spec=(), side_effect=[17, 18]
                    )
                elif field == "configuration":
                    self.document.ConfigurationManager.ActiveConfiguration = (
                        SimpleNamespace(
                            Name=mock.Mock(spec=(), side_effect=["Default", "Other"])
                        )
                    )
                else:
                    self.manager.ActiveSketch = mock.Mock(
                        spec=(), side_effect=[None, self.sketch]
                    )
                result = self.inspect()
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["observation"]["unchanged"])

    def test_read_adapter_preserves_primary_error_when_final_state_is_unreadable(self):
        self.relations.clear()
        self.document.GetUpdateStamp = mock.Mock(
            spec=(), side_effect=[17, RuntimeError("stamp")]
        )
        result = self.inspect()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "UnsupportedCenterConstraint")
        self.assertEqual(
            result["warnings"][0]["code"], "center-state-observation-failed"
        )


if __name__ == "__main__":
    unittest.main()
