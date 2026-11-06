# 文档总体绘图标准：固定观察 profile 与有限转换候选

当前增量提供独立 catalog、Windows 内部适配器和便携测试。未注册公共 operation、
CLI 或 capability。`CALIBRATED_DRAFTING_TRANSITIONS=()`，没有开放实际标准转换。
已知总体标准的同值请求在完整 CAS 和状态检查后可返回 `changed=false`，零 setter、
零 SetSaveFlag。便携测试对有限转换表的临时替换只证明控制路径，不构成原生校准。

## 精确 API 和枚举

[Document Properties > Drafting Standard](https://help.solidworks.com/2024/english/api/swconst/DP_DraftingStandard.htm)
规定总体标准使用目标文档 `IModelDocExtension.GetUserPreferenceInteger` /
`SetUserPreferenceInteger`，preference 为 `swDetailingDimensionStandard=13`，option 为
`swDetailingNoOptionSpecified=0`。不调用 `ISldWorks` 系统偏好 setter。

[官方 swDetailingStandard_e](https://help.solidworks.com/2025/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swDetailingStandard_e.html)
与 read-r1 安装的官方 type library 导出一致：

| 候选名 | 官方成员 | 原生值 |
| --- | --- | --- |
| ansi | swDetailingStandardANSI | 1 |
| iso | swDetailingStandardISO | 2 |
| din | swDetailingStandardDIN | 3 |
| jis | swDetailingStandardJIS | 4 |
| bsi | swDetailingStandardBS | 5 |
| gost | swDetailingStandardGOST | 6 |
| gb | swDetailingStandardGB | 7 |
| custom（只读） | swDetailingStandardUserDefined | 8 |

所有标准读取严格接受 Int32，拒绝 bool/float/字符串；未知整数返回
`{value: "other", native_value: 原始整数}`。custom/unknown 仍可观察，不能作为切换
来源，也不接受 custom/unknown 写目标。不识别、加载或猜测任意 `.sldstd` 路径。

数字证据来自 `/private/tmp/docprops-batch-read-r1/swconst-enums.json`，对应安装的
`C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swconst.tlb`，SHA-256
`95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`。
read-r1 只原生读取了总体标准7，没有执行任何标准 setter；新增四个 base getter
及组合 profile 的原生运行仍待后续诊断，不能由类型库证明 getter 对每类文档可用。

## drafting-defaults-v1 的固定合同

内部 `_read_snapshot(document, kind)` 返回：

```text
{
  standard: {value, native_value},
  observed_defaults: {
    profile: "drafting-defaults-v1",
    document_type: 1 | 2 | 3,
    coverage: 固定字段清单及四个base preference/option,
    annotations: 七个 {value, native_value},
    annotation_font: {font: 规范17字段, native_font: 原生17字段},
    length_units: {length_unit, decimal_places, native_units: 原生五字段},
    display: 零件/装配10个或工程图5个 {value, native_value},
    base_standards: 四个 {value, native_value}
  }
}
```

`read_document_drafting_standard_windows(app=..., document=...)` 在此合同外添加
`ok/action`。`set_document_drafting_standard_windows(..., value, expected_snapshot)`
只接受上面**恰好两个顶层键**的完整 snapshot，不接受整个含 ok/action 的读回执。
没有外部 `snapshot_reader` 或任何 callable/path 注入参数。固定 reader 直接组合
现有宿主 helper，不在 helper 外再添加 native trace 包裹。

| profile 域 | 固定读取范围与单位 |
| --- | --- |
| annotations | A18 `ANNOTATION_FIELDS` 七项：三种附着箭头、折弯开关、折弯长度、前导零、尾随零；长度规范值毫米、native_value 米 |
| annotation_font | 仅 preference19/option0：TypeFaceName、CharHeight、CharHeightInPts、Bold、Italic、Underline、Strikeout、BackWards、UpsideDown、Vertical、WidthFactor、CharSpacingFactor、Escapement、LineSpacing、LineLength、ObliqueAngle、IsHeightSpecifiedInPts；同时保留现有 helper 的规范17字段和原生17字段 |
| length_units | `IModelDoc2.GetUnits` 五原生字段：length_unit、fraction_base、fraction_value、significant_digits、round_to_fraction；不能只取 mm/inch |
| display | 网格显示、主网格间距、每主网格小线数、每小格捕捉点数、虚拟交点样式；零件/装配另含平面正反面颜色、交线颜色、透明度、显示交线。使用 read-r1 已配置的10个 ID，工程图不调用5个 plane getter |
| base_standards | preference13，以如下四个 option 各读取一次，允许 custom/other 原生整数观察 |

| base 字段 | swUserPreferenceOption_e | 精确值 | 官方配对 |
| --- | --- | --- | --- |
| geometric_tolerance | swDetailingGeometricTolerance | 103 | [Geometric Tolerances](https://help.solidworks.com/2022/English/api/swconst/DP_Annotations-GeometricTolerances.htm) |
| detail_view | swDetailingDetailView | 301 | [Detail](https://help.solidworks.com/2020/English/api/swconst/DP_ViewLabels-Detail.htm) |
| auxiliary_view | swDetailingAuxiliaryView | 303 | [Auxiliary](https://help.solidworks.com/2016/english/api/swconst/DP_ViewLabels-Auxiliary.htm) |
| section_view | swDetailingSectionView | 302 | [Section](https://help.solidworks.com/2024/english/api/swconst/DP_ViewLabels-Section.htm) |

profile 的 `coverage` 包含注释字段名、字体 preference/option/17成员名、GetUnits 五
原生字段名、按文档类型适用的 display 字段名和上述四组 base preference/option。
结果中每项都来自实际 getter；不以四个非空假字典替代这些 getter 或验证覆盖。
数据 getter 数量为零件/装配41次、工程图36次：overall1 + annotations7 +
font18（对象1和成员17）+ units1 + display10/5 + base4。Extension、metadata state、
编辑上下文和 IsSame 身份读取另计；这些也必须保持原生 trace 顺序且不嵌套。

这是**有限观察范围**。没有声明覆盖全部字体 subtype、尺寸容差、table/view/DimXpert
标量或整份 Document Properties；其他48字体等扩展研究不作为本批有限转换的无限
前置条件。四个 base option 的符号与数字已核实，但其原生读取适用性仍须在各类
真实文档上观察，失败时不能改成假值或悄悄省略字段。

## CAS、联动和失败边界

[官方总体标准说明](https://help.solidworks.com/2026/English/SolidWorks/sldworks/HIDD_OPTIONS_DRAFTING_STD.htm)
指出选择总体标准会更新各 detail 的 base standard。
[总体与基础标准说明](https://help.solidworks.com/2021/english/SolidWorks/sldworks/c_docprops_Overall_Base_StandardsOH.htm)
说明独立 base detail standard 可覆盖总体默认值。因此切换后允许观察到字体、子标准、
注释和其他 defaults 联动；候选保留 before/after/final 和
`observed_defaults_changed`，不要求所观察的其他 defaults 全部不变，也不宣称
未观察字段没有变化。

写入前严格校验 snapshot 的固定 profile、文档类型、coverage 和各域完整键集；
整份 snapshot 使用保留 JSON 类型差别的精确 CAS，bool 与 int 不可互代。CAS 涵盖
native标准和上述固定观察值；原生偏好修改可能不推进 update stamp，stamp 不能
代替 CAS。实际切换的独立白名单键为
`(document_type, source_native, target_native, "drafting-defaults-v1")`，初始为空。
未来只根据实际转换、文档类型及 profile 证据逐项加入，不从目标 enum 存在外推
全部文档或反向转换均可写。

读取先捕获 foreground/edit 身份，再读取 metadata state 并立即检查上下文稳定；
全部 getter 后再次核 state/context。写入另要求可写文档和普通 drawing sheet／
无活动模型草图上下文。实际 setter 前再次检查 readonly/viewonly 和全部状态。
只调用一次文档标准 setter，严格要求 `returned is True`；False、非 bool 或异常均
停止并保留 `mutation.attempted/may_have_changed=true`，不重试、不回滚。

setter 后完整读回请求标准和固定 defaults，允许标准联动；必要时至多一次
SetSaveFlag，再次完整读取，严格保持 post-write state 和上下文。读回若推进
stamp/dirty、切换 foreground/edit，或最后一次读回出现新的变化即失败，不通过
再次标脏或写回旧标准修复。已有 after/final 观察保留。没有隐式保存或重建。

未来公开接入仍必须由统一 dispatcher 强制选定 document ID、session、lease 冲突
和必填 update stamp；本内部候选不替代这些保护。

## 私有原生校准与集中验收

后续可显式预定每类文档两次有限转换 GB7→ISO2→GB7。第二次是预先声明的另一次
校准转换，必须在第一次成功、保存、关闭、只读重开复核后执行，不能在失败路径
作为自动 rollback。每次均记录完整固定 profile、标准 setter 参数/返回值、状态/
上下文、trace、原始文件 hash、另存的新原生文件 hash/size，并对改变值保存重开。

使用现有同一次附着宿主与600秒单调用／1800秒整组界限；首失败停止，不自动
重试、重启、回滚或放宽超时。只处理登记的新建测试文档，保留用户宿主及原文件。
profile 中的 base getter 若不能在某类文档读取，应保留失败原件并据证据重新设计
明确 profile，不能假装完整成功。

私有诊断和便携测试不构成公共 daemon/CLI 验收，也不证明 release/CI。待真实有限
转换通过后才能更新相应白名单，再集中执行公共 session/lease/stamp/CAS、readonly、
后台文档、同值零 setter 及已改变值保存重开门禁。本次修改未执行 VM、原生或 CI。
