# 本地单次 STEP 数据接口成功：离线审计与下一步边界

root 执行的第一次实际 API 诊断已成功。本轮只离线审计和研究，没有操作 VM、修改参数或新增 CI。成功仅限接口/属性取证，不能补改旧 CI 的 unknown，更不能称 LoadFile4 error1 已修复。

## 原件与精确执行范围

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/step-qi-once-4b0104b-01`。

- report SHA256 `ad362253f064f9fb620b0775379debd598eaa17a2db1712afd498dca92e90f8f`，已独立复验；六份原文件只复制到 ignored evidence，不改原件。
- 审阅提交 `4b0104bec301abfcf6163d25f0ff306a26a21e16`；传输源码 ZIP SHA256 `baacb00023feb4377945ef8b5dc75a1b14275b16fbcdcbc0274b63ae9d6808c0`。归档是 183 个 runtime 源码文件的子集，不是全仓库；每个成员均与该提交逐字节相同，report 四个实际加载代码 hash 也匹配。
- Python3.14.7 / pywin32 312；实际 swconst.tlb `95e36f79...`、sldworks.tlb `585e008c...` 与已钉住的完整 SHA 一致。VM 安装路径为 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS`，没有强行套 CI 目录路径。
- hidden owned host PID8604 / revision33.5.0；nohost-before为空；源输入为固定 Workspace 路径、10595 bytes、只读 attributes33。输入所有 metadata/hash 检查点完全相同，文件 SHA256 `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`。

逐通道 begin/end 配对、顺序、错误检查均通过：

| 实际动作 | 次数 / 结果 |
| --- | --- |
| owned acquisition | 1 |
| 八偏好读取 | 每项1次，全部 observed |
| GetImportFileData | 1，返回 CDispatch |
| 单 STEP IID safe IUnknown QI | 1，true；未查询其他 IID |
| MapConfigurationData getter | 1，false；未调用 setter |
| Load / Open / New / Save / Select / SetUserPreference | 各0 |
| 文档数 | 前后均0 |
| ExitApp / WaitForOwnedProcess / CloseProcessHandle / CoUninitialize | 各1，完成 |
| cleanup_errors / remaining_native_pids | 均为空 |

observation trace 的 ExitApp 是主 trace 里同一次调用的嵌套观察，不能误算成两次。stdout/stderr 仅保存原件，不把缺少导入记录换算成零几何。本次没有任何几何测量。

root 报告的两次长 EncodedCommand guest launcher 失败发生在源码目录/CAD 之前；它们不计为 GetImportFileData/QI 重试。成功 bundle 的实际 API trace 只有上述单次调用；本审计没有将 launcher 失败伪装为自行复验过的 API 失败。

可复跑 `step-evidence/audit-local-qi-4b0104b.py`。完整选定事实及官方帮助指纹见 [机器审计](evidence/step-local-qi-4b0104b.json)。

## 本地与旧 CI 是不同 profile

| 值 | 本地成功取证 | CI42813151084 失败导入前 |
| --- | --- | --- |
| 3D Interconnect | true | false |
| General SolidSurface | true | true |
| General FreeCurves | false | true |
| General CurvePreference | 0 | 1 |
| Neutral SolidandSurface | true | true |
| Neutral FreeCurvesAndPoints | false | false |
| Neutral CurvesAndPointsOption | 0 | 0 |
| global StepConfigData | false | false |
| 实际对象 MapConfigurationData | false（本次直接读取） | unknown（旧原件未读到） |

当前 CI reader 源码仍仅写 General 三 Toggle 加 General CurvePreference，并强制3DI=false；Neutral组是读而不写。本地脚本完全不写任何导入偏好，读到的是 VM 当时环境。局部取证成功证明安全 Python 包装和 getter 在**此环境**可用，不证明它们在旧 CI 环境已测得，更不证明两组控制的优先级。

## 官方语义复核：已知与未证明

网页部分 2025 API 页面只返回空壳；另只读提取了本机 MacSW2025 安装树的官方 CHM 指定页面，保存文件/member SHA。这些安装 TLB 与 VM hash 相同，但本轮未读取 VM CHM，不能声称其帮助文件字节也相同。

1. **General 适用条件。** 安装版 `swconst.chm::FileOpenOptionsGeneral.htm` 明确 General FreeCurves 仅在3DI=false时适用，并与 General CurvePreference 配套。其枚举0为草图、1为3D曲线。可对照 [官方 General API 表](https://help.solidworks.com/2019/English/api/swconst/FileOpenOptionsGeneral.htm)。当前 CI 对这组值的请求/读回符合表面条件，但读回成功不是 translator 消费这些值的证明。
2. **Neutral 的特定格式语义。** 安装版 `FileOpenOptionsSTEPIGESACIS.htm` 把 STEP/IGES/ACIS 的自由曲线/点作为草图开关映射到 Neutral_FreeCurvesAndPoints；[官方格式 API 表](https://help.solidworks.com/2019/English/api/swconst/FileOpenOptionsSTEPIGESACIS.htm) 同样如此。[2025 Neutral 枚举](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swImportNeutralCurvesAndPointsOptions_e.html) 定义草图0、3D曲线1。它不说明与 General 组冲突时的优先级。
3. **不能把3DI=false等同于旧 translator。** 安装用户帮助与 [官方2025 3D Interconnect说明](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_sw_3d_interconnect.htm?id=18.17) 都指出，列出的格式（含STEP）即使关闭该开关也使用新转换技术。因此旧说明里“关闭3DI即切旧导入器”的推断不成立。
4. **唯一明确的对象覆盖规则。** [2025 MapConfigurationData合同](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IImportStepData~MapConfigurationData.html) 规定：未设置时取 global StepConfigData；显式对象设置只覆盖这一项、这一轮导入。它不是曲线模式开关。原件global=false与本次对象false相容，不把此规则扩大为General/Neutral优先级。
5. **LoadFile4 文档存在需要保留的歧义。** 同安装 `sldworksapi.chm` 的方法参数表写3DI关闭时 ImportData 用 null/Nothing，且 enabled 时 ArgString为空；但同包 STEP C#/VBA 示例传 `"r"` 和 ImportStepData 对象，没有设定3DI状态。仅凭其中一段不能宣布现有调用错误或猜改为 null/空字符串；本轮没有改调用参数。官方 [LoadFile4](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~LoadFile4.html) / [STEP示例](https://help.solidworks.com/2025/English/api/sldworksapi/Import_STEP_File_Example_CSharp.htm) 是后续需澄清的具体合同点。

结论：已核实两组选项含义、General门控和对象配置覆盖范围；**没有查到两组曲线选项优先级的官方承诺**。不得从字段名、枚举值、3DI开关、成功QI或UI说明拼成已证实的优先规则。

## 交 root 审阅的最小下一步（未执行、未实现新入口）

不再为同一默认环境重复零导入 QI，也不重跑完整 CI。若 root 决定下一轮要直接区分“格式专属自由曲线开关是否影响这条导入路径”，建议只审阅一个**单布尔变量的诊断候选**：

- 固定同一只读原件、同一实际安装、单 hidden owned host；先显式核对既有 CI General profile（3DI=false、GeneralSolid=true、GeneralFree=true、GeneralCurve=1）和八项原值。只在完整CAS/原值恢复/首错停方案获 root 批准后使用。
- 相对旧 CI 已记录向量，唯一新候选是文档定义的 `Neutral_FreeCurvesAndPoints: false → true`；Neutral CurveOption仍0，其余不猜不扫。这是待证伪假设，**不是已证明的修复**。
- 原 `ArgString="r"` / ImportStepData对象不同时改变，MapConfigurationData只读。最多一次 GetImportFileData、单STEP QI/getter及一次 LoadFile4；前置未知/失败即停，禁止重试/回退/重建。现有零导入脚本的 allowlist 保持不动，若批准须另行审查独立入口。
- 若无模型/error1：原样保存、几何 unavailable，停止，不继续换选项。若有模型：在原严格12段/320mm/长度向量及表示类型断言前保存完整特征类型和部分长度；草图与参考曲线分开记录，错类型仍失败。不保存、不新建、不选择、不导出；仅关闭自有导入文档、恢复原值并确认唯一owned退出。

这能产生一条新的组合/表示行为证据；由于本地与 hosted Windows仍有环境差异，单次成功或失败**都不能严格归因为该布尔量，更不能宣布全局优先级**。要证明因果优先级，需要 root 另行批准同环境受控对照或厂商合同澄清，不能为补基线自动重放已知失败。root若认为该信息增益不足，下一步应先澄清上面的 LoadFile4 参数矛盾，暂不做任何导入试验。

以上只是审阅提案；本轮没有新源码修复依据，未改生产/reader/选项，也未运行 VM 或 CI。
