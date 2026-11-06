# 文档默认字体范围（开发分支）

本分支基线为 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
状态：便携契约与保护测试通过；原生校准、对象继承及公开验收尚未完成。
用户已批准精确范围：`document.font-scope-set` 只对原生 Windows、SOLIDWORKS `33.5.0`、
PRT/ASM/DRW 的 `notes` 七字段开放；Wine、其他版本、dimensions/tables 继续 fail closed。
内部原生证据 run `42266956658` 已独立核验；公开 CLI/Notes 对象继承门禁仍待本轮验证。
不由环境变量或 JSON 参数打开额外范围。
内部校准使用独立的 Python 入口，保留相同 dispatcher 的文档身份、lease、stamp 与完整值 CAS。

## 有界范围与官方 API

| 类型化 scope | preference 符号 | option 符号 | 边界 |
| --- | --- | --- | --- |
| `dimensions` | `swDetailingDimensionTextFormat` | `swDetailingDimension` | 尺寸总默认；不把 option 错用为 0 |
| `notes` | `swDetailingNoteTextFormat` | `swDetailingNoOptionSpecified` | Notes 默认；不是通用注释总字体 |
| `tables` | `swDetailingTableTextFormat` | `swDetailingNoOptionSpecified` | Tables 默认；不覆盖表格模板或局部单元格 |
| `annotations` | `swDetailingAnnotationTextFormat` | `swDetailingNoOptionSpecified` | 只读交叉范围保护；不重复实现现有通用注释 setter |

符号数值从已注册 SOLIDWORKS 安装旁的官方 `swconst.tlb` 读取，不猜测硬编码值；缺少任何枚举即拒绝。
本分支只读参考了 document-properties-batch 的 17 字段快照/高度约束帮助函数，
整理到独立 `font_snapshot.py`，没有合并那个分支或接入它的通用注释操作。

官方依据（2026-11-07 查核，Web Help 部分直接 URL 会重定向到空导航，搜索可见索引正文）：

- [Dimensions API 映射](https://help.solidworks.com/2019/english/api/swconst/dp_dimensions.htm)：Get/SetUserPreferenceTextFormat 配合 `swDetailingDimension`。
- [Notes API 映射](https://help.solidworks.com/2023/english/api/swconst/dp_annotations-notes.htm) 与 [Tables API 映射](https://help.solidworks.com/2024/english/api/swconst/DP_Tables.htm)：各自字体 preference，NoOptionSpecified。
- [ITextFormat 成员](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat_members.html?id=2.2.1.434.0) 以及 [CharHeight](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat~CharHeight.html?format=P&value=)：原生高度为米。
- [IsHeightSpecifiedInPts](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat~IsHeightSpecifiedInPts.html)：CharHeight 与 CharHeightInPts 分别选择系统单位与磅值模式；它本身是只读方法。
- [SetUserPreferenceTextFormat](https://help.solidworks.com/2023/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SetUserPreferenceTextFormat.html)：文档级方法，严格要求 True 返回值，不调用全局 preference setter。

## 完整快照与写入保护

`fonts` 是四个固定 scope 的封闭结构，每个 scope 有完整 17 字段：
`typeface, height_mm, height_points, height_mode, bold, italic, underline, strikeout,
backwards, upside_down, vertical, width_factor, char_spacing_factor, escapement,
line_spacing, line_length, oblique_angle`。

候选写入字段只含 `typeface, height_mm, height_points, bold, italic, underline, strikeout`。
毫米转换为原生米；磅值为正 Int32，不接受小数或 bool。两种高度不会一起写；
必须原生读回请求值和模式。字体名严格读回，不安装字体、不接受替代字体推断。

`expected_fonts` 必须完整包含四范围及全部 17 字段，不能只 CAS 当前编辑字段。
写入要求显式 document_id、expected_update_stamp、lease_id；错误 session、过期 stamp、
readonly/viewonly、模型草图、工程图格式/视图编辑上下文及身份漂移均被拒绝。
不激活目标、不自动重试/回滚/重启。属性对象可能是 live COM，首个属性赋值前即标记
`mutation.attempted=true, may_have_changed=true`；setter False 或后续失败保留部分 mutation 回执。

内部读回保护对其他三范围使用原生快照全量相等；当前范围的非请求属性保持精确不变。
高度更改允许原生高度三元组改变；非高度写入只允许非活动高度表示被原生规范化，
活动高度与模式保持精确不变。此规则来自既有快照帮助函数，不是跨范围联动的豁免。
最终 SetSaveFlag 后再次读取，不能通过第二次标脏来掩盖读取引起的状态变化。

## 继承语义与验收边界

官方 [Dimensions 属性](https://help.solidworks.com/2022/english/SolidWorks/sldworks/HIDD_OPTIONS_DIMS_New.htm?id=6.7.3.3)
说明改变总尺寸字体会更新各尺寸类型的文档级字体，不能推断子类型独立。
本实现只观察上述四范围，尚未枚举所有尺寸子类型，因此 dimensions 公开写入继续关闭。

官方 [IAnnotation.SetTextFormat](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~SetTextFormat.html)
说明简单 Notes 与显示尺寸可选择文档默认或局部格式；含富文本的 Notes 还有特殊规则。
[ITableAnnotation.SetTextFormat](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITableAnnotation~SetTextFormat.html?format=P&value=)
同样有 UseDoc 选择，表格模板设置另有开关。当前 Notes 操作不强制改变已有对象的继承标志、
局部格式、模板设置、富文本内容，也不宣称已有对象的视觉效果已验证。

## 入口

- `swcli document font-scopes --document d-xxxxxx --json`
- `swcli document font-scope-set notes bold true --if-fonts '<四范围完整 JSON>' --document d-xxxxxx --if-update-stamp 7 --lease '<lease>' --json`

第二条仅在上述精确原生 Notes profile 可写；未匹配时返回 `DocumentFontScopeNotCalibrated`
与未尝试 mutation 的回执。当前通过内部校准，公开门禁尚待运行。
Python SDK 对应 `client.document.font_scopes(...)` / `font_scope_set(...)`，MCP 沿用类型化 operation 调用。
不开放任意 COM 字典、任意 preference ID、任意成员名或公共校准开关。

## 内部校准

`ci.yml` 的 `calibrate_font_scopes=false` 专属开关只允许当前分支手动调用
`font-scopes-calibration.yml`。仅显式传递用户授权的 `RCLONE_CONFIG_B64`；不继承全部机密，
PR 不触发。专属 concurrency 使用 `swcli-font-scopes-${{ github.ref }}`，
`cancel-in-progress=false`，不共享默认 full/release 的等待槽。该路径跳过通用 portable/package 和 full-native 作业，先运行本功能便携接线检查。

校准使用一个新建隐藏宿主，按 PRT/ASM/DRW 顺序生成自有夹具，在另一个前景文档存在时：
读取完整四范围 → 公开 fail-closed、lease/stamp/CAS 拒绝 → 内部单字段写入并原生读回
→ 毫米模式保存重开 → 磅值模式保存只读重开。保留既有夹具几何断言及源文件哈希。
任何首失败即停止后续计划。硬监护每 native/dispatcher 调用 600 秒、整组 1800 秒，
只终止它自己创建的 Python worker；不搜索/终止本地 VM、其他 SOLIDWORKS 或用户文档。
原始 report、trace、stdout、stderr、watchdog 保留 30 天并下载至本 worktree 持久目录。
即使内部校准通过，也不是公共 CLI 端到端验收，不自动开放公开写入。


## Notes 公开验收准备

新增可选的 `font_scopes_profile=public-notes`，默认 `internal`。
该 profile 只验证上述已批准 Notes 范围；尚未宣称公开门禁通过。
为严格核对继承，只准备 Notes：自建一条 UseDoc、一条局部 20pt Note；
源夹具保存只读重开后固定局部完整 17 字段/原生字体及 flag。
公开 CLI 对 Notes 默认字体做单字段变化、完整 CAS、同值与冲突/readonly 拒绝、
两种字号保存重开；之后独立 owned host 只读观察输出，继承条必须跟随文档样式/活动字号，
局部条全快照和 UseDoc=false 必须不变。每个阶段独立固定 600/1800 秒，不在失败组内换宿主。

官方 [InsertNote](https://help.solidworks.com/2016/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldoc2~insertnote.html)、
[GetFirstAnnotation2](https://help.solidworks.com/2015/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetFirstAnnotation2.html)
明确区分模型与工程图的枚举：工程图通过 IView.GetFirstAnnotation3，不能套用模型入口。
[GetUseDocTextFormat](https://help.solidworks.com/2019/English/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IAnnotation~GetUseDocTextFormat.html)
用于实际观察继承标志，不通过字体当前恰好相同来猜测。
尺寸子类型联动、表格模板/单元格继承、富文本和视觉渲染不由这个 Notes profile 推广验收。


## 后置失败和前台保护

字体 setter 的可信 mutation 回执跨 handler 最终 describe、worker 上下文恢复和结果验证保存；后置失败不会覆盖第一个业务错误。另一个前台文档的身份、dirty/stamp、配置、访问模式和编辑上下文在读取与写入边界核对。CI 手动入口先校验路由，非法或冲突的组合直接失败，字体专属路由与常规路由互斥。
