# 工程图出详图默认选项（分支实现）

范围只包含文档属性 → 出详图 → 新建视图时自动插入：零件孔中心标记、零件圆角中心标记。只操作文档级默认 Toggle，不创建视图、中心标记或实体；不修改总体绘图标准、字体、公差。其他字段不在支持范围。

官方映射：[Document Properties > Detailing](https://help.solidworks.com/2024/english/api/swconst/DP_Detailing.htm)。字段为 `auto_center_marks.part_holes` / `auto_center_marks.part_fillets`，分别使用 `swDetailingAutoInsertCenterMarksForHoles` / `swDetailingAutoInsertCenterMarksForFillets`，通过 `IModelDocExtension.Get/SetUserPreferenceToggle`，option 为 `swDetailingNoOptionSpecified`。枚举数值从当前宿主安装旁的官方 `swconst.tlb` 读取，不猜数值，不调用应用级 preference setter。

[GetExecutablePath](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~getexecutablepath.html) 用于定位安装目录；常量库缺失或不完整时拒绝操作。
[SetUserPreferenceToggle](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SetUserPreferenceToggle.html) 对 false 返回的说明存在歧义。实现保留返回值，要求原生成功返回 True 和完整读回一致；失败不重试。

```sh
swcli document detailing-options --document d-ab12cd --json
swcli document detailing-option-set auto_center_marks.part_holes true \
  --if-options '{"auto_center_marks.part_holes":false,"auto_center_marks.part_fillets":true}' \
  --document d-ab12cd --if-update-stamp 7 --lease l-ab12cd34ef56 --json
```

写入必须给出明确文档、版本戳、有效 lease 与完整两个布尔旧值的 CAS。单字段写入同时校验另一个字段不变。文档必须可写并处于普通图纸编辑状态；拒绝图纸格式编辑、活动模型视图或外来/缺失草图。读取可保留其他编辑模式；读前后检查上下文、文档身份、dirty/stamp 与前台目标，后台操作不激活目标。变更后最多标 dirty 一次，最终观察不得悄悄修复状态漂移。

返回 `mutation.attempted` / `may_have_changed`；原生 setter 已尝试后即使失败也必须保留可能部分变更的回执。不会自动回滚、重复 setter 或重启宿主。相同值为无 mutation 的成功 no-op。

便携测试只证明接线与保护。内部 Windows 校准使用独立拥有的宿主、空工程图和前台零件；逐字段 true/false，逐次保存并只读重开、核对整组值、图纸/视图/投影以及原有 annotation scalars；验证 read-only 拒绝。每个追踪调用 600 秒、整组 1800 秒，首个失败停止并保留原报告、trace、文件和 hash。CI 手动 `detailing_calibration=true` 仅允许本分支，默认关闭，不运行完整 native suite，不触发 release。

当前 `CALIBRATED_REVISIONS` 为空；公开变更写入 fail closed。内部校准在其独占 Python 进程中临时允许本次宿主的准确版本号，结束后恢复。内部校准不等于公开 CLI/daemon 验收；未取得对应原生证据不得把新写入宣称为已验收。版本放行必须引用持久证据，不能根据便携测试放行。
