# 基础装配标准配合（开发分支，待公开验收）

本分支提供 `assembly.mate-targets` 的受限当前态观察，以及
`assembly.add-mate` 的完整写入链路。内部原生 Windows 校准
[run 42279916240](https://github.com/YJBeetle/SWCLI/actions/runs/42279916240)
已核对原 ZIP、digest、精确提交、四组配合＋组合场景及实际保存关闭重开内容，
收据见 `docs/verification/assembly-mates-internal-success-2026-11-07.json`。

为执行独立公开验收，当前候选仅允许原生 Windows revision `33.5.0` 的下述受限范围；
其它 revision、Wine 或未知运行时继续拒绝写入。真实 CLI→daemon→worker gate
尚未完成，内部校准不代表公开验收、可合并或可发版；便携测试不是原生 CAD 证据。

## 首批边界

仅支持平面重合 `coincident`、圆柱同心 `concentric`，对齐为 `aligned` 或
`anti-aligned`。目标 ASM 恰好有两个顶层、已解析的外部零件；每个零件恰好一个
实体，所有面为平面或圆柱，最多 64 面。ASM 与每个 PRT 均只有一个配置，PRT
活动配置必须等于组件实际引用配置，源零件必须已保存且没有未保存修改。

第一组件是固定锚点，第二组件必须浮动。操作不自动浮动、固定、解析、取消抑制、
切换配置、打开源零件、结束用户编辑、重试求解或 CAD 回滚。不支持机械/高级配合、
子装配、虚拟零件、缩放/镜像组件或装配级修改后的面。已有配合也必须属于这两个
标准类型、引用这两个组件的已验证面，且求解健康。观察上限为 16；首批写入仅允许无配合时创建第一条，或在一条
已对齐的平面重合后，补一条已对齐且不锁定旋转的圆柱同心。其余组合在提交前拒绝。

## 瞬时目标与完整值 CAS

```powershell
swcli assembly mate-targets 'part-1' 'part-2' --document d-ab12cd --json
```

读操作不激活目标、不更改 session current、不清理用户选择。结果 `snapshot` 包含
文档身份/配置/更新戳/修改标记，两个组件的名称、路径、配置、原生 ID、固定/抑制状态、
源文档更新戳/修改标记、真实 16 元素变换矩阵、完整面数组，以及所有配合的实体与求解观察。
面 `parameters` 是零件坐标中的原生无界曲面参数：平面为单位法向量 xyz 后接米单位的点 xyz，
圆柱为米单位轴线上点 xyz、单位轴方向 xyz、米单位半径。组件变换的平移元素也为米，
`area_mm2` 为原生近似面积；实际配合残差才以毫米返回。

面数组 `index` 只用于本次完整观察，不是稳定引用。每个源面通过
`IComponent2.GetCorresponding` 映射到指定装配组件实例，用 `ISldWorks.IsSame`
证明归属。组件体通过 GetBodies3 完整枚举，必须是一个 normal solid body。
组件体面的数量必须与源零件一致，每个源面对应结果都必须唯一匹配组件体中一张原生面，
GetBody 与组件体一致。身份匹配只作验证，原始 mapped wrapper 持续用于 GetComponent、
私有引用捕获和 EntitiesToMate，避免用身份相同而上下文不同的体面 wrapper 替换。
GetComponent 必须返回指定组件，任何空 owner 或错误实例都拒绝。
私有原生持久引用必须即时往返成功并保持精确 COM 身份；响应只发布摘要以参加
完整 CAS，不发布可解析 token，也不承诺跨更新、关闭重开或拓扑变化稳定。
本分支不依赖尚未验收的独立稳定引用分支。

写入参数为 `kind`、`alignment`、两个 `{component, face_index}` 的 `targets`，以及
上次读出的完整 `expected_value`。公共请求上下文中的 `expected_update_stamp` 必填，
且必须与快照相同；已有 lease 需要正确 token。schema 与语义检查在提交前拒绝目标顺序不符、
重复组件、缺失字段、未知字段或非有限值。完整快照在瞬时定义 staging 前、原生提交前各比对一次。

CLI 对应 `assembly add-mate --kind ... --alignment ... --targets JSON --expected-value JSON`，
同时带 `--document`、`--if-update-stamp` 与适用的 `--lease`。Python SDK 为
`client.assembly.mate_targets(...)` / `client.assembly.add_mate(...)`；MCP 使用已有的
`capabilities` 和 `execute`，保留相同 session/document/lease/CAS 和结果，不新增直接 COM 工具。

## 单次创建与失败证据

daemon 临时激活精确目标，在既有 COM STA worker 执行。写前读取真实只读/只查看布尔值、
编辑目标、运行中命令、用户选择、配置与组件身份，未知状态拒绝。原生路径为
`CreateMateData`、设置两条精确装配上下文面与对齐（同心明确 `LockRotation=false`），然后
单次 `CreateMate` 和单次 `EditRebuild3`。返回特征不等于成功。

创建开始前即设置 `mutation.attempted=true` / `may_have_changed=true`；返回非空 Feature
后设置 `creation_returned=true`。原错误和部分修改始终保留；后续选择清理错误单独记录，
不替换首次原生错误。拒绝、原生空返回、异常、实体读回失败和求解失败都不会自动重试或回滚。

成功要求读回配合类型/对齐/两个精确实体、未抑制、零特征错误，组件身份/源几何与固定锚点
不变，已有配合定义不变，创建前后目标 ASM 根特征诊断完整且健康，同心最终定义中的 `LockRotation=false`，原生不再需要重建。独立计算变换到装配坐标的无界平面距离或圆柱
轴线距离（≤ 1e-5 mm）及平行误差（≤ 1e-8）。这不代表碰撞检查、完整约束或有限面重叠。

## 分层证据与手动校准

- 便携测试：所有权、完整 CAS、错误保留、部分修改、CLI/SDK/MCP 契约与 CI 接线。
- 内部 Windows 校准：四组两类配合×两种对齐，并验证 aligned 重合后补 aligned 同心的组合，
  在一个新建 owned host 中逐组创建自己的圆柱零件
  和装配，读取安装的官方 `swconst.tlb` / `sldworks.tlb` 成员及枚举，检查解析几何和配合实体，
  严格保存、关闭所有文档与引用后只读重开，比较组件关系、配合定义与实际输出内容，并核查源/输出 hash。
  首失败停止，不组内重启，外部 watchdog 限单次调用组 600 秒、整个组 1800 秒。
- 公开验收：必须另记真实 CLI→daemon→COM worker 的保存重开收据；内部脚本的私有 `_calibration`
  许可不属于公开参数，也不能作为公开功能验收。

专用 workflow_dispatch 输入 `assembly_mates_calibration` 默认关闭，`assembly_mates_stage`
默认 `internal`，公开链路另选 `public`。内部脚本要求公开写入仍关闭，晋级后拒绝在该脚本中执行原先的公开拒绝探针，避免额外创建配合；job 只允许
`codex/swcli-assembly-mates` 分支，以功能和 `github.ref` 隔离 concurrency。
PR 无法触发机密安装流程，默认 full/release 门禁保持原样。ZIP、report、trace、SLDPRT 与
SLDASM 文件随独立 artifact 保留；本地交接记录见 `WORK_HANDOFF.md`。

## 官方 API 依据

- [CreateMate 与创建顺序](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAssemblyDoc~CreateMate.html)
- [官方标准配合示例](https://help.solidworks.com/2024/English/api/sldworksapi/Create_Standard_Mates_Example_CSharp.htm)
- [GetCorresponding 的装配实例上下文](https://help.solidworks.com/2022/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~getcorresponding.html)
- [IEntity.GetComponent 的装配归属语义](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IEntity~GetComponent.html)
- [配合实体 Reference](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMateEntity2~Reference.html)
- [配合类型](https://help.solidworks.com/2026/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swMateType_e.html)
- [对齐枚举](https://help.solidworks.com/2026/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swMateAlign_e.html)
- [组件抑制状态枚举](https://help.solidworks.com/2026/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swComponentSuppressionState_e.html)

- [IComponent2.IsVirtual 只读属性](https://help.solidworks.com/2020/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~isvirtual.html)

- [组件实体枚举和装配修改体标识](https://help.solidworks.com/2018/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~GetBodies3.html)
