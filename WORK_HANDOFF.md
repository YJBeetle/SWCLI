# GLB / Image Quality 独立分支交接

日期：2026-11-07（Asia/Shanghai）。本文件是当前交接，`HANDOFF.md` 保留为接管时历史初稿。

## 隔离与范围

- Worktree：`/Users/YJBeetle/.codex/worktrees/docprops-export-options/SWCLI`
- Branch：`codex/docprops-export-options`，基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 没有 `.codegraph/`；未索引、未访问/操作 VM、未改 DockerSW/MacSW 或其他分支；不合 main、不发布。
- 接管六文件草案，修复首错被 result validator 遮蔽、setter 后配置/身份/只读漂移、dirty 阶段身份漂移；收窄 mode 联动，range 改变必须失败。
- **GLB 六个格式选项的官方 API 映射仍未证实，保持 unsupported。没有 GLB resolution/triangle budget 假参数、全局偏好/注册表写入或任意 COM ExportData 字典。**
- Image Quality 写入为内部校准候选，默认 fail closed：daemon 未显式继承 `SWCLI_IMAGE_QUALITY_CALIBRATION=1` 时返回 `DocumentImageQualityUnsupported`，无 native preference getter/setter。

## 操作 / 字段 / 共享冲突面

- `document.image-quality` / CLI `document image-quality`：part-only 完整观察。
- `document.image-quality-set` / CLI `document image-quality-set FIELD VALUE --if-quality JSON --if-update-stamp N --lease TOKEN [--document ID]`。
- parameters：`field`, typed `value`, 完整 `expected_quality`；required context `expected_update_stamp`, `lease_id`，optional exact `document_id`。
- 写字段 `shaded_mode`（coarse/fine/custom）、`shaded_deviation_mm`、`optimize_edge_length`。只读观察 `save_tessellation`, `apply_to_referenced_parts`。
- 完整 quality 包含五个 normalized 字段、五成员 `native` 与 `deviation_range {status,bounds_m}`。CAS 精确全值；偏差写必须已有 custom mode 且实际 range 可用；每请求至多单 setter，首错停止，无重试/回滚。mode 仅可显式报告 deviation 联动；range/其他字段不能漂移。
- `mutation {attempted,may_have_changed}`、可序列化 `native_return`、`observed_quality` 保留部分修改。readback 成功后至多一次 dirty mark；noop 零 setter/dirty mark。
- 新文件：`src/swcli/document_image_quality.py`、`hosts/windows_document_image_quality.py`；三份测试 `test_document_image_quality.py` / `test_glb_mesh.py` / `test_image_quality_calibration.py`；`scripts/ci/verify-image-quality.py` / `gate_support/glb_mesh.py`；`docs/image-quality-calibration.md`。
- 共享文件：`cli.py`, `daemon/operations.py`, `operation_schemas.py`, `result_schemas.py`, `schemas/v1/capabilities.schema.json`（只新增标准 description 注解支持），generated SDK 两文件、typing fixtures、README、随包 skill/usage/sdk 文档、`.github/workflows/ci.yml` 与 `scripts/ci/windows/smoke-solidworks.ps1`。
- `_operation` 的 `lease_guarded` 同时覆盖 required/optional，确保本次 required lease 不是仅做 schema 检查。SDK 重生成导致相同空 TypedDict 的 alias 名变化，原名字仍有导出 alias。

## 本地验证（不等于原生证据）

- 完整 unittest：**1841 tests，OK，32 skipped**，50.113s。之后只增加两个安全反例测试，focused **24 tests OK**（含真实 DracoPy 编码/解码测试）。
- SDK generator reproducibility + strict mypy + **9 个消费者拒绝例**通过。
- actionlint v1.7.7 通过（关闭未安装的 shellcheck/pyflakes）；`git diff --check` 通过。
- 原完整回归首次因 capability description 合同失败，已修复并保留原日志，不能隐去。
- 持久原日志：`/Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107/portable-tests.log`（初次失败）与 `portable-tests-final.log`（通过）。本地 Python3.14 / DracoPy2.2.0 / numpy2.3.5；Windows internal gate 固定 Python3.12 / DracoPy2.2.0 / numpy2.2.6。
- 本地 PowerShell 不存在，wrapper 真正语法解析由 Windows portable CI 执行；本地没有任何 SOLIDWORKS 原生结果。

## 专属原生校准与未完成边界

- workflow_dispatch：`ci.yml`, `image_quality_calibration=true`, `native_full=false`。默认关闭、仅 `refs/heads/codex/docprops-export-options` 可开启、与 full 互斥；没有扩大 PR/secrets 权限。
- 复用安装步骤，跳过 property/annotation fixture 和 visible/full suites，只运行新校准。新 host 独占/隐藏，父环境恢复；每请求600秒（含SDK），外部 watchdog 整组1800秒，首失败退出，无 API 重试/组内重启。
- installed public CLI 创建真实圆柱 r10×h10 与 box40×30×10；解析安装 swconst 全部对应 IDs/modes 并记hash；SDK另一会话完整读取；单字段写/完整CAS拒绝/noop与native trace计数；粗/细/合法custom分别另存 SLDPRT、strict GLB、全值只读新handle重开、核几何与文件hash。
- GLB 实际解析 POSITION/NORMAL/indices、primitive mode、mesh数量、扩展/材质；Draco 必须真实解码，按 extension 属性ID取值并核 accessor count，不以压缩大小推断细分。未知required extension等明确失败。bounds标注mesh-local。
- 报告区分 `quality_associated_triangle_difference_observed` 与 `glb_control_proven`；XR六项尚不能独立读取/固定，**即使三角数有变化，后者仍为false**。没有变化也如实报告，不放宽几何/持久化断言。
- `image_quality_writes_accepted=false` 与 `full_acceptance_eligible=false` 始终保留；内部校准通过也不自动开放公共写入。
- 需进一步核证：真实 pywin32 range 返回形状/类型；mode/deviation联动；各原生field保存重开；圆柱/box实际GLB数量。原生失败后先保留原artifact、摘要、第一真实失败，相关修复后才允许新验证。
- 格式专属 GLB API/控制实验仍是独立未完成边界，不要用本分支替代该能力。

## 提交与 CI

首次实现将以中文提交推送本分支。只触发一次对应精确 head 的必要校准；run/head/参数和状态将在派发后补录。当前尚无 dispatch、原生通过或公开验收结论。
