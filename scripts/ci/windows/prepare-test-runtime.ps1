[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AssetsRoot,

    [Parameter(Mandatory = $true)]
    [string]$StateDirectory
)

$ErrorActionPreference = "Stop"
$registryFile = Join-Path $AssetsRoot "sw2025_network_serials_licensing.reg"
$overlaySource = Join-Path $AssetsRoot "SOLIDWORKS Corp\SOLIDWORKS"
$flexnetRoot = Join-Path $AssetsRoot "SolidWorks_Flexnet_Server"
foreach ($requiredPath in @($registryFile, $overlaySource, $flexnetRoot)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required private smoke-test input is unavailable: $requiredPath"
    }
}

$progid = Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\SldWorks.Application\CLSID" -ErrorAction Stop
$applicationClsid = $progid.'(default)'
$server = Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\CLSID\$applicationClsid\LocalServer32" -ErrorAction Stop
$serverCommand = [string]$server.'(default)'
$match = [regex]::Match($serverCommand, '^\s*"(?<quoted>[^"]+SLDWORKS\.exe)"|^\s*(?<plain>.+?SLDWORKS\.exe)', 'IgnoreCase')
if (-not $match.Success) {
    throw "Cannot resolve SLDWORKS.exe from LocalServer32"
}
$solidworksExe = if ($match.Groups['quoted'].Success) { $match.Groups['quoted'].Value } else { $match.Groups['plain'].Value }
$solidworksDirectory = Split-Path -Parent $solidworksExe
if (-not (Test-Path -LiteralPath $solidworksExe -PathType Leaf)) {
    throw "Registered SLDWORKS.exe is unavailable: $solidworksExe"
}

Write-Host "[runtime] Applying the private test-only program overlay"
Copy-Item -Path (Join-Path $overlaySource "*") -Destination $solidworksDirectory -Recurse -Force

$registryProcess = Start-Process -FilePath "reg.exe" -ArgumentList @(
    "import", ('"{0}"' -f $registryFile)
) -Wait -PassThru -WindowStyle Hidden
if ($registryProcess.ExitCode -ne 0) {
    throw "Private licensing registry import failed with exit code $($registryProcess.ExitCode)"
}

$licenseFile = Get-ChildItem -LiteralPath $flexnetRoot -Filter "*.lic" -File | Select-Object -First 1
$lmgrd = Join-Path $flexnetRoot "lmgrd.exe"
$lmutil = Join-Path $flexnetRoot "lmutil.exe"
foreach ($requiredFile in @($lmgrd, $lmutil, $licenseFile.FullName)) {
    if (-not $requiredFile -or -not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required private FlexNet input is unavailable: $requiredFile"
    }
}

New-Item -ItemType Directory -Force -Path $StateDirectory | Out-Null
$licenseLog = Join-Path $StateDirectory "flexnet-private.log"
$licenseProcess = Start-Process -FilePath $lmgrd -WorkingDirectory $flexnetRoot -ArgumentList @(
    "-c", ('"{0}"' -f $licenseFile.FullName), "-l", ('"{0}"' -f $licenseLog)
) -WindowStyle Hidden -PassThru
[IO.File]::WriteAllText((Join-Path $StateDirectory "lmgrd.pid"), [string]$licenseProcess.Id, [Text.UTF8Encoding]::new($false))

$licenseAddress = "25734@127.0.0.1"
New-Item -Path "HKCU:\SOFTWARE\FLEXlm License Manager" -Force | Out-Null
New-ItemProperty -Path "HKCU:\SOFTWARE\FLEXlm License Manager" -Name "SW_D_LICENSE_FILE" -Value $licenseAddress -PropertyType String -Force | Out-Null
New-Item -Path "HKLM:\SOFTWARE\FLEXlm License Manager" -Force | Out-Null
New-ItemProperty -Path "HKLM:\SOFTWARE\FLEXlm License Manager" -Name "SW_D_LICENSE_FILE" -Value $licenseAddress -PropertyType String -Force | Out-Null
if ($env:GITHUB_ENV) {
    "SOLIDWORKS_LICENSE_FILE=$licenseAddress" >> $env:GITHUB_ENV
    "SW_D_LICENSE_FILE=$licenseAddress" >> $env:GITHUB_ENV
}

$ready = $false
for ($attempt = 1; $attempt -le 60; $attempt++) {
    $probe = Start-Process -FilePath $lmutil -ArgumentList @("lmstat", "-a", "-c", $licenseAddress) -Wait -PassThru -WindowStyle Hidden
    if ($probe.ExitCode -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    throw "Private FlexNet service did not become ready within 60 seconds"
}
Write-Host "[runtime] Private test license service is ready"
