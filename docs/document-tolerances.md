# 文档级线性尺寸公差默认值（实验性）

本分支新增 `document.tolerances` / `document.tolerance-set`、对应 CLI 和生成的 Python SDK。
作用域固定为文档属性 Dimensions > Linear 的默认公差，不是单个模型尺寸；不访问
IDimension、IDimensionTolerance、特征尺寸或应用级偏好。不改模型数值。

读取返回 `linear.type` 与 `linear.precision` 的语义值和原生整数，未知值保留为
`other` 加原生整数。偏好编号与 Linear option 从安装的官方 `swconst.tlb` 按名称解析；
缺失即报错，不猜测编号。精度 -3 读为 `follow_nominal`；其他未支持特殊值保留为 `other`。

内部原生校准与独立artifact审计已通过（run 42266358630 / head 252ad8b）。
本分支仅为公开验收开放精确候选范围：原生 Windows 且 RevisionNumber=33.5.0；类型 none/basic；
精度字符串 0/3/8。旧值必须为类型 none/basic、精度 follow_nominal/0/3/8，包含 no-op。
同 revision 的 Wine、未知宿主探测、其他版本/字段/旧值/目标值继续拒写。`write_enabled` 表示该宿主版本的候选写入开关，
不替代只读、lease、CAS、编辑上下文等每次请求的校验。
**公开 CLI/daemon 验收尚待完成，当前不算 merge-ready。**
写入要求明确 document_id、有效 lease、expected_update_stamp 以及包含两个字段完整
语义值和原生整数的 expected_options；修改一个字段时也必须核对另一字段。
原生 setter 至多调用一次；False、异常、回读不匹配或状态变化即停止，部分 mutation
回执保留 attempted/may_have_changed，不重试、不回滚、不修补读回期间的状态漂移。

```sh
swcli document tolerances --document DOCUMENT_ID --json
```

暂不支持最大/最小偏差、配合、字体、双尺寸、角度/直径等类别、继承开关或单尺寸覆盖。
也不提供任意原生编号入口。只读/仅查看文档禁止写入；后台文档不自动激活；沿用
现有文档状态、前台、配置与工程图编辑上下文保护。

官方依据（本次查证）：

- [Document Properties > Dimensions > Dimension Tolerance](https://help.solidworks.com/2023/English/api/swconst/DP_DimensionTolerance.htm)：Extension Get/SetUserPreferenceInteger，swDetailingToleranceStyle + swDetailingLinearDimension。
- [Document Properties > Dimensions > Linear](https://help.solidworks.com/2023/english/api/swconst/DP_Dimensions-Linear.htm)：swDetailingLinearTolPrecision + swDetailingLinearDimension。
- [swTolType_e](https://help.solidworks.com/2024/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTolType_e.html)：类型映射。
- [swDimensionPrecisionSettings_e](https://help.solidworks.com/2015/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDimensionPrecisionSettings_e.html)：-3 跟随尺寸精度；-1/-2 不作为文档默认写入值。

校准仅可在 codex/docprops-tolerances 手动 dispatch CI，calibrate_tolerances=true，
native_full=false。原生调用/操作上限600秒，组上限1800秒；生成零件、装配体、工程图，
检查后台隔离、整值 CAS、noop、保存/只读重开、原始文件摘要和零件解析几何断言。
首失败停止，保留 report/trace/日志/文件；不运行全量 CAD gate，也不生成全量验收摘要。
原始证据下载后保存在本工作树 evidence 目录。此校准为内部校准，不是公开端到端验收。

公开验收使用 accept_tolerances=true、calibrate_tolerances=false、native_full=false，
仅本分支手动。复用初始隐藏daemon，不进入其他业务组；对三个文档类型分别保存并
只读重开 basic/precision0、basic/precision8、none/precision3 三个副本，保留原始源文件
和之前副本的摘要；核对跨会话lease读取、CAS/lease/stamp拒绝、干净文档noop及其零setter
trace，SDK typed与MCP bridge的读取/noop走同一daemon。MCP stdio本身由既有便携契约覆盖。

唯一获用户明确批准的几何例外：质心绝对误差≤1e-12 mm；体积、面积、实体数逐位相等，
保留原解析体积/面积，并检查解析质心(0,0,5) mm。任何状态断言未放宽。
内部ZIP SHA-256：89164b4642dc4c5d4167e1f97e30eab89945bf2583cdc804ce18708794b86285，
已匹配GitHub digest；完整审计和首轮失败历史见 WORK_HANDOFF.md。

统筹边界审查后的修复：原生宿主检查通过 ntdll 的 wine_get_version 导出区分 Wine；
独立无secret CI profile preflight提前拒绝混合模式及专属开关错误分支，所有CAD步骤只依据
已验证profile选择。写后最终文档描述失败、worker后续包装/恢复失败保留原mutation与首业务错误，
且每请求清空局部result，防止沿用上次回执。目标身份和后台前台状态漂移也会拒绝/报部分失败。
旧公开run42271130456仅证明ce147cb；上述产品边界修复须最终head重新公开验收。
