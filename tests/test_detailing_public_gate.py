"""Public gate control flow is portable-tested; this supplies no native acceptance."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from swcli.cli import _typed_operation
from swcli.document_detailing import DETAILING_FIELDS
from tests.test_document_annotations_smoke import AnnotationsCLI

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_public_detailing_test", ROOT / "scripts/ci/verify-detailing-public.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class DetailingCLI(AnnotationsCLI):
    def __init__(self, directory, trace):
        super().__init__(directory, directory, trace)
        self.detailing_calls = []
        self.setter_attempts = 0
        self.detailing_defect = None

    def dispatch(self, args):
        if args.command == "document" and args.document_command.startswith("detailing-"):
            self.detailing_calls = []
            document = self.documents[args.document_id]
            result = dict(ok=True, action="document." + args.document_command, session_id=args.session,
                          document=self.descriptor(document, args.session))
            if args.document_command == "detailing-options":
                self.detailing_calls = ["IModelDocExtension.GetUserPreferenceToggle"] * 2
                return {**result, "options": deepcopy(document["detailing"])}
            if document["lease"]["session"] != args.session:
                return self.failure("DocumentLeaseConflict")
            if args.expected_update_stamp != document["stamp"]:
                return self.failure("DocumentUpdateConflict")
            mutation = {"attempted": False, "may_have_changed": False}
            if document["read_only"]:
                return {**result, **self.failure("ValueError"), "mutation": mutation}
            _, values, *_ = _typed_operation(args)
            self.detailing_calls = ["IModelDocExtension.GetUserPreferenceToggle"] * 2
            before = deepcopy(document["detailing"])
            if values["expected_options"] != before:
                return {**result, **self.failure("ValueError"), "mutation": mutation, "field": args.field, "before": before}
            changed = before[args.field] != values["value"]
            if changed:
                self.setter_attempts += 1
                self.detailing_calls += ["IModelDocExtension.SetUserPreferenceToggle"]
                if self.detailing_defect == "setter-failed":
                    return {**result, **self.failure("RuntimeError"), "mutation": {"attempted": True, "may_have_changed": True}}
                document["detailing"][args.field] = values["value"]
                self.detailing_calls += ["IModelDocExtension.GetUserPreferenceToggle"] * 2
                if not document["modified"]:
                    self.detailing_calls += ["IModelDoc2.SetSaveFlag"]
                document["modified"] = True
                self.detailing_calls += ["IModelDocExtension.GetUserPreferenceToggle"] * 2
            result.update(field=args.field, before=before, options=deepcopy(document["detailing"]), changed=changed,
                          mutation={"attempted": changed, "may_have_changed": changed},
                          document=self.descriptor(document, args.session))
            if changed:
                result["native_return"] = True
            return result
        result = super().dispatch(args)
        if args.command == "daemon":
            result["result"]["host"]["platform"] = "windows"
        if args.command == "document" and args.document_command in ("create", "open"):
            document = self.documents[result["document"]["document_id"]]
            if args.document_command == "create" and args.type == "drawing":
                document["type"] = 3
                result["document"]["type"] = 3
                result["views"] = []
            document.setdefault("detailing", dict(zip(DETAILING_FIELDS, (False, True))))
            if args.document_command == "open" and args.read_only and self.detailing_defect == "persistence-lost":
                document["detailing"] = dict(zip(DETAILING_FIELDS, (False, True)))
        return result

    def run(self, command, **keywords):
        completed = super().run(command, **keywords)
        args = self.calls[-1]
        if args.command == "document" and args.document_command.startswith("detailing-"):
            result = json.loads(completed.stdout)
            operation = "document." + args.document_command
            request = result["request_id"]
            base = dict(event="swcli.native-call", operation=operation, request_id=request, worker_pid=4242)
            records = [{**base, "sequence": 0, "call": operation, "phase": "begin", "monotonic_seconds": 0}]
            for sequence, name in enumerate(self.detailing_calls, 1):
                records += [{**base, "sequence": sequence, "call": name, "phase": phase,
                             "monotonic_seconds": sequence} for phase in ("begin", "end")]
            phase = "error" if result.get("error", {}).get("type") in ("DocumentLeaseConflict", "DocumentUpdateConflict") else "end"
            records.append({**base, "sequence": 0, "call": operation, "phase": phase, "monotonic_seconds": len(records)})
            if self.detailing_defect == "missing-trace" and self.setter_attempts:
                records = records[:-1]
            with self.trace.open("a") as stream:
                for row in records:
                    stream.write(json.dumps(row) + "\n")
        return completed


class PublicDetailingGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.trace = self.directory / "trace.jsonl"
        self.trace.write_text("")
        self.fake = DetailingCLI(self.directory, self.trace)
        self.smoke = gate.support.AnnotationSmoke(directory=self.directory, host_directory=str(self.directory), endpoint="127.0.0.1:1")
        self.trace_reader = gate.DetailingTrace(self.trace)

    def run_gate(self):
        with mock.patch.object(gate.support.modeling.subprocess, "run", side_effect=self.fake.run), \
                mock.patch.object(gate, "contracts") as contracts, mock.patch("sys.stdout", new=io.StringIO()):
            try:
                gate.run(self.smoke, self.trace_reader, "C:/official/gb.drwdot")
            finally:
                self.smoke.cleanup()
        return contracts

    def test_public_gate_tests_both_values_with_four_independent_save_reopens(self):
        contracts = self.run_gate()
        contracts.assert_called_once()
        self.assertTrue(self.smoke.record["success"])
        self.assertEqual(self.fake.setter_attempts, 4)
        self.assertEqual(len(self.smoke.record["writes"]), 4)
        for row in self.smoke.record["writes"]:
            self.assertEqual(row["reopened_options"]["options"], row["write"]["options"])
            self.assertFalse(row["readonly_refusal"]["mutation"]["attempted"])
            self.assertFalse(row["noop"]["changed"])
        self.assertEqual(self.fake.documents, {})
        self.assertGreater(len(self.trace_reader.proofs), 20)

    def test_first_native_failure_stops_after_one_setter_attempt(self):
        self.fake.detailing_defect = "setter-failed"
        with self.assertRaises(RuntimeError):
            self.run_gate()
        self.assertEqual(self.fake.setter_attempts, 1)
        self.assertEqual(self.fake.documents, {})

    def test_missing_trace_or_lost_persistence_fail_before_a_second_write(self):
        for defect in ("missing-trace", "persistence-lost"):
            with self.subTest(defect=defect):
                self.setUp()
                self.fake.detailing_defect = defect
                with self.assertRaises(RuntimeError):
                    self.run_gate()
                self.assertEqual(self.fake.setter_attempts, 1)
                self.assertEqual(self.fake.documents, {})


if __name__ == "__main__":
    unittest.main()
