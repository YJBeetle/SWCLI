"""Single-edge fillet wire contracts fail closed on incomplete native evidence."""

import unittest

from jsonschema import Draft202012Validator

from swcli.cli import build_parser, _typed_operation
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import operation_result_schema, validate_operation_result, OperationResultInvalid


def success():
    return {
        "ok": True, "action": "feature.fillet", "entity_id": "e-ab12cd", "radius_mm": 2,
        "mutation": {"attempted": True, "creation_returned": True, "may_have_changed": True},
        "feature": {"name": "Fillet1", "type": "Fillet", "feature_id": "f-ab12cd"},
        "verification": {"passed": True, "radius_mm": 2, "edge_count": 1,
                         "profile": "circular", "tangent_propagation": False},
        "rebuilt": True, "bodies": 1, "before_volume_mm3": 12000, "after_volume_mm3": 11991,
        "diagnostics": {"healthy": True, "issues": [], "issue_count": 0,
                        "scanned_feature_count": 21, "truncated": False, "limit": 1000},
        "cleanup_errors": [],
    }


class FilletContractTests(unittest.TestCase):
    def test_cli_and_write_context(self):
        args = build_parser().parse_args([
            "feature", "fillet", "e-ab12cd", "--radius-mm", "2", "--document", "d-ab12cd",
            "--if-update-stamp", "12", "--lease", "l-ab12cd34ef56", "--json",
        ])
        self.assertEqual(_typed_operation(args), (
            "feature.fillet", {"entity_id": "e-ab12cd", "radius_mm": 2}, True,
            "d-ab12cd", 12, "l-ab12cd34ef56"))
        spec = OPERATION_CATALOG["feature.fillet"]
        self.assertTrue(spec.selected_document and spec.lease_guarded and spec.temporary_activation)

    def test_request_invalid_targets_and_numbers(self):
        for params in ({}, {"entity_id": "f-ab12cd", "radius_mm": 2},
                       {"entity_id": "Edge1", "radius_mm": 2},
                       *[{"entity_id": "e-ab12cd", "radius_mm": value}
                         for value in (0, -1, True, float("nan"), float("inf"))],
                       {"entity_id": "e-ab12cd", "radius_mm": 2, "tangent_propagation": True}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                validate_operation_request("feature.fillet", params)

    def test_success_accepts_convex_and_concave_volume_change(self):
        for volume in (11991, 12009):
            result = success()
            result["after_volume_mm3"] = volume
            validate_operation_result("feature.fillet", result)

    def test_success_schema_rejects_missing_and_tampered_evidence(self):
        validator = Draft202012Validator(operation_result_schema("feature.fillet"))
        for field in success():
            result = success()
            del result[field]
            with self.subTest(missing=field):
                self.assertFalse(validator.is_valid(result))
        for path, value in (
            (("mutation", "attempted"), False), (("mutation", "creation_returned"), False),
            (("mutation", "may_have_changed"), False), (("feature", "type"), "Boss"),
            (("verification", "passed"), False), (("verification", "edge_count"), 2),
            (("verification", "profile"), "conic"), (("verification", "tangent_propagation"), True),
            (("diagnostics", "healthy"), False), (("diagnostics", "truncated"), True),
            (("diagnostics", "issue_count"), 1), (("rebuilt",), False), (("bodies",), 2),
            (("cleanup_errors",), [{"stage": "release", "error": "failed"}]),
        ):
            result = success()
            target = result
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.fillet", result)
        result = success()
        del result["feature"]["feature_id"]
        self.assertFalse(validator.is_valid(result))

    def test_semantic_and_nonfinite_tampering(self):
        for key, value in (("after_volume_mm3", 12000), ("radius_mm", 3),
                           ("after_volume_mm3", float("inf")), ("before_volume_mm3", float("nan"))):
            result = success()
            result[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.fillet", result)

    def test_partial_failure_preserves_exact_target_and_bounded_evidence(self):
        result = {"ok": False, "action": "feature.fillet", "entity_id": "e-ab12cd",
                  "error": {"type": "FilletFailed", "message": "native creation failed"}}
        validate_operation_result("feature.fillet", result)
        result["verification"] = {"passed": False}
        validate_operation_result("feature.fillet", result)
        result["verification"]["guessed_field"] = 1
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("feature.fillet", result)


if __name__ == "__main__":
    unittest.main()
