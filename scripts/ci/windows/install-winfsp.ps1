[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Directory,

    [ValidateRange(1, 600)]
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
# The upstream v2.1 release publishes this exact MSI and SHA-256.
# Avoid Chocolatey's WinFsp feed: a 504 can omit it despite a success summary.
$url = "https://github.com/winfsp/winfsp/releases/download/v2.1/winfsp-2.1.25156.msi"
$expectedHash = "073a70e00f77423e34bed98b86e600def93393ba5822204fac57a29324db9f7a"
New-Item -ItemType Directory -Force -Path $Directory | Out-Null
$installerPath = Join-Path $Directory "winfsp-2.1.25156.msi"
$logPath = Join-Path $Directory "winfsp-install.log"

# Only the download is retried; installation and CAD operations are not.
& curl.exe --fail --location --retry 3 --retry-delay 2 --retry-max-time 120 `
    --connect-timeout 15 --max-time 60 --output $installerPath $url
if ($LASTEXITCODE -ne 0) {
    throw "WinFsp download failed with exit code $LASTEXITCODE"
}
if ((Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash -ne $expectedHash) {
    throw "WinFsp installer SHA-256 does not match the pinned upstream release"
}

$process = Start-Process -FilePath "msiexec.exe" -ArgumentList @(
    "/i", ('"{0}"' -f $installerPath), "/qn", "/norestart",
    "/l*v", ('"{0}"' -f $logPath)
) -PassThru
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
    throw "WinFsp installation timed out after $TimeoutSeconds seconds; see $logPath"
}
if (@(0, 3010) -notcontains $process.ExitCode) {
    throw "WinFsp installation failed with exit code $($process.ExitCode); see $logPath"
}
if (-not (Get-Service -Name WinFsp.Launcher -ErrorAction SilentlyContinue)) {
    throw "WinFsp MSI completed but WinFsp.Launcher is unavailable; see $logPath"
}
Write-Host "[WinFsp] Verified official installer hash, MSI completion and Launcher registration"
