import unittest

from swcli.operation_schemas import (
    OPERATIONS,
    OPERATION_CATALOG,
    operation_schemas,
    validate_operation_request,
)
from swcli.protocol import SCHEMA_NAMES, load_schema


class ProtocolSchemaTests(unittest.TestCase):
    def test_execution_policies_distinguish_selection_and_activation(self):
        self.assertFalse(OPERATION_CATALOG["document.create"].selected_document)
        self.assertFalse(OPERATION_CATALOG["document.use"].selected_document)
        self.assertFalse(OPERATION_CATALOG["document.open"].selected_document)
        self.assertTrue(OPERATION_CATALOG["document.inspect"].selected_document)
        self.assertFalse(OPERATION_CATALOG["document.inspect"].lease_guarded)
        self.assertTrue(OPERATION_CATALOG["document.export"].lease_guarded)
        self.assertTrue(OPERATION_CATALOG["document.export"].temporary_activation)
        self.assertFalse(OPERATION_CATALOG["document.save"].temporary_activation)
        self.assertIsNone(OPERATION_CATALOG["daemon.health"].handler)
        self.assertTrue(OPERATION_CATALOG["sketch.rectangle"].selected_document)
        self.assertTrue(OPERATION_CATALOG["sketch.rectangle"].lease_guarded)
        self.assertTrue(OPERATION_CATALOG["sketch.rectangle"].temporary_activation)

    def test_rectangle_parameters_reject_missing_plane_and_nonfinite_geometry(self):
        valid = {"plane": "front", "width_mm": 100, "height_mm": 50}
        validate_operation_request("sketch.rectangle", valid)
        for changed in (
            {"plane": "other"},
            {"width_mm": 0},
            {"center_x_mm": float("nan")},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_operation_request("sketch.rectangle", {**valid, **changed})
        with self.assertRaises(ValueError):
            validate_operation_request(
                "sketch.rectangle", {"width_mm": 100, "height_mm": 50}
            )

    def test_document_create_rejects_unsupported_types_and_target_context(self):
        validate_operation_request("document.create", {})
        validate_operation_request("document.create", {"type": "part", "template": "Part.prtdot"})
        with self.assertRaises(ValueError):
            validate_operation_request("document.create", {"type": "assembly"})
        with self.assertRaises(ValueError):
            validate_operation_request("document.create", {}, document_id="d-ab12cd")

    def test_extrude_schema_and_validator_agree_on_sketch_handle_and_depth(self):
        valid = {"sketch_id": "s-ab12cd", "depth_mm": 20}
        validate_operation_request("feature.extrude", valid)
        spec = OPERATION_CATALOG["feature.extrude"]
        self.assertTrue(
            spec.selected_document and spec.lease_guarded and spec.temporary_activation
        )
        for changed in (
            {"sketch_id": "Sketch1"},
            {"sketch_id": "s-short"},
            {"depth_mm": 0},
            {"depth_mm": float("inf")},
            {"merge": "false"},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_operation_request("feature.extrude", {**valid, **changed})

    def test_circle_parameters_and_policies_require_finite_radius_and_plane(self):
        valid = {"plane": "front", "radius_mm": 8}
        validate_operation_request("sketch.circle", valid)
        spec = OPERATION_CATALOG["sketch.circle"]
        self.assertTrue(
            spec.selected_document and spec.lease_guarded and spec.temporary_activation
        )
        for changed in (
            {"radius_mm": 0},
            {"radius_mm": -1},
            {"radius_mm": float("nan")},
            {"center_y_mm": float("inf")},
            {"plane": "other"},
            {"diameter_mm": 16},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_operation_request("sketch.circle", {**valid, **changed})
        with self.assertRaises(ValueError):
            validate_operation_request("sketch.circle", {"radius_mm": 8})

    def test_all_schemas_load(self):
        for name in SCHEMA_NAMES:
            with self.subTest(name=name):
                schema = load_schema(name)
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["type"], "object")

    def test_unknown_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown schema"):
            load_schema("missing")

    def test_unknown_protocol_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported protocol version"):
            load_schema("request", version="swcli/v2")

    def test_response_schema_describes_the_implemented_envelope(self):
        properties = load_schema("response")["properties"]
        self.assertEqual(
            set(properties),
            {
                "api_version",
                "request_id",
                "success",
                "duration_ms",
                "replayed",
                "result",
                "error",
            },
        )

    def test_request_schema_describes_update_stamp_precondition(self):
        properties = load_schema("request")["properties"]
        self.assertEqual(properties["expected_update_stamp"]["type"], "integer")
        self.assertEqual(properties["lease_id"]["type"], "string")

    def test_capabilities_schema_describes_daemon_health(self):
        schema = load_schema("capabilities")
        self.assertEqual(
            set(schema["properties"]),
            {
                "server_version",
                "protocol_versions",
                "operations",
                "operation_schemas",
                "operation_result_schemas",
                "request_replay",
                "worker_alive",
                "host_connected",
                "recovery_required",
                "recovery_error",
                "host",
            },
        )
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        operation_schema = schema["properties"]["operation_schemas"][
            "additionalProperties"
        ]
        self.assertIn("x-swcli-context", operation_schema["required"])
        live_host = schema["properties"]["host"]["oneOf"][0]
        self.assertEqual(
            set(live_host["properties"]),
            {
                "revision",
                "solidworks_revision",
                "language",
                "process_id",
                "visible",
                "startup_wait_seconds",
                "owned_by_daemon",
                "shared_interactive",
                "platform",
            },
        )
        self.assertEqual(set(live_host["required"]), set(live_host["properties"]))

    def test_operation_catalog_is_complete_and_isolated(self):
        schemas = operation_schemas()
        self.assertEqual(tuple(schemas), OPERATIONS)
        self.assertEqual(
            len({schema["$id"] for schema in schemas.values()}), len(schemas)
        )

        schemas["document.open"]["properties"].clear()
        self.assertIn("path", operation_schemas()["document.open"]["properties"])

    def test_operation_catalog_drives_parameter_and_context_validation(self):
        validate_operation_request(
            "document.render",
            {"output": "view.bmp", "width": 800, "fit": True},
            document_id="d-k7m2q9",
            lease_id="l-23456789abcd",
        )
        with self.assertRaisesRegex(ValueError, "document.open requires path"):
            validate_operation_request("document.open", {})
        with self.assertRaisesRegex(ValueError, "document.use requires document_id"):
            validate_operation_request("document.use", {})
        with self.assertRaisesRegex(ValueError, "read_only must be a boolean"):
            validate_operation_request(
                "document.open", {"path": "part.SLDPRT", "read_only": "false"}
            )
        with self.assertRaisesRegex(ValueError, "width_mm must be finite"):
            validate_operation_request(
                "part.create-box",
                {
                    "output": "box.SLDPRT",
                    "width_mm": float("nan"),
                    "height_mm": 50,
                    "depth_mm": 20,
                },
            )


if __name__ == "__main__":
    unittest.main()
