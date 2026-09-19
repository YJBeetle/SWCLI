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

function Invoke-SwCliJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )
    $outputPath = Join-Path $Workspace "$Name.json"
    $stderrPath = Join-Path $Workspace "$Name.stderr.log"
    $python = (Get-Command python -ErrorAction Stop).Source
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList (@("-m", "swcli") + $Arguments) `
        -RedirectStandardOutput $outputPath `
        -RedirectStandardError $stderrPath `
        -NoNewWindow `
        -Wait `
        -PassThru
    if ($process.ExitCode -ne 0) {
        $stderr = Get-Content $stderrPath -Raw -ErrorAction SilentlyContinue
        throw "sw-cli $Name failed with exit code $($process.ExitCode)`n$stderr"
    }
    $payload = Get-Content $outputPath -Raw -Encoding utf8 | ConvertFrom-Json
    if ($payload.PSObject.Properties.Name -contains "ok" -and -not $payload.ok) {
        throw "sw-cli $Name returned ok=false"
    }
    return $payload
}

Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$python = (Get-Command python -ErrorAction Stop).Source
$daemonStdout = Join-Path $Workspace "swclid.stdout.log"
$daemonStderr = Join-Path $Workspace "swclid.stderr.log"
$daemon = Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "swcli.daemon", "serve", "--startup-timeout", "120") `
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
        $stderr = Get-Content $daemonStderr -Raw -ErrorAction SilentlyContinue
        throw "swclid exited during startup with code $($daemon.ExitCode)`n$stderr"
    }
    if ((Test-Path -LiteralPath $daemonStdout) -and
        (Select-String -LiteralPath $daemonStdout -SimpleMatch '"action": "daemon.serve"' -Quiet)) {
        $daemonReady = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $daemonReady) {
    throw "swclid did not become ready within 180 seconds"
}

$started = $true
try {
    $probe = Invoke-SwCliJson -Name "host-probe-before" -Arguments @("host", "probe", "--json")
    if (-not $probe.supported) {
        throw "SWCLI does not recognize this runner as a supported Windows host"
    }
    if (-not $probe.registration.local_server_exists) {
        throw "SOLIDWORKS LocalServer32 registration is missing or points to a missing executable"
    }

    Invoke-SwCliJson -Name "part-create-box" -Arguments @(
        "part", "create-box", $partPath,
        "--width-mm", "100", "--height-mm", "50", "--depth-mm", "20", "--json"
    ) | Out-Null
    Invoke-SwCliJson -Name "document-inspect" -Arguments @("document", "inspect", "--detail", "structure", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-diagnose" -Arguments @("document", "diagnose", "--json") | Out-Null
    Invoke-SwCliJson -Name "document-render" -Arguments @(
        "document", "render", $renderPath,
        "--view", "isometric", "--width", "800", "--height", "600", "--json"
    ) | Out-Null
    Invoke-SwCliJson -Name "document-export" -Arguments @("document", "export", $stepPath, "--json") | Out-Null
    Invoke-SwCliJson -Name "document-close" -Arguments @("document", "close", "--discard", "--json") | Out-Null
    & $python -m swcli.daemon stop --json | Set-Content -Path (Join-Path $Workspace "swclid-stop.json") -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "swclid graceful shutdown failed with exit code $LASTEXITCODE"
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
}
finally {
    if ($started) {
        & python -m swcli document close --discard --json 2>&1 |
            Set-Content -Path (Join-Path $Workspace "cleanup-close.log") -Encoding utf8
        & python -m swcli.daemon stop --json 2>&1 |
            Set-Content -Path (Join-Path $Workspace "cleanup-daemon-stop.log") -Encoding utf8
        if (-not $daemon.HasExited) {
            Stop-Process -Id $daemon.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
