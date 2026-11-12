# 单原件 STEP 接口取证计划：零导入、零保存（仅统筹执行）

本计划只验证已证明的 pywin32 包装取证缺陷，不能验证或修复 `LoadFile4` error=1。不得为此重跑完整 CI。VM/SOLIDWORKS 的启动、独占协调、退出和恢复由 root 统一负责；此分支不操作 VM。

## 启动 CAD 前必须核对

1. 固定来源仍为 run `42413805736` / artifact `13591430613`，原 ZIP SHA256 `de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7`。只取其中 `swcli-native-smoke/step-public/ap203-wireframe.step`，预期 SHA256 `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`。
2. 统筹已固定唯一 CAD 输入路径为 `C:\Workspace\SWCLI-series-20261111\step-qi-input\ap203-wireframe.step`，不使用 Desktop，也不接受命令行更换输入。root 仅新建或复用完全同 hash 的原字节，不覆盖不同已有文件、不改原 ZIP；预先设置 Windows READONLY 属性。脚本拒绝链接/重解析点、路径解析偏离、hash 或原 metadata（文件 ID、大小、修改/创建时间、属性）变化，且不会复制、解包、改属性或写该输入。
3. 记录诊断提交、Python 与 pywin32 版本。原 CI 安装的是 pywin32 312；本次只使用已核对该语义的版本。实际安装 `sldworks.tlb` SHA256 必须为 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`，swconst.tlb 为 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`。版本/库不符停止，不套用另一套 IID。
4. 从该官方 TLB 核对 IImportStepData 名称与唯一 IID `{AD749A73-9AA2-4A3E-BCA5-8FC012114BB0}`；只核这个目标，不查询 IGES 或其他候选 IID。已核的 [pywin32 312 QueryInterface 实现](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyIUnknown.cpp#L96-L158) 表明第二参数仅为 Python 包装选择；使用 `pythoncom.IID_IUnknown`，不假装成 IDispatch、不调用自定义 vtable。

## 唯一执行序列与记录

- 确认 VM 可独占且没有要保留的交互 SOLIDWORKS 进程；创建一个隐藏、诊断自有 host。不得附着、杀掉或重用其他 owner 的 host。记录 PID/revision、owned 状态、初始文档数量，必须为 0。
- 不写任何 preference。只读并记录原八项 General/Neutral/3DInterconnect/global StepConfigData 原值，各一次；这些读值不证明 translator 优先级。
- 对上述唯一文件调用 **一次 GetImportFileData**，记录 None/实际 Python 类型；本次不额外查询 type-info，以免把无关诊断失败带入此最小序列。若返回 None/抛错，保留首错并停止，不查替代入口。
- 对返回对象调用 **一次 `QueryInterface(installed_step_iid, pythoncom.IID_IUnknown)`**。确切 E_NOINTERFACE 记 observed/false；其他异常记 unknown。不得在失败后再次 QI，不登记包装类型、不 makepy、不查询其他 IID 或替代 IDispatch。
- 仅在 QI 正面确认时，从原返回对象尝试 **一次只读 MapConfigurationData getter**。bool 就记录实际值；异常或非 bool 记 unknown，不回退到另一种属性调用。禁止 setter；global StepConfigData=false 不能替代对象 getter 结果。
- 核对最终文档数量仍为 0、输入文件 hash 不变。释放返回引用，唯一 ExitApp、等待自有 PID 退出、关句柄、CoUninitialize。清理错误另记，不覆盖首个 GetImportFileData/QI 诊断错误；不重启 host。

所有 native 调用使用现有 600 秒有界调用，分组上限 1800 秒；失败即停，无重试。保存原日志、原文件 hash、实际 TLB hash、库版本、调用 begin/end/error、返回对象/查询/属性结果和退出证据。**LoadFile4、OpenDoc、NewDocument、SaveAs、文档写入、导出和修复全部调用数必须为 0。** 若需要超出此序列，停止并交 root 重新判断。

成功最多能证明该原件在该 VM/安装版本下取得的接口与配置值；不能称为导入成功或生产验收。真正的产品修复仍须相关公共 CI 原件证据及 root 亲审后才可合并。本计划没有在本轮执行。


## 已准备脚本与调用合同（本地提交，尚未执行）

入口为 `scripts/ci/diagnose-step-import-data.py`，case 函数 `case_runner`。复用 `verify-through-all-calibration.py` 的单 owned 生命周期、退出和进程等待，严格枚举官方 swconst 六 Toggle + 两 Integer，以及单一 STEP IID。`ReadOnlyApp` 只暴露读取/退出所需成员，LoadFile4/OpenDoc/Save/New/Select 和偏好 setter 无法到达底层 COM。每个值都必须已知且类型正确；None、COM 拒绝、未知包装/属性或任何其他诊断错误立即停止后续业务，只有清理和只读证据检查继续。原始异常保留，清理错误分开。

root 使用该本地提交的完整**独立源码快照**，置于 Workspace 的诊断代码子目录；不覆盖现用 checkout，也不安装/替换生产包。脚本显式使用快照 `src` 及现有 owned harness，不接受只复制单文件后回退到另一版本的 STEP 模块。`preflight.json` 保存代码文件 hash、原文件/库 metadata、Python/pywin32 版本和 nohost-before；启动前进程清单须为空，ROT 只有明确“无活动对象/未注册”的状态可激活一次，其他错误停止。实际 host 隐藏状态与 revision33.5.0 再核验。

root 预先创建 `C:\Workspace\SWCLI-series-20261111\step-qi-evidence`；`--output-dir` 必须是该目录下**尚不存在的直接子目录**。示例仅供审阅，未在本轮运行：

```powershell
python -I C:\Workspace\SWCLI-series-20261111\step-qi-code\scripts\ci\diagnose-step-import-data.py `
  --output-dir C:\Workspace\SWCLI-series-20261111\step-qi-evidence\qi-once-20261111
```

原 600 秒调用/1800 秒分组由父进程监控主 trace、隐式 COM observation trace 和部分激活清理 trace。正常或首错路径都等待唯一 owned 进程退出；若超时父进程只停自有 Python worker，`timeout.json` 明确 owned 退出 unknown、需 root 清理，不能伪造退出成功或执行全局终止/重启。不得直接调用隐藏 `--worker` 绕过时限。

本脚本不接入工作流，不准备任何新原生 CI。产物成功只代表单原件接口/配置取证，不证明 LoadFile4 error1 已修复或产品验收通过。

便携验证：新增11项零导入 guard/trap 测试通过，合计70项 STEP 回归通过；全量1889项、26项跳过，其余通过。仅测试 fake COM/进程和原时限分支，未启动真实宿主；原件、接口和退出效果仍等待 root 的单次实际执行证明。代码与计划本轮仅本地提交，不推送、不派发。

## root 首次实际执行之后

root 已完成第一次实际单次执行，详见 [本地原件审计及选项语义研究](step-local-qi-4b0104b-audit.md)。单STEP QI=true、对象配置false、零导入/保存/新建/选择/偏好写与退出证据已离线复核。它属于VM默认3DI=true环境；不能替换旧CI3DI=false环境的unknown或证明LoadFile4 error1修复。此前“尚未执行”均为准备阶段历史状态。
