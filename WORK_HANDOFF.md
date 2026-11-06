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

- 实现提交：`ffc67ef2304b904752c96e1a66f328e5ba204e66`，已推送。
- 首次 dispatch：[42261706856](https://github.com/YJBeetle/SWCLI/actions/runs/42261706856)，精确 head `ffc67ef2304b904752c96e1a66f328e5ba204e66`，参数 `image_quality_calibration=true`, `native_full=false`（其他输入默认值）。
- 派发后统筹报告共享 `swcli-hosted-windows-solidworks` pending 互相替换的实际冲突。初次观察时 run 仅在 portable/package 阶段，尚未进入 native job；为避免影响其他分支，**仅取消自己的这个run**。不是原生/CAD失败，不取消他人run。
- 相关接线修复：仅 targeted group 改为 `swcli-image-quality-${github.ref}`，`cancel-in-progress=false`；默认 full/release group 保持原值。补 portable wiring test + actionlint。初次run使用旧workflow，不能冒称该run已经被后续修复隔离。
- 并发修复提交：`e62fa65bbdb079eb6d8f4eff60276f3ce1017cd3`，已推送；专属接线回归20 tests OK（3 skipped）及actionlint通过。
- 修正后校准：[42261983700](https://github.com/YJBeetle/SWCLI/actions/runs/42261983700)，head **`e62fa65bbdb079eb6d8f4eff60276f3ce1017cd3`**，参数 `image_quality_calibration=true`, `native_full=false`，其他输入默认值。此head只派发一次，不为排队重复dispatch。dispatch返回成功，结果待完成，当前没有原生通过或公开验收结论。
- 初次run已确认 `completed/cancelled`，取消发生在native前；原始结果 `run-42261706856-cancelled.json`。修正后派发原件：`dispatch-corrected-request.json`, `dispatch-corrected-result.json`。
- 原始派发请求、返回、首次run状态保存在 `/Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107/dispatch-request.json`, `dispatch-result.json`, `run-42261706856-initial.json`。

### 验收继续工作

- 用户最新要求：内部校准通过后继续独立核 artifact/head/digest/trace/save-reopen，再开放已证实的精确范围并做公开 CLI/daemon 验收；本分支当前仍不是 merge-ready。
- 复查补强：在首次 setter 前保留独立 native baseline，并经新 readonly/writable handle 核完整 raw quality、几何与文件hash。失败也保留未修改基线；补版本/来源commit/decoder版本记录。此补强不属于正在运行的 `e62fa65`，当前run不能冒称覆盖了它；下一次相关验证再使用新head，不因排队重派。

### 首次真实内部校准失败核验

- 修正并发后的run `42261983700` 已完成/failure；Windows3.9/3.14、wheel/SDK/PowerShell解析均通过，安装/decoder/client准备通过，新校准步骤失败，清理与原证据上传成功。
- 已下载**原zip**并核对GitHub artifact digest完全一致：`sha256:b0e56025fb34cd61af5e3f8ad589578f44af2090a3dd7f0de8f3e52c6db449ac`（796225 bytes），head精确 `e62fa65bbdb079eb6d8f4eff60276f3ce1017cd3`。
- 原件目录：`/Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107/run-42261983700`（原zip、metadata、download-receipt与解压original均保留）。
- 第一真实失败：校准器 `Trace.verify` 错把所有`_com_value`状态/身份/API-sequence调用与仅六个preference getters的预期列表整体比较。错误为 `quality native getter/setter count or order mismatch`，不是CAD API失败。
- 原始首个 `document.image-quality` 返回ok=true、后台身份保持，range status=0，bounds_m `[9.036144578313254e-06,0.00025]`；mode=custom，deviation_m=`1.8750000000000002e-05`；edge=false/save_tessellation=true/apply_refs=false。**零次image-quality-set请求、零次此功能setter**，没有GLB或变更保存证据。不得由该只读结果开放写入。
- host revision `33.5.0`，PID5476；swconst SHA256 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`，全部9个相关ID/mode匹配。圆柱kernel体积/面积与解析值匹配。
- 修复保留所有native pair的完整顺序/边界/终止检查，仅对preference+dirty子序列执行精确getter/setter计数；显式拒绝任何global setter。fake补真实guard traces、global setter/偏好重排反例。新head将连同首次写前baseline保护做一次必要校准，不是原run无修改重试。
- 独立复核 `independent-read-audit.json`：首read结果schema有效，document descriptor与extrusion后完全相同，解析圆柱kernel值匹配，write请求数0。最终lifecycle comparison通过，原始结束快照仍有host，1.3198387s内settle-02归零，不能只读第一结束快照就称泄漏或忽略它。report/trace各自SHA见audit。
- 修复后的trace对子序列重放原请求成功：6 getter / 0 setter / 0 dirty；完整98个leaf native calls边界顺序仍检查，原件未改。原始report的failure保持原样。

### 修复后的必要校准（等待结果）

- 相关修复提交：`d6eff718a9a6a38a0bcdd6724a9916c72256c4f7` 已推送；完整guard trace/缺失getter/全局setter/重排/原生首错基线保留等focused24 tests OK，原native只读trace离线重放通过。没有因为接收统筹消息重复全套测试。
- run：[42265919228](https://github.com/YJBeetle/SWCLI/actions/runs/42265919228)，**head `d6eff718a9a6a38a0bcdd6724a9916c72256c4f7`**，`image_quality_calibration=true`, `native_full=false`，其他参数默认值；此head派发一次。专属profile+ref concurrency，未进入默认full/release分组。
- 原件 `dispatch-trace-fix-request.json` / `dispatch-trace-fix-result.json`，低频监控 `run-42265919228-watch.log`。这是保存/审计原artifact后的相关代码修复验证，非不改代码重试。
- 当前没有任何写入、save/reopen或GLB实证通过结论，公共写入保持关闭；待此run完成后独立审计再决定精确开放范围及后续公共验收。
