"""Shared plan and session boundaries; no native SW or Wine required."""
import importlib.util
import json
from pathlib import Path
import tempfile
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
        self.assertEqual(len(full), 17)
        for plan in (core, full):
            self.assertEqual(len(plan), len({item.name for item in plan}))
            self.assertEqual(plan[-1].name, "toolbox")
            for item in plan:
                for step in item.steps:
                    self.assertTrue((SCRIPT.parent / step.script).is_file())
        self.assertNotIn("feature-depth", [item.name for item in core])
        self.assertIn("feature-depth", [item.name for item in full])
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

    def test_start_waits_for_initializing_daemon_but_rejects_reused_pid(self):
        runner = gate.Runner(self.args)
        item = {"name": "native-model"}
        runner.record["sets"] = [item]
        launcher = SimpleNamespace(pid=222, poll=lambda: None)
        with patch.object(gate.subprocess, "Popen", return_value=launcher), \
                patch.object(runner, "health", side_effect=[gate.DaemonStarting("initializing"), self.host(42)]), \
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
                patch.object(runner, "empty") as empty, self.assertRaisesRegex(RuntimeError, "reused"):
            runner.start(next_item)
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
        self.assertEqual(len(starts), 17)
        self.assertEqual(len({event[2] for event in starts}), 17)
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
