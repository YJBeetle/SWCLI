# 扩展单位 profile 工作交接

2026-11-07，指定持久 worktree `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI`，独立分支 `codex/docprops-units-expanded`，基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。接管 HANDOFF.md 所列未提交实现；无 `.codegraph/`。未修改其他 worktree、DockerSW 指针/CI/镜像、MacSW 或本地 Windows VM。

## 当前范围

- 九字段读取 + GetUnits 五原始 short + 19 有限 linkage，未知值保留。
- 新 set 路由要求 lease/stamp/完整 canonical snapshot；后台/只读/编辑上下文保护，同值不 mutation、不 dirty。
- **新增公开 changed-write domain 仍为空**。私有校准入口不注册、不暴露参数。
- 修复接管实现 snapshot schema 缺 type 导致有效请求 KeyError 的问题；增加 setter 不得清除已有 dirty 的保护。
- 保留 A17 units/units-set。SDK 重新生成。
- 独立 workflow_dispatch `units_calibration` 默认 false，仅本分支手动可运行，PR 无 secret native 入口。选择校准时跳过 property/annotation/full modeling gate；scope 明确是内部 units-read-cas 校准。
- 原生脚本 fresh DispatchEx、PID 排他/空 catalog、三类新 fixture，读/noop/拒写/保存 readonly 重开/part V/S/质心。父进程600秒 native边界、1800秒整组预算。首失败停止、原件持久 fsync；无 API retry/rollback/组内 host 重启。

## 测试与证据

- 新增 21 项测试：九字段/raw/canonical CAS（各非目标成员）、lease/stamp 实际 route、空 domain 零 mutation、noop、readonly/viewonly、drawing context、前读漂移、后读 dirty/stamp 漂移、False/exception partial、SDK/CLI 参数、watchdog/durable/workflow 接线。
- SDK generated --check + strict implementation/consumer types：通过；8 项负向 typing fixture 通过。
- Python3.9 AST 语法与 workflow YAML 解析：通过；git diff --check 通过。
- 首次完整回归 1838 tests 唯一失败为旧 workflow 字符串断言，已通过保留原 `workflow_dispatch && native_full` 表达式修复，重跑结果见后续记录。
- `docs/evidence/units-profile/swconst-export-reference.json` 为接管时既有 TLB 摘录，不是本轮 native 证据。

## 未完成边界

三类文档 read/CAS 为本次唯一预定内部校准 profile；scalar/system 的真实 setter、跨系统联动/保存持久性尚无新 native 证据，仍禁止公开 changed writes。该内部校准即使成功，也不等于公开 CLI 端到端验收或整页单位验收。不可自动开放白名单，不合 main、不发布。

CI head/参数/run 链接、原始产物与首个真实失败将在触发后追加。此前没有本组 native run。

## 本地验证最终记录

完整 portable suite：1840 tests / 54.089s，OK（32 skipped），原始输出 `evidence/units-profile/portable-tests.log`。新增21项测试通过。SDK输出 `evidence/units-profile/sdk-types.txt`。这些均不含 native 验收。

## 已提交与专属原生 dispatch

- 实现提交：`b5b935bc5d0b82b1f1bfdcdd5d524cf2d000ffeb`，已推送 `origin/codex/docprops-units-expanded`。
- 本地 wheel 构建通过；原始日志 `evidence/units-profile/wheel-build.log`。
- 仅 dispatch 一次：[42260282974](https://github.com/YJBeetle/SWCLI/actions/runs/42260282974)。GitHub 返回 head 与上述实现提交完全一致，event=`workflow_dispatch`。
- 参数：`units_calibration=true`、`native_full=false`，media/assets/cleanup/cache 使用 workflow 默认值。绝无 secrets 输出。
- 当前打包 job 已通过，Windows portable 前置在运行；native 尚未取得结果。不要将此状态标记为 native 通过。

## 集成接口清单（供主对话合并冲突）

- operation `document.unit-profile`；CLI `sw-cli document unit-profile [--document-id ID] [--if-update-stamp N] --json`。返回 `unit_profile`：profile/document_type/values/native_units/linkage。
- operation `document.unit-profile-set`；CLI `sw-cli document unit-profile-set FIELD VALUE --if-snapshot JSON --lease TOKEN --if-update-stamp N [--document-id ID] --json`。
- set schema 参数：`field`、`value`、`expected_snapshot` 全部必填；操作上下文 `lease_id`、`expected_update_stamp` 必填。字段为 `system`、`linear.unit`、`linear.precision`、`angular.unit`、`angular.precision`、`mass_properties.length_unit`、`mass_properties.mass_unit`、`mass_properties.volume_unit`、`mass_properties.precision`。
- set 结果保留 `field/before/unit_profile/changed/mutation`；失败时可附 `observed/native_return_value`，有 attempted/may_have_changed 的 partial mutation。无公开 calibration 参数。
- 共享文件修改：`src/swcli/cli.py`、`daemon/operations.py`、`operation_schemas.py`、`result_schemas.py`、`sdk/models.py`、`sdk/_generated.py` 与 `.github/workflows/ci.yml`。`_operation` 的 lease_guarded 从仅 optional 扩为 optional/required，使本组必填 lease 真正进入 registry 守护；保留原 optional 语义。
- 新 helper/schema/native-adapter/test/script 与 docs/evidence 都在本分支独立新增，无依赖其他未验收分支，无需另一线程代码；继承 main A17/A18 的编辑上下文与元数据守护。
- MCP generic execute 和 SDK 由原 operation catalog 接线，未增加专属 MCP capability 或任意 COM 字典入口。SDK 生成器需主对话最终统一重生。
- 官方限制、候选值、原生证据边界详见 `docs/document-unit-profile.md`；目前候选标量保守要求已有 Custom，绝不自动切系统。新增公共 changed-write 始终关闭。

## CI 最新已观察状态

同一 run `42260282974` / 实现 head `b5b935bc5d0b82b1f1bfdcdd5d524cf2d000ffeb`：GitHub Windows Python3.9、Python3.14（含SDK类型/PS解析/安装入口）全部成功，wheel 构建及已安装 wheel 资源核验成功。`Bounded units read/CAS calibration` job `128040131343` 状态 **pending**，尚无 steps，等待共享 native concurrency。排队不是失败；未重复 dispatch。

**未取得本组 native 结果。** 当前可交给主对话的是实现与 portable/安装接线证据，不能标记新增读取或写入已原生验收。仍需待此同一运行获得 native 原产物，核首个真实失败或完整读校准结果；scalar/system 原生写入另缺证据，白名单为空。后续只根据真实相关修复再决定新 head 校准，禁止无修改重跑。

## 统筹复核：concurrency 隔离缺口

2026-11-07 按主对话指令复核：本分支 `solidworks-e2e.concurrency.group` 仍为固定 `swcli-hosted-windows-solidworks`，`cancel-in-progress: false`。该配置**没有分支定向隔离**；主对话已报告其他分支的 pending 独立校准被后续 pending 替换取消，不能把 false 当作每分支 pending 保留保证。

复核时 run `42260282974` / head `b5b935bc5d0b82b1f1bfdcdd5d524cf2d000ffeb` 仍 `pending`，native job `128040131343` 仍 `pending`、conclusion 为空。当前唯一 run 保留；没有取消任何运行，没有修改 workflow，没有再次 dispatch。

下一步仅在该运行实际被取消时：先将首次取消的 run/job 元数据和可用原日志/产物保存到本 worktree 持久证据目录，区分基础设施取消与 native 失败；然后仅为 `units_calibration` 添加分支定向独立 concurrency group（保留非校准 full gate 原 group），补充隔离/默认关闭/非本分支拒绝的接线测试，提交推送相关修复，再对新 head dispatch 一次。当前未执行这些后续动作。

验收边界不变：当前仅 portable/安装接线通过；读/CAS native 尚未运行。即便读/CAS 阶段成功，也没有 scalar/system 九字段写入、保存重开写入持久性或公共 CLI 端到端验收证据，公共 changed-write 白名单保持空。剩余写校准须独立有界、按真实证据审核后才可讨论开放。

## 用户新授权下立即修复并发组

主对话新指令覆盖上一段等待取消的安排。先保存旧 run/job/check/artifact 原始元数据于 `evidence/units-profile/run-42260282974/`，取消前再次 GET 精确 native job：status=pending、steps=[]、runner_id=null。因此按授权仅取消自己的旧等待 run `42260282974`，取消原因/HTTP响应及取消后 run/job/check 原件均持久保存。没有取消其他运行，也没有 native 调用执行。

workflow 仅修改 native job 的 concurrency group：只有 `workflow_dispatch && inputs.units_calibration` 使用 `swcli-units-read-cas-${github.ref}`；full/tag/release 保留原有 group，cancel-in-progress=false。校准 native job/step 仍仅允许本分支手动选择。相关测试22项通过，既有 modeling/CI gate 接线12项通过（1 skipped），YAML解析与diff检查通过。原始输出 `evidence/units-profile/concurrency-tests.log`。

待推送该相关修复新 head 后，只 dispatch 一次替代读/CAS校准。内部成功后继续公共CLI验收准备，不把内部校准通过当 merge-ready。剩余 scalar/system changed-write 与公共验收证据仍缺，白名单为空。

旧 run 普通取消202后仍pending，复核 native仍steps=[]/无runner，按同一精确取消授权调用force-cancel（官方用于普通cancel不响应情形）；最终已确认 `completed/cancelled`。最终run/job/check原件与force-cancel响应保存在旧run证据目录。

替代校准仅 dispatch 一次：[42262804840](https://github.com/YJBeetle/SWCLI/actions/runs/42262804840)，head=`6c314f7d6466ccf4d7734c1127470c34e458258a`，参数=`units_calibration=true,native_full=false`。初始原件 `evidence/units-profile/replacement-run-initial.json`。旧run取消确认后才创建替代，不操作其他run。后续跟进该唯一替代的真实结果，并准备独立public CLI读/noop/CAS/lease/stamp/readonly/保存重开验收；写白名单不自动开放。
