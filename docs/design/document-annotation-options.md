# A18 文档注释标量选项

A18 开发候选在 A17 长度显示选项之上，增加 `document.annotation-options`
只读列举和 `document.annotation-option-set` 单字段写入。它对应
“选项 → 文档属性 → 注释”的一个有限子集，不代表整个页面、全部文档选项或字体已开放。

| field | 公共值 | 文档级原生 API / swconst |
| --- | --- | --- |
| `arrow.edge_vertex` | 写 `closed` / `dot`；读保留其他原生样式 | Integer preference 38、option 0，`swDetailingArrowStyleForEdgeVertexAttachment` |
| `arrow.face_surface` | 写 `closed` / `dot` | Integer 39、option 0，`swDetailingArrowStyleForFaceAttachment` |
| `arrow.unattached` | 写 `closed` / `none` | Integer 40、option 0，`swDetailingArrowStyleForUnattached` |
| `bent_leader.enabled` | boolean | Toggle 375、option 0，`swDetailingAnnotationUseBentLeaders` |
| `bent_leader.length_mm` | 正有限毫米数 | Double 113、option 0，`swDetailingAnnotationBentLeaderLength`；原生米与公共毫米相互换算 |
| `zero.leading` | `standard` / `show` / `remove` | Integer 265、option 100 (`swDetailingAnnotation`)，`swDetailingLeadingZero` |
| `zero.trailing` | `show` / `remove` / `remove_only_on_zero` / `same_as_source` | Integer 15、option 100，`swDetailingDimTrailingZero` |

每个读回字段为 `{value, native_value}`，枚举保留原始整数；未认识的原生枚举
返回 `value="other"`，不据此开放写入。尾随零的已废弃 enum 0/3 和其他
preference option 使用的 6/7/8 不进入写入域。箭头的可读枚举表比写入域宽，
不能把 enum 存在解释成三种附着场景都已验证可写。

字段映射来自官方 [DP Annotations](https://help.solidworks.com/2024/english/api/swconst/DP_Annotations.htm)，
枚举来自 [ArrowStyle](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swArrowStyle_e.html)、
[LeadingZero](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDetailingLeadingZero_e.html)、
[DimTrailingZero](https://help.solidworks.com/2025/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swDetailingDimTrailingZero_e.html)。
[原生单位约定](https://help.solidworks.com/2024/english/api/sldworksapiprogguide/Overview/Units.htm)为米/弧度。

## 写入和失败契约

只调用目标文档 `IModelDocExtension.Get/SetUserPreferenceInteger/Toggle/Double`，
没有 `ISldWorks` 全局系统偏好 setter。写入继承 document/session/lease/update-stamp
约束，另强制提供 `expected_value`（CLI `--if-value`）比较所选字段的旧值。
已校准的原生 setter 不改变 update stamp，故 stamp 不能代替字段旧值比较。

先读取七字段、文档类型/stamp/dirty/configuration、foreground 和 active sketch 身份。
写入仅限可写文档，存在活动草图时不更改字段；同值请求在状态检查后成功返回
`changed=false`，不调用 setter/SetSaveFlag。单次更改前将
`mutation.attempted` 与 `may_have_changed` 置 true；原生失败不重试、不回滚。
成功后立即完整读回七字段，验证请求值及未请求字段保持，再检查原生上下文。

Windows 2025 校准中 Integer、Double、Toggle（包含设置 false）均返回 True。
False 或非 bool 不视为成功，不用再次调用去“确认”。公开适配器采用此已证实行为，
不从目标值 false 推导 native 调用失败，也不把官方 Toggle 返回值描述的歧义隐去。
另参见 [SetUserPreferenceToggle](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SetUserPreferenceToggle.html)。

校准中 setter 后 dirty 仍为 false；公共适配器成功更改后调用文档 SetSaveFlag，
检查 dirty=true、上下文保持，并再次核对七字段。setter 后首次读回严格保持
post-setter state；标脏后末次读回严格保持 post-write state 和草图身份。
只读回阶段的 dirty/stamp/草图变化失败，不再次 SetSaveFlag 掩盖。
它不会隐式保存或重建，调用者需
显式 `document save` / `save-as`。失败响应保留 mutation 标记，表示打开的文档可能已改变。
长度的数值预检只验证正有限与米换算不下溢，不据两个校准值推定整个原生范围均可写；
每个实际请求仍须单次 native 成功和读回一致，原生不接受的值首失败停止。
毫米长度的预期值/读回比较使用 `rel_tol=1e-12, abs_tol=1e-12`，同值判断也采用这一容差。

## 私有原生校准证据（不是公共 CLI 验收）

2026-11-06 本地 Windows SOLIDWORKS 2025：单次 owned hidden PID 5160，
33.396 秒，同宿主依次新建零件、装配、工程图（真实 `gb_a4.drwdot` 模板）。
每类 14 次原生 setter，每次后读回七字段并检查其他字段未变；零件40×30×10毫米
实体的体积保持12000 mm³。每类另存新原生文件、关闭、只读重开、再次读取七字段，
检查 clean、源 baseline hash 不变。SetSaveFlag 前后 stamp 相同，dirty false→true。
各类字体 ITextFormat 全字段和总体标准只观测且保持；未调用字体/标准 setter。
前后原生进程为空、仅退出自有宿主一次、cleanup=[]。

重要边界：每类只有**最终一次保存重开**。箭头三字段和尾随零最终值不同于初值，
已证明这些改变后的持久化；水平折弯开关、长度、引头零在中间改变并读回后又恢复原值，
所以仅证明中间读回和最终恢复值重开，尚未证明其改变值保存重开。私有脚本同值分支
零 setter 是 harness 控制证据，不冒充公共 CLI 同值证明。三种箭头仅分别调用过
edge→dot、face→closed、unattached→none；白名单中的反向 edge→closed、face→dot、
unattached→closed 仍待公共门禁覆盖，不能把原生初始值当成反向 setter 证明。

- guest 原证据：`C:\Workspace\SWCLI-tests\a18-annotations-20261106-c197`
- Mac 原件：`/private/tmp/a18-annotations-native/evidence-c197`
- `report.json` SHA-256 `5cdf06db6d8d6b6ac6a0b3de8de09e8eb0e492d4630722ed9c2f3fcc2e714b42`
- `trace.jsonl` SHA-256 `03c54a0f6e53345996cd3015c5593cc911e6074c81013d4cf2e4ee63bcdcf8b4`
- 独立审计：`/private/tmp/a18-annotations-native/audit_calibration.py`，`/private/tmp/a18-annotations-native/audit-output.json` 明确 `full_acceptance_eligible=false`
- 保存零件 SHA-256 `f8034ac19ce17355958d0a5493edf1ac3f246da8960507352f32d03b9961140d`
- 保存装配 SHA-256 `45782dfbfc9fadb8919b80556dc8dc38217266be963dd07c71082a02e1bbdf34`
- 保存工程图 SHA-256 `93e0d34cf9aae07fe5c9f45bb2abf19920de5e91e48c3fdcba7d8432df82c036`

## 后续公共门禁（待完成）

同 owned 隐藏宿主，通过已安装的公共 daemon/CLI 对三类样件执行：读七字段、
每字段改为异值、旧值冲突/lease/stamp/readonly 拒绝、后台/session 当前文档保持、
同值零写入；补齐三种箭头白名单反向 setter，且各自改变后保存重开。
**使七字段均为相对初始的改变值再保存、关闭、只读重开**。核 fresh document IDs、
原文件 hash 不变、新文件 hash/size、读回七字段、零件解析几何、clean、宿主/清理。
须有实际公共回执后才标记已验收，不用本私有报告替代，也不额外建立手动 CI 校准。

注释字体需要 ITextFormat 原生对象，且可能联动各注释子类型；总体绘图标准也会
联动子标准。两者本阶段均不开放写入，另行设计和原生验证后再扩展。
