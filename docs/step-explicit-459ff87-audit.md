# 459ff87：显式调用返回成功，参考曲线表示仍失败

独立离线审计通过；实际诊断结论仍为失败。原 report SHA256 `26f7be0f5515781db1cc043c1ddd918aac69f03c6d2eff929b0d6c3d21b7eb7d`、源码 ZIP SHA256 `ebf7de18971cdae3236db6236ba73d70e0dd1eb415c091ed2d07ddfaa63b6427` 已核。完整 **434 文件**与提交 `459ff8714d544b4a148af39a5d854715127602fa` 逐字节一致，十项加载源码指纹一致。[机器审计](evidence/step-explicit-459ff87-audit.json)由独立纯文件脚本生成。

原件保留于统筹目录 `wire-once-459ff87-01`，九文件副本存于 ignored `step-evidence/wire-original-459ff87-01`。不覆盖 8c6cdc9、60f1cf8 或本次失败；不重跑原生，不扫描开关。

| 检查 | 原始证据 |
| --- | --- |
| 宿主 | owned、隐藏、SW4404/rev33.5.0；启动前/退出后 native[] |
| 新绑定 | GetIDsOfNames(0,LoadFile4)=精确 int227；VARIANT9/None；原方法/属性/缓存无变；lazy key 存在且 None |
| 返回 | raw PyIDispatch 非空，原 Python 返回策略完成；LoadFile4 返回 part，errors=0，单文档 |
| 实际表示 | 两个 3DProfileFeature，ID17/18，各6段；其余特征无测得线段；完整图18特征 |
| 原始几何 | 12段、320mm、10/30/40mm各四段；仍 complete=false、geometry unavailable/value=null |
| 首错 | reference-curve profile unexpectedly produced sketch geometry |
| 设置 | 完整60f八值；5项 owned writes/反序恢复verified；162条读取/19完整阶段；原八值恢复 |
| 输入与退出 | 同10595字节/hash/所有metadata；CloseDoc/Exit/wait/handleclose/CoUninitialize各1；cleanup[] |
| trace | 主392行/196配对，唯一error是read-imported-wireframe；观察218行/109配对均结束 |

这比此前零导入绑定拒绝增加了真实返回模型证据；**没有证明参考曲线输出，也没有证明 As3DCurves 行为修好**。绑定与 ImportData 两项同时改变，不能归因于 null 单一变量。元数据证明依然不是 native VARIANT 内存/地址测量。

GetSketchSegments实际2次、GetLength12次，部分向量独立符合原解析阈值；它们不能替代完整几何验收。本诊断明确零保存，没有 native save/read-only reopen，未采集草图 feature error code；不能把错误码未测当成零，也不能用它补齐八文件公开门禁。

审计命令：`scripts/ci/audit-step-explicit-459ff87.py --bundle <原目录> --archive <step-wire-source-459ff87.zip> --input-file <固定原STEP> --output <另一路径>`。精确 pinned report/ZIP、全归档、十源码、参数、向量、偏好和 trace 均在脚本检查。审计成功表示证据自洽，绝不把原失败改绿。
