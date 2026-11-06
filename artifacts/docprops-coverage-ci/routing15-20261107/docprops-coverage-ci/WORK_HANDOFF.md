# 文档属性覆盖 / CI 交接

- 唯一工作树：`/Users/YJBeetle/.codex/worktrees/docprops-coverage-ci/SWCLI`
- 分支：`codex/docprops-coverage-ci`；基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 只读盘点 main、主集成树和另外9个工作树。盘点时主集成树存在未提交修改；没有修改、合并或验收它们。快照见 `docs/verification/docprops-worktree-inventory.json`。
- 版本化矩阵 `docs/verification/docprops-capabilities-v1.json` 覆盖11个基线公共操作和15项独立分工；新分支全部未验收。`1593330` 仅本地未验收快照。
- 新增固定计划 baseline-properties 的单次驱动、600秒 native/1800秒整体看门狗、严格原件审计器、可复用独立workflow模板。
- 现有 CI 新增默认关闭 `docprops_targeted` / `docprops_expected_head`；仅本分支手动运行；启用时跳过 test/package，禁止与 native_full 同时运行，沿用既有原生安装器。没有更改现有PR机密隔离规则。
- 原始 report/trace/保存副本/stdout/stderr/driver 与 hash 审计保留90天；基础设施清理回执单列，不能冒充原生正常退出。内部校准始终 `full_acceptance_eligible=false`。
- 没有修改产品功能/写入边界，没有操作Windows VM、SOLIDWORKS用户实例、DockerSW或MacSW，没有发布/合入main。

## 便携验证

本机 Python 3.15，独立临时venv：新增8项（11个操作跨CLI/SDK/MCP上下文），文档97项，SDK11项，MCP18项（2项可选SDK跳过），annotation CI接线4项（2项可选SDK跳过）均通过。JSON/YAML解析、diff --check通过。
看门狗测试模拟 native/整体超时，确认只启动一次并终止子驱动、不重试、不宣称宿主退出。
这些是便携/接线证据，不是公共原生验收。

## 提交与原生校准

代码提交将用中文说明并推送本分支；为避免push自动触发无关CI使用 `[skip ci]`。
随后只手动调用一次现有 ci.yml，参数 docprops_targeted=true、native_full=false、docprops_expected_head=精确代码提交。
CI链接/head/最终状态和持久产物将在本节续记。未取得报告前，原生校准与新增写入验收均不成立。

## 已推送代码与唯一校准运行

- 代码提交：`7f7a4af80d6f731e9a625f6033b4ca496e876f94`，已推送 origin。
- [CI 42260050176](https://github.com/YJBeetle/SWCLI/actions/runs/42260050176)，attempt 1，workflow_dispatch。
- 参数：`docprops_targeted=true`、`docprops_expected_head=7f7a4af80d6f731e9a625f6033b4ca496e876f94`、`native_full=false`。
- GitHub已核head匹配；基础test/package、完整原生与发布job均 skipped，docprops-targeted曾等待共享并发队列，现已cancelled。
- 最终状态 cancelled（并发等待被替换，steps=[]），无原生报告/trace/保存副本可审计，不能标为原生通过。运行记录：`artifacts/docprops-coverage-ci/run.json`。
- 已保存取消run/jobs/check/annotations/artifacts原始元数据及SHA256；没有原始artifact ZIP可下载，不重复触发。

## 统筹读取的契约与合并信息（15对话更新）

本分支不新增产品 operation，不修改产品 CLI/schema/SDK/MCP 文件。下表是用于便携接线覆盖的**既有基线**公共契约；没有新写入原生验收声明。

| operation | CLI 入口 | schema 参数字段 | SDK 方法 |
| --- | --- | --- | --- |
| `document.summary` | `swcli document summary` | 无 | `client.document.summary()` |
| `document.summary-set` | `swcli document summary-set` | `field`, `value`, `expected_value` | `client.document.summary_set()` |
| `document.properties` | `swcli document properties` | `name`, `configuration` | `client.document.properties()` |
| `document.property-summary` | `swcli document property-summary` | `name` | `client.document.property_summary()` |
| `document.property-add` | `swcli document property-add` | `name`, `configuration`, `type`, `value` | `client.document.property_add()` |
| `document.property-set` | `swcli document property-set` | `name`, `configuration`, `value`, `expected_value` | `client.document.property_set()` |
| `document.property-delete` | `swcli document property-delete` | `name`, `configuration`, `expected_value` | `client.document.property_delete()` |
| `document.units` | `swcli document units` | 无 | `client.document.units()` |
| `document.units-set` | `swcli document units-set` | `length_unit`, `decimal_places`, `expected_length_unit`, `expected_decimal_places` | `client.document.units_set()` |
| `document.annotation-options` | `swcli document annotation-options` | 无 | `client.document.annotation_options()` |
| `document.annotation-option-set` | `swcli document annotation-option-set` | `field`, `value`, `expected_value` | `client.document.annotation_option_set()` |

全部操作的文档上下文：`document_id`（CLI `--document`）、`expected_update_stamp`（`--if-update-stamp`）；写操作另带 `lease_id`（`--lease`）。MCP 使用稳定的 `execute`，传 `operation`、`parameters` 和同名上下文字段，不为每个 operation 新增工具。矩阵测试覆盖 Unicode、空字符串、0/false、配置、完整给定值与上下文传递；底层写保护及原生正确性仍由对应产品门禁负责。

本分支命令（内部工具，不是新增公共产品接口）：

- `python scripts/ci/run-docprops-targeted.py --output DIR --expected-head SHA --swconst TLB`：固定 baseline-properties 计划，单次运行。
- `python scripts/ci/audit-docprops-calibration.py --evidence DIR --expected-head SHA`：严格审计同一计划原件，不能用于其他分支格式。
- CI `ci.yml` 的 `docprops_targeted:boolean=false`、`docprops_expected_head:string`；实际分派同时明确 `native_full=false`。

共享文件改动只有 `.github/workflows/ci.yml`：增加上述两个 input、test/package 的定向跳过条件、单个 branch-only job；原 full/release 条件和 PR secrets 隔离保持。独立新增文件是审计器、驱动、模板、便携测试、版本化矩阵、初始只读快照、说明文档、run记录和本交接。产品 `src/swcli/{cli,operation_schemas,result_schemas,sdk,mcp}` 均未修改。统筹合并时需要协调各分支 ci.yml input/job 与各自独立 profile+ref concurrency group，但本分支不合入其他分支。

依赖：已存在的 `verify-properties-calibration.py` / `verify-through-all-calibration.py` 与 hosted Windows 安装脚本；不依赖任何未验收产品分支。模板只适用当前固定properties报告契约，其他14个分工必须提供自己的计划、报告语义与专用审计器。原生读写API沿用既有基线，本分支没有新COM API映射或未经核实的官方能力声明。

已按主对话提供索引补齐15项负责人映射，但未重新读取/评定其他分支代码。新增稳定引用、配合、旋转、STL和STEP全部保持未验收。GLB/image-quality仍属于docprops-export-options；STL/STEP需要各自格式类型结构，不能据其参数推定GLB支持。若使用宿主全局偏好，验收清单额外要求独占/会话隔离、原偏好保存、精确读回、单次导出、finally恢复并核验以及保留首次业务失败；本模板不自动提供这些产品能力。

唯一校准42260050176（head 7f7a4af）最终cancelled，未执行CAD；后续文档提交不替代校准head。代码提交后的9878762仅记录交接与run信息。

## 取消事实、修复和停止重复CAD校准

- GitHub最终记录：run completed/cancelled，更新时间 `2026-11-06T17:20:41Z`（北京时间11月7日01:20:41）。此前交接里的pending是过期快照，现已更正。
- check annotation首因：`Canceling since a higher priority waiting request for swcli-hosted-windows-solidworks exists`。不是推定CAD错误；job steps为空，artifacts为0，job日志端点HTTP404。
- 原始run/jobs/check/annotations/artifacts API响应及日志请求结果：`artifacts/docprops-coverage-ci/cancelled-42260050176/`，`SHA256.json`核每个元数据原件；`run.json`同步最终状态。
- 只修改专属docprops-targeted job与其模板的并发组为 `swcli-docprops-baseline-properties-${{ github.ref }}`，保留 `cancel-in-progress=false`；默认完整原生的 `swcli-hosted-windows-solidworks` 与release组原样保留。接线测试新增回归断言。
- 实际计划只运行已有 `verify-properties-calibration.py`，覆盖基线document.properties的零件/装配读、Unicode/空值/配置遮蔽、后台状态、保存只读重开、单owned宿主及退出。样件准备会使用既有Add3，但不新增产品写功能。不运行真实公共CLI/SDK/MCP原生通路，不覆盖其余分支产品。
- 本分支是验收矩阵/工具工作，产品没有变化。为避免只验证验收工具重复运行既有CAD，**不重新dispatch**。并发修复仅有便携接线证据；原生采集/审计链仍未经本次实跑，不能称已原生验收。后续由统筹在真正产品head的必要专用计划中复用模板。

本次并发修复验证：`test_docprops_coverage_ci.py` 全部8项通过（含专属group、模板一致、默认full/release组保留断言），两个YAML解析及`git diff --check`通过。没有新dispatch。
