# 文档属性：工程图出详图默认选项交接

- 工作树：`/Users/YJBeetle/.codex/worktrees/docprops-detailing/SWCLI`
- 分支：`codex/docprops-detailing`；基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 起始 clean，无 `.codegraph`；遵循用户注入与 `/Users/YJBeetle/.codex/AGENTS.md`。
- 仅实现两个未来视图默认开关：零件孔/圆角中心标记。官方 API、字段和使用方式见 `docs/design/document-detailing.md`。
- 包含 daemon/schema/CLI/SDK 接线；显式文档、必需 stamp 与 lease、完整两值 CAS、read-only/编辑模式/前后台/文档身份保护及部分 mutation 回执。
- 公开变更写入目前 fail closed（空版本 allowlist）。内部校准通过也不能冒充公开 CLI/daemon 验收。未合并 main，未发布；不操作本地 Windows VM、DockerSW 或 MacSW。

## 测试

- 最终完整便携回归：1832 项，成功，32 项按环境跳过（本地 macOS/Python 3.15）。相关新增 13 项通过。
- SDK generator `--check` 通过；strict SDK 实现和 8 个消费者类型拒绝检查通过。CI YAML/分支 opt-in/发布隔离接线与 `git diff --check` 通过。
- 持久日志：`artifacts/detailing/portable/unittest-final.log`、`associated-final.log`、`sdk-types.log`（生成证据目录已加入本分支 `.gitignore`）。
- 专属校准使用已有 CI 的 `workflow_dispatch` 输入 `detailing_calibration=true`，默认关闭，且仅本分支可运行；该模式跳过通用 test/package/full-native。
- 原生调用 600 秒、组 1800 秒；独占宿主、首失败停、无 API 重试/自动回滚/组内重启。

## 提交和原生证据

- 实现提交 / 校准 head：`5c878c3b13f7811d50af94fca53a4d471cc5669c`，已推送 `origin/codex/docprops-detailing`。
- 唯一专属校准 run：[42260661085](https://github.com/YJBeetle/SWCLI/actions/runs/42260661085)。参数 `detailing_calibration=true`、`native_full=false`；workflow `ci.yml`，ref `codex/docprops-detailing`。
- 已核对 run head 与实现提交一致。当前等待 Windows runner/执行；排队不算失败，不重复 dispatch。
- 持久调度回执：`artifacts/detailing/dispatch.json`；run 元数据：`artifacts/detailing/run-42260661085.json`。
- 原生结果和原产物待 run 完成后补充；当前只证明便携接线，公开变更写入仍关闭。

## 操作、共享改动和依赖

- `document.detailing-options` / `swcli document detailing-options`：返回 `options`，包含 `auto_center_marks.part_holes` 与 `auto_center_marks.part_fillets` 两个布尔值。
- `document.detailing-option-set` / `swcli document detailing-option-set FIELD true|false --if-options JSON`：参数 `field`、`value`、完整 `expected_options`；上下文 `document_id`、`expected_update_stamp`、`lease_id` 均必需。回执包含 `field/before/options/changed/mutation/native_return`（失败可只有部分结果）。
- 共享文件：`src/swcli/cli.py`、`daemon/operations.py`、`operation_schemas.py`、`result_schemas.py`、`sdk/_generated.py`、`sdk/models.py`、`.github/workflows/ci.yml`、`.gitignore`。
- `_operation` 的 `lease_guarded` 支持 `required` 和 `optional`；否则新增“必需 lease”操作虽有 schema 约束却不会进入 registry 校验。已有 optional 行为保持。
- 新增独立 catalog/adapter、两组测试、设计说明、校准与 watchdog 脚本；沿用现有 annotations 的普通工程图上下文 guard 和 custom-properties 的状态/可写保护。
- 不依赖其他未验收分支。Windows 校准依赖官方 swconst、明确的 GB DRWDOT、既有私有安装设施；不使用本地 VM。

## 校准运行中的 watchdog 加固

等待首个原生 run 时复核发现，registry/状态探测可能位于命名 trace 边界之间；补充 600 秒无新边界保护，防止它们继承更长的组预算。此修正只影响监控，不改变 adapter/字段/放行策略。补充测试后 1832 项完整便携回归通过（32 跳过），相关 13 项通过。原生 run 仍绑定原实现 `5c878c3`，不会把它描述为新 watchdog head 的原生验收；暂不额外 dispatch。
