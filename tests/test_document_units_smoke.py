"""Public unit smoke checks preserve failed evidence and native file ownership."""

from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.test_modeling_smoke import FakeCLI

path = Path(__file__).resolve().parents[1] / "scripts/ci/verify-document-units.py"
spec = importlib.util.spec_from_file_location("document_units_smoke_test", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def native_units(unit="mm", places=2):
    return {"length_unit": unit, "decimal_places": places, "native_units": {
        "length_unit": {"mm": 0, "inch": 3}[unit], "fraction_base": 1,
        "fraction_value": 8, "significant_digits": places, "round_to_fraction": 0,
    }}


class UnitsCLI(FakeCLI):
    def __init__(self, directory, fixtures):
        super().__init__(directory)
        self.fixtures = fixtures
        self.units_defect = None
        self.setter_attempts = 0
        self.native_sets = 0

    def dispatch(self, args):
        if args.command == "document" and args.document_command in ("units", "units-set"):
            document = self.documents[args.document_id]
            units = document["units"]
            result = {"ok": True, "action": "document." + args.document_command, "session_id": args.session,
                      "document": self.descriptor(document, args.session)}
            if args.document_command == "units":
                result["units"] = deepcopy(units)
                return result
            if args.expected_update_stamp is not None and args.expected_update_stamp != document["stamp"]:
                return self.failure("DocumentUpdateConflict")
            if document["lease"] and document["lease"]["session"] != args.session:
                return self.failure("DocumentLeaseConflict")
            mutation = {"attempted": False, "may_have_changed": False}
            if document["read_only"]:
                return self.failure("ValueError", mutation=mutation)
            if ((args.expected_length_unit is not None and args.expected_length_unit != units["length_unit"])
                    or (args.expected_decimal_places is not None and args.expected_decimal_places != units["decimal_places"])):
                return self.failure("DocumentUnitsConflict", mutation=mutation)
            updated = native_units(args.length_unit or units["length_unit"],
                                   units["decimal_places"] if args.decimal_places is None else args.decimal_places)
            changed = units != updated
            if changed:
                self.setter_attempts += 1
                if self.units_defect == "native-write-failed":
                    return self.failure("NativeUnitsFailure", mutation={"attempted": True, "may_have_changed": True})
                self.native_sets += 1
                document["units"] = updated
                document["modified"] = True
            elif self.units_defect == "same-value-dirty":
                document["modified"] = True
            result.update(before=deepcopy(units), units=deepcopy(updated), changed=changed,
                          mutation={"attempted": changed, "may_have_changed": changed},
                          document=self.descriptor(document, args.session))
            return result
        result = super().dispatch(args)
        if args.command == "daemon":
            result["result"]["host"].update(owned_by_daemon=True, visible=False, shared_interactive=False)
        if args.command == "document" and args.document_command in ("create", "open"):
            document = self.documents[result["document"]["document_id"]]
            document.setdefault("units", native_units())
            if args.document_command == "open" and args.read_only and self.units_defect == "reopen-lost-precision":
                document["units"] = native_units()
        if args.command == "document" and args.document_command == "save-as":
            result["save_warnings"] = None
            if self.units_defect == "source-changed":
                (self.fixtures / "properties.SLDPRT").write_bytes(b"changed")
        return result


class DocumentUnitsSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "evidence"
        self.fixtures = Path(self.temporary.name) / "fixtures"
        self.fixtures.mkdir()
        for suffix in ("SLDPRT", "SLDASM"):
            (self.fixtures / ("properties." + suffix)).write_bytes(b"original fixture" * 100)
        self.fake = UnitsCLI(self.directory, self.fixtures)
        self.arguments = ["--output-dir", str(self.directory), "--fixture-dir", str(self.fixtures),
                          "--host-fixture-dir", r"C:\fixtures", "--host-output-dir", r"C:\proof"]

    def run_gate(self):
        with mock.patch.object(gate.modeling.subprocess, "run", side_effect=self.fake.run), \
                mock.patch("sys.stdout", new=io.StringIO()):
            gate.main(self.arguments)

    def record(self):
        return json.loads((self.directory / "document-units.json").read_text())

    def test_both_native_kinds_keep_scope_hashes_and_persist_unit_boundaries(self):
        self.run_gate()
        record = self.record()
        self.assertEqual((record["state"], record["success"], record["cleanup_errors"]), ("completed", True, []))
        self.assertEqual([case["format"] for case in record["unit_cases"]], ["SLDPRT", "SLDASM"])
        self.assertEqual(self.fake.native_sets, 6)
        self.assertEqual(self.fake.documents, {})
        for case in record["unit_cases"]:
            self.assertTrue(case["success"])
            self.assertEqual([write["units"]["decimal_places"] for write in case["writes"]], [0, 4, 8])
            self.assertEqual(case["reopened_units"]["units"], native_units("mm", 8))
            self.assertFalse(case["same_value"]["changed"])
            self.assertEqual(case["stale_value_refusal"]["error"]["type"], "DocumentUnitsConflict")
            self.assertFalse(case["stale_value_refusal"]["mutation"]["attempted"])
            self.assertNotEqual(case["open"]["document"]["document_id"], case["reopen"]["document"]["document_id"])
        source_saves = [call for call in self.fake.calls if call.command == "document" and call.document_command == "save"]
        self.assertEqual(source_saves, [])
        self.assertEqual(record["host"], record["host_after"])
        self.assertIn("not measured", record["geometry_coverage"])

    def test_missing_persistence_and_source_or_same_value_mutation_are_failures(self):
        for defect in ("reopen-lost-precision", "source-changed", "same-value-dirty"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                self.directory = Path(temporary) / "evidence"
                self.arguments[1] = str(self.directory)
                self.fake = UnitsCLI(self.directory, self.fixtures)
                self.fake.units_defect = defect
                with self.assertRaises(RuntimeError):
                    self.run_gate()
                self.assertEqual(self.record()["state"], "failed")
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents, {})

    def test_native_write_failure_is_not_retried_and_keeps_failed_receipt(self):
        self.fake.units_defect = "native-write-failed"
        with self.assertRaises(RuntimeError):
            self.run_gate()
        self.assertEqual(self.fake.setter_attempts, 1)
        self.assertEqual(self.fake.native_sets, 0)
        record = self.record()
        self.assertEqual(record["state"], "failed")
        self.assertFalse(record["success"])
        self.assertEqual(self.fake.documents, {})

    def test_existing_record_refuses_before_any_cli(self):
        self.directory.mkdir()
        path = self.directory / "document-units.json"
        path.write_text("original evidence")
        with mock.patch.object(gate.modeling.subprocess, "run") as cli:
            with self.assertRaises(FileExistsError):
                gate.main(self.arguments)
        cli.assert_not_called()
        self.assertEqual(path.read_text(), "original evidence")

    def test_final_checkpoint_failure_is_fatal_and_preserves_first_error(self):
        native_error = RuntimeError("first native failure")
        for failure in (None, native_error):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                cleanup_method = gate.modeling.ModelingSmoke.cleanup
                with (
                    mock.patch.object(gate, "run", side_effect=failure) as run,
                    mock.patch.object(gate.modeling.ModelingSmoke, "cleanup", autospec=True,
                                      side_effect=cleanup_method) as cleanup,
                    mock.patch.object(gate.modeling.ModelingSmoke, "write_checkpoint",
                                      side_effect=OSError("final evidence failed")) as checkpoint,
                ):
                    with self.assertRaises(type(failure) if failure else OSError) as raised:
                        gate.main(["--output-dir", directory, "--fixture-dir", str(self.fixtures)])
                if failure is not None:
                    self.assertIs(raised.exception, failure)
                run.assert_called_once()
                cleanup.assert_called_once()
                checkpoint.assert_called_once_with("document-units-final")

    def test_windows_wrapper_runs_units_after_properties_before_full_without_restart(self):
        wrapper = (path.parent / "windows/smoke-solidworks.ps1").read_text()
        block = wrapper.split("    if ($PropertyFixtureDirectory) {", 1)[1].split("    # Shared scripts", 1)[0]
        self.assertLess(block.index("verify-properties.py"), block.index("verify-document-units.py"))
        self.assertIn('if ($LASTEXITCODE -ne 0) { throw "public document units CLI gate failed" }', block)
        self.assertNotIn('"restart"', block)
        self.assertNotIn('"stop"', block)
