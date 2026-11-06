"""Annotation CI must trace the owned preflight host and stop on the first gate failure."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/ci/windows/smoke-solidworks.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or shutil.which("pwsh")


class AnnotationCIWiringTests(unittest.TestCase):
    def test_full_ci_prepares_all_annotation_inputs_and_retains_public_evidence(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        preparation = workflow.split("      - name: Prepare annotation fixtures for public CLI verification", 1)[1].split("      - name:", 1)[0]
        run = workflow.split("      - name: Run real SOLIDWORKS modeling and export smoke test", 1)[1].split("      - name:", 1)[0]
        self.assertIn("timeout-minutes: 10", preparation)
        self.assertIn("id: annotation_fixtures", preparation)
        self.assertIn('--stage "annotation-fixtures=${{ steps.annotation_fixtures.outcome }}"', workflow)
        self.assertIn("scripts/ci/prepare-annotation-fixtures.py", preparation)
        self.assertIn("--drawing-template $drawingTemplate", preparation)
        self.assertIn("drawing_template.py --program-data", preparation)
        self.assertIn('-AnnotationFixtureDirectory "$env:SWCLI_SMOKE_ROOT\\annotation-fixtures"', run)
        self.assertLess(run.index("-VisibleSmoke"), run.index("-Hidden -Suite full"))
        self.assertIn('${{ runner.temp }}\\swcli-native-smoke', workflow)
        self.assertNotIn("calibrate_annotations:", workflow)
        wrapper = WRAPPER.read_text(encoding="utf-8")
        stages = [wrapper.index(name) for name in ('"../verify-properties.py"', '"../verify-document-units.py"',
                                                  '"../verify-document-annotations.py"', '"../verify-runtime-sets.py"')]
        self.assertEqual(stages, sorted(stages))
        self.assertIn('--native-trace $daemonStderr', wrapper)
        self.assertIn('if ($AnnotationFixtureDirectory -and -not $Hidden)', wrapper)

    def test_current_annotation_and_units_examples_use_the_new_client_and_keep_mcp(self):
        import shlex
        from swcli.cli import build_parser, _typed_operation
        parser = build_parser()
        self.assertEqual(parser.prog, "swcli")
        self.assertEqual(parser.parse_args(["mcp", "serve"]).command, "mcp")
        guide = (ROOT / "src/swcli/skills/swcli/references/usage.md").read_text(encoding="utf-8")
        commands = [line for line in guide.splitlines() if line.startswith(("swcli document units", "swcli document annotation-"))]
        self.assertEqual(len(commands), 6)
        self.assertNotIn("sw-cli", guide)
        operations = {_typed_operation(parser.parse_args(shlex.split(command)[1:]))[0] for command in commands}
        self.assertEqual(operations, {"document.units", "document.units-set", "document.annotation-options", "document.annotation-option-set"})


@unittest.skipUnless(POWERSHELL, "PowerShell fake wrappers; no native process is started")
class AnnotationWrapperExecutionTests(unittest.TestCase):
    def execute(self, code, setup):
        with tempfile.TemporaryDirectory(prefix="swcli-annotation-wrapper-") as temporary:
            directory = Path(temporary)
            result = directory / "result.json"
            script = directory / "fake-wrapper.ps1"

            def literal(path):
                return "'" + str(path).replace("'", "''") + "'"

            script.write_text(
                "$ErrorActionPreference='Stop'\n$failure=$null\n" + setup + "\ntry {\n" + code
                + "\n} catch { $failure=$_.Exception.Message }\n"
                + "[ordered]@{failure=$failure;calls=@($global:Calls);trace=$env:SWCLI_TRACE_NATIVE_CALLS} | "
                + "ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 -LiteralPath " + literal(result),
                encoding="utf-8",
            )
            process = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            return json.loads(result.read_text(encoding="utf-8-sig"))

    def test_trace_is_enabled_only_for_annotation_preflight_and_parent_restored_even_on_failure(self):
        wrapper = WRAPPER.read_text(encoding="utf-8")
        code = wrapper.split('$previousNativeTrace =', 1)[1].split('# Pin the OS handle', 1)[0]
        code = '$previousNativeTrace =' + code
        for enabled, fail in ((True, False), (False, False), (True, True)):
            with self.subTest(enabled=enabled, fail=fail):
                setup = """$env:SWCLI_TRACE_NATIVE_CALLS='parent-value'
$AnnotationFixtureDirectory=ANNOTATION_DIRECTORY
$global:Calls=@()
$python='unused-python'
$daemonArguments=@()
$daemonStdout='unused.stdout'
$daemonStderr='unused.stderr'
function Start-Process {
    param($FilePath,$ArgumentList,$RedirectStandardOutput,$RedirectStandardError,[switch]$NoNewWindow,[switch]$PassThru)
    $global:Calls += $env:SWCLI_TRACE_NATIVE_CALLS
    if (FAIL_START) { throw 'injected start failure' }
    return [pscustomobject]@{Id=7100}
}
""".replace("ANNOTATION_DIRECTORY", "'fixture'" if enabled else "$null").replace("FAIL_START", "$true" if fail else "$false")
                result = self.execute(code, setup)
                self.assertEqual(result["trace"], "parent-value")
                self.assertEqual(result["calls"], ["1" if enabled else None])
                self.assertEqual(result["failure"], "injected start failure" if fail else None)

    def test_document_gate_failures_stop_later_profiles_without_restart(self):
        wrapper = WRAPPER.read_text(encoding="utf-8")
        code = wrapper.split('    if ($PropertyFixtureDirectory) {', 1)[1].split('    # Shared scripts own CAD coverage', 1)[0]
        code = 'if ($PropertyFixtureDirectory) {' + code
        expected = ["verify-properties.py", "verify-document-units.py", "verify-document-annotations.py"] + ["verify-document-preferences.py"] * 3
        for failing_index in (*range(len(expected)), None):
            with self.subTest(failing_index=failing_index):
                setup = """$global:Calls=@()
$PropertyFixtureDirectory='fixture'
$AnnotationFixtureDirectory='annotation-fixture'
$Workspace=$PSScriptRoot
$daemonStderr=Join-Path $Workspace 'swclid.stderr.log'
$failedIndex=FAILED_INDEX
function python {
    $script=Split-Path -Leaf ([string]$args[1])
    $global:Calls += $script
    $global:LASTEXITCODE=0
    if ($null -ne $failedIndex -and $global:Calls.Count -eq ($failedIndex + 1)) { $global:LASTEXITCODE=23 }
}
""".replace("FAILED_INDEX", "$null" if failing_index is None else str(failing_index))
                result = self.execute(code, setup)
                self.assertEqual(result["calls"], expected if failing_index is None else expected[:failing_index + 1])
                self.assertEqual(result["failure"] is None, failing_index is None)


if __name__ == "__main__":
    unittest.main()
