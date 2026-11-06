# 线型 / 线宽默认设置交接

**收口状态：产品实现与已知 peer 阻断已修复并推送；最终公开验收正在运行，尚非 merge-ready。停止本地持续 sleep/轮询，不建 CI automation，由统筹后续分次快照回收原件。没有待审批动作，不自行合 main/发布。**

产品精确 tip：`80b61334537d9394b19da03dee9d7baa08da58e8`。
本次交接提交只更新本文档，不改变产品、gate 或 schema。

## 当前唯一需要跟进的公开 run

- [42282239432](https://github.com/YJBeetle/SWCLI/actions/runs/42282239432)，GitHub 已核 head=`80b61334537d9394b19da03dee9d7baa08da58e8`。
- 参数：`line_font_public=true`、`line_font_calibration=false`、`native_full=false`；media_path/assets_path/cleanup_profile/vfs_cache_gib 均 workflow 默认。
- 收口仅取一次状态：`in_progress`；Build wheel success，Windows 3.9 / 3.14 portable jobs 进行中；native job 尚未产生最终结果。仅为该产品修复 head 触发这一次必要公开验收，未因正常排队重发。
- 专属 concurrency=`swcli-hosted-windows-line-font-public`，不进入默认 full/release 的共享组；不扩 PR secrets。600s请求 / 1800s group，首个非预期失败停止，无 native API重试/回滚/组内重启。
- 后续若失败：先下载 `swcli-windows-hosted-42282239432-*` 原ZIP与metadata，核 head/digest，再看 `line-font-public/line-font-public.json`、events journal、daemon stderr、SDK/MCP回执、source/changed文件hash与第一真实失败。只有相关修复后才新验证。
- 若成功：还须独立核原artifact/head/digest/trace/save-reopen与foreground完整状态，才能把精确已测子集交统筹合并。当前不可将 CI在跑、内部校准或 mocks 当成最终公开验收。

## 范围与接口 diff

- 唯一 worktree `/Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI`，分支 `codex/docprops-line-style`，创建基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`；初始干净，无 .codegraph。
- `document.line-font` / `swcli document line-font`：`options` 四字段完整 native integer map。
- `document.line-font-set` / `swcli document line-font-set FIELD VALUE --if-options JSON`：输入 `field`、`value`、完整 `expected_options`；沿用 document_id / expected_update_stamp / lease_id。
- 字段：visible_edges.style / visible_edges.weight / hidden_edges.style / hidden_edges.weight。仅 drawing 文档默认值。
- 开放域仅 revision **33.5.0**：visible style 0→1、visible weight 1→0、hidden style 1→0、hidden weight 0→1；0/1 noop无setter。逆转换、其他版本、weight 2、自定义厚度、线宽表、端帽、实体/层/组件覆盖、parts/assemblies、全局系统偏好均不开放。无网格/基准面/注释箭头字段扩展。
- 官方 API：IModelDocExtension Get/SetUserPreferenceInteger + swDetailingNoOptionSpecified，ID 从标准安装位置官方 swconst.tlb 按名解析；文档依据见 `docs/design/document-line-font.md`。
- 正常回执：field / before / options / changed / mutation；描述符收尾故障新增可选类型化 `finalization_error: {type,message}`，保留 mutation 与首 error 原值、已知session_id，不伪造无法取得的post descriptor。SDK models已同步。

## 两项 peer 产品阻断的现 head 证明（mock-only）

来源为只读 peer 报告 `docprops-coverage-ci/SWCLI/docs/verification/docprops-handler-peer-review-2026-11-07.md` 与原 `repro.py`，不是原生现场故障。

1. `operations.py:440 document_line_font_set` 捕获 `_with_document` 收尾异常，adapter receipt仍是唯一mutation事实。新增真实 `_worker_main -> execute_operation -> adapter -> handler -> result validator -> error envelope` 测试：native成功与首native失败后describe抛错，worker响应仍带mutation双true；SDK/MCP bridge也保留部分结果及首error。
2. `windows_document_line_font.py:76 _capture_guard / :84 _verify_guard` 保护目标title/path/access/仍打开，以及不同前台peer的kind/config/stamp/dirty/title/path/access/既有sketch-sheet上下文；同一ActiveDoc指针不再代表状态不变。拒绝漂移，不恢复/回滚；目标本身为前台时仍允许合法目标stamp/dirty变化。

- 在当前源码运行 peer 原 `repro.py docprops-line-style`：描述符异常现在返回mutation双true；同指针foreground stamp/dirty/title/path四项均拒绝，setter仍只调用一次。
- `tests/test_line_font_postconditions.py` 包含完整worker与SDK/MCP负例；额外保护configuration/access/sketch、目标身份/关闭、mutation前漂移。34项相关测试通过。
- 产品变化后完整便携回归 **1853 tests passed，32 skipped**；`artifacts/line-font/postcondition-full-portable.log`。SDK generator/strict typing/8项consumer拒绝通过。
- 本地持久 mock 原输出及精确源码/repro hashes：`artifacts/line-font/internal-peer-fix/`（implementation_commit=80b6133...）；不把 mocks 宣称为原生验收。
- 公开gate已增加逐次foreground完整descriptor比较；typed SDK read/noop 与 MCP live bridge execute/noop包含，**不宣称 MCP stdio transport 验收**。

## 已核内部原生证据（与公开证据分开）

- [42260712677](https://github.com/YJBeetle/SWCLI/actions/runs/42260712677)，head `6f531a595a50bbadeeab2c0f005d89c0246c7ee5`，success；line_font_calibration=true / native_full=false，其他默认。
- artifact id `13526587857`，SHA256 `5d8152062aea15f32d40c10f0947f36bceb0458702387fff0f2ef09b5ecc64e9` 已与GitHub digest核一致。
- 每字段1 setter / 12 preference getters，四项精确转换、背景文档、save/reopen、readonly拒绝与owned host清理通过；完整原ZIP/metadata/expanded本地保存在 `artifacts/line-font/internal-42260712677/`。
- 独立审计 `artifacts/line-font/internal-audit.json`，脚本 `scripts/ci/audit-line-font-calibration.py`；fixture SHA256 `92cae239235e0a5193ef0ff9577c48913cde3dc3137f5d8a30601c559cc08d98`；report `879d12f4821198e5d61fda9ebefb2e6c407dc93a95036a01fe43de1bb185ee6e`；trace `9bae5562b290c1b6865d14c768b68debae85d5bab23aa7d62833d059187a14e4`；process log `f17c814825db46044a9101cef0e054312b5949b648e3a494ff8cda8dae91248b`。
- 此证据建立叶API/值域，不代替最终保护修复 head 的公开验收。

## 已保存的真实公开失败与更正

- [42272391578](https://github.com/YJBeetle/SWCLI/actions/runs/42272391578)，head a783b498...，failure；artifact id 13533098590，SHA256 `a3064f349b415f4c7cc5f7435a7d3a5e7607f2821c66a2d36c46cf50fe4fddbb` 已核。
- 本地 `artifacts/line-font/internal-public-42272391578/` 保有原ZIP/metadata/expanded/job log；原job log 63876字节，SHA256 `af8a37335d586d9126774387337bd3d049f4ce6e922d4beb69ad11c31aca660e`。
- 第一真实失败为 gate `KeyError: health`，还未进入line-font读写；未预建summary导致final checkpoint报stat失败，原job log仍保存首错。二者均已在 c377d4f 修复并联测。
- **撤回先前错误的“共享 ModelingSmoke.health 不兼容”提醒**：普通 CLI `daemon status` 走 `daemon.health`，基类helper与该路径兼容；只有 `--details` / DaemonManager.status 走嵌套runtime-status。是本分支先前混淆路由，不要把那条提醒应用到其他分支。
- 其他取消/误触发仅历史，不算验收：42260403395（native前并发组修复）；42266835193（错误health判断后取消）；42269536427（真实worker命令scope parser修复前取消）；42272160735（GitHub拒绝push时误指旧head，立即取消）；42278005133（peer已mock证实产品缺陷，portable阶段取消）。无其他线程run被取消。
- Parser现在严格核真实owned worker CommandInProgress进入/恢复，再核业务pref读写、状态观察与request边界；没有放宽状态/几何断言。

## CI路由、共享文件与权限

- bc619f3 修复真实空绿路由：portable安装前拒绝 native_full / line_font_calibration / line_font_public 多选，以及线型开关错误branch；56组组合、CLI env解码与YAML接线测试通过。默认portable、单独full及合法tag-policy路径保留。
- 共享修改：cli.py、daemon/operations.py、operation_schemas.py、result_schemas.py、SDK _generated.py/models.py、.github/workflows/ci.yml；其余线型专属文件。复用annotation的上下文保护helper，未改其字段。最终冲突由统筹处理。
- 保留 main 已有0e72beb，不为本轮rebase/合其他未验收分支；未操作占用VM、DockerSW/MacSW、main或发布。
- 曾被自动审批拒绝：将原native ZIP/metadata/audit一并推送至可见性未核的远端，因可能含内部日志/测试文件。已采用获准安全替代：原件仅本地持久保留；远端仅推代码、便携测试与hash/永久run引用摘要。未绕过审批，当前无待审批动作。
