> **统筹更正：先前“共享 ModelingSmoke.health 不兼容”的判断错误，现撤回。普通 CLI `daemon status` 走 daemon.health，基类 helper 与该路径兼容；只有 --details / DaemonManager.status 走嵌套 runtime-status。本分支曾错误混用两条路由，现按原始失败产物修复，并补真实 CLI 路由联测。不要把先前提醒应用到其他分支。**

# 线型 / 线宽默认设置交接

当前状态：内部原生校准及独立原产物核验通过；公开 run 42272391578 已失败，首错为本分支 gate 误读 CLI health，另有摘要文件未初始化导致 checkpoint 报错致摘要缺失（原 job 日志仍保有首错），正在修复。未发生公开线型读写。**尚未 merge-ready，不自行合 main/发布。**

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

- 接线修复提交：`36a262ad020738b9bb8e4bbc8c3cbd3a993716eb`，21 项相关便携测试通过。
- 新的必要公开 run：[42269536427](https://github.com/YJBeetle/SWCLI/actions/runs/42269536427)，head=`36a262ad020738b9bb8e4bbc8c3cbd3a993716eb`；参数 line_font_public=true / line_font_calibration=false / native_full=false，其余默认。当前待结果。
- 【该提醒已被原产物否定，现已撤回；见下方实际 CLI 路由修复】先前的共享 helper 提醒：本 worktree 的 `scripts/ci/verify-modeling.py:494` 基类 health 读取旧状态形状；当前 `src/swcli/runtime_state.py` 把原始健康放在 health 子键中。本分支仅通过 LineFontSmoke 覆盖修复，不改共享 helper。其他 gate 若直接复用旧 health，需要主对话独立审查。

- 旧公开 run 42266835193 普通 cancel 后仍被 always() job 保持运行，已仅对该本线程 run 使用 force-cancel；最终 conclusion=cancelled。停止时仍在 runner 磁盘清理，未进入公开 native group；GitHub 未产生 native artifact。已保留 run metadata、无 native artifact 说明与 job-log HTTP 404 取证状态于本地（原 job 日志当前无法取得） `artifacts/line-font/internal-cancelled-public-42266835193/`。不将其冒充 SOLIDWORKS API 失败或验收。

## Owned worker trace 边界修复

- 对照 server.py 的真实执行边界又确认 gate 需核验 `native_api_sequence`：拥有的宿主会在每请求进入并恢复 CommandInProgress。原 parser 未识别这层合法且必须恢复的 scope，会误判；这是 gate 问题，不是 API 验收失败。
- run 42269536427 仍在 runner 磁盘清理、未进入 native public group 时，仅强制取消本线程该已知必失败的 gate run，避免继续消耗安装资源；未动其他 run。
- parser 现在严格要求完整 enter/read/restore/read 的固定边界，再分别核业务读写和状态观察；没有放宽状态/几何断言。
- 新增便携联测使用真实 trace_native_request + native_api_sequence + execute_operation（COM mock）重现 worker 调用边界；22 项相关测试通过。adapter、公开精确转换域、SDK/MCP schema 均未变。

- CommandInProgress 证据修复提交 `a783b498213597385bed2dfa41cc7cfa1dced2ed` 已推送；推送首次被 GitHub 远端拒绝，检查确认远端仍为36a262a。期间误触发旧 head 的 run 42272160735，发现后在 native job 前立即取消，conclusion=cancelled；随后 Git push 成功并用 ls-remote 核对精确 SHA，才重新触发正确 head。此失误不作为任何验证结果。
- 当前唯一正确的新公开 run：[42272391578](https://github.com/YJBeetle/SWCLI/actions/runs/42272391578)，已从 GitHub 核对 head=`a783b498213597385bed2dfa41cc7cfa1dced2ed`；line_font_public=true / line_font_calibration=false / native_full=false，其余默认。当前尚未达到 merge-ready。

## 授权与自动审批现状

- 统筹转达的本轮授权已覆盖自己的 codex 分支实现/中文提交推送、定向 Windows 内部/公开 gate 和已严格核实的精确域开放；当前无需额外授权。main 集成仍由主对话处理。
- 唯一自动审批拒绝动作：将原始 native CI ZIP/metadata/audit 一并 staging + push 至 GitHub。原理由原产物可能含内部日志/测试文件且远端信任/可见性尚未核实，现有本地审计授权不等于此原产物外传授权。
- 已采用获准的更安全替代：不推送 ZIP/原生日志/测试文件；保留本地持久原产物，推送代码、便携测试与无原日志的 hash/永久 run/artifact 引用摘要。未绕过自动审批，当前无待审批动作；不用为已解决的授权问题重复操作。
- 当前公开 run 42272391578 的 head 已核为 a783b498213597385bed2dfa41cc7cfa1dced2ed，Windows 3.14 portable 已成功；等待同一次必要 run 后续，不因排队重发。

## targeted/full 路由修复（不重跑 CAD）

- 统筹指出的空绿组合在本分支确实存在：native_full=true + targeted=true + 错误 branch 会进入 native job，但 targeted gate 不执行，full矩阵又被 targeted 开关跳过。
- 最小修复：portable test job 安装 SWCLI 前执行 `scripts/ci/validate-line-font-route.py`，明确拒绝 full/internal/public 多选及非本分支的线型请求；native job 原本强制 needs.test.success，因此预检失败时不会进入带私密输入的 runtime。
- 默认全 false 保持 portable；单独 native_full=true 保持 full；合法版本 tag 仍由既有 tag-policy 控制完整 native/release；错误参数 workflow 明确失败，避免空绿。
- 新增 56 组 flags/ref/event 组合断言、CLI env 解码/错误组合子进程检查，以及 YAML 接线检查；不接触 CAD 或凭据。
- 当前公开 run 42272391578 继续以原 head a783b498213597385bed2dfa41cc7cfa1dced2ed 独立取证，其参数本来就是合法单 public + 正确 branch。此路由补丁不改变产品 adapter、CLI、SDK/MCP 或公开 gate 脚本；不为统筹路由消息触发另一 CAD。

## 首次真实公开 gate 失败（原产物已保存）

- run [42272391578](https://github.com/YJBeetle/SWCLI/actions/runs/42272391578)，head a783b498213597385bed2dfa41cc7cfa1dced2ed，conclusion=failure。
- 原 artifact id 13533098590，SHA256 `a3064f349b415f4c7cc5f7435a7d3a5e7607f2821c66a2d36c46cf50fe4fddbb` 与 GitHub digest 一致；ZIP/metadata/expanded/job log 保存在本地 `artifacts/line-font/internal-public-42272391578/`，未推送原日志。
- journal 第一条 daemon.status 返回真实 raw health 封套，本分支误从 result.health 读取，KeyError；finally checkpoint 又因初始 line-font-public.json 未创建而 stat 失败，未产生 summary；原 job 日志仍完整保留 KeyError 首错。尚未进入 line-font 读写，不冒充 API 失败或验收。
- 修复：沿真实 cli.main -> daemon.main.run -> daemon.health 路径联测 health（不使用错误的 DaemonManager/status 假定）；启动任何进程前以 x 模式创建初始 summary，并测试原子 checkpoint 可保存首个失败；不放宽状态/几何/trace 断言。

- 已保存原 job 日志 63876 字节，SHA256 `af8a37335d586d9126774387337bd3d049f4ce6e922d4beb69ad11c31aca660e`；明确 KeyError: health 是首错，27 项相关（含路由）测试通过，SDK 生成一致性及既有门禁/摘要策略测试通过。

## 统筹 peer 两项产品阻断修复（待最终 head 原生验收）

- 只读核查 peer 原报告和 repro，并在本分支当前源码运行原 `repro.py docprops-line-style`：handler describe 抛错现在返回 mutation 双true；同一 ActiveDoc 对象的 stamp/dirty/title/path 四项漂移均返回失败，保留 mutation，不恢复/回滚。
- adapter 增加目标 title/path/access/仍打开保护；前台为不同peer时快照并复核 state(kind/config/stamp/dirty)、identity(title/path)、access 和 edit context；同目标前台仍允许合法目标 stamp/dirty 变化。未知/不可读状态 fail closed。
- `document_line_font_set` 收尾异常不再抛掉 receipt：ok=false，保留原 mutation 与首 error，新增可选 `finalization_error: {type,message}`，session_id已知；不伪造无法取得的 post descriptor。已同步 result schema / SDK models。
- 新增 `tests/test_line_font_postconditions.py` 通过生产 execute_operation + 实际 _worker_main + native_api_sequence + 结果校验/错误封套联测 native成功/首失败后describe故障；SDK/MCP bridge负例也保留 partial；全部无真实COM。
- 34项相关测试通过（含route），SDK strict typing/generator/consumer拒绝通过；原 peer复现输出与source hash保存在本地 artifacts/line-font/internal-peer-fix/，不是原生验收。
- 公开 gate 加逐次前台 descriptor完整比较，且记录状态观察 GetActiveConfiguration/Name。精确转换域不变，未放宽断言。
- c377d4f 的 run 42278005133 在 portable 阶段因这些已mock实证的产品缺陷请求取消；最终产品修复会形成新head，完成测试后才发必要公开run。不将旧head结果或mock当作最终native验收。

- 产品修复后一次完整便携回归：1853 tests，32 skips，全部通过；日志 `artifacts/line-font/postcondition-full-portable.log`。不是因统筹消息重复未改产品测试，而是 handler/schema/adapter实际变化后的回归。
- 精确修复入口：operations.py document_line_font_set（约440行）；windows_document_line_font.py _capture_guard（76）/_verify_guard（84）；result_schemas.py 的 line-font-set finalization_error（约563）；tests/test_line_font_postconditions.py 为完整 worker/transport 故障注入。源码SHA256绑定在本地 source-hashes.json，可由下一提交复核。
