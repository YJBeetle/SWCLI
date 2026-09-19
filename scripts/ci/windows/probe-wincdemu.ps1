[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,

    [Parameter(Mandatory = $true)]
    [string]$StateDirectory
)

$ErrorActionPreference = "Stop"
$installerUri = "https://github.com/sysprogs/WinCDEmu/releases/download/v4.1/WinCDEmu-4.1.exe"
$expectedSha256 = "c47763631d20120057766f2f71f781bf958e22712da4ac933b21db0d615dc93c"

if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    throw "SOLIDWORKS ISO is unavailable: $ImagePath"
}
New-Item -ItemType Directory -Force -Path $StateDirectory | Out-Null
$installerPath = Join-Path $StateDirectory "WinCDEmu-4.1.exe"
Invoke-WebRequest -Uri $installerUri -OutFile $installerPath
$actualSha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -ne $expectedSha256) {
    throw "WinCDEmu installer SHA-256 mismatch"
}

Write-Host "[wincdemu] Installing verified WinCDEmu 4.1 package"
$install = Start-Process -FilePath $installerPath -ArgumentList "/UNATTENDED" -PassThru
if (-not $install.WaitForExit(120000)) {
    & taskkill.exe /PID $install.Id /T /F 2>$null | Out-Null
    throw "WinCDEmu unattended installation timed out"
}
if ($install.ExitCode -ne 0) {
    throw "WinCDEmu unattended installation failed with exit code $($install.ExitCode)"
}

$batchMounterCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "WinCDEmu\batchmnt.exe"),
    (Join-Path $env:ProgramFiles "WinCDEmu\batchmnt.exe")
)
$batchMounter = $batchMounterCandidates | Where-Object {
    $_ -and (Test-Path -LiteralPath $_ -PathType Leaf)
} | Select-Object -First 1
if (-not $batchMounter) {
    throw "WinCDEmu batchmnt.exe was not installed"
}

$before = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=5" | Select-Object -ExpandProperty DeviceID)
Write-Host "[wincdemu] Mounting streamed ISO through the virtual optical driver"
$mount = Start-Process -FilePath $batchMounter -ArgumentList ('"{0}"' -f $ImagePath) -Wait -PassThru
if ($mount.ExitCode -ne 0) {
    throw "WinCDEmu batchmnt failed with exit code $($mount.ExitCode)"
}

for ($attempt = 1; $attempt -le 60; $attempt++) {
    $opticalDrives = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=5")
    foreach ($drive in $opticalDrives) {
        $coreMsi = Join-Path ($drive.DeviceID + "\") "swwi\data\solidworks.msi"
        if (Test-Path -LiteralPath $coreMsi -PathType Leaf) {
            $mediaRoot = $drive.DeviceID + "\"
            [IO.File]::WriteAllText(
                (Join-Path $StateDirectory "media-root.txt"),
                $mediaRoot,
                [Text.UTF8Encoding]::new($false)
            )
            [IO.File]::WriteAllText(
                (Join-Path $StateDirectory "batchmnt-path.txt"),
                $batchMounter,
                [Text.UTF8Encoding]::new($false)
            )
            Write-Host "[wincdemu] SOLIDWORKS media is readable at $mediaRoot"
            exit 0
        }
    }
    Start-Sleep -Seconds 1
}

$after = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=5" | Select-Object -ExpandProperty DeviceID)
throw "WinCDEmu created no readable SOLIDWORKS optical volume; before=$($before -join ',') after=$($after -join ',')"
