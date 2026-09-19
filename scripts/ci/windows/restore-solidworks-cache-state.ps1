[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StateDirectory
)

$ErrorActionPreference = "Stop"
$manifestPath = Join-Path $StateDirectory "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "SOLIDWORKS cache manifest is missing: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($manifest.format -ne 1) {
    throw "Unsupported SOLIDWORKS cache format: $($manifest.format)"
}
if (-not (Test-Path -LiteralPath $manifest.solidworks_executable -PathType Leaf)) {
    throw "Cached SOLIDWORKS executable is missing: $($manifest.solidworks_executable)"
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
Write-Host "[cache] Restored SOLIDWORKS files and registry registration"
