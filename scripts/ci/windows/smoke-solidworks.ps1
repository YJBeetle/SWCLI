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
$genericPartPath = Join-Path $Workspace "swcli-generic-model.SLDPRT"

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

function Get-SharedFileHash([string]$Path) {
    # SOLIDWORKS keeps native files open. Read without requesting an exclusive
    # file handle, unlike Get-FileHash's default path overload.
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $hash = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($hash.ComputeHash($stream))
    } finally {
        $hash.Dispose()
        $stream.Dispose()
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
        Invoke-SwCliJson -Name "rectangle-lease-renew-$plane" -Arguments @(
            "document", "lease", "renew", $sketchLease.lease.lease_id, "--json"
        ) | Out-Null
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
            $measured = Invoke-SwCliJson -Name "first-extrusion-measure" -Arguments @(
                "--session", "measurement-observer", "document", "measure",
                "--document", $emptyA.document.document_id, "--json"
            )
            if ($measured.metrics.solid_body_count -ne 1 -or
                [Math]::Abs($measured.metrics.volume_mm3 - 100000) -gt 0.00001 -or
                [Math]::Abs($measured.metrics.surface_area_mm2 - 16000) -gt 0.00001 -or
                [Math]::Abs($measured.metrics.centroid_mm.x - 10) -gt 0.000001 -or
                [Math]::Abs($measured.metrics.centroid_mm.y - 20) -gt 0.000001 -or
                [Math]::Abs($measured.metrics.centroid_mm.z - 10) -gt 0.000001 -or
                $measured.document.active -or $measured.document.current) {
                throw "native measurement did not match the first 100x50x20 solid or changed the foreground"
            }
            $hole = Invoke-SwCliJson -Name "cut-profile-circle" -Arguments @(
                "sketch", "circle", "--plane", "front", "--radius-mm", "4",
                "--center-x-mm", "10", "--center-y-mm", "20",
                "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
            )
            $sketchObserved = Invoke-SwCliJson -Name "cut-profile-inspect" -Arguments @(
                "--session", "sketch-observer", "sketch", "inspect", $hole.sketch.sketch_id,
                "--document", $emptyA.document.document_id, "--json"
            )
            if (-not $sketchObserved.geometry_complete -or $sketchObserved.sketch.absorbed -or
                $sketchObserved.editing -or $sketchObserved.profile_segment_count -ne 1 -or
                -not $sketchObserved.segments[0].geometry.complete_circle -or
                [Math]::Abs($sketchObserved.segments[0].geometry.radius_mm - 4) -gt 0.000001 -or
                $sketchObserved.sketch.constraint_status -ne $hole.sketch.constraint_status -or
                $sketchObserved.document.update_stamp -ne $hole.document.update_stamp -or
                $sketchObserved.document.active -or $sketchObserved.document.current) {
                throw "background circle observation returned incorrect geometry/state or changed foreground"
            }
            $cut = Invoke-SwCliJson -Name "feature-cut-extrude" -Arguments @(
                "feature", "cut-extrude", $hole.sketch.sketch_id, "--depth-mm", "20",
                "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
            )
            $expectedRemoved = [Math]::PI * 4 * 4 * 20
            if (-not $cut.geometry_verification.passed -or
                $cut.geometry_verification.actual_reverse -or
                [Math]::Abs($cut.geometry_verification.volume_removed_mm3 - $expectedRemoved) -gt 0.00001 -or
                [Math]::Abs($cut.measurement_after.surface_area_mm2 - (16000 + 128 * [Math]::PI)) -gt 0.00001 -or
                $cut.document.active -or $cut.document.current) {
                throw "blind cut failed native direction, hole geometry or foreground verification"
            }
            $absorbed = Invoke-SwCliJson -Name "cut-profile-inspect-absorbed" -Arguments @(
                "--session", "sketch-observer", "sketch", "inspect", $hole.sketch.sketch_id,
                "--document", $emptyA.document.document_id, "--json"
            )
            if (-not $absorbed.sketch.absorbed -or $absorbed.sketch.owner.name -ne $cut.feature.name -or
                $absorbed.document.update_stamp -ne $cut.document.update_stamp -or
                -not $absorbed.geometry_complete -or $absorbed.editing -or
                $absorbed.document.active -or $absorbed.document.current) {
                throw "absorbed circle observation did not preserve exact sketch/owner identity"
            }
            $usedCutProfile = Invoke-SwCliJson -Name "cut-profile-reuse-denied" -AllowFailure -Arguments @(
                "feature", "cut-extrude", $hole.sketch.sketch_id, "--depth-mm", "20",
                "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
            )
            if ($usedCutProfile.ok -or $usedCutProfile.error.type -ne "SketchUnavailable") {
                throw "cut creation did not reject its already absorbed profile"
            }
        }
    }
    foreach ($plane in @("front", "top", "right")) {
        Invoke-SwCliJson -Name "circle-lease-renew-$plane" -Arguments @(
            "document", "lease", "renew", $sketchLease.lease.lease_id, "--json"
        ) | Out-Null
        $circle = Invoke-SwCliJson -Name "sketch-circle-$plane" -Arguments @(
            "sketch", "circle", "--plane", $plane, "--radius-mm", "8",
            "--center-x-mm", "120", "--center-y-mm", "20",
            "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
        )
        if (-not $circle.geometry_verification.passed -or
            -not $circle.geometry_verification.complete_circle -or
            [Math]::Abs($circle.geometry_verification.actual_radius_mm - 8) -gt 0.000001 -or
            [Math]::Abs($circle.geometry_verification.actual_center_mm.x - 120) -gt 0.000001 -or
            [Math]::Abs($circle.geometry_verification.actual_center_mm.y - 20) -gt 0.000001 -or
            [Math]::Abs($circle.geometry_verification.actual_center_mm.z) -gt 0.000001 -or
            $circle.editing -or $circle.document.active -or $circle.document.current) {
            throw "circle on $plane failed native local geometry or foreground checks"
        }
        $extrusion = Invoke-SwCliJson -Name "circle-extrude-$plane" -Arguments @(
            "feature", "extrude", $circle.sketch.sketch_id, "--depth-mm", "20", "--no-merge",
            "--document", $emptyA.document.document_id, "--lease", $sketchLease.lease.lease_id, "--json"
        )
        if (-not $extrusion.geometry_verification.passed -or $extrusion.geometry_verification.actual_merge) {
            throw "circle extrusion did not produce a verified unmerged native feature"
        }
    }
    $genericMeasurement = Invoke-SwCliJson -Name "generic-model-measure" -Arguments @(
        "document", "measure", "--document", $emptyA.document.document_id, "--json"
    )
    Invoke-SwCliJson -Name "native-save-lease-renew" -Arguments @(
        "document", "lease", "renew", $sketchLease.lease.lease_id, "--json"
    ) | Out-Null
    $nativeSaved = Invoke-SwCliJson -Name "document-save-as" -Arguments @(
        "document", "save-as", $genericPartPath, "--document", $emptyA.document.document_id,
        "--lease", $sketchLease.lease.lease_id, "--json"
    )
    if ($nativeSaved.document.document_id -ne $emptyA.document.document_id -or
        $nativeSaved.document.modified -or $nativeSaved.document.path -eq "" -or
        $nativeSaved.document.active -or $nativeSaved.document.current) {
        throw "native save-as lost document identity or foreground/current state"
    }
    $savedLease = Invoke-SwCliJson -Name "lease-after-save-as" -Arguments @(
        "document", "lease", "status", "--document", $emptyA.document.document_id, "--json"
    )
    if ($savedLease.lease.lease_id -ne $sketchLease.lease.lease_id) {
        throw "native save-as lost the document lease"
    }
    $nativeHash = Get-SharedFileHash $genericPartPath
    $existingTarget = Invoke-SwCliJson -Name "save-as-existing-target" -AllowFailure -Arguments @(
        "document", "save-as", $genericPartPath, "--document", $emptyA.document.document_id,
        "--lease", $sketchLease.lease.lease_id, "--json"
    )
    if ($existingTarget.ok -or $existingTarget.error.type -ne "OutputExists" -or
        (Get-SharedFileHash $genericPartPath) -ne $nativeHash) {
        throw "save-as did not protect an existing native target"
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
    $reopened = Invoke-SwCliJson -Name "generic-model-reopen" -Arguments @(
        "--session", "reopen-verifier", "document", "open", $genericPartPath, "--read-only", "--json"
    )
    if ($reopened.document.document_id -eq $emptyA.document.document_id) {
        throw "reopening a closed native part unexpectedly reused its expired document ID"
    }
    $reopenedStructure = Invoke-SwCliJson -Name "generic-model-reopen-inspect" -Arguments @(
        "--session", "reopen-verifier", "document", "inspect", "--detail", "structure", "--json"
    )
    if ($reopenedStructure.structure.bodies.count -ne $extrusion.bodies.count) {
        throw "native save/reopen changed the modeled solid body count"
    }
    $reopenedMeasurement = Invoke-SwCliJson -Name "generic-model-reopen-measure" -Arguments @(
        "--session", "reopen-verifier", "document", "measure", "--json"
    )
    $volumeTolerance = [Math]::Max(0.00001, $genericMeasurement.metrics.volume_mm3 * 0.000000001)
    $areaTolerance = [Math]::Max(0.00001, $genericMeasurement.metrics.surface_area_mm2 * 0.000000001)
    if ([Math]::Abs($reopenedMeasurement.metrics.volume_mm3 - $genericMeasurement.metrics.volume_mm3) -gt $volumeTolerance -or
        [Math]::Abs($reopenedMeasurement.metrics.surface_area_mm2 - $genericMeasurement.metrics.surface_area_mm2) -gt $areaTolerance) {
        throw "native save/reopen changed the measured solid volume or surface area"
    }
    $reopenedDiagnosis = Invoke-SwCliJson -Name "generic-model-reopen-diagnose" -Arguments @(
        "--session", "reopen-verifier", "document", "diagnose", "--json"
    )
    if (-not $reopenedDiagnosis.diagnostics.healthy -or $reopenedDiagnosis.needs_rebuild -ne 0) {
        throw "reopened native model did not pass feature and rebuild checks"
    }
    Invoke-SwCliJson -Name "generic-model-reopen-close" -Arguments @(
        "--session", "reopen-verifier", "document", "close", "--discard", "--json"
    ) | Out-Null
    $reversePart = Invoke-SwCliJson -Name "reverse-cut-create" -Arguments @(
        "--session", "reverse-cut", "document", "create", "--json"
    )
    $reverseRectangle = Invoke-SwCliJson -Name "reverse-cut-rectangle" -Arguments @(
        "--session", "reverse-cut", "sketch", "rectangle", "--plane", "front",
        "--width-mm", "40", "--height-mm", "30", "--json"
    )
    Invoke-SwCliJson -Name "reverse-cut-boss" -Arguments @(
        "--session", "reverse-cut", "feature", "extrude", $reverseRectangle.sketch.sketch_id,
        "--depth-mm", "10", "--reverse", "--json"
    ) | Out-Null
    $reverseCircle = Invoke-SwCliJson -Name "reverse-cut-circle" -Arguments @(
        "--session", "reverse-cut", "sketch", "circle", "--plane", "front", "--radius-mm", "3", "--json"
    )
    $reverseCut = Invoke-SwCliJson -Name "reverse-cut-feature" -Arguments @(
        "--session", "reverse-cut", "feature", "cut-extrude", $reverseCircle.sketch.sketch_id,
        "--depth-mm", "10", "--reverse", "--json"
    )
    if (-not $reverseCut.geometry_verification.passed -or -not $reverseCut.geometry_verification.actual_reverse -or
        [Math]::Abs($reverseCut.geometry_verification.volume_removed_mm3 - (90 * [Math]::PI)) -gt 0.00001) {
        throw "reverse cut did not remove the expected material against the sketch normal"
    }
    Invoke-SwCliJson -Name "reverse-cut-close" -Arguments @(
        "--session", "reverse-cut", "document", "close", "--discard", "--json"
    ) | Out-Null
    # A remote profile that cannot intersect the solid must not be reported as a cut.
    Invoke-SwCliJson -Name "failed-cut-create" -Arguments @(
        "--session", "failed-cut", "document", "create", "--json"
    ) | Out-Null
    $failedCutRectangle = Invoke-SwCliJson -Name "failed-cut-rectangle" -Arguments @(
        "--session", "failed-cut", "sketch", "rectangle", "--plane", "front",
        "--width-mm", "40", "--height-mm", "30", "--json"
    )
    Invoke-SwCliJson -Name "failed-cut-boss" -Arguments @(
        "--session", "failed-cut", "feature", "extrude", $failedCutRectangle.sketch.sketch_id, "--depth-mm", "10", "--json"
    ) | Out-Null
    $outsideCircle = Invoke-SwCliJson -Name "failed-cut-outside-circle" -Arguments @(
        "--session", "failed-cut", "sketch", "circle", "--plane", "front", "--radius-mm", "2", "--center-x-mm", "1000", "--json"
    )
    $noIntersection = Invoke-SwCliJson -Name "failed-cut-no-intersection" -AllowFailure -Arguments @(
        "--session", "failed-cut", "feature", "cut-extrude", $outsideCircle.sketch.sketch_id, "--depth-mm", "10", "--json"
    )
    if ($noIntersection.ok -or $noIntersection.error.type -ne "CutExtrusionFailed") {
        throw "a nonintersecting profile did not report native cut creation failure"
    }
    $afterFailure = Invoke-SwCliJson -Name "failed-cut-measure" -Arguments @(
        "--session", "failed-cut", "document", "measure", "--json"
    )
    if ($afterFailure.metrics.solid_body_count -ne 1 -or
        [Math]::Abs($afterFailure.metrics.volume_mm3 - 12000) -gt 0.00001) {
        throw "nonintersecting cut failure changed the measured solid"
    }
    Invoke-SwCliJson -Name "failed-cut-close" -Arguments @(
        "--session", "failed-cut", "document", "close", "--discard", "--json"
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

    # The public example is executable product documentation, not COM test code.
    $exampleFolder = Join-Path $Workspace "plate-example"
    New-Item -ItemType Directory -Path $exampleFolder | Out-Null
    $example = Join-Path $PSScriptRoot "../../../examples/model-plate.ps1"
    & $example -OutputDirectory $exampleFolder |
        Set-Content (Join-Path $exampleFolder "result.json") -Encoding utf8

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
