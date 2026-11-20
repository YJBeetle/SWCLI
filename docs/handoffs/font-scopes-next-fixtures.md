# 字体 next 自建工程图夹具

夹具准备实现为 `39a0fe842d6be06591c4f738a9d3017c35b02278`。这是候选分支的离线开发阶段，Windows 首跑、公开能力和字体继承验收仍待完成。夹具和命令使用自建空图纸及公开安装模板。请勿把业务图纸或用户文件传入夹具入口。

## General 表格生成

入口在专用 owned 隐藏宿主用安装版 `GB.drwdot` 新建单页图纸。脚本使用 `IDrawingDoc.InsertTableAnnotation2`，空表格模板，1 行 2 列，左格 `Fixture inherited`，右格 `Fixture local`。它检查表及左格的文档字体标志，在右格形成局部副本后才写 Courier New 20 pt。原四范围和五个表格类型默认值在保存前均要求与初始快照一致。 [2025 工程图表格创建](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDrawingDoc~InsertTableAnnotation2.html) · [2025 表格字体](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITableAnnotation~SetTextFormat.html?format=P&value=) · [单元格字体及 UseDoc](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITableAnnotation~SetCellTextFormat.html)

自动结果保存在 `native/font-tables-fixture.SLDDRW`。报告分别保存原生保存回执、只读重开回执、前后完整字体和观察证据、输出大小及文件 SHA-256。只有读取实际访问模式为只读、字节和原生字体基线保持时，case 才成功。Windows 首跑仍需验证 `Text2` 的索引属性调用和该版本的表格/单元格格式持久化。 [ITableAnnotation 成员](https://help.solidworks.com/2022/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ITableAnnotation_members.html)

若表格自动化首跑失败，保留原 watchdog、trace、报告和已写文件。以后经排程可用 UI 手工建同一夹具。用 GB 模板新建单页无模型视图工程图，插入一张 General 表，选择 1 行 2 列且不导入表格模板。输入上述两段固定文本，表和左格使用文档字体，右格取消文档字体并设 Courier New 20 pt。保证总表格默认与 General 默认相同。另存自建图纸，关闭后计算 SHA-256。给下方表格命令加 `--inheritance-drawing` 与 `--inheritance-sha256` 可走只读资格检查。

## 尺寸手工建夹具清单

官方 `IModelDocExtension.AddDimension` 要求可见文档，并提示尺寸输入可能有对话框。`AddSpecificDimension` 文档涵盖工程图，但已有官方示例和 SWCLI 原件都没有覆盖隐藏宿主操作 GB 图纸草图时的线段选取、创建以及 `IView.GetFirstAnnotation3` 重开枚举这一组合。因此先由 UI 生成几何，再用同一 owned harness 做只读资格检查。 [AddDimension](https://help.solidworks.com/2022/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldocextension~adddimension.html) · [AddSpecificDimension](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~AddSpecificDimension.html) · [Smart Dimension](https://help.solidworks.com/2025/english/SolidWorks/sldworks/t_Dimensioning_a_2D_Sketch.htm)

1. 用安装版 GB 模板新建一张图纸，不插入模型视图。保持普通图纸编辑模式，退出图纸格式编辑。
2. 在图纸草图中画两条不相交的水平线。可分别用约 40 mm 和 55 mm 的长度，位置上下错开。为每条线各建一个 Smart Dimension，保留两个可见的显示尺寸。退出草图编辑。
3. 在尺寸 PropertyManager 的 Other 页，让第一个尺寸使用文档字体。对第二个尺寸取消 Use document font，选择 Courier New 20 pt。保持普通尺寸文字，避免给文字或公差添加覆写。 [尺寸字体设置](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_DVE_DIMENSION_OTHER.htm)
4. 另存为 `dimensions-fixture-seed.SLDDRW`，记录独立路径，关闭图纸。在 PowerShell 用 `Get-FileHash -Algorithm SHA256` 计算摘要。底下的资格检查会核对实际继承标志、两尺寸不同且非空的标识、局部字体与默认值的区别及文件是否保持。
5. 关闭负责手工建夹具的 SOLIDWORKS 窗口。owned harness 需要独占宿主，资格检查将复制输入到独立目录，只读开启副本，报告记录原始摘要、输出摘要和实际只读重开状态。

## Windows 排程命令

使用上面精确提交的源码和环境。变量指向已安装的类型库、GB 模板、手工尺寸输入和两个不同且尚未创建的持久输出目录。两次使用原看门狗预算，每调用 600 秒、每组 1800 秒。

```powershell
$head = "39a0fe842d6be06591c4f738a9d3017c35b02278"
$dimensionsSha256 = (Get-FileHash -Algorithm SHA256 $dimensionsSeed).Hash.ToLowerInvariant()

python -I scripts/ci/run-font-scopes-calibration.py --profile next-fixture --scope dimensions --source-head $head --output-dir $dimensionsFixtureEvidence --swconst $swconst --drawing-template $gbTemplate --inheritance-drawing $dimensionsSeed --inheritance-sha256 $dimensionsSha256
if ($LASTEXITCODE -ne 0) { throw "Dimension fixture qualification failed. Preserve the evidence." }

python -I scripts/ci/run-font-scopes-calibration.py --profile next-fixture --scope tables --source-head $head --output-dir $tablesFixtureEvidence --swconst $swconst --drawing-template $gbTemplate
if ($LASTEXITCODE -ne 0) { throw "Table fixture preparation failed. Preserve the evidence." }
```

分别确认 `watchdog.json.success`、`native/report.json.success` 和 `cases[0].success`。从各自的 `cases[0].path` 与 `file_sha256` 取得后续内部校准输入。按原[继承校准命令](font-scopes-next-inheritance.md)运行时，将源码 head 更新到本页的实现提交，并为每个 scope 另建校准输出目录。准备报告的 `inheritance_acceptance` 为 false。实际改变默认字体再重开观察属于下一阶段。

## 离线验证

101 项字体专项通过，其中新增 6 项覆盖表格索引参数、局部字体分离失败、手工只读复制、保存后的快照漂移、实际打开模式不符和看门狗路由。SDK 生成、Python 3.9 语法和两个 `python -I --help` 入口通过。持久日志为 `artifacts/font-scopes/next-fixture-portable.log`。精确源码包在 `artifacts/font-scopes/next-source-package-39a0fe842d6b/`，1,056 文件。ZIP SHA-256 为 `b1f8c137fb1ec432444cc63eaf729b81fa88fa9a03436fa711272494f66937b8`。清单 SHA-256 为 `c15fd92cef19293205f16124546824ebd25fb6b4d22b5232c2be51c1df83d79a`。原离线请求合同通过，详情见包目录的 `offline-requests.json`。本轮尚无两份实际生成的工程图文件和原生回执。
