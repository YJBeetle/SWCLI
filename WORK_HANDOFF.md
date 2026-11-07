# 基础装配配合第一批

- Scope: 当前装配配置中两个不同顶层已解析零件的平面重合、圆柱同心标准配合；不包含高级/机械配合、子装配、自动浮动、自动求解重试或回滚。
- Baseline: `3bda2c00489dde6a3d1e4521c548f751b1d1c197`; branch `codex/swcli-assembly-mates`。初始工作树干净，无 `.codegraph/`、无仓库内部 AGENTS.md。
- Proposed interfaces: `assembly.mate-targets` 读取当前组件/配置与面几何快照；`assembly.add-mate` 使用完整 `expected_value` 快照、显式面描述、公共 lease / expected_update_stamp。仅以组件名称+路径+配置+当前面序号及完整读回几何作受限瞬时目标，不发布稳定引用，也不依赖未验收引用分支。
- Shared files planned: operation/result schemas, daemon operations, CLI, generated SDK; 新增独立 adapter、测试与手动 targeted CI 入口。原有默认门禁保持。
- Safety: 尚未原生校准的 public mate 写入 fail closed；仅内部 owned calibration 可传内部许可。首次失败保留原错误与 partial mutation，不自动 CAD 回滚/重试。
- Tests/commit/CI: 尚未运行；原生 API 文档调查中。未占用本地 VM。
- Boundaries: 本分支未合入、未发版，尚无原生保存重开证据。

## 阶段：实现与便携测试
- 已实现 `assembly.mate-targets` / `assembly.add-mate`，完整 schema、CLI、生成 SDK、daemon handler。瞬时目标要求固定组件在前、浮动组件在后；恰好两个顶层单实体零件，ASM/PRT 均只有一个配置，面仅平面/圆柱。私有持久引用仅用于本次读回身份校验，不发布稳定句柄。
- COM adapter 首次调用创建后即标记 partial mutation，原生失败/求解失败不重试、不回滚。公开写入仍返回 `MateWriteNotCalibrated`。
- 本地首轮 14 项针对性测试通过（Python 3.14）；尚未原生验证，不能称功能验收完成。
- 已新增 owned 内部校准：两种配合×两种对齐，类型库成员/枚举校验、几何残差、实体归属、源文件 hash、关闭所有引用后 ASM 保存重开。公开验收独立标记未运行。
- 根据统筹并发纠正，新增专用 `assembly-mates-calibration` job，手动 bool 默认 false，仅本开发分支和 workflow_dispatch 可触发，concurrency=`swcli-assembly-mates-${{ github.ref }}`、cancel-in-progress=false。原 full/release job 未修改。
- 外部 supervisor 限原生调用组 600 秒/总组 1800 秒，失败保留原始 report/trace/文件，不重建 host。
- 未 commit/push/dispatch；正在接线测试和整体便携校验。

## 阶段：提交前验证
- 最新便携全套：`1837 tests`, `OK (skipped=26)`，Python 3.14，日志 `evidence/portable/all-tests.log`。本功能独立 18 项通过，日志 `evidence/portable/assembly-mates-tests.log`。
- SDK 生成一致性、strict mypy 与 8 个负向消费类型场景通过；wheel/sdist 构建和源包内容验证通过；actionlint v1.7.12 通过（无语法问题，日志含依赖下载信息）。
- 手动输入最终名 `assembly_mates_calibration`。独立 job 并发按功能+ref 隔离，未修改 full/release 的并发组和执行体，未放宽现有测试断言。
- 原生/公开边界：尚无 Windows 原生证据；本 head 公开写入仍 fail closed。内部校准后将继续单独公开 CLI→daemon→worker 验收，再提出精确开放范围，不以内部脚本代替公开验收。

## 阶段：Windows 内部校准已触发
- 功能提交已 push：`886131e9d033bc5b83e2285d119ee0e319a6fcf1`（`feat: 添加受限装配标准配合与独立原生校准`）。
- 唯一已触发内部校准：[run 42263284406](https://github.com/YJBeetle/SWCLI/actions/runs/42263284406)，对应上列精确 head；参数 `assembly_mates_calibration=true`, `native_full=false`；未对其它分支 dispatch。
- 原始 dispatch/run 记录在 `evidence/internal-dispatch.json`、`evidence/internal-run-42263284406.json`。正常排队不重复 dispatch、不取消他人 run。
- 当前仍待原生结果/原 ZIP/digest/trace/实际 SLDPRT+SLDASM 审查；公开写入仍关闭，未达到 merge-ready。

## 后续公开 gate 准备（尚未提交/触发）
- 按统筹最新指令继续准备公开 CLI gate：所有零件、装配、配合、拒绝、SaveAs/Save3、可写与只读重开均经 CLI→daemon→COM worker，脚本不导入 COM，也不使用私有 `_calibration`。
- 一组四种组合、同一个全新 owned daemon/host，配合目标为后台文档；包括 lease 外来调用、完整值 CAS、只读拒绝和源/输出文件 hash、组件关系/配合内容读回。
- 新增阶段输入 `assembly_mates_stage=internal|public`（默认 internal），复用专属 job 的隔离并发和外部 600/1800 预算。当前 886131e 的内部 CI 不受这些未提交准备影响。
- 在内部原 ZIP/head/digest/trace/保存重开审查通过前不开放公开写入，也不触发 public stage。

## 内部 CI 进展与公开准备验证
- Run 42263284406 的 Windows Python 3.9 / 3.14 便携 job 与 package 全部成功；专属原生校准 job 已获得 runner 并开始安装流程。默认 full/release job 均 skipped，符合输入范围。
- 公开 gate 的便携准备测试覆盖四组合、源引用自动卸载、关系改变/缺失引用/截断输出拒绝、首失败停止，以及真实 CLI 参数解析；共 23 项针对性测试通过，public 阶段 actionlint 通过。
- 未因正常排队重 dispatch，未取消他人 run，公开 gate 尚未原生执行。

## 公开 gate 阶段实现完成（本地待提交）
- 公开 gate 准备后的全套便携回归：1843 项通过，26 平台跳过；随后补充最终同心 `LockRotation` 定义读回及精确 native revision 许可守卫，对应最新 26 项针对性测试通过，SDK 生成/严格类型继续通过。
- `CALIBRATED_WINDOWS_REVISIONS` 当前为空、公开 flag 仍 false。未经证实的其它 native revision 不会因将来开放某个 revision 而获得写许可。
- 公开阶段仍未触发。没有把内部校准脚本的 private permission 引入 CLI/protocol/SDK/MCP 参数。
- 内部 run 42263284406 仍对应 886131e，在独立 runner 上安装 SOLIDWORKS；本地后续准备不改变该 run 的 head。
- 公开许可还检查真实原生 Windows，Wine 与未知/不可读 runtime 不能因相同 SOLIDWORKS revision 获得写许可；新增回归后最新 27 项针对性测试通过。

## 分发工件独立核验
- 本地公开 gate/许可准备已提交但未 push：`efb8bfc4696ac0cbc7f82e573037562d326c1dba`，空公开许可名单保持。
- 已保留 run 42263284406 原始分发 ZIP：`evidence/run-42263284406/swcli-dist-13525408428.zip`；SHA-256 与 GitHub artifact digest `ea519c0cefb90dd52b1b0dfc3a457dcd991bfcc11fdfbdd056ff9d5537a3926e` 一致。
- wheel 内全部 Python 源字节逐文件对比精确 CI head 886131e 一致，包含原生配合 adapter；明细 `distribution-verification.json`。这是分发溯源证据，不是原生/公开验收。

## SDK 兼容性补充
- 审查生成 diff 发现，若把新 operation 插在旧 schema 前，generator 的相同结构去重会删除旧导出 `FeatureFilletResultMutation`。已把两个新 operation 追加在既有 catalog 后，保留旧导出与既有 operation 顺序。
- 新增真实旧类型的正向 mypy 消费测试；严格 SDK 与 27 项本功能测试通过。未修改 generator 的全局策略。

## 首次原生失败与修复准备
- 内部 run 42263284406 已失败：仅第一组目标面观察返回 `com_error (-2147352565, Invalid index)`；尚未执行 CreateMate，没有配合创建或保存重开成功证据。
- 官方 swconst 枚举及必需 sldworks 成员检查通过；宿主 revision `33.5.0`。TLB SHA-256：swconst `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`，sldworks `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`。
- 原始 ZIP：`evidence/run-42263284406/swcli-assembly-mates-13526653759.zip`，digest `8471e5b44b9fe789a0cf1f565766dbc06b093f758b1db4c899c8e7e8f1a71ad2` 匹配；原解压 report/trace/PRT 保留，宿主清理无错误。
- 当前怀疑是嵌套面对象 IDispatch.GetTypeInfo 路径，不将猜测当作已证实根因。修复改从应用的官方类型库查 IID，在目标对象 QueryInterface，避免要求面对象提供 type info；新增拒绝 GetTypeInfo 的真实形态便携回归。
- 首轮外层 trace 未逐 COM 调用记录，现为 owned case 启用 native_trace，并保留原 COM 异常 traceback；不放宽几何、身份、求解或保存断言。公开许可仍为空。
- 最终修复避免对面对象或应用对象调用 GetTypeInfo：从该 COM 宿主真实 PID 的 OS image 路径定位同安装的 `sldworks.tlb`，再读取官方 IID 并 QI 目标。只读查询句柄按 finally 关闭，无其它安装搜索和猜测 GUID/IID。新增对应 PID/path/关闭句柄回归。
- 同时把写入精确范围收紧为第一条标准配合，或已有 aligned 重合后补 aligned 同心（最多两条）；内部与公开 gate 均加入该实际组合的求解、关系及保存重开，未知其它组合在提交前拒绝。

## 修复 head 提交前验证
- 最新完整便携回归：1849 项通过、26 平台跳过（`evidence/portable/native-fix-all-tests.log`）；本功能 30 项通过，SDK 生成/严格类型与 8 负向消费场景通过，actionlint 通过。
- 首失败可审查摘要：`docs/verification/assembly-mates-first-failure-2026-11-07.json`；仍无原生配合成功证据，未开放任何公开写入。
- 下一次只对包含具体接口读取修复的新 head 调用 internal stage 一次，不对原失败 head 原样重跑，不取消其它任务。

## 修复后第二次内部校准已触发
- 所有本地修复/公开准备已 push 到唯一分支，当前 head `b456bbc4558717f7220e0d7a55a9babfeeef29ad`。
- 新 head 的唯一 internal dispatch：[run 42268147736](https://github.com/YJBeetle/SWCLI/actions/runs/42268147736)，参数 `assembly_mates_calibration=true`, `assembly_mates_stage=internal`, `native_full=false`；前一失败 run 42263284406 未原样重跑。
- 溯源记录 `evidence/internal-dispatch-b456bbc.json`；仍待原 ZIP/digest/逐调用 trace/组合配合及保存重开证据。公开名单继续为空，不是 merge-ready。
- 另按基线 AST 导出逐项核验，既有 SDK public model 导出均保留，明细 `evidence/portable/sdk-export-compatibility.json`。

## Fixture 身份消歧准备
- 由首失败原 report 可见 GetTitle 对 PRT 返回无扩展名标题。发现生成 PRT/ASM 同 basename 会使 native CloseDoc/后台激活名称存在歧义，已将源命名为 `*-component.SLDPRT`、目标保留 `*.SLDASM`；两个 native/public fixture gate 同步，且有文件 stem 不相交回归。
- 这是本地待提交 fixture 修正；正在运行的 b456bbc / run 42268147736 保持原 head，没有取消或重 dispatch。公开许可仍为空。
- 公开许可开放前还在落实已有“仅外部已保存零件”边界：新增真实 `IComponent2.IsVirtual` 布尔拒绝与非空 `.SLDPRT` 文件检查，不增加请求参数或扩大支持范围；官方属性文档已核，后续 native preflight 同时核此成员。
- target 读操作补充前后真实 ActiveDoc 身份一致性检查：若读取过程中用户/原生行为切换前台，则返回 `MateObservationChanged`，不自动激活或恢复用户文档。包含该项后本地针对性 33 项通过。

## 第二次原生结果（不是验收通过）
- Run 42268147736 / b456bbc 已 completed/failure，原 ZIP `evidence/run-42268147736/swcli-assembly-mates-13529059551.zip`，GitHub digest `1d1f455b6ed9ec999039e6b9babcd4e57082972e535c96e824fad91c540a5673` 匹配，完整 native trace 原件保留。
- 目标映射读取已通过；aligned coincident 与 aligned concentric 补充均 native ok，错误码 0、未抑制，距离分别约 8.88e-16 mm / 0，parallel_error=0；同心最终 LockRotation=false。第一条创建后快照与下一次完整 CAS 完全一致。
- Strict SaveAs 成功生成 63,401 字节 ASM，SHA-256 `a3ff1b5f76bf1ad9bbac96c55c3da8ce9db9393a7b399a7ae5e2bf6620cdf0a0`。但在独立 reopen 前 GetDocumentCount 不为 0，因此无保存重开验收，后三组未执行，公开许可保持空。
- 原 report 同时证实 PRT/ASM GetTitle 均为 `coincident-aligned`；已准备的 8a7095c 文件名消歧待纳入下一新 head。将补完整关闭目录而不重试失败的关闭，不删除未知文档，不放宽空目录断言。
- 下一阶段接口补充：新 assembly.add-mate 成功结果增加目标 ASM 根特征 diagnostics_before / diagnostics，以同时核对 MateGroup 等根求解错误；只增强已有求解保护，仍为相同客户端→daemon→worker 链路。相关 schema / SDK / MCP 契约同步后才提交。
- 根诊断与关闭目录的新契约/回归已通过；公开 fixture cleanup 对同一文档生命周期只允许一次 CloseDoc，失败不重放。退出失败组时父 supervisor 只按已验证 OS handle 结束仍存活的 owned host，单次终止/未知状态不终止，保持原 child report/错误/exit code，不触碰名称匹配的其它进程。
- 本路目前无待授权动作，技术门槛仍是未取得保存关闭重开及独立公开链路的完整证据。

## 新 head 的关闭/重开修复验证
- 最新完整便携回归 1858 项通过，26 平台跳过；本功能针对性 39 项通过。SDK generator / strict mypy / 8 负向消费场景与 actionlint 均通过；日志 `evidence/portable/reopen-fix-*`。
- 专属 native/public gate 在启动 owned host 前逐文件核对已安装 wheel Python 字节与 Git 精确 commit，拒绝同版本旧安装/可编辑源目录/未知 head；只在独立 mate job 强制重装本次 wheel，默认 full/release 安装和并发未改。
- 新 head 将只触发一次 internal 校准，公开 flag/精确 revision 集合继续为空；仍未完成保存关闭重开或公开链路验收。

## 第三次内部校准（修复后的新 head）
- 已 push 精确 head `ac9e54f9e533c60ae6af49476ca71aa94b9b0fe2`，唯一 internal dispatch [run 42279916240](https://github.com/YJBeetle/SWCLI/actions/runs/42279916240)，输入 mate=true/stage=internal/native_full=false。GitHub run head 已核验。
- 包含此前本地 8a7095c 的标题消歧与虚拟组件/后台身份拒绝；未对前两次失败 head 原样重跑，也不取消其它 run。等待本次原工件审查；公开写入继续关闭。
- 本次分发工件 `swcli-dist-13534737674.zip` 的 GitHub digest `85e40486ff4bef4676c8a845996ca41c8f3840d1024a41536803f278c34fd449` 已匹配，全部 83 个 Python 文件与 ac9e54f Git blob 完全一致；wheel SHA `e340542088cf848a98448c61514dfc219a33dbf065f86eeeb03de0234bba2bad`。
- 云端 Windows Python 3.9 / 3.14 与 package 均成功，专属原生 job 128108237759 进入 runner 准备。默认 full/release skipped。
- 等待时发现公开 gate 使用 `capabilities --operation` 与共享 ModelingSmoke 的无 ok 响应处理不兼容；本地准备改为 `capabilities --full` 并逐项比对两个新接口的 request/result schema。新增真实响应形态与契约偏移拒绝回归，当前本功能 41 项通过；该脚本修改不改变运行中的内部校准 head/adapter/断言。

## 收口快照：停止持续跟进，交统筹后续分次快照
- 按最新用户指令，仅完成当前实现/修复，不扩新功能、新计划或审查子代理；本轮停止持续 sleep/轮询，不建单 CI automation，不取消其它 run，也不为 main 已合入的 detailing/revolve 进行 rebase 或重跑。
- 最后一次快照：run 42279916240、精确 head `ac9e54f9e533c60ae6af49476ca71aa94b9b0fe2`，Windows 3.9/3.14 与 package 全成功；native job 128108237759 正常 `in_progress`，当前 `Install native SOLIDWORKS`。链接 https://github.com/YJBeetle/SWCLI/actions/runs/42279916240 。本轮不再取快照。
- 当前本地公开 gate 能力查询接线修复后的完整回归 1860 项通过、26 平台跳过；针对性 41 项通过，日志 `evidence/portable/public-capabilities-{tests,all-tests}.log`。该小修复与交接记录一并提交，未触发额外 native/public run；运行中 CI 仍是 ac9e54f，不冒称覆盖更新后的公开脚本。
- 分发 ZIP/digest/83 个源码文件一致性已核，见前节；本次 native 原件尚未可用。前两次失败原 ZIP、digest、trace、首次错误及部分修改均保留。
- 尚不可合/未验收缺口：本次内部四组＋组合的独立保存关闭重开证据待原件；公开 CLI→daemon→worker gate 尚未执行。公开写 flag 仍 false，revision 白名单为空，未提交发版/版本/指针改动。已有部分创建/求解/SaveAs 成功只作为诊断证据。
- 完成/失败原件可用后由统筹继续按实际结果收口；不以本次正常安装状态或便携成功替代端到端验收。

## 内部原件首层自验完成，准备必要公开 gate
- 统筹通知 run 42279916240 已成功；已取完成快照，Windows 3.9/3.14/package/专属 native job 全 success，public stage 与默认 full/release 均 skipped。
- 原 ZIP：`evidence/run-42279916240/swcli-assembly-mates-13535673155.zip`；GitHub digest `5d5a85844241e6db86d2074e832659340c3c30a7564b65aa0089db581d4095c7` 匹配，原解压目录 `evidence/run-42279916240/native-original/`。完整元数据已保存为 `completed-metadata.json`。
- 精确校准 head ac9e54f，宿主 PID 5824 / revision 33.5.0；已安装的 83 个 Python 文件 hash 逐一匹配该 Git commit。四组两类×两种对齐＋aligned 重合后补 aligned 同心，共 5 次 CreateMate；23920 begin / 23920 end，无 error，无 watchdog/失败清理，原生组最大约 9.594 秒，总外层约 35.258 秒，cleanup_errors=[]。
- 八份实际 PRT/ASM 的大小与 SHA 全匹配 report；四组关闭前后目录均为空，独立只读 reopen API errors/warnings 均 0，完整持久内容与保存前逐字段完全相等，18 个根特征诊断完整健康、NeedsRebuild2=0；重算几何残差满足阈值。同心最终 LockRotation=false。首层收据 `docs/verification/assembly-mates-internal-success-2026-11-07.json`。
- 本候选仅晋级原生 Windows 33.5.0 和既定受限标准配合范围，为执行原计划必要公开 CLI→daemon→worker gate；其它 native revision / Wine / 未知运行时仍拒绝。公开链路尚未通过，不是 merge-ready，不发版、不后置本系列既定未完成点。
- 内部脚本在 flag 已晋级时于获取宿主前拒绝运行，防止原来的“公开应拒绝”探针在晋级后额外写入；不改变已成功 ac9e54f 原件及断言。后续使用 public stage 一次必要 dispatch，不持续轮询，正常运行保存链接后结束等待，最终 review 由统筹本人负责。
- 晋级候选提交前全量 1861 项通过（26 平台跳过），针对性 42 项通过；SDK generator / strict mypy / 8 负向消费类型场景通过。日志 `evidence/portable/promotion-{tests,all-tests,sdk}.log`。
- 原始外层生命周期追踪另核实 acquire-owned-host / ExitApp / WaitForOwnedProcess 各仅一次且正常结束，未组内重启。

## 必要公开 gate 已触发，本轮停止持续跟进
- 已 push 代码候选 `035a6e30fcdc20e8ed1fa0ff8922c8365aa730cf`，远端分支 SHA 已核对一致。唯一公开 dispatch [run 42301013926](https://github.com/YJBeetle/SWCLI/actions/runs/42301013926)，输入 `assembly_mates_calibration=true`, `assembly_mates_stage=public`, `native_full=false`；初始 GET 精确 head 一致、正常 in_progress（Windows 3.9/3.14 与 package 已获得 runner）。receipt `evidence/public-dispatch-035a6e3.json`。
- 不重复 dispatch，不取消任何 CI，不持续 sleep/轮询；正常运行后按用户指令结束本轮，由统筹完成/失败原件可用后分次快照跟进。未创建单 CI automation，未派审查代理，未 rebase main 或更改版本/发布/指针。
- 当前只是内部 native 四组＋组合及保存关闭只读重开验收完成。公开 gate 仍待真实 CLI→daemon→worker、后台文档/lease/CAS拒绝、SaveAs+Save3、可写及只读重开、源与 ASM 内容/哈希、宿主连续性和清理原件。必须继续做完本系列已计划的公开验证后才由统筹判可合并，系列能力一起完成后再发版。
- 本节为本地交接状态更新（尚未另行提交），代码候选和正在运行的 CI head 均保持 035a6e3；原始工件在本工作树 evidence/ 持续保留，不提交压缩包。

## 首次公开 gate 失败与修复
- [run 42301013926](https://github.com/YJBeetle/SWCLI/actions/runs/42301013926) 的精确 head 为 `035a6e30fcdc20e8ed1fa0ff8922c8365aa730cf`。Windows 3.9、3.14 和 package 均通过，公开 job 128180138026 在首个 `preflight-status` 失败。原始 CLI 返回 `TimeoutError` 和 `transport_phase=connect`，共享 runner 归类为 `DaemonConnectTimeout`。未启动 daemon 或 SOLIDWORKS，未发出 CAD 请求，无部分修改。
- 原始公开 ZIP `evidence/run-42301013926/swcli-assembly-mates-42301013926-1-13544353858.zip` 的 GitHub digest 为 `8f6c98f3f1d2ee9fe79d003f7a083699b9bb1d5936792395f06930b9f3758af0`，原始分发 ZIP `swcli-dist-13544596144.zip` 的 GitHub digest 为 `1c8367164447ee8c5b943f6fcd8196ef13042d7602b431018fc0f564fa733009`，均已匹配。wheel、已安装的 83 个 Python 文件 hash 与精确 Git blob 逐一一致。原件和元数据保存在该 evidence 目录，首因收据见 `docs/verification/assembly-mates-public-preflight-failure-2026-11-07.json`。
- 仅公开配合 runner 使用本地独占 bind 确认可用的专用端口。被占用则直接失败，无未知 daemon RPC。共享 runner 原有状态探测和拒绝语义由既有测试覆盖。原生断言、组预算和 CI 并发设置均保持。真实回环测试覆盖端口占用拒绝和端口释放后成功。配合测试 43 项和共享 runner 测试 28 项通过。
- 内部四组和组合场景原生保存关闭重开已完成。公开验收仍待新 head 的独立 CLI→daemon→worker 原件。
- 修复后的全量便携回归执行 1862 项，26 项平台跳过，其余通过。日志 `evidence/portable/public-bind-all-tests.log`。

## 修复后的公开 gate 已启动
- 新 tip `ebc382f76b7210372347e8e6cc5edd66db96366e` 已推送并核对。唯一新 dispatch [run 42305617301](https://github.com/YJBeetle/SWCLI/actions/runs/42305617301)，输入 `assembly_mates_calibration=true`、`assembly_mates_stage=public`、`native_full=false`。首次 GET 确认精确 head，状态 `in_progress`，快照 `evidence/public-run-42305617301.json`。
- 本地交接状态已更新。本轮按统筹要求结束等待，公开原件待审查，合并待公开验收。

## 第二次公开 gate 的首个业务失败与实体映射候选
- [run 42305617301](https://github.com/YJBeetle/SWCLI/actions/runs/42305617301) / `ebc382f76b7210372347e8e6cc5edd66db96366e` 的端口 bind 预检成功，宿主 PID 5916、revision 33.5.0 已正常启动。第一组后台装配 `assembly.mate-targets` 返回 `mapped face does not belong to the exact component`，属于 `MateObservationUnavailable`。日志中 CreateMate 为 0 次，首次失败后正常清理，server_exit_code=0，宿主退出后的进程目录为空。
- 原 ZIP `evidence/run-42305617301/swcli-assembly-mates-42305617301-1-13547066936.zip` 的 GitHub digest `cafe07ef6f88b32f6d133e5f9b21050c13a5681d35ee9e9910ac2e1776a4cb8a` 已匹配。分发原 ZIP `swcli-dist-13546661206.zip` digest `bf2b84e6edad9cfc56a1ce6dfe8115f5c8912a6c8744da1a4866af3f77583fed` 也已匹配，wheel/安装报告中全部 83 个 Python 文件与 Git blob 一致。原件元数据、journal、daemon trace、源 PRT 均保留。
- 实际只有源 PRT 产物，56447 字节，SHA `4040864a7032375cdfac6c9edc420dc3bf5228de9ee36c7df38da8d52694c217`。失败摘要 `docs/verification/assembly-mates-public-mapping-failure-2026-11-07.json`。原追踪未记录 COM 返回值，目前确认到后台映射面的组件归属失败，具体原生根因尚未确立。
- 依据官方 IEntity 面/边/顶点专用 API，候选改为先 QI 源面到 IEntity，再单次 `IComponent2.GetCorrespondingEntity`。精确 owner IsSame、几何、持久引用往返和 CAS 断言继续执行。没有 owner 时给出明确错误，错误实例仍拒绝。后台回归覆盖专用实体映射、前台身份保持及错误/空 owner 拒绝。新路径的原生后台支持继续由公开 gate 验证。
- 针对性 44 项通过，全量执行 1863 项，26 平台跳过，其余通过。日志 `evidence/portable/entity-mapping-{tests,all-tests,sdk}.log`。内部历史保存重开证据继续指向 ac9e54f / run 42279916240，更新后的实体映射候选待公开验收。

## 实体映射修复后的公开 gate 已启动
- 新 tip `cc801f78f33551a27e430277c9be3ef350c42c90` 已推送并核对远端。唯一新 dispatch [run 42361567672](https://github.com/YJBeetle/SWCLI/actions/runs/42361567672)，输入 `assembly_mates_calibration=true`、`assembly_mates_stage=public`、`native_full=false`，首次快照确认精确 head，状态 `in_progress`。receipt `evidence/public-run-42361567672.json`。
- 本节为本地交接状态。本轮按统筹要求结束等待，公开原件待审查，合并待公开验收。

## 第三次公开失败与装配文档实体上下文候选
- [run 42361567672](https://github.com/YJBeetle/SWCLI/actions/runs/42361567672) / `cc801f78f33551a27e430277c9be3ef350c42c90` 的首个业务失败仍为后台 `assembly.mate-targets`，新诊断明确 `IEntity.GetComponent` 返回 None。实体专用映射本身已正常返回，尚未取得组件 owner。原件没有 CreateMate 调用。宿主 PID 4952 / revision 33.5.0，owned server 正常退出 0，清理完成后的原生进程目录为空。
- 原 ZIP `evidence/run-42361567672/swcli-assembly-mates-42361567672-1-13569608878.zip` 的 GitHub digest 为 `2ab0cda2ab6ff92185e1181c1dcd321e75dd8c9dd96a7769df3fa123060a44ab`，原分发 ZIP `swcli-dist-13570062052.zip` digest 为 `cc8e99e06a70f52310c647d23846a95946a3e4bc0f55a2700ce76b763b159ff3`，均已匹配。已安装的 83 个 Python 文件与 wheel/Git blob 全部一致。原件摘要见 `docs/verification/assembly-mates-public-context-failure-2026-11-07.json`，实际源 PRT 为 56794 字节，SHA `504b33f46b7d6f9cb00b6e854a8eb07f29a9b278aec68e5327e114b3c7baaa70`。
- 官方 GetComponent 要求实体直接取自装配文档。候选使用既有私有引用能力，在目标 ASM 的 Extension 中捕获/解析映射面的引用，再核验解析对象与映射面 IsSame，最后执行原有组件 owner、几何、重复引用与完整 CAS 检查。仍从显式目标文档只读获取数据，并继续核对前台身份。新上下文路径尚待原生公开 gate 证明。
- 回归覆盖中间映射对象缺少上下文而装配解析对象身份相同的成功形态，以及解析到其他原生面时写前拒绝。46 项针对性通过，全量执行 1865 项，26 平台跳过，其余通过。SDK generator / strict mypy / 8 个负向消费类型场景通过。日志 `evidence/portable/assembly-context-{tests,all-tests,sdk}.log`。

## 装配文档上下文候选的公开 gate 已启动
- 新 tip `0dd4c36d496e6ce700b19a353d45544d1465ac20` 已 push 并核对远端。唯一新 dispatch [run 42365387925](https://github.com/YJBeetle/SWCLI/actions/runs/42365387925)，输入 `assembly_mates_calibration=true`、`assembly_mates_stage=public`、`native_full=false`。首次快照已核对精确 head，状态 `in_progress`。receipt `evidence/public-run-42365387925.json`。
- 本节为本地交接状态。本轮结束等待，更新后的实体上下文路径及公开全流程待原件审查。

## 第四次公开失败与组件体面候选
- [run 42365387925](https://github.com/YJBeetle/SWCLI/actions/runs/42365387925) / `0dd4c36d496e6ce700b19a353d45544d1465ac20` 的首个业务失败仍为后台 `assembly.mate-targets` 的空组件 owner。原追踪显示映射、私有引用解析与身份核对均完成，之后 GetComponent 返回 None。该候选未解决后台上下文问题。CreateMate 为 0 次，宿主 PID 3328 / revision 33.5.0，server 正常退出 0，清理错误为空，退出后原生进程目录为空。
- 原 ZIP `evidence/run-42365387925/swcli-assembly-mates-42365387925-1-13572331235.zip` 的 GitHub digest 为 `f8de0a291a0ace9b76dc3877f6a639ef75b1dc149799399967cd71fece9a030c`，分发原 ZIP `swcli-dist-13571183928.zip` 的 digest 为 `870fbc2fe144e878d83ae2a9c803a4c497a5ab2731eacf745e57d5d756f2f6e4`，均已匹配。wheel、安装报告中 83 个 Python 文件与精确 Git blob 全部一致。原件、daemon 日志、完整 journal 和官方元数据均已保留。
- 原件摘要为 `docs/verification/assembly-mates-public-resolved-context-failure-2026-11-08.json`。实际源 PRT 为 56630 字节，SHA `e9ead3e759d1e09d3c49117b7eca1f191c2eef8ac3aff57dbbcac43f4e7f443e`。没有实际保存的配合 ASM，也没有配合部分修改。
- 新候选直接调用组件实例的 GetBodies3 枚举一个 normal solid body，并检查 body info、完整 face count、每张面的 GetBody 身份。源面对应结果必须通过 IsSame 唯一匹配组件体中的原生面，再对该面执行原有 GetComponent 精确组件身份、几何、私有引用往返和完整 CAS 检查。body info 缺失/未知/user body、体或面遍历不完整、外来原生面全部拒绝。该路径的真实后台支持仍待公开 gate。
- 47 项针对性回归已通过，覆盖体元数据、外来面、唯一对应与后台前台身份保持。完整便携回归和 SDK 检查日志存入 `evidence/portable/component-body-*.log`。
- 完整回归执行 1866 项，26 平台跳过，其余通过。SDK generator / strict mypy / 8 个负向消费类型场景通过。当前代码候选待必要新公开 gate 的原件审查。

## 组件体面候选的公开 gate 已启动
- 精确 tip `202aa7cbfd27749116f1680e89947c6dabe4172a` 已 push 并核对远端。唯一新 dispatch [run 42404819519](https://github.com/YJBeetle/SWCLI/actions/runs/42404819519)，输入 `assembly_mates_calibration=true`、`assembly_mates_stage=public`、`native_full=false`。首次快照已核对精确 head，状态 `in_progress`，记录 `evidence/public-run-42404819519.json`。
- 本节为本地交接状态。本轮按统筹要求结束等待，组件体路径及公开全流程仍待原件审查。

## 第五次公开失败核验，缺少新修复依据
- [run 42404819519](https://github.com/YJBeetle/SWCLI/actions/runs/42404819519) 的精确代码 head 为 `202aa7cbfd27749116f1680e89947c6dabe4172a`。Windows 3.9/3.14 与打包均成功，公开 job 128501170660 失败。首错仍是后台 mate-targets 的 GetComponent 返回 None。
- 原始公开 ZIP `evidence/run-42404819519/swcli-assembly-mates-42404819519-1-13587473685.zip`，GitHub digest `29818ef61d2b861f39e60da649b8b87a1a83a6b27513c15591d5111b50509096`。分发 ZIP `swcli-dist-13586732711.zip`，GitHub digest `5d64d144f81f4950e5006a278eabb238682948d28b02412fc2ea36124ca8e79f`。两份摘要均匹配，wheel/安装报告的 83 个 Python 文件与精确 Git blob 一致。官方元数据、完整日志及原件保存在该目录。
- 本轮 CreateMate 实际 begin=0/end=0/error=0，完整 CLI journal 中没有 add-mate 请求。GetBodies3 和 GetCorrespondingEntity 各完成一次，组件体元数据、完整面/体归属和唯一映射面身份检查均已完成，随后 owner 为空。宿主 PID 6744 / revision 33.5.0，server 正常退出 0，cleanup_errors=[]，退出后原生进程目录为空。fixture 原始 PRT 保留，尚未创建配合或保存配合 ASM。
- 机器收据为 `docs/verification/assembly-mates-public-component-body-failure-2026-11-08.json`。组件体面候选未解决该首因。已查阅的官方 GetComponent 文档限定其实体获取上下文，现有资料未给出满足当前“不激活目标、精确取得并校验 owner”要求的新修复依据。
- 按“无信息不重跑”，本轮只提交原件核验和技术缺口记录。代码候选仍为 202aa7c，保留全部身份/组件归属/几何断言。没有新的运行时修改或 dispatch，未用 VM。现有内部历史成功仅指 ac9e54f / run 42279916240，公开验收继续未通过，不能合并或发版。
- 已收到 main 960839e 和便携 42412228332 成功的统筹信息，本工作树未变更 main 或发布/worker 保护。后续需统筹确定保持当前约束的有效组件上下文取得方案后再推进。
