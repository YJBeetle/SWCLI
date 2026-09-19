[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,

    [Parameter(Mandatory = $true)]
    [string]$StateDirectory,

    [ValidatePattern("^[A-Z]$")]
    [string]$DriveLetter = "S"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    throw "SOLIDWORKS ISO is unavailable: $ImagePath"
}
foreach ($commandName in @("devio.exe", "imdisk.exe")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required ImDisk command is unavailable: $commandName"
    }
}
if (Test-Path "${DriveLetter}:\") {
    throw "Drive ${DriveLetter}: is already in use"
}

New-Item -ItemType Directory -Force -Path $StateDirectory | Out-Null
$proxyName = "swcli_iso_$PID"
Write-Host "[imdisk] Starting user-mode read-only ISO proxy"
$devio = Start-Process -FilePath "devio.exe" -ArgumentList @(
    "-r", "shm:$proxyName", ('"{0}"' -f $ImagePath)
) -PassThru -WindowStyle Hidden
[IO.File]::WriteAllText(
    (Join-Path $StateDirectory "devio.pid"),
    [string]$devio.Id,
    [Text.UTF8Encoding]::new($false)
)

try {
    Start-Sleep -Seconds 2
    $devio.Refresh()
    if ($devio.HasExited) {
        throw "devio exited before ImDisk attached, code $($devio.ExitCode)"
    }

    Write-Host "[imdisk] Attaching shared-memory proxy as read-only CD-ROM"
    & imdisk.exe -a -t proxy -o "shm,ro,cd" -f $proxyName -m "${DriveLetter}:"
    if ($LASTEXITCODE -ne 0) {
        throw "imdisk attach failed with exit code $LASTEXITCODE"
    }
    [IO.File]::WriteAllText(
        (Join-Path $StateDirectory "mount-point.txt"),
        "${DriveLetter}:",
        [Text.UTF8Encoding]::new($false)
    )

    $coreMsi = "${DriveLetter}:\swwi\data\solidworks.msi"
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        if (Test-Path -LiteralPath $coreMsi -PathType Leaf) {
            $msi = Get-Item -LiteralPath $coreMsi
            Write-Host "[imdisk] SOLIDWORKS core MSI is readable ($($msi.Length) bytes)"
            exit 0
        }
        Start-Sleep -Seconds 1
    }
    throw "ImDisk optical volume did not expose the SOLIDWORKS core MSI within 60 seconds"
}
catch {
    & imdisk.exe -d -m "${DriveLetter}:" 2>$null | Out-Null
    Stop-Process -Id $devio.Id -Force -ErrorAction SilentlyContinue
    throw
}
