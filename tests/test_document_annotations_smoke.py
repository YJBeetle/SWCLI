"""Portable gate-control checks, not native SOLIDWORKS persistence evidence."""

from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from swcli import __version__
from swcli.cli import _typed_operation
from swcli.document_annotations import ANNOTATION_FIELDS
from tests.test_modeling_smoke import FakeCLI

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-document-annotations.py"
spec = importlib.util.spec_from_file_location("document_annotations_smoke_test", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def initial_options():
    raw = {"arrow.edge_vertex": "closed", "arrow.face_surface": "dot", "arrow.unattached": "closed",
           "bent_leader.enabled": False, "bent_leader.length_mm": 6.35,
           "zero.leading": "standard", "zero.trailing": "remove_only_on_zero"}
    return {field: option(field, value) for field, value in raw.items()}


def option(field, value):
    spec = ANNOTATION_FIELDS[field]
    native = (spec["values"][value] if spec["kind"] == "Integer" else
              value / 1000.0 if spec["kind"] == "Double" else value)
    return {"value": value, "native_value": native}


class AnnotationsCLI(FakeCLI):
    def __init__(self, directory, fixtures, trace):
        super().__init__(directory)
        self.fixtures = fixtures
        self.trace = trace
        self.annotation_defect = None
        self.native_sets = 0
        self.setter_attempts = 0
        self.last_native_calls = []
        self.trace_requests = 0
        self.initial_options_by_type = {}

    def run(self, command, **keywords):
        self.last_native_calls = []
        completed = super().run(command, **keywords)
        args = self.calls[-1]
        if args.command == "document" and args.document_command.startswith("annotation-"):
            self.trace_requests += 1
            result = json.loads(completed.stdout)
            request = result["request_id"]
            operation = "document." + args.document_command
            records = [{"event": "swcli.native-call", "request_id": request, "operation": operation,
                        "sequence": 0, "call": operation, "phase": "begin"}]
            calls = self.last_native_calls
            if self.annotation_defect == "missing-preference-getter":
                calls = [call for call in calls if not call.startswith("IModelDocExtension.GetUserPreference")]
            if self.annotation_defect == "misordered-native-readback" and "IModelDoc2.SetSaveFlag" in calls:
                calls = list(calls)
                mark = calls.index("IModelDoc2.SetSaveFlag")
                calls[8], calls[mark] = calls[mark], calls[8]
            for sequence, call in enumerate(calls, 1):
                for phase in ("begin", "end"):
                    records.append({"event": "swcli.native-call", "request_id": request,
                                    "operation": operation, "sequence": sequence, "call": call, "phase": phase})
            records.append({**records[0], "phase": "end"})
            if self.annotation_defect == "missing-trace":
                records = []
            if self.annotation_defect == "missing-trace-end":
                records = records[:-1]
            if self.annotation_defect == "operation-end-before-native":
                records.insert(1, records.pop())
            if self.annotation_defect == "native-end-before-begin" and len(records) > 2:
                records[1], records[2] = records[2], records[1]
            if self.annotation_defect == "nonmonotonic-native-sequence":
                for record in records:
                    if record["sequence"] in (1, 2):
                        record["sequence"] = 3 - record["sequence"]
            for record in records:
                record["worker_pid"] = 4242
            if self.annotation_defect == "request-worker-changed" and len(records) > 2:
                records[1]["worker_pid"] = 4343
            with self.trace.open("a", encoding="utf-8") as stream:
                for record in records:
                    stream.write(json.dumps(record) + "\n")
        return completed

    def dispatch(self, args):
        if args.command == "document" and args.document_command.startswith("annotation-"):
            document = self.documents[args.document_id]
            options = document["annotations"]
            result = {"ok": True, "action": "document." + args.document_command,
                      "session_id": args.session, "document": self.descriptor(document, args.session)}
            if args.document_command == "annotation-options":
                self.last_native_calls.extend("IModelDocExtension.GetUserPreference" + spec["kind"]
                                              for spec in ANNOTATION_FIELDS.values())
                result["options"] = deepcopy(options)
                if self.annotation_defect == "read-dirties-document":
                    document["modified"] = True
                    result["document"] = self.descriptor(document, args.session)
                return result
            _, values, *_ = _typed_operation(args)
            if args.expected_update_stamp is not None and args.expected_update_stamp != document["stamp"]:
                return self.failure("DocumentUpdateConflict")
            if document["lease"] and document["lease"]["session"] != args.session:
                return self.failure("DocumentLeaseConflict")
            mutation = {"attempted": False, "may_have_changed": False}
            if document["read_only"]:
                return self.failure("ValueError", mutation=mutation)
            field, value, expected = values["field"], values["value"], values["expected_value"]
            self.last_native_calls.extend("IModelDocExtension.GetUserPreference" + spec["kind"]
                                          for spec in ANNOTATION_FIELDS.values())
            if expected != options[field]["value"]:
                if self.annotation_defect == "cas-reached-native":
                    self.last_native_calls.append("IModelDocExtension.SetUserPreferenceInteger")
                return self.failure("DocumentAnnotationConflict", mutation=mutation)
            before = deepcopy(options)
            changed = value != options[field]["value"]
            if changed:
                self.setter_attempts += 1
                self.last_native_calls.append("IModelDocExtension.SetUserPreference" + ANNOTATION_FIELDS[field]["kind"])
                if self.annotation_defect == "native-write-failed":
                    return self.failure("NativeAnnotationFailure", mutation={"attempted": True, "may_have_changed": True})
                self.native_sets += 1
                document["annotations"][field] = option(field, value)
                self.last_native_calls.extend("IModelDocExtension.GetUserPreference" + spec["kind"]
                                              for spec in ANNOTATION_FIELDS.values())
                if not document["modified"]:
                    self.last_native_calls.append("IModelDoc2.SetSaveFlag")
                document["modified"] = True
                self.last_native_calls.extend("IModelDocExtension.GetUserPreference" + spec["kind"]
                                              for spec in ANNOTATION_FIELDS.values())
            elif self.annotation_defect == "same-value-dirty":
                document["modified"] = True
            elif self.annotation_defect == "same-value-native-setter":
                # A deceptively clean response must fail its independent native trace.
                self.last_native_calls.append("IModelDocExtension.SetUserPreference" + ANNOTATION_FIELDS[field]["kind"])
            result.update(field=field, before=before, options=deepcopy(document["annotations"]), changed=changed,
                          mutation={"attempted": changed, "may_have_changed": changed},
                          document=self.descriptor(document, args.session))
            return result
        result = super().dispatch(args)
        if args.command == "daemon":
            result["result"].update(server_version=__version__)
            result["result"]["host"].update(owned_by_daemon=True, visible=False, shared_interactive=False)
        if args.command == "document" and args.document_command in ("create", "open"):
            document = self.documents[result["document"]["document_id"]]
            if "annotations" not in document:
                document["annotations"] = initial_options()
                document["annotations"].update(deepcopy(self.initial_options_by_type.get(result["document"]["type"], {})))
            if (args.document_command == "open" and args.read_only
                    and self.annotation_defect == "reopen-lost-value"):
                document["annotations"]["bent_leader.enabled"] = option("bent_leader.enabled", False)
        if args.command == "document" and args.document_command == "save-as":
            result["save_warnings"] = None
            if self.annotation_defect == "source-changed":
                (self.fixtures / "annotations.SLDPRT").write_bytes(b"changed original")
            if self.annotation_defect == "saved-size-mismatch":
                result["artifact"]["size_bytes"] += 1
        return result


class DocumentAnnotationsSmokeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "evidence"
        self.fixtures = Path(temporary.name) / "fixtures"
        self.fixtures.mkdir()
        for suffix in ("SLDPRT", "SLDASM", "SLDDRW"):
            (self.fixtures / ("annotations." + suffix)).write_bytes(b"prepared native fixture" * 100)
        self.trace = Path(temporary.name) / "native-trace.log"
        self.trace.write_text("")
        self.fake = AnnotationsCLI(self.directory, self.fixtures, self.trace)
        self.arguments = ["--output-dir", str(self.directory), "--fixture-dir", str(self.fixtures),
                          "--native-trace", str(self.trace), "--host-fixture-dir", r"C:\fixtures",
                          "--host-output-dir", r"C:\proof"]

    def run_gate(self):
        with mock.patch.object(gate.modeling.subprocess, "run", side_effect=self.fake.run), \
                mock.patch("sys.stdout", new=io.StringIO()):
            gate.main(self.arguments)

    def record(self):
        return json.loads((self.directory / "document-annotations.json").read_text())

    def test_three_kinds_all_seven_changed_persistence_and_arrow_reverse_are_distinct(self):
        self.run_gate()
        record = self.record()
        self.assertEqual((record["state"], record["success"], record["cleanup_errors"]), ("completed", True, []))
        self.assertEqual([case["format"] for case in record["annotation_cases"]], ["SLDPRT", "SLDASM", "SLDDRW"])
        self.assertEqual(self.fake.native_sets, 30)
        self.assertEqual(self.fake.documents, {})
        self.assertEqual(record["request_timeout_seconds"], 600)
        self.assertEqual(record["group_timeout_seconds"], 1800)
        self.assertFalse(record["covers_full_modeling_suite"])
        for case in record["annotation_cases"]:
            self.assertTrue(case["success"])
            before = case["initial"]["options"]
            after = case["primary_reopened_options"]["options"]
            self.assertTrue(all(before[field]["value"] != after[field]["value"] for field in ANNOTATION_FIELDS))
            reverse = case["reverse_reopened_options"]["options"]
            for field in gate.ARROW_FIELDS:
                self.assertEqual(reverse[field], before[field])
            for field in set(ANNOTATION_FIELDS) - set(gate.ARROW_FIELDS):
                self.assertEqual(reverse[field], after[field])
            self.assertEqual(len(case["same_values"]), 7)
            self.assertTrue(all(row["native_trace"]["native_setter_calls"] == 0 for row in case["same_values"]))
            self.assertEqual(len({row["document"]["document_id"] for row in
                                  (case["open"], case["primary_reopen"], case["reverse_open"], case["reverse_reopen"])}), 4)
        self.assertEqual(record["host"], record["host_after"])
        self.assertEqual(record["native_trace_snapshot"]["verified_request_count"], len(record["native_call_proofs"]))
        self.assertFalse(any(call.command == "document" and call.document_command == "save" for call in self.fake.calls))

    def test_first_native_failure_has_one_attempt_and_failed_receipt_without_retry(self):
        self.fake.annotation_defect = "native-write-failed"
        with self.assertRaises(RuntimeError):
            self.run_gate()
        self.assertEqual(self.fake.setter_attempts, 1)
        self.assertEqual(self.fake.native_sets, 0)
        self.assertEqual((self.record()["state"], self.record()["success"]), ("failed", False))
        self.assertEqual(self.fake.documents, {})

    def test_hosted_open_arrow_initial_values_use_only_supported_write_targets(self):
        self.fake.initial_options_by_type[3] = {
            "arrow.edge_vertex": option("arrow.edge_vertex", "open"),
            "arrow.unattached": option("arrow.unattached", "open"),
            "bent_leader.length_mm": option("bent_leader.length_mm", 6.25),
        }
        self.run_gate()
        record = self.record()
        self.assertTrue(record["success"])
        self.assertEqual(self.fake.native_sets, 30)
        drawing = record["annotation_cases"][-1]
        self.assertEqual(drawing["initial"]["options"]["arrow.edge_vertex"]["value"], "open")
        self.assertEqual(drawing["changed_values"]["arrow.edge_vertex"], "closed")
        self.assertEqual(drawing["reverse_values"], {
            "arrow.edge_vertex": "dot", "arrow.face_surface": "dot", "arrow.unattached": "none",
        })
        for case in record["annotation_cases"]:
            for row in case["writes"] + case["reverse_writes"]:
                result = row["result"]
                field = result["field"]
                if field in gate.ARROW_FIELDS:
                    self.assertIn(result["options"][field]["value"], ANNOTATION_FIELDS[field]["writable"])
        setters = [call for call in self.fake.calls if call.command == "document"
                   and call.document_command == "annotation-option-set"]
        self.assertFalse(any(call.value == "open" for call in setters))
        self.assertTrue(any(call.expected_value == "open" for call in setters))

    def test_unknown_initial_arrow_profile_fails_before_any_preference_setter(self):
        self.fake.initial_options_by_type[1] = {"arrow.edge_vertex": {"value": "other", "native_value": 290}}
        with self.assertRaisesRegex(RuntimeError, "unrecognized initial enum profile: arrow.edge_vertex"):
            self.run_gate()
        self.assertEqual(self.fake.setter_attempts, 0)
        self.assertEqual(self.record()["state"], "failed")
        self.assertEqual(self.fake.documents, {})

    def test_persistence_source_dirty_state_trace_and_size_defects_fail(self):
        defects = {
            "reopen-lost-value": "changed annotation values did not persist after reopen",
            "source-changed": "annotation verification changed a source/copy file",
            "same-value-dirty": "same-value annotation operation changed document state",
            "same-value-native-setter": "annotation setter or SetSaveFlag call count",
            "cas-reached-native": "annotation setter or SetSaveFlag call count",
            "missing-trace": "native trace does not contain the completed annotation request",
            "missing-trace-end": "native annotation call boundaries are missing or repeated",
            "missing-preference-getter": "annotation native preference getter count is incomplete",
            "misordered-native-readback": "annotation native preference read/write ordering is incomplete",
            "saved-size-mismatch": "edited annotation copy did not save cleanly",
            "read-dirties-document": "annotation read changed background document state",
            "operation-end-before-native": "annotation operation trace does not enclose its native calls",
            "native-end-before-begin": "annotation native trace call ordering is invalid",
            "nonmonotonic-native-sequence": "annotation native trace call ordering is invalid",
            "request-worker-changed": "annotation request trace changed its owning worker",
        }
        for defect, message in defects.items():
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                self.directory = Path(directory) / "evidence"
                self.arguments[1] = str(self.directory)
                self.trace.write_text("")
                self.fake = AnnotationsCLI(self.directory, self.fixtures, self.trace)
                self.fake.annotation_defect = defect
                with self.assertRaisesRegex(RuntimeError, message):
                    self.run_gate()
                self.assertEqual((self.record()["state"], self.record()["success"]), ("failed", False))
                self.assertEqual(self.fake.documents, {})

    def test_existing_receipt_refuses_without_cli_or_overwrite(self):
        self.directory.mkdir()
        receipt = self.directory / "document-annotations.json"
        receipt.write_text("original evidence")
        with mock.patch.object(gate.modeling.subprocess, "run") as cli:
            with self.assertRaises(FileExistsError):
                gate.main(self.arguments)
        cli.assert_not_called()
        self.assertEqual(receipt.read_text(), "original evidence")

    def test_missing_drawing_fixture_refuses_before_any_cli(self):
        (self.fixtures / "annotations.SLDDRW").unlink()
        with mock.patch.object(gate.modeling.subprocess, "run") as cli:
            with self.assertRaises(RuntimeError):
                gate.main(self.arguments)
        cli.assert_not_called()
        self.assertEqual(self.record()["state"], "failed")

    def test_group_deadline_rejects_before_or_after_one_command_without_retry(self):
        instance = gate.AnnotationSmoke(directory=self.directory, host_directory=r"C:\proof", endpoint="localhost:1")
        instance.group_started = 0
        with mock.patch.object(gate.time, "monotonic", return_value=1801), \
                mock.patch.object(gate.modeling.ModelingSmoke, "command") as command:
            with self.assertRaisesRegex(RuntimeError, "1800-second group budget"):
                instance.command("document", "list")
        command.assert_not_called()
        with mock.patch.object(gate.time, "monotonic", side_effect=(1799, 1801)), \
                mock.patch.object(gate.modeling.ModelingSmoke, "command", return_value={}) as command:
            with self.assertRaisesRegex(RuntimeError, "1800-second group budget"):
                instance.command("document", "list")
        command.assert_called_once_with("document", "list")

    def test_checkpoint_failure_keeps_original_failure_and_always_cleans_once(self):
        first = RuntimeError("first annotation failure")
        for error in (None, first):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                cleanup_method = gate.modeling.ModelingSmoke.cleanup
                with (mock.patch.object(gate, "run", side_effect=error) as run,
                      mock.patch.object(gate.modeling.ModelingSmoke, "cleanup", autospec=True,
                                        side_effect=cleanup_method) as cleanup,
                      mock.patch.object(gate.modeling.ModelingSmoke, "write_checkpoint",
                                        side_effect=OSError("checkpoint failed")) as checkpoint):
                    with self.assertRaises(type(error) if error else OSError) as raised:
                        gate.main(["--output-dir", directory, "--fixture-dir", str(self.fixtures),
                                   "--native-trace", str(self.trace)])
                if error is not None:
                    self.assertIs(raised.exception, first)
                run.assert_called_once()
                cleanup.assert_called_once()
                checkpoint.assert_called_once_with("document-annotations-final")


if __name__ == "__main__":
    unittest.main()
