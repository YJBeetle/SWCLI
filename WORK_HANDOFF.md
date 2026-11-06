# 文档级尺寸公差默认设置交接

## 状态与范围

- 独立工作树：`/Users/YJBeetle/.codex/worktrees/docprops-tolerances/SWCLI`
- 分支：`codex/docprops-tolerances`；起点 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 仅 Dimensions > Linear 文档默认公差类型/精度；未访问 IDimension、IDimensionTolerance 或模型特征尺寸值。
- **公开写入 fail closed**：`PUBLIC_WRITE_FIELDS` 为空，读接口 `write_enabled=false`。包括 no-op 也拒绝。便携测试与内部原生校准均不等于公开端到端验收；不得据此发布或开启写入。
- 未使用本地 VM/SOLIDWORKS；未改 main、DockerSW、MacSW 或其他工作树；没有合入其他分支。

## 操作与契约

| 操作 | CLI / SDK | 参数和结果 |
| --- | --- | --- |
| `document.tolerances` | `swcli document tolerances` / `client.document.tolerances` | 无业务参数；可选 document_id、expected_update_stamp；返回 scope=`document_defaults_linear`、options、write_enabled |
| `document.tolerance-set` | `swcli document tolerance-set FIELD VALUE --if-options JSON` / `client.document.tolerance_set` | field=`linear.type` 或 `linear.precision`；value 字符串；完整 expected_options；**强制 document_id、expected_update_stamp、lease_id**；返回 before/options/changed 与 mutation.attempted/may_have_changed |

`options` 固定含 `linear.type`、`linear.precision`，每项为 `{value, native_value}`。
候选类型只写 `none/basic`；精度只写字符串 `0`–`8`。读取保留已知类型映射，精度 -3 映射
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
- Windows CI：[run 42261066525](https://github.com/YJBeetle/SWCLI/actions/runs/42261066525)，**已且仅已 dispatch 一次，运行中**。
- 精确测试 head：`27dc93077791359ded7296abee240f06350db51d`；ref=`codex/docprops-tolerances`；`calibrate_tolerances=true`、`native_full=false`、`cleanup_profile=auto`、`vfs_cache_gib=8`；media/assets 使用 workflow 既有默认值。
- `evidence/dispatch-parameters.json` 与 `dispatch-submitted.json` 保存请求/head；初始状态保存为 `evidence/run-42261066525.initial.json`。未记录任何凭据。
- 远端 origin 已验证为公开 `https://github.com/YJBeetle/SWCLI.git`，当前用户 ADMIN；初次网络审批要求核实目的地，核实后重试已获准并完成推送/dispatch。

## 待完成与验收边界

取得并保全对应原生 run/head/参数和首真实失败（若有）；排队不是失败，不重复 dispatch。
即使内部校准通过，也仍缺少公开 CLI/MCP/SDK 端到端写入验收，公开写入不得据此开启。
主对话统一处理集成冲突、公开 gate 与后续发布；本分支不合 main、不发布。
