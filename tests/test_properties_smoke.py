"""Public property evidence must reject missing rows and retain failed receipts."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

path = Path(__file__).resolve().parents[1] / "scripts/ci/verify-properties.py"
spec = importlib.util.spec_from_file_location("properties_smoke_test", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PropertiesSmokeTests(unittest.TestCase):
    def test_missing_and_empty_rows_are_distinct(self):
        rows = [
            dict(name=name, type_code=code, type="text", raw_value=value,
                 evaluated_value=value, resolution="resolved", was_resolved=True, linked=False)
            for name, (code, value) in gate.EXPECTED.items()
        ]
        result = dict(ok=True, scope="document", properties=rows)
        with mock.patch.object(gate, "validate_operation_result"):
            self.assertEqual(gate.verify_properties(result)["Drawing No"]["raw_value"], "")
            result["properties"] = [row for row in rows if row["name"] != "Drawing No"]
            with self.assertRaisesRegex(RuntimeError, "lost rows"):
                gate.verify_properties(result)

    def test_configuration_shadow_cannot_pass_as_general_metadata(self):
        rows = [
            dict(name=name, type_code=code, raw_value=value, evaluated_value=value,
                 resolution="resolved", was_resolved=True, linked=False)
            for name, (code, value) in gate.EXPECTED.items()
        ]
        rows[2]["raw_value"] = rows[2]["evaluated_value"] = "configuration-only"
        with mock.patch.object(gate, "validate_operation_result"):
            with self.assertRaisesRegex(RuntimeError, "differs"):
                gate.verify_properties(dict(ok=True, scope="document", properties=rows))

    def test_first_failure_is_persisted_and_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(gate, "run", side_effect=RuntimeError("native failure")) as run:
                with self.assertRaisesRegex(RuntimeError, "native failure"):
                    gate.main(["--output-dir", directory, "--fixture-dir", directory])
            run.assert_called_once()
            record = json.loads((Path(directory) / "properties.json").read_text())
            self.assertEqual(record["state"], "failed")
            self.assertFalse(record["success"])

    def test_existing_record_is_preserved_before_any_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "properties.json"
            path.write_text("original evidence")
            with mock.patch.object(gate, "run") as run:
                with self.assertRaises(FileExistsError):
                    gate.main(["--output-dir", directory, "--fixture-dir", directory])
            run.assert_not_called()
            self.assertEqual(path.read_text(), "original evidence")
