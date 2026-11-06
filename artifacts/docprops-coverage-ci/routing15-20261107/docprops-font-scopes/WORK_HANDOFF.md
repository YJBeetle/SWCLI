# 字体范围分支交接

- 工作树：`/Users/YJBeetle/.codex/worktrees/docprops-font-scopes/SWCLI`
- 分支：`codex/docprops-font-scopes`
- 基线：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`
- 范围：文档默认字体的 dimensions、notes、tables；annotations 仅完整交叉范围观察，避免重复通用注释字体功能。
- 没有合并其他未验收分支，没有修改 DockerSW/MacSW、main、镜像或本地 Windows VM。
- 当前发布/公开验收：**未完成**；公开 setter fail closed。

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

- 字体范围、原生调用跟踪、watchdog 与接线测试：28 项通过。
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
- 原生运行：[42262037827](https://github.com/YJBeetle/SWCLI/actions/runs/42262037827)，精确 head 同上；当前状态 in_progress，最终结果待回填。
- 自动审批起初不接受委派中的推送授权；用户随后直接授权此精确仓库/分支推送及一次校准，之后才执行。没有调用任何本地 VM。
- 内部组：一个新隐藏 owned host，PRT/ASM/DRW，四范围 CAS 和前景保护，分别毫米、磅值保存重开，readonly 拒绝，原几何断言和源文件哈希。
- 每次同步 native/dispatcher 操作 600 秒、整组 1800 秒；只停止自己的 Python worker；首失败停止，不重试、不自动回滚、不组内重启。
- 原产物：`watchdog.json`、`native/report.json`、`native/trace.jsonl`、worker stdout/stderr。stderr 有按请求关联的原生方法边界，不含参数/结果。
- 校准 artifact 保留 30 天；将下载至 `artifacts/font-scopes/`，不依赖临时目录。

## 未完成边界与依赖

1. 原生校准尚未取得结果；即使内部通过，也不是公共 CLI 端到端验收。
2. 文档总尺寸字体可能联动所有尺寸子类型；本分支只观察四个所选范围，未证明所有子类型独立。
3. Notes/显示尺寸的 UseDoc、局部/富文本格式，以及表格模板/单元格继承的真实效果尚未校准；不会强制改写这些继承标志。
4. 字体安装、替代字体、视觉输出、Wine/macOS 不在验收声明内。
5. 官方符号从安装的 `swconst.tlb` 解析；任何字段/范围缺失或 native False 都 fail closed。
6. 依赖 main 基线已有文档注册、lease、stamp、背景/readonly/工程图上下文与夹具帮助函数；不依赖任何未合并分支。

官方来源和具体语义见 `docs/design/document-font-scopes.md`。主对话统一决定集成与后续公开门禁；本分支不自行合 main 或发布。
