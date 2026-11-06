# 文档属性：工程图出详图默认选项交接

## 当前范围与接口

- 唯一工作树 `/Users/YJBeetle/.codex/worktrees/docprops-detailing/SWCLI`，分支 `codex/docprops-detailing`，基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`；起始 clean，无 `.codegraph`。
- `document.detailing-options` / `swcli document detailing-options`：`options` 包含 `auto_center_marks.part_holes` 与 `auto_center_marks.part_fillets` 两个布尔值。
- `document.detailing-option-set` / `swcli document detailing-option-set FIELD true|false --if-options JSON`：参数 `field/value/expected_options`；完整两值 CAS，上下文 `document_id/expected_update_stamp/lease_id` 均必需。回执 `field/before/options/changed/mutation/native_return`；失败可只有部分结果。
- 只修改未来视图的文档默认开关，不插入标记/实体/视图，不修改绘图标准、字体、公差。官方映射及 CLI 示例见 `docs/design/document-detailing.md`。
- 仅 **原生 Windows / SOLIDWORKS `33.5.0`** 的这两个开关允许变更写入；其他版本、Wine 与未知运行时 fail closed。读取和无 mutation no-op 不代表其他运行时的写入验收。
- 保留 read-only、普通图纸编辑模式、完整值 CAS、后台/前台、文档身份及最终 dirty/stamp 检查；setter 后描述失败仍保留 mutation 回执。无原生 API 重试、错误自动回滚或组内重启。

## 内部原生校准（已独立核验）

- run：[42260661085](https://github.com/YJBeetle/SWCLI/actions/runs/42260661085)，head `5c878c3b13f7811d50af94fca53a4d471cc5669c`，参数 `detailing_calibration=true/native_full=false`，成功。
- 宿主 revision `33.5.0`，独占 hidden host；实际校准约 16 秒，四次 true/false 写入均成功返回 True，逐次保存、只读重开、完整值/布局/无关注解标量检查和拒绝写入通过。
- 原 artifact ID `13526235874`，SHA256 `e744654c2946f79155f138143878c141f1f596bc2ee6cf43f759531381f86faa` 与 GitHub digest 相同。
- 原始 ZIP、未改写解包和本地独立核验回执位于 `artifacts/detailing/internal-42260661085/`。逐文件、report/watchdog/trace hash 与运行范围的可版本化回执见 `docs/evidence/detailing-internal-42260661085.json`。
- Windows 官方 swconst 读出：孔 308、圆角 309、NoOption 0。实现仍从当前宿主旁的官方类型库解析符号，不猜枚举值。
- 校准 head 后有 watchdog 边界补强（`87f4df68e6f041fabaee11f65c59bd44302a1b2a`）与描述失败回执补强；不把旧 head 的内部证据冒称为新 head 的公开验收。最终公开 gate 将覆盖合入候选。

## 公开 CLI/daemon 验收

- 正在准备本分支独立公开 gate；**当前尚未 merge-ready**。待提交和唯一必要 dispatch 后补 head/run/参数。
- `detailing_public_gate=true` 与 `detailing_calibration` 互斥，默认 false，仅本分支手动运行；跳过通用 test/package/full-native/release，不进入其共享 concurrency。
- `verify-detailing-public.py` 只走安装后的公开 CLI/daemon；SDK typed read/no-op 与真实 daemon 的 MCP bridge capabilities/no-op 契约一并检查。MCP stdio 仅由便携协议测试覆盖，不冒称真实 stdio CAD 验收。
- 每个 native/request 600 秒，整组 1800 秒，首个真实失败停止并保留原结果、trace、保存文件、hash。

## 便携验证

- 当前公开候选已通过：1837 项完整回归（32 环境跳过），相关 18 项，SDK generator/strict typing/8 个消费者拒绝检查。
- 公开 gate 的四次持久化控制流、首失败停止、缺 trace/丢持久值拒绝测试通过；最终完整回归和 SDK 类型检查通过。
- 原持久日志在 `artifacts/detailing/portable/`，最终候选使用 `unittest-public.log`、`associated-public.log`、`sdk-types-public.log`；该生成证据目录已加入本分支 `.gitignore`。

## 共享修改与依赖

- 共享文件：`src/swcli/cli.py`、`daemon/operations.py`、`operation_schemas.py`、`result_schemas.py`、`sdk/_generated.py`、`sdk/models.py`、`.github/workflows/ci.yml`、`.gitignore`。
- `_operation.lease_guarded` 支持 `required` 和 `optional`，确保必需 lease 的新操作也实际进入 registry 校验；已有 optional 行为保持。
- 新增独立 catalog/adapter、三组测试、设计与证据说明、内部/公开 gate 和 watchdog 脚本；沿用 annotations 的普通图纸 guard 和 custom-properties 的状态/可写保护。
- 不依赖其他未验收分支；依赖官方 swconst、明确的 GB DRWDOT 与已有私有 Windows 安装设施。
- 没有合并 main、发布、操作本地 Windows VM，也没有修改 DockerSW/MacSW。精确可合 commit 将在公开原产物核验后列出。
