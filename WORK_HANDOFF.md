# GLB / Image Quality 独立分支交接

日期：2026-11-07（Asia/Shanghai）。本文件是当前交接，`HANDOFF.md` 保留为接管时历史初稿。

## 当前继续处理状态（2026-11-07 06:03 Asia/Shanghai）

- 用户经统筹明确继续处理实际失败，停止持续poll只约束监控方式，不停止当前功能；不新增字段/新计划，不发版，本路仍不合main。上一节“运行中”现为历史快照。
- run **42280265165** / head **`c85ca5f524b3f2e4136241f9fd973d1c137fbf68`** 已completed/failure；原zip1055609 bytes，digest **`sha256:f533fef91c3ad2f1f0f1c47bc6c25c8c2aefa38fbd03ebd58139f128df25b048`** 已与GitHub metadata核对。原件/下载回执/独立audit保存在持久根`run-42280265165`，没有覆盖旧失败。
- 首因：圆柱从fine的单Double请求`0.06927710843373494 mm`返回True，并真的成为custom，但读回`0.07142857142857144 mm`。严格目标检查正确拒绝，mutation双true保留；原trace独立核251个native leaf calls、仅1个Double setter、0次dirty、0次全局setter/重试。不是handler/schema/安装失败。此前圆柱coarse/fine raw另存重开与文件hash有效，box/GLB组尚未开始，cleanup通过；这不是完整属性验收。
- 官方[Image Quality属性API](https://help.solidworks.com/2022/English/api/swconst/DP_ImageQuality.htm)只列Double偏差与range API；[UI说明](https://help.solidworks.com/2017/english/SolidWorks/sldworks/HIDD_OPTIONS_IMAGE_QUALITY_display.htm?format=P&value=)说明slider与偏差反比联动，没有据此可证实的精确量化网格。没有猜公式或放宽容差。
- 最小相关修复仅改变校准输入：选择该fixture在首写前真实观察并独立保存重开的initial custom偏差，要求仍在current range且与fine值不同；每次新fixture只执行单Double。报告保存target来源，明确仅验证“此前观察的一个native值”，任意in-range精确数值仍未证明。此为新head的新完整组验证，不是对失败请求原生重试/回滚，也不补setter。backend仍全部公共关闭。
- 新增原数值量化反例：即使返回True且custom也失败，observed/mutation保留、单Double/零dirty；fake模拟preset偏差联动及任意插值量化，证明gate使用真实先前观察值，完整严格断言保留。对应**32 tests OK**，diff-check通过。生产adapter/schema未修改，无无差异重跑。
- 独立首错audit：`/Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107/run-42280265165/independent-first-failure-audit.json`；audit_ok仅指离线核对通过，`image_quality_calibration_passed=false/public_acceptance_passed=false`保持。下一相关新head只派发一次，正常运行后记录run/head/链接即结束等待，不启动watch/sleep/automation。

### 已派发最小修复的必要新run

- 新run：[42301795947](https://github.com/YJBeetle/SWCLI/actions/runs/42301795947)，精确head **`0a5afc1508574800adb2c82561a9b1d32fe8b979`**；参数`image_quality_calibration=true`, `native_full=false`，其他默认。此head只派发一次，独立profile+ref分组，未重跑旧run/取消他人/重启组内host。
- 初次一次性快照状态`in_progress`，head已核一致；公开写全关闭，未新增验收通过宣称。正常运行后结束本轮，无watch/sleep/automation，等待统筹后续分次快照/原件就绪再处理。
- 请求/返回：`dispatch-observed-custom-value-request.json` / `dispatch-observed-custom-value-result.json`；初始快照`run-42301795947-initial-snapshot.json`，均在持久artifact根。新run尚无完成artifact/digest。
- 分支最后文档交接提交只记录上述run；CAD证据绑定`0a5afc1`，不能把后续文档tip说成正在测试的source head。整组验收/统筹review完成后才考虑发版，正式发布前仍需用户确认，本路未发布。

## 当前收口状态（2026-11-07 03:42 Asia/Shanghai）

- 按用户最新指令，本轮停止持续sleep/轮询与无变化播报；仅取一次状态后交统筹跟进。不创建单CI automation、不扩新计划、不新增审查代理、不rebase main。
- 唯一仍运行的原生run：[42280265165](https://github.com/YJBeetle/SWCLI/actions/runs/42280265165)，精确head **`c85ca5f524b3f2e4136241f9fd973d1c137fbf68`**。快照UTC `2026-11-06T19:42:20.231041+00:00`：wheel、Windows3.9/3.14均success；native处于`Free disposable runner disk for installation`，尚未进入CAD。仅终止本地`gh run watch`进程，没有取消GitHub run。
- 快照原件：`/Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107/run-42280265165-closeout-snapshot.json`。dispatch请求/返回、watch原日志均保留；新run尚无完成artifact/digest，后续由统筹分次快照跟进，结果可用再下载原件。
- **本批没有可声称公开验收/merge-ready的image-quality写子集。** Backend公共写仍全关闭；只有旧head的coarse/fine有限内部保存重开证据。新单Double custom、两实体完整布尔方向、最终foreground/handler保护仍待当前原生run。GLB格式专属选项未映射；真实缺BIN产物已收紧生产validator，普通暂存文件名假设仍未证明。
- 当前分支tip将包含随后准备的MCP公开gate检查与清理失败标记保护；它们**不属于正在运行的c85ca5f证据**，没有为这些准备额外dispatch。本次只保存当前已有工作，未开放白名单。主对话后续review/合并/发版，本路不合main、不tag。
- 生产peer保护本地1853全回归通过；原始peer脚本4/4拒绝复核通过。后续公开gate准备的定向30 tests通过，diff-check通过；它们都是portable证据，不填补native/public缺口。

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
- 写字段 `shaded_mode`（只写coarse/fine；custom为只读分类，由Double偏差调用建立）、`shaded_deviation_mm`、`optimize_edge_length`。只读观察 `save_tessellation`, `apply_to_referenced_parts`。
- 完整 quality 包含五个 normalized 字段、五成员 `native` 与 `deviation_range {status,bounds_m}`。CAS 精确全值；偏差写仅使用一个Double setter并要求原生custom分类联动读回，实际range必须可用；每请求至多单 setter，首错停止，无重试/回滚。允许显式mode→deviation和deviation→custom两类联动；range/其余字段不能漂移。
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

### 第二轮原件：真实 GLB 缺失二进制 buffer

- run `42265919228` / head `d6eff718a9a6a38a0bcdd6724a9916c72256c4f7` 已失败；原zip已验证digest：`sha256:bdfcbf0e992c951acc7a2508e6c7a38cffa7bc0613ec9f0847ef9c6931231ee7`（941989 bytes）。目录同持久artifact根下 `run-42265919228`，未改原件。
- 第一失败在严格GLB mesh解析：`external or invalid GLB buffer`。真实 `cylinder-coarse.glb` 3816 bytes，JSON chunk 3788、BIN chunk **0**；首buffer声明3696 bytes，indices/POSITION/NORMAL的bufferViews总范围也3696。没有uri或Draco扩展。声明的240 indices /114 positions/114 normals **不是实测网格**，不得据此认定80 triangles或细分有效。
- 这是实际输出缺数据，不是应放宽的解析断言。[Khronos GLB buffer规则](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#glb-stored-buffer) 要求对应BIN数据，额外padding最多3bytes。
- 此前已通过：圆柱baseline保存、完整raw readonly/writable新handle重开、SDK read；edge false→true单setter返回True；custom→coarse单setter返回True，明确deviation联动0.018750000000000003→0.12500000000000003 mm，range保持；完整CAS拒绝、三字段noop、coarse native保存及保存后raw读取。尚未到变更后的coarse readonly重开、fine/custom写入、box或完整GLB对照，所以仍未开放写入。
- 生产`export_validation._glb`存在确认缺口：只看mesh/accessor声明会接受空BIN。已增加embedded buffer字节长度和padding检查，原缺数据产物离线复验现在返回False；保留合法外部buffer/扩展容器的既有边界，不把诊断解码器要求强加为全部格式校验。
- 下一校准仅CI开启 `SWCLI_GLB_PLAIN_STAGING_CALIBRATION=1`，同一SaveAs3仅调用一次，暂存名由点号开头多扩展改为ASCII单扩展`swcli-UUID.glb`；生产默认命名尚不变。**这只是隔离文件名变量的有界假设，不宣称已确认根因**。若仍无数据，会单独保留`.invalid-native.glb`原字节，正常目标不被替换。父环境恢复，无global preference/API fallback/retry。
- GLB SaveAs3增加明确native trace，其他格式调用不变。新增共享冲突面：`src/swcli/hosts/windows_documents.py`（仅GLB staging/诊断/trace）、`hosts/export_validation.py`（GLB实际buffer检查）、`test_export_validation.py`、`test_windows_mesh_exports.py`；不改STL/STEP参数。
- 为忠实区分控制域，内部校准先运行独立 `--document-properties` 组（圆柱+box三字段、含edge true/false分别单请求及另存重开、明确 `covers_glb_mesh=false`），成功后才运行原严格GLB组；两组分别保持600/1800秒、同一个owned host，CI步骤整体35分钟上限不增。第一组失败绝不进入第二组；GLB组失败立刻停止。这样GLB exporter缺陷不冒充属性API失败或反之，不把独立property组通过声称为GLB通过。
- 本地生产GLB改动后完整回归 **1845 tests OK（32 skipped）**；新增独立属性组后focused **81 tests OK（2 skipped）**，actionlint通过。完整原日志 `portable-tests-glb-validation-fix.log`。下一次必要验证只对相关修复新head派发一次。

### GLB buffer修复与两域校准的新head

- 提交 `2f095357e6b80d324dc3563c8754bf1406f55d1a` 已推送；此head必要run：[42271766677](https://github.com/YJBeetle/SWCLI/actions/runs/42271766677)，参数 `image_quality_calibration=true`, `native_full=false`，其他默认，派发一次，无排队重派。原件 `dispatch-glb-buffer-fix-request.json` / `dispatch-glb-buffer-fix-result.json`。
- 除已记录1845全回归、81focused外，GLB SaveAs3 trace及导出/原生trace相关 **53 tests OK**；最终导出validator/mesh-wrapper/分组接线 **31 tests OK**，`git diff --check`通过。
- 新run先写 `properties-calibration/image-quality.json`，该组没有GLB导出，包含edge true/false分别单次请求并完整保存重开；通过后才进入 `calibration/image-quality.json` 的GLB实验。任一组首失败停止该组/后续步骤，整体35分钟上限不增；单组600/1800边界不变，同daemon/host不重启。
- 独立审计器已预先按两个证据域分开，位于持久artifact根 `audit-image-quality-artifact.py`。仅当property报告完整通过、全部原文件/trace/raw persistence/kernel/cleanup独立复核通过，才允许将它作为**内部property证据**；即使后一GLB组失败也不能称整run通过或GLB通过，更不能替代后续独立公开验收。公共写入当前仍全部关闭，待原证据核完再开放精确范围。

### 公开验收准备与授权状态

- 用户最新统筹授权已收到；本分支没有待审批/授权阻塞，不需要常规推进重新确认。VM与DockerSW/MacSW边界保持。
- 在等待当前精确head内部结果时，工作区已准备独立默认关闭 `image_quality_public_acceptance` 输入，仅本分支、与calibration/full互斥，独有`swcli-image-quality-public-${github.ref}`并发组。公开wrapper清除两个内部开关，只运行完整property组并保存独立public报告，不调用GLB实验；600/1800及35分钟上限不变。
- `--public-acceptance` 拒绝任何内部开关残留，公开/内部pass字段分开；增加SDK exact后台文档身份核验。便携分组/接线22 tests OK（3 skipped）与actionlint已通过。**这些准备尚未提交/派发，backend公共写入仍全部关闭；不能将fake公共报告当真实验收。**
- 只有当前原artifact按域独立审计通过，才填入已证实范围并提交/派发一次必要公开gate；当前不是merge-ready。

### 第三轮：custom Integer setter被原生忽略，正确API路径收窄

- run `42271766677` / head `2f095357e6b80d324dc3563c8754bf1406f55d1a` 已失败。原zip digest核对一致：`sha256:751f8b969d69abb593a29518d688db00562426f3b0b0554cd3705c749781f05a`（1049591 bytes），持久目录 `run-42271766677`。没有整run或属性组通过结论。
- 属性组首先成功完成cylinder coarse/fine各自另存、fresh readonly/writable重开、完整raw/geometry/hash检查。coarse偏差0.12500000000000003 mm；fine偏差0.0576923076923077 mm。下一请求`shaded_mode=custom`只调用一次Integer setter(44,0,3)，返回True，但observed仍fine/native2、偏差原样，modified仍false；严格读回断言失败，mutation attempted/may_have_changed=true保留。未调用Double、edge-disable、未创建box；**GLB组根本没启动**，故普通暂存文件名假设仍未校准。
- 根据已核官方2025 `swImageQualityShaded_e` 描述（Custom=3须用Double preference设置值）及以上原件，撤销可写Integer custom目标，CLI/请求schema/SDK运行时在COM前拒绝。读snapshot仍保留custom/3。
- 正确候选路径：一个`SetUserPreferenceDouble(32,0,value_m)`，不预调用Integer custom，也不失败后补setter；要求requested偏差读回且mode实际成为custom。显式linked_changes记录`shaded-deviation-coupling`，其余range/readonly/context/geometry断言不变。该路径仍需下一原生证据，公共写入当前继续全关闭。
- 原custom-mode noop改为COM前unsupported反例；coarse/fine仍逐字段零setter noop，custom阶段只验证两个可请求值的noop（偏差、edge），不会把不支持的枚举当noop成功。便携对应路径38 tests OK，含单Double建立custom/未建立即部分失败、拒绝Integer custom、SDK生成一致性。

### 统筹 peer review 两个保护缺口已补（待精确head原生）

- 读取统筹的 `docprops-handler-peer-review-2026-11-07.md`；其发现是精确旧head的便携故障注入，不称原生现场故障。
- 保存并验证不同于target的foreground自身kind/stamp/dirty/config/path/title/read-only/view-only，检查贯穿读前、setter后、readback、dirty与最终读；保持同指针也不放行。任何漂移只报部分失败，不恢复前台或回滚。target本身就是前台时允许本次预期dirty变化。
- image-quality两个handler收尾捕获describe/结果校验异常，将adapter receipt设失败且保留mutation/首次business error，另附`finalization_error`；worker晚期API-command恢复异常也保留已返回receipt，并继续原有host-disconnected机制。每request重置result，避免带入上一请求。其他operation行为不改。新增共享冲突面`daemon/server.py`，主对话合并时需独立检查。
- 新增真实handler→worker→adapter便携测试（不mock execute_operation/结果validator）：成功与首次native失败后的describe异常、late command restore异常均保留mutation/首错；前台7种自身状态×4阶段漂移拒绝且零补偿/单setter。focused image-quality **22 tests OK**，含subtests；便携证据不是native验收。
- 独立artifact审计器同步custom阶段两个合法noop，并拒绝overall failure且未进入后续GLB组的property成功冒称（避免wrapper终止/最后checkpoint故障误归因）。公共写仍全关闭；下一内部校准必须携带这些生产保护和单Double custom路径。

- 最终本地回归 **1853 tests OK（32 skipped，46.703s）**，持久原日志`portable-tests-peer-finalization-fix.log`；focused58通过，SDK生成一致性/strict6源文件与9消费者拒绝、actionlint、diff-check通过。尚未把任何fake当native。

### 单Double与peer保护的精确内部校准（运行中）

- 修复提交已推送：`c85ca5f524b3f2e4136241f9fd973d1c137fbf68`。run [42280265165](https://github.com/YJBeetle/SWCLI/actions/runs/42280265165)，`image_quality_calibration=true`, `native_full=false`，其他输入默认。独立profile+ref并发、只派发一次、不重排队。
- dispatch原件：`dispatch-single-double-peer-fix-request.json` / `dispatch-single-double-peer-fix-result.json`，持久watch `run-42280265165-watch.log`。原生结果未定，公共写全关闭。
- 按peer原始`repro.py`直接对新head运行，结果保存在`peer-original-probe-c85ca5f.json`：descriptor异常不抛出丢回执；mutation双true保留；stamp/dirty/title/path 4/4漂移拒绝且前台同指针。此为mock-only独立复现，不冒称native验收。

- 后续公开gate准备补真实MCP检查（尚未native运行）：从运行daemon发现写入request/result schema并与installed contract核对，随后600s单次读取exact后台handle，schema/full raw值/身份+原trace独立核验；不启停host。helper反例覆盖错误身份、品质、schema。公开group收尾cleanup失败清除所有pass/accepted标记，不留下部分成功宣称。MCP准备不属于运行中的`c85ca5f`，backend仍全关闭；此段将在必要公开gate的新head验收。
