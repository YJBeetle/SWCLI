# 默认字体范围原生验证记录

状态：**精确 Notes 子集的内部与公开 CLI/继承门禁通过，原始产物已独立核验；交统筹最终 review。尺寸/表格公开写入仍关闭，系列尚不能据此宣称完成或发版。**

## 首轮：42262037827

- [GitHub run](https://github.com/YJBeetle/SWCLI/actions/runs/42262037827)，head `a1860400953c85cf1cdbd6ca5229ae4c07c6c25d`。
- 参数 `calibrate_font_scopes=true,native_full=false`，目标本分支；普通 portable/package/full-native/release 跳过，Windows 字体便携检查通过。
- 安装 SOLIDWORKS `33.5.0`；内部组 24.058 秒，首失败停止，cleanup 无错误，无 API 重试/回滚/宿主重启。
- 原 artifact ID `13525673864`，ZIP SHA-256 `174f27e8e10a31e153ab0945c7553361a4a65d6d8558f4748f0b299a89097df3`，独立下载重算与 GitHub digest 一致。
- 原 ZIP、解包文件、元数据和独立 trace 审计保存在本 worktree 的 `artifacts/font-scopes/run-42262037827-*`，原文件未改写。
- 只运行到 PRT：三范围各 typeface、bold、italic、underline、strikeout、height_mm，共 18 次变化写入与原生读回。每次已独立匹配唯一 request、1 属性赋值、1 文档 setter、12 次字体 getter，CAS 与其他范围/字段、背景状态保持。
- 未到字号 points、改变后 save/reopen、ASM 或 DRW；不能将上述局部通过升级为范围可写验收。
- 实测官方符号为：dimensions `1/200`，notes `0/0`，tables `17/0`，annotations `19/0`（preference/option）。
- 源夹具 SHA-256 `7523b8d2efcc651c58331152406e6c0c5fc8df6a152c170053acfa3e41cfb67f` 前后相同。

第一真实失败：新校准器把两次打开实例的 metrics 字典逐位比较。
实体数 `1`、体积 `11999.999999999998 mm³`、面积 `3799.9999999999995 mm²` 全部精确相同；
仅 Y 质心从 `6.286572655403011e-16` 到 `5.514537417020185e-16 mm`，差 `-7.720352383828262e-17 mm`。
此结果保留为失败，没有通过重新解释原产物改为成功。

## 经用户批准的修复

用户明确批准替换此新增逐位比较并做一次修复校准：
记录同一 writable 实例写前几何，直接复用现有 `verify-document-annotations.py::same_geometry`。
原固定标准为实体数精确、体积/面积 rel=1e-9 abs=1e-6、质心 abs=1e-6 mm；没有改动该 helper。
既有 analytic box 断言保留，并增加毫米和磅值模式保存重开后的几何比较。
新增便携回归保留首失败数值，另断言实体数量、体积、面积、1e-5 mm 质心偏移均被拒绝。

后续结果必须以新的精确 head 和新原产物记录；当前不宣称原生、继承或公共 CLI 门禁完成。


## 预原生取消：42266550762

[Run](https://github.com/YJBeetle/SWCLI/actions/runs/42266550762) 的 head 为 `64e26324b2afd801dd6520c600fcc7082397d839`。
便携检查和两个 PowerShell wrapper 解析通过，随后仍处于磁盘清理。
补核官方 [swRebuildOnActivation_e](https://help.solidworks.com/2024/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swRebuildOnActivation_e.html)
发现恢复前景的选项 0 会请求用户决定；已改为 no-rebuild=1。
为避免已知的隐藏宿主弹窗风险，仅取消了这个尚未开始安装/原生测试的本分支 run，保存取消前步骤元数据。
这不是 CAD API 失败或通过，不计为原生校准结果，不涉及其他分支或本地 VM。


## 修正内部校准通过：42266956658

- [Run](https://github.com/YJBeetle/SWCLI/actions/runs/42266956658)，head `3f5434c593da2ae2c00c4a3b2ecd7e7a313af626`，整体 success。
- Artifact `13529107224`，原 ZIP SHA-256 `615b979b4adb667cade7bf3448a7c3c898392d1638b862904debba8bfca37eca`，独立重算一致。
- PRT/ASM/DRW 各 21 次变化写入，63 次 request 均独立匹配 1 ITextFormat 属性 setter、1 文档 setter、12 scoped getters；CAS、其他字段/范围、背景身份与 mutation 语义保持。
- 三类文档分别毫米/磅值保存重开；完整快照和模式一致，六份最终归档文件的 SHA-256 与当时保存记录一致，源夹具 hash 未变。
- PRT 写前/改变后/两种重开都采用经用户批准的同一既有几何 helper；没有对 ASM/DRW 外推物理几何结论。
- 组耗时 55.480 秒，cleanup 无错，600/1800 预算不变。审计 JSON、原 ZIP、解包文件与元数据均保存于本工作树 `artifacts/font-scopes/`。
- 内部校准不含既有 Notes 的 UseDoc/局部覆盖或公开 CLI 链路，因此**不能作为公开验收**。
- 已准备 public-notes 门禁及明确受限的 Notes 范围补丁；自动审批要求对新公开写入能力直接具名授权，用户随后直接批准了原生 Windows 33.5.0/PRT ASM DRW/Notes 七字段及一次公开门禁，才应用该补丁。原生校准实现与公开复用实现已核对 AST 等同，公开 gate 仍待新 head 的结果。


## 公开首失败与审查修复

- Run [42274572361](https://github.com/YJBeetle/SWCLI/actions/runs/42274572361)，head `e17d7bed8101aead914b952eccbe13928028f535`，在继承夹具 seed 首失败，公开 CLI 与 observer 均未运行。
- 原 artifact `13532858844`，ZIP SHA-256 `4126e58df265cf01ca3dbd4143906be78a0a813be9e36c485a39fb38a008e2ff`，独立核对一致；原 ZIP、元数据及解包文件保存在 `artifacts/font-scopes/`。
- `IAnnotation.SetTextFormat(0, True, None)` 返回 COM Type mismatch（参数 3）。改用仓库既有 `_null_dispatch()` 提供 `VT_DISPATCH` 类型的空指针；一次调用，False/异常即停止，没有 fallback 或 API 重试。
- 审查修复一：字体 handler 最终 describe、worker 上下文恢复/结果验证失败时保留可信 mutation receipt 和第一个业务错误，另附后置错误；逐请求重置 result，防止前一请求回执泄漏。
- 审查修复二：另一个前台文档的 dirty/stamp、path/title、configuration、访问模式和编辑上下文在每个边界完整核对；不激活或回滚文档。目标本身位于前台时允许自身合法 dirty 改变。
- 审查修复三：CI 首先执行无机密 dispatch-policy；错误分支、font+native_full、未选择字体入口的 public-notes 都明确失败，合法请求只进入一个验证路由，避免全部跳过的绿色运行。
- 字体专项 64 项通过；完整便携回归 1,883 项通过、32 项跳过、57.981 秒，日志 `artifacts/font-scopes/portable-postreview-final.log`；SDK 生成检查与 actionlint 通过。
- 下一步在修复后的精确 head 执行 public-notes 门禁，当前仍非 merge-ready；首失败不能升级为公开验收。


## 本批收口快照

修复实现 head `15d32ceea38b123c3cd3503b34d86663a65f5f3c` 已推送；[公开 run 42279469524](https://github.com/YJBeetle/SWCLI/actions/runs/42279469524) 精确匹配该 head。最后一次快照为 in_progress，dispatch-policy 与 Windows 字体便携检查通过，当前在 runner 磁盘清理，CAD/公开 CLI/observer 均尚未开始。按用户收口指令停止本地持续监看，保存 `artifacts/font-scopes/run-42279469524-handoff-snapshot.json`；不取消远程运行、不重复派发。公开验收仍待完成原件，当前尚非 merge-ready。


## 修复后公开 Notes 验收通过：42279469524

- [Run](https://github.com/YJBeetle/SWCLI/actions/runs/42279469524)，精确实现 head `15d32ceea38b123c3cd3503b34d86663a65f5f3c`，整体 success。后续文档提交未改变该实现。
- 原 artifact ID `13537375331`，ZIP SHA-256 `67fec36badcdfd5cb9d29218efbad91aa601aad4d4a6ca9e24fe35b86ef942c3`，下载后独立计算与 GitHub 服务端 digest 一致。
- 原 ZIP：`artifacts/font-scopes/run-42279469524-original.zip`；安全解包：`artifacts/font-scopes/run-42279469524-original/`；完整运行/产物元数据：同前缀 `-final.json`、`-artifacts.json`。
- 独立审计：`artifacts/font-scopes/run-42279469524-audit.json`；可复核脚本：`artifacts/font-scopes/audit-public-notes-original.py`。原 ZIP 和解包后的原报告/日志/保存文件未改写。
- 真实安装的 `swcli.exe` 经公开 daemon 路径执行 120 个唯一字体请求：45 次读取、21 次变化写入、21 次同值、33 次 CAS/lease/stamp/readonly 拒绝。原始 stdout 与报告结果一致，逐 request 对应完整原生 trace；每次变化恰为 1 属性 setter + 1 文档 setter + 3 轮四范围完整字体读取，同值/拒绝没有 setter。
- 每类 PRT/ASM/DRW 七字段均通过；完整四范围 CAS、非目标范围与字段保护、背景 active/current=false、脏标志与 mutation 语义保持。公开组首尾同一 owned hidden host，worker PID 9088；SOLIDWORKS revision 33.5.0，宿主 process_id 6376。
- 三类文档各毫米/磅值六份保存文件，大小/SHA-256 与原记录一致；只读重开的完整四范围字体及模式与写后一致。PRT 五份原始 geometry metrics 逐位完全相同（实体数 1、体积 11999.999999999998 mm³、面积 3799.9999999999995 mm²），没有新增公差。
- seed 用宿主 7056，自建每类一条 UseDoc=true 和一条 local=false/20pt Note。独立 observer 用新宿主 5768，只读打开六份公开输出；UseDoc=true 的 typeface/四样式/模式/活动字号跟随文档 Notes 默认；local=false 的完整归一化 17 字段、原生 17 字段和 flag 均与 seed 精确相同。
- seed 27.113 秒、公开 CLI 147.449 秒、observer 10.287 秒；同步请求 600 秒/组 1800 秒。各组 cleanup_errors=[]，三个 case 均空文档收尾，daemon.stop success，无 cleanup-error 文件。无 API 重试、回滚或组内宿主重启。
- 最终便携：运行 1,883 项，OK（32 skipped），57.981 秒；字体专项 64 项通过；SDK、actionlint 及当前 run 的 Windows 专项/PS 解析通过。

通过范围仅为 **原生 Windows、SOLIDWORKS 33.5.0、PRT/ASM/DRW、Notes 的 typeface/height_mm/height_points/bold/italic/underline/strikeout**。尺寸/表格尚无公开 gate 与对象继承验收，其写入仍关闭；annotations 仍只读保护。Wine/macOS/其他版本、尺寸子类型、表格模板/单元格、富文本、替代字体和视觉输出均不在本次通过声明中。Notes 精确子集可交统筹最终 review/合并；不能把它提升为整个系列完成或提前发版。

| 归档文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `notes-height_mm.SLDPRT` | 49001 | `c6a9026104eb2f4b656d792273195e02c3c7392d2b34e18f44c32d8da953e506` |
| `notes-height_points.SLDPRT` | 48422 | `a9c4b9ac20ce89ae52a7ef62eec0a41238654631c47008806293fadd7477b6c2` |
| `notes-height_mm.SLDASM` | 32359 | `62cde69f2ff4dd74729229898b40fa2ec6def6e695845f899b35891078b6df71` |
| `notes-height_points.SLDASM` | 32139 | `01b176f758fe2217404a096535227be7c52fd7ca7b5c5db1436bd9e412934d26` |
| `notes-height_mm.SLDDRW` | 28332 | `54a4c6f67be0c36ee7b8f0ef0e3f1a3fafb022b70de10c44bc17c4aa19bb2228` |
| `notes-height_points.SLDDRW` | 27733 | `d26ccfb866b203488ee8d6a36594ea1d2fe51e199eaf0c0743ef4cf545d2196d` |
