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
