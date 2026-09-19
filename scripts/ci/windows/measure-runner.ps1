[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$systemDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$env:SystemDrive'"
$operatingSystem = Get-CimInstance Win32_OperatingSystem
$sessionId = [Diagnostics.Process]::GetCurrentProcess().SessionId
$measurement = [ordered]@{
    timestamp_utc = [DateTime]::UtcNow.ToString("o")
    runner_environment = $env:RUNNER_ENVIRONMENT
    image_os = $env:ImageOS
    image_version = $env:ImageVersion
    operating_system = $operatingSystem.Caption
    operating_system_version = $operatingSystem.Version
    user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    user_interactive = [Environment]::UserInteractive
    session_id = $sessionId
    system_drive = $env:SystemDrive
    disk_size_bytes = [int64]$systemDrive.Size
    disk_free_bytes = [int64]$systemDrive.FreeSpace
    disk_size_gib = [math]::Round($systemDrive.Size / 1GB, 2)
    disk_free_gib = [math]::Round($systemDrive.FreeSpace / 1GB, 2)
}

$measurement | ConvertTo-Json -Depth 4 | Tee-Object -FilePath $OutputPath
if ($env:GITHUB_STEP_SUMMARY) {
    @"
### Windows runner measurement

- OS: $($measurement.operating_system) $($measurement.operating_system_version)
- Image: $($measurement.image_os) $($measurement.image_version)
- Session: $sessionId; interactive: $($measurement.user_interactive)
- System drive: $($measurement.disk_free_gib) GiB free of $($measurement.disk_size_gib) GiB
"@ | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8
}
