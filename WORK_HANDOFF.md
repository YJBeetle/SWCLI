# 工程图出详图默认选项：merge-ready 交接

## 最新统筹状态与授权

- 用户继续统筹推进的授权已确认：本路已通过限定范围验收，可由主对话先行审查合并，无需等待其他任务。
- **待审批动作：无。** 先前工作树写入授权已解决，不重复申请；本路实现、中文提交推送、定向 Windows 内部校准及公开 gate 均已完成。
- 当前仅等待主对话处理主线集成。本线程不自行合 main、不发布；如统筹反馈本路相关集成问题，可在既定范围继续修复和必要验证，不因常规推进再次等待确认。
- 本次仅补交接状态，运行时代码仍与已验收 `85f99da` 完全一致，无需重复测试或 dispatch。

## 当前结论与精确提交

- **MERGE_READY=true，仅限下述两个文档标量。** 主对话统一审查集成；本线程没有合并 main、发布或操作本地 Windows VM，也没有修改 DockerSW/MacSW。
- 唯一工作树：`/Users/YJBeetle/.codex/worktrees/docprops-detailing/SWCLI`；分支 `codex/docprops-detailing`。
- 基线：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`。精确可合代码 commit / 最终公开验收 head：`85f99dac08c768794cead88cc3755ad60c77a1d2`。
- 集成时取基线至该 commit 的完整线性实现范围，不能只 cherry-pick 最后一个修复。该 commit 后仅有交接/证据 Markdown/JSON 更新，可一并审查分支 tip；最终 tip 另记录在持久 `artifacts/detailing/merge-ready.json`。
- 起始工作树 clean，无 `.codegraph`；遵循用户注入及祖先 AGENTS.md，没有引入或合并其他未验收分支。

## 精确验收范围与接口 diff

- 两项：`auto_center_marks.part_holes`、`auto_center_marks.part_fillets`。官方分别映射 `swDetailingAutoInsertCenterMarksForHoles` / `swDetailingAutoInsertCenterMarksForFillets`，文档级 `IModelDocExtension.Get/SetUserPreferenceToggle` + `swDetailingNoOptionSpecified`。
- `document.detailing-options` / `swcli document detailing-options`：返回完整 `options` 两布尔快照。
- `document.detailing-option-set` / `swcli document detailing-option-set FIELD true|false --if-options JSON`：参数 `field/value/expected_options`；旧值必须为完整两值 CAS；`document_id/expected_update_stamp/lease_id` 均必需。
- 回执 `field/before/options/changed/mutation/native_return`；失败可只有部分结果。相同值 no-op 不调用 setter。setter 已尝试后即使最终文档描述失败仍保留 mutation 回执；无原生失败重试、错误自动回滚或组内宿主重启。
- SDK：`client.document.detailing_options()` / `.detailing_option_set(...)`；MCP 通过已有 capabilities/execute 契约暴露，不新增任意 COM 字典入口。
- 变更写入只开放 **原生 Windows + SOLIDWORKS `33.5.0`**；Wine、其他版本、未知运行时 fail closed。读取或无 mutation no-op 不代表其他环境的变更写入验收。
- 保护：read-only/view-only、普通图纸而非格式/活动视图/外来草图、完整 CAS、前台/后台、文档身份、dirty/stamp 与不请求字段保持。只写未来视图的文档默认值，不插入实体/视图，不改总体标准、字体、公差。

## 便携与包证据

- 修复候选本地完整便携测试 **1839 项成功，32 项按环境跳过**；相关 **20 项成功**。含真实 adapter instrumentation 的平面调用顺序回归、启动失败首错误报告持久化，以及四次公开保存重开的控制流/首失败停止/缺 trace/丢值拒绝。
- SDK generator `--check`、strict SDK implementation、8 个消费者 typing 拒绝检查通过。
- 同 head Windows 自动 CI：[42268553295](https://github.com/YJBeetle/SWCLI/actions/runs/42268553295)，Python 3.9 / 3.14、SDK/MCP 便携契约与 wheel 检查成功。
- 持久本地日志及 hash 回执：`artifacts/detailing/portable/unittest-public-fixed.log`、`associated-public-fixed.log`、`fixed-candidate-receipt.json`、`run-42268553295.json`。这些只是便携/包证据，不冒充真实 CAD 验收。

## 内部原生校准（独立核原产物）

- run：[42260661085](https://github.com/YJBeetle/SWCLI/actions/runs/42260661085)，head `5c878c3b13f7811d50af94fca53a4d471cc5669c`，参数 `detailing_calibration=true/native_full=false`，成功。
- 官方 swconst 解析孔 308 / 圆角 309 / NoOption 0。代码从宿主旁的官方类型库解析符号，不猜数字。
- 原 artifact `13526235874`，ZIP SHA256 `e744654c2946f79155f138143878c141f1f596bc2ee6cf43f759531381f86faa` 与 GitHub digest 一致。
- 单独拥有 hidden host `33.5.0`，实际校准约 16 秒；四次 true/false、逐次保存/只读重开、完整值、图纸布局/投影/无关注解、read-only 拒绝及宿主退出检查成功。
- 原 ZIP/未改写解包/独立核验位于 `artifacts/detailing/internal-42260661085/`；版本化 hash/trace/文件回执 `docs/evidence/detailing-internal-42260661085.json`。

## 最终公开 CLI/daemon 验收（独立核原产物）

- run：[42268599270](https://github.com/YJBeetle/SWCLI/actions/runs/42268599270)，head **`85f99dac08c768794cead88cc3755ad60c77a1d2`**；参数 `detailing_public_gate=true/detailing_calibration=false/native_full=false`，成功。
- 原 artifact `13529511630`；ZIP SHA256 **`568003c8475a5be47a90d27e50372a8dac047dd275fd9848467ec690367b960e`** 与 GitHub digest 一致。
- 独立审计脚本不导入 SWCLI/gate 代码，核对 run/head/digest、**39 个请求完整 native trace、4 次 setter、4 个独立保存重开文件 hash、8 个不复用文档身份**，以及 lease/stamp/完整 CAS/read-only 拒绝和 no-op。
- typed SDK read/no-op、真实 daemon 的 MCP bridge capabilities/no-op 回执与原 trace 一致。MCP stdio 只属于便携协议契约，不冒称为此 run 的真实 stdio CAD 证据。
- 同一独占 hidden Windows host/worker，revision `33.5.0`；实际组耗时约 **52 秒**，600 秒调用/1800 秒组预算、清理与 daemon 正常退出检查通过。
- report SHA256 `e4fc06859979c79eebca71574b53195fec6e6d9ded82b1ce4ee60b0e6da3689d`；trace SHA256 `005b465ef0157a7dfd0a2ed21fe9b4fcb79e5a84542a77f3296dc1bdc2360242`。
- 原 ZIP/解包/审计回执：`artifacts/detailing/public-42268599270/`；独立复核脚本 `artifacts/detailing/verify_public_artifact.py`；完整版本化回执与逐文件 hash：`docs/evidence/detailing-public-42268599270.json`。

## 保留的首次公开失败

- [42264404958](https://github.com/YJBeetle/SWCLI/actions/runs/42264404958) / head `732f7111bd3cf14c2da5c682ac23f029a956a7d1` **失败，不能作为验收**。
- 原 ZIP `artifacts/detailing/public-42264404958/original.zip`；artifact `13527078689`，SHA256 `a281d33f8559a8717ae28fa763bf5661edc184d7009081d683e66abc60a34869`。
- 首失败由原 trace 重现：setter trace 内嵌 Extension getter，严格顺序断言拒绝。仅 1 次 setter，成功返回 True；未重试、未回滚、未执行保存重开。另有报告未初始化导致 checkpoint 丢失汇总，原 journal/trace 保留。
- `85f99da` 移出 Extension getter、预建报告并增加回归；没有放宽断言。仅在该相关修复后启动一次新公开验证。历史失败摘要：`docs/evidence/detailing-public-42264404958-failure.json`。

## 共享改动、依赖与未完成边界

- 共享文件：`src/swcli/cli.py`、`daemon/operations.py`、`operation_schemas.py`、`result_schemas.py`、`sdk/_generated.py`、`sdk/models.py`、`.github/workflows/ci.yml`、`.gitignore`。
- `_operation.lease_guarded` 支持 required 和 optional，确保必需 lease 的新操作真正进入 registry 校验；原 optional 行为保持。集成冲突时请保留该保护。
- 新 catalog/adapter、三组测试、内部/公开 gate/watchdog、设计说明和三份成功/失败证据 JSON；复用现有 annotations 图纸上下文 guard 与 custom-properties 状态保护。
- 两个 CI 输入默认关闭、互斥、仅本分支 workflow_dispatch；专属模式跳过通用 test/package/full-native/release，不进入其共享 concurrency，不增加 PR secrets 权限。
- 不依赖其他未验收分支；Windows 依赖官方 swconst、明确 GB DRWDOT 和已有私有安装设施。
- 实测为生成的空 GB A4 工程图，验收标量存储、保护和保存重开；未验证新建模型视图时实际自动插入标记效果，也未扩大到其他工程图字段、标准/字体/公差、其他版本/Wine、完整建模 suite 或 release gate。报告 full_acceptance_eligible=false 保留，不能用于发布验收。
