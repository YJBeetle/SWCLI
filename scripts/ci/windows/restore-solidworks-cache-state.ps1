[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StateDirectory,

    [Parameter(Mandatory = $true)]
    [string]$LogDirectory,

    [Parameter(Mandatory = $true)]
    [string]$InventoryPath
)

$ErrorActionPreference = "Stop"
$manifestPath = Join-Path $StateDirectory "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "SOLIDWORKS cache manifest is missing: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($manifest.format -ne 2) {
    throw "Unsupported SOLIDWORKS cache format: $($manifest.format)"
}
if (-not (Test-Path -LiteralPath $manifest.solidworks_executable -PathType Leaf)) {
    throw "Cached SOLIDWORKS executable is missing: $($manifest.solidworks_executable)"
}

# VBA and Login Manager installed state cannot be reconstructed from shared
# files. Reapply the complete small official media using Windows Installer.
$loginManagerMsi = Join-Path $StateDirectory $manifest.login_manager_installer
if (-not (Test-Path -LiteralPath $loginManagerMsi -PathType Leaf)) {
    throw "Cached SOLIDWORKS Login Manager MSI is missing: $loginManagerMsi"
}
foreach ($relativePath in @($manifest.vba_installer, $manifest.vba_language_installer)) {
    if ([string]::IsNullOrWhiteSpace($relativePath) -or
        -not (Test-Path -LiteralPath (Join-Path $StateDirectory $relativePath) -PathType Leaf)) {
        throw "Cached official VBA prerequisite is missing: $relativePath"
    }
}
if ([string]::IsNullOrWhiteSpace($manifest.vba_media_directory)) {
    throw "Cached official VBA media directory is missing"
}
& "$PSScriptRoot\install-vba-prerequisites.ps1" `
    -VbaSourceDirectory (Join-Path $StateDirectory $manifest.vba_media_directory) `
    -LogDirectory $LogDirectory `
    -InventoryPath $InventoryPath

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$loginManagerLog = Join-Path $LogDirectory "login-manager-cache-restore.log"
$loginManager = Start-Process -FilePath "msiexec.exe" -ArgumentList @(
    "/i", ('"{0}"' -f $loginManagerMsi), "/qn", "/norestart", "DISABLEROLLBACK=1",
    "/l*v", ('"{0}"' -f $loginManagerLog)
) -Wait -PassThru
if (@(0, 1641, 3010) -notcontains $loginManager.ExitCode) {
    throw "Cached SOLIDWORKS Login Manager MSI failed with exit code $($loginManager.ExitCode)"
}

foreach ($entry in $manifest.registry_exports) {
    $registryFile = Join-Path $StateDirectory $entry.file
    if (-not (Test-Path -LiteralPath $registryFile -PathType Leaf)) {
        throw "Cached registry export is missing: $registryFile"
    }
    & reg.exe import $registryFile | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restore cached registry key: $($entry.key)"
    }
}

$registeredClsid = (Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\SldWorks.Application\CLSID" -ErrorAction Stop).'(default)'
if ($registeredClsid -ne $manifest.application_clsid) {
    throw "Restored SldWorks.Application CLSID does not match the cache manifest"
}
$serverCommand = [string](Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\CLSID\$registeredClsid\LocalServer32" -ErrorAction Stop).'(default)'
if ($serverCommand -notmatch [regex]::Escape("SLDWORKS.exe")) {
    throw "Restored SOLIDWORKS COM registration has an invalid LocalServer32 command"
}
Write-Host "[cache] Restored SOLIDWORKS files, official VBA, Login Manager, and registry registration"
