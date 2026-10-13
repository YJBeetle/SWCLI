import importlib.util
import io
import json
import shutil
import subprocess
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
        modeling = script.index('"../verify-runtime-sets.py"')
        equation = script.index('"verify-equation-dimension.py"')
        self.assertLess(modeling, equation)
        self.assertEqual(script.count('"../verify-runtime-sets.py"'), 1)
        for name in ("verify-modeling.py", "verify-driving-dimensions.py", "verify-toolbox.py"):
            self.assertNotIn(name, script)
        self.assertIn('throw "shared isolated functional sets failed"', script)
        self.assertIn('Assert-OwnedDaemonExit -Process $daemon -Name "preflight"', script[modeling:equation])
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

    def test_windows_wrapper_delegates_both_drawing_roundtrips_with_private_references(self):
        script = (SCRIPT.parent / "windows/smoke-solidworks.ps1").read_text(encoding="utf-8")
        prepare = script.index("$sampleDrawing =")
        modeling = script.index('& python -I (Join-Path $PSScriptRoot "../verify-runtime-sets.py")')
        block = script[prepare:script.index('# Shared sets stop')]
        self.assertIn('sldBenchmarking\\Macro\\Mold\\bezel moldbase.slddrw', block)
        self.assertIn('Test-Path -LiteralPath $sampleDrawing -PathType Leaf', block)
        self.assertIn('throw "Installed drawing fixture is missing: $sampleDrawing"', block)
        self.assertIn('[IO.Path]::GetTempPath()', block)
        self.assertIn('[guid]::NewGuid()', block)
        self.assertNotIn('Copy-Item', block)  # Per-set private copies belong to the shared coordinator.
        self.assertLess(prepare, modeling)
        self.assertIn('--sample-drawing $sampleDrawing --sample-drawing-local $sampleDrawing', block)
        self.assertIn('--fixture-work-dir $drawingWorkFolder --host-fixture-work-dir $drawingWorkFolder', block)
        self.assertIn('finally {', block)
        self.assertIn('Remove-Item -LiteralPath $drawingWorkFolder -Recurse -Force -ErrorAction Stop', block)
        self.assertIn('if (-not $setsFailed) { throw }', block)
        self.assertIn('preserving the original gate failure', block)
        self.assertNotIn('if ($Suite', block)
        self.assertNotIn('SaveAs3', block)
        self.assertNotIn('Save3', block)

    def test_windows_ci_core_is_visible_and_full_retains_hidden_mode(self):
        root = SCRIPT.parents[2]
        workflow = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        wrapper = (SCRIPT.parent / "windows/smoke-solidworks.ps1").read_text(encoding="utf-8")
        visible = 'scripts/ci/windows/smoke-solidworks.ps1 -Workspace $env:SWCLI_SMOKE_ROOT'
        hidden = 'scripts/ci/windows/smoke-solidworks.ps1 -Workspace "$env:SWCLI_SMOKE_ROOT\\hidden" -Hidden'
        self.assertLess(workflow.index(visible), workflow.index(hidden))
        self.assertIn("if ('${{ inputs.runtime_suite || 'core' }}' -eq 'full')", workflow)
        self.assertIn("-Suite '${{ inputs.runtime_suite || 'core' }}'", workflow)
        self.assertIn('-Hidden -Suite full', workflow)
        self.assertIn('--suite $Suite', wrapper)
        self.assertIn('[switch]$Hidden', wrapper)
        self.assertIn('if (-not $Hidden) { $daemonArguments += "--visible" }', wrapper)
        self.assertIn('-ArgumentList $daemonArguments', wrapper)
        self.assertIn(
            'if (-not $Hidden) {\n        & python -I (Join-Path $PSScriptRoot "verify-equation-dimension.py")',
            wrapper,
        )

    def test_windows_native_gate_consumes_the_same_run_package_not_editable_source(self):
        workflow = (SCRIPT.parents[2] / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        package, hosted = workflow.split("  solidworks-e2e:", 1)
        self.assertIn("needs: [test, package]", hosted)
        self.assertIn("name: swcli-dist", package)
        download = hosted.split("      - name: Download built SWCLI distributions", 1)[1].split("      - name:", 1)[0]
        self.assertIn("uses: actions/download-artifact@v8", download)
        self.assertIn("name: swcli-dist", download)
        self.assertIn("path: ${{ runner.temp }}/swcli-dist", download)
        self.assertIn("digest-mismatch: error", download)
        self.assertNotIn("run-id:", download)
        self.assertNotIn("repository:", download)
        install = hosted.split("      - name: Install built SWCLI wheel", 1)[1].split("      - name:", 1)[0]
        self.assertIn('$env:RUNNER_TEMP\\swcli-dist', install)
        self.assertIn("if ($wheels.Count -ne 1)", install)
        self.assertIn("python -m pip install $wheels[0].FullName", install)
        self.assertIn("SWCLI wheel installation failed", install)
        self.assertIn("python -I scripts/ci/verify-installed.py", install)
        self.assertNotIn("--editable", hosted)
        self.assertNotIn("pip install .", hosted)
        self.assertLess(hosted.index("Download built SWCLI distributions"), hosted.index("Install native SOLIDWORKS"))
        self.assertLess(hosted.index("Install built SWCLI wheel"), hosted.index("Run real SOLIDWORKS modeling and export smoke test"))

    def test_windows_extra_host_wait_is_bounded_by_elapsed_time_not_probe_count(self):
        wrapper = (SCRIPT.parent / "windows/smoke-solidworks.ps1").read_text(encoding="utf-8")
        block = wrapper.split('# Shared sets stop', 1)[1].split('# This Windows-only fixture', 1)[0]
        self.assertIn('$startupWait = [Diagnostics.Stopwatch]::StartNew()', block)
        self.assertIn('while ($startupWait.Elapsed.TotalSeconds -lt 180)', block)
        self.assertNotIn('$attempt -lt 180', block)
        self.assertIn('if ($daemon.HasExited)', block)
        self.assertIn('"TimeoutError", "ConnectionResetError"', block)
        self.assertIn('throw "Windows-only daemon startup deadline exceeded"', block)

    def test_windows_pins_handles_before_delayed_strict_exit_check(self):
        script = (SCRIPT.parent / "windows/smoke-solidworks.ps1").read_text(encoding="utf-8")
        self.assertEqual(script.count('$null = $daemon.Handle'), 2)
        self.assertLess(script.index('$null = $daemon.Handle'), script.index('"../verify-runtime-sets.py"'))
        check = script.split('function Assert-OwnedDaemonExit {', 1)[1].split('function Invoke-SwCliJson', 1)[0]
        self.assertIn('$Process.WaitForExit($TimeoutMilliseconds)', check)
        self.assertIn('$Process.WaitForExit()', check)
        self.assertIn('$null -eq $exitCode -or $exitCode -ne 0', check)
        self.assertIn('wait_completed = $finished', check)
        self.assertIn('"$Name-exit.json"', check)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell required for real process exit checks")
    def test_windows_delayed_exit_check_accepts_zero_rejects_nonzero_and_live(self):
        source = (SCRIPT.parent / "windows/smoke-solidworks.ps1").read_text(encoding="utf-8")
        function = 'function Assert-OwnedDaemonExit {' + source.split(
            'function Assert-OwnedDaemonExit {', 1)[1].split('function Invoke-SwCliJson', 1)[0]
        program = function + '''
$ErrorActionPreference = 'Stop'
$Workspace = $args[0]
foreach ($code in @(0, 7)) {
    $process = Start-Process -FilePath (Join-Path $PSHOME 'pwsh') -ArgumentList @('-NoProfile', '-Command', "exit $code") -PassThru
    $null = $process.Handle
    if (-not $process.WaitForExit(10000)) { throw 'fixture did not exit' }
    Start-Sleep -Milliseconds 100
    $rejected = $false
    try { Assert-OwnedDaemonExit -Process $process -Name "exit-$code" }
    catch { $rejected = $true }
    if ($rejected -ne ($code -ne 0)) { throw "wrong rejection: $code" }
    $proof = Get-Content (Join-Path $Workspace "exit-$code-exit.json") -Raw | ConvertFrom-Json
    if (-not $proof.wait_completed -or $proof.exit_code -ne $code) { throw 'wrong exit proof' }
    $process.Dispose()
}
$process = Start-Process -FilePath (Join-Path $PSHOME 'pwsh') -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 30') -PassThru
$null = $process.Handle
try {
    $rejected = $false
    try { Assert-OwnedDaemonExit -Process $process -Name 'live' -TimeoutMilliseconds 1 }
    catch { $rejected = $true }
    if (-not $rejected) { throw 'live process accepted' }
    $proof = Get-Content (Join-Path $Workspace 'live-exit.json') -Raw | ConvertFrom-Json
    if ($proof.wait_completed -or $null -ne $proof.exit_code) { throw 'wrong live proof' }
} finally { $process.Kill(); $process.WaitForExit(); $process.Dispose() }
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "exit-check.ps1"
            path.write_text(program, encoding="utf-8")
            completed = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-File", str(path), temporary],
                                       capture_output=True, text=True, timeout=40)
        self.assertEqual(completed.returncode, 0, completed.stderr)

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

    def empty_host_calls(self, *pids):
        health = iter(self.health(pid) for pid in pids)
        def call(operation, *args, **kwargs):
            if operation == "document.list":
                return {"success": True, "result": {
                    "action": operation, "ok": True, "count": 0,
                    "documents": [], "current_document_id": None,
                }}
            if operation == "daemon.health":
                return next(health)
            raise AssertionError("unexpected fixture operation: " + operation)
        return call

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
                mock.patch.object(gate, "call_daemon", side_effect=self.empty_host_calls(123, 123)) as rpc,
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
            self.assertEqual(sum(call.args[0] == "document.list" for call in rpc.call_args_list), 9)
            self.assertEqual(smoke.record["host_after"]["process_id"], 123)
            self.assertEqual(smoke.record["modeling_record"], str(path))
            with (
                mock.patch.object(gate, "call_daemon", return_value=self.health(999)),
                mock.patch.object(smoke, "plane") as plane,
            ):
                with self.assertRaisesRegex(RuntimeError, "replaced between"):
                    smoke.run()
            plane.assert_not_called()

    def test_suite_mismatch_is_rejected_before_contacting_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "modeling.json"
            path.write_text(json.dumps({**self.record(), "suite": "core"}))
            smoke = gate.DrivingSmoke(endpoint="127.0.0.1:1", session="full",
                                      output_directory="C:\\proof", after_modeling=path,
                                      local_output_directory=temporary, suite="full")
            with mock.patch.object(gate, "call_daemon") as rpc:
                with self.assertRaisesRegex(RuntimeError, "suite coverage must match"):
                    smoke.run()
            rpc.assert_not_called()

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
                gate, "call_daemon", side_effect=self.empty_host_calls(123, 999)
            ),
            mock.patch.object(smoke, "plane"),
            mock.patch.object(smoke, "center_constraints"),
            mock.patch.object(smoke, "rectangle_dimensions"),
            mock.patch.object(smoke, "prepare_origin_fixture"),
            mock.patch("sys.stdout", new=io.StringIO()),
        ):
            with self.assertRaisesRegex(RuntimeError, "during the driving gate"):
                smoke.run()
