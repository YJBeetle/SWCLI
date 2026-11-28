# 尺寸字体夹具与只读资格检查

夹具是一份合成的 SOLIDWORKS 33.5.0 工程图，使用安装版 GB 模板。两枚尺寸在同一张空白图纸的普通草图中，均为独立的水平线长度。任何涉及实际项目的图纸、模型或图框都不需要用于此验证。

## 最短建样步骤

1. 在统筹安排的可见 SOLIDWORKS 会话，新建 GB 单页图纸。跳过添加模型视图，保持普通图纸编辑模式。
2. 在纸面上方和下方各画一条互不相交的水平草图线。建议约 40 mm 和 55 mm，便于区分。用 Smart Dimension 分别标注两条线的长度，再退出草图编辑。[工程图草图](https://help.solidworks.com/2020/English/solidworks/sldworks/c_2D_sketching_in_drawings.htm)
3. 分别点选尺寸，打开 Other 中的 Dimension font。上方尺寸勾选 Use document font，下方尺寸清除此勾选，再用 Font 设 Courier New 20 pt。尺寸文字、公差和文档默认字体保持模板原值。[尺寸字体设置](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_DVE_DIMENSION_OTHER.htm)
4. 另存为 `dimensions-fixture-seed.SLDDRW` 并关闭。对最终文件运行 `Get-FileHash -LiteralPath <文件> -Algorithm SHA256`。记录完整摘要并结束用于建样的会话，把文件和记录交给统筹安排的 owned 验证环境。

已核对 Actions run `44820894046` 的合成 GB 空白图，文件 SHA-256 为 `e7e3d7448ad230d274a139a6c6c9f0b1063a85a77a11fee08a2c5adc8cc63041`。原件无模型引用，曾只读重开，可作为底稿来源。直接用安装 GB 模板新建即可完成同样的空白起点。当前仍待创建含两枚尺寸的成品。[空白图原生来源](https://github.com/YJBeetle/SWCLI/actions/runs/44820894046)

## 已排程的只读资格检查

使用随包精确 head 的源 ZIP、manifest、wheel 和 SHA-256。确认摘要后解包，安装 wheel 到专用 Windows Python 3.14 venv 并执行 `pip check`。用解包源码中的 `scripts/ci/prepare-font-scopes-next.py verify --head <完整提交> --package-dir <清单目录>` 核对 Git 内容。再用同一 venv 以 `python -I <解包源码>/scripts/ci/verify-font-scopes-next-offline.py --source-head <完整提交>` 核对安装字节和离线合同。

设置 `$python`、`$source`、`$head` 为 venv 解释器、解包后的 `source` 目录和完整候选 SHA。设置 `$swconst`、`$gbTemplate` 为本次 SOLIDWORKS 安装的类型库和 GB 模板。`$seed` 为合成图的绝对路径，`$seedSha` 为建样时记录的摘要，`$evidence` 为本次运行的新输出根目录。

```powershell
$ErrorActionPreference = "Stop"
if ($seedSha -notmatch "^[0-9a-fA-F]{64}$") { throw "Pass the recorded drawing SHA-256" }
$seedSha = $seedSha.ToLowerInvariant()
if ((Get-FileHash -LiteralPath $seed -Algorithm SHA256).Hash -ne $seedSha) {
    throw "Input drawing differs from the recorded SHA-256"
}
if (Test-Path -LiteralPath $evidence) { throw "Evidence directory must be new" }

$watchdog = Join-Path $source "scripts\ci\run-font-scopes-calibration.py"
$inputArgs = @("--profile", "next-fixture", "--scope", "dimensions", "--source-head", $head,
    "--swconst", $swconst, "--drawing-template", $gbTemplate,
    "--inheritance-drawing", $seed, "--inheritance-sha256", $seedSha)

$probe = Join-Path $evidence "supervision"
& $python -I $watchdog @inputArgs --supervision-probe --output-dir $probe
if ($LASTEXITCODE -ne 0) { throw "No-COM supervision failed. Preserve $probe" }

$qualification = Join-Path $evidence "qualification"
& $python -I $watchdog @inputArgs --output-dir $qualification
if ($LASTEXITCODE -ne 0) { throw "Read-only qualification failed. Preserve $qualification" }

$report = Get-Content -Raw -LiteralPath (Join-Path $qualification "native\report.json") | ConvertFrom-Json
if ($report.success -ne $true -or @($report.cases).Count -ne 1) { throw "Missing qualification case" }
$case = @($report.cases)[0]
if ($case.success -ne $true -or $case.scope -ne "dimensions" -or $case.source_head -ne $head -or
    $case.save_attempted -ne $false -or $case.reopen.read_only -ne $true -or
    $case.manual_input_sha256 -ne $seedSha -or $case.file_sha256 -ne $seedSha -or
    (Get-FileHash -LiteralPath $case.path -Algorithm SHA256).Hash -ne $seedSha -or
    (Get-FileHash -LiteralPath $seed -Algorithm SHA256).Hash -ne $seedSha) {
    throw "Qualification receipt differs from the pinned read-only drawing"
}
$case.reopened_observation.objects | ConvertTo-Json -Depth 8
```

资格报告分别记录 `inherited` 和 `local` 的原生及规范化字体。继承尺寸必须是 `use_document_font=true` 且有效字体等于文档默认，局部尺寸必须是 `false` 且有效字体有差异，两个显示尺寸的 API 标识必须不同。Courier New 20 pt 是标准建样值，资格门禁依据实际继承标志、有效差异和快照判断。检查不写文档字体，验证打开模式及输入、复制件字节不变。

后续内部验收在另一个新输出目录，以资格报告的 `case.path` 和 `case.file_sha256` 作为 `--profile internal --scope dimensions` 的输入。门禁比较毫米、磅两轮默认字体写入后的实际只读重开。继承尺寸须跟随默认值，局部尺寸的身份以及完整原生和规范化字体快照须保持。资格检查与内部组各最多 1800 秒，首错保留原始报告和 trace。每次复跑使用新证据目录。[内部验收命令](font-scopes-v025.md#已排程的-windows-执行)
