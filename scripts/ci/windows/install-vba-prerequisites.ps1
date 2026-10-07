[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VbaSourceDirectory,

    [Parameter(Mandatory = $true)]
    [string]$LogDirectory,

    [Parameter(Mandatory = $true)]
    [string]$InventoryPath,

    [int]$TimeoutSeconds = 3600
)

$ErrorActionPreference = "Stop"
if ($TimeoutSeconds -le 0) {
    throw "TimeoutSeconds must be positive"
}

function Write-VbaInventory {
    $registryErrors = @()
    # Reading Installer registration does not trigger product repair. Only emit
    # the VBA product name/version/key, never the complete registry properties.
    $products = @(
        Get-ItemProperty -Path (
            "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\" +
            "UserData\S-1-5-18\Products\*\InstallProperties"
        ) -ErrorAction SilentlyContinue -ErrorVariable registryErrors |
            Where-Object { $_.DisplayName -match '(?i)\b(VBA|Visual Basic for Applications)\b' } |
            ForEach-Object {
                [ordered]@{
                    name = [string]$_.DisplayName
                    version = [string]$_.DisplayVersion
                    product_key = Split-Path (Split-Path $_.PSPath -Parent) -Leaf
                }
            }
    )
    $commonFiles = $env:CommonProgramW6432
    if ([string]::IsNullOrWhiteSpace($commonFiles)) { $commonFiles = $env:CommonProgramFiles }
    if ([string]::IsNullOrWhiteSpace($commonFiles)) {
        throw "The native Common Files directory is unavailable for VBA inventory"
    }
    $runtimeDirectory = Join-Path $commonFiles "Microsoft Shared\VBA\VBA7.1"
    $dlls = @(
        foreach ($relativePath in @("VBE7.DLL", "1033\VBE7INTL.DLL")) {
            $dllPath = Join-Path $runtimeDirectory $relativePath
            $exists = Test-Path -LiteralPath $dllPath -PathType Leaf
            [ordered]@{
                relative_path = $relativePath
                exists = $exists
                version = if ($exists) { (Get-Item -LiteralPath $dllPath).VersionInfo.FileVersion } else { $null }
            }
        }
    )
    $inventory = [ordered]@{
        format = 1
        runtime_directory = $runtimeDirectory
        msi_inventory_complete = ($registryErrors.Count -eq 0)
        products = $products
        dlls = $dlls
        # Presence/registration is evidence, not proof that SW initialized VBA.
        solidworks_vba_initialization_verified = $false
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $InventoryPath -Parent) | Out-Null
    $inventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $InventoryPath -Encoding utf8
    Write-Host "[install] Recorded non-sensitive VBA runtime inventory"
    return $inventory
}

$installationError = $null
try {
    # Validate both packages before running either one. Preserve the complete
    # official directory layout so external CAB payloads remain resolvable.
    $packages = @("vba71.msi", "vba71_1033.msi")
    foreach ($package in $packages) {
        $packagePath = Join-Path $VbaSourceDirectory $package
        if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
            throw "Official VBA prerequisite is unavailable: $packagePath"
        }
    }
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
    foreach ($package in $packages) {
        $packagePath = Join-Path $VbaSourceDirectory $package
        $logPath = Join-Path $LogDirectory ($package.Replace(".msi", "-install.log"))
        Write-Host "[install] Installing official VBA prerequisite $package"
        $process = Start-Process -FilePath "msiexec.exe" -ArgumentList @(
            "/i", ('"{0}"' -f $packagePath), "/qn", "/norestart", "DISABLEROLLBACK=1",
            "/l*v", ('"{0}"' -f $logPath)
        ) -PassThru
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
            throw "$package timed out after $TimeoutSeconds seconds; installer log: $logPath"
        }
        if (@(0, 1641, 3010) -notcontains $process.ExitCode) {
            throw "$package failed with exit code $($process.ExitCode); installer log: $logPath"
        }
    }
} catch {
    $installationError = $_
}

try {
    $inventory = Write-VbaInventory
} catch {
    if ($null -eq $installationError) { throw }
    Write-Warning "VBA inventory could not be written; the original installation failure is retained"
}
if ($null -ne $installationError) { throw $installationError }
$missingDlls = @($inventory.dlls | Where-Object { -not $_.exists } | ForEach-Object { $_.relative_path })
if ($missingDlls.Count -ne 0) {
    throw "VBA installation completed but required runtime DLLs are missing: $($missingDlls -join ', '); inventory: $InventoryPath"
}
