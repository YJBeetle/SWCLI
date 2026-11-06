"""Offline harness contracts; these fixtures are not Windows terminal-state proof."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts/ci/windows/smoke-solidworks.ps1"
POWERSHELL = shutil.which("pwsh") or (shutil.which("powershell") if sys.platform == "win32" else None)


def function(source, name):
    start = source.index("function " + name + " {")
    return source[start:source.index("\nfunction ", start + 1)]


class WindowsTaskEvidenceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = HARNESS.read_text(encoding="utf-8")

    def test_inventory_reads_only_related_root_tasks_and_explicit_process_fields(self):
        block = function(self.source, "Save-LifecycleInventory")
        self.assertIn('Get-ScheduledTask -TaskPath "\\" -TaskName "SWCLI-demand-*" -ErrorAction Stop', block)
        self.assertIn('-Property Name, ProcessId, ParentProcessId, CreationDate -ErrorAction Stop', block)
        self.assertIn('Get-CimInstance -ClassName Win32_Process -Filter $filter', block)
        self.assertIn('"CmdletizationQuery_NotFound*"', block)
        for sensitive in ("CommandLine", "ExecutablePath", "Principal", "Triggers", "Get-ScheduledTaskInfo"):
            self.assertNotIn(sensitive, block)
        for mutation in ("Stop-Process", "Unregister-ScheduledTask", "Remove-Item", "Stop-ScheduledTask"):
            self.assertNotIn(mutation, block)

    def test_complete_snapshots_and_differences_are_persisted_without_inventing_empty_success(self):
        inventory = function(self.source, "Save-LifecycleInventory")
        comparison = function(self.source, "Assert-NoNewLifecycleResources")
        for field in ("task_inventory_complete", "process_inventory_complete", "errors", "created_utc", "task_name", "state"):
            self.assertIn(field, inventory)
        self.assertIn('evidence_file = "$Name-inventory.json"', inventory)
        self.assertIn('Set-Content -LiteralPath (Join-Path $Workspace $snapshot.evidence_file)', inventory)
        self.assertIn('stage = "inventory_write"', inventory)
        self.assertIn('"$Name-comparison.json"', comparison)
        self.assertIn('new_tasks = $newTasks; new_processes = $newProcesses', comparison)
        self.assertIn('if (-not $complete) { throw', comparison)
        self.assertIn('$process.process_id)|$($process.name)|$($process.created_utc)', comparison)

    def test_only_complete_new_resources_trigger_bounded_read_only_settling(self):
        block = function(self.source, "Assert-NoNewLifecycleResources")
        self.assertIn('[ValidateRange(0.01, 10.0)][double]$SettleSeconds = 10', block)
        self.assertIn('$settleWait = [Diagnostics.Stopwatch]::StartNew()', block)
        self.assertLess(block.index('if (-not $complete) { throw'), block.index('Start-Sleep'))
        self.assertLess(block.index('if ($passed) { return }'), block.index('Start-Sleep'))
        self.assertIn('$settleWait.Elapsed.TotalSeconds -ge $SettleSeconds', block)
        self.assertIn('"{0}-settle-{1:D2}" -f $Name, $observation', block)
        self.assertIn('original_after = $originalAfter', block)
        self.assertIn('after = $After.evidence_file; observations = $observations', block)
        self.assertEqual(block.count('Save-LifecycleInventory'), 1)
        for mutation in ('Invoke-SwCliJson', 'Stop-Process', 'Unregister-ScheduledTask', 'daemon start', 'daemon stop'):
            self.assertNotIn(mutation, block)

    def test_attach_refusal_invokes_start_once_and_always_collects_post_state(self):
        block = function(self.source, "Invoke-AttachWithoutHostProbe")
        self.assertEqual(block.count("Invoke-SwCliJson"), 1)
        self.assertIn('"daemon", "start", "--attach-existing", "--json"', block)
        self.assertNotIn("while (", block)
        self.assertNotIn("Start-Sleep", block)
        self.assertLess(block.index('"attach-without-host-before"'), block.index("Invoke-SwCliJson"))
        self.assertLess(block.index("finally {"), block.index('"attach-without-host-after"'))
        self.assertIn("Assert-NoNewLifecycleResources -Before $before -After $after", block)
        self.assertIn('if ($null -eq $firstFailure) { throw }', block)
        self.assertIn('"attach-without-host-evidence-error.log"', block)
        transport = function(self.source, "Invoke-SwCliJson")
        self.assertIn('Join-Path $Workspace "$Name.json"', transport)
        self.assertIn('Join-Path $Workspace "$Name.stderr.log"', transport)

    def test_preexisting_hosts_are_observed_and_refused_without_global_termination(self):
        block = self.source.split('$lifecycleInitial = Save-LifecycleInventory', 1)[1].split('$python =', 1)[0]
        self.assertIn('"SLDWORKS.exe"', block)
        self.assertIn("pre-existing SOLIDWORKS host", block)
        self.assertNotIn("Stop-Process", block)
        self.assertNotIn("Stop-ScheduledTask", self.source)
        self.assertNotIn("Unregister-ScheduledTask", self.source)

    def test_owned_attached_restart_and_cleanup_boundaries_are_wired(self):
        for name in ("visible-stop-final", "owned-stop-final", "attached-live-before",
                     "attached-live-stop-final", "attached-restart-ready",
                     "attached-disconnected-stop-final", "lifecycle-final"):
            self.assertIn('Save-LifecycleInventory -Name "' + name + '"', self.source)
        self.assertEqual(self.source.count("    Invoke-AttachWithoutHostProbe\n"), 1)
        cleanup = self.source.split('$cleanupFailure = $null', 1)[1]
        self.assertIn('if ($null -eq $smokeFailure -and $null -eq $cleanupFailure) { throw }', cleanup)
        self.assertIn('"lifecycle-final-evidence-error.log"', cleanup)
        self.assertIn('if ($null -ne $cleanupFailure -and $null -eq $smokeFailure) { throw $cleanupFailure }', cleanup)
        self.assertIn('$smokeFailure = $_', self.source)

    @unittest.skipUnless(POWERSHELL, "PowerShell required for offline JSON/preservation contract execution")
    def test_offline_fixture_writes_snapshots_retains_raw_refusal_and_preserves_first_failure(self):
        # Only the new functions are evaluated. All native inventory commands and
        # CLI calls are local fixtures; no scheduler, SW, daemon or machine policy
        # is touched. Actual terminal-state acceptance still requires native CI.
        helpers = self.source.split("function Save-LifecycleInventory {", 1)[1].split("function Save-DesktopDiagnostic", 1)[0]
        # Shorten only the generated offline fixture's observation window;
        # every production call keeps the default ten-second OS-only budget.
        helpers = helpers.replace('-After $after -Name "attach-without-host"',
                                  '-After $after -Name "attach-without-host" -SettleSeconds 0.5')
        program = "function Save-LifecycleInventory {" + helpers + r'''
$ErrorActionPreference = 'Stop'
$Workspace = $args[0]
$mode = $args[1]
$script:round = 0
$script:probeCalls = 0
function Get-ScheduledTask {
    [CmdletBinding()]
    param($TaskPath, $TaskName)
    if ($TaskPath -ne '\' -or $TaskName -ne 'SWCLI-demand-*') { throw 'inventory scope widened' }
    $script:round++
    [pscustomobject]@{ TaskName='SWCLI-demand-preexisting'; TaskPath='\'; State='Ready' }
    if ($mode -eq 'leak' -and $script:round -ge 2) {
        [pscustomobject]@{ TaskName='SWCLI-demand-new'; TaskPath='\'; State='Running' }
    }
}
function Get-CimInstance {
    [CmdletBinding()]
    param($ClassName, $Filter, $Property)
    if ($ClassName -ne 'Win32_Process' -or 'CommandLine' -in $Property -or $Property.Count -ne 4) {
        throw 'process fields widened'
    }
    if ($mode -in @('observation-failure', 'primary-and-observation-failure') -and $script:round -eq 2) { throw 'secondary observation denied' }
    [pscustomobject]@{ Name='python.exe'; ProcessId=111; ParentProcessId=10; CreationDate=[DateTime]'2025-01-01T00:00:00Z' }
    if (($mode -eq 'leak' -and $script:round -ge 2) -or ($mode -eq 'transient' -and $script:round -eq 2)) {
        [pscustomobject]@{ Name='python.exe'; ProcessId=222; ParentProcessId=20; CreationDate=[DateTime]'2025-01-02T00:00:00Z' }
    }
}
function Get-Process { [CmdletBinding()] param($Name) }
function Invoke-SwCliJson {
    [CmdletBinding()]
    param($Name, $Arguments, [switch]$AllowFailure)
    $script:probeCalls++
    $raw = '{"success":false,"error":{"code":"ExistingHostNotFound"}}'
    Set-Content -LiteralPath (Join-Path $Workspace "$Name.json") -Value $raw -Encoding utf8
    Set-Content -LiteralPath (Join-Path $Workspace "$Name.stderr.log") -Value 'original stderr' -Encoding utf8
    if ($mode -eq 'primary-and-observation-failure') { throw 'PRIMARY-GATE-FAILURE' }
    return ($raw | ConvertFrom-Json)
}
$failure = $null
try { Invoke-AttachWithoutHostProbe } catch { $failure = $_.Exception.Message }
if ($script:probeCalls -ne 1) { throw 'refusal was repeated' }
if ($mode -in @('clean', 'observation-failure', 'primary-and-observation-failure') -and $script:round -ne 2) {
    throw 'clean state or read failure caused another observation'
}
if ($mode -in @('transient', 'leak') -and $script:round -lt 3) { throw 'new process was not observed settling' }
if ($mode -in @('clean', 'transient') -and $null -ne $failure) { throw $failure }
if ($mode -eq 'observation-failure' -and $failure -notlike '*inventory is incomplete*') { throw 'read error was masked' }
if ($mode -eq 'leak' -and $failure -notlike '*left new*') { throw 'residue was not rejected' }
if ($mode -eq 'primary-and-observation-failure' -and $failure -notlike '*PRIMARY-GATE-FAILURE*') {
    throw 'observation error masked original native/CLI failure'
}
[ordered]@{mode=$mode; call_count=$script:probeCalls; failure=$failure} | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $Workspace 'fixture-result.json') -Encoding utf8
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "inventory-contract.ps1"
            script.write_text(program, encoding="utf-8")
            for mode in ("clean", "transient", "leak", "observation-failure", "primary-and-observation-failure"):
                with self.subTest(mode=mode):
                    case = root / mode
                    case.mkdir()
                    result = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                                             "-File", str(script), str(case), mode],
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    before = json.loads((case / "attach-without-host-before-inventory.json").read_text(encoding="utf-8-sig"))
                    after = json.loads((case / "attach-without-host-after-inventory.json").read_text(encoding="utf-8-sig"))
                    comparison = json.loads((case / "attach-without-host-comparison.json").read_text(encoding="utf-8-sig"))
                    self.assertEqual(before["tasks"][0]["task_name"], "SWCLI-demand-preexisting")
                    self.assertEqual(comparison["passed"], mode in ("clean", "transient"))
                    self.assertEqual(comparison["original_after"], "attach-without-host-after-inventory.json")
                    self.assertEqual(comparison["after"], comparison["observations"][-1])
                    for observation in comparison["observations"]:
                        self.assertTrue((case / observation).is_file())
                    self.assertEqual(len(comparison["observations"]), len(set(comparison["observations"])))
                    if mode == "transient":
                        self.assertEqual(len(after["processes"]), 2, "raw after snapshot must remain unchanged")
                        settled = json.loads((case / comparison["after"]).read_text(encoding="utf-8-sig"))
                        self.assertEqual(len(settled["processes"]), 1)
                        self.assertNotEqual(comparison["after"], comparison["original_after"])
                    self.assertIn("ExistingHostNotFound", (case / "attach-without-host.json").read_text(encoding="utf-8-sig"))
                    self.assertIn("original stderr", (case / "attach-without-host.stderr.log").read_text(encoding="utf-8-sig"))
                    self.assertEqual(len(after["errors"]), int(mode in ("observation-failure", "primary-and-observation-failure")))
                    if mode == "leak":
                        self.assertEqual(comparison["new_tasks"][0]["task_name"], "SWCLI-demand-new")
                        self.assertEqual(comparison["new_processes"][0]["process_id"], 222)
                    if mode == "primary-and-observation-failure":
                        self.assertTrue((case / "attach-without-host-evidence-error.log").is_file())


if __name__ == "__main__":
    unittest.main()
