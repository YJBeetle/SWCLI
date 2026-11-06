"""Reject incomplete or misattributed public native evidence."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest import mock

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
        calls = ["CommandInProgress", "SldWorks.CommandInProgress.enter", "CommandInProgress"] + calls + ["SldWorks.CommandInProgress.restore", "CommandInProgress"]
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


class LineFontRuntimeContractTests(unittest.TestCase):
    def native(self):
        return dict(server_version="test", worker_alive=True, host_connected=True, recovery_required=False,
                    host=dict(process_id=10, owned_by_daemon=True, visible=False))

    def test_actual_cli_status_routes_to_plain_daemon_health(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from swcli.cli import main
        native = self.native()
        envelope = dict(api_version="swcli/v1", request_id="health-test", success=True, duration_ms=0, result=native)
        stdout = StringIO()
        with mock.patch("swcli.daemon.main.call_daemon", return_value=envelope) as transport, redirect_stdout(stdout):
            self.assertEqual(main(["daemon", "status", "--json"]), 0)
        self.assertEqual(transport.call_args.args[0], "daemon.health")
        gate = public.LineFontSmoke.__new__(public.LineFontSmoke)
        gate.command = mock.Mock(return_value=json.loads(stdout.getvalue()))
        self.assertEqual(gate.health(), native)
        gate.command.assert_called_once_with("daemon", "status")

    def test_disconnected_health_cannot_be_promoted(self):
        gate = public.LineFontSmoke.__new__(public.LineFontSmoke)
        gate.command = mock.Mock(return_value={"result": {**self.native(), "host_connected": False}})
        with self.assertRaises(RuntimeError):
            gate.health()

    def test_initial_summary_exists_before_first_atomic_checkpoint(self):
        with TemporaryDirectory() as directory:
            gate = public.create_gate(Path(directory), "127.0.0.1:18495")
            self.assertTrue(gate.record_path.is_file())
            gate.record.update(state="failed", error=dict(type="FixtureError", message="first failure"))
            gate.checkpoint("first-failure-preserved")
            actual = json.loads(gate.record_path.read_text())
            self.assertEqual(actual["error"]["message"], "first failure")
            self.assertEqual(actual["stage"], "first-failure-preserved")
            self.assertIsNone(gate.checkpoint_error)


class LineFontOwnedWorkerIntegrationTests(unittest.TestCase):
    def test_real_request_trace_and_owned_sequence_wrap_actual_operation(self):
        from contextlib import redirect_stderr
        from io import StringIO
        import os
        from swcli.hosts.native_trace import trace_native_request
        from swcli.hosts.native_sequence import native_api_sequence
        from test_document_line_font import LineFontTests
        fixture = LineFontTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fx = fixture.fx
        fx.app.CommandInProgress = False
        fx.app.RevisionNumber = "33.5.0"
        stderr = StringIO()
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), redirect_stderr(stderr):
            with trace_native_request("owned-request", "document.line-font-set"), native_api_sequence(fx.app, enabled=True):
                result = fx.operation("document.line-font-set", dict(field="visible_edges.style", value=1,
                                                                     expected_options=fixture.before))
        self.assertTrue(result["ok"], result)
        self.assertFalse(fx.app.CommandInProgress)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stderr.log"
            path.write_text(stderr.getvalue())
            gate = SimpleNamespace(record={})
            public.Trace(path, gate).verify(dict(request_id="owned-request"), "document.line-font-set", getters=12, setters=1)
            self.assertEqual(gate.record["native_call_proofs"][0]["sequence_calls"],
                ["CommandInProgress", "SldWorks.CommandInProgress.enter", "CommandInProgress",
                 "SldWorks.CommandInProgress.restore", "CommandInProgress"])
