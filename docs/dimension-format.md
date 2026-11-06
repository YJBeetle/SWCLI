# 尺寸显示格式（内部校准阶段）

本批限定选项 → 文档属性 → 尺寸中的三项：

| 字段 | 值 | 官方文档级映射 |
| --- | --- | --- |
| `dual_display` | boolean | `IModelDocExtension.Get/SetUserPreferenceToggle(swDetailingDualDimensions=43, swDetailingDimension=200)` |
| `dual_position` | `right/top/left/bottom`（写入参数）；原生整数（读取/CAS） | `Get/SetUserPreferenceInteger(swDetailingDualDimPosition=14, swDetailingDimension=200)`；右1、上2、左3、下4 |
| `parentheses` | boolean | `Get/SetUserPreferenceToggle(swDetailingDimsShowParenthesisByDefault=48, swDetailingNoOptionSpecified=0)` |

零显示已有 `document.annotation-options` / `document.annotation-option-set` 的 `zero.leading`、`zero.trailing`，本批不重复实现。长度/角度/质量单位转换、精度转换、公差、字体、分数格式与各尺寸子类型不在本批范围。

公开操作：

```sh
swcli document dimension-format --document d-ab12cd --json
swcli document dimension-format-set dual_position top --document d-ab12cd --lease l-ab12cd34ef56 --if-update-stamp 7 --if-format '{"dual_display":false,"dual_position":1,"parentheses":false}' --json
```

读取 `format` 为完整的原生三字段快照；未知位置整数保留原值用于完整 CAS。setter 每次最多改变一项，要求显式 `document_id`、`expected_update_stamp`、`lease_id` 和 `expected_format`。公开字段不接受内部校准开关。文档身份、前台、活动配置/草图/图纸上下文、readonly/viewonly 均受保护。真正写入前再次观察完整快照；写入后精确读取全部三字段，同时保护原有单位元组与注解/零显示配置。setter 失败保留 `mutation.attempted/may_have_changed`，不重试、不回滚。

**原生写入默认关闭。** `CALIBRATED_DOCUMENT_TYPES` 为空：实际变更返回 `DimensionFormatNotCalibrated`；CAS 成功的同值调用不触碰 setter、不置脏。内部适配器校准不是安装后公开 CLI 验收，不能据此开放写入或宣称验收完成。

Windows 手动 CI：现有 `ci.yml` 的 `dimension_format_calibration=true`，仅 `codex/docprops-dimension-format` 可运行；默认 false，不接收 PR 事件，不触发完整 native suite。内部校准在独立隐藏 host 中顺序运行 part/assembly/drawing，核安装 `swconst.tlb`，验证背景读写、全部位置、true/false、保存重开、单位/零显示/全局偏好不变及零件几何。单个原生操作600秒、整组1800秒、首失败停止，无失败 API 重试/自动回滚/组内重启。原始报告、trace、stdout/stderr、原生文件由专属 artifact 保留。

官方来源（2026-11-07 核对）：

- [尺寸文档属性界面](https://help.solidworks.com/2025/english/SolidWorks/sldworks/HIDD_OPTIONS_DIMS_New.htm?id=4.7.3.3)
- [尺寸 API 映射表](https://help.solidworks.com/2019/english/api/swconst/dp_dimensions.htm)（2025 同名网页读取异常，因此同时核本机官方2025 SDK头文件与CI安装类型库）
- [2025 双尺寸位置枚举](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDetailingDualDimPosition_e.html?id=2.10.1.249)
- [文档 Toggle setter](https://help.solidworks.com/2023/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldocextension~setuserpreferencetoggle.html?format=P&value=) 的返回值文案与已有 Windows2025 校准存在差异：代码仅接受严格 True，并要求精确 readback；False 直接记录部分 mutation，不推测成功。

偏好/option ID 来自已安装官方 SOLIDWORKS 2025 SDK `samples/appcomm/win32/swconst.h`（只读读取，未启动 Wine/SOLIDWORKS），并在CI首次CAD操作前逐项核对官方类型库。
