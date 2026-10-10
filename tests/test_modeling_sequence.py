import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-driving-dimensions.py"
spec = importlib.util.spec_from_file_location("sequence_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ModelingSequenceTests(unittest.TestCase):
    def test_windows_wrapper_runs_shared_gates_in_order_without_duplicate_modeling(
        self,
    ):
        script = (SCRIPT.parent / "windows/smoke-solidworks.ps1").read_text(
            encoding="utf-8"
        )
        modeling = script.index('"../verify-modeling.py"')
        driving = script.index('"../verify-driving-dimensions.py"')
        toolbox = script.index('"../verify-toolbox.py"')
        equation = script.index('"verify-equation-dimension.py"')
        self.assertLess(modeling, driving)
        self.assertLess(driving, toolbox)
        self.assertLess(toolbox, equation)
        self.assertIn('--output-dir (Join-Path $Workspace "toolbox") --require-toolbox', script)
        self.assertIn('throw "Toolbox deployment/read-only CLI gate failed"', script)
        self.assertNotIn("--inventory-only", script[toolbox:equation])
        self.assertIn(
            '--after-modeling (Join-Path $modelingFolder "modeling.json")', script
        )
        self.assertIn(
            "--sample-part $samplePart --sample-assembly $sampleAssembly", script
        )
        between = script[modeling:equation]
        self.assertNotIn('"restart"', between)
        self.assertNotIn('"serve"', between)
        for old in (
            "$emptyA",
            "Get-SharedFileHash",
            "failed-cut-no-intersection",
            "rectangle-lease-renew",
        ):
            self.assertNotIn(old, script)
        self.assertIn('"attach-without-host"', script)
        self.assertIn('"daemon-disconnected"', script)

    def test_windows_ci_runs_the_same_smoke_in_visible_and_hidden_modes(self):
        root = SCRIPT.parents[2]
        workflow = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        wrapper = (SCRIPT.parent / "windows/smoke-solidworks.ps1").read_text(encoding="utf-8")
        visible = 'scripts/ci/windows/smoke-solidworks.ps1 -Workspace $env:SWCLI_SMOKE_ROOT'
        hidden = 'scripts/ci/windows/smoke-solidworks.ps1 -Workspace "$env:SWCLI_SMOKE_ROOT\\hidden" -Hidden'
        self.assertLess(workflow.index(visible), workflow.index(hidden))
        self.assertIn('[switch]$Hidden', wrapper)
        self.assertIn('if (-not $Hidden) { $daemonArguments += "--visible" }', wrapper)
        self.assertIn('-ArgumentList $daemonArguments', wrapper)
        self.assertIn(
            'if (-not $Hidden) {\n        & python -I (Join-Path $PSScriptRoot "verify-equation-dimension.py")',
            wrapper,
        )

    def record(self):
        return {
            "state": "completed",
            "success": True,
            "cleanup_errors": [],
            "cases": ["native-model", "rejected-cut-then-sketch"],
            "host": {"process_id": 123},
            "host_after": {"process_id": 123},
        }

    def health(self, pid=123):
        return {
            "success": True,
            "result": {
                "host_connected": True,
                "host": {"process_id": pid},
                "operations": [
                    "sketch.fix-center",
                    "sketch.dimension-diameter",
                    "sketch.dimension-rectangle",
                    "dimension.discover-diameter",
                    "dimension.discover-rectangle",
                    "dimension.inspect",
                    "dimension.set",
                    "sketch.list",
                ],
            },
        }

    def test_verified_predecessor_requires_same_host_before_any_plane(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "modeling.json"
            path.write_text(json.dumps(self.record()), encoding="utf-8")
            smoke = gate.DrivingSmoke(
                endpoint="127.0.0.1:18495",
                session="gate",
                output_directory="C:\\proof",
                after_modeling=path,
                local_output_directory=temporary,
            )
            with (
                mock.patch.object(gate, "call_daemon", return_value=self.health()),
                mock.patch.object(smoke, "plane") as plane,
                mock.patch.object(smoke, "center_constraints") as centers,
                mock.patch.object(smoke, "rectangle_dimensions") as sizes,
                mock.patch("sys.stdout", new=io.StringIO()),
            ):
                smoke.run()
            self.assertEqual(plane.call_count, 3)
            self.assertEqual(
                centers.call_args_list,
                [mock.call(plane) for plane in ("front", "top", "right")],
            )
            self.assertEqual(sizes.call_args_list, centers.call_args_list)
            self.assertEqual(smoke.record["host_after"]["process_id"], 123)
            self.assertEqual(smoke.record["modeling_record"], str(path))
            with (
                mock.patch.object(gate, "call_daemon", return_value=self.health(999)),
                mock.patch.object(smoke, "plane") as plane,
            ):
                with self.assertRaisesRegex(RuntimeError, "replaced between"):
                    smoke.run()
            plane.assert_not_called()

    def test_failed_interrupted_or_inconsistent_predecessor_refused(self):
        for changed in (
            {"success": False},
            {"state": "running"},
            {"cleanup_errors": [{}]},
            {"cases": []},
            {"host_after": {"process_id": 124}},
            {"host": {"process_id": True}},
        ):
            with (
                self.subTest(changed=changed),
                tempfile.TemporaryDirectory() as temporary,
            ):
                path = Path(temporary) / "modeling.json"
                path.write_text(
                    json.dumps({**self.record(), **changed}), encoding="utf-8"
                )
                with self.assertRaises(RuntimeError):
                    gate.modeling_host(path)

    def test_host_replacement_during_driving_is_also_a_failure(self):
        smoke = gate.DrivingSmoke(
            endpoint="127.0.0.1:18495", session="gate", output_directory="C:\\proof"
        )
        with (
            mock.patch.object(
                gate, "call_daemon", side_effect=[self.health(), self.health(999)]
            ),
            mock.patch.object(smoke, "plane"),
            mock.patch.object(smoke, "center_constraints"),
            mock.patch.object(smoke, "rectangle_dimensions"),
            mock.patch.object(smoke, "prepare_origin_fixture"),
            mock.patch("sys.stdout", new=io.StringIO()),
        ):
            with self.assertRaisesRegex(RuntimeError, "during the driving gate"):
                smoke.run()
