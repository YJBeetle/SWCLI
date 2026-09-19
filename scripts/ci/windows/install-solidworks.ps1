[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MediaRoot,

    [Parameter(Mandatory = $true)]
    [string]$LicensingRegistryFile,

    [Parameter(Mandatory = $true)]
    [string]$LogDirectory,

    [string]$InstallDirectory = "C:\Program Files\SOLIDWORKS",

    [int]$TimeoutSeconds = 3600
)

$ErrorActionPreference = "Stop"
if ($TimeoutSeconds -le 0) {
    throw "TimeoutSeconds must be positive"
}

$coreMsi = Join-Path $MediaRoot "swwi\data\solidworks.msi"
$loginManagerMsi = Join-Path $MediaRoot "swloginmgr\SOLIDWORKS Login Manager.msi"
foreach ($requiredFile in @($coreMsi, $loginManagerMsi, $LicensingRegistryFile)) {
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
Write-Host "[install] Installing the core MSI into $InstallDirectory"
Invoke-Installer -Name "SOLIDWORKS core MSI" -FilePath "msiexec.exe" -Arguments @(
    "/i", ('"{0}"' -f $coreMsi), "/qb", "/norestart", "DISABLEROLLBACK=1",
    "ENABLEPERFORMANCE=0", "OFFICEOPTION=3", "INSTALLLEVEL=100", "ADDLOCAL=$features",
    ('INSTALLDIR="{0}"' -f $InstallDirectory),
    "TOOLBOXFOLDER=C:\SWData", "SERVERLIST=25734@127.0.0.1",
    "/l*v", ('"{0}"' -f $msiLog)
)

$solidworksExe = Join-Path $InstallDirectory "SLDWORKS.exe"
if (-not (Test-Path -LiteralPath $solidworksExe -PathType Leaf)) {
    throw "SOLIDWORKS MSI completed but the expected executable is missing: $solidworksExe"
}

$progid = Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\SldWorks.Application\CLSID" -ErrorAction Stop
$applicationClsid = $progid.'(default)'
if ([string]::IsNullOrWhiteSpace($applicationClsid)) {
    throw "SOLIDWORKS MSI did not register SldWorks.Application"
}
$server = Get-ItemProperty -Path "Registry::HKEY_CLASSES_ROOT\CLSID\$applicationClsid\LocalServer32" -ErrorAction Stop
$serverCommand = [string]$server.'(default)'
$serverMatch = [regex]::Match(
    $serverCommand,
    '^\s*"(?<quoted>[^"]+SLDWORKS\.exe)"|^\s*(?<plain>.+?SLDWORKS\.exe)',
    'IgnoreCase'
)
if (-not $serverMatch.Success) {
    throw "SOLIDWORKS COM LocalServer32 does not point to SLDWORKS.exe"
}
$registeredExe = if ($serverMatch.Groups['quoted'].Success) {
    $serverMatch.Groups['quoted'].Value
} else {
    $serverMatch.Groups['plain'].Value
}
$registeredItem = Get-Item -LiteralPath $registeredExe -ErrorAction Stop
$expectedItem = Get-Item -LiteralPath $solidworksExe -ErrorAction Stop
if ($registeredItem.FullName -ne $expectedItem.FullName) {
    throw "SOLIDWORKS COM registration points to an unexpected installation: $registeredExe"
}
Write-Host "[install] Verified native SOLIDWORKS COM registration"
