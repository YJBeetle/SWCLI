# Test fixture only: isolate interactive startup from the optional network add-in.
# SWCLI itself never changes the human's add-in policy when attaching.
function Start-ManualTestHost {
    param([Parameter(Mandatory = $true)][string]$FilePath)

    $startupPath = 'Software\SolidWorks\AddInsStartup\{219180B0-7183-4FE2-B167-4E2BFE534004}'
    $existing = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($startupPath)
    $keyExisted = $null -ne $existing
    $hadDefault = $keyExisted -and ($existing.GetValueNames() -contains '')
    $previousValue = $null
    $previousKind = $null
    if ($hadDefault) {
        $previousValue = $existing.GetValue('', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $previousKind = $existing.GetValueKind('')
    }
    if ($keyExisted) { $existing.Close() }
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($startupPath)
    $process = $null
    $ready = $false
    try {
        # Marketplace can wait on external services before the UI is usable.
        # This gate tests core host ownership, not Marketplace sign-in/networking.
        $key.SetValue('', 0, [Microsoft.Win32.RegistryValueKind]::DWord)
        $process = Start-Process -FilePath $FilePath -PassThru
        $wait = [Diagnostics.Stopwatch]::StartNew()
        do {
            Start-Sleep -Seconds 1
            $doctor = Invoke-SwCliJson -Name "doctor-manual-host" -Arguments @("doctor", "--json")
            if ($doctor.com.attached -and $doctor.com.visible) {
                $ready = $true
                return @{ process = $process; process_id = [int]$doctor.com.process_id }
            }
        } while ($wait.Elapsed.TotalSeconds -lt 120)
        Save-DesktopDiagnostic -Name "desktop-manual-host-timeout"
        throw "manually launched SOLIDWORKS did not expose a visible interactive COM host"
    }
    finally {
        try {
            if ($hadDefault) { $key.SetValue('', $previousValue, $previousKind) }
            else { $key.DeleteValue('', $false) }
            $empty = $key.ValueCount -eq 0 -and $key.SubKeyCount -eq 0
            $key.Close()
            if (-not $keyExisted -and $empty) {
                # Only remove the fresh empty fixture key; retain any new values.
                [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($startupPath, $false)
            }
        }
        catch {
            if ($null -ne $process) { Stop-Process -InputObject $process -Force -ErrorAction SilentlyContinue }
            throw "Could not restore Marketplace startup configuration: $($_.Exception.Message)"
        }
        if (-not $ready -and $null -ne $process) {
            Stop-Process -InputObject $process -Force -ErrorAction SilentlyContinue
        }
    }
}
