"""Complete exact edge reads are atomic observations, never partial targets."""

import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_edge_observation as observation


class EdgeObservationTests(unittest.TestCase):
    def setUp(self):
        self.body = SimpleNamespace()
        self.foreground = object()
        self.app = SimpleNamespace(IsSame=lambda first, second: int(first is second))
        self.edges = [SimpleNamespace(
            GetBody=lambda: self.body,
            GetCurve=lambda: SimpleNamespace(IsLine=True, IsCircle=False,
                                            LineParams=(0, 0, 0, 1, 0, 0)),
            GetCurveParams3=lambda: SimpleNamespace(
                StartPoint=(0, 0, 0), EndPoint=(0.01, 0, 0),
                UMinValue=0.0, UMaxValue=0.01, Sense=True, CurveType=3001),
            reference=bytes((index + 1,)),
        ) for index in range(3)]
        self.body.GetEdgeCount = lambda: len(self.edges)
        self.body.GetEdges = lambda: tuple(self.edges)
        self.document = SimpleNamespace(GetType=1, Extension=object())
        self.document.GetBodies2 = mock.Mock(side_effect=lambda kind, visible: (self.body,) if kind == 0 else None)
        self.before = {"configuration": "default", "update_stamp": 12,
                       "modified": False, "editing": False, "foreground_present": True}
        self.state = mock.patch.object(observation, "_state", side_effect=lambda app, document:
                                      (self.before.copy(), None, self.foreground))
        self.state.start()
        self.addCleanup(self.state.stop)
        self.capture = mock.patch.object(observation, "capture_verified_reference",
                                         side_effect=lambda app, extension, edge: edge.reference)
        self.capture_mock = self.capture.start()
        self.addCleanup(self.capture.stop)

    def read(self, **kwargs):
        return observation.observe_part_edges_with_handles(self.app, self.document, **kwargs)

    def refused(self, **kwargs):
        result, handles = self.read(**kwargs)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)
        self.assertEqual(handles, [])
        self.assertNotIn("edges", result)
        self.assertNotIn("edge_count", result)
        return result

    def test_complete_bounded_read_preserves_private_bindings_and_hidden_body_scope(self):
        result, bindings = self.read()
        self.assertTrue(result["ok"])
        self.assertEqual((result["edge_count"], result["body_count"]), (3, 1))
        self.assertTrue(result["observation"]["unchanged"])
        self.assertIs(bindings[0].edge, self.edges[0])
        self.assertIs(bindings[0].body, self.body)
        self.assertEqual(bindings[0].reference, b"\x01")
        self.assertNotIn("reference", json.dumps(result))
        self.assertNotIn("entity_id", json.dumps(result))
        self.assertEqual(self.document.GetBodies2.call_args_list,
                         [mock.call(0, False), mock.call(1, False)] * 2)
        self.assertEqual(self.capture_mock.call_count, 3)

    def test_final_traversal_order_is_not_native_identity(self):
        self.body.GetEdges = lambda: tuple(reversed(self.edges))
        reads = iter((tuple(self.edges), tuple(reversed(self.edges))))
        self.body.GetEdges = lambda: next(reads)
        result, bindings = self.read()
        self.assertTrue(result["ok"])
        self.assertIs(bindings[0].edge, self.edges[0])

    def test_invalid_limits_and_non_part_do_not_read_bodies_or_references(self):
        for value in (None, True, 0, 65, 1.0, "1"):
            with self.subTest(value=value):
                self.refused(max_edges=value)
        for value in (None, True, 2, 3, 1.0, "1"):
            self.document.GetType = value
            with self.subTest(value=value):
                self.refused()
        self.document.GetBodies2.assert_not_called()
        self.capture_mock.assert_not_called()

    def test_multibody_surface_or_invalid_body_arrays_are_never_omitted(self):
        for solids, surfaces in ((None, None), ((), ()), ((self.body, object()), None),
                                 ((self.body,), (object(),)), ((None,), None), ("body", None)):
            self.document.GetBodies2.side_effect = lambda kind, visible: solids if kind == 0 else surfaces
            with self.subTest(solids=solids, surfaces=surfaces):
                self.refused()
        self.capture_mock.assert_not_called()

    def test_initial_count_and_array_must_agree_before_geometry_or_references(self):
        for value in (None, True, 0, 65, 2, 3.0):
            self.body.GetEdgeCount = lambda: value
            with self.subTest(value=value):
                self.refused()
        self.body.GetEdgeCount = lambda: 3
        for value in (None, (), "edges", (None, self.edges[0], self.edges[1])):
            self.body.GetEdges = lambda: value
            with self.subTest(value=value):
                self.refused()
        self.capture_mock.assert_not_called()

    def test_foreign_duplicate_native_edge_and_ambiguous_reference_fail(self):
        self.edges[-1].GetBody = lambda: object()
        self.refused()
        self.edges[-1].GetBody = lambda: self.body
        last = self.edges[-1]
        self.edges[-1] = self.edges[0]
        self.refused()
        self.edges[-1] = last
        self.edges[-1].reference = self.edges[0].reference
        self.refused()

    def test_unreadable_native_identity_cannot_be_treated_as_a_distinct_edge(self):
        for status in (None, True, False, 2, 3, 1.0, "1"):
            self.app.IsSame = lambda first, second: status
            with self.subTest(status=status):
                self.refused()

    def test_supported_geometry_failure_discards_all_prior_successes(self):
        self.edges[-1].GetCurve = lambda: SimpleNamespace(IsLine=True, IsCircle=False,
                                                         LineParams=(0, 0, 0, 0, 0, 0))
        result = self.refused()
        self.assertEqual(result["error"]["type"], "EntityGeometryUnavailable")
        self.assertEqual(self.capture_mock.call_count, 2)

    def test_unsupported_curve_is_explicit_with_exact_private_reference(self):
        self.edges[-1].GetCurve = lambda: SimpleNamespace(IsLine=False, IsCircle=False)
        self.edges[-1].GetCurveParams3 = lambda: SimpleNamespace(
            StartPoint=(0, 0, 0), EndPoint=(0.01, 0, 0),
            UMinValue=0.0, UMaxValue=1.0, Sense=True, CurveType=3005)
        result, bindings = self.read()
        self.assertTrue(result["ok"])
        self.assertEqual(result["edges"][-1]["curve_kind"], "unclassified")
        self.assertFalse(result["edges"][-1]["curve_geometry"]["available"])
        self.assertIs(bindings[-1].edge, self.edges[-1])

    def test_same_count_does_not_hide_replaced_missing_or_repeated_final_edges(self):
        replacement = SimpleNamespace(GetBody=lambda: self.body)
        for final in ((), (self.edges[0], self.edges[1], replacement),
                      (self.edges[0], self.edges[1], self.edges[0]), None, "edges"):
            reads = iter((tuple(self.edges), final))
            self.body.GetEdges = lambda: next(reads)
            with self.subTest(final=final):
                self.refused()

    def test_changed_final_count_or_body_discards_every_binding(self):
        for final in (None, 2, 4):
            counts = iter((3, final))
            self.body.GetEdgeCount = lambda: next(counts)
            self.refused()
        self.body.GetEdgeCount = lambda: 3
        self.document.GetBodies2.side_effect = [(self.body,), None, (object(),), None]
        self.refused()

    def test_any_state_scope_edit_or_foreground_change_discards_every_binding(self):
        for key, value in (("configuration", "other"), ("update_stamp", 13),
                           ("modified", True), ("editing", True), ("foreground_present", False)):
            with self.subTest(key=key), mock.patch.object(observation, "_state", side_effect=[
                (self.before.copy(), None, self.foreground),
                (dict(self.before, **{key: value}), None, self.foreground),
            ]):
                self.refused()
        for final_edit, final_foreground in ((object(), self.foreground), (None, object())):
            with mock.patch.object(observation, "_state", side_effect=[
                (self.before.copy(), None, self.foreground),
                (self.before.copy(), final_edit, final_foreground),
            ]):
                self.refused()

    def test_final_state_failure_retains_first_native_error(self):
        self.capture_mock.side_effect = RuntimeError("first reference failure")
        with mock.patch.object(observation, "_state", side_effect=[
            (self.before.copy(), None, self.foreground), RuntimeError("later state failure"),
        ]):
            result = self.refused()
        self.assertEqual(result["error"]["message"], "first reference failure")
        self.assertEqual(result["warnings"][0]["code"], "entity-observation-state-check-failed")


if __name__ == "__main__":
    unittest.main()
