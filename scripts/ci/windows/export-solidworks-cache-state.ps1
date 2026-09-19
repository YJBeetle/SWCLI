[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StateDirectory,

    [Parameter(Mandatory = $true)]
    [string]$LoginManagerSourceDirectory,

    [string]$InstallDirectory = "C:\Program Files\SOLIDWORKS"
)

$ErrorActionPreference = "Stop"
$solidworksExe = Join-Path $InstallDirectory "SLDWORKS.exe"
if (-not (Test-Path -LiteralPath $solidworksExe -PathType Leaf)) {
    throw "Cannot cache a missing SOLIDWORKS installation: $solidworksExe"
}

$installPrefix = [IO.Path]::GetFullPath($InstallDirectory).TrimEnd("\") + "\"
$candidateNames = @("SLDWORKS.exe", "sldworks_fs.exe")
$installedProcesses = @(
    Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object { $candidateNames -contains $_.Name } |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace($_.ExecutablePath) -and
            $_.ExecutablePath.StartsWith($installPrefix, [StringComparison]::OrdinalIgnoreCase)
        }
)
foreach ($process in $installedProcesses) {
    Write-Host "[cache] Stopping $($process.Name) (PID $($process.ProcessId)) before snapshot"
    & taskkill.exe /PID $process.ProcessId /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stop $($process.Name) before creating the cache"
    }
}

Remove-Item -LiteralPath $StateDirectory -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $StateDirectory | Out-Null
if (-not (Test-Path -LiteralPath $LoginManagerSourceDirectory -PathType Container)) {
    throw "SOLIDWORKS Login Manager media is unavailable: $LoginManagerSourceDirectory"
}
$sourceLoginManagerMsi = Join-Path $LoginManagerSourceDirectory "SOLIDWORKS Login Manager.msi"
if (-not (Test-Path -LiteralPath $sourceLoginManagerMsi -PathType Leaf)) {
    throw "SOLIDWORKS Login Manager MSI is unavailable: $sourceLoginManagerMsi"
}
$cachedLoginManagerMedia = Join-Path $StateDirectory "login-manager-media"
New-Item -ItemType Directory -Force -Path $cachedLoginManagerMedia | Out-Null
Copy-Item -Path (Join-Path $LoginManagerSourceDirectory "*") -Destination $cachedLoginManagerMedia -Recurse -Force
$cachedLoginManagerMsi = Join-Path $cachedLoginManagerMedia "SOLIDWORKS Login Manager.msi"

$registryKeys = [ordered]@{
    "hklm-solidworks.reg" = "HKLM\SOFTWARE\SolidWorks"
    "hklm-wow-solidworks.reg" = "HKLM\SOFTWARE\WOW6432Node\SolidWorks"
    "hkcu-solidworks.reg" = "HKCU\SOFTWARE\SolidWorks"
    "classes-sldworks.reg" = "HKLM\SOFTWARE\Classes\SldWorks.Application"
}

$applicationClsid = (Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\SldWorks.Application\CLSID" -ErrorAction Stop).'(default)'
if ([string]::IsNullOrWhiteSpace($applicationClsid)) {
    throw "SldWorks.Application CLSID is unavailable"
}
$registryKeys["classes-sldworks-clsid.reg"] = "HKLM\SOFTWARE\Classes\CLSID\$applicationClsid"

# A direct core-MSI installation registers the versioned ProgID below the
# CLSID, but does not necessarily create SldWorks.Application\CurVer.
$versionedProgId = (Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\CLSID\$applicationClsid\ProgID" -ErrorAction Stop).'(default)'
if ([string]::IsNullOrWhiteSpace($versionedProgId)) {
    throw "Versioned SOLIDWORKS ProgID is unavailable"
}
$registryKeys["classes-sldworks-version.reg"] = "HKLM\SOFTWARE\Classes\$versionedProgId"

$exported = @()
foreach ($entry in $registryKeys.GetEnumerator()) {
    & reg.exe query $entry.Value 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[cache] Optional registry key is absent: $($entry.Value)"
        continue
    }
    $outputPath = Join-Path $StateDirectory $entry.Key
    & reg.exe export $entry.Value $outputPath /y | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
        throw "Failed to export registry key for cache: $($entry.Value)"
    }
    $exported += [ordered]@{ key = $entry.Value; file = $entry.Key }
}

$manifest = [ordered]@{
    format = 1
    install_directory = $InstallDirectory
    solidworks_executable = $solidworksExe
    login_manager_installer = "login-manager-media\SOLIDWORKS Login Manager.msi"
    versioned_progid = $versionedProgId
    application_clsid = $applicationClsid
    registry_exports = $exported
}
$manifest | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $StateDirectory "manifest.json") -Encoding utf8
Write-Host "[cache] Prepared clean SOLIDWORKS files and registry snapshot"
