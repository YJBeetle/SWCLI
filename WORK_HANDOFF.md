# 文档属性覆盖 / CI 交接

- 唯一工作树：`/Users/YJBeetle/.codex/worktrees/docprops-coverage-ci/SWCLI`
- 分支：`codex/docprops-coverage-ci`；基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 只读盘点 main、主集成树和另外9个工作树。盘点时主集成树存在未提交修改；没有修改、合并或验收它们。快照见 `docs/verification/docprops-worktree-inventory.json`。
- 版本化矩阵 `docs/verification/docprops-capabilities-v1.json` 覆盖11个基线公共操作和15项独立分工；新分支全部未验收。`1593330` 仅本地未验收快照。
- 新增固定计划 baseline-properties 的单次驱动、600秒 native/1800秒整体看门狗、严格原件结构检查器、可复用独立workflow模板。
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
- `python scripts/ci/audit-docprops-calibration.py --evidence DIR --expected-head SHA`：检查同一计划原件结构，不能用于其他分支格式。
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

## 15路静态审查与审计假阳性修复（最新）

- 主对话审查确认旧审计器可被空属性相等和仅清理trace骗过；旧正样本无效，不应解释为原生通过。
- 已严格要求baseline五属性、所有查询/missing/空值/配置遮蔽、后台状态、fresh readonly reopen身份、完整固定调用顺序和保存文件外形/hash。输出降格为`evidence-structure-only`，去掉success，恒定`calibration_passed=false`和`source_provenance_verified=false`；driver自报head不作来源证明。
- driver.pending使用begin行序号+call名称区分连续同名调用；驱动循环测试证实第二个同名begin重置600秒预算。
- 本轮13项定向便携检查通过，含主对话要求的两项关键否定样本；没有新dispatch。旧的8项记录是历史测试数，不代表当前审计契约。
- 15路CI审查报告：`docs/verification/docprops-routing-review-2026-11-07.md`。
- 分层矩阵：`docs/verification/docprops-merge-evidence-v1.json`，包含internal/public/sourceSHA/artifact digest/portable/SDK/MCP和写门禁，均不自动标可发布。
- 只读快照与原始GitHub运行/jobs/artifacts元数据及SHA256：`artifacts/docprops-coverage-ci/routing15-20261107/`。工作文件hash与HEAD分开记录；其他工作树持续变化，报告是时点快照。
- 交统筹具体问题：线型复用full job却缺ref并发；表格独立job静态组复用前加ref；公差/线型/单位/STEP缺targeted与native_full互斥早拒；单位旧run仍使用旧共享group，不能把新配置追认给旧run。仅报告，不改其他worktree。
- 在本路11月7日01:32开始的审查快照中，尚未取得各分路的原生原ZIP独立digest与公共验收通过证据；GitHub已有dist/portable/package artifact摘要单独标metadata-only，不能作为native。各路本地SDK/便携结论注明handoff claim，没有在本分支代跑其测试。

本轮技术提交：`7f279206bd695437f527fd8fa40d3330d5366e4b`（已推送）；包括结构检查降格/否定测试、begin序号计时和15路路由/证据报告。13项测试通过；无新增native dispatch，旧取消run不变。

## 本轮持续授权与当前交接状态

用户经主对话明确延续各自分支实现、中文提交推送至YJBeetle/SWCLI、必要定向Windows校准/公共验收的授权；精确能力通过严格核验后可在开发分支开放供公共gate，最终合main由主对话办理。本路没有新增产品写能力，故无待开放白名单或待审批gate。

- 本路待审批动作：**无**。此前本路的提交/推送均已完成，没有未解决自动审批拒绝，不重复请求常规推进确认。
- 当前可审查交付：技术提交`7f279206bd695437f527fd8fa40d3330d5366e4b`，13项定向便携测试通过；结构检查不构成原生校准通过，15路报告是固定时点证据，不是其他分支的实时状态。
- 后续范围：由主对话读取本路报告、复核具体问题和决定单路滚动集成。本路不合他人分支、不改他人worktree、不重复baseline CAD dispatch；如需更新某个精确产品head的证据审阅，沿用只读来源核验。
- VM仍暂停，DockerSW/MacSW、凭据保护、原断言及自动审批边界保持。持续授权不替代实际原生/public验收证据。

## manual native scope窄审查（本轮，只读）

- 报告：`docs/verification/docprops-manual-routing-narrow-2026-11-07.md`。原始15路workflow、精确SHA/行号/完整布尔组合、远端main元数据与hash：`artifacts/docprops-coverage-ci/manual-routing-narrow-20261107/`。
- 线型a783b498：错误ref或manual tag，native_full=true + line_font_calibration/public=true，会job放行却跳过全部CAD入口，summary直接exit0。精确ci.yml行248、396/407、418/430/444、477起，交主对话协调owner修。
- 公差ce147cba同类问题仍在快照内，已由主对话交原owner，不重复代修。
- 单位在审查期间更新9d6b033；units-route及native needs/if已阻断旧路径。保存并执行其精确head的纯路由函数副本，未在他人树运行测试/写pycache。旧观察不冒充当前缺陷。
- STEP 2c7108fa：own ref下full+targeted仍可忽略full而执行targeted；wrong ref/两targeted同时true会native job skipped，未复现零CAD native-job success。与线型风险分级区分。
- 其余复用full job者：topology/revolve/STL有明确互斥throw；image-quality job条件排除混合scope。15路正常push-tag空输入均保留full CAD路径；manual-dispatch到tag带输入，与push tag区分。
- GitHub只读核远端main=83c48301414801540a29aefca2d7d1f9f174d3c1；本地main ref仍78ebaf6。未来集成须保留83c4830的detailing和78ebaf6先前修复。本路不改main ref、不合分支、不dispatch、不轮询旧CI。以上只有静态/纯路由证据，没有新的原生验收结论。

## 路由增量 + 跨路partial/peer缺陷（本轮）

- 线型精确bc619f372f9863c9654080e3a0492d994a3898e0：56路由组合与4项复制测试通过，test前置拒绝与native needs.test成功依赖已核，旧零CAD空绿结论被此修复替代（仅路由范围）。
- STEP工作区修复3456组路由组合通过，但HEAD仍2c7108f且修复未提交，已固定两文件hash，不宣称精确新head通过；owner计划随下个实质/public head提交，不重复CAD。报告`docs/verification/docprops-routing-increment-2026-11-07.md`。
- 新只读缺陷报告：`docs/verification/docprops-handler-peer-review-2026-11-07.md`，持久实证`artifacts/docprops-coverage-ci/handler-peer-review/`。
- 精确head mock证实line bc619f3、dimension441b45d、table b4f7911、units9d6b033、image-quality0f4ba7b五路handler在adapter返回mutation后describe抛错会传播异常、丢失回执；worker generic error静态链不携带该result。adapter成功为mock注入，不称native实证。
- 真实adapter+Mock COM peer注入：线型/尺寸/单位/图像品质在另一个前台文档指针不变但stamp/dirty/title/path改变时各4例仍ok=true（16个mock假阳性）；表格4例正确ok=false且partial保留。表格已有foreground_state/identity保护，不重复报该peer缺陷。
- 既有测试覆盖和缺口、精确handler/helper/worker/guard行号均写报告。公差/字体owner已接修复不重复指派；detailing main保护不受旧分支结论外推。
- STL/STEP export和配合handler直接返回adapter；旋转register_feature失败保留result，只做static排除同形_with_document点，不声称其他partial/peer路径已验收。
- 全过程只在本worktree或隔离源码副本执行纯Python mock，不修改其他worktree、不用VM/COM、不dispatch、不扩产品白名单。交主对话按精确head协调owner修复。

## 主集成基线更新（统筹通报，2026-11-07）

- 主对话通报main已推进至`0e72beb15a2266a79fd9931c80a157531c9ab42f`，已合旋转`3922bee`，保留先前detailing和78ebaf6修复；新增统一无secret预检`scripts/ci/validate-native-profile.py`。后续增量审查以该基线及之后的精确提交为参照，不把本路旧315组/窄审查结果描述为当前main缺陷。
- 主对话报告旋转原件已独立核验、组合1871项通过/32跳过、SDK及480组路由组合通过，release/tag-policy/permissions保留。本段是统筹提供的状态，本路未重新核验这些原件或代跑组合测试，不增加自己的原生验收声明。
- 跨路mutation/peer报告已由统筹分发5个owner，各自修复。本路保留原精确head源码/JSON/stdout/hash，不代改owner、不要求现在rebase/重跑；主对话合并时统一整合。
- 当前没有新CAD、dispatch、合并或待审批动作。原本路取消运行42260050176及结构检查边界不变；未来若复核owner修复，将单独固定新head和证据，不覆盖历史反例。
