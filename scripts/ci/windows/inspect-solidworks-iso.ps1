[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    throw "SOLIDWORKS ISO is unavailable: $ImagePath"
}

$image = $null
try {
    $item = Get-Item -LiteralPath $ImagePath
    Write-Host "[media] Streaming ISO: $($item.FullName) ($($item.Length) bytes logical size)"
    $image = Mount-DiskImage -ImagePath $item.FullName -StorageType ISO -PassThru
    $volume = $image | Get-Volume
    if (-not $volume.DriveLetter) {
        throw "Mounted ISO has no drive letter"
    }
    $mediaRoot = "$($volume.DriveLetter):\"
    $coreMsi = Join-Path $mediaRoot "swwi\data\solidworks.msi"
    if (-not (Test-Path -LiteralPath $coreMsi -PathType Leaf)) {
        throw "SOLIDWORKS core MSI was not found at $coreMsi"
    }
    $msi = Get-Item -LiteralPath $coreMsi
    Write-Host "[media] Core MSI is readable: $($msi.FullName) ($($msi.Length) bytes)"
    if ($env:GITHUB_STEP_SUMMARY) {
        @"
### Streamed SOLIDWORKS media

- ISO logical size: $([math]::Round($item.Length / 1GB, 2)) GiB
- Mounted volume: $mediaRoot
- Core MSI: $($msi.FullName)
- Core MSI logical size: $([math]::Round($msi.Length / 1MB, 2)) MiB
"@ | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8
    }
}
finally {
    if ($null -ne $image) {
        Dismount-DiskImage -ImagePath $ImagePath -ErrorAction SilentlyContinue
    }
}
