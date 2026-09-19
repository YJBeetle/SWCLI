[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    throw "SOLIDWORKS ISO is unavailable: $ImagePath"
}

$sevenZip = Join-Path $env:ProgramFiles "7-Zip\7z.exe"
if (-not (Test-Path -LiteralPath $sevenZip -PathType Leaf)) {
    throw "7-Zip is unavailable: $sevenZip"
}

$item = Get-Item -LiteralPath $ImagePath
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Write-Host "[media] Reading core MSI from streamed ISO: $($item.Length) logical bytes"
& $sevenZip x "-o$OutputDirectory" -y $item.FullName "swwi\data\solidworks.msi"
if ($LASTEXITCODE -ne 0) {
    throw "7-Zip could not selectively extract the SOLIDWORKS core MSI"
}

$coreMsi = Join-Path $OutputDirectory "swwi\data\solidworks.msi"
if (-not (Test-Path -LiteralPath $coreMsi -PathType Leaf)) {
    throw "SOLIDWORKS core MSI was not extracted to $coreMsi"
}
$msi = Get-Item -LiteralPath $coreMsi
Write-Host "[media] Core MSI is readable: $($msi.FullName) ($($msi.Length) bytes)"
if ($env:GITHUB_STEP_SUMMARY) {
    @"
### Streamed SOLIDWORKS media

- ISO logical size: $([math]::Round($item.Length / 1GB, 2)) GiB
- Access method: selective 7-Zip extraction through rclone VFS
- Core MSI logical size: $([math]::Round($msi.Length / 1MB, 2)) MiB
"@ | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8
}
