$ErrorActionPreference = "Stop"
$currentProcess = [Diagnostics.Process]::GetCurrentProcess()
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$sessionId = $currentProcess.SessionId

Write-Host "[session] User: $identity"
Write-Host "[session] Session ID: $sessionId"
Write-Host "[session] UserInteractive: $([Environment]::UserInteractive)"

if (-not [Environment]::UserInteractive -or $sessionId -eq 0) {
    throw "SOLIDWORKS E2E requires an interactively logged-in Windows user; do not run the Actions runner as a Windows service in Session 0."
}
