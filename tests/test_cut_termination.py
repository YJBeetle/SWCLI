"""Public termination semantics shared by discovery and request validation."""

from copy import deepcopy
import unittest

from jsonschema import Draft202012Validator

from swcli.cut_termination import (
    cut_termination_conditions, cut_termination_fields, resolve_cut_termination,
)
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request


class CutTerminationTests(unittest.TestCase):
    def validator(self):
        schema = {
            "type": "object",
            "properties": cut_termination_fields(),
            "allOf": cut_termination_conditions(),
            "additionalProperties": False,
        }
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    def test_legacy_blind_requires_depth_and_keeps_its_value(self):
        for values in ({"depth_mm": 20}, {"end_condition": "blind", "depth_mm": 20.5}):
            with self.subTest(values=values):
                self.assertTrue(self.validator().is_valid(values))
                result = resolve_cut_termination(values)
                self.assertEqual(result.end_condition, "blind")
                self.assertEqual(result.depth_mm, values["depth_mm"])
        for values in ({}, {"end_condition": "blind"}):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "requires"):
                resolve_cut_termination(values)
            self.assertFalse(self.validator().is_valid(values))

    def test_through_all_has_no_fabricated_travel_length(self):
        values = {"end_condition": "through-all"}
        before = deepcopy(values)
        self.assertTrue(self.validator().is_valid(values))
        result = resolve_cut_termination(values)
        self.assertEqual(result.end_condition, "through-all")
        self.assertIsNone(result.depth_mm)
        self.assertEqual(values, before)

    def test_any_explicit_depth_conflicts_with_through_all(self):
        for depth in (None, 0, 1, 1000000, "10", True, float("nan")):
            values = {"end_condition": "through-all", "depth_mm": depth}
            with self.subTest(depth=depth), self.assertRaisesRegex(ValueError, "does not accept"):
                resolve_cut_termination(values)
            self.assertFalse(self.validator().is_valid(values))

    def test_unknown_termination_is_not_coerced_or_defaulted(self):
        for end in (None, False, 0, 1, "", "Through-All", "through-all-both", "up-to-face", [], {}):
            values = {"end_condition": end, "depth_mm": 10}
            with self.subTest(end=end), self.assertRaisesRegex(ValueError, "end_condition"):
                resolve_cut_termination(values)
            self.assertFalse(self.validator().is_valid(values))

    def test_blind_length_refuses_nonfinite_boolean_and_unrepresentable_numbers(self):
        for depth in (None, True, False, "10", [], {}, 0, -1, float("nan"),
                      float("inf"), -float("inf"), 10**1000, 5e-324):
            with self.subTest(type=type(depth).__name__), self.assertRaises(ValueError):
                resolve_cut_termination({"depth_mm": depth})

    def test_schema_fields_and_conditions_do_not_leak_mutations_between_calls(self):
        fields, conditions = cut_termination_fields(), cut_termination_conditions()
        fields["end_condition"]["enum"].append("unsafe")
        conditions[0]["then"].clear()
        self.assertNotIn("unsafe", cut_termination_fields()["end_condition"]["enum"])
        self.assertEqual(cut_termination_conditions()[0]["then"], {"not": {"required": ["depth_mm"]}})

    def test_public_contract_advertises_termination_without_weakening_guards(self):
        spec = OPERATION_CATALOG["feature.cut-extrude"]
        validator = Draft202012Validator(spec.parameters)
        for values in (
            {"sketch_id": "s-ab12cd", "end_condition": "through-all"},
            {"sketch_id": "s-ab12cd", "depth_mm": 10, "reverse": True},
            {"sketch_id": "s-ab12cd", "end_condition": "blind", "depth_mm": 10},
        ):
            self.assertTrue(validator.is_valid(values))
            self.assertEqual(validate_operation_request("feature.cut-extrude", values), values)
        for values in (
            {"sketch_id": "s-ab12cd"},
            {"sketch_id": "s-ab12cd", "end_condition": "blind"},
            *({"sketch_id": "s-ab12cd", "end_condition": "through-all", "depth_mm": depth}
              for depth in (None, 0, 1, True)),
        ):
            self.assertFalse(validator.is_valid(values))
            with self.assertRaises(ValueError):
                validate_operation_request("feature.cut-extrude", values)
        self.assertTrue(spec.lease_guarded)
        self.assertTrue(spec.temporary_activation)


if __name__ == "__main__":
    unittest.main()
