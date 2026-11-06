# 15路CI路由与滚动集成证据审查

快照开始于 `2026-11-06T17:32:17.327392+00:00`（北京时间11月7日）。这是时点审查，其他对话持续工作中；不是实时看板。

本报告只读其他14路源码/交接及GitHub元数据，没有修改其worktree、合并分支或dispatch。工作文件与HEAD分别固定；snapshot.json记录dirty路径和工作文件SHA256。主对话逐路评定集成，本报告没有把空白名单候选标为可发布。

机器矩阵：`docprops-merge-evidence-v1.json`。原始快照：`../../artifacts/docprops-coverage-ci/routing15-20261107/`。内部校准、公共原生CLI/SDK/MCP、便携检查、源码SHA、GitHub artifact摘要、原ZIP独立核验分别记录。

## 具体路由问题

1. **R1 / 线型（合并前修）**：当前快照ci.yml的solidworks-e2e仍用 `swcli-hosted-windows-${{ inputs.line_font_calibration && 'line-font-calibration' || 'solidworks' }}`。专属组没有ref，且复用full job；移植到其他ref会再次共享pending槽。应只改targeted分支为profile+ref，full fallback保留。
2. **R2 / 表格（复用前改进）**：独立table-defaults-calibration job使用固定 `swcli-table-defaults-calibration`，当前exact branch/head白名单下与其他profile/full隔离；不属于共享full槽问题。若滚动集成后允许其他ref复用，加入ref，避免同profile多分支互相替换。
3. **R3 / 公差、线型、单位、STEP（合并前补互斥测试）**：full和targeted可同时为true且没有私有输入前拒绝。公差/线型/单位可由full分支条件放行job，但targeted=true又跳过full smoke；在不匹配的ref上targeted step也跳过。STEP允许双模式并按targeted执行，行为与full请求不一致。应在私有输入前明确互斥，并测true/true、错误ref、默认full、正常targeted四种情况。现有release是tag-only，不能据此声称已误发布；问题是手动scope路由不明确。
4. **R4 / 单位（运行事实）**：run 42260282974 的实际源码 b5b935bc 仍用共享 `swcli-hosted-windows-solidworks`，snapshot中job pending/steps=[]；当前工作源码已改profile+ref。当前修复不追溯改变旧run。不可为等待无差异重dispatch，也不能把当前group当作该run证据。
5. **R5 / 本分支审计器（已修，待主审复核）**：旧版本可接受空属性和只清理trace，不能作为校准通过证据。现改为严格fixture结构检查，输出 `structure_complete`，恒定 `calibration_passed=false`、`source_provenance_verified=false`，移除success字段。driver自报head仅做一致性检查。真正独立原生核验还须GitHub精确run/head、下载原artifact ZIP核digest并逐项审阅真实报告/trace/native副本；本脚本不提供该结论。连续同名native调用改用begin序号识别，独立600秒计时。

在本次快照中，15路专属开关均默认false，私有native路径受workflow_dispatch/仓库/分支门禁控制；未发现新增PR secrets触发。默认full/release并发fallback均保留，字体reusable的native使用profile+ref；尺寸采用真正独立无concurrency的job，不占full pending槽。这里只静态审路由，未运行所有分支的truth-table测试。

## 源码与原生证据

下表原生状态均是内部校准，不能替代公共验收。没有任何一路完成独立原生原ZIP核验；原生ZIP digest列全部未取得。已有GitHub dist/portable/package摘要详见JSON，未下载核验，绝不计作原生证据。

| 分路 | 当前HEAD（*含未提交路径） | 唯一/最新run与运行SHA | 内部状态（快照） | 公共验收 / 原生ZIP独立摘要 |
| --- | --- | --- | --- | --- |
| docprops-font-scopes | `a1860400` * | [42262037827](https://github.com/YJBeetle/SWCLI/actions/runs/42262037827) / `a1860400` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-dimension-format | `989ce4e4` | [42260887789](https://github.com/YJBeetle/SWCLI/actions/runs/42260887789) / `4a2b4f46` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-tolerances | `742fba95` * | [42261066525](https://github.com/YJBeetle/SWCLI/actions/runs/42261066525) / `27dc9307` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-table-defaults | `8ca545c8` * | [42261481759](https://github.com/YJBeetle/SWCLI/actions/runs/42261481759) / `8ca545c8` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-detailing | `87f4df68` | [42260661085](https://github.com/YJBeetle/SWCLI/actions/runs/42260661085) / `5c878c3b` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-line-style | `3ab8d214` | [42260712677](https://github.com/YJBeetle/SWCLI/actions/runs/42260712677) / `6f531a59` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-coverage-ci | `e4f534b3` * | [42260050176](https://github.com/YJBeetle/SWCLI/actions/runs/42260050176) / `7f7a4af8` | cancelled-no-CAD-evidence | 未验证 / 无 |
| docprops-units-expanded | `4f8912f7` * | [42260282974](https://github.com/YJBeetle/SWCLI/actions/runs/42260282974) / `b5b935bc` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-export-options | `818329af` | [42261983700](https://github.com/YJBeetle/SWCLI/actions/runs/42261983700) / `e62fa65b` | pending_or_in_progress_not_passed | 未验证 / 无 |
| docprops-calibration-performance | `1c57948b` * | [42261401694](https://github.com/YJBeetle/SWCLI/actions/runs/42261401694) / `1c57948b` | pending_or_in_progress_not_passed | 未验证 / 无 |
| swcli-topology-references | `3bda2c00` * | 未捕获 | no_run_captured | 未验证 / 无 |
| swcli-assembly-mates | `3bda2c00` * | 未捕获 | no_run_captured | 未验证 / 无 |
| swcli-revolve-feature | `3bda2c00` * | 未捕获 | no_run_captured | 未验证 / 无 |
| swcli-stl-export-options | `3664d4b9` | [42262477609](https://github.com/YJBeetle/SWCLI/actions/runs/42262477609) / `3664d4b9` | pending_or_in_progress_not_passed | 未验证 / 无 |
| swcli-step-export-options | `ff7f66ba` | [42262507658](https://github.com/YJBeetle/SWCLI/actions/runs/42262507658) / `ff7f66ba` | pending_or_in_progress_not_passed | 未验证 / 无 |

## 便携、SDK、MCP与集成边界

其他分支本地便携/SDK结果来自带hash保存的WORK_HANDOFF.md，未在本分支重新运行；GitHub已完成portable jobs另列在JSON，不能推定完整native。所有MCP原生端到端均未验证。本分支新增13项测试在本机执行通过。

| 分路 | 便携（证据层级） | SDK | MCP |
| --- | --- | --- | --- |
| docprops-font-scopes | 1847; 32 skips; handoff claim | generator check claimed | 原生未验证；契约状态见JSON |
| docprops-dimension-format | 1834; 32 skips; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |
| docprops-tolerances | 1833; 32 skips; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |
| docprops-table-defaults | 1834; 32 skips; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |
| docprops-detailing | 1832; 32 skips; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |
| docprops-line-style | focused 12; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |
| docprops-coverage-ci | 13 focused; independently run in this worktree | baseline outgoing contracts checked; no new SDK | 原生未验证；契约状态见JSON |
| docprops-units-expanded | handoff portable claim; see snapshot | handoff SDK claim; not rerun here | 原生未验证；契约状态见JSON |
| docprops-export-options | 1841; 32 skips; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |
| docprops-calibration-performance | 107 focused; handoff claim | no new product SDK | 原生未验证；契约状态见JSON |
| swcli-topology-references | not established in captured handoff | not independently verified | 原生未验证；契约状态见JSON |
| swcli-assembly-mates | 14 focused; handoff claim | generated contract; no independent check | 原生未验证；契约状态见JSON |
| swcli-revolve-feature | 15 focused; handoff claim; full suite unresolved | strict types claimed | 原生未验证；契约状态见JSON |
| swcli-stl-export-options | 1833; 32 skips; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |
| swcli-step-export-options | 1836; 26 skips; handoff claim | generator + strict types claimed | 原生未验证；契约状态见JSON |

所有产品分路本次都不自动标merge-ready/release-eligible。公开写入为空白名单/NotCalibrated，只说明候选被关闭；它不证明读路径、内部写候选或未来放开后的公共行为通过。可以由统筹独立审阅fail-closed代码是否适合先合入，但激活与发布须另有对应源码和独立证据。工具/性能两路没有产品写接口，也不能继承其他分路原生状态。

## 本分支修复验证

13项本机便携检查通过，包含空属性对空属性、缺少保存/重开、配置遮蔽泄漏、readonly/fresh ID缺失、原件篡改、连续同名begin序号与驱动计时重置。结果仅证明这些反例被结构检查/看门狗拒绝，不是CAD运行证据。不新增baseline dispatch。
