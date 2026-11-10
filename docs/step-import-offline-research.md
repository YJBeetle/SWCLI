# STEP 导入失败：离线研究与一次取证方案（2026-11-08）

本轮产物是可复跑的离线证据和导入取证补丁，尚无已证明的原生修复。没有启动 CAD、VM 或新 CI。当前 STEP 仍受原生读回失败阻塞，不能据此合并或发布。

## 原件与比较范围

保留的两个失败运行是 [42405019483](https://github.com/YJBeetle/SWCLI/actions/runs/42405019483)（`b363751`，Neutral 配置）和 [42413805736](https://github.com/YJBeetle/SWCLI/actions/runs/42413805736)（`060f261`，General 配置）。成功对照为 [42303929271](https://github.com/YJBeetle/SWCLI/actions/runs/42303929271)（`ee7f0ea`，早于后续保护修复，不能替代当前 head 的验收）。

| 文件 | b363751 字节数 | 060f261 字节数 | 首差异偏移（从 0 起） | 根可达曲线 / 总长 mm |
| --- | ---: | ---: | ---: | --- |
| ap203-wireframe.step | 10581 | 10595 | 102 | 12 / 320 |
| ap214-wireframe.step | 7085 | 7086 | 102 | 12 / 320 |
| ap203-wireframe-sketches.step | 14787 | 14796 | 112 | 18 / 560 |
| ap214-wireframe-sketches.step | 11200 | 11203 | 111 | 18 / 560 |
| mcp-ap203-wireframe.step | 10597 | 10608 | 106 | 12 / 320 |

五对文件字节不相同；逐对实体类型直方图、显式线性几何及重复曲线数量相同。成功对照的五个对应文件也得到相同几何签名。几何签名保留曲线类型、端点和重复项，不包含编号、文件头、实体顺序或样条参数化，因此不能声称字节差异“仅为元数据”。文件 SHA256、具体接口元数据和分类结论见 [机器可读记录](evidence/step-import-offline-2026-11-08.json)。

分析器从 `SHAPE_DEFINITION_REPRESENTATION` 到 wire representation、`GEOMETRIC_CURVE_SET` 再到曲线成员追踪引用，不用全局曲线计数替代根可达性。检查结果：

- AP203 的 FILE_SCHEMA 为 `CONFIG_CONTROL_DESIGN`，AP214 为 `AUTOMOTIVE_DESIGN`；SI 长度单位均为 milli metre。没有重复 ID、悬空引用或孤立曲线。
- 纯线框为 12 条 degree-1、两个控制点、重数 2/2 且结点递增的 `B_SPLINE_CURVE_WITH_KNOTS`，总长 320 mm；草图版本另有 6 条以 LINE 为基础的 `TRIMMED_CURVE`，总长 560 mm。裁剪点与线参数一致。
- 基础长方体图有 8 顶点、12 边、1 连通分量，每个顶点度数 3，循环秩 5；六个坐标平面边界各有 4 边且各顶点度数 2，周长为 80、100、140 mm 各两组。
- 每条样条都是开放的单独边（closed flag `.F.`）；组合几何包含上述闭合边界。wire 文件没有 `EDGE_CURVE` 或 `MANIFOLD_SOLID_BREP`，几何图闭合不等于实体 BREP 拓扑。

这些结果排除了已检查线性夹具的缺线、不可达曲线、单位缩放和长度不完整；不是完整 EXPRESS/AP203/AP214 合规验证，也不能证明某个 SOLIDWORKS 导入配置支持该表示。

离线重现（只读原始 STEP 文件）：

```sh
.venv/bin/python scripts/ci/analyze-step-wire-evidence.py \
  --left step-evidence/public-original-42405019483/swcli-native-smoke/step-public \
  --right step-evidence/public-original-42413805736/swcli-native-smoke/step-public \
  --output step-evidence/wire-byte-semantic-comparison.json
```

将 left 换为 `public-original-42303929271` 可复核成功对照。完整本地报告分别为 `wire-byte-semantic-comparison.json`、`wire-success-control-comparison.json`，原 ZIP 不修改、不上传。

## 已安装接口合同与运行时未知项

只读解析了本机安装的 SOLIDWORKS 2025 TLB 和互操作程序集，没有执行它们。程序集版本 `33.5.0.53`；`swconst.tlb` SHA256 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6` 与原生 CI 输入相同。本机 `sldworks.tlb` SHA256 为 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`；旧 CI 未记录该库 hash，因此不能将本机库等同于 CI 实际库。

| 合同 | 安装元数据 | 能推出什么 |
| --- | --- | --- |
| ISldWorks.GetImportFileData | DISPID 217；`object GetImportFileData(string FileName)`；返回按 IDispatch 封送 | 静态返回类型不证明实际对象是 STEP 数据接口 |
| ISldWorks.LoadFile4 | DISPID 227；`ModelDoc2 LoadFile4(string FileName, string ArgString, object ImportData, ref int32 Errors)` | 必须分别记录返回指针、错误码和对象类型 |
| IImportStepData | IID `AD749A73-9AA2-4A3E-BCA5-8FC012114BB0`；MapConfigurationData bool get/set，DISPID 1 | 未发现 STEP 的 CurvesAsSketches 属性 |
| IImportIgesData | IID `57988505-3843-4124-9CBE-AF121D9E0BE8`；IncludeSurfaces、IncludeCurves、CurvesAsSketches | 是不同接口，不能将 IGES 属性直接套给 STEP |

[官方 IImportStepData](https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IImportStepData.html) 描述 GetImportFileData → 导入数据对象 → LoadFile4 路径。[MapConfigurationData](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IImportStepData~MapConfigurationData.html) 控制配置映射和几何、默认来自 `swImportStepConfigData`，对象设置可覆盖单次导入的全局设置；它不是曲线表示开关。旧运行没有记录实际接口 QI 或该属性值，配置映射是否参与失败仍未知。

[LoadFile4 参数文档](https://help.solidworks.com/2015/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~LoadFile4.html) 中 STEP 的小写 `r` 表示创建新模型，`i` 表示插入现有模型；`r` 不表示只读，也不选择曲线表示。本补丁保持 `r`。

[General API 选项](https://help.solidworks.com/2019/English/api/swconst/FileOpenOptionsGeneral.htm)、[Neutral API 选项](https://help.solidworks.com/2019/English/api/swconst/FileOpenOptionsSTEPIGESACIS.htm) 与 [3D Interconnect 关闭后的 General 界面](https://help.solidworks.com/2026/english/solidworks/sldworks/hidd_options_import_general.htm) 提供选项语义，不能单凭名称证明 2025 translator 实际读取哪组值或优先顺序。安装常量如下，诊断中仍从实际 TLB 解析，不硬编码这些 ID：

| 类型 | General | Neutral / 其他 |
| --- | --- | --- |
| Toggle | SolidSurface 161；FreeCurves 162 | NeutralSolid 686；NeutralFree 687；StepConfigData 183；3DInterconnect 691 |
| IntegerValue | CurvePreference 206 | CurvesAndPointsOption 578 |
| 曲线表示枚举 | AsSketches 0；As3dCurves 1 | AsSketches 0；As3DCurves 1 |

当前原件显示 General 的四项设置成功读回和恢复，但第二个 AP203 wire `LoadFile4` error=1，尚无可测文档。先前日志路径暗示返回 None，却没有直接指针记录；不能把缺少读回当成 0 条几何。更早 9 条 / 260 mm 的原因也仍未知。早期同几何文件曾完成 8/8 原生读回，故没有证据支持“原生系统完全不支持 wireframe 导入”的笼统结论；当前参考曲线模式能否支持，仍需区分。

## 本补丁的边界

`scripts/ci/gate_support/step_import_observation.py` 增加只读诊断：实际安装 TLB 的 STEP/IGES IID；八项 General、Neutral、3D Interconnect、配置映射上下文；实际对象 type-info/QI；确认 STEP 接口后才读取 MapConfigurationData；LoadFile4 的返回/异常/错误码；成功文档类型、标题和路径。未知项显式标记 unknown，诊断异常不替换首个 CAD 错误。每个 API 诊断仍受现有有界调用保护。

表示类型不符时，先收集所有支持的 sketch/reference 特征与长度，再拒绝该表示，`complete=false`。不会把收集到足量几何转为通过。原有 12/18 数量、长度向量、体积/面积/总长阈值、质心与各段 1e-9 mm、错误码 0、原生保存/只读重开及清理条件不变。

没有改变 General 三项 Toggle 加一项 Integer 的期望值、MapConfigurationData、公开参数、工作流、生产适配器或 SaveAs3 迁移。没有 API 重试、重导入、重建、修复、回滚或重启分组。

## 交由统筹审核的一次判别验证（本轮不执行）

目的是在保持 `060f261` General 配置的条件下，区分实际接口/上下文、无文档失败和表示类型观测不足。不是选项扫描，也不重新导出模型。

1. 只在获准的受保护原生 Windows 环境执行；记录诊断提交的完整 head 到 `GITHUB_SHA`，隔离占用和清理规则沿用当前 reader。固定原件为运行 `42413805736` 的 artifact `13591430613`，ZIP SHA256 必须为 `de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7`。验证后解压到独立证据目录，不改 ZIP 或原报告。
2. 原 `swcli-native-smoke/step-public-readback/source-public-report.json` 必须 success=true、source_commit=`060f26178b4deabc330ef0959b9ec0f1704159cf` 且有 8 项 outputs。对八个原文件逐一核对 receipt SHA256，再将字节恢复至报告记录的原路径 `D:\a\_temp\swcli-native-smoke\step-public\...`（runner 原 RUNNER_TEMP）。目标不存在才复制；若已有文件，只允许其 hash 完全相同；不覆盖不同字节，不改报告路径适配另一个 runner。
3. 再次核对八个目标文件 hash，确认新 output-dir 不存在，按下列形式只运行一次现有 reader。`originalRoot` 是已验 hash 并解压的原件目录，`GITHUB_SHA` 必须是诊断代码 head。前置检查失败即停止，不启动 CAD。

```powershell
$originalRoot = Join-Path $env:RUNNER_TEMP 'step-original-42413805736'
$report = Join-Path $originalRoot 'swcli-native-smoke\step-public-readback\source-public-report.json'
$diagnostic = Join-Path $env:RUNNER_TEMP ('step-original-import-diagnostic-' + $env:GITHUB_RUN_ID)
python scripts/ci/verify-step-export-calibration.py `
  --export-report $report `
  --output-dir $diagnostic `
  --swconst 'C:\Program Files\SOLIDWORKS\swconst.tlb'
```

4. 仍是完整 8 文件计划、一个自有 reader host、每文件至多一次 GetImportFileData / LoadFile4。首失败停止；600 秒原生调用 / 1800 秒分组 watchdog；不重启、不清除首次失败、不替换 profile、不写 MapConfigurationData。保留完整 ZIP、报告、trace、输入库 hash 与退出证据。生产 SaveAs3 迁移另由其 owner 处理。

| 观察 | 解释与后续边界 |
| --- | --- |
| QI/类型信息错误或 unknown | 接口来源尚未证明；不能猜 STEP/IGES 转换，也不能用静态元数据补作运行时事实 |
| 某组设置无法读取 | 该上下文 unknown；不作优先级结论或自动改值 |
| 返回 None / error=1 | 没有可测文档；几何 unavailable，不能记录成 0 或继续保存 |
| 有完整几何但含不允许的 sketch 表示 | 保存完整部分观测，严格表示断言仍失败；不改为成功 |
| 全部 8 项读回、保存、重开、恢复、退出都成功 | 只证明原件在该诊断配置/环境的读回；集成生产变更后仍需精确 head 的新公开端到端验收 |

只有统筹审核这份方案后才安排一次必要原生验证。本轮不 dispatch，不以旧 head 或离线几何一致性替代新 head 的原生证据。

便携验证：48 项 STEP 回归通过；全量 1867 项通过，26 项跳过。最新原件报告的 head、success 与八个文件 hash，以及上述三个运行的原 ZIP hash 均已重新核对。便携结果不构成新 head 的原生验收。

## 已接线的独立手动诊断入口（2026-11-10，待统筹亲审）

采用现有 `ci.yml` 内的独立 profile，避免为新 workflow 修改 main。输入 `native_step_import_diagnostic` 默认 false；仅手动、精确仓库/专用分支、`native_step_import_head == github.sha` 可进入。`native_full`、`native_step_targeted`、`native_step_public_targeted` 必须全部 false。独立 concurrency group 为 `swcli-step-export-diagnostic-{ref}`，不取消其他运行。内部、公开和完整测试不能同时执行。

本模式调用 `prepare-step-import-original.py prepare`，顺序在分发包下载、私有路径初始化、凭据配置、私有输入读取及 CAD 安装之前。它先要求：

- event/完整 head/checkout/workflow SHA 一致，workflow 路径及分支固定，当前 `run_attempt=1`；重跑原工作流被拒绝。runner temp 必须等于原路径 `D:\a\_temp`，不能修改原报告来迁就另一条路径。
- GitHub 当前运行元数据与审核 head 一致；原运行 `42413805736` 来自相同仓库和分支、`workflow_dispatch`、CI workflow ID `362005755`、head `060f261...`、原 attempt 1、completed/failure。
- 原 artifact 的 ID `13591430613`、名称、源 run/仓库/head、未过期状态、GitHub SHA256 摘要与固定 ZIP digest 全部一致。下载 ZIP 再核字节数和摘要；保留原始 ZIP，不覆盖或重打包。
- 原 report 字节直接从固定 ZIP 保留，success/head/完整八项顺序、路径、协议、模式、CLI/SDK/MCP 来源和八个固定 SHA256 均核对。ZIP 成员拒绝逃逸路径、大小写重复、链接；所有目标先核验，遇到不同既有字节时一个文件也不开始复制；只对不存在的目标使用独占创建，或复用 hash 完全相同的文件，不覆盖。

安装完成后，`prepare-step-import-original.py verify` 在 reader 前重新核对同一上下文、保留 ZIP/report 和全部八个目标文件 hash。之后只有一次 `python -I ...verify-step-export-calibration.py --export-report ...`；独立输出目录 `step-original-import-diagnostic`，原生 trace 开启，外层 step 31 分钟，原有 600/1800 秒 watchdog 不变。General profile、MapConfigurationData 只读、首错停和单 host 机制沿用 `96d09b3`，没有新增 CAD API 调用重试、导出或回退分支。

原 ZIP、源/当前运行元数据、GitHub artifact 摘要、八个文件 receipt 和诊断结果上传为 `swcli-step-original-import-diagnostic-{run_id}-{attempt}`。上下文显式 `full_acceptance_eligible=false`、`production_public_acceptance=false`，summary scope 为 `windows-step-original-import-diagnostic`。安装/清理错误与 reader 的首次业务错误保留在各自报告中；不能把原件写出历史或这次诊断归为当前生产公开验收。

入口先提交、推送并发精确 head 给统筹；亲审后仅一次必要 dispatch，输入 head 填该完整提交 SHA。当前文档不表示已经发起诊断。

GitHub 元数据字段与 ZIP 摘要依据 [官方 artifact API](https://docs.github.com/en/rest/actions/artifacts)；手动分支入口依据 [官方 workflow_dispatch 说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)。

接线便携验证：56 项 STEP 回归通过；全量 1875 项，26 项跳过，其余通过。13,824 种门禁组合通过；actionlint v1.7.12 和拒绝重复键的 YAML 解析通过。固定原 ZIP 已离线复验八个指定 receipt/文件身份。仍未执行这次诊断。

## 首次固定原件诊断失败与最小下载修复（2026-11-10）

[诊断 42664273210](https://github.com/YJBeetle/SWCLI/actions/runs/42664273210) 精确 head `671b388ef48ee3d1f1c602cef46c0c56b0c5e205`、workflow_dispatch、attempt 1。官方日志显示当前运行、旧运行和 artifact 元数据已经验证并保存，失败在 `actions/artifacts/13591430613/zip` 下载请求。私有输入、安装、运行环境准备和 reader 均 skipped，没有调用 GetImportFileData / LoadFile4，没有实际接口、选项、配置映射、返回模型或部分几何观测；这些字段均 unavailable，不能记录成零几何。

本次原诊断 ZIP artifact `13695299906` SHA256 `7f3f827cbad03b2568501c5ddd22e1f7d728b007c4de052a588ff8a8044695f7`，仅含 diagnostic-run/source-run/source-artifact 三份元数据。官方 summary ZIP artifact `13695613449` SHA256 `36baf40dd977e88a9e14801fadb4d981149c5f89f7e6150df3fbc1b1d1d9282e`。两者已下载、核对 GitHub 摘要与源 head，原 ZIP/日志保存在 `step-evidence/diagnostic-original-42664273210/`，不改写。

原脚本只记录泛化请求错误，原失败的 HTTP 状态未保存。对同一旧请求的无 CAD 复现明确返回 HTTP 415：`Unsupported 'Accept' header: 'application/octet-stream'. Must accept 'application/json'.` 这是已经证实的请求合同缺陷；不能声称原日志直接记录了 415，或将其归因于权限不足/文件数据/CAD。官方 [artifact API](https://docs.github.com/en/rest/actions/artifacts) 的 ZIP 请求仍采用 JSON API Accept，然后重定向至 ZIP；返回原字节和请求头协商是两件事。

最小修复仅为 GitHub 请求统一使用 `application/vnd.github+json`；`binary=True` 仅控制成功响应不做 JSON 解码。失败保留 HTTP 状态、退出码和受限结构化消息，移除凭据/URL，不回显 stderr，不自动重试。修正请求的本地只读下载已得到与旧原 ZIP 逐字节相同的内容，SHA256 仍为 `de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7`，八项 receipt/文件身份全部通过。

General profile、MapConfigurationData 只读、固定源和八文件要求、工作流互斥、单 host、首错停及 600/1800 秒均未改变；没有重试失败的 CAD API。只有这个实质下载修复完成关联/完整便携验证后，才对新 head 安排一次必要诊断。它依然不是生产公开验收。

修复验证：58 项 STEP 回归通过；全量 1877 项，26 项跳过，其余通过。本轮按统筹 0 CAD 要求只提交取件修复，不新增派发。工作流、权限和 secret 均未改变。
