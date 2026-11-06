[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [Parameter(Mandatory = $true)][string]$DrawingTemplate,
    [string]$Swconst = "C:\Program Files\SOLIDWORKS\swconst.tlb",
    [ValidateSet("all", "assembly-drawing")][string]$DocumentTypes = "all"
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$evidence = Join-Path $OutputDirectory "calibration"
$stdout = Join-Path $OutputDirectory "worker.stdout.log"
$stderr = Join-Path $OutputDirectory "worker.native.stderr.jsonl"
$previousTrace = $env:SWCLI_TRACE_NATIVE_CALLS
try {
    $env:SWCLI_TRACE_NATIVE_CALLS = '1'
    $arguments = @(
        '-I', ('"' + (Join-Path $PSScriptRoot '../verify-table-defaults-calibration.py') + '"'),
        '--output-dir', ('"' + $evidence + '"'), '--swconst', ('"' + $Swconst + '"'),
        '--drawing-template', ('"' + $DrawingTemplate + '"')
    )
    if ($DocumentTypes -eq "assembly-drawing") { $arguments += @("--document-types", "assembly", "drawing") }
    $worker = Start-Process -FilePath (Get-Command python).Source -ArgumentList $arguments -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -PassThru
    # Retain the native handle while the child is live, as in the existing
    # external-host fixture; Windows PowerShell otherwise can lose ExitCode.
    $null = $worker.Handle
} finally {
    $env:SWCLI_TRACE_NATIVE_CALLS = $previousTrace
}
$started = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$failure = $null
while (-not $worker.WaitForExit(2000)) {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    if ($now - $started -ge 1800) { $failure = 'table calibration exceeded 1800 seconds'; break }
    $trace = Join-Path $evidence 'trace.jsonl'
    if (Test-Path -LiteralPath $trace) {
        $last = $null
        # A flushed JSONL append may be observed before its newline is complete.
        try { $last = Get-Content -LiteralPath $trace -Tail 1 | ConvertFrom-Json } catch { $last = $null }
        if ($last -and $last.phase -eq 'begin' -and $now - [double]$last.time -ge 600) {
            $failure = 'table native call exceeded 600 seconds: ' + $last.call
            break
        }
    }
}
if ($failure) {
    [ordered]@{ failure = $failure; group_seconds = 1800; native_seconds = 600 } |
        ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $OutputDirectory 'watchdog-failure.json')
    & taskkill.exe /PID $worker.Id /T /F 2>$null | Out-Null
    throw $failure
}
$worker.WaitForExit()
$workerExitCode = $worker.ExitCode
[ordered]@{
    success = ($null -ne $workerExitCode -and $workerExitCode -eq 0)
    worker_exit_code = $workerExitCode
    native_seconds = 600
    group_seconds = 1800
} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $OutputDirectory 'wrapper-result.json')
if ($null -eq $workerExitCode -or $workerExitCode -ne 0) {
    throw "Table calibration failed (worker exit=$workerExitCode); inspect the original report and native trace"
}
