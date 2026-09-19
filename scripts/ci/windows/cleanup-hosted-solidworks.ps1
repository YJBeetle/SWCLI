[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PrivateRoot,

    [Parameter(Mandatory = $true)]
    [string]$ProbeRoot
)

$ErrorActionPreference = "Continue"
$daemonPidPath = if ($env:SWCLI_SMOKE_ROOT) {
    Join-Path $env:SWCLI_SMOKE_ROOT "swclid.pid"
} else {
    $null
}
if ($daemonPidPath -and (Test-Path -LiteralPath $daemonPidPath)) {
    $daemonPid = [int](Get-Content -LiteralPath $daemonPidPath -Raw)
    & taskkill.exe /PID $daemonPid /T /F 2>$null | Out-Null
}
Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$lmgrdPidPath = Join-Path $PrivateRoot "state\lmgrd.pid"
if (Test-Path -LiteralPath $lmgrdPidPath) {
    $licensePid = [int](Get-Content -LiteralPath $lmgrdPidPath -Raw)
    & taskkill.exe /PID $licensePid /T /F 2>$null | Out-Null
}

$imdiskState = Join-Path $ProbeRoot "imdisk"
$mountPointPath = Join-Path $imdiskState "mount-point.txt"
if (Test-Path -LiteralPath $mountPointPath) {
    $mountPoint = (Get-Content -LiteralPath $mountPointPath -Raw -Encoding utf8).Trim()
    & imdisk.exe -d -m $mountPoint 2>$null | Out-Null
}
$devioPidPath = Join-Path $imdiskState "devio.pid"
if (Test-Path -LiteralPath $devioPidPath) {
    $devioPid = [int](Get-Content -LiteralPath $devioPidPath -Raw)
    Stop-Process -Id $devioPid -Force -ErrorAction SilentlyContinue
}

$rclonePidPath = Join-Path $ProbeRoot "rclone.pid"
if (Test-Path -LiteralPath $rclonePidPath) {
    $mountPid = [int](Get-Content -LiteralPath $rclonePidPath -Raw)
    Stop-Process -Id $mountPid -Force -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath $PrivateRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $ProbeRoot "rclone.conf") -Force -ErrorAction SilentlyContinue
Write-Host "[cleanup] Removed private installer inputs, logs, and credentials from the disposable runner"
exit 0
