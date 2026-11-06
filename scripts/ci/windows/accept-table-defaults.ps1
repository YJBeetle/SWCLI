[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [Parameter(Mandatory = $true)][string]$FixtureDirectory,
    [Parameter(Mandatory = $true)][string]$InternalReportSha256,
    [Parameter(Mandatory = $true)][string]$InternalHead,
    [Parameter(Mandatory = $true)][string]$InternalRun
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$python = (Get-Command python).Source
$daemonStdout = Join-Path $OutputDirectory 'daemon.stdout.jsonl'
$daemonStderr = Join-Path $OutputDirectory 'daemon.native.stderr.jsonl'
$previousTrace = $env:SWCLI_TRACE_NATIVE_CALLS
$daemon = $null
$gate = $null
$success = $false
try {
    try {
        $env:SWCLI_TRACE_NATIVE_CALLS = '1'
        $daemon = Start-Process -FilePath $python -ArgumentList @('-I', '-m', 'swcli', 'daemon', 'serve', '--startup-timeout', '120', '--tray', 'off') -RedirectStandardOutput $daemonStdout -RedirectStandardError $daemonStderr -NoNewWindow -PassThru
        $null = $daemon.Handle
    } finally {
        $env:SWCLI_TRACE_NATIVE_CALLS = $previousTrace
    }
    $ready = $false
    for ($check = 0; $check -lt 180; $check++) {
        if ($daemon.HasExited) { throw 'Public table daemon exited during startup' }
        if ((Test-Path $daemonStdout) -and (Select-String -LiteralPath $daemonStdout -SimpleMatch '"action": "daemon.serve"' -Quiet)) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Public table daemon startup exceeded 180 seconds' }
    $gate = Start-Process -FilePath $python -ArgumentList @(
        '-I', ('"' + (Join-Path $PSScriptRoot '../verify-table-defaults-public.py') + '"'),
        '--output-dir', ('"' + (Join-Path $OutputDirectory 'gate') + '"'),
        '--fixture-dir', ('"' + $FixtureDirectory + '"'),
        '--native-trace', ('"' + $daemonStderr + '"'),
        '--internal-report-sha256', $InternalReportSha256, '--internal-head', $InternalHead, '--internal-run', $InternalRun
    ) -RedirectStandardOutput (Join-Path $OutputDirectory 'gate.stdout.log') -RedirectStandardError (Join-Path $OutputDirectory 'gate.stderr.log') -NoNewWindow -PassThru
    if (-not $gate.WaitForExit(1800000)) { throw 'Public table acceptance exceeded its 1800-second group budget' }
    if ($gate.ExitCode -ne 0) { throw 'Public table acceptance failed; preserve its first report/trace failure' }
    & $python -I -m swcli --request-timeout 120 daemon stop --json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $OutputDirectory 'daemon-stop.json')
    if ($LASTEXITCODE -ne 0 -or -not $daemon.WaitForExit(120000) -or $daemon.ExitCode -ne 0) { throw 'Public table owned daemon shutdown was not confirmed' }
    $success = $true
} finally {
    [ordered]@{ success = $success; native_seconds = 600; group_seconds = 1800; daemon_exit_confirmed = $success } | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $OutputDirectory 'wrapper-result.json')
    # Cleanup of these two owned processes only; never a restart or CAD rollback.
    foreach ($process in @($gate, $daemon)) {
        if ($process -and -not $process.HasExited) { & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
    }
}
