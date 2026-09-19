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
if (-not (Get-Command "imdisk.exe" -ErrorAction SilentlyContinue)) {
    throw "Required ImDisk command is unavailable: imdisk.exe"
}
if (Test-Path "${DriveLetter}:\") {
    throw "Drive ${DriveLetter}: is already in use"
}

New-Item -ItemType Directory -Force -Path $StateDirectory | Out-Null
$devioUri = "https://www.ltr-data.se/files/devio.exe"
$devioSha256 = "c99f78ef1896d016bc05e9f08f10122f36c2cc33f99d3f816961579d08185902"
$devioPath = Join-Path $StateDirectory "devio.exe"
Invoke-WebRequest -Uri $devioUri -OutFile $devioPath
$actualDevioSha256 = (Get-FileHash -LiteralPath $devioPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualDevioSha256 -ne $devioSha256) {
    throw "devio.exe SHA-256 mismatch"
}

$proxyName = "swcli_iso_$PID"
Write-Host "[imdisk] Starting user-mode read-only ISO proxy"
$devio = Start-Process -FilePath $devioPath -ArgumentList @(
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
            if ($env:GITHUB_ENV) {
                "SW_MEDIA_ROOT=${DriveLetter}:\" >> $env:GITHUB_ENV
            }
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
