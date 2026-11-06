# 字体范围分支交接

- 工作树：`/Users/YJBeetle/.codex/worktrees/docprops-font-scopes/SWCLI`
- 分支：`codex/docprops-font-scopes`
- 基线：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`
- 范围：文档默认字体的 dimensions、notes、tables；annotations 仅完整交叉范围观察，避免重复通用注释字体功能。
- 没有合并其他未验收分支，没有修改 DockerSW/MacSW、main、镜像或本地 Windows VM。
- 当前发布/公开验收：**未完成**；公开 setter fail closed；**尚非 merge-ready**。

## 操作、CLI 与 schema

| 操作 | CLI | 参数 / 结果 |
| --- | --- | --- |
| `document.font-scopes` | `swcli document font-scopes --document <id> --json` | 参数为空；结果 `fonts` 为四个固定范围的完整 17 字段快照 |
| `document.font-scope-set` | `swcli document font-scope-set <scope> <field> <JSON scalar> --if-fonts '<JSON>' --document <id> --if-update-stamp <n> --lease <lease> --json` | `scope`: dimensions/notes/tables；`field`: typeface/height_mm/height_points/bold/italic/underline/strikeout；`value` 按字段条件 schema；`expected_fonts` 必须四范围全量；三个文档上下文字段均必填 |

快照字段为 `typeface, height_mm, height_points, height_mode, bold, italic, underline, strikeout,
backwards, upside_down, vertical, width_factor, char_spacing_factor, escapement, line_spacing,
line_length, oblique_angle`。`height_mm` 转米；`height_points` 正整数；模式由原生只读方法观察。
失败结果包含 `mutation.attempted/may_have_changed`。成功写入结果的 `before/fonts/changed/mutation`
及其他范围、非目标字段、脏标志必须语义一致；内部校准仍走正常 dispatcher 的 lease/stamp 保护。
公开 setter 不存在环境变量或协议校准旁路，当前返回 `DocumentFontScopeNotCalibrated`。
Python SDK 已生成 `document.font_scopes` / `document.font_scope_set`。

## 共享文件改动（供主集成处理冲突）

- `src/swcli/operation_schemas.py`：新增两操作与字段条件；修正 `_operation` 对必填 lease 的保护判定（原来只保护 optional，现为非 forbidden）。
- `src/swcli/result_schemas.py`：四范围封闭结构、完整快照与 mutation 语义检查。
- `src/swcli/daemon/operations.py`：两个 handler，无临时激活。
- `src/swcli/cli.py`、`src/swcli/sdk/models.py`、`src/swcli/sdk/_generated.py`。
- `src/swcli/skills/swcli/references/usage.md`：明确开发状态与公开拒绝。
- `.github/workflows/ci.yml`：默认 false 的 `calibrate_font_scopes`；仅当前分支 workflow_dispatch 调用专属 reusable；该路径跳过通用 portable/package/full-native，常规路径保持原门禁。
- `tests/test_modeling_sequence.py`：给新授权开关精确白名单，仍禁止便携区机密和其他旧校准开关，保留所有几何/状态断言。
- `.gitignore`：只忽略本工作树持久证据目录 `/artifacts/font-scopes/`。

新文件：`font_snapshot.py`（只读参考原批快照帮助函数并泛化，不合分支）、`document_font_scopes.py`、
`hosts/windows_document_font_scopes.py`、两份字体测试、三个 CI 脚本、独立校准 workflow、
`docs/design/document-font-scopes.md`。

## 便携测试

- 初始字体范围、原生调用跟踪、watchdog 与接线测试：28 项通过；后续公开门禁/SDK/MCP 与已授权几何回归加入后，专项共 40 项通过。
- SDK `generate-sdk.py --check`：通过。
- 两个 workflow：YAML 解析和 actionlint v1.7.7（禁用未安装的 shellcheck/pyflakes）通过。
- 既有 modeling-sequence、annotation CI wiring：通过，按环境跳过 3 项。
- 完整便携回归最终结果：1,847 项通过，32 项按环境跳过（53.210 秒）；持久日志 `artifacts/font-scopes/portable-acceptance.log`。
- 曾发现并修复：required lease 未被 catalog 标记为 guarded；专属 CI 作业位置/旧校准开关静态禁令不兼容。原失败日志保留，不把它们当原生失败。

## 原生 CI、授权与证据

- 用户已明确授权仅把 `RCLONE_CONFIG_B64` 传入该分支专属校准安装路径；不继承全部 secrets、不输出凭据、不扩大 PR 触发权限。
- 先前自动审批拒绝 broad `secrets: inherit`，也拒绝未具名授权的单机密方案；用户随后明确确认后才实现具名传递。
- 专属 concurrency 为 `swcli-font-scopes-${{ github.ref }}`、`cancel-in-progress=false`，不竞争其他 profile 的 pending 槽；默认 full/release group 保持原样。
- 已且仅派发一次已有 `ci.yml`，参数 `calibrate_font_scopes=true,native_full=false`，ref 为本分支（其余安装路径沿用默认值，cleanup=auto，vfs=8）。
- 实现提交：`a1860400953c85cf1cdbd6ca5229ae4c07c6c25d`，已推送同名分支。
- 原生运行：[42262037827](https://github.com/YJBeetle/SWCLI/actions/runs/42262037827)，精确 head 同上；最终 failure，原产物 digest 已核验；首失败和修复准备见下节。
- 自动审批起初不接受委派中的推送授权；用户随后直接授权此精确仓库/分支推送及一次校准，之后才执行。没有调用任何本地 VM。
- 内部组：一个新隐藏 owned host，PRT/ASM/DRW，四范围 CAS 和前景保护，分别毫米、磅值保存重开，readonly 拒绝，原几何断言和源文件哈希。
- 每次同步 native/dispatcher 操作 600 秒、整组 1800 秒；只停止自己的 Python worker；首失败停止，不重试、不自动回滚、不组内重启。
- 原产物：`watchdog.json`、`native/report.json`、`native/trace.jsonl`、worker stdout/stderr。stderr 有按请求关联的原生方法边界，不含参数/结果。
- 校准 artifact 保留 30 天；将下载至 `artifacts/font-scopes/`，不依赖临时目录。

## 首次内部运行审计与待授权修复

- Run `42262037827` 在 24.058 秒的内部组中首失败停止；没有 timeout、API 重试、组内重启或 cleanup error。
- 官方安装版本 `33.5.0`。官方枚举实测：dimensions preference=1/option=200，notes=0/0，tables=17/0，annotations=19/0。
- 原 ZIP `artifacts/font-scopes/run-42262037827-original.zip`，GitHub artifact `13525673864`，SHA-256 `174f27e8e10a31e153ab0945c7553361a4a65d6d8558f4748f0b299a89097df3`，独立计算与服务端 digest 一致。
- 独立审计 `artifacts/font-scopes/run-42262037827-audit.json`：仅 PRT；18 次变化写入（dimensions/notes/tables 各 typeface、4 个样式、height_mm）均找到唯一匹配的 1 property-set + 1 document-set + 12 scoped font getters，完整 CAS/其他字段范围/背景状态一致。
- 源文件哈希 `7523b8d2efcc651c58331152406e6c0c5fc8df6a152c170053acfa3e41cfb67f` 保持不变。
- 第一真实失败是本分支校准器新增的跨打开实例 metrics 字典逐位相等。实体数/体积/面积精确相同；仅 Y 质心 `6.286572655403011e-16 -> 5.514537417020185e-16 mm`，差 `-7.720352383828262e-17 mm`。
- 未到任何改字体后的 save/reopen、points 模式、ASM 或 DRW，所以不能升格任何公开写入或整组通过。
- 本地已准备修复：记录同一 writable 实例的写前 geometry；直接复用既有 `verify-document-annotations.py::same_geometry`（实体数精确，体积/面积原 rel=1e-9 abs=1e-6，质心原 abs=1e-6 mm），不修改既有 helper；保留原 analytic box 检查，并新增两种字号保存重开的几何比较。
- 这会替换本分支新增的浮点逐位比较；用户已明确答复“批准固定容差修复及一次校准”，据此准备新的实现提交与一次修复验证。公开写入仍关闭。

## 第二个 run 的预原生取消

- 几何修复提交 `64e26324b2afd801dd6520c600fcc7082397d839` 已推送；run `42266550762` 的 Windows 字体便携检查（含两个 PowerShell wrapper 解析）通过。
- 补核官方 `swRebuildOnActivation_e` 时发现校准器恢复前景用了 0（swUserDecision，可能弹窗）；正确不重建选项为 1。
- 已只取消本分支这个 run：取消前保存了步骤元数据，native 安装和字体步骤均未开始，当前处于 Free disposable runner disk。没有 API 重试、组内宿主重启或取消其他分支 run。
- 已以官方 no-rebuild=1 的修正提交 `3f5434c593da2ae2c00c4a3b2ecd7e7a313af626` 派发替代 run [42266956658](https://github.com/YJBeetle/SWCLI/actions/runs/42266956658)，仍为 calibrate_font_scopes=true/native_full=false，40 项便携专项通过。此次预原生取消不能算作 CAD 测试成功/失败。
- 官方依据：[swRebuildOnActivation_e](https://help.solidworks.com/2024/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swRebuildOnActivation_e.html)。

## 修正内部校准通过：42266956658

- [Run](https://github.com/YJBeetle/SWCLI/actions/runs/42266956658)，head `3f5434c593da2ae2c00c4a3b2ecd7e7a313af626`，整体 success。
- 原 artifact ID `13529107224`，ZIP SHA-256 `615b979b4adb667cade7bf3448a7c3c898392d1638b862904debba8bfca37eca`，下载重算与 GitHub digest 一致。
- 三类各 21 次变化写入，合计 63 次；独立核对全部对应 request、1 属性 setter、1 文档 setter、12 scoped getters，无 native error/重复调用，CAS/其他范围及字段/背景身份均保持。
- 三类分别毫米与磅值保存只读重开；独立核对完整四范围快照、模式、六个最终归档文件的大小/哈希，原源夹具 hash 保持。
- PRT 同一打开实例写前/改变后/两种模式重开均通过用户批准的既有几何标准；ASM/DRW 未外推物理几何。
- 内部组 55.480 秒、无 cleanup error，600/1800 固定预算。JSON 审计和所有原文件存于 `artifacts/font-scopes/run-42266956658-*`。
- **这仅是内部校准通过，尚非公开 CLI 或 Notes 对象继承验收。**
- 准备只开放原生 Windows 33.5.0 的 Notes、三文档类型、七字段；尺寸/表格写入及 Wine/其他版本仍关闭。自动审批要求该公开写能力直接具名授权，当前产品源码仍关闭。
- 可审阅补丁 `artifacts/font-scopes/notes-public-enable.patch`（193 行），已做 AST/git-apply 检查但未应用，等待用户对精确范围及一次 public-notes 门禁的确认。

## 公开门禁准备（独立后续提交，未开放写入）

- 主对话要求内部校准后继续公开 CLI/daemon 链路，不能以空白名单宣称完成。
- 已新增 `scripts/ci/verify-font-scopes-public.py` 与独立 owned-hidden-daemon wrapper，尚未接入 CI 或执行原生公开门禁。
- 公开门禁只调用安装后的 CLI，逐请求检查完整字体 getter/property/setter 顺序、600 秒预算、全量 CAS、lease/stamp/readonly 拒绝、同值无 mutation、背景身份、两种字号模式保存重开、源文件哈希和几何。
- 公开门禁及 SDK/MCP 契约便携测试 11 项通过（提交 `eeb5995af3f730f88c338054aedf9d5410421307`）；这些不是公开原生验收。
- 必须先独立核对当前内部运行 artifact/head/digest/trace/save-reopen，才考虑精确范围开放，再对新 head 跑必要公开门禁。当前没有开放公开写入。
- 后续已准备明确 `public-notes` profile（默认仍 `internal`）：自建 UseDoc/20pt-local 两条 Notes 的 PRT/ASM/DRW 夹具 → 安装后 CLI/daemon → 新 owned host 只读观察已保存输出。各组均 600/1800，源/输出哈希、局部完整字体及继承标志必须保持。
- `scripts/ci/verify-font-scopes-inheritance.py` 及五项便携测试已准备；模型用 GetFirstAnnotation2，工程图用 IView.GetFirstAnnotation3，符合官方 API 的不同枚举路径，不凭相同值推断继承。
- 公开 profile 准备不是产品范围开放；只有后续独立核过内部原证据，才考虑 Notes 的精确范围；尺寸总字体子类型、表格模板/单元格继承仍保留未验收边界。
- 当前字体专项合计 46 项通过；未重复无关完整套件。

## 未完成边界与依赖

1. 原生校准尚未取得结果；即使内部通过，也不是公共 CLI 端到端验收。
2. 文档总尺寸字体可能联动所有尺寸子类型；本分支只观察四个所选范围，未证明所有子类型独立。
3. Notes/显示尺寸的 UseDoc、局部/富文本格式，以及表格模板/单元格继承的真实效果尚未校准；不会强制改写这些继承标志。
4. 字体安装、替代字体、视觉输出、Wine/macOS 不在验收声明内。
5. 官方符号从安装的 `swconst.tlb` 解析；任何字段/范围缺失或 native False 都 fail closed。
6. 依赖 main 基线已有文档注册、lease、stamp、背景/readonly/工程图上下文与夹具帮助函数；不依赖任何未合并分支。

官方来源和具体语义见 `docs/design/document-font-scopes.md`。主对话统一决定集成与后续公开门禁；本分支不自行合 main 或发布。
