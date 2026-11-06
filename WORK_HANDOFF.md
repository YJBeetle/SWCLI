# 文档级线性尺寸公差默认值交接

## 最终状态

- **已完成当前有界范围，可交统筹集成。** 产品提交：`59f29e8681346495831e80b417f8d4904f75b2a2`，已推送且冻结。后续仅更新证据和文档，不追加 CI。
- 最终公开验收：[run 42277528349](https://github.com/YJBeetle/SWCLI/actions/runs/42277528349)，workflow_dispatch、分支 `codex/docprops-tolerances`、精确 head 同上，整体 success。Windows Python 3.9/3.14、wheel、无 secret profile preflight、专属公开原生 gate 全部通过。
- 独立工作树：`/Users/YJBeetle/.codex/worktrees/docprops-tolerances/SWCLI`；起点 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 没有合入 main、发布或使用用户 VM；DockerSW、MacSW 和其他工作树未改。统筹 main `0e72beb` 保持不动，集成由主对话处理。
- 本验收不是完整建模或发布验收。旧 head 的成功不替代最终 head；以下最终原件已经独立核验。

## 最终原件与审计

原生 artifact `13536290093`，名称 `swcli-windows-hosted-42277528349-1`。

- ZIP SHA-256：`e32f86cc732e7eb381cde26acea327f1c5549caa96c3a3bde9e24893374c29cc`，与 GitHub artifact digest 完全一致。
- 原 ZIP：`/Users/YJBeetle/.codex/worktrees/docprops-tolerances/SWCLI/evidence/run-42277528349/swcli-windows-hosted-42277528349-1.zip`。
- 独立审计：`evidence/run-42277528349/audit.json`，success=true、merge_ready=true，明确 full_modeling_release_eligible=false。
- 原始 run/jobs/artifacts metadata、完整解压件均在该目录；原公开记录在 `unpacked/swcli-native-smoke/tolerance-public/document-tolerances/document-tolerances.json`。
- 冻结产品 head 的唯一 dispatch 参数与回执：`evidence/public-r2-review-fixes/`。accept_tolerances=true、calibrate_tolerances=false、native_full=false、cleanup_profile=auto、vfs_cache_gib=8；media/assets 使用既有默认值。

原生 Windows SOLIDWORKS revision `33.5.0`，隐藏 owned daemon；120 个原生请求、30 次实际偏好 setter、330 次偏好 getter、9 次 SetSaveFlag，单一 worker。零件/装配体/工程图各 10 次真实写入，各完成 basic/0、basic/8、none/3 三个 profile 的保存与只读重开，共 9 个副本。原始保存、打开和拒写回执、CLI/SDK/MCP bridge 回执、trace、源文件和先前副本 hash 均核对通过；全组 77.641 秒，daemon 干净退出、生命周期无残留。lease/stamp/完整 CAS/只读拒绝、跨会话读取及干净 noop 的零 setter 证明均通过。

分发 artifact `13532164697`（swcli-dist）：

- 原 ZIP：`evidence/run-42277528349/swcli-dist.zip`；SHA-256 `17d5cb7741b5abac771c8eb866b645e8098c8f50e13af0732e083059db7f55d1`，匹配 GitHub digest。
- wheel `swcli-0.2.4-py3-none-any.whl` SHA-256：`2fd098cfa662a07be321184788edb9cf40c5d51d4ca00cdebea4f511456dd234`。
- `distribution-audit.json` 证明本分支修改的 10 个包内文件逐字节匹配产品 head 59f29e8。收口提交只改文档与产品 skill 的验收说明，运行时代码/gate 仍等同已验收 head。

`evidence/` 为未跟踪的持久本地证据，未将原生文件或日志塞入实现提交。

## 操作与严格范围

| 操作 | CLI / SDK | 契约 |
| --- | --- | --- |
| `document.tolerances` | `swcli document tolerances` / `client.document.tolerances` | scope 固定 document_defaults_linear；返回 options、write_enabled |
| `document.tolerance-set` | `swcli document tolerance-set FIELD VALUE --if-options JSON` / `client.document.tolerance_set` | field 仅 linear.type / linear.precision；强制 document_id、expected_update_stamp、lease_id 与完整 expected_options |

options 固定含 linear.type、linear.precision，每项 `{value, native_value}`；CAS 同时核对两字段语义值及原生整数。写入仅原生 Windows 且精确 revision33.5.0；目标 type=none/basic、precision 字符串 0/3/8。旧值必须为 none/basic 与 follow_nominal/0/3/8。其他版本、Wine、未知探测、其他目标值或未知旧值，含 noop 均拒绝。读取保留其他已知类型与精度 0..8；-3 映射 follow_nominal，未知整数以 other 保留。

作用域仅 Dimensions > Linear 文档默认公差。不访问 IDimension、IDimensionTolerance 或特征尺寸，不修改模型尺寸值或应用偏好。不支持上下偏差、配合、字体、双尺寸、其他尺寸类别、继承开关或单尺寸覆盖。没有任意 COM 参数、数字偏好编号或公开校准开关。

每请求 setter 最多一次；失败不重试、回滚或修补。沿用 lease、只读/仅查看、前台/配置/工程图编辑上下文保护；后台不激活。目标 title/path、前台 identity/state 全程检查。写后错误保留 before/options/mutation.attempted/may_have_changed 与首业务错误；不伪造文档描述。

## 唯一批准的几何例外

用户明确答复“允许仅此质心误差界限”：质心绝对误差 ≤1e-12 mm。体积、面积、实体数逐位相等与原解析体积/面积断言保留，并检查解析质心 (0,0,5) mm。没有放宽状态断言。内部和公开 gate 共用 `scripts/ci/gate_support/tolerance_geometry.py`，含边界、one-ULP 与非有限值便携检查。

## 官方依据与实现

- [Dimension Tolerance](https://help.solidworks.com/2023/English/api/swconst/DP_DimensionTolerance.htm)：IModelDocExtension Get/SetUserPreferenceInteger，swDetailingToleranceStyle + swDetailingLinearDimension。
- [Linear](https://help.solidworks.com/2023/english/api/swconst/DP_Dimensions-Linear.htm)：swDetailingLinearTolPrecision + swDetailingLinearDimension。
- [swTolType_e](https://help.solidworks.com/2024/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTolType_e.html) 与 [swDimensionPrecisionSettings_e](https://help.solidworks.com/2015/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDimensionPrecisionSettings_e.html)：类型和精度枚举。

偏好编号与 Linear option 从安装的官方 swconst.tlb 按名称解析；缺失、重复、类型错误即失败，不猜数字。实际观察 style375、precision25、Linear206，代码不硬编码这些值。

独立实现 `src/swcli/document_tolerances.py`、`src/swcli/hosts/windows_document_tolerances.py`；共享接线涉及 CLI、daemon operations/server、operation/result schemas、SDK generated/models、产品 skill、CI workflow 和 smoke wrapper。`_operation` 的 lease_guarded 同时保护 optional/required，其他既有操作上下文声明未变。公差复用 annotation adapter 的编辑上下文检查。与 main 的 detailing/revolve 集成时保留双方保护，解决目录冲突后重新生成 SDK。

统筹提出的三项阻断均在 59f29e8 修复，并由最终 run 重新验收：

1. 同 revision Wine 曾可写：以与已接受 main detailing 一致的 ntdll/wine_get_version 检查限定 native Windows，未知探测失败关闭。
2. 混合 CI flags 曾可能跳过 CAD 后成功：无 secret native-profile preflight 拒绝混合模式/错误分支，所有 native 阶段仅依据已验证 profile；专属 concurrency 不占用 full/release 组。
3. setter 成功后最终描述/worker 恢复错误可能丢回执：保留当前请求 partial receipt 与首错误，每次请求先清空局部 result，避免沿用前次 mutation；真实 worker loop 回归覆盖恢复失败和后继请求。

## 验证与实际边界

- 冻结 head 本地全套便携测试：共 1858 项，结果 OK（32 项跳过）（macOS / Python 3.15.2）。日志 `evidence/review-fix-portable/unittest.log`，摘要 `summary.json`。
- 新增 review 回归 12 项，覆盖实际 worker loop、Wine/native/未知探测、描述失败、身份漂移、48 个 event/ref/flags 组合及真实 profile CLI/workflow 条件。
- SDK generator --check、strict typing、8 个 typing 负例、installed CLI/schema/skill resources、YAML 与无 secret profile 依赖检查、git diff --check 均通过。
- 公开 CLI→安装 wheel daemon 为真实原生验收；typed SDK 与 MCP DaemonBridge 读取/noop 也走同一真实 daemon。MCP stdio 协议由便携契约测试覆盖，不声称原生 stdio 握手验收。
- Wine 拒写有便携/结构回归证明，无真实 Wine 验收。仅对该原生 revision、生成的三类 fixture 和记录场景作结论，不推广为任意版本、模型或编辑模式通用验收。
- 原生每请求 600 秒、组 1800 秒限制保持；首失败停止，无 API 重试/自动回滚/组内宿主重启。完整建模、内部校准和 release 在最终公开 run 均未执行。

## 历史证据（不替代最终 head）

| 阶段 | run / head | 结果与原 ZIP SHA-256 |
| --- | --- | --- |
| 首轮内部 | 42261066525 / 27dc93077791359ded7296abee240f06350db51d | 失败，仅质心 Y 差 2.757268708510093e-16 mm 触发逐位相等；未到保存重开。artifact13525731977，bf1f00be3b91ae53d289799aa27c57545a540e14eddb59e23cbc811c893e5ff8 |
| 批准界限后内部 | 42266358630 / 252ad8b86ddebc282b94ee765199f9bcec38e088 | 三类通过，45 请求、15 setter；artifact13527958282，89164b4642dc4c5d4167e1f97e30eab89945bf2583cdc804ce18708794b86285 |
| 首轮公开 | 42271130456 / ce147cba0ba43d57408e6ec12a616aea6c1559d1 | 原生通过但后续审查发现三项阻断；artifact13532461445，4729536da9d26060a430127dc1e28393e74a64a2978cdc1b42805170c4ffdbdd |

对应原件与审计保存在 `evidence/run-RUN/`。旧公开 audit.json 的 merge_ready 结论已由同目录 `code-review-hold.json` 明确取代，原件未改。最终 59f29e8 的通过及审计见本文顶部。

内部历史记录未单独保留 raw open receipt（冻结脚本已有只读断言），最终公开 gate 已逐一保留。审计器曾添加无依据的文件头假设，已移除；文件证据依据实际 native 保存/只读重开、大小与 hash，几何/状态/trace 断言没有减弱。
