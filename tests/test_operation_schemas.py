"""Focused public discovery request/catalog contract checks."""

import unittest

from jsonschema import Draft202012Validator

from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request


class DiameterDiscoveryRequestTests(unittest.TestCase):
    def test_discovery_is_a_selected_document_read_without_activation_or_lease(self):
        spec = OPERATION_CATALOG["dimension.discover-diameter"]
        self.assertEqual(spec.handler, "dimension_discover_diameter")
        self.assertTrue(spec.selected_document)
        self.assertFalse(spec.lease_guarded)
        self.assertFalse(spec.temporary_activation)
        self.assertEqual(
            spec.parameters["x-swcli-context"],
            {
                "document_id": "optional",
                "expected_update_stamp": "optional",
                "lease_id": "forbidden",
            },
        )
        values = {"sketch_id": "s-ab12cd"}
        self.assertEqual(
            validate_operation_request(
                "dimension.discover-diameter",
                values,
                document_id="d-ab12cd",
                expected_update_stamp=10,
            ),
            values,
        )
        self.assertTrue(Draft202012Validator(spec.parameters).is_valid(values))

    def test_discovery_requires_only_an_exact_short_sketch_handle(self):
        validator = Draft202012Validator(
            OPERATION_CATALOG["dimension.discover-diameter"].parameters
        )
        for values in (
            {},
            {"sketch_id": None},
            {"sketch_id": "Sketch1"},
            {"sketch_id": "s-ab12cd", "diameter_mm": 16},
            {"sketch_id": "s-ab12cd", "dimension_id": "m-ab12cd"},
            {"sketch_id": "s-ab12cd", "name": "D1@Sketch1"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_operation_request("dimension.discover-diameter", values)
            self.assertFalse(validator.is_valid(values))
        with self.assertRaisesRegex(ValueError, "lease_id is not supported"):
            validate_operation_request(
                "dimension.discover-diameter",
                {"sketch_id": "s-ab12cd"},
                lease_id="l-ab12cd34ef56",
            )


if __name__ == "__main__":
    unittest.main()
