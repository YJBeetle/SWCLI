# 固定原件导入诊断 42813151084：原件审计与取证修正

[运行 42813151084](https://github.com/YJBeetle/SWCLI/actions/runs/42813151084)，精确 head `2c4e491603e2af81ba33ab0b0a7e98a94ce800c3`，workflow_dispatch / attempt 1，结果 failure。此次已通过取件前置并安装真实原生环境。第一项 AP203 实体完成导入、原生保存和只读重开；第二项 AP203 线框的 LoadFile4 返回 **None / errors=1**，立即停止。线框几何不可测，不是零条几何。原生失败原因仍未证明，当前实现不能据此合并或发布。

## 原件、运行身份与文件

| 原始 ZIP | artifact ID | 已核对的 GitHub SHA256 |
| --- | --- | --- |
| 本次完整诊断 | 13764700892 | `02aa277ef919cf1056a8292a6729a5c4571a79eb510554e8ee9d728acb324281` |
| 本次 hosted / 官方 summary | 13764691009 | `d25c6456f8ee8c25ab0b3f4ed16668b1ab3ecde776dae6ae4db0bbbe2907c6aa` |
| 诊断内保留的固定旧原 ZIP | 13591430613（源运行 42413805736） | `de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7` |

当前运行、源运行、两份外层 ZIP 的源 head、artifact 元数据及嵌套旧 ZIP 均已核验。嵌套 ZIP 与先前保存的官方原件逐字节相同，原报告字节相同；八个恢复文件在本次失败后的 hosted 产物中仍与各自固定 hash/原字节一致。两份独立上传的 reader 文件也逐字节相同。没有重新导出 STEP。

原始 ZIP、完整官方 job 日志、run/jobs/artifacts 元数据与独立审计在 `step-evidence/diagnostic-original-42813151084/`。可用 `.venv/bin/python step-evidence/audit-original-42813151084.py` 离线复核，不启动 CAD。选定完整事实见 [机器可读审计](evidence/step-import-diagnostic-42813151084.json)。

## 实际执行和首个业务错误

| 项目 | 观察 |
| --- | --- |
| 计划 / 开始 / 完整读回 | 8 / 2 / 1；剩余 6 项未尝试 |
| GetImportFileData / LoadFile4 | 各 2 次，每文件各一次；无重试 |
| 第一项 AP203 solid-surface | LoadFile4 返回模型、error=0；1 实体，体积约 12000 mm³，面积 3800 mm²，质心约 (0,0,5) mm；保存和只读重开通过原断言 |
| 第一项原生文件 | 46297 bytes；SHA256 `8d80278f75d9b8307adcdf3cec54dd489fff5735913fd336871522518ea13780`，保存收据与原件相符 |
| 第二项 AP203 wireframe | LoadFile4 正常返回但模型为 None，error=1；未测几何、未原生保存或重开 |
| 第一业务失败 | `STEP geometry readback failed`，源于返回值与错误码断言；接口诊断错误未覆盖它 |

八个 STEP 原始内容仍满足已有夹具证据：实体的 1 solid / 1 shell / 6 faces / 12 edges / 8 vertices；线框根可达曲线为 12 / 320 mm 或含草图的 18 / 560 mm。这个离线结果不证明原生导入成功，也不构成完整 EXPRESS 合规证明。

实际宿主 revision 为 33.5.0、hidden，单个 owned reader PID 7884。两项 General 设置均准确恢复到进入前向量；cleanup_errors 为空；唯一 ExitApp、WaitForOwnedProcess、CloseProcessHandle、CoUninitialize 均完成，私有输入清理 step success。清理没有覆盖首次业务失败。

## 本次真正补齐的上下文与残留未知

两项导入前实际读到相同八项值，均为 observed：

| 组 | 实际值 |
| --- | --- |
| General | SolidSurface=true，FreeCurves=true，CurvePreference=1 |
| Neutral | SolidandSurface=true，FreeCurvesAndPoints=false，CurvesAndPointsOption=0 |
| 其他 | 3DInterconnect=false，StepConfigData=false |

这证明两组选项不同，仍不证明 translator 读取哪组或优先顺序；不能据此猜测新的 profile。**全局 StepConfigData=false 不等于实际对象 MapConfigurationData=false。**

实际安装的 swconst.tlb SHA256 为 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`，sldworks.tlb 为 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`；后者现已与此前本机只读解析的库 hash 对上。IImportStepData/IImportIgesData IID 来自实际安装 TLB。

两个 GetImportFileData 都返回 CDispatch，GetTypeInfoCount=0。IGES IID 查询报 E_NOINTERFACE；STEP IID 查询报 Python TypeError：没有注册支持该 IID 的接口包装类型。原报告将这些查询记录为 unknown，MapConfigurationData 因 STEP 接口未正面确认而未读。第一项模型还出现 type-info Invalid index，但 GetType=1、测量、保存和重开都成功；该 type-info 错误不能当作无模型或几何损坏。

## 已证明的取证源码缺陷与最小修正（待统筹审阅，不派发）

官方安装日志明确 pywin32-312。[该版本 QueryInterface 实现](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyIUnknown.cpp#L96-L158) 先做一次真实 IID 查询，再创建 Python 包装；[包装注册表缺项](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyComHelpers.cpp#L241-L260) 正会产生本次 TypeError。因此单参数 QueryInterface 无法在缺少 Python 专用包装时可靠记录查询结果。该错误不等于 COM 服务器拒绝 STEP 接口；原报告仍保持 unknown，不把源码推断伪装成本次正面运行时证明。

修正仅为 `QueryInterface(installed_iid, pythoncom.IID_IUnknown)`。第二参数仅选择 Python 包装类型，不改变实际查询 IID；pywin32 源码只做一次原生查询。[所有 COM 接口都继承 IUnknown](https://learn.microsoft.com/en-us/windows/win32/api/unknwn/nn-unknwn-iunknown)，此处只核对象存在后释放引用，不调用自定义 vtable，也不将其假装成 IDispatch。仅确切 E_NOINTERFACE 记录 observed/false；其他错误继续 unknown。STEP 支持正面确认后才尝试原有只读 MapConfigurationData getter。

这只修复接口取证的已证实源码缺陷，**没有证明可修复 LoadFile4 error=1**。没有改 GetImportFileData/LoadFile4 参数、General/Neutral 选项、MapConfigurationData、几何/八文件断言、首错停、owned host 或 600/1800 秒时限。真实取证修正效果仍需另行获准的原生诊断；本轮不新增 dispatch，也不使用本地 VM/CAD。

便携验证：59 项 STEP 回归通过；全量 1878 项，26 项跳过，其余通过。反例模拟了单参数 QI 抛出实际 unregistered-wrapper TypeError、双参数安全包装单次成功；E_NOINTERFACE 与其他未知错误分开，额外取证失败不能替换原 LoadFile4 异常。root 可按 [零导入/零保存单原件计划](step-import-qi-local-plan.md) 审查后自行执行；不为取证包装修正重复完整 CI。
