# Windows example: native editable plate + four circular cuts + verified exports.
# Requires a running daemon advertising the a4 modeling operations. No COM code.
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$OutputDirectory)

$ErrorActionPreference = "Stop"
$session = "plate-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
$output = Get-Item -LiteralPath $OutputDirectory -ErrorAction Stop
if (-not $output.PSIsContainer) { throw "OutputDirectory must be an existing local directory" }
$directory = $output.FullName
$nativePath = Join-Path $directory "plate.SLDPRT"
$stepPath = Join-Path $directory "plate.STEP"
$previewPath = Join-Path $directory "plate.bmp"
foreach ($path in @($nativePath, $stepPath, $previewPath)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite $path" }
}

function Invoke-ModelCli([string[]]$Arguments) {
    # SWCLI emits UTF-8; Windows PowerShell 5.1 may decode native pipes as CP936.
    $previousEncoding = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        $text = & sw-cli --session $session @Arguments --json
        $exitCode = $LASTEXITCODE
    }
    finally { [Console]::OutputEncoding = $previousEncoding }
    if ($exitCode -ne 0) { throw ($text -join "`n") }
    $result = ($text -join "`n") | ConvertFrom-Json
    if (-not $result.ok) { throw "SWCLI did not return a successful CAD result" }
    return $result
}

$part = Invoke-ModelCli -Arguments @("document", "create")
$documentId = $part.document.document_id
$lease = Invoke-ModelCli -Arguments @("document", "lease", "acquire", "--document", $documentId, "--ttl-seconds", "120")
$leaseId = $lease.lease.lease_id
$guard = @("--document", $documentId, "--lease", $leaseId)
try {
    $outline = Invoke-ModelCli -Arguments (@("sketch", "rectangle", "--plane", "front", "--width-mm", "100", "--height-mm", "60") + $guard)
    Invoke-ModelCli -Arguments (@("feature", "extrude", $outline.sketch.sketch_id, "--depth-mm", "8") + $guard) | Out-Null
    foreach ($center in @(@(-30, -15), @(30, -15), @(30, 15), @(-30, 15))) {
        Invoke-ModelCli -Arguments @("document", "lease", "renew", $leaseId, "--ttl-seconds", "120") | Out-Null
        $hole = Invoke-ModelCli -Arguments (@("sketch", "circle", "--plane", "front", "--radius-mm", "4", "--center-x-mm", $center[0], "--center-y-mm", $center[1]) + $guard)
        Invoke-ModelCli -Arguments (@("feature", "cut-extrude", $hole.sketch.sketch_id, "--depth-mm", "8") + $guard) | Out-Null
    }
    $measurement = Invoke-ModelCli -Arguments @("document", "measure", "--document", $documentId)
    $expectedVolume = 100 * 60 * 8 - 4 * [Math]::PI * 4 * 4 * 8
    $expectedArea = 2 * 100 * 60 + 2 * (100 + 60) * 8 + 128 * [Math]::PI
    if ($measurement.metrics.solid_body_count -ne 1 -or
        [Math]::Abs($measurement.metrics.volume_mm3 - $expectedVolume) -gt 0.00001 -or
        [Math]::Abs($measurement.metrics.surface_area_mm2 - $expectedArea) -gt 0.00001) {
        throw "Measured geometry does not match the four-hole plate"
    }
    $diagnosis = Invoke-ModelCli -Arguments @("document", "diagnose", "--document", $documentId)
    if (-not $diagnosis.diagnostics.healthy -or $diagnosis.needs_rebuild -ne 0) { throw "Model requires repair" }
    Invoke-ModelCli -Arguments (@("document", "save-as", $nativePath) + $guard) | Out-Null
    Invoke-ModelCli -Arguments (@("document", "export", $stepPath, "--strict") + $guard) | Out-Null
    Invoke-ModelCli -Arguments (@("document", "render", $previewPath, "--view", "isometric", "--width", "800", "--height", "600") + $guard) | Out-Null
    Invoke-ModelCli -Arguments @("document", "lease", "release", $leaseId) | Out-Null
    $leaseId = $null
    Invoke-ModelCli -Arguments @("document", "close", "--document", $documentId) | Out-Null
}
finally {
    # On failure, release our lease but retain any partial model for inspection.
    # Do not silently discard, save, retry, restart a host, or promise rollback.
    if ($null -ne $leaseId) {
        try { Invoke-ModelCli -Arguments @("document", "lease", "release", $leaseId) | Out-Null }
        catch { Write-Warning "Lease release failed; wait for TTL expiry: $($_.Exception.Message)" }
    }
}

Invoke-ModelCli -Arguments @("document", "open", $nativePath, "--read-only") | Out-Null
$reopened = Invoke-ModelCli -Arguments @("document", "measure")
if ([Math]::Abs($reopened.metrics.volume_mm3 - $measurement.metrics.volume_mm3) -gt 0.00001 -or
    [Math]::Abs($reopened.metrics.surface_area_mm2 - $measurement.metrics.surface_area_mm2) -gt 0.00001) {
    throw "Saved/reopened geometry changed; inspect the retained document"
}
Invoke-ModelCli -Arguments @("document", "close") | Out-Null
[PSCustomObject]@{ native = $nativePath; step = $stepPath; preview = $previewPath; metrics = $reopened.metrics } | ConvertTo-Json -Depth 5
