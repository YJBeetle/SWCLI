[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
$partPath = Join-Path $Workspace "swcli-box-100x50x20.SLDPRT"
$stepPath = Join-Path $Workspace "swcli-box-100x50x20.STEP"
$renderPath = Join-Path $Workspace "swcli-box-isometric-800x600.bmp"

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

Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Save-DesktopDiagnostic -Name "desktop-before-swclid"

$python = (Get-Command python -ErrorAction Stop).Source
$daemonStdout = Join-Path $Workspace "swclid.stdout.log"
$daemonStderr = Join-Path $Workspace "swclid.stderr.log"
$daemon = Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "swcli", "daemon", "serve", "--visible", "--startup-timeout", "120") `
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

    $emptyA = Invoke-SwCliJson -Name "document-create-a" -Arguments @("document", "create", "--type", "part", "--json")
    $emptyB = Invoke-SwCliJson -Name "document-create-b" -Arguments @("document", "create", "--json")
    if (-not $emptyA.created -or -not $emptyB.created -or
        $emptyA.document.path -ne "" -or $emptyB.document.path -ne "" -or
        $emptyA.document.type -ne 1 -or $emptyB.document.type -ne 1 -or
        $emptyA.document.document_id -eq $emptyB.document.document_id) {
        throw "document create did not return two distinct unsaved part handles"
    }
    $selectedA = Invoke-SwCliJson -Name "document-inspect-created-a" -Arguments @(
        "document", "inspect", "--document", $emptyA.document.document_id, "--json"
    )
    if ($selectedA.document.current -or $selectedA.document.active) {
        throw "inspecting a non-current created part changed its selection state"
    }
    $sketchLease = Invoke-SwCliJson -Name "sketch-lease-acquire" -Arguments @(
        "document", "lease", "acquire", "--document", $emptyA.document.document_id, "--json"
    )
    $deniedSketch = Invoke-SwCliJson -Name "sketch-lease-denied" -AllowFailure -Arguments @(
        "--session", "sketch-contender", "sketch", "rectangle", "--plane", "front",
        "--width-mm", "100", "--height-mm", "50", "--document", $emptyA.document.document_id, "--json"
    )
    if ($deniedSketch.ok -or $deniedSketch.error.type -ne "DocumentLeaseConflict") {
        throw "rectangle sketch creation bypassed the document lease"
    }
    if ($null -eq $selectedA.document.update_stamp) {
        throw "new part has no native update stamp for sketch preconditions"
    }
    $staleStamp = ([int]$selectedA.document.update_stamp + 1).ToString()
    $staleSketch = Invoke-SwCliJson -Name "sketch-stale-stamp" -AllowFailure -Arguments @(
        "sketch", "rectangle", "--plane", "front", "--width-mm", "100", "--height-mm", "50",
        "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id,
        "--if-update-stamp", $staleStamp, "--json"
    )
    if ($staleSketch.ok -or $staleSketch.error.type -ne "DocumentUpdateConflict") {
        throw "rectangle sketch creation bypassed the native update stamp precondition"
    }
    $sketchIds = @()
    foreach ($plane in @("front", "top", "right")) {
        $rectangle = Invoke-SwCliJson -Name "sketch-rectangle-$plane" -Arguments @(
            "sketch", "rectangle", "--plane", $plane,
            "--width-mm", "100", "--height-mm", "50", "--center-x-mm", "10", "--center-y-mm", "20",
            "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
        )
        if ($rectangle.editing -or -not $rectangle.geometry_verification.passed -or
            $rectangle.geometry_verification.profile_segment_count -ne 4 -or
            $rectangle.sketch.sketch_id -notmatch '^s-[a-z0-9]{6}$' -or
            $rectangle.document.active -or $rectangle.document.current) {
            throw "rectangle on $plane failed geometry, edit-state or foreground restoration checks"
        }
        $sketchIds += $rectangle.sketch.sketch_id
    }
    if (@($sketchIds | Select-Object -Unique).Count -ne 3) {
        throw "rectangle sketches did not receive distinct handles"
    }
    for ($index = 0; $index -lt $sketchIds.Count; $index++) {
        $extrudeArguments = @(
            "feature", "extrude", $sketchIds[$index], "--depth-mm", "20",
            "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
        )
        if ($index -eq 1) { $extrudeArguments += "--reverse" }
        if ($index -eq 2) { $extrudeArguments += "--no-merge" }
        $extrusion = Invoke-SwCliJson -Name "feature-extrude-$index" -Arguments $extrudeArguments
        if (-not $extrusion.geometry_verification.passed -or
            $extrusion.geometry_verification.actual_depth_mm -ne 20 -or
            $extrusion.geometry_verification.actual_reverse -ne ($index -eq 1) -or
            $extrusion.geometry_verification.actual_merge -ne ($index -ne 2) -or
            $extrusion.document.active -or $extrusion.document.current) {
            throw "extrusion failed native definition or foreground restoration checks"
        }
        if ($index -eq 0) {
            $size = $extrusion.bodies.items[0].approximate_bounding_box.size_mm
            if ($extrusion.bodies.count -ne 1 -or [Math]::Abs($size.x - 100) -gt 0.1 -or
                [Math]::Abs($size.y - 50) -gt 0.1 -or [Math]::Abs($size.z - 20) -gt 0.1) {
                throw "first extrusion did not produce the expected 100x50x20 body"
            }
        }
    }
    $usedSketch = Invoke-SwCliJson -Name "feature-extrude-used-sketch" -AllowFailure -Arguments @(
        "feature", "extrude", $sketchIds[0], "--depth-mm", "20",
        "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
    )
    if ($usedSketch.ok -or $usedSketch.error.type -ne "SketchUnavailable") {
        throw "extrusion did not reject an already absorbed sketch handle"
    }
    Invoke-SwCliJson -Name "sketch-lease-release" -Arguments @(
        "document", "lease", "release", $sketchLease.lease.lease_id, "--json"
    ) | Out-Null
    Invoke-SwCliJson -Name "document-close-created-a" -Arguments @(
        "document", "close", "--document", $emptyA.document.document_id, "--discard", "--json"
    ) | Out-Null
    $currentB = Invoke-SwCliJson -Name "document-inspect-created-b" -Arguments @("document", "inspect", "--json")
    if ($currentB.document.document_id -ne $emptyB.document.document_id) {
        throw "closing a non-current part changed the current document"
    }
    Invoke-SwCliJson -Name "document-close-created-b" -Arguments @("document", "close", "--discard", "--json") | Out-Null

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

    $connected = Invoke-SwCliJson -Name "daemon-connected" -Arguments @("daemon", "status", "--json")
    if (-not $connected.result.host_connected) {
        throw "swclid did not report its SOLIDWORKS host as connected"
    }
    $solidworksPid = [int]$connected.result.host.process_id
    Stop-Process -Id $solidworksPid -Force -ErrorAction Stop

    $disconnected = $null
    for ($attempt = 1; $attempt -le 25; $attempt++) {
        Start-Sleep -Milliseconds 200
        $status = Invoke-SwCliJson `
            -Name ("daemon-disconnected-{0:D2}" -f $attempt) `
            -Arguments @("daemon", "status", "--json")
        if (-not $status.result.host_connected) {
            $disconnected = $status
            break
        }
    }
    if ($null -eq $disconnected) {
        throw "swclid did not detect the external SOLIDWORKS exit within 5 seconds"
    }
    if ($disconnected.result.worker_alive -or
        $null -ne $disconnected.result.host -or
        -not $disconnected.result.recovery_required -or
        $disconnected.result.recovery_error.code -ne "HostDisconnected") {
        throw "swclid returned an inconsistent disconnected host state"
    }

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

    foreach ($artifact in @($partPath, $stepPath, $renderPath)) {
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
