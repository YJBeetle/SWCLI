[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$OutputDirectory)
$ErrorActionPreference = "Stop"
if ($env:GITHUB_ACTIONS -ne "true" -or $env:GITHUB_EVENT_NAME -ne "workflow_dispatch" -or
    $env:GITHUB_REF -ne "refs/heads/codex/docprops-font-scopes") {
    throw "This calibration is restricted to the authorized branch on a disposable GitHub runner"
}
$drawingTemplate = & python -I scripts/ci/gate_support/drawing_template.py --program-data $env:ProgramData --installation "C:\Program Files\SOLIDWORKS"
if ($LASTEXITCODE -ne 0) { throw "Official drawing template discovery failed" }
python -I scripts/ci/run-font-scopes-calibration.py `
    --output-dir $OutputDirectory `
    --swconst "C:\Program Files\SOLIDWORKS\swconst.tlb" `
    --drawing-template $drawingTemplate
if ($LASTEXITCODE -ne 0) { throw "Font scope calibration stopped; inspect original watchdog, trace and first failure" }
