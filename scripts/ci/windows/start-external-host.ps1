# Test-only COM owner, independent of SWCLI and the attached daemon.
function Start-ExternalTestHost {
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count) {
        throw 'External host fixture requires no existing SOLIDWORKS process'
    }
    $stdout = Join-Path $Workspace 'external-host.jsonl'
    $stderr = Join-Path $Workspace 'external-host.stderr.log'
    $script = Join-Path $PSScriptRoot 'create-external-host.py'
    $process = Start-Process -FilePath (Get-Command python).Source `
        -ArgumentList @('-I', ('"' + $script + '"')) `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -PassThru
    $ready = $false
    $pidAcquired = $null
    try {
        $wait = [Diagnostics.Stopwatch]::StartNew()
        while (-not $process.HasExited) {
            if (Test-Path -LiteralPath $stdout) {
                foreach ($line in @(Get-Content -LiteralPath $stdout -Encoding utf8)) {
                    if (-not $line.Trim()) { continue }
                    try { $event = $line | ConvertFrom-Json } catch { continue }
                    if ($event.phase -eq 'host-acquired') { $pidAcquired = [int]$event.process_id }
                }
            }
            if ($wait.Elapsed.TotalSeconds -ge 135) {
                throw 'External COM host fixture exceeded 135 seconds'
            }
            Start-Sleep -Milliseconds 200
            $process.Refresh()
        }
        $process.WaitForExit()
        $process.Refresh()
        $events = @(Get-Content -LiteralPath $stdout -Encoding utf8 | ForEach-Object { $_ | ConvertFrom-Json })
        $acquired = @($events | Where-Object phase -eq 'host-acquired')
        if ($acquired.Count -eq 1) { $pidAcquired = [int]$acquired[0].process_id }
        $hostReady = @($events | Where-Object phase -eq 'ready')
        if ($process.ExitCode -ne 0 -or $hostReady.Count -ne 1) {
            throw "External COM host fixture failed: $(Get-Content -LiteralPath $stderr -Raw)"
        }
        $hostPid = [int]$hostReady[0].process_id
        $doctor = Invoke-SwCliJson -Name 'doctor-external-host' -Arguments @('doctor', '--json')
        if ($hostPid -ne $pidAcquired -or -not $doctor.com.attached -or
            -not $doctor.com.visible -or $doctor.com.process_id -ne $hostPid -or
            $null -eq (Get-Process -Id $hostPid -ErrorAction SilentlyContinue)) {
            throw 'External visible host did not survive fixture process exit'
        }
        $ready = $true
        return @{ process_id = $hostPid }
    }
    finally {
        if (-not $ready) {
            Save-DesktopDiagnostic -Name 'desktop-external-host-failure'
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            if ($null -ne $pidAcquired) {
                Stop-Process -Id $pidAcquired -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
