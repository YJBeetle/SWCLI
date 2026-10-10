# 最小装配体创建与零件插入

当前源码新增 `document create --type assembly` 与
`assembly add-component`；这不代表已发布的 `v0.1.0a8` wheel 包含这些命令。
两者始终通过 daemon 的同一个 STA worker 执行，不提供直接 COM 后备路径。

## 显式流程

先打开已经保存的零件（也可使用 `part create-box` 返回的已保存、仍打开零件），
再创建装配体。新建文档返回短 `document_id` 并仅更新调用 session 的 current。

```powershell
sw-cli document open 'C:\Workspace\box.SLDPRT' --read-only --json
$assembly = sw-cli document create --type assembly --json | ConvertFrom-Json
sw-cli assembly add-component 'C:\Workspace\box.SLDPRT' `
  --document $assembly.document.document_id --json
sw-cli document save-as 'C:\Workspace\box-assembly.SLDASM' `
  --document $assembly.document.document_id --json
```

默认从 SOLIDWORKS 的 `swDefaultTemplateAssembly`（9）查找真实 `.ASMDOT`，
再沿用 part 的安装模板发现策略。也可显式指定 `--template`；错误扩展名、
不存在的模板以及 NewDocument 返回空对象均失败，不打开模板选择 UI。
创建失败但已经取得的文档仍登记到 daemon，避免遗失其句柄；这不是自动回滚。

## `assembly.add-component` 契约

请求 operation 为 `assembly.add-component`，parameters：

```json
{
  "path": "C:\\Workspace\\box.SLDPRT",
  "configuration": "Default",
  "x_mm": 0,
  "y_mm": 0,
  "z_mm": 0
}
```

仅 `path` 必填。`document_id`、`expected_update_stamp` 与 `lease_id` 使用公共
文档写入上下文：默认是 session current，也支持 `--document ID` 或单次 `active`。
已有 lease 必须由拥有者提交正确 token；冲突在激活或插入之前拒绝。
临时激活目标装配体后执行一次插入，随后恢复前台文档，不改变 session current。

输入须是存在且非空的 `.SLDPRT`，并已经加载到当前 SOLIDWORKS 进程中。
源零件不能有未保存修改。未加载时返回 `ComponentNotLoaded`，调用者应先
`document open`；适配器不会隐式打开、保存、关闭、切换配置或重建源零件。
目标必须为可写 ASM，且不处于组件就地编辑状态。

配置非空时先确认源配置存在，再传给 AddComponent5；不存在返回
`ConfigurationNotFound`。空配置使用原生的“最后保存配置”选项，响应记录实际
`ReferencedConfiguration`，不猜测或强制切换源文档的活动配置。

坐标都是毫米，转换为 API 米单位。它们只是原生 AddComponent5 的近似组件中心
输入，**不是零件原点的精确平移，也不保证旋转、配合、固定状态或实际中心坐标**。

成功响应包含 `inserted: true`、`component`（`name` / `path` / `configuration`）、
`component_count_before` / `component_count_after`、`placement` 和目标 `document`。
计数必须恰好增加一，返回的原生组件必须出现在顶层组件列表中，路径及显式配置
必须匹配。这里的组件名是原生描述信息，不是可用于后续操作的稳定 component ID。

返回空对象为 `ComponentInsertionFailed`；插入后核验不一致为
`ComponentVerificationFailed`，保留已插入及计数证据，不重试、不自动删除或保存。
插入不是事务，失败后的装配体可能已修改，调用者应检查或显式丢弃。
本层不包含 mates、子装配体、虚拟零件、Pack and Go 或引用文件打包。

operation 的请求、结果 schema 和能力发现由公共 operation catalog 发布，
包括可写 lease 与临时激活策略。真实保存、关闭重开与引用验证由建模门禁独立验证；
单元测试不能替代 Windows/Wine 的实际 COM 验收。

## 官方 API 依据

- [模板偏好枚举及 NewDocument 示例](https://help.solidworks.com/2016/english/api/sldworksapi/Get_Locations_and_Names_of_Document_Templates_Example_VB.htm)
- [AddComponent5 前先打开零件、再激活装配体的官方示例](https://help.solidworks.com/2023/English/api/sldworksapi/Add_Component_and_Mate_Example_VB.htm)
- [当前保存配置选项](https://help.solidworks.com/2026/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swAddComponentConfigOptions_e.html)
- [AddComponent 系列的近似中心坐标边界](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IAssemblyDoc~AddComponent4.html)
