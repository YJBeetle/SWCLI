[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [Parameter(Mandatory = $true)]
    [string]$RemotePath,
    [ValidatePattern("^[A-Z]$")]
    [string]$DriveLetter = "R",
    [Parameter(Mandatory = $true)]
    [string]$CacheDirectory,
    [Parameter(Mandatory = $true)]
    [int64]$CacheMaxBytes,
    [Parameter(Mandatory = $true)]
    [string]$LogPath,
    [Parameter(Mandatory = $true)]
    [string]$PidPath
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command rclone -ErrorAction SilentlyContinue)) {
    throw "rclone is not installed or not on PATH"
}
if (-not (Get-Service -Name WinFsp.Launcher -ErrorAction SilentlyContinue)) {
    throw "WinFsp.Launcher is unavailable"
}
if (Test-Path "${DriveLetter}:\") {
    throw "Drive ${DriveLetter}: is already in use"
}

New-Item -ItemType Directory -Force -Path $CacheDirectory | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null
$cacheSize = "$CacheMaxBytes"
$arguments = @(
    "mount", $RemotePath, "${DriveLetter}:",
    "--config", $ConfigPath,
    "--read-only",
    "--vfs-cache-mode", "full",
    "--vfs-cache-max-size", $cacheSize,
    "--vfs-cache-min-free-space", "2G",
    "--vfs-read-ahead", "32M",
    "--vfs-read-chunk-size", "16M",
    "--vfs-read-chunk-size-limit", "64M",
    "--buffer-size", "16M",
    "--dir-cache-time", "24h",
    "--cache-dir", $CacheDirectory,
    "--drive-acknowledge-abuse",
    "--stats", "30s",
    "--stats-one-line",
    "--log-level", "INFO",
    "--log-file", $LogPath
)

$mountProcess = Start-Process -FilePath "rclone" -ArgumentList $arguments -PassThru -WindowStyle Hidden
$mountProcess.Id | Set-Content -Path $PidPath -NoNewline -Encoding ascii
for ($attempt = 1; $attempt -le 60; $attempt++) {
    if ($mountProcess.HasExited) {
        throw "rclone mount exited early with code $($mountProcess.ExitCode); see $LogPath"
    }
    if (Test-Path "${DriveLetter}:\") {
        Write-Host "[rclone] Google Drive is available at ${DriveLetter}:\ (PID $($mountProcess.Id))"
        exit 0
    }
    Start-Sleep -Seconds 1
    $mountProcess.Refresh()
}
throw "rclone mount did not expose ${DriveLetter}: within 60 seconds"
