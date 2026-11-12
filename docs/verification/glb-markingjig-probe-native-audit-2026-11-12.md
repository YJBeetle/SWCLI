# MarkingJig单次只读probe实际首错

VM-20261112-MARKINGJIG-PROBE-01按统筹明确批准执行。代码为`e3d9bd9a4ce726e6fdb97277c73fca02237c6c08`（诊断修正7af1d01），产品仍固定70d8c9e及原driver/zip摘要。执行前Mac11份原件指纹与批准inventory逐项一致，批准十份native文件复制到全新C:\Workspace独立普通只读副本，nlink1且逐文件SHA/size匹配；业务二进制未入SWCLI仓/CI，既有GLB未复制到VM。

唯一一次`--mode probe`失败，未重试。owned隐藏SW PID5336、RevisionNumber33.5.0，worker4996正常exit1；OpenDoc7临时八项规格逐项保持，调用一次约7.38秒正常返回，Error=0、Warning=2。按原严格零warning门禁首停，observations为空，实际model readonly/配置/编辑/initial resolved完整组件图、现代依赖及几何窗口均未进入；不能称模型缺失引用或GLB失败。2025[官方警告定义](https://help.solidworks.com/2025/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swFileLoadWarning_e.html)中2对应ReadOnly；此次不据此放宽门禁，也不再向CAD补读验证。

独立的OS源窗口后检查另报`working-copy bytes/identity/state changed`，与首错分开保留。原输出与后续仅OS stat/hash对照表明：10份副本内容SHA全不变；唯一差异为顶层MarkingJig.REND.SLDASM的handle_before/handle_after两记录中ctime_ns，从1794484561313916500变为1794484583570629700。所有记录的path字段、birth/mode/attrs/nlink/size/mtime等其余字段保持。该变化在原OpenDoc7时间窗内被观察到，但没有完整文件访问追踪，不定原因，更不能泛化忽略held渠道ctime；现严格检查正确拒绝该窗口。

probe显式export/save均0，依赖查询0，输出GLB0，无fallback、重建、解析、配置切换、旧SaveAs、修引用或额外模型。CloseDoc、ExitApp、WaitForOwnedProcess、CloseProcessHandle、CoUninitialize均begin/end正常；supervisor与launcher前后原生进程清单均[]，没有超时或强杀。report的cleanup_errors保留OS源窗口失败，不能把它说成全部清理字段为空；COM owned退出与OS状态失败分别报告。

Mac原始10模型与既有GLB共11份完整指纹/hash前后相同。候选代码前后SHA匹配批准zip，inventory SHA `d7db20f8041424115a97b91376001be759b32fad6e5faa2cc405fe971a13185d`。VM初始stopped，执行时启动并临时idle pause off；本次已恢复原值on，最终自动paused。没有停止/清理他人进程，未编辑中央调度；资源交还统筹，不能自动invoke。

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261112/markingjig-probe-e3d9bd9-01`。report SHA `a729e16e746a8bac64ea6e51d45df9074d1de68002129f36d04b87d30d0cb42f`。完整[结构化离线审计](../evidence/glb-markingjig-probe-native-audit-2026-11-12.json)由[无CAD审计脚本](audit-glb-markingjig-probe-e3d9bd9.py)重放输出；evidence_audit_passed仅指原件/边界审计通过，probe_success仍false，不是原生能力/GLB验收。

本轮不修改诊断门禁、产品或CI，不自动再开probe/invoke；后续须统筹根据warning与真实源窗口变化审查决定。宿主普通工具权限初始化错误和本机OS-postcheck解析遗漏import的中间错误未触发额外CAD：前者改用已批准工具权限，后者只重新解析已保存stdout；首个业务错误保持原样。
