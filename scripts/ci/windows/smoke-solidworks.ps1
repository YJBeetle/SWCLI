[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,
    [switch]$Hidden,
    [switch]$VisibleSmoke,
    [ValidateSet("core", "full")]
    [string]$Suite = "full",
    [string]$PropertyFixtureDirectory,
    [string]$AnnotationFixtureDirectory
)

$ErrorActionPreference = "Stop"
if ($VisibleSmoke -and $Hidden) { throw "VisibleSmoke cannot use a hidden host" }
if ($AnnotationFixtureDirectory -and -not $Hidden) { throw "Annotation verification requires the initial hidden host" }
if (-not $VisibleSmoke -and -not $Hidden) { throw "Business suites require -Hidden; use -VisibleSmoke for the lightweight visible check" }
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
$partPath = Join-Path $Workspace "swcli-box-100x50x20.SLDPRT"
$stepPath = Join-Path $Workspace "swcli-box-100x50x20.STEP"
$renderPath = Join-Path $Workspace "swcli-box-isometric-800x600.bmp"
$genericPartPath = Join-Path $Workspace "runtime-sets\native-model\modeling\model.SLDPRT"

function Save-LifecycleInventory {
    param([Parameter(Mandatory = $true)][string]$Name)

    $snapshot = [ordered]@{
        schema_version = 1; name = $Name; observed_utc = [DateTime]::UtcNow.ToString("o")
        evidence_file = "$Name-inventory.json"
        task_scope = "\SWCLI-demand-*"; task_inventory_complete = $false
        process_scope = @("SLDWORKS.exe", "sldworks_fs.exe", "sldbgproc.exe", "python.exe", "pythonw.exe", "swclid.exe")
        process_inventory_complete = $false; tasks = @(); processes = @(); errors = @()
    }
    try {
        $snapshot.tasks = @(
            Get-ScheduledTask -TaskPath "\" -TaskName "SWCLI-demand-*" -ErrorAction Stop |
                Sort-Object TaskPath, TaskName | ForEach-Object {
                    [ordered]@{ task_name = $_.TaskName; task_path = $_.TaskPath; state = [string]$_.State }
                }
        )
        $snapshot.task_inventory_complete = $true
    }
    catch {
        # An empty wildcard result is a complete empty inventory, not an
        # unavailable ScheduledTasks cmdlet or an access failure.
        if ($_.FullyQualifiedErrorId -like "CmdletizationQuery_NotFound*") {
            $snapshot.tasks = @()
            $snapshot.task_inventory_complete = $true
        }
        else {
            $snapshot.errors += [ordered]@{ stage = "scheduled_tasks"; message = $_.Exception.Message }
        }
    }
    try {
        $filter = ($snapshot.process_scope | ForEach-Object { "Name='$_'" }) -join " OR "
        $snapshot.processes = @(
            Get-CimInstance -ClassName Win32_Process -Filter $filter `
                -Property Name, ProcessId, ParentProcessId, CreationDate -ErrorAction Stop |
                Sort-Object ProcessId | ForEach-Object {
                    if ($null -eq $_.CreationDate) { throw "Related process creation time is unavailable for PID $($_.ProcessId)" }
                    [ordered]@{ process_id = [int]$_.ProcessId; parent_process_id = [int]$_.ParentProcessId
                        name = $_.Name; created_utc = $_.CreationDate.ToUniversalTime().ToString("o") }
                }
        )
        $snapshot.process_inventory_complete = $true
    }
    catch {
        $snapshot.errors += [ordered]@{ stage = "related_processes"; message = $_.Exception.Message }
    }
    try {
        ConvertTo-Json -InputObject $snapshot -Depth 6 |
            Set-Content -LiteralPath (Join-Path $Workspace $snapshot.evidence_file) -Encoding utf8 -ErrorAction Stop
    }
    catch {
        $snapshot.errors += [ordered]@{ stage = "inventory_write"; message = $_.Exception.Message }
        Write-Warning "Cannot persist $Name lifecycle inventory: $($_.Exception.Message)" -WarningAction Continue
    }
    return [pscustomobject]$snapshot
}

function Assert-NoNewLifecycleResources {
    param(
        [Parameter(Mandatory = $true)]$Before,
        [Parameter(Mandatory = $true)]$After,
        [Parameter(Mandatory = $true)][string]$Name,
        [ValidateRange(0.01, 10.0)][double]$SettleSeconds = 10
    )
    $existingTasks = @{}
    foreach ($task in $Before.tasks) { $existingTasks["$($task.task_path)$($task.task_name)"] = $true }
    $existingProcesses = @{}
    foreach ($process in $Before.processes) {
        $existingProcesses["$($process.process_id)|$($process.name)|$($process.created_utc)"] = $true
    }
    $originalAfter = $After.evidence_file
    $observations = @($originalAfter)
    $settleWait = [Diagnostics.Stopwatch]::StartNew()
    $observation = 0
    while ($true) {
        $newTasks = @($After.tasks | Where-Object { -not $existingTasks.ContainsKey("$($_.task_path)$($_.task_name)") })
        $newProcesses = @($After.processes | Where-Object {
            -not $existingProcesses.ContainsKey("$($_.process_id)|$($_.name)|$($_.created_utc)")
        })
        $complete = $Before.task_inventory_complete -and $Before.process_inventory_complete -and
            $After.task_inventory_complete -and $After.process_inventory_complete -and
            @($Before.errors).Count -eq 0 -and @($After.errors).Count -eq 0
        $passed = $complete -and $newTasks.Count -eq 0 -and $newProcesses.Count -eq 0
        [ordered]@{ schema_version = 1; before = $Before.evidence_file; original_after = $originalAfter
            after = $After.evidence_file; observations = $observations
            settle_budget_seconds = $SettleSeconds; settle_elapsed_seconds = $settleWait.Elapsed.TotalSeconds
            inventory_complete = [bool]$complete; new_tasks = $newTasks; new_processes = $newProcesses
            passed = [bool]$passed } |
            ConvertTo-Json -Depth 6 |
            Set-Content -LiteralPath (Join-Path $Workspace "$Name-comparison.json") -Encoding utf8 -ErrorAction Stop
        # Never turn a failed observation into an apparent empty inventory, or
        # wait/retry until an access/read error disappears.
        if (-not $complete) { throw "$Name lifecycle inventory is incomplete; see original inventory errors" }
        if ($passed) { return }
        if ($settleWait.Elapsed.TotalSeconds -ge $SettleSeconds) {
            throw "$Name left new SWCLI demand tasks or related processes; see original inventory and comparison"
        }
        # A shutdown response can precede Python's process exit. Observe only OS
        # state within the existing ten-second lifecycle window; never submit
        # another startup/shutdown request. Keep the original after snapshot.
        $remainingMilliseconds = [Math]::Ceiling(($SettleSeconds - $settleWait.Elapsed.TotalSeconds) * 1000)
        Start-Sleep -Milliseconds ([int][Math]::Max(1, [Math]::Min(200, $remainingMilliseconds)))
        $observation++
        $After = Save-LifecycleInventory -Name ("{0}-settle-{1:D2}" -f $Name, $observation)
        $observations += $After.evidence_file
    }
}

function Invoke-AttachWithoutHostProbe {
    $before = Save-LifecycleInventory -Name "attach-without-host-before"
    $firstFailure = $null
    try {
        $missingHost = Invoke-SwCliJson -Name "attach-without-host" -AllowFailure -Arguments @(
            "daemon", "start", "--attach-existing", "--json"
        )
        if ($missingHost.success -or $missingHost.error.code -ne "ExistingHostNotFound" -or
            @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
            throw "attach-existing without a host created an owned instance or did not fail explicitly"
        }
    }
    catch { $firstFailure = $_; throw }
    finally {
        $after = Save-LifecycleInventory -Name "attach-without-host-after"
        try { Assert-NoNewLifecycleResources -Before $before -After $after -Name "attach-without-host" }
        catch {
            if ($null -eq $firstFailure) { throw }
            try {
                $_ | Out-String | Set-Content -LiteralPath (Join-Path $Workspace "attach-without-host-evidence-error.log") -Encoding utf8
            } catch { Write-Warning "Cannot persist secondary lifecycle evidence error" -WarningAction Continue }
            Write-Warning "Lifecycle evidence also failed; preserving original attach-without-host failure" -WarningAction Continue
        }
    }
}

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

function Assert-OwnedDaemonExit {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutMilliseconds = 30000
    )
    $finished = $Process.WaitForExit($TimeoutMilliseconds)
    if ($finished) {
        # Populate ExitCode and finish redirected output after the bounded wait.
        $Process.WaitForExit()
        $Process.Refresh()
    }
    $exitCode = if ($finished) { $Process.ExitCode } else { $null }
    [ordered]@{ process_id = $Process.Id; wait_completed = $finished;
        has_exited = $Process.HasExited; exit_code = $exitCode } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Workspace "$Name-exit.json") -Encoding utf8
    if (-not $finished -or $null -eq $exitCode -or $exitCode -ne 0) {
        throw "$Name daemon shutdown failed: wait_completed=$finished exit_code=$exitCode"
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
            throw "swcli $Name did not exit within 135 seconds"
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
        throw "swcli $Name exited without a JSON result (exit code $($process.ExitCode))`n$stderr"
    }
    try {
        $payload = Get-Content $outputPath -Raw -Encoding utf8 | ConvertFrom-Json
    }
    catch {
        $stderr = Get-Content $stderrPath -Raw -ErrorAction SilentlyContinue
        throw "swcli $Name returned invalid JSON (exit code $($process.ExitCode))`n$stderr"
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
        throw "swcli $Name returned ok=false: ${errorType}: ${errorMessage}${requestId}"
    }
    if (-not $AllowFailure -and
        $null -ne $process.ExitCode -and
        $process.ExitCode -ne 0) {
        $stderr = Get-Content $stderrPath -Raw -ErrorAction SilentlyContinue
        throw "swcli $Name failed with exit code $($process.ExitCode)`n$stderr"
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

$lifecycleInitial = Save-LifecycleInventory -Name "lifecycle-initial"
if (-not $lifecycleInitial.task_inventory_complete -or -not $lifecycleInitial.process_inventory_complete -or
    @($lifecycleInitial.errors).Count -ne 0) {
    throw "Initial lifecycle inventory is incomplete; refusing to start a test host"
}
if (@($lifecycleInitial.processes | Where-Object { $_.name -ieq "SLDWORKS.exe" }).Count -ne 0) {
    throw "Lifecycle harness refuses a pre-existing SOLIDWORKS host; it was only observed and was not stopped"
}
Start-Sleep -Seconds 2
Save-DesktopDiagnostic -Name "desktop-before-swclid"

$python = (Get-Command python -ErrorAction Stop).Source
$daemonStdout = Join-Path $Workspace "swclid.stdout.log"
$daemonStderr = Join-Path $Workspace "swclid.stderr.log"
$daemonArguments = @("-m", "swcli", "daemon", "serve", "--startup-timeout", "120")
if (-not $Hidden) { $daemonArguments += "--visible" }
$previousNativeTrace = [Environment]::GetEnvironmentVariable("SWCLI_TRACE_NATIVE_CALLS", "Process")
try {
    if ($AnnotationFixtureDirectory) {
        $env:SWCLI_TRACE_NATIVE_CALLS = "1"
    }
    else {
        Remove-Item Env:SWCLI_TRACE_NATIVE_CALLS -ErrorAction SilentlyContinue
    }
    $daemon = Start-Process `
        -FilePath $python `
        -ArgumentList $daemonArguments `
        -RedirectStandardOutput $daemonStdout `
        -RedirectStandardError $daemonStderr `
        -NoNewWindow `
        -PassThru
}
finally {
    [Environment]::SetEnvironmentVariable("SWCLI_TRACE_NATIVE_CALLS", $previousNativeTrace, "Process")
}
# Pin the OS handle while it is alive; preflight exits long before we check it.
$null = $daemon.Handle
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
$smokeFailure = $null
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

    if ($VisibleSmoke) {
        $sample = Join-Path $env:PUBLIC "Documents\SOLIDWORKS\SOLIDWORKS 2025\samples\learn\Paper Airplane.SLDPRT"
        & python -I (Join-Path $PSScriptRoot "../verify-visible.py") `
            --output-dir $Workspace --sample-part $sample
        if ($LASTEXITCODE -ne 0) { throw "shared visible smoke failed" }
        $proof = Get-Content (Join-Path $Workspace "visible.json") -Raw -Encoding utf8 | ConvertFrom-Json
        Assert-OwnedDaemonExit -Process $daemon -Name "visible"
        $started = $false
        $exitWait = [Diagnostics.Stopwatch]::StartNew()
        while ($null -ne (Get-Process -Id $proof.host.process_id -ErrorAction SilentlyContinue) -and
            $exitWait.Elapsed.TotalSeconds -lt 10) { Start-Sleep -Milliseconds 200 }
        if ($null -ne (Get-Process -Id $proof.host.process_id -ErrorAction SilentlyContinue)) {
            throw "Visible smoke did not stop its owned SOLIDWORKS process"
        }
        $visibleFinal = Save-LifecycleInventory -Name "visible-stop-final"
        Assert-NoNewLifecycleResources -Before $lifecycleInitial -After $visibleFinal -Name "visible-stop"
        return
    }

    Invoke-SwCliJson -Name "capabilities" -Arguments @("capabilities", "--full", "--json") | Out-Null
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

    if ($PropertyFixtureDirectory) {
        & python -I (Join-Path $PSScriptRoot "../verify-properties.py") `
            --output-dir (Join-Path $Workspace "properties") `
            --fixture-dir $PropertyFixtureDirectory --save-copy --edit-metadata
        if ($LASTEXITCODE -ne 0) { throw "public custom property CLI gate failed" }
        & python -I (Join-Path $PSScriptRoot "../verify-document-units.py") `
            --output-dir (Join-Path $Workspace "document-units") `
            --fixture-dir $PropertyFixtureDirectory
        if ($LASTEXITCODE -ne 0) { throw "public document units CLI gate failed" }
    }

    if ($AnnotationFixtureDirectory) {
        & python -I (Join-Path $PSScriptRoot "../verify-document-annotations.py") `
            --output-dir (Join-Path $Workspace "document-annotations") `
            --fixture-dir $AnnotationFixtureDirectory --native-trace $daemonStderr
        if ($LASTEXITCODE -ne 0) { throw "public document annotation CLI gate failed" }
        foreach ($preferenceProfile in @("fonts", "display", "standards")) {
            & python -I (Join-Path $PSScriptRoot "../verify-document-preferences.py") `
                --profile $preferenceProfile `
                --output-dir (Join-Path $Workspace ("document-preferences-" + $preferenceProfile)) `
                --fixture-dir $AnnotationFixtureDirectory --native-trace $daemonStderr
            if ($LASTEXITCODE -ne 0) { throw "public document preferences $preferenceProfile CLI gate failed" }
        }
    }

    # Shared scripts own CAD coverage and fresh CLI/SW session boundaries.
    $installation = @($doctor.installations | Where-Object { $_.year -eq 2025 }) | Select-Object -First 1
    if ($null -eq $installation) { throw "SOLIDWORKS 2025 installation path is unavailable" }
    $setsFolder = Join-Path $Workspace "runtime-sets"
    $drawingTemplateArguments = @()
    if ($Suite -eq "full") {
        # Windows PowerShell 5 native argument quoting mishandles a space-bearing
        # directory ending in backslash. The registry commonly supplies one.
        $drawingInstallDir = $installation.install_dir.TrimEnd([char[]]"\/")
        $drawingTemplate = & python -I (Join-Path $PSScriptRoot "../gate_support/drawing_template.py") --program-data $env:ProgramData --installation $drawingInstallDir
        if ($LASTEXITCODE -ne 0) { throw "Installed drawing template fixture discovery failed" }
        $drawingTemplateArguments = @("--drawing-template", $drawingTemplate)
    }
    $samplePart = Join-Path $env:PUBLIC "Documents\SOLIDWORKS\SOLIDWORKS 2025\samples\learn\Paper Airplane.SLDPRT"
    $sampleAssembly = Join-Path $installation.install_dir "sldBenchmarking\Macro\Mold\bezel moldbase.sldasm"
    $sampleDrawing = Join-Path $installation.install_dir "sldBenchmarking\Macro\Mold\bezel moldbase.slddrw"
    if (-not (Test-Path -LiteralPath $sampleDrawing -PathType Leaf)) {
        throw "Installed drawing fixture is missing: $sampleDrawing"
    }
    # Preserve relative references, but keep the fixture outside uploaded evidence.
    $drawingWorkFolder = Join-Path ([IO.Path]::GetTempPath()) ("swcli-drawing-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $drawingWorkFolder | Out-Null
    $setsFailed = $true
    try {
        $mode = if ($Hidden) { "hidden" } else { "visible" }
        & python -I (Join-Path $PSScriptRoot "../verify-runtime-sets.py") `
            --suite $Suite --mode $mode `
            --output-dir $setsFolder --host-output-dir $setsFolder `
            --sample-part $samplePart --sample-assembly $sampleAssembly `
            --sample-drawing $sampleDrawing --sample-drawing-local $sampleDrawing `
            --fixture-work-dir $drawingWorkFolder --host-fixture-work-dir $drawingWorkFolder @drawingTemplateArguments
        if ($LASTEXITCODE -ne 0) { throw "shared isolated functional sets failed" }
        $setsFailed = $false
    }
    finally {
        try { Remove-Item -LiteralPath $drawingWorkFolder -Recurse -Force -ErrorAction Stop }
        catch {
            if (-not $setsFailed) { throw }
            Write-Warning "Drawing fixture cleanup failed; preserving the original gate failure: $_"
        }
    }
    # Shared sets stop their last owned session. Windows-only lifecycle/ROT
    # assertions below need a separate fresh daemon, not a surviving CAD set.
    Assert-OwnedDaemonExit -Process $daemon -Name "preflight"
    $equationFixtureFolder = Join-Path $Workspace "equation-fixture"
    New-Item -ItemType Directory -Path $equationFixtureFolder | Out-Null
    $extraArguments = @("-I", ('"' + (Join-Path $PSScriptRoot "equation-fixture-daemon.py") + '"'),
        ('"' + $equationFixtureFolder + '"'), "daemon", "serve", "--startup-timeout", "120")
    $daemon = Start-Process -FilePath $python -ArgumentList $extraArguments `
        -RedirectStandardOutput (Join-Path $Workspace "windows-extra.stdout.log") `
        -RedirectStandardError (Join-Path $Workspace "windows-extra.stderr.log") `
        -NoNewWindow -PassThru
    $null = $daemon.Handle
    $ready = $false
    $startupWait = [Diagnostics.Stopwatch]::StartNew()
    $attempt = 0
    while ($startupWait.Elapsed.TotalSeconds -lt 180) {
        $attempt++
        $daemon.Refresh()
        if ($daemon.HasExited) { throw "Windows-only daemon exited during startup" }
        $status = Invoke-SwCliJson -Name "windows-extra-startup-$attempt" -AllowFailure -Arguments @("daemon", "status", "--json")
        if ($status.success) {
            if (-not $status.result.host_connected -or -not $status.result.host.owned_by_daemon -or
                $status.result.host.shared_interactive -or $status.result.host.visible) {
                throw "Windows-only daemon has unexpected host ownership or visibility"
            }
            $ready = $true
            break
        }
        if ($status.error.code -notin @("ConnectionRefusedError", "Starting", "TimeoutError", "ConnectionResetError")) {
            throw "Windows-only daemon status failed"
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "Windows-only daemon startup deadline exceeded" }
    # Prepare the private equation through this worker's own hidden STA COM session.
    & python -I (Join-Path $PSScriptRoot "verify-equation-dimension.py") `
        --fixture-dir $equationFixtureFolder --output-dir (Join-Path $Workspace "equation-dimension")
    if ($LASTEXITCODE -ne 0) { throw "equation-owned dimension protection gate failed" }

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

    $ownedStopFinal = Save-LifecycleInventory -Name "owned-stop-final"
    Assert-NoNewLifecycleResources -Before $lifecycleInitial -After $ownedStopFinal -Name "owned-stop"

    # An explicitly attached instance belongs to the human, not the daemon.
    Invoke-AttachWithoutHostProbe

    . (Join-Path $PSScriptRoot "start-external-host.ps1")
    $external = Start-ExternalTestHost
    $externalPid = $external.process_id
    $attachedBefore = Save-LifecycleInventory -Name "attached-live-before"
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

    $attachedLiveFinal = Save-LifecycleInventory -Name "attached-live-stop-final"
    Assert-NoNewLifecycleResources -Before $attachedBefore -After $attachedLiveFinal -Name "attached-live-stop"

    $attachedStarted = $true
    Invoke-SwCliJson -Name "reattach-external-host" -Arguments @("daemon", "restart", "--attach-existing", "--json") | Out-Null
    $restartReady = Save-LifecycleInventory -Name "attached-restart-ready"
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
    $attachedFinal = Save-LifecycleInventory -Name "attached-disconnected-stop-final"
    Assert-NoNewLifecycleResources -Before $lifecycleInitial -After $attachedFinal -Name "attached-disconnected-stop"

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
    $smokeFailure = $_
    try { Save-DesktopDiagnostic -Name "desktop-smoke-failure" }
    catch { Write-Warning "Desktop evidence failed; preserving original smoke failure" -WarningAction Continue }
    throw $smokeFailure
}
finally {
    $cleanupFailure = $null
    try {
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
    catch {
        $cleanupFailure = $_
        try { $_ | Out-String | Set-Content -LiteralPath (Join-Path $Workspace "cleanup-error.log") -Encoding utf8 }
        catch { Write-Warning "Cannot persist cleanup error" -WarningAction Continue }
    }
    finally {
        $finalInventory = Save-LifecycleInventory -Name "lifecycle-final"
        try { Assert-NoNewLifecycleResources -Before $lifecycleInitial -After $finalInventory -Name "lifecycle-final" }
        catch {
            if ($null -eq $smokeFailure -and $null -eq $cleanupFailure) { throw }
            try { $_ | Out-String | Set-Content -LiteralPath (Join-Path $Workspace "lifecycle-final-evidence-error.log") -Encoding utf8 }
            catch { Write-Warning "Cannot persist final lifecycle evidence error" -WarningAction Continue }
            Write-Warning "Final lifecycle evidence failed; preserving the original smoke/cleanup failure" -WarningAction Continue
        }
    }
    if ($null -ne $cleanupFailure -and $null -eq $smokeFailure) { throw $cleanupFailure }
}
