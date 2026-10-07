[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,
    [switch]$Hidden
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
$partPath = Join-Path $Workspace "swcli-box-100x50x20.SLDPRT"
$stepPath = Join-Path $Workspace "swcli-box-100x50x20.STEP"
$renderPath = Join-Path $Workspace "swcli-box-isometric-800x600.bmp"
$genericPartPath = Join-Path $Workspace "modeling\model.SLDPRT"

function Save-DesktopDiagnostic {
    param([Parameter(Mandatory = $true)][string]$Name)

    $screenshotPath = Join-Path $Workspace "$Name.png"
    $windowsPath = Join-Path $Workspace "$Name-windows.json"
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
        if ($bounds.Width -le 0 -or $bounds.Height -le 0) {
            throw "Interactive desktop has invalid dimensions: $($bounds.Width)x$($bounds.Height)"
        }
        $bitmap = $null
        $graphics = $null
        try {
            $bitmap = [System.Drawing.Bitmap]::new([int]$bounds.Width, [int]$bounds.Height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bounds.Size)
            $bitmap.Save($screenshotPath, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            if ($null -ne $graphics) { $graphics.Dispose() }
            if ($null -ne $bitmap) { $bitmap.Dispose() }
        }
    }
    catch {
        $_ | Out-String | Set-Content -Path (Join-Path $Workspace "$Name-screenshot-error.txt") -Encoding utf8
    }

    try {
        $visibleWindows = @(
            Get-Process -ErrorAction SilentlyContinue |
                Where-Object { $_.MainWindowHandle -ne 0 } |
                Sort-Object ProcessName, Id |
                Select-Object Id, ProcessName, MainWindowTitle
        )
        ConvertTo-Json -InputObject $visibleWindows -Depth 3 |
            Set-Content -Path $windowsPath -Encoding utf8
    }
    catch {
        $_ | Out-String | Set-Content -Path (Join-Path $Workspace "$Name-windows-error.txt") -Encoding utf8
    }
}

function Invoke-SwCliJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$AllowFailure
    )
    $outputPath = Join-Path $Workspace "$Name.json"
    $stderrPath = Join-Path $Workspace "$Name.stderr.log"
    $python = (Get-Command python -ErrorAction Stop).Source
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList (@("-m", "swcli", "--request-timeout", "120") + $Arguments) `
        -RedirectStandardOutput $outputPath `
        -RedirectStandardError $stderrPath `
        -NoNewWindow `
        -PassThru
    $startedAt = Get-Date
    $captured = @{}
    while (-not $process.HasExited) {
        $elapsedSeconds = [int][Math]::Floor(((Get-Date) - $startedAt).TotalSeconds)
        foreach ($threshold in @(15, 60, 110)) {
            if ($elapsedSeconds -ge $threshold -and -not $captured.ContainsKey($threshold)) {
                Save-DesktopDiagnostic -Name ("desktop-{0}-wait-{1:D3}" -f $Name, $threshold)
                $captured[$threshold] = $true
            }
        }
        if ($elapsedSeconds -ge 135) {
            Save-DesktopDiagnostic -Name ("desktop-{0}-timeout" -f $Name)
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "sw-cli $Name did not exit within 135 seconds"
        }
        Start-Sleep -Seconds 1
        $process.Refresh()
    }
    # With redirected streams, WaitForExit() is still required after HasExited
    # becomes true so PowerShell populates ExitCode and flushes both files.
    $process.WaitForExit()
    $process.Refresh()
    if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf) -or
        (Get-Item -LiteralPath $outputPath).Length -eq 0) {
        $stderr = Get-Content $stderrPath -Raw -ErrorAction SilentlyContinue
        throw "sw-cli $Name exited without a JSON result (exit code $($process.ExitCode))`n$stderr"
    }
    try {
        $payload = Get-Content $outputPath -Raw -Encoding utf8 | ConvertFrom-Json
    }
    catch {
        $stderr = Get-Content $stderrPath -Raw -ErrorAction SilentlyContinue
        throw "sw-cli $Name returned invalid JSON (exit code $($process.ExitCode))`n$stderr"
    }
    if (-not $AllowFailure -and
        $payload.PSObject.Properties.Name -contains "ok" -and
        -not $payload.ok) {
        $errorType = if ($null -ne $payload.error.type) {
            [string]$payload.error.type
        }
        else {
            "UnknownError"
        }
        $errorMessage = if ($null -ne $payload.error.message) {
            [string]$payload.error.message
        }
        else {
            "no error message"
        }
        $requestId = if ($null -ne $payload.request_id) {
            " [request_id=$($payload.request_id)]"
        }
        else {
            ""
        }
        throw "sw-cli $Name returned ok=false: ${errorType}: ${errorMessage}${requestId}"
    }
    if (-not $AllowFailure -and
        $null -ne $process.ExitCode -and
        $process.ExitCode -ne 0) {
        $stderr = Get-Content $stderrPath -Raw -ErrorAction SilentlyContinue
        throw "sw-cli $Name failed with exit code $($process.ExitCode)`n$stderr"
    }
    return $payload
}

function Wait-DisconnectedHost {
    param([Parameter(Mandatory = $true)][string]$Name)

    $wait = [Diagnostics.Stopwatch]::StartNew()
    $attempt = 0
    do {
        Start-Sleep -Milliseconds 200
        $attempt++
        $status = Invoke-SwCliJson -Name ("{0}-{1:D2}" -f $Name, $attempt) -Arguments @("daemon", "status", "--json")
        if (-not $status.result.host_connected) {
            if ($null -ne $status.result.host -or
                -not $status.result.recovery_required -or
                $status.result.recovery_error.code -ne "HostDisconnected") {
                throw "swclid returned an inconsistent disconnected host state"
            }
            # host_connected is the COM truth; worker_alive remains true while
            # Python releases native handles and finishes process teardown.
            if (-not $status.result.worker_alive) { return $status }
        }
    } while ($wait.Elapsed.TotalSeconds -lt 10)
    throw "swclid did not report host disconnect and finish worker teardown within 10 seconds"
}

Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Save-DesktopDiagnostic -Name "desktop-before-swclid"

$python = (Get-Command python -ErrorAction Stop).Source
$daemonStdout = Join-Path $Workspace "swclid.stdout.log"
$daemonStderr = Join-Path $Workspace "swclid.stderr.log"
$daemonArguments = @("-m", "swcli", "daemon", "serve", "--startup-timeout", "120")
if (-not $Hidden) { $daemonArguments += "--visible" }
$daemon = Start-Process `
    -FilePath $python `
    -ArgumentList $daemonArguments `
    -RedirectStandardOutput $daemonStdout `
    -RedirectStandardError $daemonStderr `
    -NoNewWindow `
    -PassThru
[IO.File]::WriteAllText(
    (Join-Path $Workspace "swclid.pid"),
    [string]$daemon.Id,
    [Text.UTF8Encoding]::new($false)
)

$daemonReady = $false
for ($attempt = 1; $attempt -le 180; $attempt++) {
    $daemon.Refresh()
    if ($daemon.HasExited) {
        Save-DesktopDiagnostic -Name "desktop-swclid-exited"
        $stderr = Get-Content $daemonStderr -Raw -ErrorAction SilentlyContinue
        throw "swclid exited during startup with code $($daemon.ExitCode)`n$stderr"
    }
    if ((Test-Path -LiteralPath $daemonStdout) -and
        (Select-String -LiteralPath $daemonStdout -SimpleMatch '"action": "daemon.serve"' -Quiet)) {
        $daemonReady = $true
        break
    }
    if ($attempt -in @(30, 90, 150)) {
        Save-DesktopDiagnostic -Name ("desktop-swclid-wait-{0:D3}" -f $attempt)
    }
    Start-Sleep -Seconds 1
}
if (-not $daemonReady) {
    Save-DesktopDiagnostic -Name "desktop-swclid-timeout"
    throw "swclid did not become ready within 180 seconds"
}
Save-DesktopDiagnostic -Name "desktop-swclid-ready"

$started = $true
$attachedStarted = $false
$externalPid = $null
try {
    $doctor = Invoke-SwCliJson -Name "doctor-before" -Arguments @("doctor", "--json")
    if (-not $doctor.supported) {
        throw "SWCLI does not recognize this runner as a supported Windows host"
    }
    if (-not $doctor.registration.local_server_exists) {
        throw "SOLIDWORKS LocalServer32 registration is missing or points to a missing executable"
    }
    if (-not $doctor.daemon.reachable) {
        throw "swclid is not reachable after startup"
    }

    Invoke-SwCliJson -Name "capabilities" -Arguments @("capabilities", "--json") | Out-Null
    & python (Join-Path $PSScriptRoot "../verify-invalid-requests.py")
    if ($LASTEXITCODE -ne 0) { throw "invalid wire requests changed the running host or documents" }

    $beforeInvalidRestart = Invoke-SwCliJson -Name "status-before-invalid-restart" -Arguments @("daemon", "status", "--json")
    $invalidRestart = Invoke-SwCliJson -Name "invalid-restart-timeout" -AllowFailure -Arguments @(
        "daemon", "restart", "--startup-timeout", "nan", "--json"
    )
    if ($invalidRestart.success -or $invalidRestart.error.code -ne "InvalidTimeout") {
        throw "invalid restart timeout was not rejected before host shutdown"
    }
    $afterInvalidRestart = Invoke-SwCliJson -Name "status-after-invalid-restart" -Arguments @("daemon", "status", "--json")
    if (-not $afterInvalidRestart.result.host_connected -or
        $afterInvalidRestart.result.host.process_id -ne $beforeInvalidRestart.result.host.process_id) {
        throw "invalid restart parameters stopped or replaced the running SOLIDWORKS host"
    }

    # Shared public modeling assertions live in SWCLI, not this host wrapper.
    # A native cut rejection must precede the driving gate in the SAME daemon.
    $installation = @($doctor.installations | Where-Object { $_.year -eq 2025 }) | Select-Object -First 1
    if ($null -eq $installation) { throw "SOLIDWORKS 2025 installation path is unavailable" }
    $modelingFolder = Join-Path $Workspace "modeling"
    $samplePart = Join-Path $env:PUBLIC "Documents\SOLIDWORKS\SOLIDWORKS 2025\samples\learn\Paper Airplane.SLDPRT"
    $sampleAssembly = Join-Path $installation.install_dir "sldBenchmarking\Macro\Mold\bezel moldbase.sldasm"
    & python -I (Join-Path $PSScriptRoot "../verify-modeling.py") `
        --output-dir $modelingFolder `
        --sample-part $samplePart --sample-assembly $sampleAssembly
    if ($LASTEXITCODE -ne 0) { throw "shared modeling CLI gate failed" }
    & python -I (Join-Path $PSScriptRoot "../verify-driving-dimensions.py") `
        --output-dir (Join-Path $Workspace "driving-dimensions") `
        --after-modeling (Join-Path $modelingFolder "modeling.json")
    if ($LASTEXITCODE -ne 0) { throw "driving-dimension CLI/protocol gate failed" }
    # This Windows-only fixture bootstraps an equation via the existing ROT
    # host. Hidden background hosts need not register there; do not Dispatch
    # another instance or make them visible to prepare the fixture.
    if (-not $Hidden) {
        & python -I (Join-Path $PSScriptRoot "verify-equation-dimension.py") `
            --output-dir (Join-Path $Workspace "equation-dimension")
        if ($LASTEXITCODE -ne 0) { throw "equation-owned dimension protection gate failed" }
    }
    else { Write-Host "[gate] Native equation ROT fixture remains mandatory in the visible run" }

    $created = Invoke-SwCliJson -Name "part-create-box" -Arguments @(
        "part", "create-box", $partPath,
        "--width-mm", "100", "--height-mm", "50", "--depth-mm", "20", "--json"
    )
    Invoke-SwCliJson -Name "document-list" -Arguments @("document", "list", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-use" -Arguments @("document", "use", $created.document.document_id, "--json") | Out-Null
    Invoke-SwCliJson -Name "document-inspect" -Arguments @("document", "inspect", "--detail", "structure", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-diagnose" -Arguments @("document", "diagnose", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-rebuild" -Arguments @("document", "rebuild", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-save" -Arguments @("document", "save", "--json") | Out-Null
    $lease = Invoke-SwCliJson -Name "lease-acquire" -Arguments @("document", "lease", "acquire", "--json")
    Invoke-SwCliJson -Name "lease-status" -Arguments @("document", "lease", "status", "--json") | Out-Null
    Invoke-SwCliJson -Name "lease-renew" -Arguments @("document", "lease", "renew", $lease.lease.lease_id, "--json") | Out-Null
    Invoke-SwCliJson -Name "document-render" -Arguments @(
        "document", "render", $renderPath,
        "--lease", $lease.lease.lease_id,
        "--view", "isometric", "--width", "800", "--height", "600", "--json"
    ) | Out-Null
    Invoke-SwCliJson -Name "document-export" -Arguments @("document", "export", $stepPath, "--lease", $lease.lease.lease_id, "--json") | Out-Null
    Invoke-SwCliJson -Name "lease-release" -Arguments @("document", "lease", "release", $lease.lease.lease_id, "--json") | Out-Null
    Invoke-SwCliJson -Name "document-close" -Arguments @("document", "close", "--discard", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-open" -Arguments @("document", "open", $partPath, "--read-only", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-close-reopened" -Arguments @("document", "close", "--discard", "--json") | Out-Null

    # The public example is executable product documentation, not COM test code.
    $exampleFolder = Join-Path $Workspace "plate-example"
    New-Item -ItemType Directory -Path $exampleFolder | Out-Null
    $unicodeFolder = Join-Path $exampleFolder ([string][char]0x4E2D + [char]0x6587)
    New-Item -ItemType Directory -Path $unicodeFolder | Out-Null
    $example = Join-Path $PSScriptRoot "../../../examples/model-plate.ps1"
    $previousEncoding = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [Text.Encoding]::GetEncoding(936)
        & $example -OutputDirectory $unicodeFolder |
            Set-Content (Join-Path $exampleFolder "result.json") -Encoding utf8
        if ([Console]::OutputEncoding.CodePage -ne 936) {
            throw "the product example changed its caller's console encoding"
        }
    }
    finally { [Console]::OutputEncoding = $previousEncoding }

    $connected = Invoke-SwCliJson -Name "daemon-connected" -Arguments @("daemon", "status", "--json")
    if (-not $connected.result.host_connected) {
        throw "swclid did not report its SOLIDWORKS host as connected"
    }
    $solidworksPid = [int]$connected.result.host.process_id
    Stop-Process -Id $solidworksPid -Force -ErrorAction Stop

    Wait-DisconnectedHost -Name "daemon-disconnected" | Out-Null

    $blocked = Invoke-SwCliJson `
        -Name "document-list-after-host-exit" `
        -Arguments @("document", "list", "--json") `
        -AllowFailure
    if ($blocked.ok -or $blocked.error.type -ne "HostDisconnected") {
        throw "a business request was not blocked after SOLIDWORKS disconnected"
    }
    Start-Sleep -Seconds 1
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw "a business request silently restarted SOLIDWORKS after disconnect"
    }

    $stopped = Invoke-SwCliJson -Name "swclid-stop" -Arguments @("daemon", "stop", "--json")
    if (-not $stopped.success -or
        -not $stopped.result.host_already_disconnected) {
        throw "swclid did not stop cleanly after its host disconnected"
    }
    if (-not $daemon.WaitForExit(30000)) {
        throw "swclid did not exit within 30 seconds after shutdown"
    }
    $started = $false

    # An explicitly attached instance belongs to the human, not the daemon.
    $missingHost = Invoke-SwCliJson -Name "attach-without-host" -AllowFailure -Arguments @(
        "daemon", "start", "--attach-existing", "--json"
    )
    if ($missingHost.success -or $missingHost.error.code -ne "ExistingHostNotFound" -or
        @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw "attach-existing without a host created an owned instance or did not fail explicitly"
    }

    . (Join-Path $PSScriptRoot "start-external-host.ps1")
    $external = Start-ExternalTestHost
    $externalPid = $external.process_id
    $attachedStarted = $true
    $attached = Invoke-SwCliJson -Name "attach-external-host" -Arguments @("daemon", "start", "--attach-existing", "--json")
    $attachedHost = $attached.result.health.host
    if ($attachedHost.owned_by_daemon -or -not $attachedHost.shared_interactive -or
        $attachedHost.process_id -ne $externalPid -or -not $attachedHost.visible) {
        throw "attach-existing changed the ownership, identity or visibility of the external host"
    }
    Invoke-SwCliJson -Name "stop-attached-live-host" -Arguments @("daemon", "stop", "--json") | Out-Null
    $attachedStarted = $false
    if ($null -eq (Get-Process -Id $externalPid -ErrorAction SilentlyContinue)) {
        throw "stopping an attached daemon terminated the human-owned SOLIDWORKS host"
    }
    $preservedHost = Invoke-SwCliJson -Name "doctor-after-attached-stop" -Arguments @("doctor", "--json")
    if (-not $preservedHost.com.attached -or -not $preservedHost.com.visible -or
        $preservedHost.com.process_id -ne $externalPid) {
        throw "stopping an attached daemon changed the visible interactive COM host"
    }

    $attachedStarted = $true
    Invoke-SwCliJson -Name "reattach-external-host" -Arguments @("daemon", "restart", "--attach-existing", "--json") | Out-Null
    Stop-Process -Id $externalPid -Force -ErrorAction Stop
    Wait-DisconnectedHost -Name "attached-host-disconnected" | Out-Null
    $blockedShared = Invoke-SwCliJson -Name "list-after-attached-host-exit" -AllowFailure -Arguments @("document", "list", "--json")
    if ($blockedShared.ok -or $blockedShared.error.type -ne "HostDisconnected" -or
        @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw "shared host disconnect was not retained or a business request silently created a host"
    }
    $stoppedShared = Invoke-SwCliJson -Name "stop-attached-disconnected-host" -Arguments @("daemon", "stop", "--json")
    if (-not $stoppedShared.success -or -not $stoppedShared.result.host_already_disconnected) {
        throw "stopping an attached daemon after host exit did not succeed cleanly"
    }
    $attachedStarted = $false

    foreach ($artifact in @($partPath, $genericPartPath, $stepPath, $renderPath)) {
        $item = Get-Item -LiteralPath $artifact
        if ($item.Length -le 0) {
            throw "Smoke artifact is empty: $artifact"
        }
        Write-Host "[artifact] $($item.Name): $($item.Length) bytes"
    }
    Save-DesktopDiagnostic -Name "desktop-after-export"
}
catch {
    Save-DesktopDiagnostic -Name "desktop-smoke-failure"
    throw
}
finally {
    if ($attachedStarted) {
        & python -m swcli daemon stop --json 2>&1 |
            Set-Content -Path (Join-Path $Workspace "cleanup-attached-daemon-stop.log") -Encoding utf8
    }
    if ($null -ne $externalPid) {
        Stop-Process -Id $externalPid -Force -ErrorAction SilentlyContinue
    }
    if ($started) {
        & python -m swcli --request-timeout 10 document close --discard --json 2>&1 |
            Set-Content -Path (Join-Path $Workspace "cleanup-close.log") -Encoding utf8
        & python -m swcli daemon stop --json 2>&1 |
            Set-Content -Path (Join-Path $Workspace "cleanup-daemon-stop.log") -Encoding utf8
        if (-not $daemon.HasExited) {
            Stop-Process -Id $daemon.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
