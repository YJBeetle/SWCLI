# GLB component-context probe 数值界限（仅源码，2026-11-13）

统筹已转达用户明确允许：**centroid每坐标绝对差≤1e-12mm，volume≤2ULP**，后续同类判断由Root自主处理。本提交仅实现当前显式GLB诊断范围，不扩字段或功能，没有VM/COM/CAD、新CI或push。原05仍failed、原件不改绿。

## 适用范围与语义路径

只在既有显式组合 `--mode probe --phase-policy opening-transition-probe --component-context-policy component-bodies-probe` 使用新策略 `glb-component-centroid-volume-v1`。默认 `strict-model-configuration` 和所有invoke路径保持原精确比较，不能借本策略导出。

唯一允许数值界限的路径：

- 局部独立modelDoc复查：`geometry[body].centroid_m[axis0..2]`、`geometry[body].volume_m3`。
- 完整snapshot：`components[i].model.geometry[...]` 与 `components[i].component_context.model_state_after.geometry[...]` 的同义字段。
- 实例body：`components[i].component_context.bodies[j].centroid_m[axis0..2]`、`.volume_m3`；同一body的 `.mass_properties_raw[0..2]` 为centroid、`[3]` 为volume。

不用任意同名键或全树模糊匹配。area、bounds/raw bounds、mass/inertia `[4..11]`、body数、type/faces/edges、所有配置/原件身份/readonly/dirty/rebuild/stamp/CAS/图/文件/phase/预算仍严格；未知形状、错类型和非有限数拒绝。原body raw与derived centroid/volume/area、raw/derived bounds在**每一份观测内部**必须逐字一致，不能分别套界限掩盖不一致。

## 数学定义与回执

centroid输入为有限binary64，单位m。比较用其精确有理数差乘1000，与精确十进制 `1/10^12 mm` 比较；逐坐标，不使用向量范数或相对误差。不会因中间浮点单位换算舍入将超界值误放行。因此最靠近十进制1e-15m的float若略高于精确界限仍拒绝，其向零相邻值接受；测试覆盖正负两侧。

volume使用有限、非负binary64的有序表示距离，最多两个相邻表示步长；不采用百分比epsilon或按decimal位数舍入。零附近和subnormal同样按表示距离；负volume拒绝。signed zero保留原hex，两个零编码不合并、不回写原值。

每次允许路径的比较均保留before/after原值与类型、hex、精确有理数delta、ULP、完整字段路径、单位/界限、accepted与原因。严格数值字段的拒绝也保留原值、hex、delta、ULP和明确strict判定。无法形成有限binary64差值时保留原类型/表示和拒绝原因。

回执只写到 **case.geometry_comparisons**，policy写case.geometry_numerical_policy；两者在native observations之外。原native字段一项不排除、不round/normalize，不用before替换after，不重建或重封baseline。两次native raw快照即使存在获准微差也分别保留。

## 三处一致准入与fail-closed状态

局部model_state_after、两次完整snapshot、supervisor audit共用同一语义比较函数。native侧每次记录本次原始before/after路径与完整回执；supervisor从原始observations逐个重算全部局部和整体回执，必须策略、判定及完整回执精确一致。缺policy、缺回执、篡改accepted/raw/state或改用旧strict名义均拒绝。旧05没有新policy与回执，仍是原failed，不用新工具覆盖旧结果。

比较前按当前document()实际字段验证状态：top是10项状态且没有geometry；component model是同10项加geometry。type/path/title/stamp、readonly/modified/viewonly、needs_rebuild、active配置与非空唯一完整配置集合都须存在且原生类型正确，clean/view-only/rebuild约束保留。外部模型必须readonly；既有virtual组件只能在明确virtual=true与原所有权门禁下保留原embedded例外。part需有界非空geometry；subassembly必须有精确原 `kind=subassembly/model_state_observed=true` 标记。

完整snapshot须保留原七键complete/host/top/components/dependencies/dependency_queries/catalog，complete=true；host必须具备原PID、creation filetime、exe路径/hash、revision及四bool flags，身份类型与当前隐藏模式正确。component kind必须匹配model type，context完整；其余集合仍逐字比较。不能把两边同时删字段或相同未知状态当成功。

## 验证与交接边界

本机macOS CPython3.15.2上MarkingJig **168项通过**，其中新增数值测试28项；typed bridge23项通过。包含精确mm换算与边界两侧、每坐标、1/2/3ULP上下行、signed zero/异号/subnormal、原始三种数值形状、非有限/错误类型/未知字段、raw alias不一致、面积/拓扑/state改动、双侧同时缺状态、host/top/subassembly结构和virtual只读边界；局部/整体/supervisor一致与篡改拒绝也覆盖。原strict对1ULP仍拒绝。

只改两个诊断runtime文件，无新增runtime模块；forensics、phase、receipt helper与typed loader/bridge逐字保持a7版本。冻结02/03/04/05准备文件未变，05 report SHA仍 `1a34ad9aa38a5d346c01af21a50b21f541bf4761882cbc7f2a606b88f9d0d37f`、success=false/未seal。原文件没有任何回写。

[源码与验证清单](../evidence/glb-component-numerical-policy-2026-11-13.json) 记录精确SHA；[边界与集成测试](../../scripts/diagnostics/markingjig/test_glb_numerical_policy.py)。当前没有新增Windows/native证据；旧CI43402895583只覆盖c39dade，不能替代本改动验证。新精确包、完整launcher、实际执行与新CAD票交Root亲审，当前不自动启动。
