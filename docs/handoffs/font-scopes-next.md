# 尺寸与表格默认字体 next 交接

2026-11-14。本轮不属于当前固定发布范围。状态：**两类受保护候选写入、定向内部校准入口及便携测试已实现；新 head 无原生验收，公开写入保持关闭**。已合入的 Notes 七字段没有重做，不自行合 main、改版本或发布。

## 分支、基线与原件

- 持久工作树：`/Users/YJBeetle/.codex/worktrees/docprops-font-scopes/SWCLI`。
- 首轮候选实现：`466035fee5f056f6c88f6afd486ed8d36d28ce8f`，首轮交接 `f5a62cfcc525e885fefe7694dc7fabfa2f407d61`。
- 新增离线准备实现：`c108af1ca97b9f07c7379a0d2dfa0f41dc00f4d6`，包含持久 witness/完整前台指针守护/源码包/离线 SDK 请求门禁；详见 [增量准备交接](font-scopes-next-preparation.md)。没有新增原生或公开通过声明。
- 新分支：`codex/docprops-font-scopes-next`；起点为已核远端 main `31ad9c256a5a106bc94a627cd41dfd6277bb6f00`。创建前原工作树干净；没有 `.codegraph/` 或更深的 AGENTS。遵循祖先 CodeGraph 规则，未自行索引。
- 原 Notes 分支 `codex/docprops-font-scopes` 保持 `0801837a6e404f65216702e02efb3f1901dd86a2`，受验产品提交 `15d32ceea38b123c3cd3503b34d86663a65f5f3c` 保留。
- 两份原 ZIP 仍存于本工作树 `artifacts/font-scopes/`，本轮重新计算一致：内部 `42266956658` SHA-256 `615b979b4adb667cade7bf3448a7c3c898392d1638b862904debba8bfca37eca`；Notes 公开 `42279469524` SHA-256 `67fec36badcdfd5cb9d29218efbad91aa601aad4d4a6ca9e24fe35b86ef942c3`。
- 保留清单：`artifacts/font-scopes/next-baseline-and-preserved-evidence.json`。旧内部 63 次写入不能作为本轮 head 或新对象继承的验收。

## 已实现

1. `font_scope_candidates.py` 给出 dimensions/tables、原生 Windows revision 33.5.0、PRT/ASM/DRW、typeface/height_mm/height_points/bold/italic/underline/strikeout 的封闭内部候选。公开 capability/catalog 仍只有 Notes；不增加参数、环境或 SDK/MCP 绕过开关。
2. `_calibrate_next_document_font_scope` 只被 owned 诊断入口在既有 dispatcher 上私有替换使用，复用完整四范围 17 字段 CAS、文档身份/lease/stamp、readonly/viewonly、编辑上下文、背景文档与前台状态、脏标志和 partial mutation。未知 runtime、版本、文档类型和非 next scope 在字体分配前拒绝。
3. 既有校准/看门狗新增 `--scope dimensions|tables`。每组只改一个默认 scope，跨 PRT/ASM/DRW 做七字段变化、逐次同值、CAS/lease/stamp/readonly 拒绝、毫米/磅值保存重开、原几何与源文件 hash。选中 next scope 时不写 Notes，仍读取四范围防交叉漂移。
4. 表格入口额外只读记录 BOM/general/hole/revision/title-block 五类字体的完整 17 字段归一化与原生快照、逐边界成员差异，覆盖初始/每次变化/两次重开。符号来自官方安装 TLB；缺符号、空字体或不可读字段即首失败停止。该只读观察检查目标与前台状态保持，独立 trace stage 为 `document-font-scopes-linked`。
5. 上述五类记录是联动观测，**不是全表格类型、对象或单元格继承验收**。本轮没有修改表格默认标量、UseTemplateSettings、任何已有对象/单元格格式，没有新建实际单个注释操作。
6. 每次同步 native/dispatcher 600 秒、每组 1800 秒；watchdog 只停止它启动的 Python worker。无 API 重试、自动回滚或组内宿主重启。原 CLI→daemon→worker 路由与 Notes 产品白名单保持。

## 首轮便携验证（466035f；增量结果见上方交接）

- 字体关联 74 项通过，包含新增 10 项 next 测试。
- 新测试覆盖两个 scope×三个文档类型×七字段的 42 个真实 dispatcher/adapter 组合；全部四范围×17字段 CAS；单位/模式、同值无修改、lease/stamp/只读/编辑拒绝、live assignment 后 False/异常 partial 且无重试、未开放 public/协议开关、只读五类快照和入口接线。
- SDK 生成一致性通过；修改文件按 Python 3.9 AST 解析通过；两个脚本 --help 在无 COM 的本地成功。
- 最终完整回归运行 **2,976 项，OK（39 skipped），131.411 秒**；`artifacts/font-scopes/next-full-portable-final.log`。这是 macOS 便携回归，不是 Windows/COM 验收。
- 日志及保留清单均在 `artifacts/font-scopes/next-*`；机器摘要为 `artifacts/font-scopes/next-portable-audit.json`。

## 官方语义与尚未验收

[2025 文档默认字体 getter](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~GetUserPreferenceTextFormat.html) 和 [2025 TextFormat 枚举](https://help.solidworks.com/2025/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swUserPreferenceTextFormat_e.html?format=P&value=) 将文档默认与任意对象修改分开。尺寸总默认沿用已核 `swDetailingDimensionTextFormat/swDetailingDimension`，表格总默认沿用 `swDetailingTableTextFormat/swDetailingNoOptionSpecified`，不改为 general-table 子类型，也不猜整数 ID。

[2025 尺寸对象字体说明](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_DVE_DIMENSION_OTHER.htm) 区分 Use document font 与局部格式；公差字号又有独立来源。本轮只改总默认，没有修改局部对象、尺寸数值、公差或子类型。后续须只读观察已准备的继承/局部 fixture，不能从默认读回一致推断实际对象继承。

[2025 表格总默认说明](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_Options_General_Tables_New.htm) 明确总字体变化会更新各类型的文档字体；模板可能决定新表格的格式。[2025 General 表 API 映射](https://help.solidworks.com/2025/english/api/swconst/DP_Tables-General.htm) 又有独立字体 preference。因此本轮五类 witness 只记录真实联动，不把子类型变化当成全范围独立，也不自动改变模板开关。表格自身与 cell 的 UseDoc、模板覆盖、剩余表格类型、尺寸子类型和视觉输出均未验收。

## 请求 root 排程的定向原生计划（尚未执行）

先安排两组独立 owned-hidden-host 内部校准，不重跑 Notes，不复用失败组宿主：

```powershell
python scripts/ci/run-font-scopes-calibration.py --profile internal --scope dimensions --source-head c108af1ca97b9f07c7379a0d2dfa0f41dc00f4d6 --output-dir <fresh-dimensions-output> --swconst <registered-swconst.tlb> --drawing-template <installed-GB.drwdot>
python scripts/ci/run-font-scopes-calibration.py --profile internal --scope tables --source-head c108af1ca97b9f07c7379a0d2dfa0f41dc00f4d6 --output-dir <fresh-tables-output> --swconst <registered-swconst.tlb> --drawing-template <installed-GB.drwdot>
```

以上仅为排程用命令，本轮没有执行。root 在排定的 Windows 2025 环境 checkout 精确 next 实现提交、安装该源码并记录匹配 source_head；每组独立 600/1800 秒。不得用当前只绑定旧分支的 workflow 或旧单机密授权自动扩到 next，本轮不修改 CI/机密路径、不手动 dispatch，也不占用 VM。

每个 scope 预期三 case、21 次变化和 21 次同值、三类各毫米/磅值保存重开。table 若任一已知类型的 getter 在某文档类型不可用，应保留首失败原件并据实收窄/修复，不能跳过 getter后继续写，也不无修改重跑。五类 subtype 差异须逐成员审查，当前不承诺除父 scope 的单字段外所有 subtype 成员独立。

内部原件独立核 head/digest/trace/源与六份输出 hash 后，再由 root 协调必要公开 CLI/daemon/worker 门禁和只读继承观察。`verify-font-scopes-public.py --scope dimensions|tables` 的现有通用门禁可复用，但目前 public 白名单关闭，不能拿它的预期拒绝当公开通过；开放精确 profile 和继承 fixture 需根据真实内部结果做后续有限实现/审阅，禁止自动晋升。这里没有给出任何合并或发版完成声明。
