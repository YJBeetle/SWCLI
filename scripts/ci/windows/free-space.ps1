[CmdletBinding()]
param(
    [ValidateSet("conservative", "aggressive")]
    [string]$Profile = "conservative"
)

$ErrorActionPreference = "Stop"
if ($env:RUNNER_ENVIRONMENT -ne "github-hosted") {
    throw "Disk cleanup is intentionally limited to disposable GitHub-hosted runners."
}

function Remove-OptionalPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return
    }
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if ($resolved -in @("C:\", "D:\", $env:SystemDrive + "\")) {
        throw "Refusing to remove a drive root: $resolved"
    }
    Write-Host "[disk] Removing optional hosted-runner payload: $resolved"
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    & cmd.exe /d /c "docker info >nul 2>&1"
    if ($LASTEXITCODE -eq 0) {
        & cmd.exe /d /c "docker system prune --all --force"
    }
    else {
        Write-Host "[disk] Docker CLI is installed but its daemon is unavailable; skipping prune."
    }
}

$conservativePaths = @(
    $env:ANDROID_HOME,
    "${env:ProgramFiles(x86)}\Android",
    "$env:ProgramData\chocolatey\cache"
) | Select-Object -Unique
foreach ($path in $conservativePaths) {
    Remove-OptionalPath -Path $path
}

if ($Profile -eq "aggressive") {
    $aggressivePaths = @(
        "$env:ProgramFiles\Microsoft Visual Studio\2022\Enterprise",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools",
        "${env:ProgramFiles(x86)}\Windows Kits\10",
        "$env:ProgramFiles\dotnet",
        "C:\ghcup"
    )
    foreach ($path in $aggressivePaths) {
        Remove-OptionalPath -Path $path
    }
}

$systemDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$env:SystemDrive'"
Write-Host ("[disk] Free space after cleanup: {0:N2} GiB" -f ($systemDrive.FreeSpace / 1GB))
