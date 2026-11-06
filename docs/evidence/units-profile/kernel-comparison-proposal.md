# 单位几何比较口径的最小变更提案（待统筹确认，未应用）

业务产品源仍为`5f307d1`，没有新字段或新写域。当前精确head的run42279525986在内部前置失败，public CLI未执行。原始ZIP artifact ID13536485767，SHA256 `c2dc13ce277eee306cce349b5b9a28fd3348b7a8a8dfdf5d9718002d86f278eb`，与GitHub digest匹配。完整原件本地`evidence/units-profile/product-42279525986/original.zip`，失败report在本目录product-42279525986。

## 实证与限制

此run的V/S/体数/质心x,z精确一致，质心y仅从5.514537417020185e-16到8.271806125530278e-16 mm，delta2.7572687085100926e-16 mm。旧诊断run42277659656也记录零附近x/y细微差异。原解析几何检查通过，额外的Python字典逐值精确相等失败。不能从这些读数直接断言物理几何被单位API改变，也不能把原失败记录改成通过。

官方IBody2.GetMassProperties文档定义返回double数组（质心、体积、面积等）及metric单位，没有为本次调用提供逐次读数按bit相同的保证：[官方文档](https://help.solidworks.com/2023/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IBody2~GetMassProperties.html)。这里不声称文档已证明本次差异根因。

仓库已有 `scripts/ci/gate_support/model_checks.py:37` 的 `unchanged_depth_metrics` 明确处理独立kernel读取浮点差异：体数保持精确int相等；V/S/三轴质心逐项有限值检查，绝对差不超过`max(1e-6, abs(baseline)*1e-12)`（各字段本来的mm/mm²/mm³单位）。本单位脚本此前额外引入了dict精确相等，尚未复用该既有判据。

## 待批准的具体patch

`kernel-comparison-proposal.patch`仅修改两份CI验收脚本和对应测试，不改产品API、模板、几何输入、Set次数或写白名单：

- 内部校准与public CLI复测统一复用上述**现有函数及阈值**，不新设容差。
- 体数精确不变、V/S/xyz每一项都保持检查；原解析几何V=12000/S=3800/质心(0,0,5)及rel_tol1e-7/abs_tol1e-5完全保留。
- raw、hex、exact_equal=false与差值全部保留，另外记录within_kernel_tolerance，不将数值不相等伪装成精确相等。
- 状态、foreground/target identity、lease/stamp、全snapshot CAS仍为原精确比较；不变更到容差或做四舍五入。

该patch仅应用在本worktree的隔离测试快照`evidence/units-profile/kernel-comparison-proposal/snapshot`，不是Git worktree，未改主产品文件。47项关联测试通过：原ULP差异保留非精确标记；六种维度（体数/V/S/xyz）越界均拒绝；NaN/Inf拒绝；public只读重开后2e-6mm漂移虽通过解析几何仍被不变性比较拒绝。保存原生读数的离线重放结果在`kernel-comparison-proposal-replay.json`；仅是离线检查，不是新native验收。

## 需要统筹决定的边界

原委托明确要求“不放宽几何或状态断言”，本提案会改变额外dict精确比较的接受范围，因此**未自行应用、未触发新CI**。需要统筹确认是否允许在本系列复用既有kernel不变性判据。若批准：应用此已审查的最小patch，完成关联检查并对新的精确head执行一次必要公共gate；此前失败原件保留，只有新的严格全组/public真实原件通过才可给可合tip。若不批准：保留当前失败，继续既定问题的其他可行定位，不能重复无差异CAD或把本系列未完点简单后置。
