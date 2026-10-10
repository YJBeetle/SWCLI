"""Pinned media dependency contracts; Windows execution uses only fakes."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "ci" / "windows" / "install-winfsp.ps1"
HASH = "073a70e00f77423e34bed98b86e600def93393ba5822204fac57a29324db9f7a"
URL = "https://github.com/winfsp/winfsp/releases/download/v2.1/winfsp-2.1.25156.msi"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")


class WinFspDependencyContractsTests(unittest.TestCase):
    def test_upstream_pin_and_download_checks_precede_installation(self):
        source = HELPER.read_text(encoding="utf-8")
        self.assertIn(URL, source)
        self.assertIn(HASH, source)
        self.assertLess(source.index("if ($LASTEXITCODE -ne 0)"), source.index("Get-FileHash"))
        self.assertLess(source.index("Get-FileHash"), source.index("Start-Process"))
        self.assertIn("-Algorithm SHA256", source)
        for option in ("--fail", "--location", "--retry-max-time 120", "--max-time 60"):
            self.assertIn(option, source)
        self.assertNotIn("--insecure", source)

    def test_native_install_is_bounded_and_never_retried(self):
        source = HELPER.read_text(encoding="utf-8")
        self.assertEqual(source.count("Start-Process"), 1)
        self.assertIn("[ValidateRange(1, 600)]", source)
        self.assertIn("$process.WaitForExit($TimeoutSeconds * 1000)", source)
        self.assertIn("taskkill.exe /PID $process.Id /T /F", source)
        self.assertIn("@(0, 3010) -notcontains $process.ExitCode", source)
        self.assertIn("Get-Service -Name WinFsp.Launcher", source)

    def test_workflow_checks_packages_and_retains_the_installer_log(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        step = workflow.split("      - name: Install rclone, WinFsp, and ImDisk", 1)[1].split("\n      - ", 1)[0]
        self.assertIn("choco install rclone imdisk --yes --no-progress", step)
        self.assertNotIn("choco install rclone winfsp", step)
        self.assertIn("if ($LASTEXITCODE -ne 0)", step)
        self.assertIn('@("rclone", "imdisk.exe")', step)
        self.assertIn("Get-Command $command", step)
        self.assertIn("scripts/ci/windows/install-winfsp.ps1", step)
        self.assertIn("swcli-hosted-media\\winfsp\\winfsp-install.log", workflow)
        self.assertIn("mount-google-drive.ps1", workflow)


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell fakes; never installs MSI")
class WinFspDependencyExecutionTests(unittest.TestCase):
    def run_helper(self, download_code=0, hash_matches=True, install_code=0, timeout=False, service=True):
        with tempfile.TemporaryDirectory(prefix="swcli-winfsp-contract-") as temporary:
            directory = Path(temporary)
            result_path = directory / "result.json"
            wrapper = directory / "fake-install.ps1"

            def literal(value):
                return "'" + str(value).replace("'", "''") + "'"

            wrapper.write_text(
                """$ErrorActionPreference = 'Stop'
$global:Download = @()
$global:Calls = @()
$global:Killed = @()
$global:Waits = @()
$global:HashReads = 0
$global:ServiceReads = 0
function global:curl.exe {
    $global:Download = @($args)
    $global:LASTEXITCODE = DOWNLOAD_CODE
}
function global:Get-FileHash {
    param([string]$LiteralPath, [string]$Algorithm)
    if ($Algorithm -ne 'SHA256') { throw 'Unexpected hash algorithm' }
    $global:HashReads++
    return [pscustomobject]@{ Hash = HASH_VALUE }
}
function global:Start-Process {
    param([string]$FilePath, [string[]]$ArgumentList, [switch]$PassThru)
    if ($FilePath -ne 'msiexec.exe') { throw 'Blocked unexpected executable' }
    $global:Calls += [ordered]@{ file = $FilePath; arguments = @($ArgumentList) }
    $process = [pscustomobject]@{ Id = 7400; ExitCode = INSTALL_CODE }
    $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
        param($milliseconds)
        $global:Waits += $milliseconds
        return WAIT_RESULT
    }
    return $process
}
function global:taskkill.exe {
    $global:Killed += ,@($args)
    $global:LASTEXITCODE = 0
}
function global:Get-Service {
    [CmdletBinding()]
    param([string]$Name)
    if ($Name -ne 'WinFsp.Launcher') { throw 'Unexpected service read' }
    $global:ServiceReads++
    return SERVICE_RESULT
}
$errorMessage = $null
try { & HELPER -Directory DIRECTORY -TimeoutSeconds 2 }
catch { $errorMessage = $_.Exception.Message }
[ordered]@{ error = $errorMessage; download = @($global:Download); calls = @($global:Calls);
    killed = @($global:Killed); waits = @($global:Waits); hashes = $global:HashReads; services = $global:ServiceReads } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath RESULT -Encoding utf8
""".replace("DOWNLOAD_CODE", str(download_code))
                .replace("HASH_VALUE", literal(HASH if hash_matches else "bad hash"))
                .replace("INSTALL_CODE", str(install_code))
                .replace("WAIT_RESULT", "$false" if timeout else "$true")
                .replace("SERVICE_RESULT", "([pscustomobject]@{ Name = 'WinFsp.Launcher' })" if service else "$null")
                .replace("HELPER", literal(HELPER))
                .replace("DIRECTORY", literal(directory / "cache with spaces"))
                .replace("RESULT", literal(result_path)),
                encoding="utf-8",
            )
            process = subprocess.run(
                [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            return json.loads(result_path.read_text(encoding="utf-8-sig"))

    def test_success_and_reboot_required_code_install_once(self):
        for code in (0, 3010):
            with self.subTest(code=code):
                result = self.run_helper(install_code=code)
                self.assertIsNone(result["error"])
                self.assertEqual(len(result["calls"]), 1)
                self.assertEqual(result["hashes"], 1)
                self.assertEqual(result["services"], 1)
                self.assertEqual(result["waits"], [2000])
                self.assertEqual(result["killed"], [])
                args = result["calls"][0]["arguments"]
                self.assertEqual(args[0], "/i")
                self.assertTrue(args[1].startswith('"') and args[1].endswith('"'))
                self.assertIn("cache with spaces", args[1])
                self.assertEqual(args[2:5], ["/qn", "/norestart", "/l*v"])
                self.assertIn(URL, result["download"])

    def test_download_failure_never_reads_hash_or_starts_msi(self):
        result = self.run_helper(download_code=22)
        self.assertIn("download failed with exit code 22", result["error"])
        self.assertEqual(result["hashes"], 0)
        self.assertEqual(result["calls"], [])

    def test_hash_mismatch_never_starts_msi(self):
        result = self.run_helper(hash_matches=False)
        self.assertIn("SHA-256 does not match", result["error"])
        self.assertEqual(result["calls"], [])

    def test_msi_failure_is_not_hidden_by_service_registration(self):
        result = self.run_helper(install_code=1603)
        self.assertIn("failed with exit code 1603", result["error"])
        self.assertEqual(len(result["calls"]), 1)
        self.assertEqual(result["services"], 0)

    def test_timeout_terminates_only_the_spawned_installer_tree(self):
        result = self.run_helper(timeout=True)
        self.assertIn("timed out", result["error"])
        self.assertEqual(result["killed"], [["/PID", 7400, "/T", "/F"]])
        self.assertEqual(result["services"], 0)

    def test_missing_service_refuses_a_successful_msi_exit(self):
        result = self.run_helper(service=False)
        self.assertIn("Launcher is unavailable", result["error"])
        self.assertEqual(result["services"], 1)


if __name__ == "__main__":
    unittest.main()
