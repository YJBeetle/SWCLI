# 工程图创建与标准三视图：最小切片

状态：**a11 开发版已接入命令，Windows／DockerSW 已有通过证据，尚未发布**。
2026-10-25 用户确认 Mac CI 仅软件渲染，并同意将复杂样例超时列为 a11 非阻塞已知 CI 限制；
保留失败证据与 Mac 平台集成／轻量冒烟检查，不宣称 Mac 完整门禁通过。
详见[当前验收记录](../verification/a11-runtime-2026-10-25.md)。a10 圆角发布不包含本能力。
Windows PRT 的第一角与显式第三角创建、视图引用、保存重开及源状态保护已校准，
见[原生记录](../verification/drawing-native-windows-2026-10-23.md)。当前验证的投影
切换路径是 `ISheet.SetProperties2`，不是尚未验证的 `SetupSheet6`。
目标是从已保存的 PRT/ASM 生成可编辑的 SLDDRW，再保存重开、导出 PDF/DWG；
不是截图拼图，也不是自动出完整制造图。所有公开动作仍通过 daemon 单 STA worker。

## 当前契约

分成两个可组合动作，而不是自动保存/导出的巨型命令：

- 扩展 `document.create`：`type: drawing`，必须显式提供现存非空 `.DRWDOT`
  `template` 和 `projection: first-angle | third-angle`。不猜地区、不弹模板 UI，
  不接受把 `.SLDDRT` 图纸格式当作工程图模板。
- 新增 `drawing.standard-views`：目标为明确选择的 drawing，参数为
  `source_document_id` 与必填、非空 `configuration`。只往单张、尚无模型视图的
  图纸插入一次原生标准三视图，使用创建时明确设定并回读的投影方式。

上述名称已在 operation catalog、schema 和 CLI 接入。创建只更新调用 session current；
`NewDocument` 返回的精确对象须立即登记，不再从 ActiveDoc 反查。
视图操作使用现有目标选择、租约、CAS、临时激活与前台恢复约定。
创建成功后后续检查失败仍登记文档并返回已取得证据；不声称事务或自动回滚。

源必须是同一 worker 已登记、已加载、路径存在的 PRT/ASM，已保存、无需重建且
无重建错误；状态不可读即拒绝，不把未知当 clean。指定配置必须存在。
首版优先要求它与源当前活动且已保存配置一致，**不隐式切换、重建或保存源模型**。
若后续校准证明可直接可靠指定其他配置，再单独放宽，不先承诺。
对源只读不修改；记录操作前后路径、配置、modified、needs_rebuild 与 update stamp，
变化即报告验证失败，不能悄悄接受源污染。

目标须可写、非 view-only，正常图纸编辑模式，单 sheet 且无已有模型视图；
首版不修改既有工程图，不自动退出用户草图/格式编辑。模板自带模型视图或多 sheet
应在插入前明确拒绝，保留新建文档供检查。不删除模板内容来凑空图。
源租约若由其他会话持有，应避免插入过程中操作触及其配置；这不构成跨 daemon 锁。

首版比例/布局采用模板与原生标准视图的自动行为，不提供任意位置或比例参数；
响应必须报告实际结果，不把自动布局包装成满足任意纸张的智能排版。
不做自动标注、BOM、多图纸、剖视/局部视图、自定义模型方向或模板生成。

## 原生映射与验证要求

1. `ISldWorks.NewDocument(template, PaperSize, Width, Height)` 创建文档；返回为空失败，
   类型必须确认为 drawing。现有 part/assembly 的 `0,0,0` 参数不可盲搬：
   绘图 PaperSize 与模板继承行为、真实 swconst 枚举必须先校准。
2. `GetCurrentSheet` 取得当前真实 sheet；读取尺寸、比例、格式路径、投影、区划等原设置。
   实现使用已校准的 `SetProperties2` 设置 FirstAngle，只改变投影并保留其余实际配置，随后
   `ForceRebuild3` 并回读。不可猜 paper/template 枚举，不能清空格式或删除标题栏注释。
   若不能无损取得所需原值，应失败而不是传默认值覆盖模板。
3. 按显式投影调用且仅调用一次 `Create1stAngleViews2(source_path)` 或
   `Create3rdAngleViews2(source_path)`；返回 true 不是完成标准。
   两者没有配置参数，需回读每一视图的 `ReferencedConfiguration`；若校准路径需设置
   此属性，必须在重建后再核实，并确认不改变源活动配置/修改状态。
4. `IDrawingDoc.GetViews` 是每 sheet 一个数组，每数组首项为 sheet 自身，
   **不能把数组长度 3/4 或前 3 项直接当三视图**；多 sheet 数组顺序也非保证。
   按当前 sheet 的实际身份关联，恰有三个新增模型视图，无额外模型视图。
5. 每视图返回 native name（描述而非稳定 ID）、源完整路径、配置、实际比例、
   sheet 上 Position 与 GetOutline（公开结果保留接口米，显式 `unit=meter`）、方向/投影证据。
   路径须规范化比对，`ReferencedDocument` 能取得时以原生身份交叉验证源对象；
   同名文件不能误认。比例有限且正，位置/包围框有限、非退化。
6. 不用本地化的 `Drawing View1`、数组顺序或屏幕截图认定 front/top/side。
   必须校准 `ModelToViewTransform` 与标准模型轴的映射、相对投影布局及容差，
   不能先给未经证明的视图贴 front/top/right 标签。第一角的侧视方向也需原生证明。
   如无法可靠分类就输出原始证据并失败，不假装创建正确。
7. 重建与诊断通过后，源状态未改变，目标保持 modified（因为尚未保存）是正常结果。
   返回 sheet（名称、尺寸、投影、比例）、三个 views、source、目标 document 和诊断。
   视图是描述信息，首版不发可长期引用的 view ID。保存/重开由现有独立命令负责。

首版不承诺标题栏避让/自动布局优化；但全部视图须可观察且轮廓在纸内，明显重叠
或出界不能宣称可交付。复杂排版超出范围时明确失败，让用户换适当模板/模型尺度，
不要通过重试、缩小几何或改验证阈值过关。部分插入失败不继续重复创建，返回第一失败
与已存在视图证据，用户可检查或显式丢弃文档。

## 校准门槛与测试

先做内部单 STA、独占可见宿主的校准，不新增公开 eval/COM 旁路：

1. SW2025 Windows CI 生成非对称尺寸零件和含该零件的简单 ASM，各自保存、clean；
   用真实模板分别覆盖 first/third-angle。记录模板路径/hash、sheet 原值、native enums，
   每个 COM 方法开始/完成/异常落盘，不失败重试。
2. 先读模板再新建，校准 PaperSize 处理；比较设置投影前后模板格式、尺寸、比例、
   区划和标题栏不变。确认 FirstAngle sheet 状态与三视图调用一致。
3. 逐视图记录 referenced path/config、transform、位置、轮廓、比例，证明三个方向
   与 first/third 相对布局，不靠名字。测试指定非活动配置的拒绝策略。
4. 保存 SLDDRW，关闭重开，重新读回 sheet 和视图引用/配置/方向/比例；PDF 与 DWG
   用既有严格导出与产物校验。PDF 成功不替代工程图内部引用验证。
5. 负例：缺模板/错扩展名、源未保存/modified/需重建、配置不存在、错类型、非空/多 sheet
   模板，必须在相应原生副作用前拒绝；注入创建后失败须保留句柄与证据。
6. 相同共享脚本在 DockerSW Linux/Wine 与 MacSW macOS/Wine 验证；各宿主只负责
   环境和调用。Windows 通过不等于 Wine 通过。先完成此切片再扩通用 view/sheet API。

## 官方依据与尚未证明的事项

2026-10-23 检索时，部分 2025 直达 URL 返回空 2027 帮助壳，不能把 URL 年份当作
已读到 SW2025 正文。以下为实际可读的官方 API 正文；历史签名只是选型依据，
必须再用 SW2025 typelib/真机校准当前绑定、枚举和行为。

- [NewDocument](https://help.solidworks.com/2020/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~NewDocument.html)：模板完整路径、纸张参数、返回文档或 null。
- [SetupSheet6](https://help.solidworks.com/2020/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.idrawingdoc~setupsheet6.html)：FirstAngle、模板/纸张/比例/区划参数；修改投影后要 ForceRebuild3。
- [GetCurrentSheet](https://help.solidworks.com/2016/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.idrawingdoc~getcurrentsheet.html)：当前 sheet，不是所有 sheet 的首项。
- [第一角三视图](https://help.solidworks.com/2022/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~Create1stAngleViews2.html)、[第三角三视图](https://help.solidworks.com/2018/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~Create3rdAngleViews2.html)：仅 ModelName 参数、布尔结果，遵守文档自动比例设置。
- [GetViews](https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~GetViews.html)：sheet 嵌套数组及 pseudo-view、顺序限制。
- [IView 引用路径](https://help.solidworks.com/2011/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetReferencedModelName.html)、[IView 成员](https://help.solidworks.com/2017/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView_members.html)：ReferencedConfiguration、ModelToViewTransform、Position、ScaleRatio 等候选观察面。

已校准的 A4、显式投影、标准模型坐标系下三视图方向与布局见原生记录；不能再将它们
描述为全部尚未验证。仍不承诺任意 DRWDOT 纸张继承、SetupSheet6 无损修改、隐式
配置选择/父子联动、任意模型方向或自动比例/外部格式依赖在三宿主的一致性。
标题栏视觉保真与导出视觉等价也不是文件校验通过即可证明；Mac 完整验收未通过，
复杂样例软渲染 CI 超时已由用户批准不阻塞 a11，不等于新增硬件性能或通用兼容性保证。
