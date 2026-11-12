# d232e35 首次单次线框导入：离线独立审计

原件审计通过，原生诊断仍失败。首错为 `reference-curve profile unexpectedly produced sketch geometry`，不是 LoadFile4 错误：本次唯一 LoadFile4 返回 part / errors=0，但严格参考曲线表示检查拒绝了两个3D草图。未重试，未保存、重开、新建、选择或导出。

## 原件与源码

- 原件：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/wire-once-d232e35-01`。report SHA256 `4e8332dd621a389268e92ecb4cac317acb77a930b314c0b396662f9eaa10ee4e`，完整六文件原样复制在 ignored `step-evidence/wire-original-d232e35-01`；逐文件 SHA 见[机器审计](evidence/step-wire-d232e35-audit.json)。
- 实际源码归档 `step-wire-source-d232e35.zip` SHA256 `de52dbe3ca79c0a032ce6b488a2477859796c209234ee58e1bb5b43afff9707e`。184个 runtime 文件逐字节匹配提交 `d232e35fabdd2d89fecd8b2f4b90b9485d7425e3`；这是选定 runtime 子集，不是全仓库。report 六个关键实际代码 hash 均与归档和该提交匹配。
- Python3.14.7 / pywin32312，实际 TLB hash 与原计划一致，安装库解析出 Neutral AsSketches=0、As3DCurves=1。唯一 hidden owned PID2568 / revision33.5.0。启动前/退出后 native 进程清单均空。

## 原始特征和几何

完整保留18个去重特征 ID。14个顶层、4个光源子特征；两项可测几何均为顶层 `3DProfileFeature`，ID17/18，名称草图1/草图2，各6段。12次原生 GetLength，排序向量为10×4、30×4、40×4，其中一条原始长度29.99999999999999 mm；按原逐段1e-9 mm条件核验，合计320 mm。两个草图都记录在 `representation_mismatches=[17,18]`，没有记录到参考曲线几何。

原 `raw_observation.complete=false`、计数/长度/特征均保持不变；`geometry.status=unavailable,value=null`。离线核算原始长度只说明这份**错误表示的部分观察**满足12/320数值，不能将严格失败改成通过，也不证明参考曲线实现正确。原生保存/重开没有执行，生产或公开验收均不成立。

## 调用与首错

主 trace316行=158次 begin/完成配对，仅 `read-imported-wireframe` 以 error结束；observation218行=109次配对，全部结束。GetImportFileData、单STEP IID安全IUnknown QI、只读 MapConfigurationData、LoadFile4 各1；QI=true/Map=false，原 ArgString=r 与同 factory 对象。读取两个 GetSketchSegments、12次 GetLength。主 CloseDoc/ExitApp/WaitForOwnedProcess/CloseProcessHandle/CoUninitialize各1且按此顺序完成。嵌套 observation ExitApp 是主调用的同一次动作，不另算一次退出；重复 GetTitle 含代理内部读取，不能当成重复 CloseDoc。

未知/失败后只继续 owned 恢复和退出，未进入输入-after-observation成功路径。首错在 case、顶层 failure和 trace 中一致。无 timeout/部分激活错误文件，cleanup_errors为空。没有 fallback、重载、另起host或基线重放。

## 输入、CAS 与恢复

实际只读输入SHA仍为 `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`，独立核对原字节10595 bytes。preflight、case input_before、report input与input_final的文件ID、创建/修改时间、大小、attributes33、规范路径和SHA完全一致。输入在失败后由只读postflight复核；未补造没有执行的成功检查点。

128条偏好读记录、15个完整八项阶段均 observed。复核每个完整 CAS、每次 setter 全向量读回和最终向量；实际只写3DI→false、GeneralFree→true、GeneralCurve→1、NeutralFree→true共4项，反序恢复4项，全部原始返回/读回通过。GeneralSolid本来true而未写。NeutralSolid/NeutralCurve0/globalStepConfig从未设置。完整原向量恢复、restore_errors为空；没有靠覆盖外部状态来生成成功。

## 边界与下一步依据

旧 CI42813151084 的同原件返回 None/errors1；本地这次返回模型/errors0。两次环境不同，本次没有在同安装上重放失败基线，不能把差别归因于 NeutralFree、不能证明全局参数优先级、也不能宣布旧 CI 已修复。

已观察的组合为 NeutralFree=true、NeutralCurveOption=0，而安装版官方枚举和实际库均将0定义为AsSketches、1定义为As3DCurves。这为**只把 NeutralCurveOption改为官方As3DCurves(1)**提供一个有明确语义的候选依据；它尚未证明 importer 会消费该值或通过严格表示检查。下一候选应保持NeutralFree=true及所有其他值、r/原factory不变，不重放baseline，只离线准备供root审阅。不得据此修改生产/旧reader或发起完整CI。

可复跑（只读原件/源码、本地写审计结果，无CAD）：

```sh
.venv/bin/python scripts/ci/audit-step-wire-d232e35.py \
  --bundle step-evidence/wire-original-d232e35-01 \
  --source-zip /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/step-wire-source-d232e35.zip \
  --input-file /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/step-qi-ap203-wireframe.step \
  --output step-evidence/wire-d232e35-audit-repeat.json
```

本轮未操作VM、未执行CAD/CI/网络、未推送。全部原件保持原样；机器审计不包含原始内部日志或CAD字节。
