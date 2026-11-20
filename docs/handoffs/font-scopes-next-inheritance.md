# 尺寸与表格工程图继承验收准备

2026-11-21。独立分支 `codex/docprops-font-scopes-next` 的实现提交为 `7ce0e90980ea22f0d1bce2ae1043b62cc023a306`。本轮范围是可运行的验收准备及便携验证。尺寸和表格的原生、公开及继承状态待验收，本路排除当前发版。

## 运行前准备

在排定的原生 Windows SOLIDWORKS 2025 SP5（`33.5.0`）环境，安装指定提交的 SWCLI 源码和既有依赖。执行前验证 [离线源码包](../../artifacts/font-scopes/next-source-package-7ce0e90980ea/manifest.json) 对应完整提交，核对已安装 Python/schema。旧包和新包均需分别使用对应的源码提交验证。模板采用原校准的安装版 GB.drwdot，枚举从注册安装的 swconst.tlb 解析。

准备两份自建的、保存后可重新打开的独立 SLDDrw，各一张普通图纸，只含图纸视图，无外部模型引用。每份都从干净状态计算 SHA-256。

- **尺寸夹具**包含恰好两个图纸草图显示尺寸。两者名称须各自唯一且保存重开后稳定。一个选用文档字体，另一个使用明显不同的局部字体，例如 Courier New 20pt。普通尺寸字号与文档默认绑定，避免公差字号、富文本和尺寸文本覆写。
- **表格夹具**包含恰好一个 General 表，1 行 2 列，两个单元格都有简短文本。表格使用文档设置，左格使用文档字体，右格使用不同的局部字体，例如 Courier New 20pt。为验证关联，初始 General 类型默认和总默认选择同一字体与模式。避免模板覆盖、合并单元格和额外表格。
- 夹具目前需要在排定环境准备。本工作树没有这两份 SLDDrw。默认字体校准可以省略夹具参数，但该运行不会产出继承结果。

## 命令与资源窗口

以下为已排程环境用命令。将变量填为两份独立夹具及各自的 SHA-256。输出目录分别使用未创建的持久路径。两组串行，每组独立 owned 隐藏宿主，预留最多 30 分钟，合计 60 分钟，不含安装和夹具准备。单次调用预算 600 秒。以此前校准为参考，装好后的实际校准预计短于预算，当前候选尚无实测耗时。

```powershell
$head = "7ce0e90980ea22f0d1bce2ae1043b62cc023a306"
python -I scripts/ci/prepare-font-scopes-next.py verify --head $head --package-dir $verifiedSourcePackage
if ($LASTEXITCODE -ne 0) { throw "Source bundle verification failed" }
python -I scripts/ci/verify-font-scopes-next-offline.py --source-head $head
if ($LASTEXITCODE -ne 0) { throw "Offline request gate failed" }
python -I scripts/ci/run-font-scopes-calibration.py --profile internal --scope dimensions --source-head $head --output-dir $dimensionsEvidence --swconst $swconst --drawing-template $gbTemplate --inheritance-drawing $dimensionsDrawing --inheritance-sha256 $dimensionsSha256
if ($LASTEXITCODE -ne 0) { throw "Dimensions calibration failed. Preserve the original evidence." }
python -I scripts/ci/run-font-scopes-calibration.py --profile internal --scope tables --source-head $head --output-dir $tablesEvidence --swconst $swconst --drawing-template $gbTemplate --inheritance-drawing $tablesDrawing --inheritance-sha256 $tablesSha256
if ($LASTEXITCODE -ne 0) { throw "Tables calibration failed. Preserve the original evidence." }
```

每组先做原来的 PRT 和 ASM，用已校验 SHA-256 的新副本替代空 DRW。预期仍为三个文档、21 次变化、21 次同值和六份保存输出。工程图记录基线、毫米和磅值两个只读重开结果。验证继承标志、五项字体/样式和活跃高度变化、对象身份和局部原生/归一化全量 17 字段一致。表格依次核对总默认、General 类型默认、表格本体和两个单元格。五类型联动 JSONL 继续记录原值、后值、成员差异和 mutation 回执。读取使用 SOLIDWORKS 官方接口。 [显示尺寸字体](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IAnnotation~GetTextFormat.html) · [工程图表格入口](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~GetFirstTableAnnotation2.html) · [单元格继承标志](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITableAnnotation~GetCellUseDocTextFormat.html)

验收时核对每组 watchdog 的 source head、首失败、完整 trace 和原始文件。绘图 case 的 `inheritance_witness.success` 必须为 true，三条观察均已检查，源文件与两种输出摘要一致。该结果只覆盖单页工程图的上述对象组合。五类联动日志只证明相应类型默认的原值和变化。模型尺寸、本地覆盖的其他对象、其余表格类型、模板和视觉效果仍无证据。公开写入需另经统筹审查及真实公开门禁。

## 本地证据

- 两个新离线包从同一精确实现生成，共 1,053 个文件，ZIP 与清单逐字节一致。ZIP SHA-256 `453a5483a2b153083dd0823179f5a87b7dd0d6560028e5ee1561ba0d04b00e68`。清单 SHA-256 `cee021bce22e178d0fbaa85390849f283ce3f71593ff683d1fd18770ed1907f9`。目录 `artifacts/font-scopes/next-source-package-7ce0e90980ea/` 及 `-repro/`。
- 重启后复查原 `c108af1` 源码包，旧双副本逐字节匹配。原 ZIP `42266956658` SHA-256 `615b979b4adb667cade7bf3448a7c3c898392d1638b862904debba8bfca37eca`，原 ZIP `42279469524` SHA-256 `67fec36badcdfd5cb9d29218efbad91aa601aad4d4a6ca9e24fe35b86ef942c3`。前者每文档类型 21 次默认写入，后者是 Notes 公开及继承证据。两份均无新增的五类联动 JSONL。
- 最终实现字体专项 95 项通过。离线门禁核对 124 个安装源码和 schema 文件、42 个前端检查、10 类无效请求、2 条部分修改回执。
- 最新远端 main 核对为 `7400b2c615da5017f819ab8c13c194b4445fd75b`。独立快照应用最终候选后，对候选源码和测试逐文件比对，SDK 与 95 项字体专项通过，完整便携回归 3,049 项 OK（39 跳过），104.126 秒。首次嵌套 Git 命令跳过补丁，3,018 项结果仅属于 main。已在阻止外层仓库发现的快照重做。最终日志见 `artifacts/font-scopes/next-compat-7400b2c-7ce0e90/portable.log`，机器摘要见新包目录的 `compatibility-evidence.json`。
