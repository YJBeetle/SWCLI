# 文档级线性尺寸公差默认值（实验性）

本分支新增 `document.tolerances` / `document.tolerance-set`、对应 CLI 和生成的 Python SDK。
作用域固定为文档属性 Dimensions > Linear 的默认公差，不是单个模型尺寸；不访问
IDimension、IDimensionTolerance、特征尺寸或应用级偏好。不改模型数值。

读取返回 `linear.type` 与 `linear.precision` 的语义值和原生整数，未知值保留为
`other` 加原生整数。偏好编号与 Linear option 从安装的官方 `swconst.tlb` 按名称解析；
缺失即报错，不猜测编号。精度 -3 读为 `follow_nominal`；其他未支持特殊值保留为 `other`。

公开写入当前 fail closed（`write_enabled: false`），包括 no-op。候选写入仅在内部校准
进程启用：类型 none/basic，精度字符串 0–8。内部成功也不自动开启公开写入。
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
