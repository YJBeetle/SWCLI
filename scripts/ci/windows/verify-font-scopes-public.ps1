[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [Parameter(Mandatory = $true)][string]$FixtureDirectory,
    [Parameter(Mandatory = $true)][ValidateSet("dimensions", "notes", "tables")][string]$Scope
)
$ErrorActionPreference = "Stop"
if ($env:GITHUB_ACTIONS -ne "true" -or $env:GITHUB_EVENT_NAME -ne "workflow_dispatch" -or
    $env:GITHUB_REF -ne "refs/heads/codex/docprops-font-scopes") {
    throw "Public font verification requires the authorized branch and disposable GitHub runner"
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "Refusing to attach to or replace a pre-existing SOLIDWORKS host"
}
if (Get-NetTCPConnection -LocalPort 18496 -State Listen -ErrorAction SilentlyContinue) {
    throw "Dedicated font-gate endpoint is already occupied"
}
if (Test-Path -LiteralPath $OutputDirectory) { throw "A fresh evidence directory is required" }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$python = (Get-Command python -ErrorAction Stop).Source
$client = (Get-Command swcli -ErrorAction Stop).Source
$daemonOutput = Join-Path $OutputDirectory "daemon.stdout.log"
$daemonError = Join-Path $OutputDirectory "daemon.stderr.log"
$gateOutput = Join-Path $OutputDirectory "gate.stdout.log"
$gateError = Join-Path $OutputDirectory "gate.stderr.log"
$endpoint = "127.0.0.1:18496"
$daemon = $null
$worker = $null
$firstFailure = $null
$previousTrace = [Environment]::GetEnvironmentVariable("SWCLI_TRACE_NATIVE_CALLS", "Process")
try {
    $env:SWCLI_TRACE_NATIVE_CALLS = "1"
    $daemon = Start-Process -FilePath $client `
        -ArgumentList @("daemon", "serve", "--host", "127.0.0.1", "--port", "18496", "--tray", "off", "--startup-timeout", "120") `
        -RedirectStandardOutput $daemonOutput -RedirectStandardError $daemonError -PassThru -NoNewWindow
    $null = $daemon.Handle
    [IO.File]::WriteAllText((Join-Path $OutputDirectory "daemon.pid"), [string]$daemon.Id)
    $ready = $false
    $startup = [Diagnostics.Stopwatch]::StartNew()
    while ($startup.Elapsed.TotalSeconds -lt 180) {
        $daemon.Refresh()
        if ($daemon.HasExited) { throw "Owned public font daemon exited before readiness" }
        if ((Test-Path -LiteralPath $daemonOutput) -and
            (Select-String -LiteralPath $daemonOutput -SimpleMatch '"action": "daemon.serve"' -Quiet)) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "Owned public font daemon readiness timed out; no restart attempted" }
    $script = Join-Path $PSScriptRoot "../verify-font-scopes-public.py"
    $gateDirectory = Join-Path $OutputDirectory "gate"
    $arguments = @("-I", ('"{0}"' -f $script), "--output-dir", ('"{0}"' -f $gateDirectory),
        "--fixture-dir", ('"{0}"' -f $FixtureDirectory), "--native-trace", ('"{0}"' -f $daemonError),
        "--scope", $Scope, "--endpoint", $endpoint, "--cli-command", ('"{0}"' -f $client))
    $worker = Start-Process -FilePath $python -ArgumentList $arguments `
        -RedirectStandardOutput $gateOutput -RedirectStandardError $gateError -PassThru -NoNewWindow
    $null = $worker.Handle
    [IO.File]::WriteAllText((Join-Path $OutputDirectory "gate.pid"), [string]$worker.Id)
    if (-not $worker.WaitForExit(1800 * 1000)) {
        Stop-Process -Id $worker.Id -Force -ErrorAction Stop
        throw "Public font group exceeded 1800 seconds; only its gate Python process was stopped"
    }
    if ($worker.ExitCode -ne 0) { throw "Public font gate failed; retain original report, journal and trace" }
}
catch {
    $firstFailure = $_
    throw
}
finally {
    [Environment]::SetEnvironmentVariable("SWCLI_TRACE_NATIVE_CALLS", $previousTrace, "Process")
    if ($null -ne $daemon) {
        try {
            $daemon.Refresh()
            if (-not $daemon.HasExited) {
                & $client --endpoint $endpoint --request-timeout 600 daemon stop --json 2>&1 |
                    Set-Content -LiteralPath (Join-Path $OutputDirectory "daemon-stop.json") -Encoding utf8
                if ($LASTEXITCODE -ne 0) { throw "Owned public daemon shutdown failed; no restart attempted" }
                if (-not $daemon.WaitForExit(30000)) { throw "Owned public daemon process did not exit" }
            }
        }
        catch {
            $_ | Out-String | Set-Content -LiteralPath (Join-Path $OutputDirectory "cleanup-error.log") -Encoding utf8
            if ($null -eq $firstFailure) { throw }
        }
    }
}
