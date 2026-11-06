# 文档注释字体（开发中）

状态：**schema、CLI 和 daemon 已接线，本批原生及公共验收仍进行中**。
操作为 `document.annotation-font` 和 `document.annotation-font-set`，与完整
catalog/snapshot/Windows adapter 及便携测试相连；CLI 写入要求 stamp、lease
和 `--if-font` 完整 17 字段 JSON。接线不代表整组原生验收或发布完成。
read-r1 只读观测和 fonts-r1 首失败证据按下文保留；本文件尚未记录 fonts-r2
三类全组通过结论，也未声明本批公共 CLI 门禁、CI、Wine 交付或新版本发布通过。

目标是文档注释总字体 `swDetailingAnnotationTextFormat`，preference 19、option 0，
不是应用全局字体，也不是字体安装服务。A18 私有只读观测已取得零件、装配、
工程图三类各完整 17 个成员，但没有调用字体 setter；该证据不证明字体可写、
子字体独立或改变值持久化。

## 官方接口和仍待证明的语义

[GetUserPreferenceTextFormat](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~GetUserPreferenceTextFormat.html)
取得文档默认文本格式对象。
[SetUserPreferenceTextFormat](https://help.solidworks.com/2020/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SetUserPreferenceTextFormat.html)
接受该对象并以 boolean 表示设置成功。官方
[Get and Set User Preferences 示例](https://help.solidworks.com/2019/english/api/sldworksapi/Get_and_Set_User_Preferences_Example_VBNET.htm)
使用 Get → 改对象属性 → Set 的顺序；没有保证返回对象是 detached copy，
也没有保证赋值前后文档状态不变、仅 final Set 才提交或对子类型无联动。

[CharHeight](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat~CharHeight.html)
的单位是米；公共候选字段用毫米换算。
[CharHeightInPts](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat~CharHeightInPts.html)
是整数磅值。
[IsHeightSpecifiedInPts](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat~IsHeightSpecifiedInPts.html?format=P&value=)
是只读方法：以 CharHeight 写高度后为 false，以 CharHeightInPts 写后为 true。
不能赋值该方法，也不能同时写两种高度而意外覆盖调用者选择的模式。

## 候选字段和完整快照

读取同时返回完整 `font` 和完整 `native_font`，不输出 COM 对象。

| font 字段 | native_font 成员 | 候选写入 |
| --- | --- | --- |
| `typeface` | `TypeFaceName` | 非空、首尾无空白且不含控制字符的字体名；不推断已安装 |
| `height_mm` | `CharHeight`（米） | 正有限毫米数，米换算不下溢；显式选择毫米模式 |
| `height_points` | `CharHeightInPts`（Int32） | 正整数磅值；显式选择磅值模式 |
| `height_mode` | `IsHeightSpecifiedInPts` | 只读 `millimeters` / `points` |
| `bold` / `italic` / `underline` / `strikeout` | `Bold` / `Italic` / `Underline` / `Strikeout` | 严格 boolean |
| `backwards` / `upside_down` / `vertical` | `BackWards` / `UpsideDown` / `Vertical` | 只读严格 boolean |
| `width_factor` / `char_spacing_factor` | `WidthFactor` / `CharSpacingFactor` | 只读有限数 |
| `escapement` / `line_spacing` / `line_length` / `oblique_angle` | `Escapement` / `LineSpacing` / `LineLength` / `ObliqueAngle` | 只读有限数，保留原生单位 |

`expected_font` 必须提供恰好全部 17 个规范字段，严格拒绝 bool 冒充数值、
小数冒充整数磅值、NaN/Infinity、缺失和多余字段。非活动的整数磅表示允许 0，
以保留原生截断结果；磅值模式下必须为正。读快照保留未知但可读的字体名，
不据此放宽新字体名写参数。

完整 CAS 使用数值精确相等；未请求成员变化也使请求失败，微小高度变化不被
容差吞掉。请求高度的实际读回匹配才使用 `rel_tol=1e-12, abs_tol=1e-12`。
同值判断同时比较高度模式，因此毫米模式下请求与备用磅值相等的
`height_points` 仍是显式模式变更。

## 保护和失败边界

公共 operation 层先保证 document/session/lease/update-stamp；adapter
本身不管理租约，不能据其便携测试声称公共 lease/stamp 已验收。
adapter 复用 A18 的编辑上下文和文档 metadata/foreground 保护。
只读/view-only 先拒绝；完整 CAS 和状态检查通过后的同值请求不赋属性、不调用
文本格式 Set，也不标脏。异值请求只赋所选的一个 ITextFormat 属性，
不重建对象、不重新赋全部属性，不触碰全局应用偏好。

第一次属性赋值前就设置 `mutation.attempted=true` 和
`may_have_changed=true`。即使属性赋值异常或 final Set 尚未调用，也可能是
partial mutation。赋值后的配置、前台或编辑上下文漂移在 final Set 前失败；
不重试、不回滚、不激活文档、不修复上下文。字体属性本身的 stamp/dirty
变化作为写阶段状态保留，仍须校准真实语义。

final Set 必须严格返回 True，随后重新 Get 全 17 字段。请求值和目标高度模式
必须读回一致。非高度写入必须严格保留原模式和该模式的生效高度：millimeters
模式是原生 CharHeight，points 模式是原生 CharHeightInPts；比较原生 type/value，
不以毫米规范化或容差隐藏生效高度变化。除目标成员外，仅备用高度表示可以
发生原生规范化，其余成员一律严格保持；不因此允许模式翻转、改高度或改宽度等。
高度写入允许高度三元组 `height_mm` / `height_points` / `height_mode` 联动，
其余 14 字段严格保持。任何实际请求仍须目标值和明确高度模式匹配。

成功 set 结果必有 `native_normalizations` 数组，无规范化和同值请求返回 `[]`。
每个条目严格为 `{member, before, after, reason}`，member 仅 CharHeight 或
CharHeightInPts，reason 固定 `inactive-height-representation`，最多一项。
成员 before/after 使用实际原生值，不重算或猜测它；若后续保护失败，已取得的
该数组可随失败保留，但不构成成功。完整 before/native_before、font/native_font
均保留所有 17 字段；旧值 CAS 仍包含备用高度，同值请求也必须通过完整 CAS。
标脏后的最终完整 raw 快照必须与首次读回完全相等，不能持续放宽备用高度变化。
保存/只读重开的校准也必须比较完整 raw 快照，不跳过备用表示。
高度换算精度、字体度量原因仍待证明，不用数学模拟结果宣称真实原生转换。

共享纯函数 `annotation_font_native_normalizations(before_native17, after_native17, member)`
只校验上述副作用并返回数组，违反约束抛 ValueError。它也供 final Set 前的独立
Get 复用，因此高度写入的旧模式不由此函数拒绝；caller 在 final Set 后另以
requested matcher 强制目标值和模式。独立 Get 的 live 判断须看有效目标是否
已可见，备用表示单独变化不能被归类为目标已生效。
首次读回严格保持 post-setter state，标脏最多一次后再读完整快照并验证
post-write state。读阶段造成 stamp/dirty/configuration/foreground/context 变化
即失败，不再次 SetSaveFlag 掩盖。

每个 Get、ITextFormat 成员读取、所选属性赋值和 final Set 均有独立的扁平
native trace 边界。失败保留 mutation 和已经取得的 observed_font；
不自动保存或重建文档。

当前 adapter **只核注释总字体内的未请求成员**，没有声称其他 font preference
或注释子类型保持。公共写入开放之前必须先解决下述联动问题。

## 原生校准必须回答的问题

1. 对三类独立样件，Get 返回对象的属性赋值是否立即改变再次 Get 的结果、
   dirty、stamp？单独赋值和 final Set 的作用分别是什么？即使 setter 失败，
   已赋值的属性是否保留？须按属性写、再观测、final Set、再观测记录真实 trace，
   不能只记录 final Set。
2. 每个候选字段写异值、boolean 两方向、毫米/磅值两方向模式切换时，
   返回类型和值、17 字段读回及备用高度舍入分别是什么？不合法/不存在字体名
   是否替换、拒绝或规范化？规范化不能默认为成功。
3. 注释总字体修改是否联动尺寸、注释子类、独立字体 override、总体/子绘图
   标准及 A18 七字段？先从 installed typelib/官方 enum 明确完整观察范围，
   然后前后对照；未知联动不得当作单字段独立支持。
4. 每类样件各次改变值保存、关闭、以 fresh readonly document ID 重开后，
   总字体、字体模式、子类型/override 和几何是否保持？源 baseline 字节不变。
   只最终保存一次不能证明中途改变后又恢复的字段持久化。
5. 安装版公共 daemon/CLI 是否满足 full snapshot CAS（包括非目标成员）、
   session/lease/stamp、readonly、后台文档与当前文档保持，以及同值零属性赋值 /
   零 final Set / 零 SetSaveFlag？必须用实际 request ID 对应 trace 证明，
   不能从 mutation 回执或便携测试推断。

按已有 600 秒请求 / 1800 秒组预算执行单次原生调用，首失败保存原证据并停止。
不重试原生 API、不回滚、不拓宽预算、不调度额外宿主或 CI 来替代缺失证据。

## read-r1 的新增只读观测

2026-11-06，SOLIDWORKS 2025 revision `33.5.0`、用户既有 PID 2940，
read-r1 在零件/装配/工程图分别取得注释总字体完整 17 成员。三类均为
TypeFaceName=`汉仪长仿宋体`、CharHeight=0.0035 米（3.5 mm）、备用
CharHeightInPts=12、IsHeightSpecifiedInPts=false（毫米模式）。四种样式和
BackWards/UpsideDown/Vertical 均为 false，WidthFactor/CharSpacingFactor=1.0，
Escapement/LineLength/ObliqueAngle=0，LineSpacing=0.0015。
这只证明这三份样件的总字体可读；字体安装、属性赋值是否 live、final Set、
字体子类型传播、改变值保存重开及公共 CLI 均未由该只读阶段证明。

原件 `/private/tmp/docprops-batch-read-r1/report.json` 的 SHA-256 为
`57b41f4539f1a7c15878987eb5b1ac9bc8dd59138c22b003e1aa40724bd62eea`。
报告 stage=read、success=true、full_acceptance_eligible=false，各 case writes=[]，
没有偏好 setter；用户宿主保持运行。独立基线 SaveAs 不能当成字体改变值持久化证据。

## fonts-r1 首失败与针对性契约修正

2026-11-06 私有 fonts-r1 在首个 part 的 TypeFaceName 写入后失败，整体仍为
failed、full_acceptance_eligible=false；display 阶段未执行。原件不改写、不按新
规则回标 success。实际执行源包的脚本 SHA-256 为
`21905da7201d281398dbf8991ff7a116cc5bceefd0deacbbe90255829081649e`。

精确时序为：Typeface 属性赋值一次 → 独立 Get 完整结果仍为 before →
final Set 一次返回 True → 独立 after Get。after 只出现两项差异：
TypeFaceName 从汉仪长仿宋体变 Arial，备用 CharHeightInPts 从 12 变 14；
CharHeight 始终 0.0035 米、IsHeightSpecifiedInPts 始终 false，其余 15 成员
保持。各阶段 state 均为 `[1,144,false,默认]`。这说明本次目标赋值在 final Set
前未由独立 Get 观察到；不推广为所有字体属性永远 detached。

旧 `font_unrequested` 把备用磅表示变化也视作无关字段变化，因而阻断。官方
IsHeightSpecifiedInPts 允许区分当前指定模式，但没有承诺两种 getter 的固定
换算或字体名改变后备用表示不变。新契约将此类差异作为明确输出的备用表示
规范化，继续严格保护生效高度、模式和其他成员；不声称 12→14 的字体度量
原因已证明，也不采用 mm↔pt 公式修复原生对象。

trace 有 474 个完整 begin/terminal 对，无原生 call exception 终点；契约失败
发生在校验行，仍是失败。没有 SetSaveFlag 或改变值保存，只有两个基线 SaveAs，
因此不证明任何改变值持久化。cleanup_errors=[]，原文档目录、visibility
保持，用户 PID 2940 仍运行；无 host start/exit 或 visibility setter。

- 原件目录：`/private/tmp/docprops-batch-fonts-r1`
- `report.json` SHA-256：`2cdf2603bf787c87c87ccc7b3de835885a599106b21bc5542ca7ee170b826c1e`
- `trace.jsonl` SHA-256：`5a4f8f5b7908c392b81bc455ec512437ff7c910b2e6bffe24a82b4947abbc066`
- source ZIP：`/private/tmp/docprops-batch-write-source-r2.zip`
- source ZIP SHA-256：`ad8bcee045a9be3a7d8bba66d7d9d1aa543d3128878f55dab7d8880a0ceb9592`

该针对性修复经便携测试后仍须新的差异化原生组验证，不无差异重跑，不用
failed 原件或源码修改替代新调用回执。

## 便携验证

`tests/test_document_annotation_fonts.py` 使用纯 Python 对象模拟 detached/live
两种可能语义，验证 snapshot/types、完整 CAS、7 字段单属性写入、模式切换、
同值、readonly、绘图保护、每阶段状态漂移、属性异常、final Set 首失败、
未请求成员变化、标脏末次读取和扁平字体调用 trace。
新增规范化测试离线重放 fonts-r1 的毫米模式 12→14，及合成 points 模式备用
米值变化；拒绝全部其他成员、生效高度或模式变化，包含毫米乘算舍入会隐藏的
原生微小生效高度变化。还验证旧备用高度 CAS 拒绝且零写、noop 的空数组、
标脏后备用表示再次漂移失败，以及 detached 高度 probe 旧模式允许但 final
目标模式仍必须匹配。这些测试只证明控制代码，不证明新增原生行为、公共接线或持久化。
