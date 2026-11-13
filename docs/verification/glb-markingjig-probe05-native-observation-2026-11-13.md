# MarkingJig probe05：首次组件 bodies 返回与严格几何首停（2026-11-13）

05 原结果仍为 **failed / first-failure-stop**。本路只读封存现有原件，没有改比较规则、套用数值例外、补native动作或派CI。用户尚未答复统筹的数值边界问题；本审计不作可接受性判断，也不把05改绿。

Root执行的source为a7ecb97、产品70d8c9e。唯一BYREF `GetBodies3` 在首个part `MarkingJig-1/MarkingJigEpoxy-1` 成功返回tuple3 bodies、tuple body-info `[1,1,1]`，三份component body原始bounds与12项mass properties均已保存。随后 `model_state_after` 与独立modelDoc原状态精确比较触发首错 `independent model state changed during component body observation`。

完整递归原字段比较只发现以下三处，每处载入后的IEEE754 binary64表示恰相隔1ULP；类型、字段、数组及signed-zero均纳入比较，没有删除或归一化字段：

| 原字段 | before | after | 绝对差 |
| --- | --- | --- | --- |
| `geometry[0].centroid_m[2]` | `-0.00491648046615544` | `-0.004916480466155441` | 约 `8.673617379884035e-16 mm` |
| `geometry[1].centroid_m[0]` | `0.027470467043563977` | `0.027470467043563974` | 约 `3.469446951953614e-15 mm` |
| `geometry[1].volume_m3` | `3.657348806308393e-08` | `3.657348806308394e-08` | 约 `6.617444900424222e-24 m³` |

审计另存每个原float的repr、hex、精确十进制差与ULP距离。这里只量化已序列化观测值的不同，不证明真实物理变化、差异原因或任何误差界限。面积/拓扑/state/CAS等其余model字段在该局部比较相同；整装配没有完成，不能将局部相同推广到全部组件。

## 已达边界与未达边界

一个subassembly与首个part已进入观测；首个part引用/active配置都是“默认”。尚未走到03原先失败的MarkingJigBlock配置不一致位置，也未走完现代依赖图、全部几何或第二完整观察。loaded baseline未seal，context complete=false，SaveAs/export0，不能称probe、配置问题或GLB导出已验收。

这次原件首次证明现有明确BYREF形式在该首个part上实际返回了预期数组；它不等于取得native TYPEDESC，也不证明所有配置/组件封送均通过。此前纯PIA/合成测试与这次有限native返回证据分别保留，不改写旧证据。

404条trace全begin/end配对。acquire-owned-host、OpenDoc7、GetBodies3、CloseDoc、ExitApp、WaitForOwnedProcess、CloseProcessHandle、CoUninitialize均各一次。native report与launcher primary_failure完全一致，launcher first_error=null，cleanup/secondary均[]。三次native清单before/after/postcleanup均[]，十私有input、全部八code与四份bootstrap后核完整通过；11Mac原件before/after完整指纹逐字相同。历史host-after显示idle:on。

candidate/worker退出码1属于失败子进程；原trace没有记录SOLIDWORKS native进程退出码，不能称native exit0。清理完成和文件守恒不能升级业务结果。

## 原件与可复现审计

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-a7ecb97-05`，本路未改任何文件。

- 原native report SHA `1a34ad9aa38a5d346c01af21a50b21f541bf4761882cbc7f2a606b88f9d0d37f`。
- [独立审计JSON](../evidence/glb-markingjig-probe05-native-observation-2026-11-13.json) 保存原首错、全部三delta、trace计数、源包8blob逐字Git核对、原件SHA及证明边界。
- [只读重放脚本](audit-glb-markingjig-probe05.py) 仅读既有原件和固定Git blobs，不导入诊断runtime、连接VM、读取业务源或调用任何比较容差。重放输出与归档JSON逐字一致。

Root另有05/coordinator-independent-audit.json/.py独立封存。用户边界未答复期间，仅归档已有证据；比较代码、策略、旧结果及冻结包保持原样。后续范围与任何新票仍由统筹明确。
