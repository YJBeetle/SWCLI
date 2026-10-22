"""Execute the dependency helper with fakes; never install real packages."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/ci/windows/install-media-dependencies.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or shutil.which("pwsh")


@unittest.skipUnless(POWERSHELL, "PowerShell required; package installation is always mocked")
class MediaDependencyExecutionTests(unittest.TestCase):
    def run_helper(self, attempts):
        def literal(value):
            return "'" + str(value).replace("'", "''") + "'"

        with tempfile.TemporaryDirectory(prefix="swcli-media-dependencies-") as temporary:
            directory = Path(temporary)
            wrapper = directory / "mock-install.ps1"
            result_path = directory / "result.json"
            wrapper.write_text(
                """$ErrorActionPreference = 'Stop'
$global:Attempts = ConvertFrom-Json -InputObject ATTEMPTS
$global:Calls = @()
$global:Checks = @()
$global:Sleeps = @()
function global:choco {
    $index = $global:Calls.Count
    if ($index -ge $global:Attempts.Count) { throw 'Unexpected extra installation attempt' }
    $global:Calls += ,@($args)
    $global:LASTEXITCODE = $global:Attempts[$index].code
}
function global:Get-Command {
    [CmdletBinding()]
    param([string]$Name)
    if (@('rclone', 'imdisk.exe') -notcontains $Name) { throw 'Unexpected command probe' }
    $global:Checks += $Name
    $current = $global:Attempts[$global:Calls.Count - 1]
    if ($current.available -contains $Name) { return [pscustomobject]@{ Name = $Name } }
    return $null
}
function global:Start-Sleep {
    param([int]$Seconds)
    $global:Sleeps += $Seconds
}
$message = $null
try { & HELPER } catch { $message = $_.Exception.Message }
[ordered]@{ error = $message; calls = @($global:Calls); checks = @($global:Checks); sleeps = @($global:Sleeps) } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath RESULT -Encoding utf8
""".replace("ATTEMPTS", literal(json.dumps(attempts)))
                .replace("HELPER", literal(HELPER))
                .replace("RESULT", literal(result_path)),
                encoding="utf-8",
            )
            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result_path.read_text(encoding="utf-8-sig"))
            for call in data["calls"]:
                self.assertEqual(call, ["install", "rclone", "imdisk", "--yes", "--no-progress"])
            self.assertEqual(data["checks"], ["rclone", "imdisk.exe"] * len(data["calls"]))
            return data

    def test_success_installs_once_and_does_not_sleep(self):
        result = self.run_helper([{"code": 0, "available": ["rclone", "imdisk.exe"]}])
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["calls"]), 1)
        self.assertEqual(result["sleeps"], [])

    def test_false_success_is_retried_until_both_commands_exist(self):
        for available in ([], ["rclone"], ["imdisk.exe"]):
            with self.subTest(available=available):
                result = self.run_helper([
                    {"code": 0, "available": available},
                    {"code": 0, "available": ["rclone", "imdisk.exe"]},
                ])
                self.assertIsNone(result["error"])
                self.assertEqual(len(result["calls"]), 2)
                self.assertEqual(result["sleeps"], [10])

    def test_temporary_native_failure_then_success(self):
        result = self.run_helper([
            {"code": 1, "available": []},
            {"code": 0, "available": ["rclone", "imdisk.exe"]},
        ])
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["calls"]), 2)
        self.assertEqual(result["sleeps"], [10])

    def test_false_success_exhausts_exactly_three_attempts(self):
        result = self.run_helper([{"code": 0, "available": ["imdisk.exe"]}] * 3)
        self.assertIn("failed after 3 attempts", result["error"])
        self.assertIn("missing commands: rclone", result["error"])
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual(result["sleeps"], [10, 10])

    def test_nonzero_exit_cannot_be_hidden_by_existing_commands(self):
        result = self.run_helper([{"code": 42, "available": ["rclone", "imdisk.exe"]}] * 3)
        self.assertIn("Chocolatey exit code 42", result["error"])
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual(result["sleeps"], [10, 10])


if __name__ == "__main__":
    unittest.main()
