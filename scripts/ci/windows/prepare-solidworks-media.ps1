[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,

    [Parameter(Mandatory = $true)]
    [string]$Destination
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
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Write-Host "[media] Selectively extracting native installer payload from $($item.Length) logical bytes"
& $sevenZip x "-o$Destination" -y $item.FullName `
    "swwi\data\*" `
    "PreReqs\VCRedist17\*" `
    "swloginmgr\*"
if ($LASTEXITCODE -ne 0) {
    throw "7-Zip could not prepare the selected SOLIDWORKS installer payload"
}

foreach ($requiredFile in @(
    (Join-Path $Destination "swwi\data\solidworks.msi"),
    (Join-Path $Destination "PreReqs\VCRedist17\VC_redist.x64.exe"),
    (Join-Path $Destination "swloginmgr\SOLIDWORKS Login Manager.msi")
)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Selected SOLIDWORKS installer payload is incomplete: $requiredFile"
    }
}

if ($env:GITHUB_ENV) {
    "SW_MEDIA_ROOT=$Destination" >> $env:GITHUB_ENV
}
Write-Host "[media] Selected native installer payload is ready at $Destination"
