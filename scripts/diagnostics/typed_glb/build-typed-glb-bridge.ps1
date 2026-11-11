[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Windows compile only; no COM creation' }
$compiler = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$pia = 'C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist\SolidWorks.Interop.sldworks.dll'
$expectedPia = 'a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1'
function Digest([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
if (!(Test-Path -LiteralPath $compiler -PathType Leaf) -or !(Test-Path -LiteralPath $pia -PathType Leaf)) { throw 'existing compiler/installed PIA required' }
if ((Digest $pia) -ne $expectedPia) { throw 'installed PIA differs from audited original' }
$target = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $target) { throw 'refuse existing output directory' }
$null = New-Item -ItemType Directory -Path $target
$record = [ordered]@{
    schema='swcli.typed-glb-build.v1'; success=$false; native_compile=$true; cad_operations=0
    compiler=$compiler; compiler_version=[Diagnostics.FileVersionInfo]::GetVersionInfo($compiler).FileVersion
    compiler_sha256=(Digest $compiler); pia_origin=$pia; pia_sha256=$expectedPia
    pia_version=[Diagnostics.FileVersionInfo]::GetVersionInfo($pia).FileVersion
    architecture='x64'; sources=[ordered]@{}; source_after=[ordered]@{}
}
try {
    $sourceFiles = @('BridgeCore.cs', 'TypedGlbBridge.cs')
    foreach ($name in $sourceFiles) { $record.sources[$name] = Digest (Join-Path $PSScriptRoot $name) }
    $piaCopy = Join-Path $target 'SolidWorks.Interop.sldworks.dll'
    Copy-Item -LiteralPath $pia -Destination $piaCopy
    if ((Digest $piaCopy) -ne $expectedPia -or (Digest $pia) -ne $expectedPia) { throw 'installed PIA changed during copy' }
    $helper = Join-Path $target 'TypedGlbBridge.exe'
    $arguments = @('/nologo', '/target:exe', '/platform:x64', '/langversion:5', '/optimize+', '/debug-', '/warnaserror+',
        ('/out:'+$helper), '/reference:System.dll', '/reference:System.Core.dll',
        '/reference:System.Runtime.Serialization.dll', ('/reference:'+$piaCopy))
    foreach ($name in $sourceFiles) { $arguments += Join-Path $PSScriptRoot $name }
    & $compiler @arguments 1> (Join-Path $target 'compile.stdout.log') 2> (Join-Path $target 'compile.stderr.log')
    $record.compiler_exit = $LASTEXITCODE
    foreach ($name in $sourceFiles) { $record.source_after[$name] = Digest (Join-Path $PSScriptRoot $name) }
    if ($record.compiler_exit -ne 0 -or !(Test-Path -LiteralPath $helper -PathType Leaf)) { throw 'actual installed PIA compilation failed; stop at zero CAD' }
    foreach ($name in $sourceFiles) { if ($record.sources[$name] -ne $record.source_after[$name]) { throw 'source changed during compile' } }
    if ((Digest $pia) -ne $expectedPia -or (Digest $piaCopy) -ne $expectedPia) { throw 'PIA changed during compile' }
    $image = [IO.File]::ReadAllBytes($helper)
    $peOffset = [BitConverter]::ToInt32($image, 0x3c)
    if ($image[0] -ne 0x4d -or $image[1] -ne 0x5a -or $peOffset -lt 0 -or $peOffset+26 -ge $image.Length -or
        [BitConverter]::ToUInt32($image,$peOffset) -ne 0x4550 -or
        [BitConverter]::ToUInt16($image,$peOffset+4) -ne 0x8664 -or
        [BitConverter]::ToUInt16($image,$peOffset+24) -ne 0x20b) { throw 'compiled helper is not AMD64 PE32+' }
    $record.helper_machine = 'AMD64'; $record.helper_optional_magic = 'PE32+'
    $record.helper_sha256 = Digest $helper
    $record.success = $true
} catch {
    $record.error = $_.Exception.ToString()
    throw
} finally {
    $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $target 'build.json') -Encoding UTF8
}
