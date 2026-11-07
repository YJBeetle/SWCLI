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

## 阶段 9：保存所有权修复已推送，新 head 一次校准
- 提交：`c097909fe0d929a853adce37fb2b98ceb83e6c24`（fix: 保持原生校准保存操作的宿主所有权），已 push 本分支；修复仅校准夹具保存调用，产品公开实现/SDK 不改，22 tests PASS。
- 唯一对应 head dispatch：<https://github.com/YJBeetle/SWCLI/actions/runs/42273663491>，已读回 head 匹配；targeted=true / native_full=false，默认媒体/清理参数。前两次失败的 run/head/ZIP/错误均保留，不原样重跑，不取消他人 run。
- 本地回执：`.task-evidence/dispatch/owned-save-fix-request.json`。无待审批动作，继续跟进同一 run；保存重开/拓扑变更和公开验收完成前仍非 merge-ready。

## 阶段 10：保存重开通过；实际删除失效状态校准
- run `42273663491` 最终在内部圆柱面删除状态断言失败。原 native ZIP artifact ID `13534426132`，SHA256=`197bf7346d0c74259d5b0e0e1805f590054b33ebca789f0221342f8e2931aa30`，GitHub digest/head=`c097909fe0d929a853adce37fb2b98ceb83e6c24` 已核。原 ZIP/report/trace 保存 `.task-evidence/ci-42273663491/`，cleanup_errors=[]。
- 本次额外已证实的内部范围：face/edge 基线 save、close/reopen（api errors/warnings=0）、重新解析成功；创建 hole 后原 reference 被拒绝；实际单体穿孔体积 `11717.256661176916 mm³`；mutated content 已保存；owned cut 删除返回成功。公开组未启动，notch 尚未执行，仍不能声明整体或公开验收通过。
- 首失败详情：删除圆柱面后 `GetObjectByPersistReference3` 实际返回 **Invalid=1 / NULL**；原先自设的 Deleted=4 预期失败，原始错误不抹去。官方 enum 的 Deleted=4 值确实存在，但“删除这个 fixture 一定返回该 bit”未被 API 文档保证，也未被实测支持。
- 新的有界夹具校准按实际 owning source 修正为 **恰为 Invalid=1 且 NULL**，额外增加保存后、唯一一次删除前同一 raw reference 恰为 OK=0 / 非空、且与当前唯一 native cylinder `IsSame=1` 的独立证明；再要求实际 box 体积、native save/reopen 和失效继续成立。此处不采用任意非零白名单，不改产品只接受 integer 0 + 完整双射的门禁，不放宽几何/保存/退出/时间断言。Deleted=4 与 Suppressed=2 继续明确列为原生未观察状态。
- 23 targeted/wiring tests PASS；新增 fixture 精确状态回归会拒绝 0、2、4、3、5、7、bool/float、对象仍存在等；日志 `.task-evidence/portable-invalidation-fix/targeted.log`。原 `Deleted=4` 失败仍保留在原 run；后续只对这一确切校准修正提交的新 head dispatch 一次。
- 产品代码未因三次校准失败改变；目前仍非 merge-ready。

## 阶段 11：精确失效夹具校准提交与对应 run
- 提交：`806620e45c0c55e92bfc41a594cffa015b1956e9`（fix: 按原生读回精确校准拓扑引用失效状态），已 push；最终 23 targeted/wiring checks PASS，日志 `.task-evidence/portable-invalidation-fix/targeted-final.log`。
- 唯一该 head dispatch：<https://github.com/YJBeetle/SWCLI/actions/runs/42278901394>，head 已核；targeted=true / native_full=false，默认安装参数。原三个 run/head 各自只 dispatch 一次，首错误与原 ZIP 均保留。
- 本地回执 `.task-evidence/dispatch/invalidation-fix-request.json`。继续等待该 run 的内部/公开组，不将历史部分成功当作整体验收；无待审批动作、merge-ready 仍为否。

## 本轮收口快照：停止轮询，待统筹后续分次核验
- 按用户最新指令，本轮只收口已做范围；不扩功能/计划，不新增审查子代理，不创建单个 CI 的自动定时，不再持续 sleep/轮询或无变化播报。不取消其他 run，不重复 dispatch，不为新 main rebase/重跑。
- 仅取最后一次状态：run <https://github.com/YJBeetle/SWCLI/actions/runs/42278901394>，测试源 head **`806620e45c0c55e92bfc41a594cffa015b1956e9`**；Build wheel、Windows Python 3.9 / 3.14 均 success；Targeted topology reference verification **in_progress，当前 Install native SOLIDWORKS**。此快照之后本轮停止查询。
- 快照原数据：`.task-evidence/dispatch/final-snapshot.json`；唯一 dispatch 参数/回执 `.task-evidence/dispatch/invalidation-fix-request.json`。代码与三次确切校准修正均已推送；当前产品提交链为 `74eeb7d` → `fa01d65` → `c097909` → `806620e`，最后三次只改校准/回归/文档，未改变公共产品身份门禁。
- **当前不是 merge-ready。** 最新 run 的原 native ZIP/digest、内部 hole 完整失效/最终重开、notch split/merge 与实际输出，以及公开 CLI/daemon/SDK/MCP native 组仍未核验，不把内部部分成功、便携、安装或 CI 运行中当成公共验收。
- 历史已证实的精确内部子集见阶段 8/10：官方真实类型库和 enums；单体 40×30×10 box（6 faces/12 edges）face/edge capture→resolve→rebuild→save/close/reopen→resolve；加穿孔后旧 topology census 拒绝；删除 cylinder 原生返回 Invalid=1/NULL（原先 Deleted=4 预期失败原件保留）。这些证据来自 `c097909` 及前一 run 的相同产品实现，尚不提供整套公开验收通过结论。
- 功能/接口差异：只读 `entity.reference-create` / `entity.reference-resolve`，显式 saved-path/configuration scope，完整 face/edge 双射，无几何最近重绑定；CLI 文件输入、生成 SDK、MCP capabilities/execute 沿现有 daemon/COM worker 路由。短 ID registry 未修改，无新增写入旁路，未知/非 OK native 状态仍拒绝。
- 已保留的原始 native ZIP/hash：42262912751=`0638ab1d99e71c5da1ff9dd9b682f13a6925dcbb368e6e581acbe206c10e5bfd`；42268048904=`c6ead8c9c858cf491c27258f2601ef01023be0a03f40c984889b903a75535a43`；42273663491=`197bf7346d0c74259d5b0e0e1805f590054b33ebca789f0221342f8e2931aa30`。各 run 目录内原 metadata/report/trace/first-failure.json 完整保留，未覆盖。
- 后续仅需统筹在当前 run 完成后读取一次状态并下载其原件，按 `.task-evidence/audit-native.py` 与原报告核验；已通过精确子集再由统筹本人 review/决定合 main 与发版。未完成项如实保留，不为凑齐无限迭代。本路无待授权/待审批动作。

## 阶段 12：按用户继续处理实际失败——notch 原平面识别修复
- 当前首因来自已结束 run <https://github.com/YJBeetle/SWCLI/actions/runs/42278901394>（head `806620e45c0c55e92bfc41a594cffa015b1956e9`）：内部 notch fixture 的选择器只用 +Y 法向，把 y=9、面积60 mm² 的槽底面与 y=15、各170 mm² 的两块原侧面一起计入，候选数3触发“必须恰好2个侧面”断言。
- 原 native ZIP artifact ID `13535707278`，SHA256=`8cc92f634ecebe8b9a61478a36b2c683c5b9ddad2876c0c33d8f4df195f2490b`，GitHub digest/head 已核。原 ZIP/metadata/report/trace 与结构化首因在 `.task-evidence/ci-42278901394/`，不覆盖历史原件。
- 同一 run 的 hole 内部场景已完整成功：删除前同一引用0/非空/IsSame=1→删除后Invalid=1/NULL，实际体积、保存、只读重开、持续失效和最终文件哈希均已独立核验；`hole.SLDPRT` SHA256=`f87dbf5747a96118203a490a778453a1a1f657aa1ecf3e4dd7aae8dad72bcbea`。这仍不是公共 CLI/SDK/MCP 验收，公开组因 notch 首失败未启动。
- 最小修复只在 calibration fixture：`notch_split_faces` 用 +Y 精确方向及原侧面 y=15 的平面偏移选择生成夹具，保留恰好2面的断言，并增加各170 mm²断言。槽底面 y=9 被排除；不使用最近几何、不修改持久引用解析/公开接口，不放宽任何原断言，不新增功能/字段/计划。
- 验证：24 targeted/CI wiring tests PASS；使用该原始 report 的真实10面列表离线复核，旧选择器确为3，新选择器恰为原两面。日志 `.task-evidence/portable-notch-fix/targeted.log`；原件离线复核不运行任何 CAD，也不重试原生操作。
- 用户明确继续当前系列实际失败处理；无待授权动作。只在此确切修复提交后对新 head 一次必要 targeted CI，正常运行即记录链接并结束本轮，不持续盯守。review 和最终合 main 由统筹本人负责，正式发布前用户确认。当前仍非 merge-ready：notch merge/save-reopen 与公开 native gate 尚待新证据。

## 阶段 13：notch 最小修复已推送并启动必要验收
- 精确 tip：`a62663accc8f5ec8753081a53c37145c01d9033a`（fix: 按原侧面平面位置识别拓扑分裂夹具），已 push `codex/swcli-topology-references`；24 targeted/wiring tests PASS。公开实现、契约、原生断言未放宽；只修夹具平面筛选并加强面积检查。
- 唯一新 head run：<https://github.com/YJBeetle/SWCLI/actions/runs/42301645599>，run/head 已读回匹配；`native_topology_targeted=true` / `native_full=false`，其余默认。当前一次快照 status=in_progress，conclusion=pending。
- 回执 `.task-evidence/dispatch/notch-fix-request.json`，状态 `.task-evidence/dispatch/notch-fix-snapshot.json`。原 run 42278901394 的首因、完整 hole 内部证据和原 ZIP/digest 已保留；无无差异重跑、CAD API 重试/回滚或组内重启。
- 按最新用户要求，新 run 正常运行后本轮结束等待，停止持续轮询；后续原件可用时由统筹分次跟进。当前不是 merge-ready：notch merge/最终重开及公开 native CLI/SDK/MCP 尚待该 run 证明。不扩新功能/计划，不创建 CI automation，不碰 main/DockerSW/MacSW；正式发布前用户确认。

## 阶段 14：内部两场景已验收，修正公开 runner 绑定地址

- [42301645599](https://github.com/YJBeetle/SWCLI/actions/runs/42301645599) 的 head 为 `a62663accc8f5ec8753081a53c37145c01d9033a`。Windows Python 3.9/3.14 与 wheel 构建通过。原 native ZIP artifact ID `13545456690`，SHA256 为 `c6046b83e11543932ea8115b953046fd0b98b18ed9be0aca14d3c82a462ebfff`，已核 GitHub digest、head，保留于 `.task-evidence/ci-42301645599/`，含原日志和 `first-failure.json`。
- hole 与 notch 的内部原生校准均通过，清理无错误。已独立核对两组修改态及最终态共四个 SLDPRT 哈希，以及只读重开后的 12000 mm³ 体积。hole 删除前 OK 且原生身份一致，删除后 Invalid=1/NULL。notch 的分裂、合并、保存重开和持续拒绝均通过。
- 公开组首个 `daemon status` 连接 `127.0.0.1:45191` 超时。原启动回执显示 daemon 实际监听 `127.0.0.1:18495`，因为 runner 把客户端的全局 `--endpoint` 当作服务端绑定参数。后续停止命令也使用错端口，进程等待超时是次生结果。公开组尚未执行引用用例。
- 修复只在 runner 和回归测试。使用 `daemon serve --host 127.0.0.1 --port 45191`，收到同端口且成功的服务启动回执后才运行公开组，并以该回执约束清理时发送的停止命令。25 项针对性检查通过，覆盖成功端口贯通与错误端口时禁止进入公开组。产品、并发策略及 CAD 验收断言不变。

- 端口修复提交 `2a431a1eccc7c0061b6791b0634cd817082bfd1e` 已推送。唯一新 head 验收 <https://github.com/YJBeetle/SWCLI/actions/runs/42305484520> 已核对提交，当前状态 `in_progress`，结论 `pending`。参数 `native_topology_targeted=true` / `native_full=false`。回执和快照见 `.task-evidence/dispatch/daemon-endpoint-fix-*.json`。待公开 CLI/SDK/MCP 原生证据，仍不可合并。

## 阶段 15：公开重开后的前台夹具修复

- [42305484520](https://github.com/YJBeetle/SWCLI/actions/runs/42305484520) 的 head 为 `2a431a1eccc7c0061b6791b0634cd817082bfd1e`。原 native ZIP artifact ID `13547291392`，SHA256 为 `dbe884fdfb8368c2b6588bb86e9ed70639fa25a56b5655b6d53d0122a8191c01`，已核 digest/head，完整保存在 `.task-evidence/ci-42305484520/`。
- 内部 hole/notch 再次全部通过，四个模型文件 SHA256 与原报告一致，重开体积 12000 mm³ 通过。公开 SDK face 和 MCP edge 的真实 daemon 解析都已成功，native_status=0。CLI 的捕获、后台读取、另一 session lease 下读取、跨文档拒绝、重建及 CAS 检查也已执行到后续保存重开。
- 首失败是公开夹具的前台准备。只读打开目标使其 active=true；随后 `document use b` 只设置 session current，回执中 b.active=false。接下来的 face 引用解析成功、observation.unchanged=true、目标 current=false / active=true，触发原有 background 断言。原始状态和完整错误已保存在 `first-failure.json`。
- 最小修复在 `verify-topology-references.py`。目标重开后关闭已完成任务的旧 b，再创建新的 owning foreground b，随后执行原有 active=false/current=false 断言。产品行为与断言保持原契约。25 项关联检查通过，日志 `.task-evidence/portable-reopen-foreground-fix/targeted.log`。
- 公开验收仍待完成重开后台 face/edge、保存后拓扑变更拒绝及最终输出内容检查。完成后由统筹本人 review，当前尚不可合并。

- 前台夹具修复提交 `f3259439507c8be03c7f2577c51e71f17233c15f` 已推送。唯一新 head run <https://github.com/YJBeetle/SWCLI/actions/runs/42361455599>，一次状态快照为 `in_progress`，结论 `pending`。参数 `native_topology_targeted=true` / `native_full=false`，run/head 已核。回执和快照在 `.task-evidence/dispatch/reopen-foreground-fix-*.json`，本轮结束等待。

## 阶段 16：本轮新原件独立审计通过，可交统筹 review

- 最终可审查/合入的代码 tip 为 **`f3259439507c8be03c7f2577c51e71f17233c15f`**，本地 HEAD 与 `origin/codex/swcli-topology-references` 一致，精确对应成功 run [42361455599](https://github.com/YJBeetle/SWCLI/actions/runs/42361455599)。本阶段只写持久审计数据和交接记录，代码 tip 保持该受测提交。
- 已收集该 run 的全新原件。native artifact ID **13570058206**，原 ZIP SHA256 **`d0968ef994392cce86e8c426b13cdfe98b4ed3da7ca3c1e4adcda33bd7d98f69`**。distribution artifact ID **13569676640**，原 ZIP SHA256 **`4cdae93201f85545788b92b9629a16f971f02e7cb7a4483d2d5d553c6d356100`**。两者官方 metadata 的 run/head/digest 均匹配，旧 run 原件仍单独留存。
- 独立离线审计通过。核对了四个必要 job 成功、原 ZIP digest、wheel 全部随包文件与三个 sdist gate 文件共99项源内容同受测 git commit 一致、两组内部场景、公开成功/拒绝覆盖、19个引用请求在单一 worker 上的 trace 边界、600/1800预算、前后台身份、空文档目录与正常停止。错误 head 和 ZIP 字节变动两项负对照均返回非零并给出对应拒绝原因。
- 原生范围为 Windows/SOLIDWORKS 2025 SP5 `33.5.0` 隐藏 owning host、Default 配置的单体 box/hole/notch。内部证明官方类型库签名、face/edge 捕获/解析、重建、保存重开、hole 删除失效、notch 分裂/合并及最终重开。公开证明 CLI 经 daemon 的 face/edge 持久引用、后台与另一 session lease 下读取、跨文档及 CAS 拒绝、只读重开后全量身份解析、切除后及重开后拒绝原拓扑、实际输出体积。SDK 方法和 MCP `DaemonBridge.execute` 的真实 daemon 解析均成功。
- 当前已核对最终公开 SLDPRT SHA256 **`26c590b9c0b407bb2ac7d97e8843756ac181b127e9a9ff054bc9a3f7f917e95e`**。只读重开测得原 box 约12000 mm³、最终穿孔体积 `11717.256661176916 mm³`。内部最终 hole SHA256 `27c31a5157e86fa70e27c4cf70f1d7e6e5b353710ba6c833c7d194df95dbe79c`，notch 合并后 SHA256 `af1c7b0aaa11489fbb37a2bc9cbb543ff1adf3cbbf4d755672cb0f98c0f682e6`，四个内部模型及公开最终模型均已从本轮原 ZIP 重算。
- 能力边界沿现有契约。已保存路径/精确配置、单 solid 无 surface body、各1–64 face/edge 的完整 census 原生双射；任意编辑历史、文件替换/移动/另存为、多体/装配不承诺永久稳定。Deleted=4、Suppressed=2 官方枚举值已读库，原生失效转移实际证实为 Invalid=1/NULL。MCP 本轮证据来自 execute 桥接，stdio 握手沿现有独立契约测试。本次 targeted 证据保留 `full_acceptance_eligible=false`；系列发布由统筹完成整组验收后请用户确认。
- 最新 WORK_HANDOFF 审计记录为工作树本地更新，审计脚本/原件置于 gitignore 的持久 `.task-evidence`，便于统筹复跑。产品代码无额外未提交改动。

完整路径如下。

- 原 native ZIP `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/native.zip`
- 官方 native metadata `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/native.metadata.json`
- 原 distribution ZIP `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/swcli-dist.zip`
- 官方 distribution metadata `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/swcli-dist.metadata.json`
- 官方 run/job 回执 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/run.json`、`jobs.json`
- 独立审计脚本 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/audit-topology-acceptance.py`，SHA256 `c7a9abc2a5864db45ab5149c786e10301b18776c0b2c3c95af6a1341c9da08fe`
- 独立审计报告 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/topology-acceptance-audit.json`，SHA256 `b3e9b998b8c27512450901e3f6b2ea29e75bcde56cce2f43d848ccc1a47c1f14`
- 全部关键原件/报告清单 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/evidence-manifest.json`
- 负对照记录 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/audit-negative-controls.json`
- 解压内部原报告 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/native/swcli-native-smoke/topology-targeted/internal/report.json`
- 解压公开原报告 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/native/swcli-native-smoke/topology-targeted/public/modeling.json`
- 解压公开 trace `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/native/swcli-native-smoke/topology-targeted/daemon.stderr.log`
- 解压最终公开模型 `/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599/native/swcli-native-smoke/topology-targeted/public/references.SLDPRT`

可复跑命令如下，读取本轮原 ZIP 和固定受测 commit，失败时返回非零。

```sh
/Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.venv/bin/python \
  /Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/audit-topology-acceptance.py \
  /Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI/.task-evidence/ci-42361455599 \
  --repo /Users/YJBeetle/.codex/worktrees/swcli-topology-references/SWCLI
```
