# 单原件 STEP 接口取证计划：零导入、零保存（仅统筹执行）

本计划只验证已证明的 pywin32 包装取证缺陷，不能验证或修复 `LoadFile4` error=1。不得为此重跑完整 CI。VM/SOLIDWORKS 的启动、独占协调、退出和恢复由 root 统一负责；此分支不操作 VM。

## 启动 CAD 前必须核对

1. 固定来源仍为 run `42413805736` / artifact `13591430613`，原 ZIP SHA256 `de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7`。只取其中 `swcli-native-smoke/step-public/ap203-wireframe.step`，预期 SHA256 `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`。
2. root 先核对本次 VM 允许写入的实际测试路径。候选为既有测试根下的 `C:\Users\YJBeetle\Desktop\TestModel\SWCLI-Step-QI-Only\ap203-wireframe.step`，这只是候选，不自动授予路径权限。若根目录/允许路径不符，先停，不能自动另选位置。目标仅新建或复用完全同 hash 字节；不覆盖不同已有文件，不改原 ZIP，拒绝路径链接/重解析点。记录最终绝对路径与 hash，随后再启动 host。
3. 记录诊断提交、Python 与 pywin32 版本。原 CI 安装的是 pywin32 312；本次只使用已核对该语义的版本。实际安装 `sldworks.tlb` SHA256 必须为 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`，swconst.tlb 为 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`。版本/库不符停止，不套用另一套 IID。
4. 从该官方 TLB 核对 IImportStepData 名称与唯一 IID `{AD749A73-9AA2-4A3E-BCA5-8FC012114BB0}`；只核这个目标，不查询 IGES 或其他候选 IID。已核的 [pywin32 312 QueryInterface 实现](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyIUnknown.cpp#L96-L158) 表明第二参数仅为 Python 包装选择；使用 `pythoncom.IID_IUnknown`，不假装成 IDispatch、不调用自定义 vtable。

## 唯一执行序列与记录

- 确认 VM 可独占且没有要保留的交互 SOLIDWORKS 进程；创建一个隐藏、诊断自有 host。不得附着、杀掉或重用其他 owner 的 host。记录 PID/revision、owned 状态、初始文档数量，必须为 0。
- 不写任何 preference。只读并记录原八项 General/Neutral/3DInterconnect/global StepConfigData 原值，各一次；这些读值不证明 translator 优先级。
- 对上述唯一文件调用 **一次 GetImportFileData**，记录 None/实际 Python 类型及一次 GetTypeInfoCount（0 就记 0，不将它当作不支持 STEP）。若返回 None/抛错，保留首错并停止，不查替代入口。
- 对返回对象调用 **一次 `QueryInterface(installed_step_iid, pythoncom.IID_IUnknown)`**。确切 E_NOINTERFACE 记 observed/false；其他异常记 unknown。不得在失败后再次 QI，不登记包装类型、不 makepy、不查询其他 IID 或替代 IDispatch。
- 仅在 QI 正面确认时，从原返回对象尝试 **一次只读 MapConfigurationData getter**。bool 就记录实际值；异常或非 bool 记 unknown，不回退到另一种属性调用。禁止 setter；global StepConfigData=false 不能替代对象 getter 结果。
- 核对最终文档数量仍为 0、输入文件 hash 不变。释放返回引用，唯一 ExitApp、等待自有 PID 退出、关句柄、CoUninitialize。清理错误另记，不覆盖首个 GetImportFileData/QI 诊断错误；不重启 host。

所有 native 调用使用现有 600 秒有界调用，分组上限 1800 秒；失败即停，无重试。保存原日志、原文件 hash、实际 TLB hash、库版本、调用 begin/end/error、返回对象/查询/属性结果和退出证据。**LoadFile4、OpenDoc、NewDocument、SaveAs、文档写入、导出和修复全部调用数必须为 0。** 若需要超出此序列，停止并交 root 重新判断。

成功最多能证明该原件在该 VM/安装版本下取得的接口与配置值；不能称为导入成功或生产验收。真正的产品修复仍须相关公共 CI 原件证据及 root 亲审后才可合并。本计划没有在本轮执行。
