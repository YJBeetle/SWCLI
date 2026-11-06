# 默认字体范围交接（本批收口）

状态：**精确 Notes 子集已完成内部及公开 CLI/继承验收，原始产物已独立自验，可交统筹本人最终 review/合并。整个字体系列尚不能据此认定完成或发版。** 没有取消远程 CI、重复派发、增加审查代理或扩展范围。

## 精确分支和已完成运行

- worktree：`/Users/YJBeetle/.codex/worktrees/docprops-font-scopes/SWCLI`
- 分支：`codex/docprops-font-scopes`；基线：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 已推送的实现提交：`15d32ceea38b123c3cd3503b34d86663a65f5f3c`。后续收口提交只更新交接/文档；通过验收的实现精确 head 仍是此提交。
- [公开 run 42279469524](https://github.com/YJBeetle/SWCLI/actions/runs/42279469524)，head 与上项一致；`calibrate_font_scopes=true,font_scopes_profile=public-notes,native_full=false`。
- 运行最终 `completed/success`，公开 CLI、保存重开和独立 Notes 继承观察均通过；已下载原件并完成独立自验。
- 在途历史快照仍保留；最终状态见 `artifacts/font-scopes/run-42279469524-final.json`。没有持续监看或额外 dispatch。
- 没有 rebase 当前 main，没有修改 DockerSW/MacSW，没有调用本地 Windows VM，没有自行合并或发布。

## 已实现范围

`document.font-scopes` / `swcli document font-scopes --document <id> --json` 返回 dimensions、notes、tables、annotations 四个固定范围的完整 17 字段字体快照。annotations 仅作为只读交叉保护。

`document.font-scope-set` / `swcli document font-scope-set <scope> <field> <JSON scalar> --if-fonts '<JSON>' --document <id> --if-update-stamp <n> --lease <lease> --json` 要求显式文档、lease、stamp，以及四范围完整 CAS；SDK 方法已生成。

用户已明确批准的公开写入只有 **原生 Windows、SOLIDWORKS revision 33.5.0、PRT/ASM/DRW、Notes** 的 `typeface,height_mm,height_points,bold,italic,underline,strikeout`。尺寸/表格写入、Wine、未知运行环境及其他版本 fail closed。字体 setter 不保存文件，不强制改变对象的 UseDoc 标志。

17 字段：`typeface,height_mm,height_points,height_mode,bold,italic,underline,strikeout,backwards,upside_down,vertical,width_factor,char_spacing_factor,escapement,line_spacing,line_length,oblique_angle`。毫米写入转换为米；磅值为正整数；height_mode 只读观察。官方枚举从安装的 swconst.tlb 读取，不接受调用者给 COM 名称或整数 preference。

## 验证证据

- 最终便携回归：**运行 1,883 项，OK（32 skipped），57.981 秒**；`artifacts/font-scopes/portable-postreview-final.log`。
- 字体专项 **64 项通过**；当前 run 的 Windows 端专项、SDK 检查、两个 PowerShell 包装器解析也已通过。
- SDK 生成检查、actionlint v1.7.7、git diff --check 通过。
- 内部原生成功：[run 42266956658](https://github.com/YJBeetle/SWCLI/actions/runs/42266956658)，head `3f5434c593da2ae2c00c4a3b2ecd7e7a313af626`；artifact `13529107224`，原 ZIP SHA-256 `615b979b4adb667cade7bf3448a7c3c898392d1638b862904debba8bfca37eca`，独立计算与服务端一致。
- 内部成功包含 PRT/ASM/DRW 各 21 次变化写入、合计 63 次；逐 request 核对 1 属性 setter、1 文档 setter、12 scoped getters、完整 CAS 与非目标保护；六份毫米/磅值保存文件的快照、大小与哈希核对；cleanup 无错，组 55.480 秒。
- 内部成功**不等于公开 CLI 或对象继承验收**；后续公开成功证据在下面单独记录。
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

## 公开 Notes 原件自验通过

- Artifact `13537375331`，原 ZIP SHA-256 `67fec36badcdfd5cb9d29218efbad91aa601aad4d4a6ca9e24fe35b86ef942c3`，与服务端 digest 一致。
- 原件：`artifacts/font-scopes/run-42279469524-original.zip` 和同前缀 `-original/`；元数据 `-final.json`、`-artifacts.json`；独立审计 `-audit.json`。所有路径均相对于本 worktree。
- 120 个唯一字体请求：45 read、21 changed、21 same-value、33 refused。原始 stdout/trace 逐请求核对；changed 各 1 property-set + 1 document-set，same/refused 无 setter，四范围完整读取顺序和 600 秒预算保持。
- PRT/ASM/DRW 各七字段公开变化、同值、CAS/lease/stamp/readonly 拒绝及两种高度保存重开通过；六份输出大小/hash/完整快照/模式独立核对。
- 新 owned observer 宿主只读重开六份输出：UseDoc=true 的字体/四样式/模式/活动高度跟随 Notes 默认，local=false/20pt 的完整 17 字段归一化和原生字体与 flag 精确保持。
- 五次 PRT geometry metrics 逐位完全相同；源文件 hash 保持；三个 case 文档列表收空；各阶段 cleanup_errors=[]，daemon.stop success。seed/public/observer 分别 27.113/147.449/10.287 秒，无 API 重试/回滚/组内宿主重启。
- 独立核验脚本 `artifacts/font-scopes/audit-public-notes-original.py` 已对原件执行通过；完整六文件 hash 表及原始失败历史见 `docs/verification/document-font-scopes-native-2026-11-07.md`。

## 系列剩余边界，不能推广的结论

1. 本次可供统筹最终 review 的公开子集只有 Notes/原生 Windows/33.5.0/PRT ASM DRW/七字段。尺寸与表格只有先前内部原生校准，没有公开 CLI 及对象继承验收，其写入仍关闭；不能用 Notes 成功认定这两路完成。
2. 尺寸子类型联动、表格模板/单元格继承、富文本、字体替代与视觉输出没有验收；Wine/macOS/其他 SOLIDWORKS 版本没有验收。本批未新增任意字段/API。
3. 原生同步请求 600 秒、每组 1800 秒；首失败停止，没有 API 重试、自动回滚或组内宿主重启。只使用本分支 disposable GitHub runner 与 owned hidden hosts。

主对话负责最终 review、逐条合并和整个系列验收齐备后的发版；本分支未自行合 main 或发布，也没有将剩余系列缺口宣称为已完成或自动后置发版。
