# 固定原件的单次线框导入诊断（待统筹审阅）

当前真实首错仍是 CI42813151084 的第二项：AP203 wireframe 的 `LoadFile4` 返回 None / errors=1，只有第一项实心导入完成。本入口只检验一个新的自由曲线开关组合，不是已证明的修复，不接入 CI，也不改变现有 reader、零导入脚本或生产导出逻辑。VM 与 CAD 的独占和实际执行仍由统筹负责。本轮只做本地准备。

## 固定输入和环境

脚本：`scripts/ci/diagnose-step-wire-import-once.py`。必须使用审阅提交的独立完整 runtime 源码快照，放在 Workspace 独立目录，不替换现用 checkout 或安装包。preflight/report 记录实际源码目录、六个关键代码文件 SHA、Python/pywin32、库 hash、输入 metadata 和进程清单；统筹另外保存实际传输归档及提交对应的逐文件校验清单。

唯一输入为 `C:\Workspace\SWCLI-series-20261111\step-qi-input\ap203-wireframe.step`，SHA256 `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`。来源为 run42413805736 / head060f26178b4deabc330ef0959b9ec0f1704159cf / artifact13591430613，原 ZIP SHA256 `de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7`。统筹先复核原 ZIP 与单文件字节；脚本不下载、复制、修复或修改属性。要求文件预先 Windows READONLY、固定规范路径、无链接/重解析点，hash/文件ID/大小/修改创建时间/属性在各检查点完全一致。

要求原生 Windows、pywin32=312、实际 revision33.5.0。固定 swconst.tlb SHA256 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`；sldworks.tlb SHA256 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`。从这两份库解析对应枚举及唯一 STEP IID `{AD749A73-9AA2-4A3E-BCA5-8FC012114BB0}`，库、枚举、接口名称或版本不符即停。不会扫描候选 IID、makepy 或替换包装。

## 八项原值、旧 CI 基线和唯一新变量

| 偏好 | 本地4b0104b原件观察值 | 必须精确读回的旧 CI 基线 | 单次候选 |
| --- | --- | --- | --- |
| 3D Interconnect | true | false | false |
| General SolidSurface | true | true | true |
| General FreeCurves | false | true | true |
| General CurvePreference | 0 | 1 | 1 |
| Neutral SolidandSurface | true | true | true |
| Neutral FreeCurvesAndPoints | false | false | **true** |
| Neutral CurvesAndPointsOption | 0 | 0 | 0 |
| global StepConfigData | false | false | false |

表中本地值是历史观察，不假设下一次启动仍相同。先读取实际完整八项且核验类型；曲线原枚举须为已知0/1。Neutral Solid/Free/CurveOption/global StepConfig 必须分别为 true/false/0/false，否则零设置、零导入停止，不自动归一化。完整八项 CAS 比较原快照，再逐项准备旧 CI General 基线；每个实际 setter 前做完整八项 CAS、调用前记录可能修改、调用后记录原始返回与完整八项读回。已等于请求的字段不写。

旧 CI 八项精确读回通过后，只新写 `Neutral_FreeCurvesAndPoints=true`。Neutral CurveOption 保持0，另外三项不允许 setter 到达底层 COM。导入前再次核对完整候选向量。

失败或完成均只按逆序恢复本次**尝试写过**的字段，包括 setter 已部分生效后抛错或拒绝的字段。每个恢复前核对该字段仍是原值/请求值之一，外部第三值不覆盖；恢复一次并读回，不重试。其他 owned 字段继续清理，最后全八项与原快照比较，不写未拥有的字段来凑齐。未尝试任何写入时恢复标记为 not required / null，不能把外部漂移称为恢复成功。首个业务错误与恢复/清理错误分开保存。

## 唯一原生序列

1. 启动前无 SOLIDWORKS 进程；单次 ROT 查询仅接受明确无宿主。一次独立隐藏 owned host，实际 revision33.5.0、初始文档数0；不附着已有宿主。
2. 执行上述快照、CAS、General 基线和唯一新开关。重新核对只读输入。
3. 最多一次 `GetImportFileData`，对原对象最多一次安全 `QueryInterface(installed_step_iid, IID_IUnknown)`，仅正面结果后一次 MapConfigurationData getter，严格要求 bool。无 setter。任一 unknown/None/拒绝/异常即停，不能为取证继续尝试导入。
4. 最多一次 `LoadFile4(INPUT, "r", same_factory_object, errors)`。保留原 ArgString 与原 factory 对象，不同时更换参数，也不设置对象映射。调用前持久化可能创建文档状态；原始 errors、返回类型、空模型或异常原样记录。
5. 返回模型即先交给 owned 清理，即使 errors 非0也不丢失清理责任。仅 errors=0、part类型、可读自有标题和文档数1才能测量。使用现有完整特征遍历，严格核验参考曲线表示、恰好12段、320 mm、排序长度向量 `[10×4,30×4,40×4]`；保留现有逐段1e-9 mm与总长度原阈值，不改断言。
6. 无模型、错误、未知或几何断言失败时 `geometry.status=unavailable,value=null`，保留原 `raw_observation` 的特征、部分计数/长度/表示不符，不把未测量转换为零几何。即使草图有12段/320 mm，参考曲线表示检查仍失败。
7. 释放数据引用，恢复本次 owned 偏好；仅关闭本次自有导入文档一次，ExitApp、等待本次进程退出、关句柄、CoUninitialize。文件 metadata/hash 与剩余进程复核。保留原 first_error，不让清理失败覆盖它。

全程禁止 OpenDoc/New/Save/Export/Select，没有回退、重试、参数扫描、重建、另起宿主或自动回放失败基线。只读代理在底层 COM 前阻止这些调用。主 trace、隐式观察 trace、部分激活清理 trace 都由父进程监督：600秒调用/1800秒分组，必须从主入口运行。超时只停止本次 Python worker，保留原 report 并另写 timeout，明确 owned exit unknown、交统筹清理，不全局终止 CAD。

## 统筹审阅后的执行方式（未执行）

统筹先完成源码归档对应提交校验、独占协调，准备父证据目录 `C:\Workspace\SWCLI-series-20261111\step-wire-import-evidence`。输出须为全新直接子目录，不复用旧报告。示例不代表已执行授权或已执行结果：

```powershell
python -I C:\Workspace\SWCLI-series-20261111\step-wire-import-code\scripts\ci\diagnose-step-wire-import-once.py `
  --output-dir C:\Workspace\SWCLI-series-20261111\step-wire-import-evidence\wire-once-01 `
  --swconst "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swconst.tlb"
```

保留原 preflight/report/trace、observation与partial-acquisition日志、stdout/stderr和源码归档 hash。若失败，只审计本次首错和部分观察，不换开关重放。成功也只证明该本地安装与组合的单次行为，不证明全八项公开读回、生产验收、General/Neutral优先级或因果修复。

本地原始默认值与 hosted CI 有三项 General/3DI差异，安装路径也不同；准备旧 CI 向量不能消除环境差异。既有官方语义及 LoadFile4 参数文档歧义见 [原始接口取证审计](step-local-qi-4b0104b-audit.md)。需要因果结论应另行澄清厂商合同或审阅同环境受控方案，不能自行多次导入。

便携验证已通过：14项专用测试、84项 STEP 回归；全量1903项（26项跳过）。这些使用 fake COM/进程，不是实际导入结果。CLI help 和 whitespace 检查通过；原零导入脚本、现有 CI/reader 和生产代码均未改。

## d232e35 首次实际执行之后

root已实际执行一次默认模式，LoadFile4返回part/errors0但严格参考曲线表示失败：两个3D草图各6段。详见[原件独立审计](step-wire-d232e35-audit.md)。此前“未执行”是该准备阶段的历史状态；不得重跑默认baseline。现仅准备[Neutral As3DCurves单变量候选](step-wire-neutral-3d-candidate-plan.md)，尚未执行、未证明修复。
