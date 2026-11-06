# 默认字体范围交接（本批收口）

状态：**实现与便携回归完成，公开验收仍在运行，尚非 merge-ready**。按用户最新收口要求取一次快照后停止本地持续监看；没有取消远程 CI、重复派发或扩展范围。由统筹后续分次检查完成/失败原件。

## 精确分支和当前运行

- worktree：`/Users/YJBeetle/.codex/worktrees/docprops-font-scopes/SWCLI`
- 分支：`codex/docprops-font-scopes`；基线：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 已推送的实现提交：`15d32ceea38b123c3cd3503b34d86663a65f5f3c`。后续收口提交只更新交接/文档；待验收实现精确 head 仍是此提交。
- [公开 run 42279469524](https://github.com/YJBeetle/SWCLI/actions/runs/42279469524)，head 与上项一致；`calibrate_font_scopes=true,font_scopes_profile=public-notes,native_full=false`。
- 2026-11-06 19:41 UTC 附近最后快照：`in_progress`，dispatch-policy 和 Windows 字体便携检查已通过，正在 `Free disposable runner disk for installation`；SOLIDWORKS 安装、夹具、公开 CLI、继承 observer 尚未开始。
- 快照：`artifacts/font-scopes/run-42279469524-handoff-snapshot.json`。本地 `gh run watch` 已停止，GitHub run 保持运行。
- 没有 rebase 当前 main，没有修改 DockerSW/MacSW，没有调用本地 Windows VM，没有自行合并或发布。

## 已实现范围

`document.font-scopes` / `swcli document font-scopes --document <id> --json` 返回 dimensions、notes、tables、annotations 四个固定范围的完整 17 字段字体快照。annotations 仅作为只读交叉保护。

`document.font-scope-set` / `swcli document font-scope-set <scope> <field> <JSON scalar> --if-fonts '<JSON>' --document <id> --if-update-stamp <n> --lease <lease> --json` 要求显式文档、lease、stamp，以及四范围完整 CAS；SDK 方法已生成。

用户已明确批准的公开写入只有 **原生 Windows、SOLIDWORKS revision 33.5.0、PRT/ASM/DRW、Notes** 的 `typeface,height_mm,height_points,bold,italic,underline,strikeout`。尺寸/表格写入、Wine、未知运行环境及其他版本 fail closed。字体 setter 不保存文件，不强制改变对象的 UseDoc 标志。

17 字段：`typeface,height_mm,height_points,height_mode,bold,italic,underline,strikeout,backwards,upside_down,vertical,width_factor,char_spacing_factor,escapement,line_spacing,line_length,oblique_angle`。毫米写入转换为米；磅值为正整数；height_mode 只读观察。官方枚举从安装的 swconst.tlb 读取，不接受调用者给 COM 名称或整数 preference。

## 验证证据

- 最终便携回归：**1,883 通过、32 跳过、57.981 秒**；`artifacts/font-scopes/portable-postreview-final.log`。
- 字体专项 **64 项通过**；当前 run 的 Windows 端专项、SDK 检查、两个 PowerShell 包装器解析也已通过。
- SDK 生成检查、actionlint v1.7.7、git diff --check 通过。
- 内部原生成功：[run 42266956658](https://github.com/YJBeetle/SWCLI/actions/runs/42266956658)，head `3f5434c593da2ae2c00c4a3b2ecd7e7a313af626`；artifact `13529107224`，原 ZIP SHA-256 `615b979b4adb667cade7bf3448a7c3c898392d1638b862904debba8bfca37eca`，独立计算与服务端一致。
- 内部成功包含 PRT/ASM/DRW 各 21 次变化写入、合计 63 次；逐 request 核对 1 属性 setter、1 文档 setter、12 scoped getters、完整 CAS 与非目标保护；六份毫米/磅值保存文件的快照、大小与哈希核对；cleanup 无错，组 55.480 秒。
- 内部成功**不等于公开 CLI 或对象继承验收**，新保护代码的原生结果仍待当前新 head。
- 公开首轮失败：[run 42274572361](https://github.com/YJBeetle/SWCLI/actions/runs/42274572361)，head `e17d7bed8101aead914b952eccbe13928028f535`；artifact `13532858844`，原 ZIP SHA-256 `4126e58df265cf01ca3dbd4143906be78a0a813be9e36c485a39fb38a008e2ff`，独立核对一致。继承夹具 SetTextFormat 第三参数 None 引发 COM Type mismatch，公开 CLI 与 observer 均跳过，不能算局部公开成功。
- 当前 head 将该参数改为仓库既有 `_null_dispatch()`（VT_DISPATCH null），只调用一次，不 fallback、不重试。
- 更早首失败、用户批准的既有固定几何容差、预原生取消均完整保留在 `docs/verification/document-font-scopes-native-2026-11-07.md`；没有改写失败原件为成功。

## 三项审查修复（已提交并回归）

1. handler 最终 describe、worker 上下文恢复/结果验证失败保留可信 mutation receipt 和第一个业务错误；逐请求清空 result，防止前一回执泄漏。故障注入走真实 execute/worker 路径。
2. 另一个前台文档的 dirty/stamp、path/title、configuration、访问模式和编辑上下文在每个边界核对；不激活或回滚。目标本身在前台时允许自身合法 dirty 改变。
3. 无机密 dispatch-policy 先拒绝错误分支、font+native_full、未选择字体入口的 public-notes，避免所有验证跳过的绿色运行；合法路线互斥。

## 统筹集成涉及的共享文件

- `src/swcli/operation_schemas.py`：两操作的参数与上下文；修正必填 lease 的保护判定为非 forbidden。
- `src/swcli/result_schemas.py`：封闭四范围/17字段/回执语义。
- `src/swcli/daemon/operations.py`、`src/swcli/daemon/server.py`：handler 与字体专属后置失败回执。
- `src/swcli/cli.py`、`src/swcli/sdk/models.py`、`src/swcli/sdk/_generated.py`：CLI 与 SDK 接线。
- `src/swcli/schemas/v1/capabilities.schema.json`：精确 Notes profile 的封闭 metadata，拒绝扩大范围/版本/字段。
- `.github/workflows/ci.yml` 与 `tests/test_modeling_sequence.py`：默认关闭手动开关、明确单机密、dispatch-policy 与精确白名单；常规 full/release 保持原路径。
- 独立实现：`font_snapshot.py`、`document_font_scopes.py`、`hosts/windows_document_font_scopes.py` 及对应脚本/专项测试。只参考 batch 分支快照 helper，没有合并任何未验收分支。

## 尚待完成，不能推广的结论

1. 当前 run 的公开 CLI/daemon、七字段变化/同值、CAS/lease/stamp/readonly 拒绝、毫米和磅值保存重开，以及独立 Notes 继承观察仍未取得结果。
2. 完成后须先下载原 ZIP、核对服务端 digest/head，再核对 trace、六份输出文件、UseDoc true 的样式/活动字号，以及 local false 的完整 17 字段与原生快照保持。`artifacts/font-scopes/audit-public-notes-original.py` 是准备好的独立核验脚本，**尚未对当前 run 执行**，不能作为成功证据。
3. 尺寸子类型联动、表格模板/单元格继承、富文本、字体替代与视觉输出没有验收；Wine/macOS/其他 SOLIDWORKS 版本没有验收。不会为本批补齐而扩新功能或无限迭代。
4. 原生同步请求 600 秒、每组 1800 秒；首失败停止，没有 API 重试、自动回滚或组内宿主重启。只使用本分支 disposable GitHub runner 与 owned hidden hosts。

主对话负责后续 review、选择可合精确子集和发版；本分支当前不能以内部校准或便携测试宣称整个公开功能验收。
