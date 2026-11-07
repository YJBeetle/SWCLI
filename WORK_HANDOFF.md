# 表格文档默认设置交接

## 当前状态与范围

- 工作树 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI`；分支 `codex/docprops-table-defaults`；基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。只提交、推送本分支；main 合并由主协调负责，不发版。
- 五个非字体默认设置：`all.use_template_settings`、`bom.box_border`、`bom.grid_border`、`general.box_border`、`general.grid_border`。前三区分 part/assembly/drawing，General 仅 drawing。未实现表格实例插入/编辑、字体、图层、padding 或其他表格族。
- **尚未 merge-ready。** 33.5.0 装配体/工程图精确转换已按成功的内部原件限定开放，待同分支公开验收。零件写入继续关闭，系列完整验收仍待完成。
- 内部范围 `assembly-drawing`（类型 `[2,3]`，8 项）已在 wrapper 修复后的 run `42301331238` 通过。公开 gate 和 part 原生失败仍是本系列未完成阻断，默认完整计划保留零件精确几何断言。
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
