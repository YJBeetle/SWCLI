# 文档级尺寸公差默认设置交接

## 状态与范围

- 独立工作树：`/Users/YJBeetle/.codex/worktrees/docprops-tolerances/SWCLI`
- 分支：`codex/docprops-tolerances`；起点 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 仅 Dimensions > Linear 文档默认公差类型/精度；未访问 IDimension、IDimensionTolerance 或模型特征尺寸值。
- **当前公开验收候选**：内部原生及独立artifact审计通过后，仅 revision33.5.0、类型none/basic、precision0/3/8及已证实旧值开放本分支写入；其余含noop拒绝。公开gate待完成，统筹代码审查发现边界阻断，当前修复后须最终head重验，不发布。历史关闭状态及失败保留在下文。
- 未使用本地 VM/SOLIDWORKS；未改 main、DockerSW、MacSW 或其他工作树；没有合入其他分支。

## 操作与契约

| 操作 | CLI / SDK | 参数和结果 |
| --- | --- | --- |
| `document.tolerances` | `swcli document tolerances` / `client.document.tolerances` | 无业务参数；可选 document_id、expected_update_stamp；返回 scope=`document_defaults_linear`、options、write_enabled |
| `document.tolerance-set` | `swcli document tolerance-set FIELD VALUE --if-options JSON` / `client.document.tolerance_set` | field=`linear.type` 或 `linear.precision`；value 字符串；完整 expected_options；**强制 document_id、expected_update_stamp、lease_id**；返回 before/options/changed 与 mutation.attempted/may_have_changed |

`options` 固定含 `linear.type`、`linear.precision`，每项为 `{value, native_value}`。
候选类型只写 `none/basic`；精度只写字符串 `0/3/8`。旧值限定类型none/basic、精度follow_nominal/0/3/8。读取保留已知类型映射，精度 -3 映射
follow_nominal，未知原生整数用 other 保留。CAS 比较两个字段的完整语义值与原生整数。
没有任意 COM 参数、数字偏好编号或校准开关的公开入口。

保护沿用 lease、只读/仅查看、后台不激活、前台/配置/工程图编辑上下文与状态核对。
原生 setter 最多一次；失败不重试/回滚；读回变化不修补；部分 mutation 回执保留。

## 官方 API 与边界

- [Dimension Tolerance](https://help.solidworks.com/2023/English/api/swconst/DP_DimensionTolerance.htm)：IModelDocExtension Get/SetUserPreferenceInteger，swDetailingToleranceStyle + swDetailingLinearDimension。
- [Linear](https://help.solidworks.com/2023/english/api/swconst/DP_Dimensions-Linear.htm)：swDetailingLinearTolPrecision + swDetailingLinearDimension。
- [swTolType_e](https://help.solidworks.com/2024/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTolType_e.html)：类型值依据。
- [swDimensionPrecisionSettings_e](https://help.solidworks.com/2015/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDimensionPrecisionSettings_e.html)：-3 跟随尺寸精度，-1/-2 不写入文档默认。
- 偏好编号/Linear option 从安装的官方 swconst.tlb 按名称解析，缺失/重复/类型不符报错，不猜测数字。
- 不支持其他尺寸类别、上下偏差、配合、字体、双尺寸、继承开关、单尺寸覆盖。

## 文件与集成注意

新增独立实现：`src/swcli/document_tolerances.py`、`src/swcli/hosts/windows_document_tolerances.py`。
共享文件改动：`src/swcli/cli.py`、`daemon/operations.py`、`operation_schemas.py`、
`result_schemas.py`、`sdk/_generated.py`、`sdk/models.py`、产品 skill 的 `references/usage.md`、
`.github/workflows/ci.yml` 与 `tests/test_modeling_sequence.py` 的唯一校准输入例外。SDK 应在主集成解决目录冲突后重新生成。

`_operation` 的 lease_guarded 判定扩充为 optional/required 均保护，以支持本操作强制 lease；
其他既有操作上下文声明未变。公差依赖现有 annotation adapter 的编辑上下文检查函数。

新增 `scripts/ci/verify-tolerance-calibration.py` 复用 existing owned-host harness，生成 part/assembly/drawing。
通过测试进程局部 patch 开启候选引擎；分发包/请求/环境变量不能开启公开写入。
原生操作600秒、组1800秒、首失败停止、无 API 重试/自动回滚/组内宿主重启。
保留原始 report.json、trace.jsonl、worker 日志、原生 fixture 和摘要。

CI 使用既有 `ci.yml` 新增默认关闭 `calibrate_tolerances`，仅本分支 workflow_dispatch 可触发。
使用该开关时跳过 property/annotation fixture 和完整 CAD smoke，摘要明确 internal-only、
full_acceptance_eligible=false；不改变 PR secrets 规则或 release/tag 条件。

## 验证与提交

- 公差/接线便携测试：15 项通过（模拟 COM，不是原生验收）。
- SDK generator --check、strict SDK/消费者 typing 检查通过。
- installed CLI/schema/product skill 资源检查通过（未激活 COM）。
- workflow YAML/新增 Python AST 解析通过；git diff --check 通过。
- 全套便携测试：1833 项通过，32 项跳过（macOS / Python 3.15.2，专用隔离 venv）；之后新增一项 watchdog 行为测试，最终公差相关15项通过。初次环境/接线失败已修正，不属于原生失败。
- 原始便携日志与摘要保存在 `evidence/portable/`（持久本地证据，不纳入实现提交）。
- 实现提交：`27dc93077791359ded7296abee240f06350db51d`（已推送；提交消息含 skip ci，避免重复 push CI）。
- Windows CI：[run 42261066525](https://github.com/YJBeetle/SWCLI/actions/runs/42261066525)，**首轮失败；未重复 dispatch**。Windows Python 3.9/3.14 便携作业与 wheel 均通过。
- 精确测试 head：`27dc93077791359ded7296abee240f06350db51d`；ref=`codex/docprops-tolerances`；`calibrate_tolerances=true`、`native_full=false`、`cleanup_profile=auto`、`vfs_cache_gib=8`；media/assets 使用 workflow 既有默认值。
- `evidence/dispatch-parameters.json` 与 `dispatch-submitted.json` 保存请求/head；初始状态保存为 `evidence/run-42261066525.initial.json`。未记录任何凭据。
- 远端 origin 已验证为公开 `https://github.com/YJBeetle/SWCLI.git`，当前用户 ADMIN；初次网络审批要求核实目的地，核实后重试已获准并完成推送/dispatch。

## 待完成与验收边界

取得并保全对应原生 run/head/参数和首真实失败（若有）；排队不是失败，不重复 dispatch。
即使内部校准通过，也仍缺少公开 CLI/MCP/SDK 端到端写入验收，公开写入不得据此开启。
主对话统一处理集成冲突、公开 gate 与后续发布；本分支不合 main、不发布。

## 首轮原生失败与后续公开 gate 准备

- 原生 head `27dc93077791359ded7296abee240f06350db51d`；原 ZIP artifact `13525731977`。
- SHA-256 `bf1f00be3b91ae53d289799aa27c57545a540e14eddb59e23cbc811c893e5ff8`，已逐字匹配 GitHub artifact digest。原 ZIP、解压内容、run/artifact metadata、独立核查 JSON 均在 `evidence/run-42261066525/`。
- 第一真实失败：part 的 `document defaults changed model geometry`，触发新增 metrics 整字典逐位相等比较。体积11999.999999999998 mm³、面积3799.9999999999995 mm² 前后逐位一致；仅质心Y从5.514537417020185e-16变为8.271806125530278e-16 mm，差2.757268708510093e-16 mm。两次解析体积/面积检查均通过，但整组仍失败。
- 原生 trace 独立核对13个request的完整边界、顺序与单一worker；5次setter、5次noop、44次偏好getter、0次SetSaveFlag（该生成零件在创建几何后已为dirty）；无原生调用异常，无清理错误。文档stamp保持163，说明完整值CAS确有必要。
- **不能算通过**：未到part保存重开；assembly/drawing未开始。公开写入保持关闭。
- 用户原要求“不放宽几何或状态断言”；已异步请求用户明确选择：维持质心逐位相等，或仅允许质心绝对误差≤1e-12 mm并保留体积/面积逐位相等与原解析断言。未获答复前不修改该断言、不发起新原生验证。
- 已按统筹新要求准备 `verify-document-tolerances.py`：公开CLI→daemon，保存副本/只读重开/hash、后台/lease/stamp/完整CAS/noop、原生trace顺序和零setter证明；SDK typed读/noop及MCP bridge发现/读/noop走同一daemon。MCP stdio协议本身沿用既有便携契约测试，不把bridge实测冒充stdio握手验收。
- `accept_tolerances` 新增默认关闭且仅本分支手动；独立concurrency；wrapper使用初始隐藏daemon，专属gate后停止并验证生命周期，不进入full/release其他组。尚未dispatch公开验收，当前引擎关闭导致其不能误报成功。
- 新公开gate便携故障注入通过，公差相关共18项；关联CI接线7项（2跳过）、modeling sequence12项（1跳过）通过。并未为统筹消息重复全套测试。
- 后续若内部完整证据通过，拟只开放实际逐项证明的none/basic及precision=0/3/8；其他可读精度不因边界点通过而自动开放。然后做一次必要公开验收，核原始证据后再给主对话merge-ready commit。

- 供用户具体审阅但**尚未应用**的判据补丁：`evidence/proposed-centroid-criterion.patch`；仅质心≤1e-12 mm，同时新增(0,0,5) mm解析质心检查；体积/面积/实体数逐位相等及原解析体积/面积断言保留。公开gate后续也须与获准判据一致。

- 公开gate准备及首失败记录提交：`510f421d470c58cd73d1bd58ee3b08cd096e8816`，已推送。当前无 merge-ready commit；原生判据待用户明确选择，公开写入白名单仍空。此条为本地实时交接补充。

## 用户批准的唯一几何判据例外（2026-11-07）

用户明确答复“允许仅此质心误差界限”。内部与公开gate统一采用质心绝对误差≤1e-12 mm；体积、面积、实体数逐位相等和原解析体积/面积检查保留，并新增(0,0,5) mm解析质心检查。未放宽任何状态断言。该例外不适用于其他几何值或其他线程。关联边界/one-ULP/非有限值测试已补充；测试通过后将对修复head进行一次必要内部校准。公开写入仍关闭。

- 第二轮内部校准：[run 42266358630](https://github.com/YJBeetle/SWCLI/actions/runs/42266358630)，head `252ad8b86ddebc282b94ee765199f9bcec38e088`；calibrate_tolerances=true、accept_tolerances=false、native_full=false、cleanup_profile=auto、vfs_cache_gib=8；本修复head仅dispatch一次。请求与回执在 `evidence/calibration-r2/`。

## 第二轮内部原生审计通过，公开验收准备中

- run `42266358630` / head `252ad8b86ddebc282b94ee765199f9bcec38e088`：三个文档类型均完成5次真实setter、5次noop、完整值CAS拒绝、保存与只读重开及只读拒写，45个request完整且同一worker。
- 原ZIP SHA-256 `89164b4642dc4c5d4167e1f97e30eab89945bf2583cdc804ce18708794b86285`，匹配GitHub artifact digest；审计摘要 `evidence/run-42266358630/audit.json`。138次偏好getter、15次setter；trace整组10.81秒，最大span2.60秒，未超600/1800秒，无清理错误。实际native revision `33.5.0`。
- 新审计器曾误加未有依据的原生文件头假设；已移除该假设，改核实际原生保存/只读重开断言、最小尺寸与精确摘要；几何/状态/trace断言未减弱。内部冻结脚本校验readonly=true但未单独保留open raw receipt，公开gate将逐个保留原始open回执。
- 为公开验收仅开放 revision33.5.0、none/basic、precision0/3/8，旧值限定none/basic与follow_nominal/0/3/8；其他版本/值及未知旧值含noop均拒绝。该开发分支尚未完成公开验收，不算merge-ready，不发布。
- 公开gate扩为每种文档三个保存重开profile：basic/0、basic/8、none/3；同时覆盖两种类型下各精度的内存往返、所有原源/前次副本hash、干净noop、只读拒绝、CLI/SDK/MCP bridge原始回执与trace。

- 公开候选集成检查：1846项全套便携测试通过、32项跳过；SDK generator/strict typing/8项负例与installed resources通过；公差相关27项（含固定界限、版本/旧值拒绝、三个持久profile、首失败原回执及SDK/MCP转发）通过。当前即将对公开候选head只dispatch一次accept_tolerances=true，calibrate_tolerances/native_full=false。

- 公开候选提交：`ce147cba0ba43d57408e6ec12a616aea6c1559d1`，已推送。
- 公开验收：[run 42271130456](https://github.com/YJBeetle/SWCLI/actions/runs/42271130456)，测试head同上；accept_tolerances=true、calibrate_tolerances=false、native_full=false、cleanup_profile=auto、vfs_cache_gib=8。本公开head仅dispatch一次，尚未终态，不应合并。请求、内部门槛digest与回执在 `evidence/public-r1/`。

- 统筹最新授权已收到：本分支提交推送、定向校准/公开gate继续自主推进，主对话负责合main。当前无未解决审批；先前origin目的地审批核实后已解决，不重复操作。用户仅批准质心≤1e-12 mm，其他几何/状态冻结要求仍有效；VM/DockerSW/MacSW/凭据边界不变。

## 统筹三项阻断修复（旧ce147cb验收不代替新head）

- 已确认旧公开artifact13532461445 / SHA4729536da9d26060a430127dc1e28393e74a64a2978cdc1b42805170c4ffdbdd真实通过，120请求、30setter、9副本与干净退出均经双方独立核对；旧源wheelfile也匹配ce147cb（distZIP SHA c0a07e2eb68820925923a84a1ffe5b9ff4c0cd7c59d5d8e9d53f32f1e9c7ff8c，wheel SHA0e08a192525811eac1ba755a44cfb05508c6e3c1da9b7d3d1392b7cea0d5d032）。
- 修复native-only：与main83c4830 detailing相同，用ctypes.WinDLL(ntdll)检查wine_get_version；同revision Wine也拒写，未知探测失败关闭。增加平台/native/Wine/探测失败回归。
- 修复CI模式：新无secret native-profile preflight穷举互斥，拒绝错误分支、full+专属、校准+公开；所有CAD步骤只按validated profile选择，private job要求profile job成功与明确白名单值，不能混合开关造成零CAD成功。新增实际CLI/48组合/真实step条件测试。
- 修复最终描述失败：document_tolerance_set捕获_with_document失败，ok=false、保留原before/options/mutation与首业务错误，附第二观察错误，不伪造document；worker后续恢复/验证错误也保留本请求partial receipt，并在每请求前result=None，防串上次mutation。新增真实_worker_main双请求与恢复失败回归。
- 同时补强原有身份约束：目标title/path、后台前台的state和identity全程固定，漂移在写前拒绝；写后漂移保留may_have_changed且不修补。没有放宽任何几何或状态断言。
- 当前未宣称新产品head merge-ready；三项修复提交推送并跑一次最终head公开gate后再交接。主对话负责与main83c4830顺序集成，本线程不合main。

- 最终审查修复便携集成：1858项全套测试通过、32项跳过；12项新增review回归包含worker恢复失败停止、后继请求绝不沿用旧mutation、48个event/ref/布尔参数组合及真实CLI/step条件。SDK generator/strict typing/8项拒绝、installed resources与YAML secret-free preflight依赖检查均通过。接下来冻结修复head，仍只对该head进行一次必要公开gate。
