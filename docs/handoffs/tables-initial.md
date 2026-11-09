# 表格文档默认设置交接

## 当前状态与范围

- 工作树 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI`；分支 `codex/docprops-table-defaults`；基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。只提交、推送本分支；main 合并由主协调负责，不发版。
- 五个非字体默认设置：`all.use_template_settings`、`bom.box_border`、`bom.grid_border`、`general.box_border`、`general.grid_border`。前三区分 part/assembly/drawing，General 仅 drawing。未实现表格实例插入/编辑、字体、图层、padding 或其他表格族。
- **健康路径保护与零件完整 internal 已通过，仍待全量 public，暂不可合并。** 已有装配体/工程图公开原件对应 `5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b`，不能替代本轮新 adapter 的 native 验收。worker late-fault 独立修复 `1d44a42` 保留，交统筹本人审查。
- 用户于 2026-11-08 明确批准“允许，仅限表格路线的质心界限”：每轴绝对差 `<=1e-12 mm`。其余几何 V/S/实体数、身份、状态、lease/CAS 等严格规则不变，原值/hex/delta 和旧失败均保留。见 `docs/verification/table-defaults-centroid-decision-2026-11-08.md`。
- 完整 internal `42415716434` / `f1881a7` 已success且原ZIP独立审核通过：11 setters / 237 getters、完整3类型及save/reopen。已人工固定实测零件3项和原有A/D8项及同值pair；public all验收尚未完成，不能把内部通过当公共通过。
- 没有触碰 VM、DockerSW、MacSW、其他任务工作树、main、release 或凭据。此前所有权与 artifact 上传边界的自动审批问题已通过只读查证和收窄路径解决，无待批常规动作。

## 接口和行为

- `document.table-options` / `swcli document table-options --document ... --json`：完整 `options`，每项 `{value,native_value}` 或 `{unavailable:"document_type"}`。后台目标直接读取，不激活。
- `document.table-option-set`：`field`、typed `value`、完整 `expected_options`；envelope 必须 `document_id`、`expected_update_stamp`、`lease_id`。CLI 使用 `--document`、`--if-update-stamp`、`--lease`、`--if-options-json`。
- SDK `client.document.table_options()` / `table_option_set(...)`；MCP generic execute/catalog 同一路由，无 force/calibration 公共参数。
- 单 setter、完整 CAS、readonly/viewonly/sketch/sheet 检查；目标 identity/config/stamp/dirty、文档成员及前台 peer identity/config/stamp/dirty 保持；未请求字段保持。无重试、回滚或组内 host 重启。
- 进入 setter 即 `mutation.attempted=true` / `may_have_changed=true`；保留 Boolean `native_returned`，false 保守失败。adapter 首错后 handler 不再读取 descriptor；成功写入后 descriptor 失败仍保留首错、已有值和修改回执。失败可缺失已不可用的 document metadata；成功必须完整验证。
- 常量从拥有该文档的安装目录 `swconst.tlb` 按官方符号解析，无猜测 ID；`GetExecutablePath` 单次读取兼容 pywin32 属性/方法。
- 公开 admission 精确到 `RevisionNumber`、文档类型、字段、`(before raw, after raw)`，只包含已观察的 changed/self-noop pair。声明 Wine host 的表格写入在 supervisor 启动/排队 worker 前拒绝，不从 Windows 外推 Wine。

## 合并涉及文件

- 共享：`src/swcli/operation_schemas.py`、`result_schemas.py`、`daemon/operations.py`、`daemon/server.py`、`cli.py`、`sdk/_generated.py`、`sdk/models.py`、`.github/workflows/ci.yml`。schema 整合后重新生成 SDK，不手工拼 generated 冲突。
- 新模块：`document_tables.py`、`document_table_profiles.py`、`hosts/windows_document_tables.py`。
- 校准/验收：`scripts/ci/verify-table-defaults-{calibration,public,proof}.py`、`gate_support/table_defaults_evidence.py`、`windows/{calibrate,accept}-table-defaults.ps1`。
- 测试：`tests/test_document_tables.py`、`test_table_defaults_{calibration,public,evidence,proof_preflight,worker_receipts}.py`。
- 官方来源、协议及边界：`docs/design/document-table-defaults.md`。

## CI 边界和证据策略

- 既有 `CI` 增加默认关闭的 `table_defaults_calibration`，只允许本 repo/branch、`table_defaults_head == github.sha` 的手动运行；不增加 PR secret 执行。
- `table_defaults_mode=internal|public`；内部 `table_defaults_document_types=all|assembly-drawing`，report 请求计划与完成 cases 必须完全一致，不能挑成功行冒充整组通过。
- 专用 concurrency `swcli-table-defaults-calibration`；`native_full=false`，无全量或 release gate。每次 native 600 秒，组 1800 秒，首错停组。
- 只上传本组生成的 `swcli-native-smoke/table-defaults/` 文档、report、traces；不上传安装器、runtime/config/license/credential。所有原始 ZIP、GitHub metadata、日志长期保留在 ignored `docs/verification/table-defaults-evidence/`。
- 公开 gate 在准备 private runtime 之前验证 pinned successful run/head/artifact/digest，独立审核 report/trace/saved-file hashes。类型 `[2,3]` 必须 8 setters / 186 preference getters / 零 application preference setters。
- 公开验收必须 CLI→daemon→worker 实际 changed/noop/CAS/lease/stamp/readonly、独立 save-as/新 handle 只读 reopen、同一 daemon 的 SDK/MCP；逐请求 trace 证明单 setter/零 setter、顺序与同一 host。排除 part 时另查 part read + 拒绝 write（零 native preference 调用）。
- 公开失败后不再 close/status/CAD 请求，由 owned wrapper 清理进程，避免 timeout 后 lazy host replacement；成功必须空文档/ownership journal 并确认 daemon 退出。

## 已推送提交与原生失败（均不接受）

| Head / run | 首次真实失败 | 原始 artifact / ZIP SHA256 |
| --- | --- | --- |
| `8ca545c8edc707fedbf5669934aed247ab905b91` / [42261481759](https://github.com/YJBeetle/SWCLI/actions/runs/42261481759) | `GetExecutablePath` 字符串被调用，任何 table getter/setter 之前失败，cleanup 无错 | ID `13527120695`，`table-defaults-internal-42261481759-1`；`a482eb9aed4184ed6a6150130894dc8b29a3717c1d44d3bfaf4139181eb49375` |
| `973dcaa86f3332605475c0a9520b2bdb555ff2dd` / [42266161306](https://github.com/YJBeetle/SWCLI/actions/runs/42266161306) | 两次 part scalar/CAS/noop 后精确几何失败，未保留当时 actual 原值，无 edited-save/reopen、无 assembly/drawing | ID `13528935364`，`table-defaults-internal-42266161306-1`；`2a6ba4b978bd84f2b2dd0f7db3b3ecfe6e5dbaf4b9b880151f14e609df2a556b` |
| `b4f79111dce508ac6947b1b19bdc80e2e315cd73` / [42269888379](https://github.com/YJBeetle/SWCLI/actions/runs/42269888379) | 第一次 part template `True→False` 后精确几何失败；原始 operands 已在 report/jsonl 保留；无 edited-save/reopen，cleanup 无错 | ID `13530843312`，`table-defaults-internal-42269888379-1`；`34b9c6fe5950da54da469db49db91990585dfec73a2dd08426a34ee6723acdd4` |

第三组 volume `11999.999999999998`、area `3799.9999999999995`、solid count 1、centroid x/z 未变；centroid y `8.271806125530278e-16 → 6.286572655403011e-16 mm`。没有对该差异作通过解释，也未使用其他线程的容差许可。原始 ZIP 均与 GitHub digest 核对一致，保存在 `run-<id>/original.zip`。

Report SHA256（依上表顺序）：`afb23a5832c588778117ca30d562b8f0029cad9bd5926132dab2e73730412d5c`、`11e7c4a9d404ddaf9936eead447c3acad462a3feb9cbab3b9f0e8d2121a4d7c0`、`317b403efe6437b84a1eced96fda7bc57a6bcb0904760137aa1fd437a06a1a7e`。

实现首提交 `df3fa41bac6073e308c93323c210a571228ce2a6`；8ca 收窄 artifact；973 修 GetExecutablePath 并增加公开 gate；b4 在精确比较前记录原值并加入 Wine supervisor guard。各自普通 push CI 均通过，最近 [42269850513](https://github.com/YJBeetle/SWCLI/actions/runs/42269850513)；它们只是 portable/package 验证，不能代替 native 验收。

## 最新可移植验证

- 前一完整本地安装套件 1834 tests / 32 skips；SDK generator、strict mypy 6 文件、8 negative consumer 检查通过。
- 本次 handler/真实 `_worker_main`/daemon/native-sequence 126 tests 通过；覆盖首业务错误后不重读以及写入成功后描述失败的 mutation 回执穿透。
- 当前 receipt/scope head 完整 portable suite **1855 tests / 32 skips 通过**；SDK generator、strict mypy 与 8 negative consumers 通过。检查日志：`receipt-scoped-full-portable.log`、`receipt-scoped-sdk-types.log`。
- Windows push CI 会解析 PowerShell；本地未运行 Windows CAD。可移植 mock 和内部 native 均不作为公开链路验收。


## 收口快照（2026-11-07 Asia/Shanghai）

- 已推送产品修复 tip：`5cc22a70204724c237991706d1d11ae290811fe4`，中文提交“fix: 保留表格修改首错回执并限定装配体工程图校准范围”。完整本地 portable 1855 tests / 32 skips 与 SDK generator/strict mypy/8 negative consumers 通过。
- 同 head 普通 push CI [42279908900](https://github.com/YJBeetle/SWCLI/actions/runs/42279908900) **success**（Windows Python 3.9、3.14、wheel；full/release skipped）。真实 handler/worker 收尾回执修复已在该 head，前台 peer 四项检查没有重复修改。
- 当前唯一进行中的内部 scoped run [42279939696](https://github.com/YJBeetle/SWCLI/actions/runs/42279939696)，exact head `5cc22a70204724c237991706d1d11ae290811fe4`；`native_full=false`、`table_defaults_calibration=true`、`table_defaults_mode=internal`、`table_defaults_document_types=assembly-drawing`、`table_defaults_head=5cc22a70204724c237991706d1d11ae290811fe4`。
- 按最新收口指令只取一次状态：**in_progress**，仍在 `Free disposable runner disk for installation`，尚无本组 CAD 校准结果、完成 artifact 或摘要。原始 inputs / dispatch metadata / handoff snapshot 保存在 `docs/verification/table-defaults-evidence/run-42279939696/`。停止本地持续 watcher，不取消 GitHub run，不再 dispatch、sleep 或持续轮询。
- 当前 **没有可合并发版的公开原生验收子集**；`PROFILES` / `INTERNAL_PROOF` 均空。不得将 portable 通过或在跑内部校准视为公开 CLI/daemon 验收。SDK/MCP 本地契约已检查，但真实同 daemon 的 native public gate 尚未执行。
- 后续由统筹分次快照：待本 run 完成、原件可用再核对 original ZIP/GitHub digest、head、首错、完整 requested `[2,3]` cases、trace/fixtures；成功也仅属内部证据，公开精确 scope 开放及一次 exact-head public gate 尚未完成。若失败如实交接，不为凑齐无限迭代。
- part 写入继续关闭，前次精确 centroid 比较失败原件保持；不复用其他线程容差许可、不放宽断言、不扩展新功能/计划、不重跑旧失败。保留 main `0e72beb` 的 detailing/revolve 整合，不在此 rebase/merge/release。


## 42279939696 完成失败：原件与最小修复（覆盖上面的在跑快照）

- run `42279939696` / head `5cc22a70204724c237991706d1d11ae290811fe4` **completed/failure**。首个失败步骤 `Calibrate only bounded table defaults`；日志定位 `calibrate-table-defaults.ps1:49` 的子进程 `$worker.ExitCode -ne 0` 收尾检查。原 wrapper 未记录该值，不能声称原值已证实为 null。
- Artifact ID `13536576827`、名称 `table-defaults-internal-42279939696-1`。原始 ZIP `run-42279939696/original.zip` 与 GitHub digest 均为 `sha256:af6372f11df6322a14a254e3bec5d025fff5ce2ce294849e3d8f0e05bcb94894`；metadata、原始完整失败 log、report/trace 已保存。
- 原始 report `success=true`、请求/完成类型 `[2,3]`、3+5 个写入/CAS/no-op、两份 distinct save-as/readonly reopen 均完整，cleanup errors 空；native request 正常 end，无 traceback。共享 harness 返回整数 `0 if report["success"] else 1`。
- 独立原件审核通过：SOLIDWORKS `33.5.0`，8 setters / 186 preference getters，零应用偏好 setter、单 owned host 生命周期、完整 paired/nested traces、最大阶段约 7.173 秒、原始和保存文件哈希均符合。审核结果保存在 `run-42279939696/independent-audit.json`。**这不改变整轮 failure，不是公开验收，不作为 profile/pin。**
- 原始 SHA256：report `f206ad7a1bf9ac1e5908645759ade6d6def13205734cf8321f2513ff5d4b14b9`；harness trace `72ac09b6775bb582c77b5308aa6263e247bc35882ef7d1f715c0bdbb7aff4182`；native trace `d7fc8c13690620471046ddcdab17725ee6f17a54d3925696f2bb4eba66fb5327`。
- 最小修复沿用已有 `start-external-host.ps1` 的 live process Handle 保留方式，避免 Windows PowerShell 在等待短命子进程后丢失 ExitCode；内部 wrapper 新增实际 `worker_exit_code` 回执，unknown/nonzero 仍 fail closed；公开 wrapper 的 gate 子进程同样保留 handle，bounded wait 后 flush，无重试/回滚/host 重启。
- 新 Windows 真子进程测试 `tests/test_table_defaults_process_exit.py`：复制生产 wrapper，仅用无 CAD Python 子脚本替代 worker，分别验证 exit 0/7、实际回执与 wrapper 成败、带空格路径和 stdout。普通 CI 执行；定向原生 job 也在 private runtime 准备前执行该测试，避免包装器退化再消耗安装环境。本地 macOS 无 Windows PowerShell，此项明确 skip，待 CI 确认。
- 本地 focused table tests 22 tests / 1 Windows skip，以及 table/modeling-sequence/annotation-wiring 相关 38 tests / 4 platform skips 通过；workflow YAML 与 preflight 顺序验证通过。产品 API/字段、精确几何/CAS/状态断言及 600/1800 秒限制均未修改；profiles/pin 仍空。
- 最新用户澄清：既定系列能力需一起完成后发版，part/public 未完成点仍为阻断，不因收口改成后置；不扩字段/新计划、不派审查代理。仅对这次 wrapper 首因做相关修复；后续定向 run 一次 dispatch 后保存状态，不持续轮询。


## Wrapper 修复 head 与必要验收 run

- 产品/包装器修复已推送 `50db73af937cd78aa9adcd8c4bfdd5467c956533`：“fix: 保留表格校准进程句柄并记录真实退出码”。此后文档提交不改变该验收 head。
- 对实际 wrapper 首因修复只 dispatch 一次 [42301331238](https://github.com/YJBeetle/SWCLI/actions/runs/42301331238)，exact head `50db73af937cd78aa9adcd8c4bfdd5467c956533`；`native_full=false`、`table_defaults_calibration=true`、mode `internal`、document types `assembly-drawing`、head 参数同 SHA。
- 单次 API 快照状态 **in_progress**；snapshot 与原始 dispatch inputs 保存在 `docs/verification/table-defaults-evidence/run-42301331238/`。未启动 watcher/持续 poll 或 automation；不取消他人 CI，完成原件可用后再推进。无原生 API retry/rollback/host replacement。
- 先执行实际 Windows plain-child exit 0/7 regression，再准备 private runtime，再执行既有 `[2,3]` CAD plan。Windows 进程回执修复仍待该 CI 证实；前轮 CAD report 审核通过不能代替新 wrapper 成功或公开验收。
- 既定系列仍未完成：part 精确几何失败保持阻断；`PROFILES`/`INTERNAL_PROOF` 空；真实公开 CLI/daemon/SDK/MCP native gate 尚未执行。相关能力不改成“后置交付”，系列整组完成后才进入发版确认；本路不 merge/main/release。


## 装配体和工程图内部校准通过，进入公开验收

- [42301331238](https://github.com/YJBeetle/SWCLI/actions/runs/42301331238) / `50db73af937cd78aa9adcd8c4bfdd5467c956533` 完成成功。原始 wrapper 回执为 exit 0，native/group 限制为 600/1800 秒。
- Artifact `13545815581`（`table-defaults-internal-42301331238-1`）。原始 ZIP 与 GitHub digest 均为 `sha256:7e473478064998f3e116329d29007f8f21c441be74d7827a7d3bfbc90fc2f4f6`。在 ignored `run-42301331238/` 保存 run/artifact metadata、original.zip、extracted 原件及独立 audit。
- 独立审核确认 33.5.0、完整请求和完成类型 [2,3]、8 setters / 186 getters、零应用偏好 setter、单一 owned host、完整 trace、原始及另存/reopen 文件哈希。最大阶段约 4.067 秒。
- Report SHA256 `f04b79376ea8e5e5fd7569c7d20feb28ae6193215ee9dc29695c3bca5dbbd7f9`，harness trace `eb97a6e5fb77dae6d1f46f63122c9847d90dc965c16a319df92b87f8d5393afa`，native trace `d95c6b1ac3c577cb4a90772a83b7f47f51b618adabeab5880cf03bbd7812ef13`。
- 只在分支开放通过审核的 raw pairs。装配体 toggle true→false，工程图 false→true，两类型适用边框 0→1，并各自允许目标值同值请求。零件、其他 revision 和未验证方向仍关闭。
- 公开 CLI/daemon/SDK/MCP gate 将使用上述 pinned 原件，在独立 run 检查全量 CAS、lease/stamp、readonly、单 setter 和另存重开。零件先前精确几何失败仍是系列阻断，公开 gate 另验零件读取及写入被拒绝。


## 公开验收已启动

- 验收 head `c6614e0cd9a3ecae751587b53f0802486df4dfde`。本地 remote 和 local 预检均通过，相关测试共 37 项，其中 1 项 Windows 专属测试在 macOS 跳过。
- [公开 run 42305463102](https://github.com/YJBeetle/SWCLI/actions/runs/42305463102) 单次启动，快照为 `in_progress`。参数为 `native_full=false`、`table_defaults_calibration=true`、mode `public`、类型参数 `assembly-drawing` 和上述精确 head。实际公开范围由 pinned 内部原件的 [2,3] 决定。快照和参数存于 ignored `run-42305463102/`。
- 公开结果待原始 artifact 核验，系列还需解决零件精确几何验收。系列整组完成后再请用户确认发版。


## 公开 run 42305463102 的首次失败与相关修复

- [42305463102](https://github.com/YJBeetle/SWCLI/actions/runs/42305463102) / `c6614e0cd9a3ecae751587b53f0802486df4dfde` 已 completed/failure。首次失败在 `Check pinned internal run and original artifact provenance`，尚未准备 private runtime 或执行 CAD。GitHub artifact 列表为空，原始 run/jobs/artifacts metadata 和完整 failed-step log 保存在 ignored `run-42305463102/`，文件摘要见 `evidence-digests.json`。
- 原始 failed-step log SHA256 `fc1954faed7fdb6d394a0e2d0d88a957a788d355456ab44cfe29b52f97e982f0`。首错为 subprocess reader 使用 Windows 默认 charmap 解码 `gh api` 的 UTF-8 JSON，byte `0x9d` 导致 `UnicodeDecodeError`，随后 `json.loads(None)` 报错。原始来源校验还未完成。
- 随后 cleanup 因路径初始化步骤尚未运行，`PrivateRoot` 为空而再次报错。相关修复仅为 table job 在 PRIVATE_ROOT 和 PROBE_ROOT 均已初始化时执行 always cleanup。
- `scripts/ci/verify-table-defaults-proof.py` 的 gh subprocess 显式指定 `encoding='utf-8'`。新增实际 Python 子进程输出包含中文及弯引号的 UTF-8 JSON 回归，模拟隐式 cp1252 解码并验证来源适配器按正确编码读取。
- 本地相关 54 tests / 4 platform skips 通过。实际 pinned internal remote preflight 和原始 artifact local audit 均通过，workflow YAML 与 cleanup 条件验证通过。已有内部原件、精确 profile、CAS/状态/零件几何硬断言及 600/1800 秒限制继续作为验收门禁。
- 本轮仅对上述首错及后续空路径清理错误修复。下一次公开 gate 使用该修复的精确 head，完成后仍需原件核验。零件精确几何仍为系列未完成项，系列整组完成后再请用户确认发版。


## UTF-8 预检修复后的必要公开 gate

- 修复提交 `c95ecdefa40689b2c8723a2e85998bbde2b6633f` 已推送，首次失败及原始日志摘要见上段。
- [42361458023](https://github.com/YJBeetle/SWCLI/actions/runs/42361458023) 仅 dispatch 一次，验收 head `c95ecdefa40689b2c8723a2e85998bbde2b6633f`，mode `public`，`table_defaults_calibration=true`，`native_full=false`，类型参数 `assembly-drawing`。单次快照为 `in_progress`，metadata 与原始参数保存在 ignored `run-42361458023/`。
- 继续使用内部 `42301331238` 的已审核原件和精确 profile。结果待本轮完成原件核验，零件精确几何仍为本系列待完成项。按统筹指令记录正常在跑状态后结束本轮等待。


## 新公开原件审计与统筹发现的 runtime 准入阻断

- 新公开 [42361458023](https://github.com/YJBeetle/SWCLI/actions/runs/42361458023) / `c95ecdefa40689b2c8723a2e85998bbde2b6633f` completed/success，artifact `13569274991`，名称 `table-defaults-public-42361458023-1`，GitHub/ZIP SHA256 `f1877623dfc909900ba9784644e4266809d67afd68dd109feee49f42c82e66ad`。
- 该 run 的全新原 ZIP、官方 metadata、报告、trace、journal、CAD 文件和独立 audit 保存在 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42361458023/`。可复跑命令和完整路径见 `docs/verification/table-defaults-public-42361458023.md`，审计脚本为同目录 `audit-table-defaults-public-42361458023.py`。
- 独立重算 57 个表格请求、8 setters / 274 getters、120 CLI 事件、4 SDK 和 4 MCP bridge 回执、完整 lease/stamp/CAS 参数、另存/新 handle readonly reopen、10 handles 全关闭、空 catalog 和 daemon 退出。最长 native 请求约 1.271 秒，trace 跨度约 30.157 秒。8 项原件破坏和来源替换探针全部拒绝。
- 随后统筹本人复现合并阻断。旧 public adapter 仅按 revision/type/profile 放行，在 macOS 直接调用已接受的装配体 profile 也能进入 setter。因此该成功原件只证明其精确 head 的上述功能路径，修复后必须使用新提交 gate。
- 最小修复在 adapter 首次写入准入处加严格 native 探针。win32、kernel32 GetModuleHandleW(ntdll.dll)、已知 NtClose 导出、wine_get_version 缺失且新 last_error=127 必须同时满足。其余平台、Wine、异常或未知值均在文档观察/偏好读取前拒绝，mutation 双 false。内部 candidate 同样需要 native 证明，仅 profile 可在诊断进程内 bypass。
- 共享变更涉及 `src/swcli/hosts/windows_document_tables.py`、table job 的 CAD 前真实 runtime preflight。新 `tests/test_table_defaults_native_runtime.py` 覆盖直接 adapter 拒绝、Wine/未知/异常、no-op 也拒绝、零 setter/dirty/save，以及真实 handler 在 positive native probe 下的精确 profile 写入。
- macOS 当前实际 direct repro 使用真实 fixture、kind=2/native200=True、公共 adapter true→false，现为 ok=false，getter/setter/dirty 均 0，结果保存 `native-runtime-direct-repro.json`。通用测试 helper 只在明确的 fake native 业务路径内 mock positive probe，fixture 本身保持真实平台判断。
- 相关 41 tests 通过。完整 portable suite 本轮 1861 tests / 33 skips 通过。原有 part 几何硬断言、精确 profiles 和 600/1800 秒限制继续为系列门禁。修复公开 gate 只 dispatch 一次，正常运行保存链接后结束等待。


## 严格 native 准入修复的必要公开 gate

- 修复 head `5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b` 已推送。最终 native 探针针对实际准入的 changed 和 target self-noop 均有拒绝测试，相关测试 41 项及完整 portable 1861 tests / 33 skips 通过。后续仅文档记录提交。
- [42366316568](https://github.com/YJBeetle/SWCLI/actions/runs/42366316568) 单次 dispatch，精确 head `5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b`，mode `public`，`table_defaults_calibration=true`，`native_full=false`，类型参数 `assembly-drawing`。单次快照 `in_progress`，metadata 和输入保存在 ignored `run-42366316568/`。
- 新 head 先在 Windows 实际执行 strict probe，再准备 private runtime 和既有公开计划。当前 merge 仍等待本轮原件通过及统筹本人 review。c95 成功 ZIP 的独立审计明确报告当前产品代码与 c95 不同，防止把旧通过用于新 guard。
- 零件精确几何仍为系列未完成项，严格断言及既有精确 profile 继续作为门禁。系列整组完成后才请用户确认发版。


## 严格 native guard 的新公开原件验收通过

- [42366316568](https://github.com/YJBeetle/SWCLI/actions/runs/42366316568) / `5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b` completed/success。CAD 前真实 native Windows 探针与公开 gate 均成功。新 ZIP 为 artifact `13571309953`，官方/本地 SHA256 `337b23a2c96913725b3281a12325d918c539753e7a96fe6da4fabca6ed74f17b`。
- 新原件独立审核成功，产品树与该 head 一致。57 请求、8 setters / 274 getters、120 CLI 事件、4 SDK / 4 MCP bridge 回执、另存/readonly reopen、零件拒绝、空 catalog 和 daemon 退出均符合预期。单调用最大约 1.847 秒，trace 组跨度约 39.400 秒。
- 原始 report SHA256 `2d93886d6ceeda7afb8ca911d50f848b5bfbf7ab7ed388e6efb39589b96bf958`，native trace `00815ec92f37720ff090c7e32e43cc411d43e940a4f0fc9e97177a30aacaf572`。全部原始 artifact/hash、完整路径和可复跑命令见 `docs/verification/table-defaults-public-42366316568.md`，独立脚本为 `audit-table-defaults-public-42366316568.py`。
- 旧临时 venv 已被系统清理，当前审计环境改用工作树忽略目录 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/.venv/`，复跑命令已更新。
- 装配体/工程图精确范围可供统筹 review/合并，系列发版仍待原计划零件严格几何问题解决。
- 零件旧原 ZIP 已有首个关键线索。创建后 `geometry.centroid_mm.y=5.514537417020185e-16`，首次保存/只读重开后为 `8.271806125530278e-16`，均发生在表格写入之前。当前严格 table 比较跨越只读 handle 和重新打开的可写 handle，缺少当前可写 handle 在首个 setter 前的严格测量对照。下一项仅补该对照及留证，保留原 exact equality 和首错停组规则。


## 零件严格几何阻断的最早差异与最小对照修正

- 已从 `42269888379` 原 ZIP 再次核 SHA256 与 report SHA256，确认 `geometry` 与 `geometry_reopened` 的质心 y 在首次 table writer stage（trace index 40）之前已不完全相同。两次 measure stage 均完整结束，初次保存/只读重开的 y 差值为 `2.7572687085100926e-16 mm`。结构化对照保存在 `docs/verification/table-defaults-evidence/part-prewrite-first-difference.json`。
- 直接阻断仍是 exact geometry dict equality。当前证据把最早数值差异定位到 fixture 保存/重开阶段，但旧 run 没有可写 handle 在首个 setter 前的读数，尚不足以把该次差异归因于 table setter。`measure_part_windows` 对单实体读取 GetMassProperties(1.0) 并换算为毫米，原生 12 元组未保留，当前不推断更深的 kernel 原因。
- 最小修正补 `verify_part_before_write`。在首个 candidate setter 前，单次通过原测量函数读取完整 metrics/bodies，保存目标/前台 metadata，验证 context 未变，并与原 readonly baseline 做原样 exact equality。后续每字段和 save/reopen 的 exact equality 全保留。错误信息按实际 phase 命名，便于区分 pre-write 与 post-write 首错。
- 在既有 internal 文档类型选择中加 `part`，只执行原计划零件，避免重跑已验装配体/工程图。通用默认仍 all，600/1800 秒、单 owned host 和首错停组为硬限制。
- 审计器要求零件有完整 pre-write 数据及 exact/context 通过标记。新增单 ULP 质心变化在首个 table setter 前即被拒绝的测试，以及独立原件审核对 pre-write context/metrics 篡改的拒绝测试。Windows plain-child 测试覆盖 part/assembly-drawing 的参数路由和 exit 0/7，均不启动 CAD。
- 相关 44 tests / 4 platform skips 通过，既有 pinned internal [2,3] 原件审核继续通过，workflow YAML 解析通过。零件 profile 保持关闭。下一组单次 internal/part run 将补齐可写 handle 的因果对照，完成原件可用后再处理首因或确认后续最小修复。


## 零件首写前严格对照的单次必要验证

- 装配体/工程图经验证的候选 tip 固定 `5a4d861d9caf7c4b79ef9f288630aa06247e50d1`，对应公开 run `42366316568` / 产品 head `5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b`。统筹本人 review/合并使用该候选及其新原件。
- 后续零件诊断提交 `6396034fe941b28d90ced2b941ae0d6c26907be9` 已推送，产品 adapter/profile 与候选一致。该提交增加 pre-write exact 对照和 part-only CI 选择，尚待其自身原件。
- [42405733149](https://github.com/YJBeetle/SWCLI/actions/runs/42405733149) 单次 dispatch，精确 head `6396034fe941b28d90ced2b941ae0d6c26907be9`，mode `internal`，`table_defaults_calibration=true`，`native_full=false`，类型参数 `part`。单次快照 `in_progress`，metadata 与输入保存在 ignored `run-42405733149/`。
- 本轮验证会在任何 candidate table setter 前读取当前可写 handle，与原只读基线严格比较。该数据用于判断先前的 exact centroid 阻断是否在首写前已存在。原有全部 post-write/save-reopen exact 检查和首错停组规则继续执行。结果待完成原件核验。


## worker 恢复/late validator 回执的独立修复

- 统筹继续 source review 发现 `_worker_main` 原 except 会丢失 table setter 已知 mutation 及第一业务错误。本轮按 main `00f4538` 语义增加表格专用 helper，现有其他偏好 helper 由统筹合并时保留。
- 只接纳当前 `document.table-option-set` operation/action 匹配及精确两 bool mutation。第一业务错误保持 type/message，次级故障放入 `worker_error`。完整 payload 经现有 validator（含 finite UTF-8 JSON）验证，不可信字段降级最小失败，非法 native 文本复用 server 的可见转义。每请求 result=None 防止借用前一请求。
- 恢复不明的 NativeCommandRestoreFailed 仍使用原 envelope code、host-disconnected lifecycle 和 break 退休规则。未改变正常操作分派和 supervisor recovery 机制。
- 新测试执行真实 handler/adapter/native_api_sequence/worker，覆盖成功写后 restore fault、native 抛错或 false 后 restore fault、实际坏描述符、首错+late validator 降级、clean no-op、第二请求执行前失败无回执借用、严格 guard 及 JSON/text 降级。相关 126 tests 通过。
- 复跑命令、完整日志路径和各故障结果见 `docs/verification/table-defaults-worker-late-fault-2026-11-08.md`。异常路径按统筹指令用 portable fault injection 验证，无新增 native dispatch。本轮代码/测试/证据独立提交交统筹本人审查。
- 零件 `42405733149` / `6396034fe941b28d90ced2b941ae0d6c26907be9` 的受测历史保持不变，严格几何和其他系列范围继续作为原门禁。


## 零件 42405733149 已核原件并确认前置阻断

- `42405733149` / `6396034fe941b28d90ced2b941ae0d6c26907be9` completed/failure。Artifact `13588160547` / `table-defaults-internal-42405733149-1`，官方/原始 ZIP SHA256 `3a1d78b525c62488eb75d82324dd9551d8700333d74f0e2a623850e586876d92`。
- 首错为 `before-first-table-write` 的 exact equality，测量、解析 V/S 和 context 验证均已通过。table setter=0、table getter=3、显式 dirty setter=0、`writes=[]`。原有草图推断 global toggle 为 2 次 fixture disable/restore。cleanup 无错，worker exit 1。
- 体积三次均 `11999.999999999998 mm3`，面积三次均 `3799.9999999999995 mm2`，实体数1，x=`-7.058607893785837e-16 mm`、z=`5.0 mm`。创建/只读重开/可写首写前三次 y 依次 `5.514537417020185e-16`、`6.286572655403011e-16`、`8.271806125530278e-16 mm`。首写前与只读基线 y 差 `1.9852334701272664e-16 mm`。
- 已证明此次差异先于任何 candidate table setter，具体重开/访问模式/前后台或 kernel 数值路径仍未分离。当前没有保持原 exact 规则及测量语义的已证实有效修复，零件继续阻断，不无差异重跑。
- 完整原值、全部原始文件 hash、路径和可复跑原件检查命令见 `docs/verification/table-defaults-part-42405733149.md`，脚本 `audit-table-defaults-part-42405733149.py`。原件位于 ignored `run-42405733149/`。
- 统筹随后发现 post-setter writable/peer 再确认缺口，健康路径修复另作提交和一次既有 [2,3] public gate。worker late-fault 修复 `1d44a42` 继续保留，当前暂不能合。


## 2026-11-08 表格专属质心许可与健康路径修复

- 明确许可和实现范围见 `docs/verification/table-defaults-centroid-decision-2026-11-08.md`。此前 `42405733149` 仍是按旧严格规则失败，不改写、不追认。
- adapter 捕获并核对目标/前台 peer 的 Extension、身份、编辑上下文和 peer permissions；目标 state 读取前后均核对完整 peer。绑定每个 setter 后、实际 mutation 前再核对 writable/context/peer，避免健康 setter 后 drift 再进入 SetSaveFlag。显式 dirty marking 仍必须确认 dirty=true 和原 type/config，单次 setter、partial mutation/首错规则不变。
- 内部重验的装配体/工程图转换不得超出已有8项 profile；零件仅在内部 candidate bypass 下执行原计划3项，公开入口不扩值、不提前开放。
- 最终完整 portable **1880 tests / 33 skips 通过**；相关52项通过。日志 `docs/verification/table-defaults-evidence/approved-rule-guards-final-full-portable.log`。旧 pinned `[2,3]` 原件本地 preflight 复核仍通过：8 setters，原 report/trace digest 不变。这不证明新 adapter 原生通过。
- 后续单次 dispatch 保存 inputs/run/head/快照后交接，不持续轮询、不加 native 预算、不组内重启或重试、不建自动化。本工作树不 merge main/release。


## 表格专属许可与保护修复后的完整内部 run（2026-11-08）

- 修复已提交并推送 `f1881a7421200e46028652538892c15a366f2ef8`。完整 portable 1880 tests / 33 skips 通过，相关52项通过。worker late-fault `1d44a42` 已包含；健康路径 writable/peer/dirty 保护及仅表格 `1e-12 mm` 质心界限均在本精确 head。
- 单次 dispatch [内部 all run 42415716434](https://github.com/YJBeetle/SWCLI/actions/runs/42415716434)，输入 `native_full=false`、`table_defaults_calibration=true`、mode `internal`、document types `all`、`table_defaults_head=f1881a7421200e46028652538892c15a366f2ef8`。计划 `[1,2,3]`，零件3项及既有装配体/工程图8项，native600/group1800秒。
- 仅取一次状态快照：**in_progress**。原始 metadata、dispatch inputs 与 snapshot 保存在 ignored `docs/verification/table-defaults-evidence/run-42415716434/`。本轮尚无已审核完成原件，不能视为 native 成功。未启动 watcher/automation，不再轮询或 dispatch。
- 待该原件可用后核 ZIP/GitHub digest、exact head、完整计划、原始几何、setter/noop/CAS、save/reopen 和 cleanup。成功也仅为内部证据；固定完整3类型 profile/pin 后，仍需一次新 exact-head public all gate。零件公开写入当前继续关闭，统筹本人审查/main合并与最终发版不在本轮执行。


## 42415716434 原件通过，进入新三类型公开验收

- 官方/本地 ZIP `7e1d8fcd8c1d8b26346024305c0f30a0c77536b2ea4ade06f3c694e382db9e8e`，artifact13591813168；head `f1881a7421200e46028652538892c15a366f2ef8`。完整原件/逐字段/预算/target-peer-guard和原始几何核验见 `docs/verification/table-defaults-internal-42415716434.md`，可复跑脚本 `audit-table-defaults-internal-42415716434.py`。
- native完整组27.843395秒，最大harness阶段3.711325秒，11 setters/237 getters；单worker4192/host8968、wrapper exit0、cleanup空。原始metrics只有y有小幅差，最大1.5440704767656523e-16mm，按仅表格许可通过，其余几何严格一致。
- 手工新增part True→False/BOM0→1及目标同值，A/D8项不变，pin指向本轮全量原件。运行前remote/local preflight和必要portable/SDK检查，随后仅一次public all exact-head组，拥有独立600/1800秒预算和首错停组规则。
- 新公开结果尚待验证；内部成功不构成公开成功，不main合并、不发版、不触VM/DockerSW/MacSW。

- 本次promotion必要检查已通过：完整1881 tests / 33 skips，相关72项，SDK generator、strict mypy 6 source files与8 negative consumer refusals；remote/local新原件preflight均通过。日志在ignored `run-42415716434/promotion-{full-portable,related,sdk-types}.log`，remote结果同目录。


## 全三类型公开门禁已单次启动（2026-11-08）

- 精确候选head `9bb806b454cdcbcb225135886482a2e555044444` 已推送；仅part三项实测转换及self-pair新增，A/D8项与受测guard不变。完整1881 tests/33 skips、相关72项、SDK生成/strict/8 negative及新pin remote/local均通过。
- [public all run 42419965068](https://github.com/YJBeetle/SWCLI/actions/runs/42419965068) 单次dispatch，参数 `native_full=false`、calibration=true、mode=public、types=all、head=9bb806b454cdcbcb225135886482a2e555044444。固定内部run42415716434/artifact13591813168/原ZIP7e1d8fcd...为前置proof。
- 仅取一次状态快照 **in_progress**，metadata/inputs/snapshot已保存在ignored `run-42419965068/`。公开组拥有独立600秒native/1800秒group预算；新part3转换和A/D新guard旧8转换均走CLI/daemon/worker，SDK/MCP同daemon，包含readonly和独立save/reopen。首错即停组并保留原始回执/日志，不重试/回滚/换host。
- 内部原ZIP审核命令及所有12文件hash见 `docs/verification/table-defaults-internal-42415716434.md`，脚本 `audit-table-defaults-internal-42415716434.py`。公开run尚无已审核完成原件，不能声称公共通过或可合并。此处停止watcher/poll/dispatch，待原件可用再逐次审核，最终review/merge由统筹本人做；本任务不改main、不发版。
