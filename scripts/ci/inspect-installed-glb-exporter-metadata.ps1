param(
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
# Parse data only. No target assembly loading, trust/chain checks or COM activation.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$fixedRoot = 'C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS'
$allowed = @('sldgltfu.dll', 'spiop/files/code/bin/SPAXGLTFBase.dll',
             'spiop/files/code/bin/SPAXGLTFVisualization.dll', 'spiop/files/code/bin/VisGltf.dll',
             'SWXRExporter.dll', 'SWXRExporter.tlb')
$report = [ordered]@{ success=$false; kind='data-only-file-version-and-embedded-CMS-metadata'
    target_dll_loads=0; cad_activations=0; network_verification=$false; signature_verified=$false; files=@() }
$outputSafe = $false
function Assert-PlainParents([string]$Path) {
    $parent = [System.IO.Directory]::GetParent($Path)
    while ($null -ne $parent) {
        $info = Get-Item -LiteralPath $parent.FullName -Force
        if (-not $info.PSIsContainer -or ($info.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw 'Non-plain or reparse parent directory'
        }
        $parent = $parent.Parent
    }
}
function Get-PlainFile([string]$Path) {
    Assert-PlainParents $Path
    $info = Get-Item -LiteralPath $Path -Force
    if ($info.PSIsContainer -or ($info.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw 'Source must be a regular non-reparse file'
    }
    return $info
}
try {
    if ($PSVersionTable.PSEdition -ne 'Desktop' -or -not [Environment]::Is64BitProcess) {
        throw 'Existing native 64-bit Windows PowerShell Desktop is required'
    }
    if (-not [System.IO.Path]::IsPathRooted($OutputPath) -or -not [System.IO.Path]::IsPathRooted($RequestPath)) {
        throw 'Absolute request/output paths required'
    }
    $fullOutput = [System.IO.Path]::GetFullPath($OutputPath)
    foreach ($blocked in @($fixedRoot, 'C:\Windows\System32', 'C:\Windows\SysWOW64')) {
        if ($fullOutput.Equals($blocked, [StringComparison]::OrdinalIgnoreCase) -or
            $fullOutput.StartsWith($blocked + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Output cannot modify inspected locations'
        }
    }
    Assert-PlainParents $fullOutput
    if (Test-Path -LiteralPath $fullOutput) { throw 'Metadata output already exists' }
    $outputSafe = $true
    $requestFile = Get-PlainFile $RequestPath
    if ($requestFile.Length -gt 16777216) { throw 'Metadata request exceeds bound' }
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($request.install_root -cne $fixedRoot -or @($request.files).Count -gt 6) { throw 'Fixed root/file count differs' }
    $seen = @{}
    # System.Security is the existing framework decoder, never an inspected DLL.
    Add-Type -AssemblyName System.Security
    foreach ($item in @($request.files)) {
        $relative = [string]$item.relative_path
        if (-not ($allowed -ccontains $relative) -or $seen.ContainsKey($relative)) { throw 'Unexpected/duplicate fixed relative file' }
        $seen[$relative] = $true
        if ($item.expected_sha256 -cnotmatch '^[0-9a-f]{64}$' -or @($item.certificates).Count -gt 16) { throw 'Invalid metadata input bounds' }
        $path = Join-Path $fixedRoot ($relative.Replace([char]'/', [System.IO.Path]::DirectorySeparatorChar))
        $before = Get-PlainFile $path
        if ($before.Length -gt 268435456) { throw 'Source byte bound exceeded' }
        $beforeState = @($before.Length, $before.LastWriteTimeUtc.Ticks, [int]$before.Attributes)
        $row = [ordered]@{ relative_path=$relative; path=$path; version=[ordered]@{status='unknown'}
            signature=[ordered]@{status='metadata_only'; cryptographic_validity='unknown_not_verified'
                catalog_signature='unknown_not_queried'; entries=@()} }
        $report.files += $row
        $row['sha256_before'] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($row.sha256_before -cne $item.expected_sha256) { throw 'Input bytes differ before metadata read' }
        try {
            $version = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($path)
            $row.version = [ordered]@{status='observed'; file_version=$version.FileVersion; product_version=$version.ProductVersion
                file_description=$version.FileDescription; company_name=$version.CompanyName
                fixed_file_version=@($version.FileMajorPart,$version.FileMinorPart,$version.FileBuildPart,$version.FilePrivatePart)
                fixed_product_version=@($version.ProductMajorPart,$version.ProductMinorPart,$version.ProductBuildPart,$version.ProductPrivatePart)}
            if ([string]::IsNullOrEmpty($version.FileVersion) -and [string]::IsNullOrEmpty($version.ProductVersion)) {
                $row.version.status = 'no_version_strings_observed'
            }
        } catch {
            $row.version = [ordered]@{status='unknown'; error_type=$_.Exception.GetType().FullName; message=$_.Exception.Message}
        }
        foreach ($encoded in @($item.certificates)) {
            if ($encoded.Length -gt 1398104) { throw 'CMS payload exceeds bound' }
            $entry = [ordered]@{status='unknown'; signers=@()}
            $row.signature.entries += $entry
            try {
                $cms = New-Object System.Security.Cryptography.Pkcs.SignedCms
                $cms.Decode([Convert]::FromBase64String($encoded))
                if ($cms.SignerInfos.Count -gt 16 -or $cms.Certificates.Count -gt 64) { throw 'CMS metadata count exceeds bound' }
                foreach ($signer in $cms.SignerInfos) {
                    $certificate = $signer.Certificate
                    $description = [ordered]@{digest_algorithm=$signer.DigestAlgorithm.Value; certificate=$null}
                    if ($null -ne $certificate) {
                        $description.certificate = [ordered]@{subject=$certificate.Subject; issuer=$certificate.Issuer
                            thumbprint=$certificate.Thumbprint; serial_number=$certificate.SerialNumber
                            not_before_utc=$certificate.NotBefore.ToUniversalTime().ToString('o')
                            not_after_utc=$certificate.NotAfter.ToUniversalTime().ToString('o')}
                    }
                    $entry.signers += $description
                }
                $entry.status = 'decoded_metadata_only_not_verified'
            } catch {
                $entry['error_type'] = $_.Exception.GetType().FullName
                $entry['message'] = $_.Exception.Message
            }
        }
        $row['sha256_after'] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        $after = Get-PlainFile $path
        $afterState = @($after.Length, $after.LastWriteTimeUtc.Ticks, [int]$after.Attributes)
        if ($row.sha256_after -cne $row.sha256_before -or
            (Compare-Object $beforeState $afterState)) { throw 'Input changed while metadata was read' }
    }
    $report['powershell'] = [ordered]@{edition=$PSVersionTable.PSEdition; version=$PSVersionTable.PSVersion.ToString(); is_64_bit_process=[Environment]::Is64BitProcess}
    $report.success = $true
} catch {
    $report['first_error'] = [ordered]@{type=$_.Exception.GetType().FullName; message=$_.Exception.Message}
} finally {
    if ($outputSafe) {
        $encoding = New-Object System.Text.UTF8Encoding($false)
        $bytes = $encoding.GetBytes((ConvertTo-Json -InputObject $report -Depth 20) + "`n")
        if ($bytes.Length -gt 16777216) {
            if (-not $report.Contains('first_error')) {
                $report['first_error'] = [ordered]@{type='ResponseBoundExceeded'; message='Metadata response exceeds byte bound'}
            }
            $report.success = $false
            $report.files = @()
            $report['metadata_omitted'] = 'response byte bound exceeded'
            $bytes = $encoding.GetBytes((ConvertTo-Json -InputObject $report -Depth 20) + "`n")
        }
        $stream = [System.IO.File]::Open($OutputPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
        try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
    } elseif ($report.Contains('first_error')) {
        [Console]::Error.WriteLine((ConvertTo-Json -InputObject $report.first_error -Compress))
    }
}
if (-not $report.success) { exit 1 }
