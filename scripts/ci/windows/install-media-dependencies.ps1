$ErrorActionPreference = "Stop"

# Chocolatey's community feed can return a 503 with a misleading exit code 0.
# Retry only these bootstrap dependencies, and verify the actual commands.
$attemptLimit = 3
for ($attempt = 1; $attempt -le $attemptLimit; $attempt++) {
    choco install rclone imdisk --yes --no-progress
    $installExitCode = $LASTEXITCODE
    $missing = @(@("rclone", "imdisk.exe") | Where-Object {
        -not (Get-Command $_ -ErrorAction SilentlyContinue)
    })
    if ($installExitCode -eq 0 -and $missing.Count -eq 0) {
        Write-Host "[Media dependencies] Verified rclone and ImDisk (attempt $attempt)"
        return
    }

    $detail = "Chocolatey exit code $installExitCode; missing commands: $($missing -join ', ')"
    if ($attempt -eq $attemptLimit) {
        throw "rclone/ImDisk installation failed after $attemptLimit attempts: $detail"
    }
    Write-Warning "Media dependency attempt $attempt failed: $detail; retrying in 10 seconds"
    Start-Sleep -Seconds 10
}
