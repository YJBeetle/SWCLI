"""Offline fault injection for NEW-only gate; no native/VM or success artifacts."""

from copy import deepcopy
from contextlib import redirect_stderr
from io import StringIO
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/ci" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load("test_new_detailing_line_gate", "detailing_line_gate.py")
watchdog = load("test_new_detailing_line_watchdog", "run-detailing-lines-calibration.py")
native = load("test_new_detailing_line_backend", "verify-detailing-lines-calibration.py")


class FakeBackend:
    """Stateful saved-byte fixture, not simulated SOLIDWORKS acceptance."""
    def __init__(self, failure=None, initial=None):
        self.values = deepcopy(initial) if initial is not None else dict(zip(gate.DETAILING_LINE_SNAPSHOT_FIELDS, (True, False, False, True)))
        self.state = dict(document_id="d-fake00", update_stamp=10, modified=False, read_only=False,
                         active=False, current=False, normal_sheet=True, layout={"sheet": [1, 2]},
                         foreground={"id": "d-front", "configuration": "default"})
        self.failure, self.enabled, self.writes, self.reopens, self.calls = failure, False, 0, 0, []
        self.saved = {}

    def observe(self):
        return deepcopy(self.state)

    def enable_internal(self):
        self.enabled = True
        return {"fake": True}

    def validate(self, operation, result):
        pass  # Real backend separately runs the production result schema.

    def invoke(self, operation, field, value, expected, mode):
        self.calls.append((operation, mode))
        request = "fake-%d" % len(self.calls)
        rows = []
        def row(sequence, call, phase):
            return dict(request_id=request, operation=operation, sequence=sequence,
                        call=call, phase=phase, duration_ms=0)
        rows.append(row(0, operation, "begin"))
        result = dict(ok=True, action=operation, options=deepcopy(self.values), write_enabled=self.enabled)
        raised = None
        getters, setters = 4, 0
        if operation == gate.SET:
            result["mutation"] = dict(attempted=False, may_have_changed=False)
            if mode != "normal":
                getters = 0
                result = None
                raised = dict(type="DocumentUpdateConflict" if mode == "stale-stamp" else "DocumentLeaseConflict")
            elif self.state["read_only"]:
                getters = 0
                result.update(ok=False, error={"type": "ValueError", "message": "read-only"})
            elif expected != self.values:
                result.update(ok=False, error={"type": "ValueError", "message": "CAS"})
            elif self.values[field] == value:
                result["changed"] = False
            else:
                self.writes += 1
                getters, setters = 12, 1
                result.update(before=deepcopy(self.values), changed=True, native_return=True,
                              mutation=dict(attempted=True, may_have_changed=True))
                self.values[field] = value
                self.state.update(modified=True, update_stamp=self.state["update_stamp"] + 1)
                result["options"] = deepcopy(self.values)
                if self.failure == "partial" and self.writes == 3:
                    result.update(ok=False, error={"type": "RuntimeError", "message": "first setter business error"})
                if self.failure == "old-guard" and self.writes == 3:
                    old = next(iter(gate.DETAILING_FIELDS))
                    self.values[old] = not self.values[old]
                    result["options"] = deepcopy(self.values)
                if self.failure == "foreground" and self.writes == 3:
                    self.state["foreground"] = {"configuration": "drift"}
                if self.failure == "layout" and self.writes == 3:
                    self.state["layout"] = {"sheet": [3, 4]}
                if self.failure == "dirty" and self.writes == 3:
                    self.state["modified"] = False
        for sequence, call in enumerate([gate.GETTER] * getters + [gate.SETTER] * setters, 1):
            rows.extend([row(sequence, call, "begin"), row(sequence, call, "end")])
        rows.append(row(0, operation, "end"))
        if self.failure == "borrowed-trace" and self.writes == 3:
            rows[1]["request_id"] = "old-success"
        return dict(request_id=request, mode=mode, result=result, raised=raised, trace=rows)

    def save(self, path):
        self.saved[str(path)] = deepcopy(self.values)
        path.write_bytes(json.dumps(self.values).encode().ljust(512, b' '))
        self.state["modified"] = False
        if self.failure == "save" and self.writes == 3:
            return dict(ok=False, error={"message": "first save error"})
        return dict(ok=True, api_saved=True, save_errors=0, save_warnings=None, document=dict(modified=False))

    def close(self):
        if self.failure == "close" and self.writes == 3:
            raise RuntimeError("first close error")
        return dict(stale_id_refused=True, retired_id=self.state["document_id"], native_catalog_count=1)

    def reopen(self, path, readonly):
        self.reopens += 1
        self.values = deepcopy(self.saved[str(path)])
        self.state.update(read_only=readonly, modified=False)
        if self.failure != "reuse-id" or self.writes != 3:
            self.state["document_id"] = "d-fake%02d" % self.reopens
        if self.failure == "persistence" and self.writes == 3:
            field = next(iter(gate.DETAILING_LINE_FIELDS))
            self.values[field] = not self.values[field]
        if self.failure == "hash" and self.writes == 3:
            path.write_bytes(path.read_bytes() + b"changed")
        return dict(ok=True, api_errors=0, api_warnings=0, read_only=readonly)


class DetailingLineGateTests(unittest.TestCase):
    def run_fake(self, path, failure=None, initial=None):
        report = {"success": False, "native_accepted": False}
        backend = FakeBackend(failure, initial)
        engine = gate.Gate(backend, path, report)
        return engine, backend, report

    def test_all_eight_directed_edges_for_every_start_and_old_guard_pair(self):
        for mask in range(16):
            initial = {field: bool(mask & (1 << i)) for i, field in enumerate(gate.DETAILING_LINE_SNAPSHOT_FIELDS)}
            with self.subTest(mask=mask), tempfile.TemporaryDirectory() as folder:
                engine, backend, report = self.run_fake(folder, initial=initial)
                engine.run_plan()
                self.assertTrue(report["plan_complete"])
                self.assertFalse(report["native_accepted"])
                self.assertFalse(report["public_acceptance"])
                self.assertEqual(backend.writes, 8)
                self.assertEqual(backend.reopens, 16)
                self.assertEqual(backend.values, initial)
                fields = list(gate.DETAILING_LINE_FIELDS)
                edges = {(r["field"], r["value"], r["before"][fields[1-fields.index(r["field"])]]) for r in report["writes"]}
                self.assertEqual(len(edges), 8)
                for record in report["writes"]:
                    self.assertEqual(record["file"], record["file_after"])
                    for field in gate.DETAILING_FIELDS:
                        self.assertEqual(record["before"][field], record["after"][field])
                self.assertEqual(len(list(Path(folder).glob("*.SLDDRW"))), 8)

    def test_first_fault_stops_without_retry_and_preserves_original_result(self):
        for failure in ("partial", "old-guard", "foreground", "layout", "dirty", "borrowed-trace",
                        "save", "close", "reuse-id", "persistence", "hash"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                engine, backend, report = self.run_fake(folder, failure)
                with self.assertRaises(RuntimeError):
                    engine.run_plan()
                self.assertEqual(backend.writes, 3)
                self.assertEqual(len(report["writes"]), 3)
                self.assertNotIn("plan_complete", report)
                self.assertFalse(report["success"])
                persisted = json.loads((Path(folder)/"report.json").read_text())
                if failure == "partial":
                    result = persisted["writes"][-1]["write"]["result"]
                    self.assertTrue(result["mutation"]["may_have_changed"])
                    self.assertEqual(result["error"]["message"], "first setter business error")
                if failure == "close":
                    self.assertEqual(persisted["writes"][-1]["first_failure"]["message"], "first close error")

    def test_legacy_two_field_success_never_satisfies_new_gate(self):
        legacy = {field: True for field in gate.DETAILING_FIELDS}
        with self.assertRaisesRegex(RuntimeError, "four-field"):
            gate.transitions(legacy)
        with tempfile.TemporaryDirectory() as folder:
            engine, backend, report = self.run_fake(folder)
            original = backend.invoke
            def old_success(*args):
                envelope = original(*args)
                envelope["result"]["options"] = legacy
                return envelope
            backend.invoke = old_success
            with self.assertRaisesRegex(RuntimeError, "four-field"):
                engine.run_plan()
            self.assertEqual(backend.writes, 0)
            self.assertFalse(backend.enabled)

    def test_missing_trace_or_field_and_false_native_return_fail_closed(self):
        for mutation in ("trace", "field", "return", "count", "duration"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                engine, backend, report = self.run_fake(folder)
                original = backend.invoke
                def altered(operation, *args):
                    env = original(operation, *args)
                    if operation == gate.SET and env["result"] and env["result"].get("changed"):
                        if mutation == "trace": env["trace"] = []
                        if mutation == "field": env["result"]["options"].pop(next(iter(gate.DETAILING_FIELDS)))
                        if mutation == "return": env["result"]["native_return"] = False
                        if mutation == "count": env["trace"] = env["trace"][:1] + env["trace"][3:]
                        if mutation == "duration": env["trace"][2]["duration_ms"] = 600001
                    return env
                backend.invoke = altered
                with self.assertRaises(RuntimeError): engine.run_plan()
                self.assertEqual(backend.writes, 1)

    def test_watchdog_bounds_untraced_cleanup_and_nested_pending_boundaries(self):
        self.assertIn("untraced", watchdog.timeout_reason(0, 600, []))
        rows = [{"call": "write", "phase": "begin", "time": 5},
                {"call": "nested", "phase": "begin", "time": 100},
                {"call": "nested", "phase": "end", "time": 104}]
        self.assertIsNone(watchdog.timeout_reason(0, 604, rows))
        self.assertIn("600-second", watchdog.timeout_reason(0, 605, rows))
        self.assertIn("1800-second", watchdog.timeout_reason(0, 1800, []))

    def test_bounded_wrapper_times_out_only_its_child_and_never_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"bounded"
            process = mock.Mock(pid=1234, returncode=-9)
            process.poll.side_effect = [None, -9]
            with mock.patch.object(watchdog.sys, "platform", "win32"), \
                    mock.patch.object(watchdog.subprocess, "Popen", return_value=process) as spawn, \
                    mock.patch.object(watchdog.subprocess, "run") as kill, \
                    mock.patch.object(watchdog.time, "monotonic", side_effect=[0, 1800, 1801]):
                code = watchdog.main(["--output-dir", str(output), "--swconst", "unused", "--drawing-template", "unused",
                                      "--source-head", "a"*40, "--execute-owned-native"])
            self.assertEqual(code, 1)
            self.assertEqual(spawn.call_count, 1)
            self.assertEqual(kill.call_args.args[0], ["taskkill", "/PID", "1234", "/T", "/F"])
            receipt = json.loads((output/"watchdog.json").read_text())
            self.assertFalse(receipt["success"])
            self.assertFalse(receipt["native_accepted"])
            self.assertIn("1800", receipt["failure"])
            process.wait.assert_called_once_with(timeout=30)

    def test_probe_side_effects_and_previous_file_damage_are_rejected(self):
        for fault in ("noop-state", "cas-state", "repeat-request", "previous-file"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                engine, backend, report = self.run_fake(folder)
                original = backend.invoke
                first_request = []
                def altered(operation, field, value, expected, mode):
                    env = original(operation, field, value, expected, mode)
                    if not first_request:
                        first_request.append(env["request_id"])
                    elif fault == "repeat-request":
                        env["request_id"] = first_request[0]
                        for row in env["trace"]: row["request_id"] = first_request[0]
                    if operation == gate.SET and env["result"]:
                        if fault == "noop-state" and env["result"].get("changed") is False:
                            backend.state["modified"] = False
                        if fault == "cas-state" and env["result"].get("ok") is False:
                            backend.state["update_stamp"] += 1
                        if fault == "previous-file" and backend.writes == 2:
                            paths = list(Path(folder).glob("*.SLDDRW"))
                            paths[0].write_bytes(b"corrupt" * 100)
                    return env
                backend.invoke = altered
                with self.assertRaises(RuntimeError): engine.run_plan()
                self.assertLessEqual(backend.writes, 2)
                self.assertNotIn("plan_complete", report)

    def test_watchdog_ignores_only_incomplete_last_line(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"trace.jsonl"
            path.write_text('{"call":"x","time":1,"phase":"begin"}\n{"call":')
            self.assertEqual(len(watchdog.progress_records(path)), 1)
            path.write_text('broken\n{"call":"x"}')
            with self.assertRaises(json.JSONDecodeError): watchdog.progress_records(path)

    def test_main_without_native_permission_never_loads_com_or_spawns(self):
        with mock.patch.object(native, "NativeBackend") as backend, mock.patch.object(watchdog.subprocess, "Popen") as spawn:
            for module in (native, watchdog):
                argv = ["--output-dir", "/unused", "--swconst", "/unused", "--drawing-template", "/unused", "--source-head", "0"*40]
                if module is native: argv += ["--watchdog-pid", "0"]
                with redirect_stderr(StringIO()), self.assertRaises(SystemExit): module.main(argv)
            backend.assert_not_called()
            spawn.assert_not_called()


class NativeBackendPortableTests(unittest.TestCase):
    def setUp(self):
        from tests import test_document_detailing_lines as fixtures
        self.fx = fixtures.DetailingLineTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = native.NativeBackend(self.fx.fx.app, Path(self.temp.name), Path("unused"), Path("unused"), {})
        self.backend.registry, self.backend.entry = self.fx.fx.registry, self.fx.fx.entry
        self.backend.session, self.backend.lease = "writer", self.fx.fx.lease
        self.backend.document = self.fx.fx.document
        self.trace = mock.patch.dict("os.environ", {"SWCLI_TRACE_NATIVE_CALLS": "1"})
        self.trace.start()
        self.addCleanup(self.trace.stop)

    def test_real_handlers_adapter_schema_and_trace_are_used_without_com(self):
        field = next(iter(gate.DETAILING_LINE_FIELDS))
        before = self.fx.options()
        with self.fx.proof():
            desired = {**before, field: not before[field]}
            env = self.backend.invoke(gate.SET, field, desired[field], before, "normal")
            self.backend.validate(gate.SET, env["result"])
            gate.check_result(env, gate.SET, desired, changed=True, getters=12)
            for mode in ("stale-stamp", "invalid-lease"):
                env = self.backend.invoke(gate.SET, field, before[field], desired, mode)
                self.assertIsNone(env["result"], env)
                gate.check_result(env, gate.SET, desired, refused=True, getters=0)
            # A zero actual stamp must still generate a valid stale request,
            # rather than failing schema validation on a negative integer.
            self.fx.fx.document.GetUpdateStamp = lambda: 0
            env = self.backend.invoke(gate.SET, field, before[field], desired, "stale-stamp")
            self.assertEqual(env["request"]["expected_update_stamp"], 1)
            gate.check_result(env, gate.SET, desired, refused=True, getters=0)
            self.fx.fx.document.GetUpdateStamp = lambda: 7
            wrong = {**desired, next(iter(gate.DETAILING_FIELDS)): not desired[next(iter(gate.DETAILING_FIELDS))]}
            env = self.backend.invoke(gate.SET, field, before[field], wrong, "normal")
            self.backend.validate(gate.SET, env["result"])
            gate.check_result(env, gate.SET, wrong, refused=True, getters=4)
        self.assertEqual(self.fx.fx.extension.SetUserPreferenceToggle.call_count, 1)
        self.assertEqual(self.fx.fx.document.SetSaveFlag.call_count, 1)

    def test_partial_native_failure_is_retained_not_converted_to_preflight_refusal(self):
        field = next(iter(gate.DETAILING_LINE_FIELDS))
        self.fx.fx.extension.SetUserPreferenceToggle.side_effect = RuntimeError("first native failure")
        with self.fx.proof():
            env = self.backend.invoke(gate.SET, field, True, self.fx.options(), "normal")
        self.assertEqual(env["result"]["error"]["message"], "first native failure")
        self.assertTrue(env["result"]["mutation"]["may_have_changed"])
        with self.assertRaises(RuntimeError):
            gate.check_result(env, gate.SET, self.fx.options(), changed=True, getters=12)
        self.assertEqual(self.fx.fx.extension.SetUserPreferenceToggle.call_count, 1)


if __name__ == "__main__":
    unittest.main()
