# 文档属性覆盖与原生验收清单

本清单基于 2026-11-06 的 main `60c6f463560b2541a17f91e0d6c5d84fe317b8bd`，
用于规划“工具 → 选项 → 文档属性”后续集中开发与验收。官方 API 有 getter/setter，
仅证明存在原生入口；公共契约、实现、持久化和用户可见行为通过前，均不标为 SWCLI 已支持。
本批新增功能在合入和原生验收前属于进行中，不能继承 A18 的完成状态。

## 已完成、进行中、未覆盖

| 范围 | 状态 | 已有公共能力和证据边界 |
| --- | --- | --- |
| 文件 → 属性：摘要、自定义属性、配置自定义属性 | 已完成的既有范围 | `document.summary` / `summary-set`、`properties`、`property-summary`、`property-add/set/delete`；摘要五字段可编辑、时间/保存人/历史只读，配置作用域明确。它们是文件元数据，不算 Options 页覆盖。 |
| 文档属性 → 单位 | 部分完成 | `document.units` 读原生五字段；`units-set` 仅已校准十进制 profile 下 mm/inch、0–8 位小数，零件/装配修改及保存重开已过公共门禁。整套 MMGS/MKS/CGS/IPS、质量/时间/角度、双单位、分数、工程图写入均未覆盖。 |
| 文档属性 → 注释 | 部分完成 | A18 七字段：三种附着场景箭头、折弯开关/长度、前导/尾随零；零件/装配/普通工程图 sheet 均已验收异值、反向箭头、同值零写、拒绝及保存只读重开。字体、子类型设置和总体标准未覆盖。 |
| 本批新增文档选项 | 代码接线进行中，原生/公共验收待完成 | 总注释字体七写字段、十项显示字段和有限标准转换已接六个CLI/MCP操作。见[本批公共契约](document-preferences-batch.md)，未发布，不继承A18验收。 |
| 其余下表类别 | 未覆盖 | API 路线及优先级是后续实施建议，不构成支持承诺。 |

现状依据：[操作目录](../../src/swcli/operation_schemas.py)、
[公共使用说明](../../src/swcli/skills/swcli/references/usage.md)、
[roadmap](../roadmap.md)、[A18 最终 Windows 回执](../verification/a18-final-windows-2026-11-06.md)。
最终回执确认继承的元数据/单位门禁通过；A17 冻结说明和旧设计中的 pending 描述是历史快照，
不能覆盖后来的最终状态。本文未重新运行 Windows、Wine 或发布核验。

## 页面级缺口矩阵

P0 是优先集中实现的明确标量；P1 是有联动或依赖的后续组；P2 需要文件、复杂原生对象、
模型行为或显示验收。优先级表示实施顺序，不表示可省略验收。P/A/D 分别为零件/装配/工程图。
官方表可能跨版本，必须在实际 SOLIDWORKS 版本和文档类型上校准；未显示的页面不能靠
enum 存在或 getter 返回默认值推定适用。

| 页面/类别 | 基线状态及文档类型 | 原生路线与剩余范围 | 优先级及验收重点 |
| --- | --- | --- | --- |
| 绘图标准 | 未覆盖；P/A/D | 总体标准是 `IModelDocExtension.Get/SetUserPreferenceInteger`；大写开关/排除列表是 Toggle/String。总体标准切换会更新各细节基础标准；自定义标准还涉及复制、命名和文件加载/导出。 | P1：独立的大写标量；P2：总体标准、`.sldstd` 文件。必须声明并比较固定关联观察profile、记录未观测边界，不能套用“只许目标字段变化”的单标量假设。[API](https://help.solidworks.com/2024/english/api/swconst/DP_DraftingStandard.htm)、[总体标准联动](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_OPTIONS_DRAFTING_STD.htm) |
| 注释及子页 | 七标量已完成；P/A/D，子页有类型差异 | Integer/Toggle/Double 可承载部分标量；字体需 `ITextFormat`；注释、气泡、基准、几何公差、位置标签、注解、修订云、表面粗糙度、焊接符号等各有 option 与子标准，不能视作七字段的自动扩展。 | P0：逐项新增明确标量；P2：字体对象与其传播。层名称需真实图层验证，尺寸零显示不可误用 `swDetailingAnnotation` 的 option。[已验收契约](document-annotation-options.md)、[注释 API](https://help.solidworks.com/2024/english/api/swconst/DP_Annotations.htm) |
| 尺寸及子页 | 未覆盖；P/A/D | 文档默认精度、双尺寸、箭头大小、延伸线/间距等多为 Integer/Double/Toggle；字体是 `ITextFormat`。角度、角向运行、弧长、倒角、直径、孔标注、线性、坐标、半径等子页分别映射。 | P0/P1：白名单标量；P2：字体、容差及更新旧规则等动作。尺寸总字体会更新各尺寸类型，单位/公差精度和分数显示需成组设计；文档默认设置不等于直接修改现有每个尺寸。[官方页面](https://help.solidworks.com/2025/english/SolidWorks/sldworks/HIDD_OPTIONS_DIMS_New.htm) |
| 虚拟交点 | 未覆盖；P/A/D | 单一 `swDetailingVirtualSharpStyle` Integer、`swDetailingVirtualSharp_e` 枚举。 | P0：明确枚举候选。验证读写/保存重开及真实虚拟交点显示；设置不包含创建虚拟交点实体。[API](https://help.solidworks.com/2025/english/api/swconst/DP_VirtualSharps.htm) |
| 表格及子页 | 未覆盖；子页类型不同 | 边框/网格线宽、零显示、部分格式为 Integer/Toggle；字体为 `ITextFormat`；层为 String。BOM、General、Bend、Hole、Punch、Revision、Title Block、Weld 分别有映射。 | P0/P1：分表类型的边框/零显示等；P2：字体、图层、修订“更新全部”语义。不得把同 enum 的不同 option 混为同字段，也不能把默认设置当编辑已有表格。[General API](https://help.solidworks.com/2025/english/api/swconst/DP_Tables-General.htm)、[Revision API](https://help.solidworks.com/2025/English/api/swconst/DP_Tables-Revision.htm) |
| DimXpert | 未覆盖；模型 DimXpert 与工程图 DimXpert 需分开 | 工程图倒角/槽/圆角方案有明确 Integer；模型尺寸、公差、链尺寸、几何公差、倒角控制、显示选项有不同子页。模型容差还依赖标准、单位及外部一般公差文件。 | P1：工程图方案标量；P2：模型容差组和文件加载。装配和零件的选项适用性不同，工程图显示不能冒充修改源模型公差。[工程图 API](https://help.solidworks.com/2024/English/api/swconst/DP_DraftingDimXpert.htm)、[模型容差](https://help.solidworks.com/2022/English/SolidWorks/sldworks/HIDD_TX_BLOCKTOL_OPTIONS.htm)、[装配 DimXpert](https://help.solidworks.com/2025/English/SolidWorks/sldworks/c_dimxpert_assemblies.htm) |
| 出详图 | 未覆盖；P/A/D 项目不同 | 注释显示、比例、自动插入中心标记/尺寸、父子视图配置、螺纹显示等有多种偏好和实际视图上下文。 | P1：明确且独立的显示默认标量；P2：视图创建时自动插入、引用部件传播与现有注释显示。使用有注释及模型视图的真实样件。[官方页面](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_OPTIONS_DETAILING.htm) |
| 网格/捕捉 | 未覆盖；P/A/D | `swGridDisplay`、`swGridAutomaticScaling` Toggle；`swGridMajorSpacing` Double（米）；`swGridMinorLinesPerMajor`、`swSnapPointsPerMinor` Integer。 | P0：上述五项可一起校准。`swGridDisplayDashed` 官方表注明不影响当前文档、只影响未来文档，不能未经验证作为当前文档标量开放。网格显示和捕捉行为需草图/工程图样件。[API](https://help.solidworks.com/2025/English/api/swconst/DP_GridSnap.htm) |
| 单位 | 长度显示部分完成；新增范围未覆盖 | `GetUnits/SetUnits` 和 Extension Integer/Toggle 等是不同入口。整套单位系统、质量/截面、角度、时间、双显示、分数及舍入分别映射；部分质量单位仅 Custom 系统可写。 | P0：整套系统与常用单位成组设计；P1：分数、双显示、舍入及工程图 profile。切换系统需完整相关设置读回，不能以长度变 mm 就宣称 MMGS。[API](https://help.solidworks.com/2025/english/api/swconst/dp_units.htm?format=P&value=)、[既有边界](document-units.md) |
| 模型显示 | 未覆盖；P/A | 文档/特征颜色、同色开关、忽略特征色、纹理缩放、卡通边宽等存在 Extension 偏好；高级外观还涉及颜色/材质数组、外观对象和显示状态；存储外观/贴图/场景涉及资源嵌入。 | P1：独立开关与有明确范围的边宽；P2：颜色优先级、外观对象、嵌入资源。零件/装配字段不同；渲染或原生显示证据单独验收。[API](https://help.solidworks.com/2024/english/api/swconst/DP_Colors.htm) |
| 图像品质 | 未覆盖；P/A/D，字段有差异 | Integer/Double/Toggle 有原生入口，偏差可查询动态范围。滑块/弦偏差相互联动；装配可对所有引用零件应用；保存 tessellation 改变显示数据。 | P2：单文档模式先独立验证。禁止默认跨引用部件写；曲面样件、线框/HLR/HLV、保存重开和显示数据是必要证据，平面盒子不足以证明品质效果。[API](https://help.solidworks.com/2023/english/api/swconst/DP_ImageQuality.htm)、[官方行为](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_OPTIONS_IMAGE_QUALITY.htm) |
| 钣金 | 未覆盖；P/A/D 选项不同 | 展平简化/成形工具显示等有偏好入口；工程图有折弯注解、引线/字体/图层/颜色；新钣金体覆盖默认参数及材料驱动具有模型后效。 | P1：经过明确映射的显示标量；P2：真实钣金/多实体/展平行为、材料和折弯注解文件。不能仅用普通零件读回验证。[官方页面](https://help.solidworks.com/2025/english/SolidWorks/Sldworks/HIDD_OPTIONS_SHEETMETAL_dpp.htm) |
| 焊件 | 未覆盖；优先实际焊件零件 | 自动切割清单、更新、派生配置、描述/重命名等默认行为会影响原生树和属性；包围框表达式、ID 还涉及结构数据。 | P1/P2：即使入口是 Toggle，也须验证切割清单、配置及属性副作用；有“派生配置→描述”依赖，不可统一独立 Set。含旧模板/新模型边界。[官方页面](https://help.solidworks.com/2022/English/SolidWorks/Sldworks/HIDD_OPTIONS_WELDMENTS.htm) |
| 基准面显示 | 未覆盖；P/A | 三项颜色为 RGB Integer，透明度 Integer 0–100，交线显示 Toggle。 | P0：五项可作为一个明确组。需检查 RGB 编码、边界与保存重开；实际显示还受阴影基准面显示开关控制。[API](https://help.solidworks.com/2024/english/api/swconst/DP_PlaneDisplay.htm)、[显示前提](https://help.solidworks.com/2025/english/solidworks/sldworks/HIDD_OPTIONS_REFPLANE_DISPLAY.htm) |
| 配置 | 未覆盖；P/A | `swRebuildSaveNewConfig`、`swDisplayDataMarkNewConfig` Toggle 是新配置默认值；较新 UI 另有新配置默认 BOM 零件号。与 A16 配置自定义属性不是同一功能。 | P0/P1：两个标记先校准并验证新建配置行为；BOM 默认单独核 API。2022 API 表注明不支持 SOLIDWORKS Connected，不能无条件套用其他产品/版本。[API](https://help.solidworks.com/2022/english/api/swconst/dp_configurations.htm)、[较新 UI](https://help.solidworks.com/2024/english/SolidWorks/sldworks/HIDD_OPTIONS_CONFIGURATIONS.htm) |
| 配合 | 未覆盖；A | 错位配合最大偏差 Double、默认错位类型 Integer 已有 API；较新 UI 另列槽配合默认约束。 | P1：明确错位选项；P2：真实配合/求解与新建配合默认效果。不能借此宣称已支持创建或编辑所有 mate；槽约束需另核映射。[API](https://help.solidworks.com/2024/english/api/swconst/DP_Mates.htm)、[UI](https://help.solidworks.com/2025/English/SolidWorks/sldworks/r_document_properties_mates.htm) |

## 文档类型不能遗漏的页面

上述十六类对应本次截图范围。完整三种文档的 Options 范围还包含：
工程图 Borders、Centerlines/Center Marks、Views（Auxiliary/Detail/Section/Orthographic/Other）、
Drawing Sheets、Line Font、Line Style、Line Thickness、Performance；零件 Material Properties、
Sheet Metal MBD；以及各大类的全部子页。这些均未由 A16–A18 覆盖。
具体可见项以目标版本与文档类型为准，不将一张零件/装配截图作为完整工程图清单。
[官方 API 导航](https://help.solidworks.com/2024/English/api/sldworksapiprogguide/overview/System_Options_and_Document_Properties.htm)、
[文档属性类型差异](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_document_properties.htm)。

## 本批可合并范围建议

集中一批可以包含多组已明确字段，但仍采用按字段显式白名单的公共目录：
每条记录固定 key、文档类型、API family、preference、option、公共单位、枚举/范围、
版本/依赖、关联读回字段与官方来源。用户不能直接传任意原生 preference ID 或 option。
Integer/Double/Toggle/String 只是调用机制，不能据此承诺页面级安全。

1. 优先集中虚拟交点、五项网格/捕捉、五项基准面显示，以及已核对的尺寸/表格独立标量。
   配置默认标记和配合默认设置可以同批开发，新增配置/配合行为须有自己的样件。
2. 单位系统应作为相关单位整体读回与守护的专门组；工程图、分数和 Custom 限制分别验证。
   已有长度操作继续保留，避免两个入口静默互相覆盖而公共结果不解释。
3. 字体对象、总体标准/文件、层名称、钣金/焊件后效、图像品质及引用传播可以同批设计，
   但只有对应原生验证通过的范围才能启用公共写入。未完成项保留明确 unsupported/未覆盖状态。

这些是选型建议；最终批次清单应以实际实现字段目录及验收回执为准，不把建议计为已实现。

## 每组共同验收与完成条件

- 公共请求/结果 schema、CLI/MCP 路由、capabilities/字段目录一致；可读原生未知值保留，未知值不自动进入写域。
- 文档类型、版本、只读、活动草图/工程图上下文、session/lease/stamp 与字段 CAS 在首次 setter 前检查；
  同值零 setter，失败即停止，不重试、不声称自动回滚、不隐式保存。
- 每次成功修改验证目标字段及所有已声明关联字段；独立字段应保持未请求字段，联动字段则按明确契约验证预期变化。
  setter 可能不推进 stamp/dirty，应校准并保留实际证据，不能以 stamp 代替字段 CAS。
- 每个适用文档类型通过安装后的公共 CLI：异值、边界/双向枚举、无变化、拒绝路径、背景文档/配置保持；
  修改后另存副本、关闭、fresh ID 只读重开，读回改变值，核输入 hash 不变、几何与上下文及宿主清理。
- 默认行为通过真实新建目标对象验证；字体/标准通过关联子设置及注释样件；图像/外观通过适当曲面与原生显示/渲染验证；
  钣金/焊件/配合分别通过原生展平/切割清单/求解。getter 等于 setter 请求不是这些后效的充分证明。
- 最终矩阵逐项列出“代码已实现 / 本地便携验证 / Windows 原生验收 / Wine 交付验证 / 发布”状态和证据来源。
  文档支持只针对明确字段；未完成页面和子项继续列出，直到相应门禁通过。

系统选项存储与文档选项不同；本操作仅面向目标打开文档及明确授权的后效，不调用
`ISldWorks.SetUserPreference*` 修改全局系统偏好。
[官方选项范围说明](https://help.solidworks.com/2025/english/SolidWorks/sldworks/r_overview_of_solidworks_options.htm)。
