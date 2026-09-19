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


if __name__ == "__main__":
    unittest.main()
