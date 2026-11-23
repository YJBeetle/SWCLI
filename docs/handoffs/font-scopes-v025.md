# v0.2.5 尺寸与表格字体原生验证交接

候选分支 `codex/docprops-font-scopes-next` 保留旧候选历史，并以已发布的 `8408b8a657b6fdfb05dd47422cd5cdea9010a056` 为基线。夹具生成和字体校准均按 SaveAs3 的真实回执检查保存成功、错误码和警告码均为 0。随候选附带的 manifest 绑定完整提交和源码 ZIP。

## 可用入口

| 入口 | 检查内容 | 调度 |
| --- | --- | --- |
| 普通分支 push 的 [CI](../../.github/workflows/ci.yml) | Windows Python 3.9 和 3.14 单元测试、无 COM 的 venv 看门狗探针、SDK 和打包 | 使用现有工作流 |
| [字体专属原生工作流](../../.github/workflows/font-scopes-calibration.yml) | 旧字体分支的 `internal` 或 `public-notes` | 限旧分支 `codex/docprops-font-scopes`。本候选无受保护的 GitHub 原生入口 |
| 本页 Windows 命令 | 使用 SOLIDWORKS 33.5.0 的 owned 宿主，一轮一个 scope | 统筹给出独占时段后运行 |

先用表格占一个独占时段，依次跑无 COM 探针、夹具生成和内部继承验证。夹具组与内部组各有 1800 秒硬上限，每次调用上限 600 秒，建议为两组预留合计 60 分钟并另计安装。尺寸需要额外的手工建图时段，再以同样的上限依次资格检查和内部验证。实际耗时待首跑测量。

## 两份自建样件

- **表格** 由已安装的 GB 模板生成一个 1×2 General 表。整表与左格使用文档字体，右格用局部 Courier New 20 pt。首跑会产出第一份真实 `font-tables-fixture.SLDDRW`，检验 `Text2` 实际 COM 绑定与只读重开的结果。已有候选包没有合格的生成文件。
- **尺寸** 缺一份 GB 单页无模型视图的真实 `.SLDDRW`。其中有两个可被 API 分别枚举的显示尺寸，一个继承文档字体，一个为局部 Courier New 20 pt。按[尺寸自建清单](font-scopes-next-fixtures.md#尺寸手工建夹具清单)创建和关闭图纸，记录 SHA-256。自动入口负责在独立目录复制并只读核验。

## 已排程的 Windows 执行

在独立 Python 3.14 venv 安装与本候选同一提交的 wheel 并运行 `pip check`。以源码包的完整 head 和交付摘要为准，校验 ZIP、manifest 和 wheel，解包后执行 `prepare-font-scopes-next.py verify` 和 `verify-font-scopes-next-offline.py` 检查源包及安装字节。已排程窗口内选定一个 `$scope`，将 `$source`、`$head`、`$python`、`$evidence`、`$swconst` 和 `$gbTemplate` 指向解包源码、精确提交、venv 解释器、新证据根目录及官方类型库和模板。尺寸另外设置 `$dimensionsSeed` 和已独立记录的 `$dimensionsSha256`。

```powershell
$ErrorActionPreference = "Stop"
if ($scope -notin @("tables", "dimensions")) { throw "Select exactly one font scope" }
if (Test-Path -LiteralPath $evidence) { throw "Evidence directory must be new" }
$watchdog = Join-Path $source "scripts\ci\run-font-scopes-calibration.py"
$common = @("--scope", $scope, "--swconst", $swconst, "--drawing-template", $gbTemplate, "--source-head", $head)
$inputDrawing = @()
if ($scope -eq "dimensions") {
    if ($dimensionsSha256 -cnotmatch "^[0-9a-f]{64}$") { throw "Pin the synthetic dimension drawing's SHA-256" }
    $inputDrawing = @("--inheritance-drawing", $dimensionsSeed, "--inheritance-sha256", $dimensionsSha256)
}

$probe = Join-Path $evidence "supervision"
& $python -I $watchdog --profile next-fixture --supervision-probe --output-dir $probe @common @inputDrawing
if ($LASTEXITCODE -ne 0) { throw "Supervision probe failed. Preserve $probe" }
$p = Get-Content -Raw -LiteralPath (Join-Path $probe "watchdog.json") | ConvertFrom-Json
if (-not $p.success -or -not $p.supervision_verified -or $p.native_executed -ne $false) {
    throw "Missing no-COM launch proof"
}

$fixture = Join-Path $evidence "fixture"
& $python -I $watchdog --profile next-fixture --output-dir $fixture @common @inputDrawing
if ($LASTEXITCODE -ne 0) { throw "Fixture preparation failed. Preserve $fixture" }
$f = Get-Content -Raw -LiteralPath (Join-Path $fixture "native\report.json") | ConvertFrom-Json
$prepared = @($f.cases)[0]
if (-not $f.success -or @($f.cases).Count -ne 1 -or -not $prepared.success -or $prepared.scope -ne $scope) {
    throw "Missing qualified drawing"
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $prepared.path).Hash -ne $prepared.file_sha256) {
    throw "Qualified drawing hash changed"
}

$internal = Join-Path $evidence "internal"
& $python -I $watchdog --profile internal --output-dir $internal @common --inheritance-drawing $prepared.path --inheritance-sha256 $prepared.file_sha256
if ($LASTEXITCODE -ne 0) { throw "Internal inheritance gate failed. Preserve $internal" }
$r = Get-Content -Raw -LiteralPath (Join-Path $internal "native\report.json") | ConvertFrom-Json
$drawings = @($r.cases | Where-Object { $_.kind -eq "drawing" })
if (-not $r.success -or @($r.cases).Count -ne 3 -or $drawings.Count -ne 1 -or -not $drawings[0].inheritance_witness.success) {
    throw "Missing internal inheritance witness"
}
```

交付三组的原始 `watchdog.json`、`native/supervision.json` 和日志，保留原生报告、trace、夹具与六份保存文件。表格另交五类默认值的只读 JSONL。内部门禁验证毫米、磅两种模式保存后只读重开时，继承对象随默认字体变化，局部字体保持，零件几何符合现有容差。失败时保留第一个错误及清理回执，停止该组。公开能力仍限已验收的 Notes。

历史包及验证日志见[原 Windows 安装交接](font-scopes-next-windows-supervision.md)。使用对应提交的 verifier 核对旧包。
