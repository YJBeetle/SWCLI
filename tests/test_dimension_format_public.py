"""SDK/MCP native-context preservation and public trace proof failure cases."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import test_dimension_format as fixtures
from swcli.sdk import Client
from swcli.mcp import DaemonBridge

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dimension_public_test", ROOT / "scripts/ci/verify-dimension-format-public.py")
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class DimensionPublicTests(unittest.TestCase):
    def test_typed_sdk_preserves_false_complete_snapshot_and_required_context(self):
        fixture = fixtures.DimensionFormatTests(); fixture.setUp()
        parameters = fixture.values(value=False)
        result = fixture.public(True, parameters)
        client = Client(session_id="display-sdk")
        def respond(operation, values, **context):
            return dict(api_version="swcli/v1", request_id=context["request_id"], success=True, duration_ms=1, result=result)
        with mock.patch("swcli.sdk.client.call_daemon", side_effect=respond) as wire:
            response = client.document.dimension_format_set(**parameters, document_id=fixture.entry.document_id,
                expected_update_stamp=0, lease_id=fixture.lease["lease_id"], request_id="display-once")
            self.assertTrue(response.success)
            self.assertEqual(wire.call_args.args, ("document.dimension-format-set", parameters))
            self.assertEqual(wire.call_args.kwargs["expected_update_stamp"], 0)
            self.assertEqual(wire.call_args.kwargs["lease_id"], fixture.lease["lease_id"])
            self.assertEqual(wire.call_args.kwargs["session_id"], "display-sdk")
            wire.assert_called_once()
        with mock.patch("swcli.sdk.client.call_daemon") as wire, self.assertRaises(ValueError):
            client.document.dimension_format_set(field="parentheses", value=False, expected_format={},
                document_id=fixture.entry.document_id, expected_update_stamp=0, lease_id=fixture.lease["lease_id"])
        wire.assert_not_called()

    def test_mcp_execute_preserves_snapshot_and_has_no_lifecycle_side_effect(self):
        parameters = dict(field="dual_position", value="top", expected_format=dict(dual_display=False, dual_position=1, parentheses=False))
        arguments = dict(operation="document.dimension-format-set", parameters=parameters, document_id="d-ab12cd",
                         expected_update_stamp=0, lease_id="l-ab12cd34ef56", request_id="display-once", session_id="display-mcp")
        with mock.patch("swcli.mcp.DaemonManager") as manager, mock.patch("swcli.mcp.call_daemon", return_value={
                "api_version": "swcli/v1", "request_id": "display-once", "success": True, "duration_ms": 1, "result": {"ok": True}}) as wire:
            bridge = DaemonBridge(session_id="default")
            self.assertTrue(bridge.call("execute", arguments)["success"])
            self.assertEqual(wire.call_args.args, (arguments["operation"], parameters))
            for key in ("document_id", "expected_update_stamp", "lease_id", "request_id", "session_id"):
                self.assertEqual(wire.call_args.kwargs[key], arguments[key])
            manager.return_value.start.assert_not_called(); manager.return_value.stop.assert_not_called()
            wire.assert_called_once()

    def proof(self, damage=None):
        operation = "document.dimension-format-set"
        method = "IModelDocExtension.SetUserPreferenceToggle"
        rows = []
        def pair(sequence, call, stage):
            rows.extend(dict(event="swcli.native-call", request_id="one", operation=operation, worker_pid=123,
                             sequence=sequence, call=call, stage=stage, phase=phase) for phase in ("begin", "end"))
        pair(0, operation, "operation")
        begin, end = rows; rows.clear(); rows.append(begin)
        cycle = ["IModelDocExtension.GetUserPreferenceToggle", "IModelDocExtension.GetUserPreferenceInteger", "IModelDocExtension.GetUserPreferenceToggle"]
        sequence = 0
        for index in range(4):
            if index == 2:
                sequence += 1; pair(sequence, method, "document-dimension-format")
            for call in cycle:
                sequence += 1; pair(sequence, call, "document-dimension-format")
        rows.append(end)
        if damage: damage(rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows))
            trace = public.DimensionTrace(path)
            gate = SimpleNamespace(record={"events": [{"command": ["swcli", "document", "dimension-format-set", "dual_display", "true"],
                "result": {"request_id": "one", "ok": True}}]})
            return trace.verify(gate, setters=1)

    def test_public_trace_requires_complete_single_call_boundaries(self):
        self.assertEqual(self.proof()["native_format_getters"], 12)
        for damage in (lambda rows: rows.pop(-2), lambda rows: rows.extend(rows[1:3]),
                       lambda rows: rows[1].update(worker_pid=456),
                       lambda rows: rows[1].update(operation="document.units")):
            with self.subTest(damage=damage), self.assertRaises(RuntimeError): self.proof(damage)

    def test_public_plan_exercises_every_setter_value_and_saves_nondefault_snapshot(self):
        from itertools import product
        for dual, position, parentheses in product((False, True), public.POSITIONS.values(), (False, True)):
            initial = dict(dual_display=dual, dual_position=position, parentheses=parentheses)
            current = dict(initial)
            actual = {field: set() for field in initial}
            for field, value in public.mutation_plan(initial):
                native = public.POSITIONS[value] if field == "dual_position" else value
                if native != current[field]: actual[field].add(native)
                current[field] = native
            with self.subTest(initial=initial):
                self.assertEqual(actual["dual_display"], {False, True})
                self.assertEqual(actual["parentheses"], {False, True})
                self.assertEqual(actual["dual_position"], set(public.POSITIONS.values()))
                self.assertTrue(all(current[field] != initial[field] for field in initial))

    def test_public_lease_refusal_reaches_daemon_with_a_valid_wire_token(self):
        from jsonschema import Draft202012Validator
        from swcli.protocol import load_schema
        refusal = dict(ok=False, action="document.dimension-format-set", error=dict(type="DocumentLeaseConflict", message="held by writer"))
        gate = SimpleNamespace(command=mock.Mock(return_value=refusal))
        before = dict(format=dict(dual_display=False, dual_position=1, parentheses=False),
                      document=dict(update_stamp=0))
        public.edit(gate, "d-ab12cd", before, "dual_display", True, mock.Mock(),
                    error="DocumentLeaseConflict", session="contender")
        token = gate.command.call_args.kwargs["lease"]
        Draft202012Validator(load_schema("request")["properties"]["lease_id"]).validate(token)
        self.assertEqual(gate.command.call_args.kwargs["expected_error"], "DocumentLeaseConflict")

    def test_public_trace_rejects_wrong_setter_kind_or_order(self):
        def wrong_kind(rows):
            for row in rows:
                if row["call"] == "IModelDocExtension.SetUserPreferenceToggle":
                    row["call"] = "IModelDocExtension.SetUserPreferenceDouble"
        with self.assertRaises(RuntimeError): self.proof(wrong_kind)
        def wrong_order(rows):
            setter = [row for row in rows if row["call"] == "IModelDocExtension.SetUserPreferenceToggle"]
            rows[:] = rows[:1] + setter + [row for row in rows[1:-1] if row not in setter] + rows[-1:]
            # Preserve valid unique consecutive trace sequence numbers so the
            # failed proof is specifically about the setter's operation order.
            for index, row in enumerate(rows[1:-1]): row["sequence"] = index // 2 + 1
        with self.assertRaises(RuntimeError): self.proof(wrong_order)

    def test_public_write_default_timeout_is_bounded_without_none_comparison(self):
        # Exercise the inherited write() path used by stale-stamp and real
        # edits: it explicitly forwards timeout_seconds=None to command().
        for requested, now, expected in ((None, 110, 600), (300, 110, 300),
                                         (900, 110, 600), (None, 1835, 50)):
            with self.subTest(requested=requested, now=now):
                gate = object.__new__(public.DimensionSmoke)
                gate.cleaning_up = False
                gate.group_started = 100
                gate.request_timeout_seconds = 600
                gate.leases = {"d-ab12cd": "l-ab12cd34ef56"}
                gate.lease_deadlines = {"d-ab12cd": 99999}
                with mock.patch.object(public.time, "monotonic", return_value=now), \
                        mock.patch.object(public.annotations.AnnotationSmoke, "command", return_value={"ok": True}) as command:
                    result = gate.write("document", "dimension-format-set", "dual_display", "true",
                                        document="d-ab12cd", timeout_seconds=requested)
                self.assertTrue(result["ok"])
                command.assert_called_once()
                self.assertEqual(command.call_args.kwargs["timeout_seconds"], expected)
                self.assertEqual(command.call_args.kwargs["lease"], "l-ab12cd34ef56")

    def test_public_group_deadline_stops_before_dispatch(self):
        gate = object.__new__(public.DimensionSmoke)
        gate.cleaning_up = False
        gate.group_started = 100
        with mock.patch.object(public.time, "monotonic", return_value=1886), \
                mock.patch.object(public.annotations.AnnotationSmoke, "command") as command:
            with self.assertRaisesRegex(RuntimeError, "1800 seconds"):
                gate.command("document", "dimension-format")
        command.assert_not_called()

    def test_public_mode_precedes_unrelated_suites_and_stops_owned_daemon_once(self):
        wrapper = (ROOT / "scripts/ci/windows/smoke-solidworks.ps1").read_text()
        block = wrapper.split("    if ($DimensionFormatFixtureDirectory) {", 1)[1].split("    if ($VisibleSmoke)", 1)[0]
        self.assertIn("verify-dimension-format-public.py", block)
        self.assertIn("Assert-OwnedDaemonExit", block)
        self.assertIn("$started = $false", block)
        self.assertIn("return", block)
        self.assertNotIn("daemon restart", block)


if __name__ == "__main__": unittest.main()
