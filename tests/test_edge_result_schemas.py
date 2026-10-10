"""Edge wire evidence stays raw/untrimmed, bounded and separate from faces."""

from copy import deepcopy
import math
import unittest

from jsonschema import Draft202012Validator

from swcli.operation_schemas import OPERATION_CATALOG
from swcli.result_schemas import (
    OperationResultInvalid, operation_result_schema,
    validate_entity_result, validate_entity_observation,
)
from test_entity_result_schemas import face_result


def edge_result(name="entity.list", *, public=True, curve="line"):
    result = face_result(name, public=public)
    result["scope"] = "single-solid-part-edges"
    result["edge_count"] = result.pop("face_count")
    geometry = {
        "line": {"root_point_mm": [60., 45., 20.], "direction": [0., 0., -1.]},
        "circle": {"center_mm": [10., 20., 5.], "axis_direction": [0., 0., -1.], "radius_mm": 3.},
    }
    edge = {
        "kind": "edge", "curve_kind": curve,
        "parameter_data": {
            "coordinate_system": "part-model", "interpretation": "native-edge-parameter-data",
            "start_point_mm": [60., 45., 20.], "end_point_mm": [60., 45., 0.],
            "u_min_native": 0., "u_max_native": .02,
            "curve_and_edge_same_direction": True,
            "curve_type": {"line": 3001, "circle": 3002, "unclassified": 3005}[curve],
        },
        "curve_geometry": (
            {"available": True, "coordinate_system": "part-model", "boundary": "untrimmed-curve",
             curve: geometry[curve]} if curve in geometry else
            {"available": False, "reason": "unsupported-curve-kind"}
        ),
    }
    if public:
        edge["entity_id"] = "e-ab12cd"
    result.update({"entities": [edge]} if name == "entity.list" else {"entity": edge})
    return result


class EdgeResultSchemaTests(unittest.TestCase):
    def rejects(self, mutate, *, name="entity.list", curve="line"):
        result = edge_result(name, curve=curve)
        mutate(result)
        with self.assertRaises(OperationResultInvalid):
            validate_entity_result(name, result)

    def test_both_public_operations_support_all_curve_variants(self):
        for name in ("entity.list", "entity.inspect"):
            schema = operation_result_schema(name)
            self.assertEqual(schema, OPERATION_CATALOG[name].result)
            Draft202012Validator.check_schema(schema)
            for curve in ("line", "circle", "unclassified"):
                with self.subTest(name=name, curve=curve):
                    validate_entity_result(name, edge_result(name, curve=curve))

    def test_private_shape_requires_no_ids_and_public_shape_requires_ids(self):
        for name in ("entity.list", "entity.inspect"):
            validate_entity_observation(name, edge_result(name, public=False))
            with self.assertRaises(OperationResultInvalid):
                validate_entity_result(name, edge_result(name, public=False))
            with self.assertRaises(OperationResultInvalid):
                validate_entity_observation(name, edge_result(name))

    def test_raw_sense_negative_interval_equal_endpoints_do_not_claim_closure(self):
        result = edge_result(curve="circle")
        params = result["entities"][0]["parameter_data"]
        params.update(curve_and_edge_same_direction=False, u_min_native=-math.tau, u_max_native=0.)
        params["end_point_mm"] = params["start_point_mm"].copy()
        validate_entity_result("entity.list", result)
        for key in ("length_mm", "closed", "seam", "adjacency", "owning_feature_id"):
            with self.subTest(key=key):
                self.rejects(lambda r: r["entities"][0].update({key: False}))

    def test_kind_scope_and_count_cannot_disagree_or_mix(self):
        for mutate in (
            lambda r: r.update(scope="single-solid-part-faces"),
            lambda r: r.update(face_count=1),
            lambda r: r.pop("edge_count"),
            lambda r: r.update(edge_count=2),
            lambda r: r.update(entities=[]),
            lambda r: r["entities"].append(face_result()["entities"][0]),
            lambda r: r["entities"][0].update(kind="face"),
            lambda r: r["entities"][0].update(reference="private-bytes"),
        ):
            self.rejects(mutate)
        for mutate in (lambda r: r.update(face_count=1), lambda r: r.pop("edge_count")):
            self.rejects(mutate, name="entity.inspect")

    def test_failed_observation_cannot_publish_edge_count_or_records(self):
        result = {"ok": False, "action": "entity.list", "error": {"type": "NativeError", "message": "first"}}
        validate_entity_result("entity.list", result)
        for key, value in (("edge_count", 1), ("entities", edge_result()["entities"]), ("body_count", 1)):
            with self.subTest(key=key), self.assertRaises(OperationResultInvalid):
                validate_entity_result("entity.list", dict(result, **{key: value}))

    def test_curves_are_disjoint_and_types_classification_must_agree(self):
        for curve in ("line", "circle", "unclassified"):
            for value in (True, "3001", 0, 3001.5, 3002 if curve != "circle" else 3001):
                with self.subTest(curve=curve, value=value):
                    self.rejects(lambda r: r["entities"][0]["parameter_data"].update(curve_type=value), curve=curve)
        self.rejects(lambda r: r["entities"][0]["curve_geometry"].update(circle={}), curve="line")
        self.rejects(lambda r: r["entities"][0]["curve_geometry"].update(available=True), curve="unclassified")

    def test_vectors_scalars_and_booleans_are_strict_and_finite(self):
        for key in ("start_point_mm", "end_point_mm"):
            for value in ([0, 0], [0, 0, 0, 0], [True, 0, 0], [math.nan, 0, 0], [math.inf, 0, 0]):
                with self.subTest(key=key, value=value):
                    self.rejects(lambda r: r["entities"][0]["parameter_data"].update({key: value}))
        for key in ("u_min_native", "u_max_native"):
            for value in (True, "0", None, math.inf, math.nan):
                with self.subTest(key=key, value=value):
                    self.rejects(lambda r: r["entities"][0]["parameter_data"].update({key: value}))
        for value in (0, 1, None, "false"):
            self.rejects(lambda r: r["entities"][0]["parameter_data"].update(curve_and_edge_same_direction=value))

    def test_interval_unit_direction_and_radius_require_semantic_proof(self):
        for low, high in ((0, 0), (1, 0)):
            self.rejects(lambda r: r["entities"][0]["parameter_data"].update(u_min_native=low, u_max_native=high))
        for direction in ([0, 0, 0], [2, 0, 0], [0, 0, math.inf]):
            self.rejects(lambda r: r["entities"][0]["curve_geometry"]["line"].update(direction=direction))
            self.rejects(lambda r: r["entities"][0]["curve_geometry"]["circle"].update(axis_direction=direction), curve="circle")
        for value in (0, -3, math.inf, True):
            self.rejects(lambda r: r["entities"][0]["curve_geometry"]["circle"].update(radius_mm=value), curve="circle")

    def test_unchanged_full_state_and_unique_handles_are_mandatory(self):
        for mutate in (
            lambda r: r["observation"]["after"].update(update_stamp=13),
            lambda r: r["observation"].update(unchanged=False),
            lambda r: r["observation"].pop("after"),
            lambda r: r["document"].update(modified=True),
            lambda r: (r["entities"].append(deepcopy(r["entities"][0])), r.update(edge_count=2)),
        ):
            self.rejects(mutate)


if __name__ == "__main__":
    unittest.main()
