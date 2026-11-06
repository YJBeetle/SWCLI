# 线型 / 线宽默认设置交接

当前状态：内部原生校准及独立原产物核验通过；已开放证实的精确范围，公开 CLI/daemon 验收运行中。**尚未 merge-ready，不自行合 main/发布。**

## 范围与接口

- 工作树 `/Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI`；分支 `codex/docprops-line-style`；基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。初始 git status 干净，无 .codegraph；未动其他 worktree、VM、DockerSW 或 MacSW。
- `document.line-font` / `swcli document line-font`：四字段 native integer map `options`。
- `document.line-font-set` / `swcli document line-font-set FIELD VALUE --if-options JSON`：`field`、`value`、完整 `expected_options`；沿用 document_id、expected_update_stamp、lease_id；回执 field / before / options / changed / mutation。
- 仅 drawing 文档默认值：visible_edges.style / visible_edges.weight / hidden_edges.style / hidden_edges.weight。无任意 COM 字典或偏好 ID。
- 官方 IModelDocExtension Get/SetUserPreferenceInteger + swDetailingNoOptionSpecified；ID 从官方已安装 swconst.tlb 按名解析，固定标准安装路径；依据见 `docs/design/document-line-font.md`。
- 精确写入域：revision **33.5.0**，visible style 0→1，visible weight 1→0，hidden style 1→0，hidden weight 0→1；0/1 noop 无 setter。其他版本、逆转换、weight 2、自定义厚度、端帽、实体/层覆盖、全局选项、parts/assemblies 继续拒绝。
- 完整四字段 CAS；lease/stamp、readonly/viewonly、背景/文档 sheet/sketch 身份保护、单 setter、部分 mutation 回执，无 retry/rollback/restart。annotation helper 仅复用上下文保护；不混入箭头/网格/基准面字段。

## 共享文件

`src/swcli/operation_schemas.py`、`result_schemas.py`、`cli.py`、`daemon/operations.py`、生成 SDK `_generated.py` / `models.py`、`.github/workflows/ci.yml`。其余为线型专属文件；无其他未验收分支依赖。主对话统一处理集成冲突。

## 便携验证

- 完整 unittest 1831 项通过，32 skip（最初实现）；Windows 3.9 / 3.14 在内部 run 的 portable jobs 均成功。
- SDK 生成一致性、strict types / 8 项 consumer 拒绝及 installed resources 通过。
- 续作新增公开证据拒绝测试、精确域保护测试；最终相关结果见 `artifacts/line-font/public-gate-portable.log`。不因统筹消息重复全套测试。

## 内部原生证据（已独立核）

- [42260712677](https://github.com/YJBeetle/SWCLI/actions/runs/42260712677)，head `6f531a595a50bbadeeab2c0f005d89c0246c7ee5`；conclusion success；参数 line_font_calibration=true / native_full=false，其余默认。
- 原 artifact id `13526587857`，name `swcli-windows-hosted-42260712677-1`；SHA256 `5d8152062aea15f32d40c10f0947f36bceb0458702387fff0f2ef09b5ecc64e9` 与 GitHub digest 一致。
- 原 ZIP、GitHub artifact/run metadata 仅在本地持久保留（未复制推送），保存在 `artifacts/line-font/internal-42260712677/`；expanded 原产物也在本地持久保留。独立核验 `artifacts/line-font/internal-audit.json`，脚本 `scripts/ci/audit-line-font-calibration.py`。
- 每字段 1 setter / 12 preference getter，读取顺序完整；已知状态保护 getter 单独显式核验并保留，未知调用/全局 setter 均拒绝。背景文档、保存重开、只读拒绝、owned host 清理均通过。
- fixture SHA256 `92cae239235e0a5193ef0ff9577c48913cde3dc3137f5d8a30601c559cc08d98`；report `879d12f4821198e5d61fda9ebefb2e6c407dc93a95036a01fe43de1bb185ee6e`；trace `9bae5562b290c1b6865d14c768b68debae85d5bab23aa7d62833d059187a14e4`；process log `f17c814825db46044a9101cef0e054312b5949b648e3a494ff8cda8dae91248b`。
- 初次 run 42260403395 在 native 前因发现共享 concurrency 风险主动取消；仅修复后启动上述 run，未动其他 run。

## 公开 gate 与剩余边界

- `scripts/ci/verify-line-font-public.py`：public CLI + 独立隐藏 daemon，lease/stamp/完整 CAS/readonly 拒绝、单次四字段变化、noop、源 hash、save/reopen/fresh ID、完整结果/状态比较，native 每 request trace。
- SDK typed read/noop + MCP live bridge execute/noop 包含；不宣称 MCP stdio transport 验收。
- `line_font_public=false` 默认关闭，仅本分支手动，独立 `swcli-hosted-windows-line-font-public` 并发组；不扩 PR secrets，不进入默认 full/release。600s 请求 / 1800s group，首失败停止。
- 内部校准成功不等于公开验收。公开 run/head/原 ZIP/digest/trace/save-reopen 证据待下一步回收；完成后才写精确 merge-ready commit。
- 当前已推送：216ebec（实现）、6f531a5（并发隔离）、3ab8d21（首次交接）、497f23e（公开 gate 准备）。最终公开验收提交待补充。

## 本次公开验收运行

- 代码提交 `0addd65346a537a2eaefaf81c92257b4b7c30720` 已推送。
- [42266835193](https://github.com/YJBeetle/SWCLI/actions/runs/42266835193)，head=`0addd65346a537a2eaefaf81c92257b4b7c30720`；line_font_public=true / line_font_calibration=false / native_full=false，其余默认。只触发这一必要公开验收，不因正常排队重发。
- 最终相关便携测试 19 项通过，SDK generator/strict typing/8项 consumer 拒绝通过，门禁策略与摘要相关检查通过；未为消息重复全套测试。
- 原始 native ZIP/metadata/expanded 与独立 audit JSON 仅在本地持久目录保留，远端已有 GitHub 原 artifact；推送仅含代码、测试与 hash/链接交接摘要。
- 当前待回收公开结果，仍非 merge-ready。

## 公开 gate 接线修复

- 在 run 42266835193 仍清理 runner、未进入原生测试时，静态核实际 runtime-status 契约发现复用旧 helper 的 health 解析错误（当前状态的原始 health 在 `result.health`，不能从 result 顶层读取 recovery_required/host/server_version）。主动取消本线程 run，未取消其他运行；不是正常排队重发，也不算 SOLIDWORKS API 失败。
- 新增线型专属 LineFontSmoke.health 解析当前状态封套，保留外层 ready/reachable/connected 与内层无 recovery、PID 的全部断言；新增两项实际 snapshot 契约测试，不修改共享 modeling/annotation helper。
- 相关修复、测试通过后才触发新 head 的公开验证。
