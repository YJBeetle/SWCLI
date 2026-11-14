> 新增私有最小外层及最新来源见 [adapter说明](assembly-mates-active-census-adapter-2026-11-15.md)。下面无parent/supervisor的描述属于reader边界；当前外层亦未执行或授权。

# 当前主线上的活动 ASM 配合能力收敛

起点精确origin/main `31ad9c256a5a106bc94a627cd41dfd6277bb6f00`。新worktree `/Users/YJBeetle/.codex/worktrees/swcli-assembly-mates-active/SWCLI`、branch `codex/swcli-assembly-mates-active`；旧诊断分支及evidence保留，33归档提交c63c213。旧分支并非主线后续可整体合并的产品补丁：当前main没有配合API，存在大量更新的daemon/schema/SDK/文档偏好与导出实现。本候选只新增私有只读host模块、root-owned观察入口、最小私有外层和三份测试，既有main产品源码与测试零修改（只追加本路交接记录）；未带回旧校准写开关/配合写实现/CLI/schema/SDK或废弃映射路径。逐项来源收据 `assembly-mates-active-census-mainline-port-2026-11-15.json`。

33有限成功与31后台NULL失败见同目录33 JSON/MD。安装版2025 GetComponent契约限制实体装配来源，实际TLB描述是“In active assembly, get Component which owns this entity”。33仅第一组件第一圆柱面、713字节同引用、native owner非空+精确组件身份与后置通过；不证明其它面、公共入口或CAS。本候选不得把它外推为后台通用owner来源。

## 阶段A：先证明完整目标census（本轮代码）

`windows_assembly_target_observation.observe_readonly_active_targets(app, document, components)` 是私有函数，要求调用者已拥有同一worker STA。入口先比对ActiveDoc与target native identity，后台抛明确code `AssemblyNotActive`，此时尚未遍历实体/读owner/初始化接口或写CAD。活动条件不是由代码修复，绝不ActivateDoc。此阶段严格限定clean readonly、non-view-only、saved ASM和两份计划组件的保存外部PRT；exactly两组件、第一固定第二浮动、单配置、resolved/nonvirtual、每组件一solid/no surface、每体1..64个plane/cylinder面。

先完整枚举source与component body faces并核count/体membership。对两组件每个source face按预定顺序：只一次GetCorresponding，保留原对象；mapped native face在对应组件体中必须唯一且未重复，官方IFace2/QI与查询指针/native身份、体和几何必须通过；target ASM extension捕获一次引用并typed解析一次，status严格int0、对象非空、mapped/resolved native identity与resolved体/几何匹配；resolved官方IEntity上只一次GetComponent，owner非空且native IsSame精确计划IComponent2。原mapped/source/body枚举wrapper getter零次。全census引用摘要去歧义，body/reference/IsSame绝不代替owner。

每面在mapping前和getter前再次核活动身份，trace stage `assembly-targets.component[i].face[j]`，各map/capture/resolve/getter/owner-IsSame分别唯一begin/end；不存在owner失败后试下一面或第二receiver。全部面通过才作source/config/stamp/path/pose/fixed/suppression/edit/ASM/foreground后置检查，才整体返回plain value与私有原生binding tuple；失败以原异常退出，不返回部分绑定。只读census不是现有mate树/solver状态的完整snapshot，不发公共token、不执行CAS或写。

新绑定类保留component/source face/original mapped/resolved/body/reference私有对象，严格不是可跨请求公开entity_id。不会把part face registry和assembly face绑定混用。新官方绑定只采用同拥有宿主安装目录的sldworks.tlb，查询官方dual接口、保留确切QI指针并核native identity；typed resolver必须与33的真实2025 FUNCDESC完全一致，不退回旧公共refs helper或Invoke路径。

## 阶段B：公共只读入口与typed句柄/CAS契约（仅设计，尚未注册）

公共operation名称、schema、CLI/SDK接线仍需root亲审，不恢复旧整套API。能力应明确声明foreground `target_assembly_already_active`、范围/上限与本机版本门禁，后台返回AssemblyNotActive；客户端/daemon/worker统一暴露该边界，不能由daemon静默切前台。不得在未完成下述公共验收前填calibrated-write或backend-supported成功。

新assembly-target token必须具有独立kind/registry，绑定session/worker代次、document_id与确切ASM native对象、ASM配置/stamp、确切component实例/名称、source保存路径/config/stamp、transform/fixed/suppression、确切face native对象和私有reference。它不是part face token、数组index或引用hash的别名；错误kind/会话/文档/旧代次/配置/stamp首先拒绝。只有完整census和最后活动/状态检查通过后批量发token，中途失败零发放，旧token不能被同index或几何近似静默替换。

CAS入口先做协议/lease/类型/注册scope核对；worker在任何owner读取/写setup前再次require_active_assembly。再执行一次明确计划的完整新观察并对旧绑定做唯一native映射和每面真实owner证明，比较全部值：ASM路径/配置/stamp/dirty/edit、组件native实例/来源/config/stamp/pose/fixed/suppression、完整面的几何与引用scope，以及未来写所需的现有mate树定义/状态。不能只比较两张选中面或持久hash。活动身份须在读取入口、CAS重读入口和紧贴首次CAD写前分别验证，任一漂移明确拒绝，无自动激活/新token/重试。

阶段A当前故意要求readonly clean。公共可写ASM/预期dirty的观察政策、mate树读取及CAS重读是下一独立候选，不能仅删除readonly/clean守卫就算写域可用；必须明示版本/范围、逐项保留归属与源保护并补对应原生证明。现有part EntityRegistry/拓扑reference APIs不修改、不借其kind替代assembly owner来源。

## 阶段C：同类型配合写与保存重开（未实现、未授权）

只考虑既定平面coincident和圆柱concentric，不扩类型。单个明确写请求必须通过typed旧句柄与完整CAS、write UI/edit/selection/writable守卫，然后一次CreateMate与明确原生错误/partial mutation记录；错误不回滚、不重试。成功仍要完整重新观察新mate与原mate定义、solve/几何、fixed锚点/组件来源、root diagnostics及重建状态。每次观察pass在执行前明确计划，每pass每面唯一getter；不能在失败后启动另一pass试探。

最终公共门禁必须经真实CLI/SDK/MCP→daemon→owning worker路径验证活动约束与旧句柄拒绝，并对每个既定类型取得写后native定义/solver、save/close/reopen持久性证据。源码/离线测试/只读全目标/公共读取/写CAS/save-reopen分别报告，33或阶段A成功不能替代后续门禁。本轮没有任何公共operation/capability/schema/SDK/写入变更，也没有main合并或发布。

## 当前离线验证与下一执行输入

110项相关测试通过（census/reader30项、adapter22项，当前main既有引用/face observation/native_sequence/trace58项），日志 `/private/tmp/swcli-active-target-adapter-related-20261115.log`。覆盖所有面各自owner、在每个位置NULL立即停止、正确body/ref却错误component拒绝、后台在实体遍历前拒绝、typed返回形态/未知status不强转、原异常不重试、完整census不丢面、官方指针/库/描述符、引用跨实例歧义、配置/pose/edit/boolean后置漂移，以及root观察入口无部分结果/文件次错不覆盖首错。无公共schema/SDK变化，不重跑生成器或无关全套。

完整Git src/scripts/tests `515`项清单 `assembly-mates-active-census-inputs-2026-11-15.json` SHA `a67792386c45ca0c9eb5dc11fe2e9850f16c45c2cee04963878379a17e5ea219`；manifest只是离线来源，不是grant。下一readonly门禁具体安排见 [完整census执行提议](assembly-mates-active-census-proposal-2026-11-15.md)，当前尚未原生执行。

新配置读取只用当前main同款 `ConfigurationManager.ActiveConfiguration.Name`，完整names/count=1校验保持；manager/active缺失、名称无效/不匹配、属性原错均拒绝，不回退GetActiveConfiguration。fake旧API调用即失败，完整读取及成功后置亦覆盖。main已有其它旧调用未改。
