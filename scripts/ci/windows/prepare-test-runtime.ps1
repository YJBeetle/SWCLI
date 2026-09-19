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

function Get-InstalledSolidWorksProcesses {
    $installPrefix = [IO.Path]::GetFullPath($solidworksDirectory).TrimEnd("\") + "\"
    $candidateNames = @("SLDWORKS.exe", "sldworks_fs.exe")
    return @(
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object { $candidateNames -contains $_.Name } |
            ForEach-Object {
                if (-not [string]::IsNullOrWhiteSpace($_.ExecutablePath)) {
                    $resolvedExecutable = (Get-Item -LiteralPath $_.ExecutablePath -ErrorAction Stop).FullName
                    if ($resolvedExecutable.StartsWith($installPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                        $_
                    }
                }
            }
    )
}

# The core MSI can leave SOLIDWORKS Fast Start resident with program DLLs
# loaded. An overlay is equivalent to a program-file patch, so wait briefly for
# natural installer teardown and then stop only the SOLIDWORKS executables from
# this exact installation directory.
for ($attempt = 1; $attempt -le 10; $attempt++) {
    $installedProcesses = @(Get-InstalledSolidWorksProcesses)
    if ($installedProcesses.Count -eq 0) { break }
    if ($attempt -eq 1) {
        $installedProcesses | Select-Object ProcessId, Name, ExecutablePath | Format-Table -AutoSize
        Write-Host "[runtime] Waiting for post-install SOLIDWORKS processes to release program files"
    }
    Start-Sleep -Seconds 1
}
$installedProcesses = @(Get-InstalledSolidWorksProcesses)
foreach ($process in $installedProcesses) {
    Write-Host "[runtime] Stopping $($process.Name) (PID $($process.ProcessId)) before overlay"
    & taskkill.exe /PID $process.ProcessId /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stop $($process.Name) before applying the private overlay"
    }
}

Write-Host "[runtime] Applying the private test-only program overlay"
$overlayApplied = $false
for ($attempt = 1; $attempt -le 5; $attempt++) {
    try {
        Copy-Item -Path (Join-Path $overlaySource "*") -Destination $solidworksDirectory -Recurse -Force
        $overlayApplied = $true
        break
    }
    catch [IO.IOException] {
        if ($attempt -eq 5) { throw }
        Write-Host "[runtime] Program file is still busy; retrying overlay ($attempt/5)"
        Start-Sleep -Seconds 2
    }
}
if (-not $overlayApplied) {
    throw "Private runtime overlay was not applied"
}

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
