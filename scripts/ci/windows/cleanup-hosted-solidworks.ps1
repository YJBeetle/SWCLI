[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PrivateRoot,

    [Parameter(Mandatory = $true)]
    [string]$ProbeRoot
)

$ErrorActionPreference = "Continue"
Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$lmgrdPidPath = Join-Path $PrivateRoot "state\lmgrd.pid"
if (Test-Path -LiteralPath $lmgrdPidPath) {
    $licensePid = [int](Get-Content -LiteralPath $lmgrdPidPath -Raw)
    & taskkill.exe /PID $licensePid /T /F 2>$null | Out-Null
}

$rclonePidPath = Join-Path $ProbeRoot "rclone.pid"
if (Test-Path -LiteralPath $rclonePidPath) {
    $mountPid = [int](Get-Content -LiteralPath $rclonePidPath -Raw)
    Stop-Process -Id $mountPid -Force -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath $PrivateRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $ProbeRoot "rclone.conf") -Force -ErrorAction SilentlyContinue
Write-Host "[cleanup] Removed private installer inputs, logs, and credentials from the disposable runner"
