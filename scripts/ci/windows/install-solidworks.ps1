[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MediaRoot,

    [Parameter(Mandatory = $true)]
    [string]$LicensingRegistryFile,

    [Parameter(Mandatory = $true)]
    [string]$LogDirectory,

    [int]$TimeoutSeconds = 3600
)

$ErrorActionPreference = "Stop"
if ($TimeoutSeconds -le 0) {
    throw "TimeoutSeconds must be positive"
}

$coreMsi = Join-Path $MediaRoot "swwi\data\solidworks.msi"
$vcInstaller = Join-Path $MediaRoot "PreReqs\VCRedist17\VC_redist.x64.exe"
$loginManagerMsi = Join-Path $MediaRoot "swloginmgr\SOLIDWORKS Login Manager.msi"
foreach ($requiredFile in @($coreMsi, $vcInstaller, $loginManagerMsi, $LicensingRegistryFile)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required private installation input is unavailable: $requiredFile"
    }
}
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null

function Invoke-Installer {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [int[]]$SuccessCodes = @(0, 1641, 3010)
    )

    Write-Host "[install] Running $Name"
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        throw "$Name timed out after $TimeoutSeconds seconds"
    }
    if ($SuccessCodes -notcontains $process.ExitCode) {
        throw "$Name failed with exit code $($process.ExitCode); protected logs remain on the disposable runner only"
    }
}

function Get-MsiProductVersion {
    param([Parameter(Mandatory = $true)][string]$Path)

    $installer = New-Object -ComObject WindowsInstaller.Installer
    $database = $installer.OpenDatabase($Path, 0)
    $view = $database.OpenView("SELECT ``Value`` FROM ``Property`` WHERE ``Property``='ProductVersion'")
    $view.Execute()
    $record = $view.Fetch()
    if ($null -eq $record) {
        throw "SOLIDWORKS MSI has no ProductVersion"
    }
    return [string]$record.StringData(1)
}

$productVersion = Get-MsiProductVersion -Path $coreMsi
$versionParts = $productVersion.Split(".")
if ($versionParts.Count -lt 2) {
    throw "Unsupported SOLIDWORKS ProductVersion: $productVersion"
}
$productYear = [int]$versionParts[0] + 1992
$servicePackCode = [int]$versionParts[1] - 100
if ($productYear -lt 2000 -or $productYear -gt 2100 -or $servicePackCode -lt 0 -or $servicePackCode -gt 99) {
    throw "Unsupported SOLIDWORKS ProductVersion: $productVersion"
}
$servicePack = "{0}.{1}" -f [math]::Floor($servicePackCode / 10), ($servicePackCode % 10)
$eulaKey = "HKCU:\Software\SolidWorks\IM\$productYear\Setup"
New-Item -Path $eulaKey -Force | Out-Null
New-ItemProperty -Path $eulaKey -Name "EULA Accepted SP$servicePack" -PropertyType DWord -Value 1 -Force | Out-Null
Write-Host "[install] Recorded EULA acceptance for SOLIDWORKS $productYear SP$servicePack"

$vcLog = Join-Path $LogDirectory "vcredist-x64.log"
Invoke-Installer -Name "Microsoft VC++ x64 prerequisite" -FilePath $vcInstaller -Arguments @(
    "/install", "/quiet", "/norestart", "/log", ('"{0}"' -f $vcLog)
) -SuccessCodes @(0, 1638, 1641, 3010)

$loginLog = Join-Path $LogDirectory "login-manager-install.log"
Invoke-Installer -Name "SOLIDWORKS Login Manager" -FilePath "msiexec.exe" -Arguments @(
    "/i", ('"{0}"' -f $loginManagerMsi), "/qn", "/norestart", "DISABLEROLLBACK=1",
    "/l*v", ('"{0}"' -f $loginLog)
)

Write-Host "[install] Importing private network-serial settings before MSI AppSearch"
$registryProcess = Start-Process -FilePath "reg.exe" -ArgumentList @(
    "import", ('"{0}"' -f $LicensingRegistryFile)
) -Wait -PassThru -WindowStyle Hidden
if ($registryProcess.ExitCode -ne 0) {
    throw "Private licensing registry import failed with exit code $($registryProcess.ExitCode)"
}

$msiLog = Join-Path $LogDirectory "solidworks-msi.log"
$features = "SolidWorks,ProgramFiles,i386_ProgramFiles,i386_ThirdPtyFiles,i386_DCubeFiles,i386_SWFiles,i386_VistaFiles"
Invoke-Installer -Name "SOLIDWORKS core MSI" -FilePath "msiexec.exe" -Arguments @(
    "/i", ('"{0}"' -f $coreMsi), "/qb", "/norestart", "DISABLEROLLBACK=1",
    "ENABLEPERFORMANCE=0", "OFFICEOPTION=3", "INSTALLLEVEL=100", "ADDLOCAL=$features",
    "TOOLBOXFOLDER=C:\SWData", "SERVERLIST=25734@127.0.0.1",
    "/l*v", ('"{0}"' -f $msiLog)
)

$progid = Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\SldWorks.Application\CLSID" -ErrorAction Stop
$applicationClsid = $progid.'(default)'
if ([string]::IsNullOrWhiteSpace($applicationClsid)) {
    throw "SOLIDWORKS MSI did not register SldWorks.Application"
}
$server = Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\CLSID\$applicationClsid\LocalServer32" -ErrorAction Stop
$serverCommand = [string]$server.'(default)'
if ($serverCommand -notmatch '(?i)SLDWORKS\.exe') {
    throw "SOLIDWORKS COM LocalServer32 does not point to SLDWORKS.exe"
}
Write-Host "[install] Verified native SOLIDWORKS COM registration"
