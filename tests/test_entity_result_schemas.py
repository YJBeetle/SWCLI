"""Internal face wire contracts refuse partial evidence and misleading geometry."""

from copy import deepcopy
import unittest

from jsonschema import Draft202012Validator

from swcli.operation_schemas import OPERATION_CATALOG
from swcli.result_schemas import (
    OperationResultInvalid,
    operation_result_schema,
    validate_entity_result,
    validate_entity_observation,
)


def face_result(name="entity.list", *, public=True):
    state = {
        "configuration": "Default",
        "update_stamp": 12,
        "modified": False,
        "editing": False,
        "foreground_present": True,
    }
    face = {
        "kind": "face",
        "surface_kind": "plane",
        "area_mm2": 1000.0,
        "area_accuracy": "approximate",
        "surface_geometry": {
            "available": True,
            "coordinate_system": "part-model",
            "boundary": "untrimmed-surface",
            "face_normal_opposes_surface": True,
            "plane": {
                "point_mm": [10.0, 20.0, 5.0],
                "surface_normal": [1.0, 0.0, 0.0],
                "outward_normal": [-1.0, 0.0, 0.0],
            },
        },
    }
    if public:
        face["entity_id"] = "e-ab12cd"
    return {
        "ok": True,
        "action": name,
        "scope": "single-solid-part-faces",
        "body_count": 1,
        "face_count": 1,
        "document": {
            "title": "A",
            "path": "",
            "type": 1,
            "modified": False,
            "update_stamp": 12,
            "document_id": "d-ab12cd",
        },
        "observation": {"before": state, "after": state.copy(), "unchanged": True},
        **({"entities": [face]} if name == "entity.list" else {"entity": face}),
    }


class EntityResultSchemaTests(unittest.TestCase):
    def test_result_contracts_are_not_yet_advertised_operations(self):
        for name in ("entity.list", "entity.inspect"):
            self.assertNotIn(name, OPERATION_CATALOG)
            Draft202012Validator.check_schema(operation_result_schema(name))
            validate_entity_result(name, face_result(name))

    def test_private_evidence_is_checked_before_public_ids_exist(self):
        for name in ("entity.list", "entity.inspect"):
            private = face_result(name, public=False)
            validate_entity_observation(name, private)
            with self.assertRaises(OperationResultInvalid):
                validate_entity_result(name, private)
            with self.assertRaises(OperationResultInvalid):
                validate_entity_observation(name, face_result(name))

    def test_cylinder_and_unknown_have_disjoint_geometry_not_plane_guesses(self):
        result = face_result()
        face = result["entities"][0]
        face["surface_kind"] = "cylinder"
        del face["surface_geometry"]["plane"]
        face["surface_geometry"]["cylinder"] = {
            "axis_point_mm": [0.0, 0.0, 0.0],
            "axis_direction": [0.0, 0.0, -1.0],
            "radius_mm": 3.0,
        }
        validate_entity_result("entity.list", result)
        face["surface_geometry"]["outward_normal"] = [1, 0, 0]
        with self.assertRaises(OperationResultInvalid):
            validate_entity_result("entity.list", result)
        face["surface_kind"] = "unclassified"
        face["surface_geometry"] = {
            "available": False,
            "reason": "unsupported-surface-kind",
        }
        validate_entity_result("entity.list", result)

    def test_failure_can_return_state_error_not_partial_entities(self):
        result = {
            "ok": False,
            "action": "entity.list",
            "error": {"type": "EntityObservationUnavailable", "message": "failed"},
        }
        validate_entity_result("entity.list", result)
        for key, value in (
            ("entities", face_result()["entities"]),
            ("entity", face_result()["entities"][0]),
            ("face_count", 1),
            ("body_count", 1),
        ):
            with self.subTest(key=key), self.assertRaises(OperationResultInvalid):
                validate_entity_result("entity.list", dict(result, **{key: value}))

    def test_counts_duplicates_missing_after_or_changed_snapshots_refuse_success(self):
        for mutate in (
            lambda r: r.update(face_count=2),
            lambda r: r.update(entities=[]),
            lambda r: (
                r["entities"].append(deepcopy(r["entities"][0])),
                r.update(face_count=2),
            ),
            lambda r: r["observation"].pop("after"),
            lambda r: r["observation"].update(unchanged=False),
            lambda r: r["observation"]["after"].update(modified=True),
            lambda r: r["document"].update(update_stamp=13),
            lambda r: r["document"].update(type=2),
        ):
            result = face_result()
            mutate(result)
            with self.assertRaises(OperationResultInvalid):
                validate_entity_result("entity.list", result)

    def test_bad_arrays_units_or_nonfinite_numbers_refuse_success(self):
        for value in (
            None,
            [1, 0],
            [1, 0, 0, 0],
            [True, 0, 0],
            [float("inf"), 0, 0],
            [float("nan"), 0, 0],
            ["1", 0, 0],
        ):
            result = face_result()
            result["entities"][0]["surface_geometry"]["plane"]["point_mm"] = value
            with self.subTest(value=value), self.assertRaises(OperationResultInvalid):
                validate_entity_result("entity.list", result)
        result = face_result()
        result["entities"][0]["surface_geometry"]["coordinate_system"] = "sketch"
        with self.assertRaises(OperationResultInvalid):
            validate_entity_result("entity.list", result)

    def test_outward_normal_and_unit_direction_are_semantic_not_only_shape_checks(self):
        for key, value in (
            ("surface_normal", [2, 0, 0]),
            ("surface_normal", [10**1000, 0, 0]),
            ("outward_normal", [1, 0, 0]),
            ("outward_normal", [0, 1, 0]),
        ):
            result = face_result()
            result["entities"][0]["surface_geometry"]["plane"][key] = value
            self.assertTrue(
                Draft202012Validator(operation_result_schema("entity.list")).is_valid(
                    result
                )
            )
            with self.assertRaises(OperationResultInvalid):
                validate_entity_result("entity.list", result)

    def test_native_reference_bytes_and_unbound_foreign_fields_cannot_escape(self):
        for field, value in (
            ("reference", "private"),
            ("body", {}),
            ("index", 1),
            ("entity_id", "Face1"),
        ):
            result = face_result()
            result["entities"][0][field] = value
            with self.assertRaises(OperationResultInvalid):
                validate_entity_result("entity.list", result)


if __name__ == "__main__":
    unittest.main()
