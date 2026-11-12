# 60f1cf8 首次 Neutral 三维曲线候选：原件离线审计

独立审计通过，原生诊断仍失败。唯一 LoadFile4 返回 part / errors=0，但两项3D草图再次触发 `reference-curve profile unexpectedly produced sketch geometry`。严格参考曲线要求保持，geometry仍 unavailable/null，原始部分观察不改写为通过。

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/wire-once-60f1cf8-01`。report SHA256 `0abe0117a2f06ccf8f7335f376d5e3a9f7c29e39af05d2ce5f2f0faf3e68b50c`；源码ZIP SHA256 `ed6c6a0d5799bfe38dcefabebf830cd0e2b44bd1cf707b07fc7c6e1acfdc020a`。184个选定runtime文件均逐字节匹配提交 `60f1cf889dac3b9b17e272ab25eec9b2974bc348`，不是全仓库归档；六个实际关键代码hash也逐项匹配。原件全文件原样保留在ignored `step-evidence/wire-original-60f1cf8-01`；未用统筹摘要代替独立原数据检查。随目录的coordinator-independent-audit.json仅保留/hash，不参与判定。

[机器审计](evidence/step-wire-60f1cf8-audit.json)记录精确值和调用次数。主要结论：

- 隐藏owned PID7080 / revision33.5.0，Python3.14.7 / pywin32312、实际TLB hash与d232e35一致。进程清单启动前/退出后均空；无timeout/部分激活错误。
- 单GetImportFileData/STEP QI/只读Map/LoadFile4，QItrue/Mapfalse，ArgString=r、同factory对象；原生part/errors0。无重试或基线重放。
- 主trace372行=186次配对，唯一error是read-imported-wireframe；observation218行=109次配对全完成。原生GetSketchSegments2次/GetLength12次。18个去重特征中，ID17/18均为3DProfileFeature、各6段，12段总320 mm；原长度向量及完整feature_inventory与d232e35原件完全相同。两份记录都未测得参考曲线；wrong representation仍严格失败，没有保存重开证据。
- 五项尝试设置顺序：3DI、GeneralFree、GeneralCurve、NeutralFree、NeutralCurve；原始返回/全八项读回均verified，随后按逆序五项恢复并完整读回原八值。154条读取、18个完整阶段均observed，restore_errors=[]。NeutralCurve真实从0写成1，changed_from_d232e35只有该key，其他七个导入前值与上次原件相同。未写NeutralSolid/globalStepConfig或额外字段。
- 固定10595字节原输入SHA `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`；preflight/case/report/final的文件ID、大小、创建/修改时间、attributes33和路径完全一致，并与上次记录相同。独立复核保留的原始输入字节，不声称本轮读取过VM当前metadata。
- CloseDoc/ExitApp/WaitForOwnedProcess/CloseProcessHandle/CoUninitialize各1且按序完成，cleanup_errors=[]；嵌套observation ExitApp是同一次调用，不多算。原first_error、顶层failure和trace一致；无Open/New/Save/Select/Export/fallback/第二次导入。

本次将NeutralCurve从0改为官方As3DCurves1，没有改变这两份记录的已测表示；这不足以证明全局优先级、字段被忽略的普遍规律，或替其他环境解释原因。尤其不能把本地model/errors0回填到旧hosted CI None/errors1，也不能将草图数值正确当参考曲线通过。停止继续扫开关/枚举，优先只读澄清LoadFile4参数合同。

可复跑本次审计（只读原件/源码，本地另写结果）：

```sh
.venv/bin/python scripts/ci/audit-step-wire-d232e35.py --candidate-60f1cf8 \
  --bundle step-evidence/wire-original-60f1cf8-01 \
  --previous-bundle step-evidence/wire-original-d232e35-01 \
  --source-zip /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/step-wire-source-60f1cf8.zip \
  --input-file /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/step-qi-ap203-wireframe.step \
  --output step-evidence/wire-60f1cf8-audit-repeat.json
```

旧d232e35默认审计复跑仍与已提交机器记录字节一致。输出路径新增保护，拒绝覆盖任一原件目录、输入文件或源码ZIP。本轮不操作VM/CAD/CI、不推送；VM已释放的状态只由统筹告知，本审计未自行探测或恢复VM。main和功能CI按统筹要求未查询。
