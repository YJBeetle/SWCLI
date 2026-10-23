"""Shared plan and session boundaries; no native SW or Wine required."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ci/verify-runtime-sets.py"
spec = importlib.util.spec_from_file_location("runtime_sets_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class RuntimeSetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        inventory = patch.object(gate, "solidworks_process_ids", return_value=[])
        inventory.start()
        self.addCleanup(inventory.stop)
        root = Path(self.temp.name)
        source = root / "source"
        source.mkdir()
        drawing = source / "sample.slddrw"
        drawing.write_bytes(b"fixture")
        self.args = SimpleNamespace(suite="core", mode="visible", output_dir=root / "evidence",
            host_output_dir="C:\\Evidence", cli_command=None, endpoint="127.0.0.1:18495",
            sample_part="C:\\Installed\\part.sldprt", sample_assembly="C:\\Installed\\asm.sldasm",
            sample_drawing="C:\\Installed\\sample.slddrw", sample_drawing_local=drawing,
            fixture_work_dir=root / "private-work", host_fixture_work_dir="C:\\PrivateWork",
            request_timeout=600, startup_timeout=300, set_timeout=1800,
            daemon_log=None, wine_prefix=None)

    def host(self, pid):
        return {"host_connected": True, "recovery_required": False,
                "host": {"process_id": pid, "visible": self.args.mode == "visible",
                         "owned_by_daemon": True, "shared_interactive": False}}

    def test_plan_is_identical_for_platforms_and_core_is_not_silent_full(self):
        core, full = gate.runtime_plan("core"), gate.runtime_plan("full")
        self.assertEqual(len(core), 11)
        self.assertEqual(len(full), 18)
        for plan in (core, full):
            self.assertEqual(len(plan), len({item.name for item in plan}))
            self.assertEqual(plan[-1].name, "toolbox")
            for item in plan:
                for step in item.steps:
                    self.assertTrue((SCRIPT.parent / step.script).is_file())
        self.assertNotIn("feature-depth", [item.name for item in core])
        self.assertIn("feature-depth", [item.name for item in full])
        self.assertNotIn("fillets", [item.name for item in core])
        self.assertIn("fillets", [item.name for item in full])
        bridge = next(item for item in full if item.name == "continuation-front-diameter")
        self.assertEqual([step.script for step in bridge.steps],
                         ["verify-host-continuation.py", "verify-diameter-dimensions.py"])
        for plane in ("front", "top", "right"):
            names = [item.name for item in full]
            self.assertIn("center-" + plane, names)
            self.assertIn("rectangle-" + plane, names)

    def test_foreign_shared_wrong_mode_or_unready_host_rejected(self):
        runner = gate.Runner(self.args)
        for host_changes, root_changes in (({"owned_by_daemon": False}, {}),
                ({"shared_interactive": True}, {}), ({"visible": False}, {}),
                ({"process_id": "42"}, {}), ({}, {"recovery_required": True}),
                ({}, {"host_connected": False})):
            value = self.host(42)
            value["host"].update(host_changes)
            value.update(root_changes)
            with self.subTest(changes=host_changes), self.assertRaises(RuntimeError):
                runner.exclusive(value)

    def simulate(self, runner, failure_at=None, cleanup_failure=False):
        events = []
        active = [None]
        def health(label):
            if label == "preflight-status":
                raise gate.DaemonUnavailable("refused")
            return self.host(active[0])
        def start(item):
            active[0] = 100 + len(events)
            item["host"] = self.host(active[0])["host"]
            events.append(("start", item["name"], active[0]))
        def stop(item):
            events.append(("stop", item["name"], active[0]))
            active[0] = None
            if cleanup_failure:
                raise RuntimeError("cleanup failure")
        def command(arguments, **kwargs):
            script = Path(arguments[2]).name
            events.append(("step", script, active[0]))
            if script == failure_at:
                raise RuntimeError("original native failure")
            output = Path(arguments[arguments.index("--output-dir") + 1])
            filename = "toolbox.json" if script == "verify-toolbox.py" else (
                "driving-dimensions.json" if "--sample-part" not in arguments else "modeling.json")
            proof = {"success": True, "state": "completed", "completed": True,
                     "native_test": "passed", "cleanup_errors": [], "suite": self.args.suite,
                     "host": self.host(active[0])["host"], "host_after": self.host(active[0])["host"],
                     "cases": ["stub"], "case_cleanup": [{"empty": True}]}
            if "--plane" in arguments:
                proof["selection"] = {"plane": arguments[arguments.index("--plane") + 1]}
            (output / filename).write_text(json.dumps(proof))
        patches = (patch.object(runner, "health", side_effect=health),
                   patch.object(runner, "start", side_effect=start),
                   patch.object(runner, "stop", side_effect=stop),
                   patch.object(runner, "command", side_effect=command), patch.object(runner, "empty"))
        return events, patches

    def test_fresh_session_per_set_but_no_restart_inside_continuation(self):
        runner = gate.Runner(self.args)
        events, patches = self.simulate(runner)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            runner.run()
        starts = [event for event in events if event[0] == "start"]
        stops = [event for event in events if event[0] == "stop"]
        self.assertEqual(len(starts), len(runner.plan))
        self.assertEqual(len(stops), len(starts))
        begin = next(i for i, e in enumerate(events) if e[:2] == ("start", "continuation-front-diameter"))
        self.assertEqual([e[0] for e in events[begin:begin+4]], ["start", "step", "step", "stop"])
        self.assertEqual(len({e[2] for e in events[begin:begin+4]}), 1)
        self.assertTrue(runner.record["completed"])
        self.assertTrue(runner.record["success"])
        self.assertEqual(runner.record["expected_sets"], [item["name"] for item in runner.record["sets"]])
        self.assertEqual(self.args.sample_drawing_local.read_bytes(), b"fixture")
        self.assertEqual(list(self.args.fixture_work_dir.iterdir()), [])

    def test_failure_is_not_retried_or_hidden_by_shutdown_failure(self):
        runner = gate.Runner(self.args)
        events, patches = self.simulate(runner, failure_at="verify-native-model.py", cleanup_failure=True)
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
                self.assertRaisesRegex(RuntimeError, "original native failure"):
            runner.run()
        self.assertEqual([event[0] for event in events], ["start", "step", "stop"])
        self.assertFalse(runner.record["success"])
        self.assertEqual(len(runner.record["sets"]), 1)
        self.assertFalse(runner.record["sets"][0]["success"])

    def test_shared_modeling_record_is_passed_only_within_bridge(self):
        runner = gate.Runner(self.args)
        bridge = next(item for item in runner.plan if item.name == "continuation-front-diameter")
        args, output = runner.step_args(bridge, bridge.steps[1], Path("private"), "C:\\Private")
        self.assertEqual(args[-1], output.parent / "modeling/modeling.json")
        self.assertEqual(args[args.index("--plane") + 1], "front")
        geometry = next(item for item in runner.plan if item.name == "geometry-top")
        args, _ = runner.step_args(geometry, geometry.steps[0], Path("private"), "C:\\Private")
        self.assertNotIn("--after-modeling", args)

    def test_preflight_errors_do_not_authorize_shutdown(self):
        runner = gate.Runner(self.args)
        with patch.object(runner, "health", side_effect=RuntimeError("untrusted health")), \
                patch.object(runner, "public") as public, self.assertRaisesRegex(RuntimeError, "untrusted health"):
            runner.run()
        public.assert_not_called()

    def test_entrypoints_are_importable_with_isolated_python(self):
        import subprocess, sys
        for name in sorted({step.script for item in gate.runtime_plan("full") for step in item.steps}):
            completed = subprocess.run([sys.executable, "-I", SCRIPT.parent / name, "--help"],
                                       capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_source_only_adapter_uses_explicit_paths_not_ambient_pythonpath(self):
        self.args.cli_command = "/adapter/sw-cli"
        self.args.python_path = [ROOT / "src"]
        runner = gate.Runner(self.args)
        step = runner.plan[0].steps[0]
        arguments, _ = runner.step_args(runner.plan[0], step, Path("private"), "C:\\Private")
        self.assertEqual(arguments[:3], [sys.executable, "-I", SCRIPT.parent / "gate_support/python_entrypoint.py"])
        self.assertEqual(arguments[3:5], ["--python-path", (ROOT / "src").resolve()])
        self.assertEqual(runner.record["python_import_paths"], [str((ROOT / "src").resolve())])
        # No installed package/site: emulate the Linux source-only interpreter.
        # Poisoned cwd/PYTHONPATH must not override explicitly supplied SWCLI.
        poison = Path(self.temp.name) / "swcli.py"
        poison.write_text("raise RuntimeError('ambient path must not be imported')\n")
        for name in sorted({step.script for item in gate.runtime_plan("full") for step in item.steps}):
            base = [sys.executable, "-I", "-S", SCRIPT.parent / "gate_support/python_entrypoint.py"]
            completed = subprocess.run([*base, "--python-path", ROOT / "src", SCRIPT.parent / name, "--help"],
                cwd=self.temp.name, env={**os.environ, "PYTHONPATH": self.temp.name},
                capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        # This is the original failure without the explicit source bootstrap.
        missing = subprocess.run([sys.executable, "-I", "-S", SCRIPT.parent / step.script, "--help"],
                                 capture_output=True, text=True, timeout=10)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("No module named 'swcli'", missing.stderr)

    def test_explicit_paths_require_adapter_and_existing_absolute_directories(self):
        for paths, cli in (([ROOT / "src"], None), ([Path("relative")], "/adapter/sw-cli"),
                           ([Path(self.temp.name) / "missing"], "/adapter/sw-cli")):
            self.args.python_path, self.args.cli_command = paths, cli
            with self.subTest(paths=paths, cli=cli), self.assertRaises(RuntimeError):
                gate.Runner(self.args)

    def test_start_waits_for_initializing_daemon_and_allows_recycled_pid_after_exit(self):
        runner = gate.Runner(self.args)
        item = {"name": "native-model"}
        runner.record["sets"] = [item]
        launcher = SimpleNamespace(pid=222, poll=lambda: None)
        with patch.object(gate.subprocess, "Popen", return_value=launcher), \
                patch.object(runner, "health", side_effect=[gate.DaemonTransportPending("TimeoutError"),
                    gate.DaemonTransportPending("ConnectionResetError"), gate.DaemonStarting("initializing"),
                    self.host(42)]), \
                patch.object(runner, "empty") as empty, patch.object(gate.time, "sleep"):
            runner.start(item)
        empty.assert_called_once_with("native-model-before")
        self.assertEqual(item["server_process_id"], 222)
        runner.server_log.close()
        runner.server = None
        next_item = {"name": "assemblies"}
        runner.record["sets"].append(next_item)
        with patch.object(gate.subprocess, "Popen", return_value=launcher), \
                patch.object(runner, "health", return_value=self.host(42)), \
                patch.object(runner, "empty") as empty:
            runner.start(next_item)
        empty.assert_called_once_with("assemblies-before")
        self.assertEqual(next_item["host"]["process_id"], item["host"]["process_id"])
        self.assertNotEqual(next_item["instance_id"], item["instance_id"])
        self.assertTrue(item["before_start"]["verified"])
        self.assertTrue(next_item["before_start"]["verified"])
        runner.server_log.close()

    def test_remaining_sw_blocks_start_without_spawning_or_killing(self):
        runner = gate.Runner(self.args)
        clock = [0]
        item = {"name": "native-model"}
        with patch.object(gate, "solidworks_process_ids", return_value=[777]), \
                patch.object(gate.subprocess, "Popen") as spawn, \
                patch.object(gate.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(gate.time, "sleep", side_effect=lambda _: clock.__setitem__(0, 31)), \
                self.assertRaisesRegex(RuntimeError, "remained at test-set boundary"):
            runner.start(item)
        spawn.assert_not_called()
        self.assertEqual(item["before_start"]["native_process_ids"], [777])
        self.assertFalse(item["before_start"]["verified"])

    def test_stop_waits_for_real_host_exit_after_normal_launcher_exit(self):
        from unittest.mock import Mock
        runner = gate.Runner(self.args)
        runner.server = Mock(returncode=0)
        runner.server.poll.return_value = None
        launcher = runner.server
        runner.server_log = Mock()
        item = {"name": "native-model", "host": self.host(42)["host"]}
        with patch.object(runner, "public") as stop, \
                patch.object(gate, "solidworks_process_ids", side_effect=[[777], []]) as inventory, \
                patch.object(gate.time, "sleep"):
            runner.stop(item)
        self.assertEqual(inventory.call_count, 2)
        self.assertTrue(item["after_stop"]["verified"])
        self.assertEqual(item["server_exit_code"], 0)
        launcher.terminate.assert_not_called()
        launcher.kill.assert_not_called()
        stop.assert_called_once()

    def test_inventory_failure_is_not_treated_as_no_host(self):
        runner = gate.Runner(self.args)
        with patch.object(gate, "solidworks_process_ids", side_effect=RuntimeError("inventory unavailable")), \
                patch.object(gate.subprocess, "Popen") as spawn, \
                self.assertRaisesRegex(RuntimeError, "inventory unavailable"):
            runner.start({"name": "native-model"})
        spawn.assert_not_called()

    def test_stop_with_surviving_sw_fails_without_force_killing_it(self):
        from unittest.mock import Mock
        runner = gate.Runner(self.args)
        launcher = Mock(returncode=0)
        launcher.poll.side_effect = [None, 0]
        runner.server, runner.server_log = launcher, Mock()
        item = {"name": "native-model", "host": self.host(42)["host"]}
        clock = [0]
        with patch.object(runner, "public"), \
                patch.object(gate, "solidworks_process_ids", return_value=[777]), \
                patch.object(gate.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(gate.time, "sleep", side_effect=lambda _: clock.__setitem__(0, 31)), \
                self.assertRaisesRegex(RuntimeError, "remained at test-set boundary"):
            runner.stop(item)
        self.assertFalse(item["after_stop"]["verified"])
        self.assertEqual(item["server_exit_code"], 0)
        launcher.terminate.assert_not_called()
        launcher.kill.assert_not_called()
        self.assertIsNone(runner.server)

    def test_actual_cli_error_envelopes_classify_only_status_transitions(self):
        runner = gate.Runner(self.args)
        # Real subprocess/stdout parsing, not mocked health exceptions. These
        # match the MacSW/DockerSW failed CI status envelopes.
        for code, phase, exception in (("TimeoutError", None, gate.DaemonTransportPending),
                                ("TimeoutError", "connect", gate.DaemonConnectTimeout),
                                ("ConnectionResetError", None, gate.DaemonTransportPending),
                                ("ConnectionRefusedError", None, gate.DaemonUnavailable),
                                ("Starting", None, gate.DaemonStarting), ("WorkerTimeout", None, RuntimeError)):
            error = {"code": code, "message": "fixture"}
            if phase:
                error["transport_phase"] = phase
            payload = json.dumps({"success": False, "error": error})
            child = "import sys; print(" + repr(payload) + "); sys.exit(1)"
            with self.subTest(code=code), self.assertRaises(exception) as caught:
                runner.command([sys.executable, "-c", child, "daemon", "status", "--json"],
                               timeout=5, label="status-" + code + (phase or ""), json_result=True)
            self.assertIs(type(caught.exception), exception)
            self.assertEqual(runner.record["commands"][-1]["exit_code"], 1)
        payload = json.dumps({"success": False, "error": {"code": "TimeoutError", "message": "fixture"}})
        child = "import sys; print(" + repr(payload) + "); sys.exit(1)"
        with self.assertRaisesRegex(RuntimeError, "Functional command failed") as caught:
            runner.command([sys.executable, "-c", child, "document", "list", "--json"],
                           timeout=5, label="document-timeout", json_result=True)
        self.assertIs(type(caught.exception), RuntimeError)  # No CAD retry classification.

    def test_shutdown_reset_and_timeout_do_not_count_as_stopped(self):
        runner = gate.Runner(self.args)
        runner.plan = runner.plan[:1]
        runner.record["expected_sets"] = [runner.plan[0].name]
        events, patches = self.simulate(runner)
        statuses = [self.host(41), gate.DaemonTransportPending("reset"),
                    gate.DaemonTransportPending("timeout"), gate.DaemonUnavailable("refused"), self.host(100)]
        def health(label, **kwargs):
            result = statuses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        with patch.object(runner, "health", side_effect=health) as probes, patches[1], patches[2], \
                patches[3], patches[4], patch.object(runner, "public", return_value={"stopping": True}) as stop, \
                patch.object(gate.time, "sleep"):
            runner.run()
        stop.assert_called_once_with("daemon", "stop", label="preflight-stop")
        self.assertEqual([call.args[0] for call in probes.call_args_list[:4]],
                         ["preflight-status", "preflight-shutdown-1", "preflight-shutdown-2", "preflight-shutdown-3"])
        self.assertTrue(runner.record["success"])
        self.assertEqual([event[0] for event in events], ["start", "step", "stop"])

    def test_ambiguous_initial_probe_never_authorizes_stop_or_start(self):
        runner = gate.Runner(self.args)
        with patch.object(runner, "health", side_effect=gate.DaemonTransportPending("timeout")), \
                patch.object(runner, "public") as public, patch.object(runner, "start") as start, \
                self.assertRaises(gate.DaemonTransportPending):
            runner.run()
        public.assert_not_called()
        start.assert_not_called()

    def test_persistent_shutdown_transport_errors_exhaust_original_deadline(self):
        runner = gate.Runner(self.args)
        clock = [0]
        with patch.object(runner, "health", side_effect=[self.host(41), gate.DaemonTransportPending("reset")]) as probes, \
                patch.object(runner, "public", return_value={"stopping": True}) as public, patch.object(runner, "empty"), \
                patch.object(runner, "start") as start, patch.object(gate.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(gate.time, "sleep", side_effect=lambda _: clock.__setitem__(0, 31)), \
                self.assertRaisesRegex(RuntimeError, "endpoint did not stop"):
            runner.run()
        public.assert_called_once_with("daemon", "stop", label="preflight-stop")
        start.assert_not_called()
        self.assertEqual(probes.call_args_list[-1].kwargs["timeout"], 30)

    def test_windows_connect_timeout_after_acknowledged_stop_allows_fresh_start(self):
        runner = gate.Runner(self.args)
        runner.plan = runner.plan[:1]
        runner.record["expected_sets"] = [runner.plan[0].name]
        events, patches = self.simulate(runner)
        with patch.object(runner, "health", side_effect=[self.host(41), gate.DaemonConnectTimeout("closed"), self.host(100)]), \
                patches[1], patches[2], patches[3], patches[4], \
                patch.object(runner, "public", return_value={"stopping": True}):
            runner.run()
        self.assertTrue(runner.record["success"])
        self.assertEqual([event[0] for event in events], ["start", "step", "stop"])

    def test_unacknowledged_stop_and_initial_connect_timeout_cannot_start_a_host(self):
        runner = gate.Runner(self.args)
        with patch.object(runner, "health", side_effect=gate.DaemonConnectTimeout("initial unknown")), \
                patch.object(runner, "public") as public, patch.object(runner, "start") as start, \
                self.assertRaises(gate.DaemonConnectTimeout):
            runner.run()
        public.assert_not_called()
        start.assert_not_called()
        with patch.object(runner, "health", return_value=self.host(41)), \
                patch.object(runner, "empty"), patch.object(runner, "public", return_value={"already_stopped": True}), \
                patch.object(runner, "start") as start, self.assertRaisesRegex(RuntimeError, "not acknowledged"):
            runner.run()
        start.assert_not_called()

    def test_startup_transport_wait_has_finite_deadline_and_one_launcher(self):
        runner = gate.Runner(self.args)
        clock = [0]
        launcher = SimpleNamespace(pid=222, poll=lambda: None)
        with patch.object(gate.subprocess, "Popen", return_value=launcher) as spawn, \
                patch.object(runner, "health", side_effect=gate.DaemonTransportPending("timeout")), \
                patch.object(runner, "empty") as empty, \
                patch.object(gate.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(gate.time, "sleep", side_effect=lambda _: clock.__setitem__(0, 331)), \
                self.assertRaisesRegex(RuntimeError, "startup exceeded"):
            runner.start({"name": "native-model"})
        spawn.assert_called_once()
        empty.assert_not_called()
        runner.server_log.close()

    def test_startup_never_accepts_health_after_its_launcher_exits(self):
        runner = gate.Runner(self.args)
        polls = iter((None, 1))
        launcher = SimpleNamespace(pid=222, poll=lambda: next(polls))
        with patch.object(gate.subprocess, "Popen", return_value=launcher), \
                patch.object(runner, "health", return_value=self.host(42)), \
                patch.object(runner, "empty") as empty, self.assertRaisesRegex(RuntimeError, "exited during startup"):
            runner.start({"name": "native-model"})
        empty.assert_not_called()
        runner.server_log.close()

    def test_document_leftovers_block_transition_without_closing_unknown_documents(self):
        runner = gate.Runner(self.args)
        with patch.object(runner, "public", return_value={"count": 1, "documents": [{"id": "human"}]}) as public, \
                self.assertRaisesRegex(RuntimeError, "Unknown open documents"):
            runner.empty("before")
        public.assert_called_once_with("document", "list", label="before")

    def test_full_hidden_plan_also_uses_fresh_sessions_and_private_copies(self):
        self.args.suite, self.args.mode = "full", "hidden"
        runner = gate.Runner(self.args)
        events, patches = self.simulate(runner)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            runner.run()
        starts = [event for event in events if event[0] == "start"]
        self.assertEqual(len(starts), 18)
        self.assertEqual(len({event[2] for event in starts}), 18)
        self.assertTrue(runner.record["success"])

    def test_preflight_does_not_stop_shared_or_nonempty_host(self):
        for shared in (True, False):
            with self.subTest(shared=shared):
                self.args.output_dir = self.args.output_dir.parent / ("preflight-" + str(shared))
                runner = gate.Runner(self.args)
                health = self.host(42)
                health["host"]["shared_interactive"] = shared
                with patch.object(runner, "health", return_value=health), \
                        patch.object(runner, "empty", side_effect=RuntimeError("unknown documents")), \
                        patch.object(runner, "public") as public, self.assertRaises(RuntimeError):
                    runner.run()
                public.assert_not_called()


if __name__ == "__main__":
    unittest.main()
