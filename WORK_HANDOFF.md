# 稳定实体引用与拓扑变化检测

## 阶段 1：范围与共享接口（2026-11-07）
- 分支：`codex/swcli-topology-references`；建立基线与当前 HEAD：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`，初始 worktree 干净，无 `.codegraph/`、无仓库 AGENTS.md（遵循父目录 CodeGraph 条款）。
- 仅本 worktree；不修改 DockerSW、MacSW、main、版本或发布，不使用本地 VM。
- 计划新增只读 `entity.reference-create` / `entity.reference-resolve`，CLI `entity reference-create` / `entity reference-resolve`；由现有客户端 → daemon → COM worker 路由，自动生成 SDK/MCP 契约。
- 与既有 `e-*` 短 ID 分离：不延长旧 ID 生命周期。解析成功只发布当前观察范围的新/现有短 ID，不提供写入权限旁路。
- 显式 scope：已保存 `.SLDPRT` 的 Windows 规范化绝对路径、精确配置、单 solid 无 surface body、完整 face/edge census（各 1–64）。拒绝未保存、另一路径、另一配置、缺失/非 OK 原生状态、重复映射、拓扑 census 非双射；不进行最近几何重绑定。
- 保守边界：不是跨任意修改永久稳定标识；路径不是不可伪造的文档 UUID，序列化引用不是授权凭证；不证明未观察到的编辑历史。只承诺原生引用当前可唯一解析且完整已记录拓扑仍能对应。
- 官方依据：IModelDocExtension.GetPersistReference3 / GetObjectByPersistReference3 / Persistent Reference IDs（SOLIDWORKS 官方 API Help）；真实 swconst + sldworks 类型库及保存重开证明留待本分支 Windows targeted 校准。
- 将触及共享文件：operation_schemas.py、result_schemas.py、daemon/operations.py、cli.py、SDK 生成文件；新增隔离的 contracts/host helper/test/CI 校准脚本。与主对话合并时需按契约处理冲突。
- CI：仅新增显式 workflow_dispatch targeted 选项，默认 false；保留既有 PR/secret/default gate。计划便携与 CI 接线测试后仅 dispatch 本分支对应 head 一次；600s/native call、1800s/group，无组内重启/失败原生操作重试。
- 测试/提交/CI run/原生证据：尚未执行或产生。内部校准和公开验收分别记录，未满足保存重开前不声明完成。

## 阶段 2：实现与便携检查完成，待本分支原生校准
- 实际新增 `entity.reference-create` / `entity.reference-resolve`、CLI `--reference-file`、生成式 SDK 方法/TypedDict；MCP 通过既有 capabilities/execute 路由，未新增 COM 公共入口。
- 新增 contracts：`src/swcli/topology_references.py`；COM 身份双射：`hosts/windows_topology_references.py`；worker 公共编排：`daemon/topology_references.py`。共享接口改动：operation_schemas/result_schemas/cli/daemon.operations/sdk generated；既有短 ID registry 不修改。
- 保存路径＋配置精确 scope、完整 faces/edges 双射；原生非零/未知/未写状态、重复映射、跨文档、CAS、最终状态变化均拒绝。失败无 usable handle/reference；首原生错误在最终状态/descriptor 再失败时仍保留。仅新增只读操作，无未知写入白名单。
- 文档：`docs/design/topology-references.md` 与 README；公开限制包括不证明所有几何/邻接/编辑历史不变、路径不是不可伪造文档 UUID、复制/替换/移动不承诺存活。
- 便携：Python 3.14 全套 1839 tests，32 skipped，PASS；包含新增 20 targeted checks。SDK generator/strict mypy 和 11 consumer typing refusals PASS；installed commands/schemas/skill PASS；workflow YAML parse / diff whitespace PASS。
- 持久原始便携证据：`.task-evidence/portable/unit-final.log`、`sdk-types.log`、`targeted.log`（targeted.log 为 descriptor 最终保护测试加入前 19 tests；全套日志包含最终 20 项），未使用 tmp 作为主证据。
- 内部原生脚本：`verify-topology-calibration.py`（实际 swconst 与 IModelDocExtension 签名；hole 删除、notch 面分裂/合并；重建、保存重开、体积及 SHA256）。公开脚本：`verify-topology-references.py`（CLI/SDK/MCP、后台/lease/CAS/另文档、face/edge 保存只读重开、公开 cut 后拒绝与实际输出体积）。`run-topology-targeted.py` 分开记录内部和公开，均非 full release evidence。
- CI：新增默认 false 的 `native_topology_targeted`；仅本分支 workflow_dispatch 且 native_full=false；test/package 前提保留；专属 `swcli-topology-targeted-${github.ref}` concurrency、cancel-in-progress=false；默认 full/release group 仍为 swcli-hosted-windows-solidworks。600s 原生/请求、1800s 每组，无组内重启和失败 CAD 重试；不取消他人 run、不为排队重复 dispatch。
- 提交：本阶段功能提交（精确 SHA 在提交/dispatch 后补记）。CI run/head/参数与原生证据：尚未产生。**未达到 merge-ready，不声明 Windows 原生或公开验收通过。**

## 阶段 3：已推送并首次 dispatch
- 功能提交/测试源 head：`74eeb7d4bfa9c600b9f1abe5d84aa3c64c53f5ee`（feat: 增加有界实体持久引用与拓扑变化检测），已 push `origin/codex/swcli-topology-references`。
- 唯一手动 targeted dispatch：<https://github.com/YJBeetle/SWCLI/actions/runs/42262912751>，run head 已读回匹配上述 SHA；参数 `native_topology_targeted=true`、`native_full=false`，其余媒体/清理参数保留 workflow 默认；未向其他分支触发，不为排队重复 dispatch。
- 本地回执：`.task-evidence/dispatch/request.json`。当前 run queued，portable/package/installed Windows 内部校准、公开验收与原始 artifact ZIP/digest/trace/save-reopen 仍待核验。
- merge-ready：否。不会把 queued 或便携成功表述为原生通过，也不自行合 main/发布。

## 阶段 4：CI 便携/构建已通过，原生安装准备中
- 同一 run `42262912751` 的 Windows Python 3.9 / 3.14 和 Build wheel 均 success；Targeted topology reference verification 已启动，尚在 disposable runner 磁盘准备阶段，未产生原生结论。
- 已独立下载原 `swcli-dist` artifact（ID `13525796665`），GitHub head=`74eeb7d4bfa9c600b9f1abe5d84aa3c64c53f5ee`；原 ZIP SHA-256=`8d5b047d7036d352fc81dac5907be9c08457a0b03100a9b8edc788e0879edd4e` 与 API digest 一致；wheel 内 9 个关键源文件与该提交逐字节一致。
- 包原始证据：`.task-evidence/ci-42262912751/swcli-dist.zip`、`swcli-dist.metadata.json`、`distribution-proof.json`。已准备独立 `.task-evidence/audit-native.py`，待原生原 ZIP 上传后核验内部报告/官方类型库/公开 trace/保存重开/实际文件哈希；目前仍非 merge-ready。

## 阶段 5：首失败已留证，修复类型库读取入口后才能重跑
- 首次 run `42262912751` 最终 failure；安装、wheel、Windows portable 均 success，内部校准在创建任何模型前的 `app._oleobj_.GetTypeInfo()` 返回 `com_error(-2147319765, Element not found)`。这不是 persistent API 或 CAD 读写校准结论；公开组未启动，cleanup_errors=[]。
- 原生原 ZIP artifact ID `13528136038`，SHA-256=`0638ab1d99e71c5da1ff9dd9b682f13a6925dcbb368e6e581acbe206c10e5bfd`；已与 GitHub digest/head 匹配，完整保留于 `.task-evidence/ci-42262912751/native.zip`。解压原 report/trace 位于 `native/swcli-native-smoke/topology-targeted/internal/`；原始错误与 traceback 未替换。
- 首次真实 swconst 已证实：OK=0 / Invalid=1 / Suppressed=2 / Deleted=4 / swDelete_Absorbed=2 / Blind=0 / ThroughAll=1 / ThisConfiguration=1。尚未证实接口签名、创建/解析、分裂/合并、删除状态及保存重开。
- 修复限于校准脚本：不依赖运行对象 ITypeInfo，按官方 Type Libraries 文档直接 `pythoncom.LoadTypeLib` 读取同安装目录的 `sldworks.tlb`，记录实际路径与文件 SHA256；缺失文件在启动 host 前拒绝。签名/状态断言、600/1800、独立 host 及 secret/concurrency 门禁均不放宽，无 native fallback/retry。
- 修复针对性与 CI 接线检查：21 tests PASS（含缺失真实类型库在 host 前拒绝）；持久日志 `.task-evidence/portable-typelib-fix/targeted.log`。仅此确切修复提交后才允许新 head 一次必要 dispatch，未重跑首个失败 head。
- merge-ready：否。

## 阶段 6：类型库入口修复已推送并一次 dispatch
- 修复提交：`fa01d65c16e83732b8c02319be355a03550d78f5`（fix: 直接读取安装类型库完成原生签名校准），本分支已 push；未修改公开操作/SDK 契约或 CAD 实现。
- 新 run：<https://github.com/YJBeetle/SWCLI/actions/runs/42268048904>，已读回 head 精确匹配修复提交；`native_topology_targeted=true` / `native_full=false`，其余默认。此 head dispatch 一次，首失败 head 未重跑。
- 便携修复日志：`.task-evidence/portable-typelib-fix/targeted.log`（21 tests PASS）；原生首失败结构化摘要 `.task-evidence/ci-42262912751/first-failure.json`。
- 新 run 仍在前置任务，原生接口/拓扑/public 保存重开仍待证实，merge-ready 仍为否。

## 阶段 7：授权与当前待办（统筹最新口径）
- 当前没有待授权/待审批动作；指定 worktree 写入、中文提交/push、本分支定向 dispatch 均已按既有授权执行，自动审批未拒绝。不占用本地 VM，不修改 DockerSW/MacSW/正式分支，不自行合 main/发布。
- 修复 run `42268048904` 的 Windows Python 3.9 / 3.14 与 Build wheel 全部 success；Targeted job 已完成磁盘准备，当前在安装 native SOLIDWORKS，尚未产生该 head 的原生校准结论。
- 同一 run 原始 swcli-dist artifact ID `13527601916`，ZIP SHA256=`ee695c37763b9b5e29a93fc8fbcf398d4bfa6b9201ee12032e17ee35e156a6fd`，已核 GitHub digest、head=`fa01d65c16e83732b8c02319be355a03550d78f5` 及 wheel 内 9 个关键源码逐字节匹配；原 ZIP、metadata 与 proof 在 `.task-evidence/ci-42268048904/`。
- 后续：等待同一 run 的内部＋公开组结束；独立核原 native ZIP/digest/head/trace/save-reopen/实际输出后再提供可合提交。当前仍非 merge-ready，不等其它路，也不因普通推进再请求确认。

## 阶段 8：实际签名与初始引用读回通过；夹具保存入口修复
- 修复 run `42268048904` 最终 failure；原生原 ZIP artifact ID `13532305425`，SHA256=`c6ead8c9c858cf491c27258f2601ef01023be0a03f40c984889b903a75535a43`，GitHub digest/head 已核，原 ZIP/metadata/report/trace 完整保存在 `.task-evidence/ci-42268048904/`。
- 已证实精确内部范围（不是公开验收）：SOLIDWORKS 2025 revision `33.5.0`；实际 `C:\Program Files\SOLIDWORKS\sldworks.tlb` SHA256=`585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`，IModelDocExtension GetPersistReference3 参数 1、GetObjectByPersistReference3 参数 2（第二参 BYREF I4）、DeleteSelection2 参数 1，全部严格通过。6 faces/12 edges 的已保存单体 box 上，face/edge capture、即时 resolve、原生 rebuild 后 resolve 均 ok 且 native_status=0。
- 首失败在校准脚本的保存入口：调用 `save_active_windows_document(document=document)` 漏传已拥有的 `app`，helper 进入 ROT 查找并返回 HostNotRunning / Operation unavailable，保存 API 未执行；之后清理 CloseDoc/ExitApp/WaitForOwnedProcess 错误原样保留为次要 cleanup_errors。最终 runner cleanup 另已 success。此失败不等于保存重开通过，公开组未启动。
- 纠正：新增本脚本 `save_owned_document(app, document)`，所有三处保存都明确传入同一 app/document，不进入 ROT/COM 初始化/退出分支；产品 daemon 本来已正确传 app，公开实现未改。没有 native fallback/retry，没有放宽任何保存、退出或几何断言。
- 回归：22 targeted/CI wiring tests PASS；新测试运行真实 save helper 并使 ROT / CoInitialize / CoUninitialize 路径一旦进入即失败，确认 Save3 仅调用一次且同一 owning STA 保留。日志 `.task-evidence/portable-owned-save-fix/targeted.log`。
- 仍未完成：保存重开、hole 删除/notch 分裂合并、公开 CLI/SDK/MCP native gate；merge-ready 否。下一次仅在该确切修复提交后对新 head dispatch 一次，首两个失败 head 均不重跑。
