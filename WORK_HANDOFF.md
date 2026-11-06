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
