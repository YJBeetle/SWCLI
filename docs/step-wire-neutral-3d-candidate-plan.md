# Neutral 曲线表示单变量候选（仅准备，待 root 审阅）

有足够依据准备一次可证伪的诊断候选，没有足够证据宣称导入修复。d232e35首次实际执行得到 part/errors0，但两个3D草图使参考曲线表示检查失败；原始12段/320mm并未被提升为成功。[独立审计](step-wire-d232e35-audit.md)保留原件、完整CAS/恢复、退出和环境差异。

## 依据与唯一差异

本次实际安装库解析 Neutral AsSketches=0、As3DCurves=1；之前只读提取的安装版官方2025帮助同样如此。该枚举页面SHA256 `575e3f7bda3e5c2f99eef0878d06ccf5a0ec7da9aad3cee055f5343c7ec6e791`，swconst.chm SHA256 `d9227d92abc44bc964d897641352a2f4efe984453d28c14a4364008a14bf3300`，保留在ignored installed-help-2025及此前机器证据。它来自本机MacSW安装帮助，不声称VM CHM字节相同。实际VM TLB SHA与report枚举则是此次已观察的原生证据。

候选只把 `swImportNeutral_CurvesAndPointsOption` 从官方AsSketches(0)改为As3DCurves(1)。实际setter使用经过hash核验的安装库解析值，0/1整数合同不符时，在任何setter前停止。其他七值与d232e35实际导入前完全一致：

| 值 | d232e35实际导入前 | 下一候选 |
| --- | --- | --- |
| 3D Interconnect | false | false |
| General SolidSurface | true | true |
| General FreeCurves | true | true |
| General CurvePreference | 1 | 1 |
| Neutral SolidandSurface | true | true |
| Neutral FreeCurvesAndPoints | true | true |
| Neutral CurvesAndPointsOption | **0** | **1** |
| global StepConfigData | false | false |

保持同一个固定只读原件、r参数与原factory对象；MapConfigurationData只读，不设置、不按global推测对象值。虽然枚举与当前错误表示有语义上的一致性，尚未证明此导入路径消费该字段，更没有官方General/Neutral优先级承诺。不得解释为已验证因果修复。

## 显式入口及保护

在原独立脚本中增加显式 `--neutral-3d-candidate` 模式，diagnostic_case为 `step-wire-neutral-3d-once`；不接入CI、不改零导入脚本、生产adapter或既有公共reader。原d232e35执行字节仍由提交/归档固化；默认模式兼容历史审阅，但**本轮不得再次执行默认基线模式**。

候选仍只有一个case、一个owned host和最多一次LoadFile4。先记录实际完整八项原值和初始CAS；原NeutralSolid/Free/Curve/global须为true/false/0/false，否则零设置/零导入停止。像d232e35一样准备General向量和NeutralFree=true，并仅用读取核验这份**准备后的向量**；这不是基线导入重放。随后完整CAS后设置唯一新NeutralCurve=As3DCurves，读回完整八项，持久化 `changed_from_d232e35=[swImportNeutral_CurvesAndPointsOption]`。此时才允许唯一GetImportFileData/QI/getter/LoadFile4。

相比d232e35，自本地默认原值出发最多多出一次owned整数setter及对应恢复；原已等值的字段不写。每次setter前完整八项CAS、先记可能修改/再调用、保存原始返回与完整读回。允许写入NeutralCurve仅限显式候选模式，另外两个未拥有的NeutralSolid/global字段仍禁止。记录并反序恢复所有本次尝试写项，包括异常部分生效或原生false拒绝；第三外部值不覆盖，原错误优先，完整原八项恢复必须复核。原固定输入文件metadata/hash与库/IID/pywin32312/revision33.5.0前提不变。

严格参考曲线表示、12段/320mm、原长度向量与阈值全部保留；草图即使12/320仍失败。错误/未知几何保留unavailable/null与原始部分特征/长度。不保存/重开、新建、导出或选择，无fallback、重试、参数扫描、另起host。返回模型先交owned清理；CloseDoc一次、Exit/wait/handleclose/CoUninitialize，首错与恢复/退出错误分记。主/观察/部分激活trace仍受600秒调用、1800秒分组监督；超时owned退出unknown，交统筹清理。

## 审阅后的唯一执行计划（未执行）

root先亲审差异与原件审计，决定语义依据是否值得一次原生运行。只在root决定执行后由其协调VM独占、保存审阅提交对应的完整runtime源码归档/hash/清单，不替换生产安装。固定输入/实际库仍按[原执行计划](step-wire-import-once-plan.md)逐项核验。新输出必须是 `C:\Workspace\SWCLI-series-20261111\step-wire-neutral-3d-evidence` 下全新直接子目录，不复用旧证据。

```powershell
python -I C:\Workspace\SWCLI-series-20261111\step-wire-neutral-3d-code\scripts\ci\diagnose-step-wire-import-once.py `
  --neutral-3d-candidate `
  --output-dir C:\Workspace\SWCLI-series-20261111\step-wire-neutral-3d-evidence\neutral-3d-once-01 `
  --swconst "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swconst.tlb"
```

parent将候选标志显式传给worker；不同证据父目录防止与历史默认入口混淆。不得直接运行隐藏worker绕过监督。原件/日志/stdout/stderr/超时记录/代码hash必须全部保留，失败即审计首错后停止，不自动转回0或另一个组合。

结果判定：模型/errors0且严格表示/12段/向量通过，仅说明该环境下这份原件的一次候选行为；没有保存重开或八文件公开读回，仍不是生产/公开验收。任何失败保留原结果，无下一次native尝试。本地与hosted CI仍是不同环境，不重放已知失败baseline，不能从两环境差异归因全局优先级。

本轮只做源码/测试/文档准备，无VM/CAD/CI/push，等待root审阅。正式执行必须另由root安排。

便携验证通过：20项专用测试、90项 STEP 回归；全量1909项（26项跳过）。新用例核对候选八项只差NeutralCurve、原factory/r、无基线导入、五项写/反序恢复、枚举未知零设置、整数拒绝/部分生效/恢复失败、外部第三值不覆盖、草图12/320仍失败、缺段/错长度/None错误保留unavailable，以及父进程传递显式模式和独立证据目录。均为fake COM/进程，不是原生候选执行。d232e35原件审计复跑字节一致，CLI help/whitespace检查通过。
