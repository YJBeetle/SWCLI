"""Reject incomplete or misattributed public native evidence."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("_line_font_public_test", Path(__file__).parents[1] / "scripts/ci/verify-line-font-public.py")
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class LineFontPublicTraceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "trace.log"
        self.gate = SimpleNamespace(record={})
        self.operation = "document.line-font-set"

    def rows(self, calls, terminal="end"):
        rows = []
        for sequence, call in enumerate([self.operation, *calls]):
            for phase in ("begin", "end"):
                if sequence == 0 and phase == "end":
                    continue
                rows.append(dict(event="swcli.native-call", request_id="request", operation=self.operation,
                                 sequence=sequence, call=call, phase=phase, worker_pid=100))
        rows.append(dict(event="swcli.native-call", request_id="request", operation=self.operation,
                         sequence=0, call=self.operation, phase=terminal, worker_pid=100))
        return rows

    def verify(self, rows, getters=4, setters=0):
        self.path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        public.Trace(self.path, self.gate).verify(dict(request_id="request"), self.operation,
                                                getters=getters, setters=setters)

    def test_failed_precondition_has_zero_native_calls(self):
        self.verify(self.rows([], "error"), getters=0)

    def test_exact_integer_snapshot_read_has_four_paired_calls(self):
        self.verify(self.rows(["IModelDocExtension.GetUserPreferenceInteger"] * 4))
        self.assertEqual(self.gate.record["native_call_proofs"][0]["setters"], 0)

    def test_state_observation_getters_are_preserved_separately(self):
        self.verify(self.rows(["GetType", "GetSaveFlag"] + ["IModelDocExtension.GetUserPreferenceInteger"]*4))
        self.assertEqual(self.gate.record["native_call_proofs"][0]["observation_calls"], ["GetType", "GetSaveFlag"])

    def test_single_mutation_requires_three_complete_snapshots_in_order(self):
        getter = "IModelDocExtension.GetUserPreferenceInteger"
        setter = "IModelDocExtension.SetUserPreferenceInteger"
        self.verify(self.rows([getter]*4 + [setter] + [getter]*4 + ["IModelDoc2.SetSaveFlag"] + [getter]*4),
                    getters=12, setters=1)
        with self.assertRaises(RuntimeError):
            self.verify(self.rows([getter]*8 + [setter] + [getter]*4), getters=12, setters=1)

    def test_global_call_duplicate_or_missing_terminal_fails(self):
        calls = ["IModelDocExtension.GetUserPreferenceInteger"] * 4
        rows = self.rows(calls)
        for invalid in (self.rows(calls + ["ISldWorks.SetUserPreferenceIntegerValue"]),
                        rows[:-1], rows + [rows[1]],
                        [{**row, "worker_pid": 101} if index == 1 else row for index, row in enumerate(rows)]):
            with self.subTest(case=len(invalid)), self.assertRaises(RuntimeError):
                self.verify(invalid)
