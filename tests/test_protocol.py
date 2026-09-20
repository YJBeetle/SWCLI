import unittest

from swcli.protocol import SCHEMA_NAMES, load_schema


class ProtocolSchemaTests(unittest.TestCase):
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
                "worker_alive",
                "recovery_required",
                "recovery_error",
                "host",
            },
        )
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
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


if __name__ == "__main__":
    unittest.main()
