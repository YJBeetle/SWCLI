# 文档显示选项十字段草案

状态：**schema、CLI 和 daemon 已接线，read-r1 只读观测通过；本批原生及公共验收仍未完成**。
操作为 `document.display-options` 和 `document.display-option-set`，固定为下列
十字段；CLI 写入要求 stamp、lease 和 `--if-value` 类型化旧值。公共请求不接受
原生 preference ID、option 或注入映射。本目录不代表页面级支持，接线不代表
原生写入/保存重开、视觉效果、公共门禁、CI、Wine 或新版本发布已通过。

所有 `preference` 数值已按 read-r1 的目标安装版 SOLIDWORKS 2025 swconst
导出填写，option 固定为 0；数值和三类 getter 的证据见下节，不从文档顺序猜 ID。
配置缺失或无效时仍 fail closed，不调用偏好 getter/setter。
私有 `_preference_ids` 只为测试和校准集成保留：必须提供完整十个固定原生符号
的 Int32 非负映射，同一 API family/option 下不得重复；校验映射结构不证明
数值正确。便携测试使用已导出的实际 ID 和模拟数据，另离线重放 read-r1
观察值检查单位换算；这些测试不构成新的原生调用或写入证据。

## 字段目录

| 顺序 | field | 原生符号 / family | 候选值 | 文档类型 |
| --- | --- | --- | --- | --- |
| 1 | `grid.display` | `swGridDisplay` / Toggle 57 | 严格 boolean | P/A/D |
| 2 | `grid.major_spacing_mm` | `swGridMajorSpacing` / Double 30 | 正有限毫米数，写入时除 1000 转米 | P/A/D |
| 3 | `grid.minor_lines_per_major` | `swGridMinorLinesPerMajor` / Integer 42 | 正 Int32；真实可接受范围待校准 | P/A/D |
| 4 | `grid.snap_points_per_minor` | `swSnapPointsPerMinor` / Integer 43 | 正 Int32；真实可接受范围待校准 | P/A/D |
| 5 | `virtual_sharp.style` | `swDetailingVirtualSharpStyle` / Integer 41 | `none` / `plus` / `star` / `witness` / `dot` | P/A/D |
| 6 | `plane.front_face_color` | `swPlaneDisplayFrontFaceColor` / Integer 145 | 候选 0–0xFFFFFF 原生整数，不转换 RGB | P/A |
| 7 | `plane.back_face_color` | `swPlaneDisplayBackFaceColor` / Integer 146 | 同上 | P/A |
| 8 | `plane.intersection_line_color` | `swPlaneDisplayIntersectionLineColor` / Integer 148 | 同上 | P/A |
| 9 | `plane.transparency` | `swPlaneDisplayTransparency` / Integer 147 | 0–100 整数 | P/A |
| 10 | `plane.show_intersections` | `swPlaneDisplayShowIntersections` / Toggle 138 | 严格 boolean | P/A |

P/A/D 指零件/装配/工程图。工程图仅读取前五项候选，写入基准面五字段连同
同值请求也在偏好 getter/setter 之前拒绝。read-r1 已取得前五项在工程图中的
真实 getter 返回；其写入、持久化和用户可见行为仍待验收。

原生路线来自官方
[Grid/Snap](https://help.solidworks.com/2025/English/api/swconst/DP_GridSnap.htm)、
[Virtual Sharps](https://help.solidworks.com/2025/english/api/swconst/DP_VirtualSharps.htm)、
[Plane Display](https://help.solidworks.com/2024/english/api/swconst/DP_PlaneDisplay.htm)。
[虚拟交点枚举](https://help.solidworks.com/2024/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDetailingVirtualSharp_e.html?id=2.10.1.261)
为 none=0、plus=1、star=2、witness=3、dot=4。
该设置控制显示，不创建虚拟交点实体。
颜色尚未校准 COLORREF 字节序、特殊值及规范化行为；内部整数候选不能当作
`#RRGGBB`。透明度和网格计数的验证仅是输入约束，不承诺原生接受整个区间。

`swGridDisplayDashed` 官方说明只影响未来文档，本批明确排除；
`swGridAutomaticScaling` 不在本次指定十字段内，也不额外扩入目录。
网格自动缩放可能影响实际主间距行为，需要校准时作为关联观察，不能静默
修改额外 preference 来使请求“成功”。

## 内部读写与保护契约

Windows 适配函数为 `read_document_display_options_windows` 和
`set_document_display_option_windows(field, value, expected_value)`，action 已接线为
`document.display-options` / `document.display-option-set`。每个观察字段为
`{value, native_value}`：米换算为毫米；虚拟交点未知枚举返回 `other` 并保留
原始整数，但未知枚举不进入写参数或 CAS 域。其他 Integer 的原生 Int32
即使超出候选写域仍可读、可作精确 CAS 前值，不因此放宽目标写域。

公共 operation 层先完成 document/session/lease/update-stamp
校验；adapter 不管理租约。adapter 复用 A18 编辑上下文和 metadata/foreground
保护，拒绝 readonly/view-only；后台文档不激活、不改变当前文档或配置。
模型存在活动草图时拒绝异值写；工程图异值写需普通 sheet 上下文，拒绝格式、
视图、外来/缺失草图。状态检查通过的同值请求不调用 setter 或 SetSaveFlag。

单字段 CAS 在第一次 setter 前检查，观察旧值使用精确数值相等：Double
允许等值 JSON integer/number（例如 100 与 100.0），但不允许 boolean 冒充；
其余字段要求类型和值都一致。相邻浮点数的旧值也判为冲突，即使 stamp 不变，
即使目标本身是同值，也不能跳过该完整旧值检查。只有请求目标的实际读回和
目标同值判断保留 `rel_tol=1e-12, abs_tol=1e-12` 的表示容差。
此为公共 adapter 的收紧，冻结的私有显示校准源码快照保持不变；公共最终 CI
仍需单独验证，不能据此改写原生回执。
写入固定文档 Extension 的固定 API family/preference/option，严格只尝试一次，
setter 前即记录 `mutation.attempted=true` / `may_have_changed=true`。
原生返回必须严格为 True；False、非 boolean 或异常均首失败返回，不重试、
不回滚、不调用全局应用偏好、不隐式保存或重建。

写后完整读回该文档类型全部候选字段，目标值必须匹配；未请求字段的
`value` 和 `native_value` 均必须保持。模型十项、工程图五项，成功改变各读取
三轮。post-setter getter 必须保持其开始时的 stamp/dirty/context；如需标脏，
最多 SetSaveFlag 一次，再完整读回并检查 post-write state。读阶段出现漂移
直接失败，不能再次标脏掩盖。每个偏好 getter/setter 有独立扁平 native trace
边界；失败返回 mutation，并在已取得时保留 `observed_options`。

当前未请求字段保护只覆盖本目录，不把它说成整个文档属性完全无副作用。
标准、注释、单位、字体及可见行为还需原生关联观察。

## 原生校准和公共验收要求

1. read-r1 已从目标 installed swconst 导出十个精确符号的数值和 family，
   记录版本、导出来源、hash，并读回 P/A 十项、D 五项。该只读步骤不代替下述写入门禁。
2. P/A 全十项、D 前五项依次基线读、每字段异值单次 Set、完整读回，
   记录返回类型和值、dirty/stamp、配置/sheet/foreground、未请求字段；
   网格计数边界及 spacing 与自动缩放的实际联动单独报告。
3. 用区分三个通道的非对称颜色确认编码、前后面和交线映射；确认透明度
   0/100。检查[阴影基准面显示前提](https://help.solidworks.com/2025/english/solidworks/sldworks/HIDD_OPTIONS_REFPLANE_DISPLAY.htm)，
   不因 getter 匹配就声称实际显示已经生效。
4. 保存每组实际改变值到新副本、关闭、fresh document ID 只读重开，
   核改变值、clean、源 baseline hash 不变、几何及宿主清理；不能只保存
   已恢复到初值的最终状态而宣称所有中间改变持久化。
5. 安装版公共 daemon/CLI 验证 lease/stamp/readonly/单字段 CAS、后台当前
   文档保持、同值零 setter / 零 SetSaveFlag，request ID 对应真实 trace；
   另用有网格/捕捉、虚拟交点、基准面交线的实际样件验证用户可见行为。

沿用请求 600 秒 / 组 1800 秒预算，首失败保留原证据，不重试原生调用、
不回滚或拓宽预算。本模块的开发和离线测试未启动额外原生宿主或 CI；
下节只记录已有 read-r1 原件，不重放原生请求。

## read-r1 原生只读证据

2026-11-06，Windows SOLIDWORKS 2025 revision `33.5.0`，连接用户已打开的
PID 2940；阶段 `read`，success=true、full_acceptance_eligible=false。
零件/装配取得全部十项，工程图取得前五项；各 case writes=[]、
no_preference_setters=true。该轮创建并保存了独立基线样件，不等于改变选项值
保存重开。原件报告记录源模板/typelib/基线文件 hash、原文档身份保持和测试文档
清理；host start/exit、visibility setter、global preference setter 均为 0，
用户原生宿主仍运行。这里不把该私有诊断称为公共 CLI 验收。

原始观察的 `grid.major_spacing_mm` key 实际存放 API 原始米值 **0.1**；
本模块规范化返回 **100.0 mm**，不得照原报告的 key 名误当 0.1 mm。
三类均为 grid.display=false、minor=4、snap=1、virtual sharp native=3（witness）。
P/A 的前面/后面/交线颜色原始整数分别为 33023/16512/0，透明度 95，
show intersections=true。只有原始整数读取成立，RGB 字节序、视觉效果及任何
颜色/透明度改变尚未证明。

- 原件目录：`/private/tmp/docprops-batch-read-r1`
- `report.json` SHA-256：`57b41f4539f1a7c15878987eb5b1ac9bc8dd59138c22b003e1aa40724bd62eea`
- `swconst-enums.json` SHA-256：`a526d78c856b3efa294c1a5379ee23cec09334fd23ef27c7dcb42784a4751eec`
- installed `swconst.tlb` SHA-256：`95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`

## 便携测试边界

`tests/test_document_display_options.py` 用已导出 ID 和纯 Python 对象验证
十字段顺序、未配置 fail closed、映射限制、适用类型、所有字段单 setter、
enum/boolean 两方向、输入类型/有限值、CAS/同值、未知值保留、只读与绘图
保护、未请求字段保持、各读取阶段漂移、单次失败 partial mutation、扁平
getter→setter→getter→getter 顺序。它不证明官方数值映射、SOLIDWORKS 原生
行为、保存重开、公共权限或真实显示效果。
