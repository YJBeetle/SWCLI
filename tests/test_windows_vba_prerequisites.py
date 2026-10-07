"""Installer/cache contracts and non-installing Windows VBA helper tests."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_SCRIPTS = ROOT / "scripts" / "ci" / "windows"
HELPER = WINDOWS_SCRIPTS / "install-vba-prerequisites.ps1"
CACHE_KEY = "windows-2025-solidworks-2025-sp5-core-v4-vba71"


def script(name):
    return (WINDOWS_SCRIPTS / name).read_text(encoding="utf-8")


def workflow_step(workflow, name):
    marker = "      - name: " + name
    return workflow.split(marker, 1)[1].split("\n      - ", 1)[0]


class WindowsVbaPrerequisiteContractsTests(unittest.TestCase):
    def assert_mandatory_string(self, source, name):
        self.assertRegex(
            source,
            r"\[Parameter\(Mandatory\s*=\s*\$true\)\]\s*\[string\]\$"
            + re.escape(name)
            + r"\b",
        )

    def test_cold_install_validates_both_official_packages_before_installing(self):
        source = script("install-solidworks.ps1")
        self.assert_mandatory_string(source, "InventoryPath")
        self.assertIn('Join-Path $MediaRoot "prereqs\\VBA"', source)
        self.assertIn('Join-Path $vbaSourceDirectory "vba71.msi"', source)
        self.assertIn('Join-Path $vbaSourceDirectory "vba71_1033.msi"', source)
        required = source.index("foreach ($requiredFile")
        validation_end = source.index("function Invoke-Installer", required)
        validation = source[required:validation_end]
        self.assertIn("$vbaMsi, $vbaLanguageMsi", validation)
        self.assertIn("Test-Path -LiteralPath $requiredFile -PathType Leaf", validation)
        helper = source.index('install-vba-prerequisites.ps1"')
        login = source.index('Invoke-Installer -Name "SOLIDWORKS Login Manager"')
        core = source.index('Invoke-Installer -Name "SOLIDWORKS core MSI"')
        self.assertLess(validation_end, helper)
        self.assertLess(helper, login)
        self.assertLess(login, core)
        invocation = source[helper:login]
        for parameter in (
            "-VbaSourceDirectory $vbaSourceDirectory",
            "-LogDirectory $LogDirectory",
            "-InventoryPath $InventoryPath",
            "-TimeoutSeconds $TimeoutSeconds",
        ):
            self.assertIn(parameter, invocation)

    def test_export_caches_complete_vba_media_and_format_two_paths(self):
        source = script("export-solidworks-cache-state.ps1")
        self.assert_mandatory_string(source, "VbaSourceDirectory")
        validation = source.index(
            'foreach ($package in @("vba71.msi", "vba71_1033.msi"))'
        )
        self.assertLess(
            validation, source.index("Remove-Item -LiteralPath $StateDirectory")
        )
        self.assertIn('Join-Path $StateDirectory "vba-media"', source)
        self.assertIn(
            'Copy-Item -Path (Join-Path $VbaSourceDirectory "*") '
            "-Destination $cachedVbaMedia -Recurse -Force",
            source,
        )
        manifest = source.split("$manifest = [ordered]@{", 1)[1]
        for field in (
            "format = 2",
            'vba_media_directory = "vba-media"',
            'vba_installer = "vba-media\\vba71.msi"',
            'vba_language_installer = "vba-media\\vba71_1033.msi"',
        ):
            self.assertIn(field, manifest)

    def test_restore_requires_format_two_and_installs_vba_before_login_manager(self):
        source = script("restore-solidworks-cache-state.ps1")
        self.assert_mandatory_string(source, "InventoryPath")
        format_check = source.index("if ($manifest.format -ne 2)")
        helper = source.index('install-vba-prerequisites.ps1"')
        login = source.index('$loginManager = Start-Process -FilePath "msiexec.exe"')
        self.assertLess(format_check, helper)
        self.assertLess(helper, login)
        validation = source[:helper]
        self.assertIn(
            "$manifest.vba_installer, $manifest.vba_language_installer", validation
        )
        self.assertIn(
            "Test-Path -LiteralPath $loginManagerMsi -PathType Leaf", validation
        )
        self.assertIn(
            "Test-Path -LiteralPath (Join-Path $StateDirectory $relativePath) -PathType Leaf",
            validation,
        )
        invocation = source[helper:login]
        self.assertIn(
            "-VbaSourceDirectory (Join-Path $StateDirectory $manifest.vba_media_directory)",
            invocation,
        )
        self.assertIn("-InventoryPath $InventoryPath", invocation)
        self.assertEqual(source.count('Start-Process -FilePath "msiexec.exe"'), 1)
        self.assertNotIn("solidworks.msi", source.lower())

    def test_cold_and_cache_hit_paths_share_inventory_and_bumped_cache_key(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        restore_cache = workflow_step(
            workflow, "Restore clean SOLIDWORKS installation cache"
        )
        save_cache = workflow_step(workflow, "Save clean SOLIDWORKS installation cache")
        self.assertIn("key: " + CACHE_KEY, restore_cache)
        self.assertIn(
            "key: ${{ steps.solidworks-cache.outputs.cache-primary-key }}", save_cache
        )
        self.assertEqual(workflow.count(CACHE_KEY), 1)
        self.assertNotRegex(workflow, r"core-v[123]\b")
        for step in (
            "Install native SOLIDWORKS",
            "Restore cached SOLIDWORKS registry and official prerequisites",
        ):
            self.assertIn(
                '-InventoryPath "$env:SWCLI_SMOKE_ROOT\\vba-runtime.json"',
                workflow_step(workflow, step),
            )
        self.assertIn(
            '-VbaSourceDirectory "$env:SW_MEDIA_ROOT\\prereqs\\VBA"',
            workflow_step(workflow, "Prepare clean installation cache state"),
        )

    def test_common_helper_uses_bounded_msi_calls_and_safe_inventory(self):
        source = HELPER.read_text(encoding="utf-8")
        for name in ("VbaSourceDirectory", "LogDirectory", "InventoryPath"):
            self.assert_mandatory_string(source, name)
        self.assertIn('$packages = @("vba71.msi", "vba71_1033.msi")', source)
        self.assertLess(
            source.index("Test-Path -LiteralPath $packagePath"),
            source.index("Start-Process"),
        )
        self.assertIn('$process = Start-Process -FilePath "msiexec.exe"', source)
        self.assertIn('"/qn", "/norestart", "DISABLEROLLBACK=1"', source)
        self.assertIn("$process.WaitForExit($TimeoutSeconds * 1000)", source)
        self.assertIn("taskkill.exe /PID $process.Id /T /F", source)
        self.assertIn("@(0, 1641, 3010) -notcontains $process.ExitCode", source)
        self.assertIn("UserData\\S-1-5-18\\Products\\*\\InstallProperties", source)
        self.assertIn('@("VBE7.DLL", "1033\\VBE7INTL.DLL")', source)
        self.assertIn("solidworks_vba_initialization_verified = $false", source)
        product_fields = source.split("ForEach-Object {", 1)[1].split(
            "\n            }", 1
        )[0]
        self.assertEqual(
            re.findall(r"^\s*(\w+)\s*=", product_fields, re.MULTILINE),
            ["name", "version", "product_key"],
        )
        self.assertIn(
            "if ($null -ne $installationError) { throw $installationError }", source
        )
        for name in (
            "install-vba-prerequisites.ps1",
            "install-solidworks.ps1",
            "export-solidworks-cache-state.ps1",
            "restore-solidworks-cache-state.ps1",
        ):
            text = script(name)
            self.assertNotRegex(text, r"(?i)Win32_Product|KB2783832|\.msp\b")

    def test_runtime_dll_gate_follows_inventory_and_original_installation_error(self):
        source = HELPER.read_text(encoding="utf-8")
        inventory = source.index("$inventory = Write-VbaInventory")
        primary_error = source.index(
            "if ($null -ne $installationError) { throw $installationError }"
        )
        missing_dll_error = source.index(
            "VBA installation completed but required runtime DLLs are missing"
        )
        self.assertLess(inventory, primary_error)
        self.assertLess(primary_error, missing_dll_error)
        gate = source[primary_error:missing_dll_error]
        self.assertIn("$inventory.dlls", gate)
        self.assertIn("-not $_.exists", gate)


POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")


@unittest.skipUnless(
    os.name == "nt" and POWERSHELL,
    "requires Windows PowerShell; never runs MSI installers",
)
class WindowsVbaPrerequisiteExecutionTests(unittest.TestCase):
    def run_helper(
        self,
        exit_codes=(0, 0),
        missing=(),
        inventory_failure=False,
        timeout=False,
        missing_dlls=(),
    ):
        with tempfile.TemporaryDirectory(prefix="swcli-vba-contract-") as temporary:
            directory = Path(temporary)
            media = directory / "official VBA media"
            media.mkdir()
            for name in ("vba71.msi", "vba71_1033.msi"):
                if name not in missing:
                    (media / name).write_bytes(
                        b"synthetic test package; never installed"
                    )
            (media / "external payload.cab").write_bytes(b"synthetic cabinet")
            common_files = directory / "synthetic native common files"
            runtime = common_files / "Microsoft Shared" / "VBA" / "VBA7.1"
            for relative_path in ("VBE7.DLL", "1033\\VBE7INTL.DLL"):
                if relative_path not in missing_dlls:
                    dll = runtime.joinpath(*relative_path.split("\\"))
                    dll.parent.mkdir(parents=True, exist_ok=True)
                    dll.write_bytes(b"synthetic DLL; no executable code")
            inventory = directory / "evidence" / "vba-runtime.json"
            if inventory_failure:
                inventory.parent.write_text(
                    "block directory creation", encoding="utf-8"
                )
            result_path = directory / "result.json"
            wrapper = directory / "fake-install.ps1"

            def literal(value):
                return "'" + str(value).replace("'", "''") + "'"

            wrapper.write_text(
                """$ErrorActionPreference = 'Stop'
$global:Calls = @()
$global:Killed = @()
$global:Waits = @()
$global:ExitCodes = @(EXIT_CODES)
$global:FakeTimeout = TIMEOUT
function global:Start-Process {
    param([string]$FilePath, [string[]]$ArgumentList, [switch]$PassThru)
    $index = $global:Calls.Count
    $global:Calls += [ordered]@{ file = $FilePath; arguments = @($ArgumentList) }
    $process = [pscustomobject]@{ Id = 7400 + $index; ExitCode = $global:ExitCodes[$index] }
    $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
        param($milliseconds)
        $global:Waits += $milliseconds
        return (-not $global:FakeTimeout)
    }
    return $process
}
function global:taskkill.exe {
    $global:Killed += ,@($args)
    $global:LASTEXITCODE = 0
}
function global:Get-ItemProperty {
    [CmdletBinding()]
    param([string]$Path)
    return [pscustomobject]@{
        DisplayName = 'Microsoft Visual Basic for Applications 7.1'
        DisplayVersion = '7.1.0.0'
        PSPath = 'Registry::HKEY_LOCAL_MACHINE\\Synthetic\\PublicVbaProduct\\InstallProperties'
        PrivateValue = 'PRIVATE_SENTINEL_MUST_NOT_BE_EXPORTED'
    }
}
function global:Get-Item {
    [CmdletBinding()]
    param([string]$LiteralPath)
    if (-not $LiteralPath.StartsWith($env:CommonProgramW6432)) {
        throw 'Test blocked an unexpected native file read'
    }
    return [pscustomobject]@{ VersionInfo = [pscustomobject]@{ FileVersion = '7.1.0.0' } }
}
$env:CommonProgramW6432 = COMMON_FILES
$errorMessage = $null
try {
    & HELPER -VbaSourceDirectory MEDIA -LogDirectory LOGS -InventoryPath INVENTORY -TimeoutSeconds 2
} catch {
    $errorMessage = $_.Exception.Message
}
[ordered]@{ error = $errorMessage; calls = @($global:Calls); killed = @($global:Killed); waits = @($global:Waits) } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath RESULT -Encoding utf8
""".replace("EXIT_CODES", ", ".join(map(str, exit_codes)))
                .replace("TIMEOUT", "$true" if timeout else "$false")
                .replace("COMMON_FILES", literal(common_files))
                .replace("HELPER", literal(HELPER))
                .replace("MEDIA", literal(media))
                .replace("LOGS", literal(directory / "logs"))
                .replace("INVENTORY", literal(inventory))
                .replace("RESULT", literal(result_path)),
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(wrapper),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            result = json.loads(result_path.read_text(encoding="utf-8-sig"))
            evidence = None
            if inventory.is_file():
                evidence = json.loads(inventory.read_text(encoding="utf-8-sig"))
            return result, evidence, process.stdout + process.stderr

    def test_success_and_reboot_exit_codes_install_both_packages(self):
        for codes in ((0, 0), (1641, 3010), (3010, 1641)):
            with self.subTest(exit_codes=codes):
                result, evidence, output = self.run_helper(codes)
                self.assertIsNone(result["error"])
                self.assertEqual(len(result["calls"]), 2)
                for call, package in zip(
                    result["calls"], ("vba71.msi", "vba71_1033.msi")
                ):
                    self.assertEqual(call["file"], "msiexec.exe")
                    arguments = call["arguments"]
                    self.assertEqual(arguments[0], "/i")
                    self.assertTrue(arguments[1].endswith("\\" + package + '"'))
                    self.assertEqual(
                        arguments[2:5], ["/qn", "/norestart", "DISABLEROLLBACK=1"]
                    )
                    self.assertEqual(arguments[5], "/l*v")
                self.assertEqual(result["waits"], [2000, 2000])
                self.assertEqual(result["killed"], [])
                self.assertEqual(evidence["format"], 1)
                self.assertFalse(evidence["solidworks_vba_initialization_verified"])
                self.assertEqual(
                    set(evidence["products"][0]), {"name", "version", "product_key"}
                )
                self.assertEqual(
                    [item["relative_path"] for item in evidence["dlls"]],
                    ["VBE7.DLL", "1033\\VBE7INTL.DLL"],
                )
                self.assertTrue(all(item["exists"] for item in evidence["dlls"]))
                self.assertEqual(
                    [item["version"] for item in evidence["dlls"]],
                    ["7.1.0.0", "7.1.0.0"],
                )
                self.assertNotIn("PRIVATE_SENTINEL", json.dumps(evidence) + output)

    def test_successful_msi_requires_each_native_runtime_dll_and_keeps_inventory(self):
        for missing in (
            ("VBE7.DLL",),
            ("1033\\VBE7INTL.DLL",),
            ("VBE7.DLL", "1033\\VBE7INTL.DLL"),
        ):
            with self.subTest(missing_dlls=missing):
                result, evidence, _ = self.run_helper(missing_dlls=missing)
                self.assertIn(
                    "VBA installation completed but required runtime DLLs are missing",
                    result["error"],
                )
                self.assertEqual(len(result["calls"]), 2)
                self.assertIsNotNone(evidence)
                for item in evidence["dlls"]:
                    self.assertEqual(
                        item["exists"], item["relative_path"] not in missing
                    )
                    if not item["exists"]:
                        self.assertIsNone(item["version"])

    def test_missing_runtime_dlls_do_not_replace_original_msi_failure(self):
        missing = ("VBE7.DLL", "1033\\VBE7INTL.DLL")
        result, evidence, _ = self.run_helper((1603, 0), missing_dlls=missing)
        self.assertIn("failed with exit code 1603", result["error"])
        self.assertNotIn("required runtime DLLs are missing", result["error"])
        self.assertEqual(len(result["calls"]), 1)
        self.assertFalse(any(item["exists"] for item in evidence["dlls"]))

    def test_bad_media_is_rejected_before_any_msi_runs_but_retains_inventory(self):
        for missing in ("vba71.msi", "vba71_1033.msi"):
            with self.subTest(missing=missing):
                result, evidence, _ = self.run_helper(missing=(missing,))
                self.assertIn(
                    "Official VBA prerequisite is unavailable", result["error"]
                )
                self.assertIn(missing, result["error"])
                self.assertEqual(result["calls"], [])
                self.assertIsNotNone(evidence)

    def test_msi_failure_stops_later_installation_and_keeps_inventory(self):
        for codes, count in (((1603, 0), 1), ((0, 1603), 2)):
            with self.subTest(exit_codes=codes):
                result, evidence, _ = self.run_helper(codes)
                self.assertIn("failed with exit code 1603", result["error"])
                self.assertEqual(len(result["calls"]), count)
                self.assertIsNotNone(evidence)

    def test_timeout_kills_only_the_fake_installer_pid(self):
        result, evidence, _ = self.run_helper(timeout=True)
        self.assertIn("timed out after 2 seconds", result["error"])
        self.assertEqual(len(result["calls"]), 1)
        self.assertEqual(result["killed"], [["/PID", 7400, "/T", "/F"]])
        self.assertIsNotNone(evidence)

    def test_inventory_failure_does_not_replace_installation_error(self):
        result, evidence, output = self.run_helper(
            (1603, 0),
            inventory_failure=True,
            missing_dlls=("VBE7.DLL", "1033\\VBE7INTL.DLL"),
        )
        self.assertIn("failed with exit code 1603", result["error"])
        self.assertIn("original installation failure is retained", output)
        self.assertIsNone(evidence)

    def test_inventory_failure_after_success_is_fatal(self):
        result, evidence, _ = self.run_helper(inventory_failure=True)
        self.assertIsNotNone(result["error"])
        self.assertEqual(len(result["calls"]), 2)
        self.assertIsNone(evidence)


if __name__ == "__main__":
    unittest.main()
