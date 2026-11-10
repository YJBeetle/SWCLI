param(
    [Parameter(Mandatory=$true)][string]$InteropPath,
    [Parameter(Mandatory=$true)][string]$SolidWorksExe,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
# Metadata only: target assembly code and custom-attribute constructors never run.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$report = [ordered]@{
    success = $false; evidence_kind = 'reflection-only-installed-interop'; model_calls = 0
    cad_object_activations = 0; native_binding_accepted = $false; interfaces = [ordered]@{}
    reflection_only_dependencies = @()
}
$taskDependencies = New-Object 'System.Collections.Generic.List[object]'
$taskResolver = $null
function Get-FileRecord([string]$Path) {
    $file = Get-Item -LiteralPath $Path
    $version = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($file.FullName)
    return [ordered]@{
        path = $file.FullName; size_bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        file_version = $version.FileVersion; product_version = $version.ProductVersion
    }
}
function Get-TypedArgument($Argument, [int]$Depth = 0) {
    if ($Depth -gt 8) { throw 'Attribute metadata exceeds depth bound' }
    $value = $Argument.Value
    if ($null -ne $value -and $Argument.ArgumentType.IsArray) {
        $value = @(foreach ($element in $value) { Get-TypedArgument $element ($Depth + 1) })
    } elseif ($value -is [System.Type]) {
        $value = $value.FullName
    } elseif ($null -ne $value -and $Argument.ArgumentType.IsEnum) {
        $value = [Convert]::ToInt64($value)
    }
    return [ordered]@{ type = $Argument.ArgumentType.FullName; value = $value }
}
function Get-MetadataAttributes($Member) {
    foreach ($attribute in [System.Reflection.CustomAttributeData]::GetCustomAttributes($Member)) {
        $named = [ordered]@{}
        foreach ($argument in $attribute.NamedArguments) {
            $named[$argument.MemberName] = Get-TypedArgument $argument.TypedValue
        }
        [ordered]@{
            type = $attribute.Constructor.DeclaringType.FullName
            constructor_arguments = @(foreach ($argument in $attribute.ConstructorArguments) { Get-TypedArgument $argument })
            named_arguments = $named
        }
    }
}
try {
    if ($PSVersionTable.PSEdition -ne 'Desktop') { throw 'Windows PowerShell Desktop is required for reflection-only metadata; no execution-load fallback' }
    $report['powershell'] = [ordered]@{
        version = $PSVersionTable.PSVersion.ToString(); edition = $PSVersionTable.PSEdition
        process_id = $PID; is_64_bit_process = [Environment]::Is64BitProcess
        clr_version = [Environment]::Version.ToString()
    }
    $report['interop_file'] = Get-FileRecord $InteropPath
    $report['solidworks_exe'] = Get-FileRecord $SolidWorksExe
    $taskInteropDirectory = [System.IO.Path]::GetDirectoryName($report.interop_file.path)
    # Dependencies are metadata-only, from this explicit folder or known framework names.
    $taskResolver = [ResolveEventHandler]({
        param($sender, $request)
        foreach ($loaded in [AppDomain]::CurrentDomain.ReflectionOnlyGetAssemblies()) {
            if ($loaded.FullName -eq $request.Name) { return $loaded }
        }
        if ($taskDependencies.Count -ge 16) { throw 'Reflection dependency bound exceeded' }
        $identity = New-Object -TypeName System.Reflection.AssemblyName -ArgumentList $request.Name
        if ($identity.Name -in @('mscorlib', 'System', 'System.Core', 'System.Runtime.InteropServices')) {
            $dependency = [System.Reflection.Assembly]::ReflectionOnlyLoad($request.Name)
        } else {
            $candidate = Join-Path $taskInteropDirectory ($identity.Name + '.dll')
            if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw ('Explicit-folder metadata dependency is unavailable: ' + $identity.Name) }
            $dependency = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($candidate)
        }
        if ($dependency.FullName -ne $request.Name -or -not $dependency.ReflectionOnly) { throw 'Reflection dependency identity differs' }
        $dependencyFile = Get-Item -LiteralPath $dependency.Location
        $dependencyVersion = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($dependencyFile.FullName)
        $taskDependencies.Add([ordered]@{
            path = $dependencyFile.FullName; size_bytes = $dependencyFile.Length
            sha256 = (Get-FileHash -LiteralPath $dependencyFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            file_version = $dependencyVersion.FileVersion; product_version = $dependencyVersion.ProductVersion
        })
        return $dependency
    }.GetNewClosure())
    [AppDomain]::CurrentDomain.add_ReflectionOnlyAssemblyResolve($taskResolver)
    $assembly = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($report.interop_file.path)
    if (-not $assembly.ReflectionOnly) { throw 'Interop was not loaded into reflection-only context' }
    $report['assembly'] = [ordered]@{
        full_name = $assembly.FullName; image_runtime_version = $assembly.ImageRuntimeVersion
        reflection_only = $assembly.ReflectionOnly; processor_architecture = $assembly.GetName().ProcessorArchitecture.ToString()
        attributes = @(Get-MetadataAttributes $assembly)
    }
    $targets = [ordered]@{ IModelDocExtension = @('SaveAs3'); IDimension = @('SetSystemValue3', 'GetSystemValue3') }
    foreach ($interfaceName in $targets.Keys) {
        $type = $assembly.GetType(('SolidWorks.Interop.sldworks.' + $interfaceName), $true, $false)
        $row = [ordered]@{
            full_name = $type.FullName; is_interface = $type.IsInterface; is_import = $type.IsImport
            attributes = @(Get-MetadataAttributes $type); methods = [ordered]@{}
        }
        $report.interfaces[$interfaceName] = $row
        foreach ($methodName in $targets[$interfaceName]) {
            $methods = @($type.GetMethods() | Where-Object { $_.Name -eq $methodName })
            if ($methods.Count -ne 1) { throw ('Required method is missing or ambiguous: ' + $interfaceName + '.' + $methodName) }
            $method = $methods[0]
            $methodRow = [ordered]@{
                name = $method.Name; return_type = $method.ReturnType.FullName
                implementation_flags = $method.GetMethodImplementationFlags().ToString()
                attributes = @(Get-MetadataAttributes $method)
                return_attributes = @(Get-MetadataAttributes $method.ReturnParameter); parameters = @()
            }
            $row.methods[$methodName] = $methodRow
            foreach ($parameter in $method.GetParameters()) {
                $parameterRow = [ordered]@{
                    position = $parameter.Position; name = $parameter.Name; type = $parameter.ParameterType.FullName
                    is_by_ref = $parameter.ParameterType.IsByRef; is_in = $parameter.IsIn
                    is_out = $parameter.IsOut; is_optional = $parameter.IsOptional
                    attributes = @(Get-MetadataAttributes $parameter)
                }
                $methodRow.parameters += $parameterRow
            }
        }
    }
    $report.success = $true
} catch {
    $report['first_error'] = [ordered]@{ type = $_.Exception.GetType().FullName; message = $_.Exception.Message }
} finally {
    if ($null -ne $taskResolver) { [AppDomain]::CurrentDomain.remove_ReflectionOnlyAssemblyResolve($taskResolver) }
    $report.reflection_only_dependencies = @($taskDependencies.ToArray())
    $json = ConvertTo-Json -InputObject $report -Depth 30
    [System.IO.File]::WriteAllText($OutputPath, $json + "`n", (New-Object System.Text.UTF8Encoding($false)))
}
if (-not $report.success) { exit 1 }
