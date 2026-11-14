# 逐路集成交接

- 单位九字段有限profile已完成42935636514/459b0cf原件与统筹独立逐请求审查；整合保留86旧合同、新增2份单位合同，2773测试/39skip、SDK31负消费通过。详见docs/document-unit-profile.md及docs/evidence/units-main-integration-2026-11-11；未发布。

- main 已合入工程图出详图两个默认标量；代码、验收范围与原件摘要见 [出详图交接](docs/handoffs/detailing.md) 和 docs/evidence/detailing-main-integration-2026-11-07.json。
- 有界旋转凸台已完成本地集成及 1871 项便携回归（32 跳过）、SDK 与 CI 参数检查；精确产品 head 3922bee798b0b5b33dc6aa7a4bf34b01dc0e79ad，最终公开 run 42273047248。最终原始证据已独立核对通过，见 docs/evidence/revolve-main-integration-2026-11-07.json；原分支历史交接见 [旋转交接](docs/handoffs/revolve.md)；最终集成审阅结果单独记录，不将历史待验收状态冒充最终结论。
- 文档为滚动集成记录；不代表创建发布标签、完整发布验收或 Docker/Wine 晋升。

- 线性尺寸文档默认公差：最终产品 head59f29e8、公开42277528349已核原件；本次组合1910项便携测试通过（32跳过），SDK及统一CI预检通过，见 docs/handoffs/tolerances.md。

- Notes字体七字段：最终15d32ce/公开42279469524原件已本人核验，组合1974项便携测试通过（32跳过），SDK通过；该Notes子集已完成集成，整个系列待完成后发布。

- STL 参数宿主限制修复提交 f22b7a1 已通过公开原生验收 42302254750。

- 工程图线型四字段：宿主修复85ae6c1/公开42361465979原件已本人独立核验，精确范围和哈希见docs/handoffs/line-font.md及docs/evidence/line-font-main-integration-2026-11-07.json。

- 尺寸格式三字段：严格宿主修复e1d1870/公开42361878938原件已本人独立核验；三类39次setter及保存重开通过，组合证据见docs/evidence/dimension-format-main-integration-2026-11-07.json。

- 集成收尾保护：线型/尺寸格式在CommandInProgress恢复或late validator异常后仍保留修改回执及首错；恢复失败退休worker。真实handler/adapter的便携故障注入48关联通过，组合2094项/33skip通过。不是原生故障现场证明，原健康native原件保持。

- 文档图像品质：严格native宿主修复950c833/公开42361573569由本人复核；仅已证实零件品质字段，GLB细分控制仍未解决，不能当作已完成功能。

- 持久拓扑引用：f325943/公开42361455599原件由本人复核，单实体零件完整面/边 census 双射；非任意拓扑永久稳定保证。组合2160项便携测试完成（34跳过），SDK及14个类型拒绝例通过。见 docs/handoffs/topology-references.md 与 docs/evidence/topology-references-main-integration-2026-11-08.json。

- 总注释字体七字段、显示十字段（工程图五项）及GB往返六标准36转换：42361904486原件由本人复核；三setter描述符和worker异常回执已补保护。组合2520项测试完成（34跳过），SDK及31类型拒绝例通过。主CI保持不变，手动专项迁至独立document-preferences.yml。见docs/handoffs/document-preferences.md及docs/evidence/document-preferences-main-integration-2026-11-08.json。

- main自动CI42406720872暴露Windows测试夹具句柄清理、CRLF分类假设和PyYAML未安装三类问题；仅测试/CI依赖修复，30关联与2520本地项（34skip）通过，新Windows CI42412228332已成功。原日志及两摘要ZIP已核官方digest留存，详见docs/evidence/main-windows-portable-fixture-fix-2026-11-08.json。

- 表格默认设置：三类型公共42419965068/head9bb806b已成功，统筹已亲审原件及组合检查（2582项/35skip、SDK31拒绝例通过）；仅零件/装配3字段、工程图5字段的11条精确转换。历史交接见docs/handoffs/tables-initial.md，集成审计另记；当前系列未发布。

- 表格最终集成范围与机器记录见docs/handoffs/tables.md及docs/evidence/table-defaults-main-integration-2026-11-10.json；主CI保持原22输入，表格专项独立手动入口。

- 表格公共42419965068最终审核器与原件明细见docs/verification/table-defaults-public-42419965068.md；负责人纯文档tip c488b4c已合入，精确产品仍9bb806b，未改变生产实现或native结论。


---

## 单位路线历史交接（最终整合状态以本文件首段为准）

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

- operation `document.unit-profile`；CLI `swcli document unit-profile [--document ID] [--if-update-stamp N] --json`。返回 `unit_profile`：profile/document_type/values/native_units/linkage。
- operation `document.unit-profile-set`；CLI `swcli document unit-profile-set FIELD VALUE --if-snapshot JSON --lease TOKEN --if-update-stamp N [--document ID] --json`。
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

## 公共 CLI 验收已落盘准备（尚未执行）

- 新 `verify-document-unit-profile.py` 只调用已安装公共CLI；成功内部 native 报告/三类 fixture hash 为前置。覆盖三类文档读/raw9+5+linkage、后台身份、noop不dirty、lease/stamp/完整CAS拒绝、空domain零mutation回执、另存copy、fresh只读重开、原件/复制件hash不变。part独立V=12000/S=3800/质心(0,0,5) mm，原容差与完整before/after测量不变。
- 新 `run-unit-profile-public.py` 启动一次独立隐藏daemon、提前PID清单/health新PID排他、每CLI请求600秒、整组1800秒看门狗、一次关闭与PID清单恢复核验。启动失败不会向未证明端点发送stop；无重启、无失败API重试。
- workflow新增 `units_public_acceptance` 默认false；只有本分支 `workflow_dispatch + units_calibration + units_public_acceptance` 且前序校准成功才运行public step。full/release不改变。当前替代run来源6c314f7中没有该新开关，所以本次不会执行public准备代码。
- 当前准备源与校准源的 `src/swcli/` 没有功能变化，新增内容限验收脚本/测试/默认关闭接线/交接。
- 最新完整portable回归1851项通过（32 skipped）；随后增加公共开关接线与最终budget收口，相关33项通过，既有modeling接线12项通过（1 skipped）。原始输出 `public-preparation-portable.log`、`public-preparation-tests.log`。
- 公共准备测试含完整三类型流程，以及noop被dirty、CAS忽略、拒写mutation、readonly联动漂移、源文件变化、几何漂移、磁盘错误覆盖首失败、已有host PID拒绝、一次宿主启停/启动超时不向未证明端点stop等负向场景。
- 替代run `42262804840` 前置Windows3.9/3.14与package均通过，native job已从queued进入in_progress并初始化/准备安装。未取得native业务结论，未触发公共验收或其他run。待该同一run真实内部证据通过，再按新public head执行必要公共验收；不以内部绿灯止步，不在原生前宣称merge-ready。

## 拒写断言收紧（不重触发当前内部run）

准备公共验收时进一步收紧：预期空域拒写只接受 `UnitProfileCalibrationRequired` / `ValueError`，COM/API/RuntimeError 不能当作成功拒写。public按对应native fixture原始`refused.error.type`精确断言，非目标CAS漂移也保持有效Int32边界。相关34项通过，记录`public-refusal-tests.log`。

当前正在执行的内部run仍是6c314f7；新增校准脚本断言尚不在该run中，因此即使它绿灯，仍须人工复核每类原始refused.error.type与zero-mutation回执。若原件符合收紧断言，无需为纯断言收紧无信息重跑；若真实错误暴露则保存首失败并作相关修复。未来公共验收head将含收紧断言。此变动仍无 `src/swcli` 改动。


## 并发修复与公共准备当前交接

- 并发隔离修复提交 `6c314f7`；旧run `42260282974` 已精确取消并保存run/job/check原件；替代仅一次 `42262804840` / head `6c314f7d6466ccf4d7734c1127470c34e458258a`。
- 当前替代 native job `128049625609` 已实际获得runner并进入in_progress，不再挂在全局pending。最新观察仍在 `Free disposable runner disk for installation`，尚未进入units API业务；这不是单位功能通过或失败。原始run/job快照位于 `docs/evidence/units-profile/run-42262804840/`。
- 公共验收准备提交 `e21b4ad`，拒写异常收紧提交 `a439a18`。尚未触发公共验收，尚无public原生结果，不提供merge-ready声明。当前无其他代码未提交。
- 已准备后续公共命令：在此内部run原件审核通过后，使用含公共准备的明确head，手动选择 `units_calibration=true,units_public_acceptance=true,native_full=false`。该必要公共profile将先在同head准备/核对新fixtures，再运行公共CLI；不要在当前内部结果出来前重复dispatch。
- 若当前内部run失败，先持久下载该run原始产物及首个真实失败，按相关修复行动；若绿灯，仍须审核三类完整snapshots、原件hash、readonly重开、part几何及refused.error.type再执行公共profile。后续source纯断言收紧不要求为相同已证明事实无信息重跑。
- 新CLI入口应写为已安装 `swcli` 或 `python -I -m swcli`；文档已纠正选择器为实际 `--document`。九字段changed-write、scalar/system跨系统联动与写入持久性仍未验收，空白名单保持不变。

## 内部原生校准已审阅通过，继续公共 gate

`42262804840` / head `6c314f7d6466ccf4d7734c1127470c34e458258a` 最终success。原始Windows artifact ZIP保存在 `evidence/units-profile/native-42262804840/original.zip`，SHA256 `00545f8a24b4998b5bdf43582ed80d8c85c777926b93400a62f3bffde49b351f`；解压原件在同目录`original/`。ZIP/native文件仅持久本地，未提交至仓库。完成run/job/artifact元数据、原始report及review在 `docs/evidence/units-profile/run-42262804840/`。

原始report SHA256 `46fc0ccfa42a7ccf0ac98d31675b79b24ddde808f3319ff3363bb0239c5a2bca`。5170 begin/end边界完整匹配、无error事件、最长10.234秒、全组39.437秒、cleanup_errors空。part/assembly源MMGS，drawing源IPS。三类noop零mutation/不dirty，拒写均明确ValueError且zero-mutation；before/after-refusal/readonly-reopened完整snapshot精确一致，原始native文件hash与报告一致。part V约12000、S约3800、质心约(0,0,5) mm，原始严格容差与精确重开比较通过。

这仅证明此三fixture的内部读取/CAS/拒写范围；没有changed-write证据，不开放任何写白名单。已按用户延续授权继续公共验收，无待审批动作，也未遇自动审批拒绝。本轮公共准备关联34项与SDK generated --check通过，将对明确新head仅执行一次`units_calibration=true,units_public_acceptance=true,native_full=false`公共profile，仍不合main/不发布。

公共CLI gate仅手动触发一次：[42273356741](https://github.com/YJBeetle/SWCLI/actions/runs/42273356741)，head=`ca892d83eab6baca0f456050d501ee141cb20133`，参数=`units_calibration=true,units_public_acceptance=true,native_full=false`。精确head已核对，初始原件位于`docs/evidence/units-profile/public-42273356741/run-initial.json`。这不是新的写能力校准；只验证现有公开读/noop/CAS拒写入口。当前无待审批动作，未遇自动审批拒绝；不操作VM、不触碰DockerSW/MacSW、不合main。待公共原件结果后才能提交该精确只读/保护能力的merge-ready清单。

## 手动路由空绿漏洞：已确认并最小修复

统筹提示对应本路实际漏洞成立：错误ref + `native_full=true,units_calibration=true`可进入native job，却因`!units_calibration`跳过full步骤、因错误ref跳过units步骤而空绿。正确ref的full+targeted也语义互斥；public=true/calibration=false应明确拒绝。

新增无secrets的`units-route`轻量manual-only前置job（独立Python3.14），调用`validate-units-route.py`：拒绝full与targeted混用、拒绝public缺少calibration、拒绝targeted错误ref。native job对manual事件要求该前置success；push/tag原路径仍按原条件运行，full/release原group和PR secrets边界不变。24组ref/开关真值表、非manual拒绝/默认tag路径、真实workflow前置依赖测试通过；关联34项与既有modeling接线12项（1 skipped）也通过，YAML/diff检查通过。

当前唯一公共run `42273356741` 参数合法且来源`ca892d8`，不取消，不因这个CI-only路由修复无信息重跑CAD。其结果证明对应合法profile的业务源；可合tip须包含本路由修复并列明此差异。当前公共native仍在准备安装，暂无公共业务结论。无待审批动作。

## 公共run首失败：几何精确比较，公开步骤尚未运行

`42273356741` / head `ca892d83eab6baca0f456050d501ee141cb20133` 最终failure。失败step为内部`Calibrate bounded document unit profile`，首个真实失败 `RuntimeError: reopened geometry changed`（part第一例）；公开CLI step未执行。不是route问题，也不是secrets/安装失败。清理成功，无API重试或组内重启。

原始ZIP持久位于`evidence/units-profile/public-42273356741/original.zip`，SHA256 `af2b1a72555eb1bdafd0f27b683b691d7ca2c21e42a7174c4c363e3cbfb20e1f`，与GitHub artifact digest一致。原始run/job/artifact元数据、失败report与首因摘要在`docs/evidence/units-profile/public-42273356741/`。保留旧成功内部run证据，但不以其替代本次失败。

原实现对重开几何先做原解析容差检查（均已通过）再做原字典精确相等；后者失败。然而报告只存before，遗漏了重开actual，无法判断差异大小/具体字段，更不能直接声称ULP或几何不变。没有放宽任何断言。

相关诊断修复：每次测量先持久记录完整native测量，再运行原V/S/三轴质心解析检查；精确比较前记录before/after、逐字段差值和float.hex。保留原`before==after`、原rel_tol=1e-7/abs_tol=1e-5不变。新增测试确认一ULP也仍然失败并已持久保存actual，解析检查失败同样保留原测量。

关联36项通过，完整portable1858项/51.485s通过（32 skipped），记录`geometry-diagnostic-tests.txt`与`geometry-diagnostic-portable.txt`。这仅修复证据缺口，不宣称原几何差异已解决；计划仅对此相关修复head做一次有信息的新验证。若复现则按原件协调，不自动降级容差。无待审批动作，仍无merge-ready tip，写域为空。

相关诊断修复提交`39409386d628bc439f1be3197aed07ede23556c3`已推送；仅触发一次有信息验证：[42277659656](https://github.com/YJBeetle/SWCLI/actions/runs/42277659656)，参数`units_calibration=true,units_public_acceptance=true,native_full=false`，精确head已核对，原始初始元数据在`docs/evidence/units-profile/diagnostic-42277659656/`。不是无差异重跑，原因是旧失败缺失重开actual；新head会保留该actual并继续使用原精确断言。公开gate仍需内部严格全通过才执行，若复现不会跳过或放宽几何比较。当前不具备可合资格。

路由修复`9d6b033`的push CI `42275204523`已success，仅CI路由/测试差异、不改`src/swcli`。当前业务实现相对公共失败head仍无功能变化。已有授权覆盖正常提交/推送和本次有界验证，无待审批动作，也未遇自动审批拒绝；后续若涉及更改既有几何断言须明确协调，不能自行放宽。

## 独立mock实证阻断：产品已修复（尚缺修复后精确head公开native）

只读引用统筹的`docprops-coverage-ci/.../docprops-handler-peer-review-2026-11-07.md`与`artifacts/.../repro.py`，没有修改其他worktree。当前确实存在原handler描述符异常丢mutation及同ActiveDoc指针下peer自身变化漏检；不是原生现场故障，不将mock结论冒充native。

产品最小修复：

- 两个units-profile handler使用本组专属`_with_unit_profile_document`收尾。describe/registry收尾异常将ok设false，保留adapter的mutation/native_return_value/observed/before；若已有业务error保留其首次type/message，仅附加`document-descriptor-unavailable` warning，不伪造新鲜descriptor、不重试、不回滚。
- adapter捕获前台peer自身`_state`（type/stamp/dirty/configuration）与title/path身份；每次guard校验同一ActiveDoc及peer这些值、打开catalog身份，同时核目标title/path与打开身份。前台就是target时允许setter合法stamp/dirty变化，不将目标当另一peer检查。漂移拒绝、partial回执保留，不恢复被改的peer。

完整handler测试经真实`execute_operation`（lease/stamp预检），成功adapter及首业务失败后describe抛错均保持schema有效partial。真实`server._worker_main`不mock execute或result validator，验证相同两条路径的response.result仍有双true mutation和原错误；附reader收尾失败schema测试。

统筹原独立repro脚本在当前修复源上再次只读执行：mutation_reached_response=true；stamp/dirty/title/path四个同指针peer探针全部ok=false、partial双true、peer改动保留。原始JSON `docs/evidence/units-profile/peer-product-fix/independent-repro.json`。

完整portable1864项通过（32 skipped）；随后补充peer配置/关闭catalog、目标identity、dirty mark中peer变化、reader peer变化、前台就是target的stamp变化，相关45项通过；SDK generated/strict types/8负向typing也通过。记录同目录portable/targeted txt。这些是便携与mock证据，**不是修复后native验收**。

当前诊断run `42277659656`来源`3940938`仍是旧产品源，不因本消息取消或重复；它仅用于现有几何首因诊断。产品修复提交推送后，最终精确head必须执行必要public gate；不能用旧head校准或mock已修复直接给merge-ready。现无待审批动作，changed-write域仍为空，未改任何几何断言。

## 产品P1修复后精确head的必要public gate

修复提交 `5f307d1f4fa908acbcc25b59f6be7c32c3ed24fa` 已推送。相同用户授权下，仅对该精确产品head触发一次必要public验证：[42279525986](https://github.com/YJBeetle/SWCLI/actions/runs/42279525986)，参数 `units_calibration=true,units_public_acceptance=true,native_full=false`，实际head已核对，初始run原件 `docs/evidence/units-profile/product-42279525986/run-initial.json`。

旧几何诊断run `42277659656` / 3940938继续保留，最近观察在安装；本次新run由同一分支profile group串行等待旧运行，未取消旧run或其他人的run。两者目的不同：旧run保留重开几何actual定位首因，新run验证已实际修改的产品peer/回执保护。不得以旧head的任何绿灯作为P1已原生修复，也不能因新guard而跳过/放宽几何断言。最终merge-ready仍取决于新head严格内部与public原件审核。

官方源复核：ISldWorks.GetDocuments返回本session打开文档数组（https://help.solidworks.com/2021/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~GetDocuments.html）；本组foreground快照沿用现有`_state`的IModelDoc2.GetActiveConfiguration，2025文档标注已由IConfigurationManager.ActiveConfiguration取代（https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~GetActiveConfiguration.html）。本次不旁路改写旧A17/A18 helper、不在失败后切API重试；按既有兼容路径的实际native结果核验。

## 本轮收口（覆盖此前继续迭代计划）

按用户最新范围收口指令，本轮只取一次状态，不再持续sleep/轮询/无变化播报，不创建单CI automation，不新增审查代理、功能或计划，不为凑齐无限迭代。未rebase，不改main（统筹已保留的0e72beb detailing/revolve合入不受本分支影响）。现有授权无待审批/自动审批拒绝事项。

一次快照：

- 最终产品修复业务head `5f307d1f4fa908acbcc25b59f6be7c32c3ed24fa` 的唯一public run [42279525986](https://github.com/YJBeetle/SWCLI/actions/runs/42279525986) 仍in_progress，native job `128106109186` 正在Install native SOLIDWORKS，无已记录失败。快照已保存 `docs/evidence/units-profile/product-42279525986/closeout-snapshot.json`。不取消，不重复dispatch，后续由统筹分次快照跟进。
- 旧诊断run [42277659656](https://github.com/YJBeetle/SWCLI/actions/runs/42277659656) / `3940938` 已failure，step=Calibrate bounded document unit profile，public CLI未执行。现已处理可用原件，不因本轮消息再触发任何运行。

旧诊断原件：artifact ID `13535157052`，本地ZIP `evidence/units-profile/diagnostic-42277659656/original.zip`，SHA256 `016c5cb5b21f9ee659eb0a5f1506fe4bfc60786b3379625af1d02f476b96e8ba` 与GitHub artifact digest一致；解压原件在同目录original。失败report SHA256 `1a5269b9d0745e8c5b582aeaa2db2942516efea8c27ce97f646b5ce49b70f4c7`。原始report/artifact元数据/首因摘要/状态快照位于 `docs/evidence/units-profile/diagnostic-42277659656/`。

首个真实失败是part拒写后对比 `unit observation changed geometry`。新增诊断完整记录：V/S/体数/质心z无差异，质心x由 `-7.058607893785837e-16` 到 `-1.102907483404037e-15` mm，delta=`-3.970466940254533e-16`；质心y由 `5.514537417020185e-16` 到 `6.286572655403011e-16` mm，delta=`7.720352383828262e-17`。解析容差检查通过，但原字典精确相等仍失败；cleanup_errors为空。只陈述返回测量差异，不能据此归因单位API造成物理几何变化，也不把它改称通过。精确断言未放宽，未重试/回滚/组内重启。

收口结论：**目前无可合tip、无已完成public验收子集。** 旧内部read/CAS run42262804840/6c314f7的通过仅是旧源内部三fixture证据，不能替代修复后5f307d1公开验收。产品P1修复及独立mock/handler/worker/便携证据已落盘；最终public严格结果仍待统筹后续取证。九字段changed-write、scalar/system联动和写入持久性均未验收，白名单仍空。本轮就此停下，不新增迭代。

## 继续系列后的最新首因与待统筹决定（未后置）

已保存并核对`42279525986 / 5f307d1`失败原件。artifact ID13536485767，ZIP SHA256 `c2dc13ce277eee306cce349b5b9a28fd3348b7a8a8dfdf5d9718002d86f278eb`与GitHub digest匹配，本地`evidence/units-profile/product-42279525986/original.zip`；run/job/artifact与原始report在`docs/evidence/units-profile/product-42279525986/`。首因仍为part重开几何dict精确比较；仅质心y delta2.7572687085100926e-16 mm，V/S/体数/x,z精确一致。public未执行，P1产品修复尚未取得公开验收，不给可合tip。

未扩新字段/功能，未把未完点后置，未新dispatch或持续poll。发现本仓库已有冻结的`unchanged_depth_metrics`处理独立kernel浮点观测；已准备可审查最小patch（未应用产品），复用原函数阈值、保留全维度、原解析几何、raw/hex及所有状态/CAS精确断言。隔离快照47项测试通过，两份失败原始数值的离线重放保留exact_equal=false且满足既有kernel判据。这不是native通过。

详见`docs/evidence/units-profile/kernel-comparison-proposal.md`、同名.patch、proposal-tests.txt及proposal-replay.json。因原指令“不放宽几何或状态断言”，该接受范围调整需统筹明确确认，当前未擅自应用或重跑。本系列继续推进的具体阻断是这个比较口径决定，而不是以收口简单后置。没有sandbox自动审批拒绝；这是原用户验收约束的实质变更待确认。

## 最新继续指令下的明确状态

继续处理失败CI和本系列既定范围，不将“停止持续poll”解释为停止功能，不把未完点简单后置。当前首因已收敛并给出可审查修复：已推`6a8b338`的失败原件、精确差值与仅复用仓库既有kernel判据的提案patch；47项隔离测试和两份已保存原生观测离线重放完成。产品源和现有几何断言仍未变，P1产品修复业务head仍5f307d1；没有正在执行或新增的CI run。

统筹最新再次明确“禁止放宽断言”，因此不能自行把这个提案应用后宣布问题解决。需统筹本人裁决：单位脚本额外dict精确比较是否可以纠正为本仓库既有`unchanged_depth_metrics`（函数及阈值原样复用、所有V/S/xyz维度/原解析几何仍检验、raw/hex保留，所有状态/CAS仍精确）。这是一项具体可审查的验收口径决定，不是普通提交/push/CI授权或sandbox审批问题。若允许，接下来是在既定单位范围应用此最小patch并做必要精确head公共gate；当前未擅自改断言、未做无差异重跑、没有原生API重试/回滚/组内重启。

## 用户明确批准的窄质心界限已应用（替代此前等待裁决状态）

统筹转达用户原话：“允许这个仅限单位路线的质心界限”。批准仅为xyz各轴绝对差≤1e-12 mm；**不是**原提案max(1e-6,abs*1e-12)通用V/S/xyz阈值。无需再次确认，当前审批阻断已解决。

内部calibrate与public CLI脚本共用`require_unit_geometry_unchanged`/`record_exact_geometry`：仅xyz获得绝对界限，无relative tolerance；V/S仍严格数值相等、实体数严格int相等；有限值与完整metrics结构检查；原解析几何检查保持原样。raw measurement、hex、delta与exact_equal=false仍保留，新增accepted_under_units_centroid_bound记录该窄判据结果。所有state/identity/CAS及src/swcli产品P1逻辑未变；common model_checks.py未修改。历史宽提案明确标注未批准/未应用，旧失败原件全部保留。

关联51项通过，含xyz正负边界/nextafter越界、无相对容差、NaN/+Inf/-Inf（before/after、各维度）、V/S正负一ULP仍失败、实体数类型/数量严格，以及public完整三类型流程的相同窄界限绑定和V/S/越界拒绝。完整portable1873项/47.118s通过（32 skipped），SDK generated --check和diff检查通过。原始输出与旧原生读数的**离线**新窄判据重放在`docs/evidence/units-profile/approved-centroid-bound/`；离线通过不是新native或翻转旧run结论。

本次仅完成已批准既定范围的最小修复，不新扩字段/写域/计划；将中文提交推送后仅对明确新head做一次必要公共验证。changed-write白名单仍为空，不合main、不发布，正常CI启动后只记录链接结束等待，不持续poll。

## 获批窄界限新head的唯一必要公共验证

修复提交`9d1d54633a0ad7f9a8149342f6d3b58b0e55b05f`已中文提交推送。仅触发一次：[42303169518](https://github.com/YJBeetle/SWCLI/actions/runs/42303169518)，参数 `units_calibration=true,units_public_acceptance=true,native_full=false`。实际head已核对，初始原始run元数据在`docs/evidence/units-profile/approved-bound-42303169518/run-initial.json`。本次覆盖P1产品修复以及用户已批准的仅质心绝对1e-12mm界限；V/S/实体数及所有state/identity/CAS仍严格相等，原解析几何与raw/hex/delta全部保留。

正常运行已记录链接，本轮结束等待，不持续sleep/poll、不建automation、不新建review agent、不新扩字段/计划、不触碰main/VM/DockerSW/MacSW。旧失败原件保留、不翻绿；新run未完成前无可合tip、无新native/public通过声明。后续由统筹分次取完成/失败原件审核，正式发布前仍由用户确认。原几何口径授权阻断已解决，无待审批动作。

## 获批窄界限run42303169518：内部通过，公开首因是非法测试token

精确head`9d1d54633a0ad7f9a8149342f6d3b58b0e55b05f`，workflow最终failure，step=Verify public document unit profile CLI。内部calibrate三类全部success/cleanup_errors空；原始part比较保存centroid_absolute_limit_mm=1e-12，V/S/count精确，accepted_under_units_centroid_bound=true，当前严格helper独立审计通过。质心例外没有扩到relative或V/S，也不是本轮首失败。

原始Windows artifact ID `13545229213`，ZIP SHA256 `885a31ad601536c74093c968550a11242c2ce7d870aeb78a890ff50f6487ebc9`与GitHub digest一致。本地ZIP `evidence/units-profile/approved-bound-42303169518/original.zip`及original/解压原件保留；run/job/artifact、内部report、host-report、公共CLI完整report及first-failure.json位于`docs/evidence/units-profile/approved-bound-42303169518/`。

首业务失败：public脚本用`l-not-owned`作竞争token，违反真实协议`^l-[0-9a-hjkmnp-tv-z]{12}$`，因此在protocol层返回ValueError，没有走到预期DocumentLeaseConflict。此前FakeCLI只模拟业务，漏掉协议语法。清理次因：stop返回success、daemon进程结束后立即采样仍见owned native PID6592；报告未等待native进程退出，不直接据此断言真实持久泄漏。

仅相关最小修复：

- 竞争session使用gate实际已获取的合法owner token，按同文档/不同session验证真实lease所有权拒绝；不申请竞争lease、不绕过公开gate。FakeCLI在本组操作前执行真实server.validate_request，新增旧非法token应在协议层拒绝、合法token应进入DocumentLeaseConflict的测试。
- 公开宿主wrapper从本次CLI报告核owned_by_daemon/hidden/unshared、新PID不在before库存，捕获该PID的SYNCHRONIZE句柄。仍只请求一次daemon stop；daemon退出后对这个已保留句柄单次WaitForSingleObject（10秒），确认native退出后再做原sorted(before)==sorted(after)严格库存核验；无API重试、native进程kill、回滚或宿主重启。捕获失败也仍单次关闭自己的daemon并保留首业务失败，退出超时仍失败，句柄关闭有证据。

关联56项通过，完整portable1878项/45.784s通过（32 skipped）；SDK generated --check、diff检查通过。记录`docs/evidence/units-profile/lease-exit-fix/`。窄质心<=1e-12mm及V/S/count/state/identity/CAS完全未变，src/swcli产品P1源未修改。本次中文提交推送后只对相关修复head做一次必要public gate，正常记录run后结束等待，不持续盯CI。无新范围/字段/计划，无待审批动作，无可合tip。

最小相关修复提交 `577309005a858c11543b5def253dca36e5d0c598` 已推送；仅对该head手动触发一次必要public gate：[42361728509](https://github.com/YJBeetle/SWCLI/actions/runs/42361728509)，参数 `units_calibration=true,units_public_acceptance=true,native_full=false`。实际head已核对，初始原件 `docs/evidence/units-profile/lease-exit-42361728509/run-initial.json`。旧失败及approved bound原件保留，不改其状态；本次无几何阈值、V/S、count、state/identity/CAS或src/swcli功能变化。正常运行记录链接后结束等待，由统筹后续一次性快照跟进，不持续poll/automation，不新增范围或代理。无待审批动作，无可合tip或public通过声明。

## 新原件最终审计通过：交统筹review的精确可合子集

只使用本轮新run `42361728509 / 577309005a858c11543b5def253dca36e5d0c598` 原件，workflow与internal/public均success。新artifact ID13571025062，373398 bytes，官方/下载ZIP digest一致：`92c718be6f704c350075ce4de8fbce5e621d81de40e77ae5b915d95d8e882e6c`。原ZIP完整路径`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/lease-exit-42361728509/original.zip`，原始解压同目录original/；metadata与三个原report在`docs/evidence/units-profile/lease-exit-42361728509/`。没有复用旧run原件作为通过。

独立标准库审计器 `docs/verification/audit-units-42361728509.py` 已复跑audit_success=true，98 CLI事件/三类case/15预期拒绝，5656 internal+5003 public native边界及预算均通过，public组44.359s，native PID9108单次关闭后句柄确认退出，PID库存[]恢复[]；合法owner token与竞争session有原CLI事件关联。原ZIP每份source/copy hash重算一致，全profile/state严格一致；V/S/count精确、质心仅获批绝对≤1e-12 mm，没有relative或通用kernel宽阈值。审计器10项边界/负向自检通过，且强制当前src/scripts-ci/workflow与验收head相同及changed-write白名单仍空。

完整可复跑**绝对路径命令**、head/artifact/digest/报告hash/精确范围及缺口位于 `docs/verification/units-42361728509-handoff.md`。最终可合tip为本轮完成审计文档提交（精确SHA由最终回复给出），其后相对验证head仅docs/auditor与本地原件忽略规则，无操作源码变化，可由独立命令复核。最终review/merge仍由统筹本人办理，本线程不合main不发布、不新增代理、不扩范围、不重复CI。

可合只限九字段read/raw5/linkage、公开precision=2 noop、lease/stamp/完整CAS/readonly/闭域拒写、save/reopen及owned生命周期的上述三fixture子集。changed-write/scalar/system切换/写持久性仍未验收、白名单空；P1异常故障注入是portable/mock证据，本轮native是正常正向/拒绝覆盖。不得宣称九字段写能力或全系列/发布已完成。旧失败原件原状态全部保留，正式发布仍待用户确认。

## 九字段原定完整收口清单（替代“本路已完成”的任何解读）

按统筹最新要求再次独立复审 run42361728509 / head577309005a858c11543b5def253dca36e5d0c598 的原 ZIP，audit_success=true、10项负向/边界自检通过、当前操作源与验收head相同。没有新CI或产品改动。已通过范围保持三fixture九字段读取/raw5/linkage、仅precision=2 noop、五类拒写、只读文件生命周期及owned退出；不是九字段全读写。

新增 `docs/verification/units-original-scope-closeout.md` 逐项列九字段既定目标与最小剩余验证。changed-write白名单仍空，公开完成0/9：八scalar真实setter/各目标保存重开、system独立联动与公共有限策略、审原件后手动精确domain、公开changed-write验收均未完成。当前CI不调用private校准写；公共system无条件拒绝，private仅system目标roundtrip也不构成完整联动验收，不能只填白名单宣称完成。

原计划scalar值/precision0与8端点、MMGS↔CGS/MKS/IPS/Custom有限方向不新增；端点不外推1..7、part不外推assembly/drawing、只读保存不外推写入持久性。剩余能力继续属于本系列，不能默认后置并发半组。“精确可合子集”仅是只读/noop/拒写代码可交统筹技术review，不是本路/系列完成或发布资格。V/S/count及state/identity/CAS全部原标准，质心只用用户已批准逐轴绝对≤1e-12mm；无相对容差、无通用kernel宽阈值。

本轮只完善既定范围交接，未扩字段/计划、未新增CI/代理、未触碰其他worktree/VM/main/tag/release；后续实现与必要新head原生写证据按此清单继续，不能用当前read gate重复运行代替。

## 2026-11-08：按继续指令实现原定真实写入路线

已落实private有限写校准、空白名单下安全关闭的system完整后态策略及公开changed-write验收入口，不停在清单。八scalar使用原catalog候选（包含精度0..8逐值，不凭端点外推）；system仅MMGS↔CGS/MKS/IPS/Custom八方向，模板实际来源及显式Custom准备过程全部记录。每目标单Set、native bool/partial、完整snapshot/raw5/19linkage、后台/peer/state/identity/CAS、源文件hash、保存/关闭/readonly重开/计划内writable重开和原始几何均保留；首次失败停止，无API重试、回滚或组内重启。关闭后不再查询旧COM handle。

生产`CALIBRATED_UNIT_WRITES`和`CALIBRATED_UNIT_SYSTEM_RESULTS`均空，当前公开写入完成仍0/9。公共system要求精确域与完整after hash，host及result schema一起核对；scalar非目标精确不变，补目标/GetUnits一致性。新public gate在任何CAD open之前核三类型完整候选/方向、精确domain、受审完整后态和原生文件hash；空表的public-write dispatch在Ubuntu preflight就失败，不接触私有native setup。后续只有审阅真实原件后人工启用有限域，再跑新head public，不自动填表或宣称完成。

完整说明`docs/verification/units-write-calibration-2026-11-08.md`。Python3.14.10完整portable1918项/51.783秒通过（32 skipped），关联55项通过；SDK generated/strict6文件和8负向typing通过，全部src/CI/tests的Python3.9 AST与workflow YAML/新模式isolated help导入通过。原始日志持久保存`evidence/units-profile/write-implementation-2026-11-08/`，hash/本地结果在`docs/evidence/units-profile/write-implementation-2026-11-08/validation.json`。首次全套仅因临时venv未安装SWCLI的-I导入失败，已安装editable后重跑，不改产品断言；首次工具输出摘录另存且明确不是完整原stdout。

本轮将只触发精确新head的private写校准：`units_calibration=true,units_write_calibration=true,units_public_acceptance=false,native_full=false`。正常启动一次快照即停，不持续轮询、不用VM或审查代理、不合main/发版。V/S/count/state/identity/CAS保持严格；仅既有批准质心xyz各轴绝对≤1e-12mm，无relative，raw/hex/delta/exact_equal保留。旧read run42361728509不为已改变的操作源提供新写入通过证明。

实现业务head `4f20723116103c6e5f43def9f3d42b5a91372903` 已中文提交并推送。仅触发一次 [42406393957](https://github.com/YJBeetle/SWCLI/actions/runs/42406393957)，已核 workflow_dispatch/head/ref；输入 `units_calibration=true,units_write_calibration=true,units_public_acceptance=false,native_full=false`。原始一次run/job快照及精确参数保存在`docs/evidence/units-profile/write-native-42406393957/`。该快照状态in_progress：units-route及wheel success，Win3.9/3.14前置检查运行中；尚无本轮native/public写入结果。正常快照即结束本轮，不持续poll、不重复dispatch、不cancel其他run。

下一步由后续一次快照取得完成/失败原件，保留第一业务错误、原native文件/raw数值/trace/sha，审139预定步骤的实际覆盖及600/1800预算/owned退出；若失败先处理首因，不跳过/降低守护或扩大V/S容差。只有原件完成审阅后，才手动填精确白名单及system完整后态，并对包含这些手动域的新head触发必要public验收。当前两表仍空、公开完成0/9、系列未完成，不能据本地合成139步骤或workflow启动标成九字段全读写或可发布。

## 42406393957失败原件：预算首因及仅相关持久化修复

官方artifact13588889164，5744172bytes，ZIP官方/下载SHA256一致`aa850757a3940f0d26ac6ccc8fc20a213842ad2ead2a21bab29b986d7dd5b7ad`。原ZIP/官方日志ZIP/安全解压保存在`evidence/units-profile/write-native-42406393957/`；完整元数据、相关日志、标准库独立审计与离线重放在`docs/evidence/units-profile/write-native-42406393957/`。reportSHA98be23a6b37edef57dd63312fd9c13578621d4dd4b1a13313f1b4d5bdc3a2cab。详细证据/绝对路径重现命令见`docs/verification/units-write-failure-42406393957.md`。

首个失败是1800秒group watchdog（trace首尾1800.297秒），0个native/API error，最大完成调用19.484秒，无600秒调用超限。part46完整private步骤（37 scalar+8system+1准备）有真实原件；assembly仅Custom准备+linear.unit inch/mm3步完整，第4步precision=0 Set True并保存但RO重开未完成；其余asm字段/方向及drawing未到达。共50个setter成功回执、49个完整步骤，无public，不能用139合成或旧read补齐。part92个几何比较V/S/body严格，16个保留exact_equal=false的质心微小变化，max3.970466940254533e-16mm及raw/delta/hex均核过，仅获批绝对≤1e-12mm。worker被杀，没有owned Exit/句柄退出确认，不以cleanup_errors空数组当成功。

仅修改写诊断重复全报告序列化开销：显式语义/观察/写前意图检查点完整持久化，每native begin/end/error仍fsync；default read原逻辑保持。真实报告离线1000合成getter保留2000 durable事件，完整序列化1002降2，本机3.61s降0.076s只是离线证据。关联70项通过、Python3.9 AST通过；src产品/白名单/schema/workflow/main property tests无diff，不扩大预算/容差、不减少guard/字段、不回滚或原生失败重试。main960839e的PyYAML及测试修复必须在统筹集成中保留，不整文件覆盖旧tests/CI。

仅对相关新head推送后做一次必要private验证，参数保持units_calibration=true,units_write_calibration=true,units_public_acceptance=false,native_full=false；正常一次快照即停，不持续poll或再开agent，不用VM/不合main/不发布。新原件前两表仍空、public0/9、系列未完成；旧run保持failure。

最小相关修复业务head`68b05c98e0a13000b4ac06002163d01820fba7b7`已推送。仅一次必要新验证 [42414478796](https://github.com/YJBeetle/SWCLI/actions/runs/42414478796)，head/ref/event已核，private参数不变。原始一次run/jobs及输入在`docs/evidence/units-profile/write-checkpoints-42414478796/`；快照in_progress，route success，Windows3.9/3.14及wheel运行中，尚无native结果。正常快照后结束本轮，不持续poll、不repeat dispatch，不把旧part/assembly原件清成全失败，也不把未测类型计通过。若新优化后仍触硬预算，先交实际时间分布供统筹评估，不改600/1800或拆组/少测。此后提交只docs，操作源保持68b05c98。

## 42414478796内部成功已独立审原件；人工有限域与三公共通路待验

官方artifact13591264000，10944652 bytes，下载/官方ZIP SHA一致`fdf66026e457ff035652acb0fde3d4929b8b0cadde41f0dbc2ca855ebf43e4f0`；原reportSHA`13a4b243b6362436ab200ee6db03928b0671ffbf1c5d31062467874838f68fd2`。原ZIP/官方日志ZIP/安全解压持久存`evidence/units-profile/write-checkpoints-42414478796/`。标准库独立审核脚本`docs/verification/audit-units-write-42414478796.py`无产品/gate/COM依赖，两次结果相同；metadata与`independent-audit.json`同名docs/evidence目录。绝对路径重现命令和范围在`docs/verification/units-write-42414478796-handoff.md`。

真实三类46/46/47共139步骤、281原生文件hash，八scalar全部37目标/类型、system八方向/类型以及4个显式准备步骤均闭环；full snapshot/raw5/19 linkage/保存RO/上下文及首错策略核过。421302 trace、210651完成边界，max3.453s、group357.297s，0 error；owned PID7892一次Exit/句柄退出确认，前后[]。part92几何比较V/S/body严格，40次保留exact_equal=false，最大centroid绝对delta3.970466940254533e-16mm；仅原批准1e-12，无relative。模板仅原hash入report，模板字节不在ZIP，未伪称重算模板本身。内部直接adapter没有registry lease证明，必须由公共阶段真实验证。旧失败原件不翻绿或清空已完成部分。

审核后人工录入137去重精确域/26完整system后态，固化原run/head/artifact/digest。仅33.5.0和PRT/ASM Default配置、drawing正常无模型配置；未测版本/配置拒绝，精确源不能外推任意值组合。无CI自动填表。真实公共gate升级为CLI/SDK/MCP各139共417步骤，SDK实际typed writer+generic其他操作，MCP实际一次stdio frontend的execute工具，全部同一个owned CAD/worker及同一1800组（600请求边界），不拆组/重置/少测。每通路完整正向/lease竞争token/stamp/非目标CAS/闭域/RO拒绝及保存几何；原始wire以JSONL每次fsync，语义/意图/最终报告完整持久化。仅显式public写模式wheel安装既有mcp extra；main960839e的矩阵依赖和property测试修复未覆盖。

真实SDK TCP/MCP stdio对假daemon的4项连接测试、137域逐项匹配、未测配置/版本/新getter漂移拒绝及合成417接线均通过；这些不是CAD证明。公共原生417/清理原件未完成前仍不能称本路/系列验收完成、合main或发布。下一步只触发明确新head的一次public必要验证，正常一次快照即停。

本轮待提交源完整portable1933项/59.706秒通过（26 skipped），最终47关联通过，真实SDK TCP/MCP stdio对假daemon4项通过；SDK generated/strict6文件与8负向typing、全部Python3.9 AST/YAML及isolated入口导入通过。持久原日志及hash `docs/evidence/units-profile/write-checkpoints-42414478796/admission-validation.json`。公共CAD417验收未到，不因这些合成/协议结果标通过。

最终追加SDK ProtocolError/MCP回复不一致时的raw回复保留，避免已执行写入的回执被校验异常丢弃；不重试。此最终失败路径修改及所有相关路由由48项/8.874秒通过覆盖；完整1933项记录为此前完整基线，未冒称运行了新增第1934项的完整套件。相关原日志/hash已追加admission-validation.json。

人工域与三通路验收业务head`ac8e7f26ced8148d16fe236280082d4f78ec9290`已中文提交推送。仅触发一次必要公共验证 [42423042929](https://github.com/YJBeetle/SWCLI/actions/runs/42423042929)，head/ref/event已核；输入三个units开关true、native_full=false。一次正常快照在`docs/evidence/units-profile/public-writes-42423042929/`：route/wheel success，Win3.9/3.14前置运行中，尚无公共native结果。首次run元数据HTTP EOF只补读该元数据，没有原生重试或重复dispatch。

正常快照后结束本轮，不持续poll、不建代理/automation。后续必须下载本run新原ZIP/digest并分别核CLI/SDK/MCP各139实际case、真实租约/完整CAS及拒绝、137受限域/26受审后态、保存RO/配置/状态/raw geometry、同一owned host/单worker、600/1800及MCP frontend/owned CAD清理。未到/失败不能以内部139或合成417补齐；若触硬预算先交时间分布评估，不拆组/少测/改限。当前公共验收仍未完成，main/release仍交统筹本人，未合/未发布。其后交接tip只docs，不改变ac8e7f26操作源。


## 42423042929 首错已审：可读 inch 不是合法 noop 写目标

官方 artifact13596036567 / 19290057 bytes，下载与官方ZIP SHA256一致`924c3bab00df410f36761d0ddd4fc03bf2fb554fb8ae3f7d53f5eb58230c72d8`；公共reportSHA`6b8ed34c531bec9c4df8f8caae514bc16ed9743a66a24272d29a1881a2767c12`。原ZIP/日志ZIP/安全解压在`evidence/units-profile/public-writes-42423042929/`，不改旧failure原件。标准库独立审计`docs/verification/audit-units-public-failure-42423042929.py`复跑audit_success=true；metadata/真实源快照/审计JSON见同名docs/evidence。详细可重现说明`docs/verification/units-public-failure-42423042929.md`。

首错CLI117/drawing25：真实源mass_properties.length_unit=inch/native3，原计划changed target=mm/native0。门禁把可读inch当noop目标，daemon协议校验返回ValueError unsupported candidate unit target，未到业务worker/native setter。更正此前“客户端前拒绝/零daemon”说法：到达daemon validation，零worker/零setter；原件不重写。CLI仅116/139闭环（part46/asm46/drawing24），SDK0/MCP0。116真实changed True，lease/stamp/CAS/RO各116及closed98；232公共原生文件hash、92part几何比较核过。单worker/owned退出确认/PID []恢复[]，public1487.031秒、最大完成native边界2.047秒，无nativeAPI error；内部139成功503.75秒独立记录，不补公共未到达部分。

只修门禁noop顺序：当前源属于合法候选保留原前置noop，否则成功合法changed write+完整guarded reread后，以实际合法目标noop，完整snapshot/raw/linkage/document/stamp/dirty状态严格不变。inch继续不可写，137域/26后态不变。真实drawing inch源反例覆盖三路后置noop及417changed次数；原ZIP快照经真实CLI解析/daemon handler返回同一ValueError，一次validation请求、业务worker manager零调用。增加transport/case耗时记录供硬预算时交原分布，600/1800、139x3、同ownedhost/单worker、lease/CAS/负向/RO/几何/单次清理不改，无拆组/少测/重试/回滚。

关联60项/14.361秒、完整1936项/63.407秒（26skipped）、SDK generated --check、三个改动文件Python3.9 AST及diff检查通过；日志/hash在`fix-validation.json`。src/.github/workflows与main property/PyYAML修复未修改。推送后只触发一次新公共验证并保存精确head/run一次快照即结束；公共全验收仍未完成，不合main/不发布、不用VM/代理/automation。


noop最小修复业务head`64af40c908c01ca20027d06799eaec702627e5ee`已中文提交推送；只触发一次必要新公共验收 [42664223806](https://github.com/YJBeetle/SWCLI/actions/runs/42664223806)。已核head/ref/workflow_dispatch，三个units=true、native_full=false，600/1800与CLI/SDK/MCP各139不变。初始run/jobs/精确参数在`docs/evidence/units-profile/public-noop-42664223806/`。该唯一快照in_progress，route/wheel成功、Win3.9/3.14前置运行中，尚无公共CAD结果。正常快照后结束等待，不持续poll、不重复dispatch/新代理，不合main/发布或触碰VM/其他路线。此后提交只docs，操作源固定64af40c。若后续失败保留首错与各transport实际完成边界，硬预算先交已新增的transport/case耗时分布，不改预算/拆组/少测。


## 42664223806硬预算首错与前端开销方案：未实施、未重跑

本次新原ZIP artifact13698368440/22180727bytes，官方及下载SHA256一致`5ac6169f03d869379d349e48c116d5ec7a204f7ab47d7fe68f7f933c875f34a9`；报告SHA`a3d4228f24e140e41fe9053c76b09c4152d06e6f3eb44c1f28d52b1a81e751ab`。原ZIP/官方logs ZIP/安全解压/整作业日志在`evidence/units-profile/public-noop-42664223806/`。标准库独立审计`docs/verification/audit-units-public-budget-42664223806.py`两次相同，错误digest/head两个负向检查通过；完整metadata/audit/timing在同名docs/evidence。日志摘录为派生文件，官方整作业字节和ZIP完整保留。

首因公共1800s watchdog（最终1801.344s），CLI139完整，SDK15完整/16已source-open回执并发create，MCP0。SDK16 create native operation end但wire回复未持久记录，无第155次setter，不能计完整。旧inch非法noop修复在CLI117真实通过；未到的SDK/MCP drawing不外推。154完整case/308文件hash、真实lease/stamp/CAS/RO各154+closed128、122part几何（68nonexact保原批准界限）逐项核过。633590 trace、154setter、单worker，native APIerror0，308仅预期lease/stamp operationerror，最大完成边界1.781s。内部139成功466.906s独立记录。公共超时后stop被ActiveDocument拒绝，daemon终止、owned native退出未确认、pids_after缺失，不能称清理通过。

按统筹“先交硬预算分布”的指令，没有改预算/步骤/域/guards/geometry或先派CI。CLI139case1657.457s/4677调用1594.368s；SDK15case90.562s/538调用45.322s。离线真实fresh CLI subprocess20次median约0.146s；父进程cli.main函数直调约0.006s，只是下界、不是常驻CLI或逐次进程验收。现有本机Python3.12对原26MB完整报告pretty/compact各5次编码写入fsync回读，median约0.349/0.083s，内容全等；3.14差异小，不混用结论，均非Windows保证。

亲审提案`docs/verification/units-public-budget-42664223806-review.md`：只去WriteGate完整报告缩进保持全部字段/检查点/fsync；另需root决定能否接受单隔离CLI helper进程调用真实main/parser/RPC、减少每command冷启动的策略变化。明确失去逐command冷启动/进程隔离覆盖，不得以SDK或函数直调改名假称原CLI策略。拟定IPC序号/原stdout-stderr/失败不重发或重启/一次关闭/相同600-1800与139x3要求及关联+全套portable后必要一次新public。尚未实施任何候选，操作源保持64af40c，仅文档/独立诊断。root统一占用Windows VM，本路不碰VM/main/其他路线、不发版。

用户已在本聊天明确授权向统筹chat发送本次证据和首因，随后成功送达上述原件/审计/提案绝对路径；此前自动审批拒绝发送的请求未绕过。等待root亲审前端策略，不无差异重跑。


## 统筹批准后实施：隔离CLI复用与本run身份句柄收尾，待root审核再派CI

统筹随后亲审并明确批准第1项compact、CI专用隔离CLI前端及最小owned native清理方案。实现/证据说明`docs/verification/units-public-budget-fix-review.md`。仅单位WriteGate改成一个隔离python -I helper逐帧调用真实CLI main/parser/RPC，报告明示isolated-reused-cli-main，不宣称139次冷启动；每文档类型额外一个真正独立python -I -m swcli只读探针对照同未变完整snapshot/state，两份raw stdout单独记录。请求JSON原文/回复frame/CLI stdout-stderr-returncode逐次fsync，序号/EOF/异常/超时/unknown和partial保留，无重发/重启；helper路径/hash/PID/安装CLI SHA/一次退出wait明确。SDK/MCP各139、同ownedhost/worker、417/600/1800与所有guards不变。compact仅去完整semantic报告缩进，全部字段/历史/检查点/fsync保留，其他门禁仍逐次CLI进程。

单位write wrapper运行中尽早抓取并持续持有native句柄：owned/hidden/unshared、PID不在原库存、GetProcessId/CreationTime窗/本CI完整已安装SLDWORKS.exe路径验证；不在失败后重开PID寻找替代。一次正常stop失败后，只对同一handle重核identity并最多一次TerminateProcess+wait/库存，首错与ActiveDocument/forced/清理次错都保留；强制退出即使确认也不翻绿，无身份不kill。helper父进程正常一次wait，wrapper另只读持有已核helper Python handle确认EOF退出，不申请其TERMINATE权限、不碰未知PID/树/按名清理。

最终关联84项/23.473s通过，完整1960项/75.689s通过（26skipped），SDK生成/strict6/consumer负向8项通过，改动8个CI/test文件Python3.9 AST/diff通过。原日志/hash/源码SHA在implementation-validation.json。真实fresh与已实现隔离helper的假daemon TCP各20次逐字节一致，median约0.143092/0.006465s，starts1/exit_waits1/exit0；只作本机协议/进程证据，不保证Windows1800整组。产品src/域/schema/workflow/main property-PyYAML/geometry不改，VM未用，未合main或发版。已把未实施历史提案标注后续实现，旧run failure/unconfirmed不翻绿。

本次待中文逻辑提交推送后交root亲审精确head；尚未发新的public CI。root审核后才一次必要新公共验收，正常一次快照即停；不以旧CLI139/SDK15或本地1960项补SDK/MCP缺口。


## 统筹亲审后唯一新公共验证42818564935：初始快照即停

统筹核473b26a的5个CI实现/3测试与日志SHA后批准精确tip`473b26a06e09538a4565cc0adb765988f61b44ee`唯一新dispatch；另报告其正确安装本分支后54关联/21.406s（1skip）通过。其首次已安装main造成identity mismatch属于环境错配，纠正安装后通过，不归为产品失败、不放宽identity guard；本路本地84/1960及SDK证据仍独立保留。

派前核本地/远端同为该精确head、干净状态、同head workflow_dispatch数量0、单位分支没有未完成manual run。原workflow SHA/concurrency表达式及查询摘要在`docs/evidence/units-profile/public-frontend-42818564935/preflight.json`：单位并发组`swcli-units-read-cas-refs/heads/codex/docprops-units-expanded`，与main/其他ref不共享，cancel-in-progress=false且无workflow级共享取消。未cancel任何run，不重跑旧head。

只派一次 [42818564935](https://github.com/YJBeetle/SWCLI/actions/runs/42818564935)，精确head/event/ref已核；三个units=true、native_full=false。初始一次run/jobs/原dispatch回执与actual route inputs验证在同名docs/evidence目录。初始快照in_progress，route success，Windows3.9/3.14和wheel前置in_progress；从此同一次snapshot的已完成route job官方原日志核实际ROUTE_* env以及Validated native route: units-write-public，非仅复述请求flags。原查询JSON/route原日志保留同名evidence目录。gh初次拒绝输出控制字符，只用允许原字符并重定向文件补取该日志，不是新状态poll或再次dispatch。

正常快照后停止等待，不连续poll，不用VM，不合main/发版。新run尚无public native结果，旧42664223806的failure、CLI139/SDK15/MCP0和owned退出unconfirmed全保留。后续必须核本run新ZIP/digest、CLI/SDK/MCP各139+三额外独立读探针、同ownedhost/worker、600/1800、原始完整JSON/原生持久化/geometry与helper/native真实退出；原生API首次失败不重试，强制收尾不得翻绿。此后提交仅元数据/交接文档，业务源固定473b26a。


## 42818564935 portable失败：平台文本writer字节修复已获条件批准

官方terminal run/jobs/artifacts已各取一次；复用root原failed.log，原日志SHA`8d614a43c26f600194b6c0fa3e503475acacd73b2cba5667359dfeb11be848a4`。四个官方原ZIP各一次下载且digest全核同（dist13766028046、package summary13765898140、portable3.14 13765683939、portable3.9 13764544642），清单与独立审计在`docs/evidence/units-profile/public-frontend-42818564935/`，原件/解压/failed.original.log在同名evidence目录。旧initial记录不改；原473b run仍failure。

两Windows各1960测试只失败同两frontend compare：fresh CRLF vs旧StringIO LF；3.9耗245.823s/skip11，3.14耗184.297s/skip4。最早3.14 actual_cli_read记录UTC12:49:09.9024458Z。native job skipped，私有/公共CLI/SDK/MCP各0CAD，无native ZIP；非identity/原生API首错，不拿旧run局部补齐。标准库独立审计复跑一致，坏head/原ZIP拒绝。

只改两CI helper和关联测试：真实TextIOWrapper(BytesIO,newline=None)按平台写出，stdout UTF8、stderr该-I子进程实际codec/errors；-I忽略PYTHON环境变量，不假定stderr一定UTF8。严格base64保存原stdout/stderr，文本/codec只审计；parent直接用原bytes构造CompletedProcess，不decode再encode或normalize比较。未知/坏字节保原件并拒绝。保留中文/LF/CRLF/孤立CR标准writer输出及CP932非roundtrip bytes，identity/序号/argv/RPC/fsync/无重发重启、三cold probe、417/600-1800/几何/宿主收尾不改。产品src/workflow/其他业务helper不改。

最终90关联25.396s、完整1966项101.419s（26skip）、SDK生成/strict6/consumer拒绝8项、Python3.9 AST4文件/diff全过；源码和原日志SHA见stdio-fix-validation.json。统筹亲跑stdio/frontend17项9.866s通过并锁四文件SHA，本地逐一匹配；条件批准同SHA且全部检查过/无其他业务变化后，中文提交推送再自行必要一次units-write-public，派前remote=精确head/干净/同head未派/独立并发核对。详细说明`docs/verification/units-portable-stdio-42818564935.md`。尚无新Windows/CAD证明，VM/main/release未动；新公共正常一次快照即停，不持续poll。


## 条件批准四SHA未变：stdio修复唯一次新公共42865595677

四文件与root锁定SHA、90关联/1966完整/SDK/AST/diff条件逐一匹配；审计与修复已分开中文提交推送（b413238原件审计，业务head`085ae73570f023706319738d1130fd21256e4144`平台writer+B64原字节修复）。相对a53业务路径只有这四文件，src/workflow/geometry/预算/其他helper均无diff，原473b失败证据及0CAD结论保留。

按条件批准只派一次 [42865595677](https://github.com/YJBeetle/SWCLI/actions/runs/42865595677)，已核官方head/event/ref。派前remote=085ae/工作区干净/官方同head manual count0/单位分支无未完成manual；单位ref独立并发组、cancel=false、无workflow级共享取消，不cancel main/其他路线。实际三个units=true、native_full=false由此一次初始snapshot已完成route job官方日志核实，Validated native route: units-write-public。

初始run/jobs/receipt/preflight/actual-route原件在`docs/evidence/units-profile/public-stdio-42865595677/`，原查询与route日志在同名evidence目录。该唯一快照in_progress，route/wheel success，Win3.9/3.14前置in_progress；尚无新Windows完整结果或公共native证明。正常快照即停止等待，不连续poll、不再dispatch；VM/main/release均未动。此后只文档快照提交，业务源固定085ae。后续必须先核本run Windows前置、原ZIP/digest，再分别核CLI/SDK/MCP各139+三额外fresh读、同host/worker、全部守护/持久化/geometry/600-1800及真实helper/native退出，不把本地writer仿真或旧run局部算作通过。


## 42865595677原生阶段身份首错：先补观测，不改准入/不派native

已单次取官方terminal metadata，复用root原failed日志SHA38c14c1bdb3cc942bbf702b71231bb205afc0833816be7d3e9d9a02ae2d101be。native13790060166 ZIP10930120bytes/SHA207a75330e6bb35b368f2d5ba054ec908bfa661205e068c3c8f275a32d246c75、install logs13789251418 ZIP3215896bytes/SHA2a52d351cc9f74cbc4be2e94a761a591748f3dceedbe6981c6a72f6f2b0f4cec均官方/下载相符。原件/安全解压在evidence/units-profile/public-stdio-42865595677，terminal/meta/独立image-failure-audit.json同名docs目录。

Win3.9/3.14/轮包/route已success；本次首错wrapper capture_early native-host完整image准入，5.813s，不是helper或600/1800。公共CLI1开始但完整0/139，SDK/MCP0/139，3cold probes0。raw status/list完成，open native operation ended但回执未持久；82trace/worker6536、0setter/0nativeAPIerror。内部139成功259.579s/owned退出确认，独立核278文件hash和92part几何（67nonexact保原窄界限），不补公共。公共stop ActiveDocument、native/helper退出均未确认，原件不翻绿。上次stdio在Windows前置及真实CLI list CRLF/B64已通过，仍不是417通过。

MSI INSTALLDIR/注册路径及安装COM验证与原expected常量一致；实际Query返回image/len/size/creation未保存，不能把差异先判成安装路径错误/截断/别名。统筹批准只补diagnostic：before validation持久化observed PID/fullimage/creation、expected/repr、Query输入/输出字符数、类型实际宽度/NUL/有界raw wchar B64。callback只JSON deep copy，不拿handle且不能篡改判据；稳定identity仍四字段，校验/原constant/同handle重核/终止AST不变。观测fsync失败先停，首错不被close/观测次错覆盖。Windows-only只读当前Python API探针对照独立module image，记录venv入口/base事实而不误判；不CAD/别PID/VM。

最终97关联25.036s（1skip）、完整1973项78.009s（27skip）、SDK生成/strict6/consumer8、Python3.9 AST3/diff通过，源码与日志SHA见identity-observer-validation.json。Windows真实API probe尚待push轻量检查，本地mock不是Windows证明。具体说明docs/verification/units-image-admission-42865595677.md。按统筹要求先发精确diff/head并可中文push轻量Windows，暂不再派native；路径修法和可信receipt绑定待真实observed数据。预算/域/geometry/417与cold probe策略、main/其他路线均不变。


identity观测修复精确业务head`e2f787666c504e72c289825a7753f27f6bdbb049`已交root亲审三文件diff。root本人核before-validation fsync/deepcopy无handle、stable4字段及validate_identity/terminate/exited对085ae AST相同，认可仅push轻量Windows而非native。中文push已完成，唯一该push [42902927609](https://github.com/YJBeetle/SWCLI/actions/runs/42902927609) event/head/ref核过；一次初始listing快照in_progress保存在docs/evidence/units-profile/identity-observer-push-42902927609/。没有workflow_dispatch、private/native/VM操作；native job在该push ref按原workflow不启用。正常快照后停止等待，不busy追；Windows自身API原观测结果尚待后续terminal原件，不把本机skip当通过。原42865595677原失败/public0/3probe0/未确认退出及actual image未知全部保留。此后提交只docs，业务源固定e2f7876。


## root批准同步身份预检：实现与本地验证完成，未派native

42902927609 / e2f两Windows原job日志和summaryZIP原件已核：各1973项通过，3.9 160.412s/skip11，3.14 202.445s/skip4；自身Query/module image完整相同，实际ABI8/4/4/2、返回55/56、NUL与rawUTF16LE一致。官方summary ZIP digest同下载，固定原日志SHA并保run/head/job源绑定；独立stdlib audit重复相等、错head拒绝。纯docs证据独立提交push3a38693，不替代未知SW actual image。

root亲审提案/复跑审计后批准最小wrapper同步预检。本次只改run-unit-profile-public.py和test_unit_profile_public_runner.py：daemon ready后/任何public worker前一次真实CLI daemon status，raw bytes/returncode/parsedJSON先fsync，原健康/恢复/owned/hidden/unshared/priorPID后调用原e2f capture及observe/原谓词。任一失败不启动public；成功持续持同handle，public报告每次出现仍核owner/PID，终局要求报告存在，不能提前return跳过。预检与capture耗时计入原1800，CLI参数请求600，实际health RPC固定10秒/connect1秒（daemon.main.run不转发该CLI参数）；process timeout取min(600,原剩余)，无重置；原417+3cold/域/几何/src/workflow/helper均不改。至多一次normal stop，无verified handle不终止/重开，第一错误和退出边界保留。

runner41/0.125s（1skip），关联85/26.421s（1skip），完整1988/79.958s（27skip），SDK生成/strict6/consumer8通过；2文件Python3.9AST/diff通过；原identity helper逐字e2f，validate/terminate/exited/constant对085ae及e2f AST一致，ownership predicate表达式也一致。最终源码和原日志SHA在docs/evidence/units-profile/identity-observer-push-42902927609/synchronous-preflight-validation.json。说明docs/verification/units-synchronous-identity-preflight-review.md。

本实现仅本地中文提交交root精确head/diff亲审，未push实现/未新dispatch/native/VM；先前docs push不查新run。Windows同步预检与实际SW映像尚未运行，不把macOS mock和旧Python自身probe算作SW通过。旧42865595677失败/public0/3probe0/未确认退出/actual path未知保持，新的native路由必须root另行明确授权。原件目录evidence/units-profile/identity-observer-push-42902927609仍本地untracked，禁止整目录stage。


## c600超时报告语义补正，待root复核，不派CI

root亲跑runner41/0.155s（1skip）并核源/日志hash后指出：当前daemon status不带--details，实际走swcli.daemon.main.run固定call_daemon(timeout_seconds=10.0,connect_timeout_seconds=1.0)，不转发父CLI args.request_timeout；旧request_timeout_seconds=600字段/“CLI请求仍600”表述不准确。仅将报告拆为requested_cli_timeout_seconds=600、effective_health_rpc_timeout_seconds=10、effective_health_connect_timeout_seconds=1并给源码契约，process_timeout_seconds=min600/原剩余保持，产品CLI不改。历史validation字段同步明确实际语义，保留其c600源码/日志hash。

新增测试从wrapper实际command进入真实swcli.cli.main->daemon.main.run，仅mock最终call_daemon，确认一次daemon.health实际10/1并比对报告字段/原JSON；runner+CLI78项/1.668s（1skip）通过。2文件Python3.9AST/diff通过；wrapper完整AST仅report metadata dict差异，src/workflow/identity/transport helper无diff，实际预算/guard/417+3cold均不变。新源码/原日志/contract源SHA在docs/evidence/units-profile/identity-observer-push-42902927609/timeout-semantics-correction-validation.json。先前c600 full1988及SDK证据独立保留，本次不为纯报告语义补正重复整套。

按root要求补正后本地中文提交、交精确head/SHA复核；未push实现/新dispatch/native/VM，actualSW path仍未知。


## root复核95a后唯一新公共运行42928824277：初始快照后停止

root亲审95a2edc vs c600 metadata/真实CLI契约测试，三SHA匹配，亲跑runner42项0.385s（1Windows skip）通过，结合c600 full1988/SDK后明确批准精确95a2edccd26dfa274e0f66468248838d71cf7e53提交链push及一次units-write-public。已push该精确head，派前remote=HEAD/受跟踪干净，全部13次同ref manual记录核同head0次、未完成0；原件untracked未stage。workflow SHA13c45095bacb226a84a9d4a610b5a74e564a80d578e56b9c6b93b5a0f9d028c7不变，单位ref独立并发组、cancel=false且无workflow级并发；不cancel其他run。

只派一次 https://github.com/YJBeetle/SWCLI/actions/runs/42928824277 ，官方event=workflow_dispatch/head=95a/ref=codex/docprops-units-expanded/attempt1已核。三个units=true/native_full=false不只取请求回执：一次初始run/jobs snapshot里route job130222100992已success，单次读原log核实际ROUTE_* env及Validated native route: units-write-public。初始run in_progress，Win3.9/3.14 in_progress，wheel/route success，tag-policy skipped；尚无新Windows完成或public native通过证明。正常初始快照后停止所有run查询，不poll、不重复dispatch。

metadata/preflight/receipt/route核对在docs/evidence/units-profile/public-sync-preflight-42928824277，原路由日志和派前查询原件在同名evidence目录。此后只本地docs快照提交，业务源仍95a，remote继续95a，不push新业务。无VM/main/release。若本run再次identity拒绝，原Query/expected必须在public Popen前已fsync，首错/未确认退出不翻绿，不重试API或再派。即使run成功仍须root审本run原ZIP/digest、417+3cold、同host/worker、保存RO/hash/严格geometry/CAS及真实helper/native退出后才能决定merge，不借旧内部139/portable补公共缺口。


## 42928824277终态首错与获批严格路径候选，本地提交待审

官方本run terminal run/jobs/artifacts各一次，native job130224083602失败public CLI步骤；Win3.9/3.14/轮包/route通过。native13816502372 ZIP10937528/SHA90fb3eb856a671a1cc5c98f56e3fc219d76208203d35a7934e14428cdaa4681b、install13816611572 ZIP3211059/SHA76e85630997b8241e150d55ad7691803b800bc570fdac9e088b52c630e30643a与官方digest相同；原native log本地SHA8143e35f82298445213f362c7815632e16719e0d28935f4ec48d5dc1546f8bd3。原件/安全解压evidence/units-profile/public-sync-preflight-42928824277，独立审计/docs同名目录，root也已重放通过。

本次actual Query终于持久化：C:\PROGRA~1\SOLIDW~1\SLDWORKS.exe，完整33字符/B64/UTF16/NUL，ABI8/4/4/2；expected仍完整长路径。4.891秒在public Popen前被原exact路径谓词拒绝；PID9980/实际creation在窗内，但creation谓词未执行。无public worker/CLI/SDK/MCP/cold，公共trace/setter0。正常stop一次exit0，原receipt stopping=true，无ActiveDocument/未知强杀；daemon.wait返回0从postwait原错误推断；native未有verified handle/wait/pids_after，退出仍不确认，helper未启动，不翻绿。内部139/258.437s/owned退出成功，278文件hash/92几何（67nonexact）独立核过，不补公共。旧ZIP没有short/long同文件证明。

root批准仅准备路径身份候选、local tests/提交供亲审，不dispatch。unit_owned_native新增一次GetLongPathNameW有界32768、DWORD/wchar/返回长度/NUL/raw buffer，失败关闭不扩容重试。实际OS展开完整路径必须满足原expected完整谓词，另os.stat raw/expected + os.path.samefile及非零inode/device证据均同一；不字符串替换/basename/白名单/realpath兜底。raw/展开/文件标识/比较/异常先通过原deepcopy observer fsync，返回仍原raw4字段，同held handle终止严格重核raw不变；admission_identity副本明确标注展开representation。原process_identity AST与95a相同，validate/terminate/exited/expected与95a/085ae相同；输入副本的representation变化如实披露。wrapper/src/workflow/WriteGate/600-1800/417+3cold/域几何无diff。

最终关联105/24.938s（3skip）、full2008/74.141s（29skip）、SDK生成strict6/consumer8、Python3.9 AST3/diff通过。新增两Windows-only真实短长同文件/不同缺失文件探针本机都skip；macOS mock/wchar4不冒充Windows证明。精确源/原日志SHA见docs/evidence/units-profile/public-sync-preflight-42928824277/short-path-candidate-validation.json，审阅说明docs/verification/units-short-image-42928824277-review.md。原audit重复一致/错head拒绝；未新CI/VM/main/release、不push候选，等待root精确head亲审。


## root亲审严格路径候选后唯一42935636514，初始快照即停

root完整亲审459b0cf helper/19tests/runner4行适配，核产品src/workflow/wrapper对95a无diff，亲跑新路径+runner61项0.407s（3skip）通过，明确准入为OS-expanded整条expected+samefile/stat匹配可用，raw4字段/PID/creation/同handle终止不变，不宣称Windows实际证明已过。批准显式push精确459b0cf88892fe1af013156994568d6e52e6df2e后仅一次原公共native。派前核remote95a、只含已授权74a/ccf/459三提交；受跟踪干净、原件untracked未stage。push后remote=exact459；全部14个同ref manual记录核同head0派、未完0，独立单位ref并发组/无workflow并发/cancel=false与原workflowSHA均不变。

只派一次 https://github.com/YJBeetle/SWCLI/actions/runs/42935636514 ，官方event workflow_dispatch/head459/ref codex/docprops-units-expanded/attempt1已核；actual route job130244936823已success，单次读取原log核ROUTE_*三units=true/native_full=false及Validated native route: units-write-public。一次初始run/jobs snapshot：run in_progress，Win3.9 job130244936740及3.14 job130244936949 in_progress，wheel130244936395 success、route success、tag-policy skipped。Windows真实路径正负probe尚未在该快照完成，不算通过；既有workflow须portable成功才可native，前置失败不重试native。

meta/preflight/receipt/initial/route审计在docs/evidence/units-profile/public-short-path-42935636514，原route/派前查询原件在同名evidence。初始快照后停止全部CI查询、不poll/不重派，不动VM/main/release。此后仅本地docs快照提交，remote与业务源保持459；旧42928824277 failure/公共0/cold0/原生退出未确认/短长同文件未证明均保留。新run首失败待原件保存后再审，不自行重试API或放宽准入；成功也须root原件审417+3cold/同host-worker/保存RO/hash/strict geometry/CAS及真实退出后才能决定merge。


## 42935636514成功原件独立审计完成，纯证据本地提交

本run official terminal run/jobs/artifacts各一次，native13820837309 ZIP47688318/SHA c34b58cd4796d7778eae31b01d69bacc1108d9c9c12e22908b6d054c37fb7117核同。native/Windows3.9与3.14原job日志和两portable summary原ZIP均保存；installer ZIP确无（if:failure上传，本success步骤skip），不借旧run。通用summary public-evidence仍SKIP因RECEIPTS不识别public-unit-profile.json，原样保留并说明，实际units/public/cleanup stages PASS。

独立stdlib audit绑定本source459：CLI/SDK/MCP139各(46/46/47)，每route137精确域和全afterhash匹配静态表，3真实fresh probes；417changed各一次setter、417noop零写、2010negative零写。全部九字段/raw5/link19/CAS/stamp/lease/session/readonly/path/原bytes及1251实际open-save请求、417source引用+417保存hash核过；276公共part geometry(190nonexact)与内部92(59nonexact)保原严格body/V/S和仅逐轴1e-12mm质心。46764journal行/14031commands一致，1710960native frames完整配对/14029typed requests逐ID绑定，单worker6088、原生APIerror0、834error仅预期lease/stamp。内部139/248.422s/281native files独立，不补公共。

public总1355.766s/原600-1800边界，SW PID9208 raw短名33真实展开expected40、samefile和device/inode证明通过，raw identity保留；normal stop0、同retained native wait/readonly helper8500 wait均确认、before/after[]、cleanup[]、无force。两Windows真实短长与不同缺失probe实际ok：各2008项，3.9 252.285s/skip11、3.14 178.279s/skip4，不将macOS mock算Windows。

重放docs/verification/audit-units-public-success-42935636514.py，说明docs/verification/units-public-success-42935636514-review.md，meta/结果/校验SHA在docs/evidence/units-profile/public-short-path-42935636514/{public-success-audit,independent-audit-validation}.json。原件安全展开在同名evidence/original，未stage。错head/digest/伪samefileID/原buffer/缺九字段都拒绝；Python3.9AST/import/diff通过，无产品/gate/COM import。root亦独立基础与trace审计通过。

统筹后续已接管并完成main整合，要求无需继续merge分析或复跑既有测试；本路只完成纯证据本地提交，不碰其integration/main，不push/CI/VM/发布。本459成功仅对应原始有界单位验收，不宣称完整原生产品矩阵或整合后main原生验证；旧failures及当时未确认退出不翻绿。

## STEP route historical handoff (bounded evidence, not whole-series release)
# STEP export options handoff

## Scope / coordination (2026-11-07)
- Worktree: swcli-step-export-options/SWCLI; branch codex/swcli-step-export-options.
- Baseline HEAD: 3bda2c00489dde6a3d1e4521c548f751b1d1c197; initially clean; no .codegraph directory.
- Own only STEP/STP options. Proposed additive document.export parameters: step_protocol (`ap203`, `ap214`) and step_geometry (`solid-surface`, `wireframe`, `wireframe-sketches`). STL/GLB untouched.
- Shared files: operation_schemas.py, cli.py, daemon/operations.py, daemon/server.py, hosts/windows_documents.py, generated SDK, CI workflow. Integrator must reconcile additive edits from other export branches.
- STEP preferences are application-global: require trusted daemon-owned invisible host scope, serialized worker, native type-library enum resolution, complete preference snapshot/CAS before changes, checked setters/readbacks and finally restore verification. Shared/visible hosts fail closed.
- Uncalibrated public writes remain disabled. A targeted manual CI-only calibration scope will exercise the identical worker/adapter; public release eligibility remains separate from this evidence.
- Official API supports swStepAP values 203/214 and swStepExportPreference with swAcisOutputGeometryPreference_e. No AP242 assumption.

## Tests / commit / native evidence
- Initial inspection only; implementation, portable tests, commit/push and single branch-head workflow_dispatch pending.
- No local VM use, main merge, version change, release, DockerSW pointer or MacSW changes.

## Implementation / portable verification phase
- Implemented additive `step_protocol` + `step_geometry` request/CLI/generated SDK fields; MCP uses the existing execute surface. Both options, STEP/STP extension, live lease and expected stamp are required together.
- New `windows_step_export.py` resolves the installed official enum names; supports AP203/AP214 and solid-surface/wireframe/wireframe-sketches only. Restricts to clean writable non-editing parts in an owned hidden worker scope. Revision allowlist remains empty: public writes fail closed pending reviewed native/public acceptance.
- Complete two-preference snapshot/CAS, setter/readback, post-export desired readback, finally original restore/readback, original-error preservation plus partial mutation/restore evidence; failed restoration quarantines the worker. STEP schema/termination/entity-family verification precedes atomic output publication.
- Native script plans six combinations in one owned host. Checks default public gate rejection separately, explicit background document identity, real STEP schema and hashes, analytic box/wire geometry after LoadFile4, native save and readonly reopen. No restart/retry; 600-second native and 1800-second group watchdogs.
- CI input `native_step_targeted` defaults false, dedicated branch/manual event only. STEP uses `swcli-step-export-{github.ref}` concurrency, cancel-in-progress=false; full/release keep `swcli-hosted-windows-solidworks`. No other runs canceled or dispatched.
- Targeted portable tests: 17 passed. SDK strict typing/generation: passed, including 10 negative consumer fixtures. YAML parsing and CI event/branch truth table passed. Existing mesh export tests: 8 passed.
- Initial full suite found only a static workflow guard assertion; adjusted expression to retain its default-full clause and reran targeted gate tests successfully. Final full portable suite: 1836 tests passed, 26 skipped (55.064 seconds).
- Persistent evidence: `step-evidence/` (ignored local logs), not tmp. Implementation commit/push and single workflow_dispatch pending; portable and wiring checks passed.

## Remote authorization review
- Automatic approval review rejected a combined local-commit/remote-push command before execution. Stated reason: remote code egress to YJBeetle/SWCLI was not explicitly authorized by a trusted user message; delegated authorization alone was not accepted.
- Local commit is being completed separately. Remote push and workflow_dispatch have NOT happened; no workaround or alternate network write attempted.

## Commit / dispatched native calibration
- Implementation commit: `ff7f66bab0403a5b4e3dd7f6f0155ad56595eeda` (Chinese feature commit), pushed to origin/codex/swcli-step-export-options after the user explicitly approved this exact destination/head/payload and one dispatch.
- Single internal calibration run: https://github.com/YJBeetle/SWCLI/actions/runs/42262507658
- Event/head: workflow_dispatch / ff7f66bab0403a5b4e3dd7f6f0155ad56595eeda; inputs native_step_targeted=true, native_full=false; other workflow defaults.
- Initial state: portable/package jobs queued. Native calibration and output/save-reopen evidence remain unproven. Raw dispatch metadata: step-evidence/dispatch.json.
- Coordinator follow-up accepted: internal evidence alone is insufficient. After success, independently verify original artifact/head/digest/trace/save-reopen, then open only the exact proven range and add public CLI/daemon native acceptance plus SDK/MCP contract checks. Not merge-ready; no main merge/release.

## Public acceptance preparation (uncommitted; no second dispatch)
- Coordinator requires eventual merge-ready public proof. Prepared `verify-step-export-public.py`: one daemon-owned hidden host; public CLI exports six combinations, plus SDK and MCP bridge exports; CAS/foreign lease/illegal protocol/readonly rejection; native source close/read-only reopen/analytic measure; SHA256 and raw CLI/daemon traces; explicit host-process exit.
- Prepared separate `--export-report` output-readback mode in the native script. It refuses a mismatched public output digest, then imports the actual public files, verifies analytic geometry, native save/read-only reopen, and original STEP/native file hashes. These are two explicit groups (public writer, independent output observer), each owns one host and has no failure retry/replacement.
- Added default-off, dedicated-branch/manual-only `native_step_public_targeted` CI profile with a distinct public-profile+ref concurrency group. No public profile has run. Public revision allowlist is STILL empty pending original internal artifacts.
- Preparation verification: 19 STEP/offline harness tests pass; default-full guard tests and YAML parse pass. These additional uncommitted files were not part of ff7f66b or run 42262507658.
- Run 42262507658: Build wheel and Windows Python 3.9/3.14 jobs passed; native STEP job is queued for GitHub quota. No cancellation or duplicate dispatch.

## First native result: failed, original evidence retained
- Run 42262507658 / head ff7f66bab0403a5b4e3dd7f6f0155ad56595eeda completed failure at the first AP203/solid-surface case; no second case started, no retry/restart. Installer and cleanup completed. Not merge-ready and public allowlist remains empty.
- Original evidence ZIP: `step-evidence/internal-original-42262507658.zip`, artifact ID 13527496084. SHA256 `fe4470212b224bb965afd9ae77e8b5d96918dbc637526cd5df4cbc316ae877c6` exactly matches GitHub digest.
- Official installed SwConst: swStepAP=75, swStepExportPreference=142; solid/surface=0, wireframe=1, wireframe+sketches=2. Owned hidden host revision 33.5.0.
- AP203 output header CONFIG_CONTROL_DESIGN, size 16070, STEP SHA256 `4024956fff86d9aa261d6d17a288d323506a78ba69317abf8140421dc3631997`. Export, source readonly reopen, STEP import, imported native save and readonly reopen all returned success. Pref snapshot 203/0 restored 203/0; this first case did not exercise changing either preference.
- First failure is raw equality of the complete measurement dictionaries: volume/area identical; centroid Y changed from 7.72035238382826e-17 to -1.9852334701272667e-16 mm. Original report/trace/logs and native/STEP files extracted; independent audit `step-evidence/internal-audit.json`.
- Because the user explicitly prohibits relaxing assertions, prepared but DID NOT APPLY `step-evidence/proposed-numeric-readback.patch`. Proposal keeps exact body/segment topology, existing analytic volume/area/total-length tolerances (rel 1e-7, abs 1e-5), and adds analytic/pairwise centroid and per-segment 1e-9 mm bounds instead of bitwise float dictionary equality. Needs explicit user decision before replacing the assertion or rerunning. No public whitelist promotion from this failed run.


## Approved diagnostic correction / second internal head preparation
- User explicitly approved `proposed-numeric-readback.patch` and authorized pushing the correction, public acceptance scripts/isolated CI profile, diagnostics, documentation/tests to YJBeetle/SWCLI/codex/swcli-step-export-options; each repaired head gets only one necessary internal/public dispatch. Failed original evidence must be retained; only substantive fixes justify another run.
- Applied the approved physical-comparison correction: exact topology/method/schema; existing analytic volume/area/total-length thresholds unchanged; analytic and pairwise centroid/per-segment bounds 1e-9 mm. Added portable refusal tests for actual centroid, volume, area, topology and wire-length changes/nonfinite values.
- Additional public-phase preparation includes explicit native SaveAs3 attempted/possible-mutation flags and trace boundaries, fail-closed unknown original preferences, native input type-library SHA256/head identity. Public revision allowlist remains empty.
- Preparing a new commit and a single internal dispatch on that new head after portable/wiring checks. No public acceptance or whitelist promotion yet.
- Approved repair verification: full portable suite 1841 tests passed, 26 skipped (55.311 seconds); STEP/offline harness tests 22 passed; SDK generator/strict typing and 10 negative consumer fixtures passed; Python compilation/YAML and full/default CI guard tests passed. Logs in step-evidence/portable-second-head.log and sdk-types-second-head.log.


## Repaired internal run
- Repair commit: `6d477667e74aa2cf734fceff86c14186d82ef5cb`, pushed to the same authorized branch.
- First dispatch API call returned HTTP 500 and created no run; two read-only dispatch-list checks one minute apart confirmed absence. A resubmission then established exactly one actual run for this head.
- Internal run: https://github.com/YJBeetle/SWCLI/actions/runs/42267422666
- Verified workflow_dispatch head: 6d477667e74aa2cf734fceff86c14186d82ef5cb. Parameters native_step_targeted=true, native_step_public_targeted=false, native_full=false; other workflow defaults. Independent internal-profile+ref concurrency, no cancellations.
- This is a new repaired head; the failed ff7f66b run/ZIP remain unchanged. Public allowlist is empty; public acceptance remains pending successful full internal evidence/audit.

- While the repaired internal run executes, prepared a native-runtime identity guard for the eventual public head. Matching SOLIDWORKS revision alone will not enable Wine/non-Windows; unreadable runtime identity fails closed. Its portable negative test passes; no whitelist entry has been added.
- Pending public-head guards (not part of 6d47766): require actual native Windows identity in addition to the calibrated revision, and reject an unsaved source before preference setters/native SaveAs. Portable STEP checks now 24 passed; existing mesh export checks 8 passed. Public whitelist is still empty.
- Independent first-run raw STEP audit confirmed recorded hash/schema plus exact 1 solid/1 closed shell/6 faces/12 edges/8 vertices. Native source/import file hashes/signatures recorded in internal-audit.json. This remains failed/partial evidence and does not promote the first run.

## Second internal result / substantive observer-profile repair
- Run 42267422666 / head 6d477667e74aa2cf734fceff86c14186d82ef5cb failed at its first AP203 wireframe LoadFile4 readback (error code 1). AP203 solid-surface completed full native import/save/read-only reopen successfully. Two cases started, one completed, no later cases/retries. Cleanup/owned process exit succeeded.
- Original ZIP `step-evidence/internal-original-42267422666.zip`, artifact 13528703173; SHA256 `3203496cde278d8f1ac83d9b3b122052b05f492e38655cad5a1f2ed2b43d681e` matches GitHub digest. Report/trace/files extracted; audit `step-evidence/second-audit.json`.
- Independent wire STEP proof: exact AP203 header/hash, 12 degree-one B-spline line edges, 8 vertices degree 3, millimeter units, 4 each of 10/30/40 mm, total 320 mm. Preference 142 set 0->1 and restored 1->0 with complete snapshot checks. Native import error remains unaccepted; no public promotion.
- The observer previously relied on unrecorded import defaults. Official API references identify `swMultiCAD_Enable3DInterconnect`, `swImportNeutral_SolidandSurface`, `swImportNeutral_FreeCurvesAndPoints`. Implemented test-only observer profile (False/True/True), exact installed enum-name/owner resolution, complete bool snapshot/CAS/readback and finally restore, preserving first failure if restore also fails. This is a substantive test-environment repair, not relaxed error/geometric assertions or a native retry.
- All import error-code-zero, geometry, topology, approved precision, source identity and save/reopen requirements remain. Public allowlist stays empty. Pending native-Windows/saved-source guards are now included with the upcoming repaired internal head.
- STEP/offline checks: 25 pass. Full portable, SDK/wiring verification and new repair commit/one internal dispatch are next. No public run yet.

- Before dispatch, official setter signature review confirmed ISldWorks.SetUserPreferenceToggle is void (unlike the integer setter). Observer accepts the expected None return and requires complete readback after every setter/restoration. Portable stand-ins use this actual contract; no guessed boolean toggle return remains.
- Third-head verification complete: 1845 portable tests passed, 26 skipped (50.946 seconds); 26 STEP/offline checks passed; SDK strict typing/generation plus 10 negative consumer fixtures passed; Python compilation and diff checks passed. Logs: step-evidence/portable-third-head.log and sdk-types-third-head.log.


## Third internal head/run
- Repair commit `2c7108fa5c6c22ebfc9a6c98bdb0a9f67acac58f`, pushed to the authorized codex branch.
- Single workflow_dispatch: https://github.com/YJBeetle/SWCLI/actions/runs/42272463402 ; verified head 2c7108fa5c6c22ebfc9a6c98bdb0a9f67acac58f.
- Parameters: native_step_targeted=true, native_step_public_targeted=false, native_full=false; other defaults. Internal-profile+ref concurrency remains separate, cancel-in-progress=false. No other runs canceled.
- Purpose: verify the substantive observer import-profile repair with all original error-code/geometry/restore/save-reopen gates. Public allowlist is still empty; no public acceptance or merge-ready claim.

## Coordinator authorization/status refresh
- Coordinator forwarded continued user authorization for own-branch implementation/Chinese commits/push to YJBeetle/SWCLI and targeted native/public gates; precise verified capabilities may be enabled on the development branch for public acceptance. Main integration remains coordinator-owned.
- No outstanding approval request on this lane. Earlier remote approval issue was resolved by explicit user approval; the diagnostic precision correction was also explicitly approved. No repeated approval action needed.
- Active work: unique third internal run 42272463402 at 2c7108fa5c6c22ebfc9a6c98bdb0a9f67acac58f, after substantive observer-profile repair. No unapproved assertion changes, VM use, DockerSW/MacSW changes or credential output. Next: audit complete original native evidence before any exact-scope public whitelist/public gate.

## Coordinator-requested CI mode audit (current run unchanged)
- Found actual exclusivity gap: workflow_dispatch on the STEP branch with native_full=true plus exactly one STEP flag currently executes that STEP mode instead of rejecting the mixed full/targeted request. Current third run uses full=false/internal=true/public=false and its CAD step is selected, so it is not an empty-green instance.
- Preparing minimal selector repair: require !native_full for internal/public modes; default full CAD selectors explicitly select push-version-tags or exclusive manual full; STEP name/concurrency/summary selection must require workflow_dispatch so tag mode stays full/default group. Add event/ref/tag-policy/all-flag matrix proving every eligible job has exactly one CAD mode (public observer paired with public writer).
- Do not rerun/cancel 42272463402 because of this wiring repair. Its actual 2c7108f source/head and original results remain authoritative for its valid parameters. Repair will be carried into the next substantive/public head.
- CI selector repair is implemented locally and passes 3456 combinations across event/ref/all three flags/tag-policy/repository ownership/portable+package outcomes. Every eligible job selects exactly one full/internal/public CAD mode; public observer matches public writer; display name/evidence scope/concurrency match the selected mode. Exclusive full preserves existing tag/full group. Original default-full guard tests and YAML parse pass.
- This local wiring repair does not change/cancel/re-dispatch active run 42272463402. It will be included in the next substantive/public head; not a reason to duplicate the current valid-parameter run.

## Third native result / independent fixture-oracle correction
- 42272463402 at 2c7108fa5c6c22ebfc9a6c98bdb0a9f67acac58f completed failure after AP203 solid-surface AND wireframe each fully passed import/native save/read-only reopen/hash checks. First failure: wireframe-sketches analytic total; three cases started, two completed, no retries/restart; cleanup/owned exit succeeded.
- Original ZIP step-evidence/internal-original-42272463402.zip, artifact 13533248737; SHA256 `43aebd4a830e05aa68f938122365098c59bfbb961e0f6414b2768e5ba9b950d1` matches GitHub digest. Independent audit third-audit.json preserves failure.
- Observer profile repair is native-verified: SwConst IDs SolidandSurface=686, FreeCurvesAndPoints=687, 3DInterconnect=691. All three cases observed original True/True/False, requested False/True/True, restored exact original. Every STEP import now error=0. Wireframe native save/reopen retained 12 segments totaling ~320 mm.
- New failure is an incorrect fixture oracle, not an error-code allowance: CreateCenterRectangle fixture includes construction diagonals. Original STEP independently contains twelve box B-spline edges totaling 320 mm plus six trimmed sketch lines [30,30,40,40,50,50] totaling 240 mm. Native readback is 18 segments / 560 mm. The old oracle omitted the two diagonals and expected 460.
- Prepared substantive correction: independent pre-export native/public sketch inspection must prove one source sketch, four outline lines and two construction diagonals with expected lengths. Exported/imported wire profile now requires the exact 12 or 18 segment vector derived analytically from the source fixture. Total/centroid/per-segment precision thresholds are unchanged; exact count/vector checks are stricter. Old 16-segment/460-mm output is explicitly rejected. No production export behavior is changed or enabled by this oracle correction.
- Includes coordinator-requested full/internal/public CI selector repair and 3456-case no-empty-CAD-mode matrix. Pending new repaired internal commit after portable checks; existing original run/head retained. Public allowlist is still empty.
- Fourth-head portable verification: 1846 tests passed, 26 skipped (62.526 seconds); 27 STEP/offline checks passed, including strict source construction-line oracle and 3456 CI selector combinations. Python compilation/diff checks passed. SDK source/schema/model blobs are unchanged from the preceding strictly typed head; the new CI still gates on its fresh Windows SDK/type checks.


## Fourth internal repair head/run
- Commit `193ab6c64fac32c42783704f8e66a1804c751cc4`, pushed to the same authorized codex branch.
- Unique workflow_dispatch https://github.com/YJBeetle/SWCLI/actions/runs/42278790303 ; verified head 193ab6c64fac32c42783704f8e66a1804c751cc4. Inputs internal=true/public=false/native_full=false (native_step_targeted=true, native_step_public_targeted=false); other defaults.
- Includes independent source sketch precondition/exact analytic wire vectors and the coordinator-requested mutually exclusive/no-empty-CAD-mode workflow repair. New selector matrix selects exactly this internal CAD mode for the actual inputs. No prior run is canceled or repeated unchanged.
- Public allowlist remains empty; native/internal full scope and public validation remain pending this actual head's evidence.

- Pending public-head check tightened: the public source readonly reopen must explicitly return api_errors=api_warnings=0, requested readonly=true and modified=false, matching the existing internal zero-status gate. A returned partial document remains tracked for cleanup if validation fails. No public/native run is duplicated for this assertion addition.


## Bounded handoff after coordinator closeout instruction
- Latest user/coordinator scope: finish only the current batch, no new feature/plan or endless iteration; coordinator owns review and integration. No rebase/rerun for main 0e72beb. Stop continuous sleep/polling and unchanged updates; no single-CI automation.
- Final bounded snapshot: run https://github.com/YJBeetle/SWCLI/actions/runs/42278790303 at exact pushed head `193ab6c64fac32c42783704f8e66a1804c751cc4`, workflow_dispatch internal=true/public=false/native_full=false. Windows Python 3.9, Python 3.14 and Build wheel all succeeded. Native job 128103608940 remains in progress at `Free disposable runner disk for installation` (started 2026-11-06T19:24:18Z); no fourth-run CAD result/artifact/digest yet. Snapshot: step-evidence/fourth-handoff-snapshot.json.
- Local gh watch for this run was stopped; the GitHub CI run was NOT canceled. No duplicate dispatch, new automation, native retry/rollback/restart, local VM use or other lane edits.
- NOT merge-ready: public revision allowlist is empty; no successful complete six-case internal run and no public CLI/daemon+SDK/MCP native acceptance yet. No option-write subset is promoted from prior failed runs. Fourth original ZIP must be downloaded/digest-verified and independently audited when complete before exact-scope promotion is considered. Earlier three original failed ZIPs/digests/audits remain retained above.
- Local uncommitted changes: this WORK_HANDOFF update and the prepared stricter source readonly reopen assertion in scripts/ci/verify-step-export-public.py (requires api_errors=api_warnings=0, read_only=true, modified=false and retains cleanup ownership before checking). This assertion has not been pushed or run natively. Do not confuse it with tested head 193ab6c.
- Later bounded continuation: collect completed fourth result and original ZIP first; report exact accepted scope or remaining failure. If all six internal combinations pass, any exact revision promotion/public proof remains a separate currently unfinished acceptance phase within the existing scope. Main merge/release remains coordinator-owned.


## Fourth completed original evidence / exact public-gate candidate
- Coordinator requested bounded continuation after live success confirmation, necessary public gate within existing scope, no continuous CI watcher. Final review/integration remains coordinator-owned; no agent review or rebase.
- Run 42278790303 completed success at exact head `193ab6c64fac32c42783704f8e66a1804c751cc4`. Original artifact ID 13537145378 saved as `step-evidence/internal-original-42278790303.zip`; SHA256 `cf257c569e2d62ebb727c4a49041ab2a1b9c536b6f6d17e8b7208d5d3dc1b6cf` matches GitHub digest. Extracted unmodified tree: `step-evidence/fourth-original-42278790303/swcli-native-smoke/step-export-calibration/`.
- First-layer independent audit: `step-evidence/fourth-audit.json`; reproducible checks `step-evidence/audit-fourth-original.py`. All 6 cases completed: AP203/AP214 x solid-surface/wireframe/wireframe-sketches. Actual STEP headers/topology and SHA256, source six-segment sketch including diagonals, native import error=0, imported save error=0, source/imported native readonly reopen errors=warnings=0, analytic mass/centroid or exact 12/18 vectors (320/560 mm), original native file hashes and both STEP+observer complete preference restoration passed. Trace: one owned invisible host (revision33.5.0), six exports, no error phase, process exit confirmed. Input SwConst SHA256 95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6; exact source head verified.
- Audit initially assumed an OLE signature for native files; modern native files do not use that signature. No native test/assertion was changed: audit uses actual native save/reopen status plus exact file hash instead. The independent report still has full_acceptance_eligible=false/public_acceptance=false by design.
- Prepared exact native-Windows revision33.5.0 allowlist for separate public gate only; all other runtime/revision/ownership/lease/CAS/document safeguards remain. Internal script skips extra public rejection probe on already-audited revisions to avoid a duplicate export; unknown revisions retain fail-closed probe. Public script includes previously prepared zero-error/warning readonly source reopen check. Not merge-ready until public writer plus independent actual-output readback evidence completes.

- Public-candidate portable checks passed: 1847 tests, 26 skipped (53.243 seconds); STEP-focused 28 passed, including exact revision acceptance and nearby revision rejection. No schema/SDK/generated model changes since the previously typed head; the public CI also retains fresh mandatory Windows portable/type/package gates. Log: step-evidence/portable-public-head.log.


## Public candidate pushed / one necessary public gate dispatched
- Exact pushed tip `f81d3d89f2cfe1f4c4a9f30c5c2571a4c0b07c3b` (Chinese commit: feat: 依据六组合原件开放精确 STEP 版本验收). Only own codex/swcli-step-export-options branch; no main/rebase/release/other lane changes.
- Single public workflow_dispatch: https://github.com/YJBeetle/SWCLI/actions/runs/42301050390 . Inputs native_step_public_targeted=true, native_step_targeted=false, native_full=false, other defaults. Dispatch returned success and this exact URL; subsequent bounded GET verified event/head. Record: step-evidence/public-dispatch.json; first snapshot: step-evidence/public-first-snapshot.json.
- This public run must complete both: public CLI/daemon writer (6 combinations plus SDK .STP and MCP exports, identity/restore/CAS/lease/readonly/source reopen/exit checks) and separate SHA256-pinned actual-output native reader (8 imports, geometry and native save/readonly reopen, import preference restoration and own host exit). Internal six-case success alone does not establish this gate.
- At bounded snapshot the run is in_progress. No continuous watch/sleep/polling started. Coordinator can collect a later single status snapshot and return the completed original artifact for audit. No duplicate dispatch or cancellation.
- Still NOT merge-ready; candidate enables only audited native Windows33.5.0 AP203/AP214 x three geometry modes. Current native proof is generated40x30x10 box including six-line rectangle source sketch, not arbitrary content/assemblies/Wine/other revisions/AP242. Candidate’s exact public path and all eight actual output roundtrips remain pending. Series release should await the planned series gates; do not relabel remaining acceptance as a post-release followup.


## First public result / original preserved / CLI harness repair
- Run https://github.com/YJBeetle/SWCLI/actions/runs/42301050390 at head f81d3d89f2cfe1f4c4a9f30c5c2571a4c0b07c3b completed failure in public writer; public readback skipped. Original artifact13544099154 saved as step-evidence/public-original-42301050390.zip; SHA256 e39955dc956167e2011037c6f2584b1146e69b87a9c8926d3468e2c535e5bdaf matches GitHub. Unmodified extracted files in step-evidence/public-original-42301050390/; first-layer audit step-evidence/public-first-audit.json.
- First export exited2 at argparse: harness/docs used nonexistent --expected-update-stamp; existing CLI flag is --if-update-stamp. stdout empty led harness to report JSONDecodeError, but original stderr preserves the true parse cause. Native trace contains ZERO document.export calls; outputs0; fixture/source sketch checks and daemon cleanup/owned process exit passed. No native export failure, retry or rollback occurred; this run does not count as public proof.
- Minimal substantive repair: use existing --if-update-stamp in public script/docs, move shared context builder into portable-testable function, test all six full CLI export command shapes with the actual parser retaining document/lease/CAS fields. Improve non-JSON failure message to include original returncode/stderr; raw original stdout/stderr still saved. No new CLI aliases, API fields or assertion relaxation. Existing production STEP transaction/allowlist unchanged.
- Public six-combination plus SDK/MCP and eight actual-output roundtrip gap remains a series release blocker. Prepare repaired head and only one necessary public gate after relevant checks; no continuous polling or review agents.

- Repair portable checks: all29 STEP tests passed, including3456-mode CI selection matrix, real-parser six-combination context regression, first-failure/cleanup, geometry precision and source oracle. Production library/SDK/schema/CI wiring unchanged from f81d3d8; fresh mandatory complete Windows portable/type/package checks remain before the repaired native gate.


## Repaired public head / single bounded dispatch
- Pushed exact tip ee7f0ea51cc23924cf84462f7688800dc6bca626 (fix: 修正 STEP 公开验收的 CAS 参数与首因诊断).
- Unique public workflow_dispatch https://github.com/YJBeetle/SWCLI/actions/runs/42303929271 ; inputs public=true/internal=false/native_full=false, other defaults. Return code0, exact head/event verified by one bounded GET. Record step-evidence/public-second-dispatch.json and public-second-first-snapshot.json; state at snapshot: in_progress.
- No watcher, sleep loop, duplicate dispatch, other-run cancellation, automation or native retry/restart. The previous failed public original remains preserved. Next continuation must first collect this completed run's original artifact/digest and independently assess actual public output/native save-reopen evidence.
- Still NOT merge-ready; planned STEP public six combinations, SDK/MCP receipts and eight-file independent native readback remain a series release blocker. No added feature/field, no tolerance changes and no claim that CLI-parse failure proved native export behavior.


## Successful public original retained / coordinator review repair
- Run42303929271 completed success at exact head ee7f0ea51cc23924cf84462f7688800dc6bca626, both public writer and independent reader steps success; Windows3.9/3.14+SDK types/build passed. Artifact13546292159 original ZIP step-evidence/public-original-42303929271.zip SHA2564623ccc98e3cd4f745d31680bbef53560a855e85f6aef982553be0678acfd717 matches GitHub. Extracted original tree step-evidence/public-original-42303929271/swcli-native-smoke/.
- Independent offline stdlib-only audit command: .venv/bin/python step-evidence/audit-public-original-42303929271.py ; output step-evidence/public-second-audit.json. Audit PASS: six CLI modes plus SDK AP214 solid .STP and MCP AP203 wireframe; exact raw files/digests/Part21 schema/entity topology and independent raw spline/trimmed-line lengths; all8 frontend request IDs correlate1:1 to native SaveAs3; one COM worker and one public hidden owned host; all8 separately-owned-host imports/native saves/readonly reopens with zero status/hash stability; full STEP/observer prefs restore; source native bytes unchanged; staleCAS/foreignlease/AP242/readonly refused; both cleanup/owned exit checks passed. Proof is targeted nativeWindows33.5.0 generated box, not a full-suite/release acceptance.
- Coordinator's own review found runtime fail-open: getattr(WinDLL(ntdll),wine_get_version,None) accepts an export-less object. Preserve the successful original but block merge until product repair gets its necessary new public gate. Reused exact already-merged main STL narrow probe (read owning main:windows_stl_options.py): kernel32 GetModuleHandleW(ntdll.dll), known NtClose, explicit missing Wine export with last_error127; every unknown/non127/exception fails closed before setters/SaveAs3. Regression matrix includes coordinator's export-less object, missing module/known export, Wine,0/5/126 errors and loader/lookup exceptions; no preference setter/ClearSelection/SaveAs3 occurs.
- Related review confirmed actual holes: step peer protection checked foreground identity but not peer state; worker context finalization/schema exceptions could erase an already-returned STEP receipt. Minimal scoped repair adds peer type/config/stamp/modified/title/path snapshot checks before setters/after successful export, plus public before/after foreground inspect. STEP-only worker catch retains trusted mutation+first native error/valid receipt fields, quarantines and never reuses previous result; invalid payload fallback strips schema-invalid fields without losing mutation. Existing non-STEP semantics unchanged. Main has font/tolerance-specific receipt preservation, so integrator must combine scoped helpers and keep both lanes.
- STEP-focused34 tests pass: known127 native acceptance; unknown-probe zero-setter/zero-SaveAs; peer stamp/config/modified/path drift rejects success while originals restore; command finalization retains first numeric native save error/mutation and quarantines; schema-invalid result retains trusted receipt. Full portable suite running because shared worker handling changed. No new native run until these checks complete; only one necessary repaired public gate planned.

- Peer verification also runs after preference restoration itself: a restore setter that changes foreground path is rejected before publication (new regression). With an earlier native error, the context-check warning is appended without replacing that first error. Focused35 tests passed; prior intermediate full suite1853/26 skipped passed; final full suite for this last check is running (step-evidence/portable-review-repair-final.log). No native dispatch yet.

- Final review-repair portable suite PASS:1854 tests/26 skipped (47.955 seconds), log step-evidence/portable-review-repair-final.log; STEP-focused35 passed. Runtime/peer/postflight code now ready for the one necessary new public native gate. Earlier ee7f0ea success remains retained evidence for the prior code, not substituted for this repaired head.


## Review-repair pushed / one necessary public gate
- Pushed exact tip b5b2d1d2894e7ea78b81642b2b1b0b9dd593b7fa (fix: 收紧 STEP 原生探针并保留后处理首错与前台状态). Same authorized branch, no rebase/main/other lane/version/release changes.
- Single public workflow_dispatch https://github.com/YJBeetle/SWCLI/actions/runs/42361918322 , public=true/internal=false/native_full=false, other defaults. Dispatch returned0 and one bounded GET verified exact head/event; snapshot in_progress. Records step-evidence/public-review-repair-dispatch.json and public-review-repair-first-snapshot.json. No continuous watcher, polling/sleep loop, duplicate dispatch or automation.
- Not yet merge-ready after coordinator's guard review: this repaired head requires completed public writer+8-file native readback original ZIP/digest audit. Earlier ee7f0ea/42303929271 successful original and stdlib audit are retained; they do not stand in for repaired-head proof. After new result, update exact candidate status and resolve current docs' pending-gate language without runtime changes/rerun for evidence-only documentation.
- Integration note: shared daemon server helper is STEP-only, alongside main font/tolerance receipt helpers; combine all scoped preservation and quarantine conditions. Foreground state check is STEP-only; preserve existing STL transaction hooks when reconciling shared export wrapper. Final review/integration remains coordinator-owned, no new review agents.


## Review-repair public failure preserved / observer coverage repair
- Run42361918322 at exact b5b2d1d2894e7ea78b81642b2b1b0b9dd593b7fa failed in independent readback only. Original artifact13570691525 ZIP step-evidence/public-original-42361918322.zip SHA256d113f76a96f31d27aee5a776ad357b1998fe5404651f264dd62f736888ce55be matches GitHub. Original native/daemon traces/reports retained extracted; job log step-evidence/public-review-repair-job.log; honest partial audit step-evidence/public-review-repair-audit.json.
- Actual first failure: eighth MCP AP203 wireframe LoadFile4 returned error0, but observer counted9 sketch-segment GetLength calls across3 sketches and failed minimum12 count before imported native save/reopen. Previous7 cases fully completed zero-error imports/native saves/readonly reopens/hash checks. Public writer all8 exports succeeded (sixCLI+SDK+MCP), one worker/host, foreground before/after exactly equal, source/native bytes stable, narrow runtime guard actual native passed, preferences restored and owned exits/cleanup succeeded. Whole run remains failed/not merge-ready.
- Independent raw STEP parsing proves last MCP file has twelve unique box B-spline edges [10x4,30x4,40x4] totaling320mm; no output protocol/vector defect found. Original observer traverses only top-level FirstFeature/GetNextFeature and discards partial lengths at its assertion; trace lacks types/IDs, so the evidence cannot distinguish native import loss from nested sketch omission. Do not claim nested features are the proven root cause.
- Minimal substantive observer repair: one bounded top+subfeature graph pass using official GetFirstSubFeature/GetNextSubFeature and document-unique IFeature.GetID deduplication; retain feature IDs/type/name/parent and partial lengths before failure. Unit fixture9 top-level+3 absorbed segments now passes exact12/320, duplicate top/sub references remain12, actual9 remains rejected and persisted, sibling cycles rejected. Original12/18 counts, length vectors, errors0, native saves/reopens and all tolerances unchanged. No reread/reimport/rebuild/native retry/rollback/host replacement. New native gate must confirm or refute this coverage explanation; no unchanged-head retry.
- Official primary references recorded in docs/step-export-options.md. No production/worker/schema/SDK changes in this repair; all previous guard fixes retained. STEP-focused36 tests pass including3456-mode CI selector matrix and runtime/peer/receipt guards. Fresh complete Windows portable/type/package gates remain mandatory before one necessary public dispatch. Existing full portable1854/26 skipped at guard head is not relabeled as running the new observer natively.


## Observer repair pushed / unique necessary public gate
- Pushed d6505f7384911b43b28a5f273ab14262032c4698 (test: 补齐 STEP 原生读回子特征并保留部分观察), own authorized branch only, production guard code unchanged from b5b2d1d.
- Single public workflow_dispatch https://github.com/YJBeetle/SWCLI/actions/runs/42365535291 ; public=true/internal=false/native_full=false, other defaults. One bounded GET verified exact head/event; snapshot in_progress. Records step-evidence/public-observer-repair-dispatch.json and public-observer-repair-first-snapshot.json.
- No ongoing watch/poll/sleep/automation, native retries/rollback/group restart or other CI cancellation. Next continuation must preserve original ZIP/digest and read actual feature inventories/partial geometry first. Full8-file evidence still required: do not promote7/8 or claim nested-feature root cause until actual native report establishes it. If fewer than12/18 remain after complete graph observation, keep failure and diagnose the real imported representation rather than re-dispatch unchanged.


## Full feature inventory refutes omission / native reference-curve observer repair
- Run42365535291/d6505f7384911b43b28a5f273ab14262032c4698 failed first on fifth AP214 wireframe reader case. Original artifact13571478417 saved step-evidence/public-original-42365535291.zip; SHA256b2e70c0786e67a9e97ff7a0af60234516eb2fd2a4884bf9b8506d7e6c9af1475 matches GitHub; metadata public-observer-repair-artifacts.json, original job log public-observer-repair-job.log, official summary in extracted swcli-test-summary/summary.json. Partial audit step-evidence/public-observer-repair-audit.json.
- All8 public writers/foreground identity+state/negative cases/owned exits passed;4 independent native cases fully completed; fifth import error0 but full top+subfeature graph shows9 sketch segments /260mm, sketch1 seven segments, sketch2 two, sketch3 empty. No nested sketch omitted: previous hypothesis is refuted. Raw AP214 STEP still12 lines /320mm. Group stopped at first strict count failure and retained partial inventory; settings/host cleanup passed. No accepted5th case or native retry.
- Official GetSketchSegments explicitly warns it may omit segments when a sketch has errors. Original evidence lacks underlying sketch error code; do not assert a diagnosed solver bug. IEnumSketchSegments.Next is in-process-only, so rejected as an out-of-process alternative. Do not heal/rebuild or retry the failed import.
- Minimal related observer correction selects native3D reference curves up front through exact installed swUserPreferenceIntegerValue_e.swImportNeutral_CurvesAndPointsOption and swImportNeutralCurvesAndPointsOptions_e.As3DCurves. Three existing boolean options+one integer share full snapshot/CAS/readback/restore, void vs bool setter contracts preserved. Runtime enum IDs resolved from TLB, never guessed. Original unknown representation rejects before writes.
- New reader measures official IReferenceCurve GetSegmentCount/GetSegments edges; calls edge.GetCurve before GetCurveParams3, normalizes documented reversed negative U ranges, then GetLength3 meters->mm. Explicit reference mode only, no fallback/reimport; exact12/18 counts, lengths, volume/area/centroid tolerances, zero native statuses and native save/reopen/hash checks unchanged. Old sketch reader remains only a portable/legacy diagnostic helper; native gate always selects reference-curves before the first import and uses same method after reopen. Complete partial feature/curve range data retained on failure.
- Only scripts/ci/verify-step-export-calibration.py, related portable test and docs/handoff change. No modern SaveAs3 migration/interface/export/worker files modified. Coordinator owns that separate work; original guard fixes retained. Focused38 tests passed including reverse-edge range/one-call order, native array/count mismatch and real9-edge rejection, mixed integer partial mutation/restore with zero retry, existing35 guard/geometry/CI tests. Complete portable suite running at step-evidence/portable-reference-curve-observer.log before one necessary new gate.

- Final native-reference-curve observer portable suite PASS:1857 tests/26 skipped (53.128 seconds), log step-evidence/portable-reference-curve-observer.log; STEP-focused38 passed. Fresh native TLB enum resolution/reference curve output remains unproven until the one new public gate. No migration files touched.


## Reference-curve observer tip / one bounded public dispatch
- Pushed exact tip b36375197873820c1197ea3cb6174382ba9fd49d (test: 显式导入 STEP 参考曲线并核验原生边长度), own branch only; no product/export/modern SaveAs3 migration files changed.
- Unique public workflow_dispatch https://github.com/YJBeetle/SWCLI/actions/runs/42405019483 ; public=true/internal=false/native_full=false, other defaults. Dispatch success and one bounded GET verified head/event; snapshot in_progress. Records step-evidence/public-reference-curve-dispatch.json and public-reference-curve-first-snapshot.json. No watch/poll loop/sleep/automation or other-run cancellation.
- Next continuation: save original ZIP/log/official digest, verify actual installed neutral integer enum and complete4-setting restore, native reference feature types/counts/edge ranges and8 file save/reopen proof. Keep previous9/260 sketch failure intact; do not claim native loss or solver root cause is fully explained. This fixed import profile is selected before one import only; no fallback or native retries.
- Still not merge-ready until repaired-head full public/native8-file acceptance audited. Final review/integration coordinator-owned; preserve modern SaveAs3 migration lane ownership. Do not rebase/rerun merely for other main changes.


## Reference-profile failure / confirmed General-vs-neutral parameter mismatch
- Run42405019483/b36375197873820c1197ea3cb6174382ba9fd49d completed failure only in independent reader. Original artifact13587497385 saved step-evidence/public-original-42405019483.zip, SHA2565149d2d543cab9461ab6fd826fa465a239577866d4326aa51655dab12e49e945 matches official GitHub digest. Original log public-reference-curve-job.log, metadata public-reference-curve-artifacts.json, extracted official swcli-test-summary/summary.json and first-failure audit public-reference-curve-audit.json preserved.
- Exact accounting:8 public writes succeeded (6CLI+SDK+MCP) with8 native export calls, all raw STEP solid topology/wire vectors/hash verified; writer source+foreground/prefs/cleanup stable. Reader started2, completed1 AP203 solid native save/readonly reopen, second AP203 wireframe LoadFile4 error0 rejected at nonempty3DProfileFeature type check BEFORE any GetLength call. Report0/0 means unmeasured partial, NOT lost/zero geometry. No physical native wire count/length is established by this run. Both cases’4 prefs restored and owned exit/cleanup succeeded.
- API parameter check found documented mismatch: swMultiCAD_Enable3DInterconnect=false selects General curve controls. The code wrongly set neutral swImportNeutral_CurvesAndPointsOption578=1; observed native still sketched. Official General API maps free curves to swImportFreeCurves + swImportCurvePreference=swGeneralImportAs3dCurves, with swImportSolidSurface; official General UI states these controls apply when3D Interconnect disabled. LoadFile4 arg r explicitly means new document, so it is correct and remains unchanged. This is a concrete configuration-family repair, not a presumption that lost geometry is only observer error. Prior9/260 sketch mismatch is still retained/unresolved.
- Minimal repair changes only test observer profile names/enum owners to General family; dynamic installed-TLB resolution and full4-value snapshot/CAS/status/readback/restore unchanged. Unexpected sketch type still fails, but now its actual lengths are recorded first and complete=false prevents interpreting unmeasured0 as physical loss. Exact12/18 vectors/counts, all tolerances/statuses/native save/reopen checks unchanged, no retry/reimport/rebuild/healing. Production/SaveAs3 migration files untouched.
- Focused40 tests passed: General-vs-neutral independent preference regression; correct enum-owner/name contract; partial unexpected-sketch measurement and incomplete marker; all previous edge-count/range and guard/CI cases. Full portable suite running at step-evidence/portable-general-import-profile.log. Main960839e passing portable is acknowledged without rebase/rerun for unrelated main changes. Only one necessary public gate follows portable verification.

- Final General-profile portable suite PASS:1859 tests/26 skipped (50.476 seconds), log step-evidence/portable-general-import-profile.log; STEP-focused40 passed. No product/SaveAs3 migration/interface changes. General installed enum IDs and actual reference-curve8-file roundtrip remain to be proved by one necessary new gate; current branch not merge-ready.


## General-profile repair pushed / one bounded necessary gate
- Pushed060f26178b4deabc330ef0959b9ec0f1704159cf (fix: 对齐 STEP 旧导入器的 General 参数并记录未完成读回), same dedicated branch. Only observer script/test/docs/handoff changed; no SaveAs3 migration or runtime adapter file modified.
- Single public workflow_dispatch https://github.com/YJBeetle/SWCLI/actions/runs/42413805736 ; public=true/internal=false/native_full=false, other defaults. Success return and one bounded GET verified exact head/event; snapshot in_progress. Records public-general-profile-dispatch.json and public-general-profile-first-snapshot.json. No ongoing CI watch/polling/sleep/automation.
- Next: preserve original ZIP/log/official summary/digest before judging actual General enum mapping and native representation. Full8-file strict roundtrip still required. If no successful full reader proof, keep release blocker; never interpret unmeasured partial counts as missing geometry, never substitute a prior successful head or loop unchanged native attempts. Final review coordinator-owned.


## General-profile native failure: technical blocker, no further gate
- Run42413805736 exact060f26178b4deabc330ef0959b9ec0f1704159cf failed in reader; originals retained before any edits. Artifact13591430613 ZIP step-evidence/public-original-42413805736.zip, SHA256de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7 matches GitHub; metadata public-general-profile-artifacts.json; original job log public-general-profile-job.log; extracted official swcli-test-summary/summary.json; audit public-general-profile-audit.json.
- Exact counts:8 public writes succeeded (all6CLI+SDK+MCP),8 native export calls; raw solids1/6/12/8 topology and wire12/320 or18/560 vectors/hash all checked. Writer source/foreground/prefs/cleanup unchanged. Reader started2, completed1 AP203 solid import/native save/readonly reopen. Second AP203 wireframe LoadFile4 error1, no imported_geometry/native save fields. Native physical count/length are UNAVAILABLE, not0. Current source assigns returned pointer into live.document; cleanup trace has no CloseDoc after this load and cleanup_errors empty, so the audited harness path implies returned None. Direct returned-object metadata was not persisted; no other native geometry is available to read.
- Actual current General constants from installed TLB: swImportSolidSurface161, swImportFreeCurves162, swMultiCAD_Enable3DInterconnect691, swImportCurvePreference206, AsSketches0/As3dCurves1. All4 requested values exactly read back and originals restored for both cases; owned reader exit confirmed. This establishes API preference effects, NOT actual translator route/representation. Earlier General-family rationale did not yield a working fix; do not present it as proven root cause. No new parameter/observer replacement is substantiated by current artifacts.
- Therefore NO new code commit/push/native gate, unchanged-head retry, API retry, reimport/rebuild/healing/rollback/group restart, CI watcher/poll/sleep or cancellation. Product and modern SaveAs3 migration files untouched. Main960839e portable success is not substituted for this missing native gate. STEP remains NOT merge-ready and a series release blocker.
- Minimal next diagnostic is concrete/reviewable but unapplied: step-evidence/proposed-minimal-import-diagnostics.patch. It reads both7-value General+neutral context families before ONE import without changing requested settings, persists returned-pointer class/error metadata, and defers strict representation rejection until all supported sketch/reference geometry has been inventoried. All existing12/18 counts/lengths/tolerances/error0/native save-reopen assertions stay. This is a diagnostic proposal only, not a proven correction; no tests or native dispatch were run on it, and it is not in branch code. Coordinator can review whether the extra information warrants a bounded diagnostic before any further acceptance run.
- Current branch runtime/code tip remains060f26178b4deabc330ef0959b9ec0f1704159cf. Only local docs/handoff and ignored evidence/proposal records changed this turn. Final review/integration and SaveAs3 migration remain other owners; no review agents spawned.


## Offline research / applied import provenance (supersedes unapplied proposal above)
- Latest coordinator direction: complete offline root-cause research, apply/test the diagnostic patch and make a reviewable Chinese commit; NO native dispatch this turn. Modern SaveAs3 production migration and final review/integration remain other owners. No local CAD/VM, new agent, CI watch/poll/retry or production change.
- docs/step-import-offline-research.md records full findings and one discriminating original-output readback plan; docs/evidence/step-import-offline-2026-11-08.json holds selected hashes/metadata/results. Stdlib analyze-step-wire-evidence.py and step_wire_evidence.py reproduce root-reachable linear geometry/units/graph checks; no full EXPRESS claim. Five failed-run pairs b363751→060f261 and successful ee7f0ea→060f261 control all have equal geometry:12/320 or18/560, no dangling/orphan curves;8 vertices/12 base edges/degree3/one component/six closed geometric boundary loops. Byte equality is false and geometry signature excludes parameterization; do not claim metadata-only differences or solid BREP topology.
- Installed2025 static contract: PIA33.5.0.53; local swconst.tlb SHA95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6 matches native inputs; local sldworks.tlb SHA585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159 is NOT known to match old CI. GetImportFileData returns generic IDispatch/object; IImportStepData only MapConfigurationData(bool), no IGES CurvesAsSketches. r means new model, not readonly or curve mode. Runtime QI/MapConfigurationData/General-vs-Neutral precedence and prior9/260 remain UNKNOWN; no substantiated production repair.
- Applied diagnostic reads8 actual preferences (6Toggle+2Integer), installed sldworks.tlb interface IIDs/hash, GetImportFileData type-info/QI/STEP mapping getter, explicit LoadFile4 returned-pointer/errors/exception, and successful document type/title/path. No profile desired-value changes or MapConfigurationData setter. Unknown diagnostics cannot replace first CAD error. Full supported sketch/reference inventory is collected before strict type rejection, with complete=false on mismatch. Native save filename remains case-specific; regression covers consecutive different names. All existing geometry/count/vector/tolerance/error/save-reopen assertions remain.
- Necessary native plan is NOT executed: revalidate original42413805736/artifact13591430613 ZIP SHAde9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7 and all8 receipt file hashes, restore only exact original paths, run existing --export-report reader once under unchanged General profile with one host/first-failure stop/600s+1800s deadlines. No new exports, parameter sweep, native API retry, group restart or workflow change. Coordinator reviews then arranges native. Even diagnostic8/8 would require later fresh integrated public acceptance; STEP remains NOT merge-ready.
- Focused STEP tests48 PASS; full portable verification final log step-evidence/portable-offline-import-research-final.log (result recorded below after completion). No SDK/schema/workflow or production adapter changes. Old ignored proposed-minimal-import-diagnostics.patch is historical and superseded by the actual reviewed diff.

- Final offline verification PASS: STEP-focused48 tests; full portable1867 tests/26 skipped in51.121s, log step-evidence/portable-offline-import-research-final.log. Original ZIP SHA256 rechecked for42413805736/42405019483/42303929271; latest original source receipt/head and all8 STEP digests rechecked; both5-pair geometry/fixture reports verified. git diff --check clean. Scope remains observer/offline tools/tests/docs only; public interface, profile desired values, workflows and production SaveAs3 files untouched.

## Fixed-original import diagnostic wiring (2026-11-10; review before dispatch)
- Coordinator has accepted one bounded, information-adding original8 readback plan; requests exact-head preparation and quick personal review before owner dispatches once. Implemented a separate default-off manual profile in existing ci.yml, not a new default-branch workflow or main change. No dispatch yet.
- New inputs native_step_import_diagnostic=false and native_step_import_head=''; eligible only exact repository/manual dedicated ref/head matching github.sha, exclusive with native_full/internal/public. Distinct diagnostic concurrency group, cancel-in-progress=false. Existing tag/full/internal/public mode semantics preserved;13824 event/ref/flag/head/result combinations checked.
- New stdlib prepare-step-import-original.py has no CAD imports. Before any private stage: exact current checkout/workflow/run/event/repo/attempt1; source42413805736/060f261/event/workflow362005755/completed failure/original attempt1; GitHub artifact13591430613 identity/source/unexpired/digest; original ZIP fixed SHAde9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7 and size; unchanged original report; all8 pinned ordered paths/protocol/geometry/surface/SHA256. Only exact original D:\a\_temp paths, rejects links/reparse points, checks all targets before first copy, exclusive create or identical-byte reuse, never overwrites different files. Original ZIP and metadata retained.
- Before one existing -I reader invocation, verify mode rechecks all8 restored hashes, ZIP/report bytes and exact diagnostic context. One owned host and original eight-case plan, no re-export/profile switch/MapConfigurationData setter/retry/rebuild/rollback/restart;600s/1800s guards and31-minute outer step unchanged. Input provenance and output directories separate. Dedicated diagnostic artifact, summary scope and false production/full acceptance eligibility; not a fresh public acceptance claim. No production code/SaveAs3 changes.
- STEP-focused56 tests PASS including new provenance/path/conflict/rerun refusals. Original real ZIP offline validation passes exact8 identities; full portable and actionlint/YAML review results follow. Await coordinator personal exact-head review before a single dispatch; no native execution in local VM.

- Final wiring verification PASS:56 STEP tests; full portable1875 tests/26 skipped in49.589s; actionlint v1.7.12 exit0; PyYAML6.0.3 duplicate-key-rejecting parse confirms9 inputs and job permissions; git diff --check clean. Real fixed ZIP validated offline against all8 pinned original identities. Logs original-import-focused.log, original-import-portable.log, original-import-actionlint.log in ignored step-evidence. Native script/production adapter/SaveAs3/profile desired settings unchanged. Preparing review commit and exact-head handoff; NO dispatch until coordinator review.

## Original diagnostic42664273210: first failure preserved, HTTP contract repair
- Coordinator reviewed671b388 and approved one dispatch after portable/SDK/actionlint; same-head manual runs0 before single POST. Run42664273210 exact671b388ef48ee3d1f1c602cef46c0c56b0c5e205/workflow_dispatch/attempt1 now FAILURE. Windows portable3.9/3.14, SDK and package jobs succeeded. No CI watcher/repeated dispatch.
- Official failed job129326033161 log and run/jobs/artifacts JSON retained in step-evidence/diagnostic-original-42664273210/. Diagnostic original artifact13695299906 SHA7f3f827cbad03b2568501c5ddd22e1f7d728b007c4de052a588ff8a8044695f7 contains only3 validated metadata JSONs; official summary artifact13695613449 SHA36baf40dd977e88a9e14801fadb4d981149c5f89f7e6150df3fbc1b1d1d9282e. Both ZIP hashes match GitHub and sourcehead; no original bytes replaced.
- First failure is source ZIP download at actions/artifacts/13591430613/zip after current/source/artifact metadata passed. Private inputs/install/runtime/reader all SKIPPED. GetImportFileData/LoadFile4 were not reached; actual QI/options/MapConfigurationData/returned model/native geometry are UNAVAILABLE, never0. No source file restoration or new CAD export.
- Original error omitted HTTP detail. A single same-request no-CAD reproduction returned415 Unsupported Accept application/octet-stream; API requires JSON Accept. Corrected application/vnd.github+json request produced a byte-identical fixed original ZIP de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7 and all8 pinned identities passed. Original failure HTTP status itself remains unrecorded; do not invent proof or blame permissions/CAD.
- Minimal fix only HTTP Accept and sanitized structured status/exit/message retention, no stderr/credentials/signed URL logging or automatic retry; binary controls decoding only. Added original-byte/no-retry/error-redaction regression. Workflow/owned reader/profile/settings/8-file assertions/600+1800 unchanged. Coordinator authorizes one necessary new-head validation only after related+full portable checks; no native blind retry or main/SaveAs3 changes.

- Final HTTP repair checks PASS:58 STEP tests, full portable1877 tests/26 skipped in52.132s, logs original-import-http-focused.log and original-import-http-portable.log. Workflow, permissions, secret set and all native/product files unchanged. Latest coordinator note requests0CAD for this phase: commit/push the proven retrieval fix and report original first cause; NO new dispatch in this turn. This source-run failure remains pre-CAD, not STEP/LoadFile4/public acceptance evidence.

## Fixed-original diagnostic42813151084: detailed original audit / no new dispatch
- Coordinator requests official original audit, first real native failure and cleanup; only proven source/fixture defects may justify a minimal tested patch for root review, no dispatch. Current runtime head2c4e491603e2af81ba33ab0b0a7e98a94ce800c3/workflow_dispatch/attempt1 FAILURE. Native install/private stages passed; no VM used locally.
- Preserved official full job129821421626 log, run/jobs/artifacts and original ZIPs in step-evidence/diagnostic-original-42813151084/. Diagnostic artifact13764700892 SHA02aa277ef919cf1056a8292a6729a5c4571a79eb510554e8ee9d728acb324281; hosted/official summary artifact13764691009 SHAd25c6456f8ee8c25ab0b3f4ed16668b1ab3ecde776dae6ae4db0bbbe2907c6aa, all matched GitHub/head. Embedded fixed source ZIP de9e6312... byte-identical; unchanged original receipt and all8 restored STEP files rechecked after failure; common reader files in both uploads byte-identical. Offline reproducible audit-original-42813151084.py + audit.json; committed selected machine record and human audit docs.
- Native plan8, started2, completed1. First AP203 solid LoadFile4 model/error0; original numeric/body checks, native save and readonly reopen pass. Saved46297 bytes SHA8d80278f75d9b8307adcdf3cec54dd489fff5735913fd336871522518ea13780. Second AP203wire LoadFile4 returned None/error1; no native geometry/save/reopen. First business failure STEP geometry readback failed; no replacement by diagnostics. Remaining6 unattempted. Raw source topology1/1/6/12/8 and root-reachable wire12/320 or18/560 remain intact but do not prove native import.
- Actual same8 preferences both cases: Interconnectfalse; General solidtrue/freetrue/curve1; Neutral solidtrue/freefalse/curve0; global StepConfigfalse. This is observed context, NOT translator precedence or actual object MapConfigurationData. Installed swconst95e36... and sldworks585e... identities now native-recorded. Import data CDispatch/typeinfo count0; IGES QI E_NOINTERFACE; STEP QI Python unregistered-wrapper TypeError; object MapConfigurationData UNKNOWN/unread. Model typeinfo invalid-index diagnostic did not block successful solid measurement/save/reopen.
- Complete cleanup: both preference vectors restored exactly; hidden owned PID7884; one acquisition, one ExitApp and successful owned-process wait/handle close/CoUninitialize; cleanup_errors empty and private cleanup step success. GetImportFileData/LoadFile4 exactly2 each, one per file, no retry/host restart/new STEP export.
- Proven separate observer source defect: actual pywin32-312 installed; official b312 PyIUnknown.cpp and PyComHelpers.cpp show single-argument QI may succeed natively then fail creating an unregistered Python wrapper. Minimal patch uses QueryInterface(installedIID, pythoncom.IID_IUnknown), one native QI, only base wrapper/no custom vtable. Exact E_NOINTERFACE→observed false; other errors unknown; MapConfigurationData getter only after positive QI. Original report unknown remains unchanged. This is NOT proof of a LoadFile4 repair; no profile, option, product, assertion, CI workflow, SaveAs3 or watchdog changes. Await root review; NO dispatch.

- Latest root direction: no full CI repetition for the QI-only observer correction; provide minimal diff/counterexample, optional local single-original GetImportFileData+single STEP IID QI plan with zero LoadFile4/import/save and no IID scan. Root exclusively manages VM. docs/step-import-qi-local-plan.md specifies immutable file SHA, candidate path pending root allow-path verification, actual library/version/IID prerequisites, one hidden owned host, zero preference setters, at-most-one mapping getter, failure stop/deadlines/input-hash/exit proof. Not executed here.
- Final QI observer checks PASS:59 STEP tests; full portable1878 tests/26 skipped in53.790s (original-import-qi-focused.log/original-import-qi-portable.log). Detailed audit-original-42813151084.py passed all original/hash/trace/cleanup checks. No native/business failure correction is claimed. Minimal source/test diff prepared at step-evidence/review-import-qi-minimal.patch; no new CI dispatch or local CAD. Original current native evidence remains1/8 complete, wireNone/error1; root review required.

## Root-only zero-import STEP data script (2026-11-11; local commit only)
- Latest root-approved fixed CAD input is exclusively C:\Workspace\SWCLI-series-20261111\step-qi-input\ap203-wireframe.step (SHA3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90), never Desktop. Implemented independent scripts/ci/diagnose-step-import-data.py / case_runner for root review, no CI wiring, VM control, production modification or push requested.
- Reads original byte/file-ID/time/attributes metadata and requires pre-existing Windows READONLY, exact canonical path/no link or reparse, pinned input SHA and original source run/artifact/ZIP identity. Both actual installed TLB SHA and pywin32=312 verified before host; actual single official STEP IID verified from the pinned installed library. Enum reader must be the same hash-verified swconst.tlb. Uses reviewed isolated source snapshot without replacing production install; code hashes recorded.
- Reuses existing owned harness lifecycle with one case and same600/1800 supervisor. No-host process guard plus one strict ROT absence check before a single activation; unknown ROT errors never create/attach. ReadOnlyApp exposes only required reads/ExitApp, denying all CAD import/save/new/select/preference writes before underlying COM. Actual hidden/revision33.5.0/empty catalog checked. Exactly6Toggle+2Integer reads, one GetImportFileData, one installed STEP IID safeIUnknown QI, at most one MapConfigurationData getter only after positive QI. No type-info/IID scan/fallback/import/save/retry.
- Every unknown/type mismatch/COM refusal/None/exception stops subsequent case work immediately. Original exception retained; only owned cleanup and read-only postflight continue. Data released before exit. Existing owned process wait/handle close/CoUninitialize preserved. Partial activation config failure stores first error + known PID before cleanup while COM is still initialized; errors remain separate. Primary/observation/partial-cleanup traces are all supervised at unchanged600/1800; timeout records owned exit unknown/root cleanup required, never fabricates shutdown or uses process-name/global CAD termination.
- Portable traps cover success, unknown first preference/data/QI/mapping, existing host/unknown ROT, readonly/hash/library/IID guards, partial activation cleanup before CoUninitialize, cleanup failure preserving first error, read-only proxy denial and all3 trace channels at600 plus group1800. LoadFile4/OpenDoc/Save/New/Select and preference setters remain zero reached; no business or API retries. Updated docs/step-import-qi-local-plan.md with fixed Workspace input and root-only command/source-snapshot/output contract. Native execution remains NOT PERFORMED, no new CI dispatch. Validation results recorded after completion below.

- Final local-only verification PASS:70 STEP tests; full portable1889 tests/26 skipped in50.599s; CLI --help parsed; diff whitespace clean. Logs step-qi-only-all-step.log and step-qi-only-portable-final.log. Preparing local Chinese commit only; no push/VM/CAD/CI. Code fingerprint manifest step-evidence/step-qi-only-review-manifest.json and review patch retained for root. This script remains unexecuted natively and cannot validate production STEP import.

## Root first actual local QI success / offline audit only
- Root executed pin4b0104bec301abfcf6163d25f0ff306a26a21e16 once using a short fixed Python launcher. Original task artifact step-qi-once-4b0104b-01 report SHAad362253f064f9fb620b0775379debd598eaa17a2db1712afd498dca92e90f8f verified; selected183-runtime-file archive SHAbaacb00023feb4377945ef8b5dc75a1b14275b16fbcdcbc0274b63ae9d6808c0 all members match commit, not a whole-repository archive. All4 actually loaded code hashes match. Copies retained under ignored local-qi-original-4b0104b-01; reproducible audit-local-qi-4b0104b.py passes.
- Actual Python3.14.7/pywin32312, same pinned TLB hashes, hidden owned PID8604/rev33.5.0; one acquire/data/STEP QI/getter, QItrue/MapConfigurationDatafalse; eight prefs each1;0Load/Open/New/Save/Select/UserPrefSet,0docs before/after; exactreadonly bytes+metadata all checkpoints same; cleanup[]/remaining[] and owned exit wait confirmed. Nested observation ExitApp is same main call, not2. Root reports2 EncodedCommand launcher failures before code dir/CAD; successful fixed launcher is first actual API run, not retry. This lane did not operate VM/CI.
- Critical differences local vsCI42813151084: local3DItrue/GeneralFreefalse/GeneralCurve0 vsCIfalse/true/1; other5 raw prefs same. Local objectfalse must NOT backfill oldCI unknown; native LoadFile4 error1 unresolved. Current source CI still writes General3toggles+curve only, Neutral read-only. No production acceptance/merge proof.
- Read-only official help research: MacSW2025 installation CHMs and selected-member hashes retained; not claiming VM CHM byte identity. General table gates FreeCurves to3DI=false; format-specific STEP/IGES/ACIS maps freecurves-as-sketch toNeutral;0/1 enums known but precedence NOT documented. Official2025 UI says STEP uses latest conversion technology even with3DI disabled, so off!=legacy translator proof. MapConfigurationData override applies only STEP configmapping, not curvefamily. Installed LoadFile4 parameter table null-when-off vsSTEP example r+object has unresolved documentation ambiguity; no guessed argument change.
- docs/step-local-qi-4b0104b-audit.md records exact evidence, full8-value comparison, primary sources and one unexecuted root-reviewed hypothesis candidate (single NeutralFree bool change relative oldCI, no simultaneous argument/profile sweep). Explicitly not a proven fix or causal priority proof across local/CI environments; if gain insufficient, clarify vendor parameter contract before import. No new executable code or native dispatch; local docs/evidence commit only. Existing zero-import allowlist untouched.

## Independent one-import hypothesis prepared (local only; no execution)
- Latest carried-forward root scope is an independently reviewable single-import entry, local Chinese commit only. New user replies confirm the historical ff7f66/numeric repair/public validation authorization; that numeric repair already exists at6d47766 and subsequent pushed native runs, so the old patch is not reapplied and historical runs are not duplicated. Current proven native first failure remains42813151084 AP203wire None/errors1; no import repair is claimed.
- Added scripts/ci/diagnose-step-wire-import-once.py and docs/step-wire-import-once-plan.md. Existing zero-import entry, production adapter, original reader and CI workflow remain byte-identical to578dcca. Fixed readonly original/hash/path and pinned actual libraries/pywin32312; same owned harness/600+1800 watchdog. No VM control, new CI wiring or push.
- Full8 typed original snapshot/CAS before writes, exact oldCI General profile readback, then only new NeutralFree=true; NeutralCurve0 remains unchanged and NeutralSolid/globalStepConfig have no setters. Unreviewed initial Neutral/default fields stop before any setter. Each attempted setter/readback is persisted, including partial application/refusal, then only owned attempted writes are restored in reverse under value guards. Unknown/foreign values retained, never repaired into a success claim. Complete original8 verification and restore errors remain separate from first business error.
- At most1fixed GetImportFileData,1safe STEP QI/getter,1LoadFile4 with unchanged r/samefactory object; Map readonly. Strict reference representation,12segments/320mm/exactlengths remain. Unknown/failing geometry is unavailable/null with raw partial observations preserved. No retry/fallback/Open/New/Save/Export/Select. Returned error model immediately enters owned cleanup; at most1owned CloseDoc, one Exit/wait/handleclose/CoUninitialize; timeout preserves original report and explicitly unknown exit/root cleanup.
- Portable verification PASS:14 dedicated tests;84 STEP tests; full1903 tests/26 skipped in51.487s. Focused fake-COM traps cover exact candidate success, initial unknown/CAS conflict/unowned drift, early and final partial setter failures, refused integer return, QI/map unknown, native None/error1 and exception, failed restoration/foreign third value, CloseDoc failure preserving first error, strict wrong representation/partial geometry and all3trace600/group1800 watchdog paths. CLI help parsed and diff whitespace clean. Logs step-wire-once-focused.log, step-wire-once-all-step.log, step-wire-once-portable.log.
- Native execution NOT PERFORMED. This is a hypothesis for root review, not a proven fix/priority/causality result or public/full acceptance. Local-vsCI environment differences remain explicit. No full CI repetition for the QI-only change, no default DockerSW checkout/main/rebase/merge/release or other lane edits. Root owns any actual VM allocation, reviewed snapshot transport and single execution.

## d232e35 first actual wire import: offline audit only
- Root reviewed all guards and14 fake tests, then executed first actual single import once. Immutable task bundle wire-once-d232e35-01 reportSHA4e8332dd621a389268e92ecb4cac317acb77a930b314c0b396662f9eaa10ee4e; sourceZIPde52dbe3ca79c0a032ce6b488a2477859796c209234ee58e1bb5b43afff9707e. Local copies retained under ignored step-evidence/wire-original-d232e35-01. New stdlib offline audit verifies184 runtime members and6 loaded code hashes against exactd232e35, raw input bytes/metadata, all CAS/set/read/restore stages and trace pairs; docs/step-wire-d232e35-audit.md and machine record committed.
- Native result FAILURE on strict reference representation:1LoadFile4 part/errors0,1data/QI/map, QItrue/Mapfalse;18unique features include two3DProfileFeature IDs17/18 each6segments,12GetLength, raw12/320 vector valid at original bounds. Geometry remains unavailable/null, rawcompletefalse/mismatches17,18. No native save/reopen. Main158paired calls has exactly1error at read-imported-wireframe; observation109paired calls allend. No retry/fallback/baseline replay.
- Original file10595bytes/SHA3a4f0326.../metadata/attributes33 identical across actual checkpoints. Four attempted owned writes/readbacks restored in reverse, full8original equal,128read records/15full stages observed. Cleanup[]/nohostbefore[]/remainingnative[]; hidden ownedPID2568/rev33.5.0, CloseDoc/Exit/wait/handleclose/CoUninitialize each1complete. Nested observation exit is not a second native call. Original first failure retained.
- Local model return differs from hostedCI None/error1 but installation/environment differs and no controlled baseline replay; no causal fix or preference-priority proof. Root permits preparation only of NeutralCurve0→officialAs3DCurves1 withNeutralFree=true/allotherargs unchanged; still root review before any execution. This audit did not use VM/CAD/CI/network/push or alter original artifacts/production/reader.

## Neutral As3DCurves single-variable candidate prepared; root review only
- Semantic basis: actuald232e35 pinned TLB enums AsSketches0/As3DCurves1 and previously extracted official2025 installed enum pageSHA575e3f7b... agree; wrong sketch representation observed atNeutralFree=true/NeutralCurve0. This supports a falsifiable candidate, NOT proven translator consumption/priority/causal repair. Official CHM is localMacSW copy, no claimed VM CHM byte identity.
- Explicit --neutral-3d-candidate mode only; new diagnostic_case step-wire-neutral-3d-once/new fixed evidence parent step-wire-neutral-3d-evidence. Preserve8original/CAS and previous General+NeutralFree=true vector; verify this vector by reads WITHOUT importing baseline, then set only NeutralCurve to actual installed As3DCurves1 and require changed_from_d232e35 exactly that key. Invalid/noninteger0/1 enum stops before any setter. Default historical mode remains compatible but MUST NOT be run again.
- Only candidate mode grants this additional integer setter; other unowned fields remain blocked. Five attempted owned writes from knownlocaldefaults restore in reverse; every setter persisted before attempt/fullreadback, partial refusal and foreign third value guards retained. Same1data/QI/getter/Load withr/samefactory, strict reference12/320/vector; no Save/Open/New/Export/Select/fallback/retry. Existing reader/zero-import/production/CI unchanged,600/1800 unchanged. Concrete root-only execution command/provenance/decision rules in docs/step-wire-neutral-3d-candidate-plan.md.
- PASS20 dedicated/90STEP tests; full1909tests/26skip in65.374s, final focused20 pass after text cleanup. Logs step-wire-neutral-3d-focused-final.log, step-wire-neutral-3d-all-step.log, step-wire-neutral-3d-portable.log. Fake tests cover only-one-vector change/no baseline import, originaldata/r, candidatepartial/refusal/restorefailure, unknownenumzeroSetter, foreignNeutralvalueguard, sketch12/320/missingedges/wronglength/None errors strictunavailable, flagforward/newroot/supervisor. d232e35offline audit rerun byte-identical, help/diffcheck pass.
- LOCAL COMMIT ONLY. Candidate NOT executed; no VM/CAD/CI/push. Root must personally review whether evidence warrants one execution and coordinate VM/source archive; no production acceptance or release/integration claim. No new feature or broader parameter sweep.

## 60f1cf8 first actual candidate failed; offline independent audit
- Root reviewed60f1cf8/20tests and ran candidate once, no retry; VM released/idlepauseON is root-reported, not operated/probed here. Immutable reportSHA0abe0117a2f06ccf8f7335f376d5e3a9f7c29e39af05d2ce5f2f0faf3e68b50c/sourceZIPed6c6a0d5799bfe38dcefabebf830cd0e2b44bd1cf707b07fc7c6e1acfdc020a verified.184runtime members match60f1cf8, all6actual codehashes match. Local original copies under ignoredwire-original-60f1cf8-01. Audit script now also pins this exact run and compares previous immutable bundle; prior audit output remains byte-identical. Machine+Chinese audit committed separately.
- Single data/QI/map/Load, modelpart/errors0,QItrue/Mapfalse;SW7080/33.5.0. StrictFAILURE same reference-curve sketch geometry;18features,3DProfile17/18each6,12GetLength/320/rawvector+featureinventory exactly equalprevious original;geometry unavailable/null. Main186pairedcalls/1firsterror;observation109pairedcalls/allend. NeutralCurveactual1/changeonlythiskey vsd232 original. No baseline import/retry/save/reopen.
- Fiveowned setter/readback/restoreverified reverse,154readrecords/18fullstages,complete8originalrestored,restoreerrors[]. Inputhash10595bytes/allactualmetadata checkpoints identical andsameprior. Close/Exit/wait/handleclose/CoUoncecomplete;cleanup[]/nativebeforeafter[]/no timeout. Retainfirsterror,notroot-summarysubstitute.
- User/root says stop blind enum/toggle sweep. Next READONLYresearch only: exact2025LoadFile4 3DIoff/null table vsremarks/examples, installedTLB/interop parameterABI andr semantics. Any supported minimal single-variable idea is proposal only; do not implement/execute native/CI/push. Preserve strict reference representation and no causal/generalpriority claim. main841b49e/CI42994990176 alreadyreportedpassed; not queried.

## LoadFile4 2025 conditional contract: read-only research; no new native candidate implemented
- Freshly re-extracted installed2025 .NET LoadFile4/GetImportFileData/STEP CSharp+VBA and VBA typelib LoadFile4 CHM members; old member hashes identical, new VBA memberhash7e11ab93... /CHM9b7e4352... retained. Official2025 web attempts returned navigation shells, not claimed as observed body; no2012search substitute. Full source fingerprints/research machine record and docs/step-loadfile4-contract-2025.md saved.
- Exact parameter table confirms ImportData null/Nothing when3DIoff; ArgStringempty whenon. Remarks put lowercaser in off/nonDXF/nonProE branch for a new document; r is NOTreadonly/referencecurveselector, upperProER separate. InlineIGESfragment merelynamesimportData without initialvalue, so earlier overstrong “nonnull object” characterization corrected; not used as proof. CompleteSTEPexamples explicitlyfactory+Maptrue+r with no3DIstate, solidexport/import/repair context/no wire evidence; either literal booleanstate conflicts with one tablecondition. No vendor erratum found; conditionalbehavior remains UNRESOLVED, not proven callingdefect.
- New purely static inspect-step-loadfile4-metadata.py reads pinned2MBMSFT TLB plus local .NET metadata(dnfile0.18), noLoadTypeLib/COM/DLLexecution. Method227record941396: nativeHRESULT;2BSTR;ImportData[in]VT_DISPATCH;Errors[in,out]PTRI4;retval[out,retval]PTRPTRIModelDoc2, nooptionalargs. CLR explicitIDispatchmarshal1a agrees, actual signature tokens independently decoded; interfaceGUIDsame; inputhashes stablebeforeafter. TLBsha585e... equalsVMreports; localInteropsha a53c.../33.5.0.53 not assertedVMbyteidentity becauseVMInterophash absent.
- Read officialpywin32b312: genericNone→VT_NULL vs typedVT_DISPATCHNone→NULLpointer; VARIANTwrapper/Nothing not assumed interchangeable in typed method. Original reports do not prove exact Python binding branch. Semantic minimum PROPOSAL ONLY: only third LoadFile4 input nonnullfactory→explicitNULLIDispatch, keeping60f1cf8eightvalues/r/file/strictreference12/320,1Load/no baseline replay and originalguards. Fix/verifybindingrepresentation androotreview first; existingnativeproxy stillrequiresnonnullsamefactory and is UNCHANGED. No runnable null mode or command, no native implementation/VM/CI/push. Vendor conditionalclarification remains preferred if informationgain insufficient.
- Validation: new+old original audits PASS(oldoutputbyteidentical); staticTLB/Interopdecoder PASS and badhashrefusal PASS; existing20fake single-import tests PASS in2.628s; CLIhelp/whitespace check. Production, originalreader/zeroimport, nativecandidate entry, workflows unchanged from60f1cf8. No need to relabel previous1909portable result as testing newnative code: no newnative code here. Main841b49e/CI42994990176 not queried perroot instruction.

## Explicit NULL IDispatch candidate prepared after root approval; LOCAL ONLY
- Root accepted2c773f8 research and authorized preparation/tests only, notVM/CI/push. New --null-import-data-candidate retains complete60f8value vector (computedchanged_from_60f1cf8=[]), fixedreadonlyoriginal/r/errors/1factory-QI-readonlyMap/strictreference12/320/vector/ownedrestore/600+1800. Factory explicitlyobservationonly;actualLoadthirdargNULL. Independentnull-dataevidenceparent; modeexclusive/forwardedtochild. Existingdefault/neutral modes remain historical, no baseline rerun.
- Addedstep_null_binding helper: beforehost attests3installedb312PythonfilesSHA(CRLFonly) and4runtimeCDispatchhandlers againstsame-interpreter whole-sourcecompiledcode incltypedconstants/exceptiontables. Duringcase readsnormalmethodmap, ifneeded onlyoriginalreadonlyLazyAddAttr_, neverunknownmemberInvokeprobe. ExactMapEntry227/signature/name/optional/type/normalgenerator and cachedboundreceiver/code proof; unsupportedwrappers/signatures/source/handlerchanges reject0Load, noForceDispatch/EnsureDispatch/manualInvokeTypes orbindingreplacement.
- ExistingtypedApplyTypes→InvokeTypes keeps None only withactualDISPATCH9signature and b312NoneOKinterfaceconversionproof;existinggenericInvoke usesoneexplicitVARIANT9/Nonecarrier. Determinedbycurrentbindingmetadata, nottry/fallback; refusals poison and cannotreprepare/retry. Nativecall usescachednormalboundmethod, notmanualInvoke path. Actualsignature/payload/code fingerprints andconversionSOURCES saved;pointerclaim explicitlysourceproof+observedPythonmetadata, NOTnativeaddress/memorymeasurement. bound_method_invocation_attempted doesnotpretendPythonconversionfailureprovesnativecall. Historical60factualbranchnotrecorded, cannotclaimcross-runbranchidentity; disclosedforrootreview.
- PASS12newbindingtests +25entrytests, relatedSTEP107tests in5.189s. Newfaults covertyped/genericactualcarrier,nonNull/wrongVARTYPE/unknownbinding0Load, sourcehash/handler/cache/carrier changes,attemptlocks, nativefirsterror vsrestore/closeerrors, QIunknown,sketch12/320strictfailure,root/modewatchdog. Static officialb312whole-module classcode proof passed;supportsPython3.14sliceconstants,typedconstants andexceptiontables. Logsstep-null-all-step-final.log/step-null-b312-static-source-selfcheck.json/help. No repeatedfullportable/nativeSuite.
- docs/step-null-import-data-candidate-plan.md providescompleteexecution/review/evidencecontract. Reportsourcefingerprints includenewhelper. Originalzero-import/publicreader/ownedharness/production/workflow unchanged. NoVM/CAD/CI/push/nativecallorbaselineexecution. Root must personally review exacthead and decide whetherconversionproof/currentbindingevidence sufficient; ifnative-memoryinspection orcross-runbranchidentity required, this doesnotclaimit and extra variable needsseparatereview. Official2025conditionalconflict remains unresolved, no repair/acceptance claim.

## 811bb97 first actual NULL candidate: unsupported original wrapper, zero Load; offline audit
- Root reviewed811bb97/37focusedtests and executedonce. OriginalreportSHA297e635248a9473ee3f27fb6c29d0f87ec1ab36c3033275c2a27ea67067ce352/sourcearchivea6bf3df44e81cf057d58b10f2205e9cce96838c20ed8134d51d16c158300e80e verified. Archive now COMPLETE424commitfiles/allbytes equal811bb97, not184runtime subset;7loadedcodehashes match. Seven originals copiedignoredwire-original-811bb97-01. New independentstdlibrun-pinnedaudit+machine+Chinese audit saved; no summarysubstitution.
- Firstfailure exact unsupportedwrapperclass; actualwin32com.client.CDispatch, nullbindingunknown/boundmethodattemptfalse;Loadnotattempted/return+errorsnull,geometryunavailable/null withNOraw/count. Actualfactory/QI/readonlyMaponce,true/false. Main181pairedcalls/onebindingerror,observation7pairedcalls/allend. ZeroLoad/CloseDoc/measure/save/new/select/export/retry. Fiveownedsets+reverse restoreverified/154reads18fullstages/full8originalequal. Inputbytes/metadataunchanged;SW7952/33.5.0,Exit/wait/handleclose/CoUonce,cleanup[]/nativebeforeafter[],no timeout.
- Static acquisitionchain: ownedharness importsdaemon.server.acquire_resident_app→passedclient.DispatchEx; b312DispatchEx→Dispatch→WrapDispatch defaultsWrapperClass=client.CDispatch in normalfallback, then dynamic.Dispatch(createClass). Actualwrapperconsistent;gencacheresultnotrecorded,notinvented. ClientCDispatch directlyinheritsdynamic andonlyoverridesreturnwrapping/dir,notloadbinding. Oldexactdynamicgate excludesnormaloriginalwrapper:diagnosticallowlistgap,NOTCADfailure/nullconversionoutcome.
- Root authorizes only preparation/tests/localcommit for EXACToriginalclient.CDispatch support withsource/runtime/MRO/inheritedhandlerproof, no broadisinstance/generated/customsupport/no rewrap/host/bindingforce. Keep8prefs/r/strictreference12/320/owned/600+1800,unknown0Load. NO VM/CI/push/replay; candidate forrootpersonalreview.

## Narrow support for original client.CDispatch prepared; review only
- Root authorizes preparation after811zeroLoadrefusal. Actualacquisition sourcechain confirmed:clientDispatchEx→Dispatch→WrapDispatch→normalclient.CDispatch fallback; preciseclassinheritsdynamic andonlydefinesreturnwrap/dir. Keeporiginalobject andmethodbinding, noforceInvoke/InvokeTypes/rewrap/host. Existingdiagnosticentry/sourceprofile/r/reader/ownedharness/production/YAML unchanged; onlybindinghelper+tests/docs changed.
- Additionalprehostproof: compileverifiedb312clientfullmodule inclfutureflags; actualtwoClientoverridesandthreefactoriescomparecode inclconstanttypes/exceptiontables. Exactclientclassmustdirectlyinheritdynamic/MROclient,dynamic,object;bindinghandlers/defaultlookup/goodobjecthelpersinheritedidentity, noLoadclassoverride. Newclientwrapper/factoryfingerprints inpackage, coreproofcheckedbeforehost. No broadisinstance/custom/generated/multipleinheritance support. Exactoriginalreceiver retained,clientreturnwrappingpolicyunchanged;validateMRO/handlers/factories/receiverclass/cache/instanceoverridesagainbeforecall. Unknownstill0Loadandterminal,noalternativecarrier/path.
- Newcaseproof wrapper_family/MRO/binding_handlers_inherited/return_wrapper_policy_preserved; originalargumentproofboundary remainsstaticconversion+actualbindingmetadata,notnative-memorymeasurement. Historical811neverresolvedactualLoadsignature/route,notretrofilled. Strictreference12/320/vector,8prefs/samefile/r/1factoryQIreadonlyMap/CASrestore/6001800/firsterror remain unchanged. No business repair claim; officialconditionalconflict unresolved.
- PASS18binding+28entry=46focused;relatedSTEP116tests in5.996s(step-client-all-step-final.log). New9cases coveroriginalclienttyped/generic/receiverpolicy,customMRO/subclass/handlerpolicyfactorychanges,unknown/nonNull0Loadterminal,receiverclass/defaultattributechange,fullrestoration/strictsketchandfirsterrorvsrestore. Officialfull-modulePythonclass/functionstaticproofPASS(step-client-b312-static-source-selfcheck.json),zeroCOM. 811audit rerun byte-identical. No repeated1909suite/native/VM/CI/push/replay. Newplan docs/step-null-client-wrapper-plan.md; exactnewhead forrootpersonalreview beforeanyexecution.

## 8c6cdc9 original-wrapper candidate: zero Load metadata refusal, offline audit
- Root reviewed8c/46tests and executedonce. ReportSHA926102eaab43af5f2051b9ed44f6de5ad73dcb8e30ea35f946845fcb160cc85b/archivec8258b64cc4a35252ba5090b21175c0ecb5261352e1580721ce4a726a66dcfae verified; complete428files/allbytes+7loadedhashes match8c. Originals copiedignoredwire-original-8c6cdc9-01. Existingofflineaudit supportsnewpinnedrun, 811oldoutputbyteidentical; machine+Chinese audit saved.
- Clientwrapper/MRO/inheritedpolicyproof passed, firstfailure no known method and no readable lazy metadata. ZeroLoad/boundattemptfalse/notattemptednullreturn+errors/geometryunavailablewithoutmeasure. Main181pairedcalls/onebindingerror,obs7pairs/allend;5ownedwrites/reverseverified/154reads18stages/full8originalrestore;inputunchanged;SW1384/33.5.0/ExitwaitcloseCoUonce/cleanup[]/nativebeforeafter[]. Notnullconversion/importfailure.
- Staticb312source can swallow constructorGetTypeInfo/GetTypeComp/MakeOleReprerrors; methodmap+lazyabsence cannotprove rawTypeInfoCount0 or exactcause. Oldstate/cache/propertymaps/nativeTypeInfowereNOTcaptured. OrdinaryunknowngetattrmayGetIDs thenzeroargInvokeprobe; gateavoidedLoadprobe. Factoryouteroperationcount1 isnotinventednativeInvoke count. NoFlagAsMethod/rewrap/InvokeTypespretendingoldbinding.
- Root supplement: no infinitehostdiagnostics/replay. PreparePython-onlyexistingstate snapshots andboundedreadonlymetadata evidence (unwired), then separatelynamedinstalled-TLBexplicitbinding+null scheme ifneeded; ACKTWOchangedvariables vs60f, notsingle-nullcause. Code/portabletests/localreview ONLY, noVM/CI/push/nativeexecution. Fixedowned/file/r/8prefs/strictreference12/320/onecall/nofallback/restoration unchanged.


## Installed-TLB explicit Invoke + NULL: separate TWO-variable preparation, local only
- Continued root supplement after0630c11 audit. New --installed-tlb-null-binding-candidate distinctly labels invocation binding AND ImportData changes versus60f; single_null_causal_claim=false/original_bound_method_used=false. No old binding proof invented, no8c replay, host rewrap/FlagAsMethod/InvokeTypes/fallback. Historical numeric/push replies rechecked:6d47766 already applied/pushed/tested; do not repeat old patch or dispatch.
- Before host: existing pinned libraries and b312 package/core/client proof; additionally pure-file installed Load4 declaration verification and three runtime return-helper source proofs. During case: exact original registered PyIDispatch, one direct GetIDsOfNames(0,LoadFile4)=int227 and unchanged Python maps; one explicit Generic Invoke227/LCID0/METHOD/resultwanted1 with fixedfile/r/VARIANT9None/original BYREFI4zero. Use original Python return policy. Actual raw returned/type persisted and pointer retained before wrapping; first conversion/native/wrapping refusal terminal, never retry. attempted flag is Python entry, not invented native boundary or memory proof; reviewed CPP source SHA not loaded-binary attestation.
- Python-only existing-state snapshot also records old gate refusal state without loosening it. Bounded read-only native metadata collector prepared with no Invoke and first-error stop, but UNWIRED: no repeated host diagnostics to establish historical TypeInfo state. Old8c raw report/archive/input re-audit PASS and output byte-identical.
- Same60f all8 vector/changed_from_60f=[]; fixed readonly input/r/onefactory+QI+readonlyMap observation only/oneLoad/strictreference12segments320mm vector/owned CAS+reverse restore/firsterror/6001800 remain. Distinct evidence parent and exclusive/child-forwarded mode. Production/originalreader/zero-import/ownedharness/workflows unchanged. Full source fingerprint set now10 files including new helpers and reviewed static parser.
- Verification PASS139 relatedSTEP tests in8.649s:18 oldbinding+34 entry+17 newexplicit/observation+70 others. Covers original map/lazy missing without fill or getattr, null+BYREFcarrier, wrong/unknown ID zeroLoad, pointer/helper/carrier/contract drift and terminal refusals, same5writes/reverse8restore, native firsterror vsrestore/close, strictsketch12/320 and wronglength rejection, boundedmetadata/unknownTypes/firstfailure/noInvoke, mode/deadline. Full-module b312 source class/function static proof and actual pinned local TLB parse PASS; bad TLB hash refusal covered. Logsstep-installed-all-step.log,step-installed-b312-static-source-selfcheck.json,step-installed-tlb-static-contract.json/help in ignored evidence. No repeated fullportable/native suite.
- Plan docs/step-installed-explicit-null-candidate-plan.md gives source/conversion/evidence limits and exact preserved scope. Code/tests/local Chinese commit ONLY; NO VM/CAD/CI/push/native calls, baseline replay, defaultcheckout/main/rebase/merge/release. Root personal exact-head review chooses whether two-variable evidence merits one execution later; no automatic public acceptance. Official conditional conflict and actual reference-curve/native8-file acceptance remain unproven.

## 459ff87 first actual explicit Invoke: immutable failure audit, no native replay
- Root personally reviewed69focused tests and executednewTWO-variable modeonce. Independent pinned audit confirms report26f7be0f5515781db1cc043c1ddd918aac69f03c6d2eff929b0d6c3d21b7eb7d/archiveebf7de18971cdae3236db6236ba73d70e0dd1eb415c091ed2d07ddfaa63b6427; complete434commitfiles/allbytes and10loadedhashes match. Nine originals copiedignoredwire-original-459ff87-01; new stdlibaudit/machine/Chinese record saved.
- ExactGetIDs227,explicitVARIANT9None,Pythonmapsunchanged,lazykeypresentNone,rawPyIDispatchreturned/originalreturnpolicycompleted;Loadpart/errors0/catalog1. Still2x3DProfileFeature IDs17/18 each6segments,12/320/vector;strictreferencefirsterror,completefalse/geometryunavailable/null retained. Main196pairedcalls/oneerror,obs109pairsallend;GetSketchSegments2/GetLength12. NoSave/reopen/featureerror-code evidence and noacceptance; two changes prohibit single-nullcausality.
- 5ownedsets/reverseverified,162reads19fullstages/same60f8originalrestore;input10595bytes/SHA/allmetadataunchanged;ownedSW4404/33.5.0/CloseExitwaitcloseCoUonce/cleanup[]/prepostnative[]. NoCAD/VM/CI/push/replay this audit.
- Root supplement confirms b363 forcedreference is test-only choice after real9/260 sketch loss, notpublic product export representation contract. Next prepare separately named explicit officialAsSketches0 observer candidate with strict type/error/full12/18vector/save-readonlyreopen/hash/state/CAS/owned guards; no arbitrary fallback or oldfailurepromotion, mustlaterfresh8filepublicacceptance. Code/portabletests only beforepersonalreview, no native/CI.

## Explicit AsSketches0 observer boundary candidate after root review direction; not enabled
- Root personally confirmed b363 reference requirement was test-only strategy after d650 true9/260 loss, notpublicSTEPexportcontract. Read-only investigation pins actualschema/exportadapter, b363diff, oldee7publicZIP/report8/8 and d650originalZIP/partial9/260; installed2025export/IFeature/ISketchhelp re-extracted/hashmanifest saved. Oldreader measuredsketchtypes but didnotrecordfeaturehealth/grouping; neverretrofill them. Research+plan docs/step-sketch-observer-contract-and-candidate.md/machinerecord saved.
- Review-only --sketch-readback-candidate defaultoff and --export-report-only; exactcurrentGITHUB_SHA/freshsuccessfulwriter/cleanup[]/6CLI+SDK+MCP8uniqueorderedreceipts required, nativeWindows/hiddenowned/rev33.5.0. Existing reference/defaultreader/assertion body, originalsingle-importdiagnostics, production/writer/YAML untouched. Generic optional read callback preserves all existing save/reopen code; no459binding/nullexperiment copied.
- Newhelper full8typedCAS/eachsetter/fullreadback/beforeLoad, GeneralF/T/T+officialAsSketch0, Neutral/Step4unchanged; partialsetterownedattemptrestore/reverse/thirdvalueguards/firsterrorseparate/restorefailureclearscasegreen. StrictknownISketchtypes+boundedmetadatawhitelist; no reference/mixed/unknownfallback, exacttop/subIDgraph, GetErrorCode2(BYREFBOOL) preciseint0 beforesegments, rejectwarnings/unknown/empty. Full12/18vectors320/560/originalthresholds bothbefore+afterSave/reopen; saveactualerrors0/warningsNonepreserved/read_onlyclean/native+STEPhash/physicalsolidchecks allretained. Feature API is notdocumentedallinternalerrors, soexactgeometryremainsrequired.
- FinalPASS24newcandidate tests included in163relatedSTEP in7.916s, includingall139old; nativeDocumentCount property/method shape regression added. Faults coverwrongenum/CAS/partial/restore/foreign/nongreen,9/260/missingdiagonals/NaN/typefallback/cycles/errorcode/warning/unknown,readonlyreopenlengthhealthandhashdrift/saveimporterrors,oldhead/7of8/duplicatepath,non-native/parentflag1800. Logsstep-sketch-candidate-focused.log/step-sketch-all-step.log. No unrelatedfullsuite replay.
- This is localpreparedsourceonly, NO VM/CAD/CI/push/replay, no defaultmodepromotion ornewCIinput. Root personallyreviews exactcommit beforechoosing freshnative8filepublicacceptance onnewhead; 459strictreferencefailure permanent/notgreen; noAs3DCurvesfixclaim orsingle-nullcausality. No productionSTEPguard/schema/source-state/lease/CAS/ownedcleanup relaxation.

## Reviewed sketch observer: minimal existing-public CI wiring only
- Coordinator personally reviewed b55 helper/reader/contract and reran24candidate tests, accepted explicitAsSketches0 as observer-boundary repair. Authorized localCIwiring only, NOdispatch/VM; coordinator will personally review exactnewhead and inspectqueue before one fresh8filepublicCI.
- ci.yml changes exactlyONEaddedargumentline --sketch-readback-candidate in existing step_public_readback/native_step_public_targeted command. Removing thatline makes entireworkflow BYTEIDENTICAL to b55; duplicate-safe parsedworkflow alsoequal. No newinputs/PRentry/defaults/guards/timeout/concurrency/nativegeometry/CAS/hostchanges. Internal/oldoriginaldiagnostic/defaultreference routes unchanged; no sourceproduction/reader/helper changes this turn.
- Newwiring regression proves soleflag/publicwriter-matchingguard/samecontinuedPowerShellcommand/freshpublicreportpaths/31min/throwonfailure, absent fromwriter/internal/originaldiagnostic. Focused4workflow tests PASS including13824selectorcombinations. AllrelatedSTEP164tests PASS in7.549s, logstep-sketch-ci-all-step.log. actionlint1.7.12 PASS/exit0; PyYAML6.0.3 duplicate-key rejection/9existinginputs/publicdefaultfalse/sole-line byte+AST equality PASS; Pythoncompile/CLIhelp/gitdiffcheck PASS. NativePowerShell notexecuted; argumentcontinuationstructure checkedportably.
- AllfailedoriginalZIP/report/evidence retained untouched; no oldreport reuse, nativeacceptanceclaim orAs3DCurvesfixclaim. OnlylocalChinesecommit and exactheadhandoff; NOpush/dispatch/queueorVMconnection/resourceassignment changes. Nextaction requires coordinator personalreview and explicitone-new-eight-filepublicCI scheduling.

## Public43102613261 fixed-original audit before combination repair
- Coordinator supplied terminalfailure/artifact13895175070/originalZIP SHA6b69d6b9671b9af4fd2220552d6d8b2939a706ac38181acc109aef00717cba18/jobSHA c3ee4025692d2c0d8dcb748f9ab98a84fe308583974529c88a8c7f0cc8af4f0a. Independent localonlyaudit verifiesAPIrun/headf56f792/ZIP/105expandedmembers/reports/all8rawSTEPdigests/sourcehash/8nativeSaveAs3pairs. Fulloriginal copiedignoredpublic-original-43102613261; wrongZIPrefusalPASS. No newquery/download/native/CI.
- Correctfirstfailure: readercase0 AP203solid SUCCESS withLoadmodel/errors0/physicalmetrics/native46785Bhash/saveerrors0 warningsnull/ROreopenerrorswarnings0 clean andsecondmetrics. case1 AP203wire LoadNone/errors1 beforeanygeometry; planned8/started2/completed1/remain6unattempted. Factorynonnull/QItrue/Mapfalse/typeinfocount0. Wire raw12/320 notnativecount; noGetSketchSegments/GetLength/featurehealth. Do notmislabelsolidfailure orsketchassertionfailure.
- BothcasesGeneralF/T/T/AsSketch0+NeutraloriginalF/0 preserved, full8CAS/readback/only2ownedwritesreverseverified;88reads11stages and80reads10stages,original8restored. Main238pairs/obs37pairs/noerrorrows; businessreturnguardafterLoadfailedstrictly. Ownedreader5980 vswriter1232/rev33.5.0/ExitwaitcloseCoUonce/cleanup[]; no globalPIDinventory fabricated. Headreceiptsstrongbutno loadedsource-bytemanifest inartifact.
- Root asks minimal separately preselected explicitNULL+reviewedsketchobserver candidate, notfactoryfailurefallback/retry, nopreferencegrid orassertionrelaxation; all8/r/owned/6001800/strictgeometry/health/saveROreopen/hash remain. Prior459 localdifferentprofile+doublevariables cannotcausallysettlehostederrors1. Preparecode/tests forpersonalreview only; noVM (allocatedGLB), noCI/push/replay/oldreportpromotion.

## Preselected explicit NULL + reviewed sketch observer: minimal combination prepared, review only
- After immutablebcb6196 audit, root requested onlynewpreselectedNULL+reviewedAsSketch0 combination, nofailurefallback orassertionchange. Separate --null-sketch-readback-candidate mutuallyexclusivewitholdfactory/sketchflag/export-report-only, distinctdiagnosticname. ExistingpublicCIparameterreplacement included asreviewablecode only: newflag→oldflag makeswholeworkflowbyteidenticalf56; nonewinputs/guards/timeouts/defaults/PR/concurrency. NOpush/dispatch/VM; rootpersonallyreviews first.
- Prehostexactpywin32312/source/runtime/core/client/factory/returnproof plusinstalledTLBpinnedABI; sixsourcefilehashes/proofJSON. Eachcase1factory/QIMapreadonlyobservation, neveractualfactoryImportData. Reuse459exactexistingPyIDispatch/returnpolicy/oneGetIDs227/mapsunchanged/VARIANT9None+BYREFI4zero/oneGenericInvoke/r. Before+afterbindingfilehash andfull8CAS; currentf56completeAsSketchprofilefixedF/T/T/T/F/F/0/0 orzeroLoadrefusal, noNeutralwrites orparametergrid. Changedvariablesbinding+ImportData relativef56, no single-nullcausalclaim. Old459defaultbaseline/oldfactory/refdiagnosticbehavior preserved.
- BaseoptionalLoadcallbackandexistingreadbackcallback carryactualresult tosameownedcleanup/save/ROreopen; strictint0/importpart/type/health/12or18vector/physicalmetrics/allsamebounds/hashes/CAS/thirdvalue/firsterror/restorefailure-nongreen/6001800 remain. NullNone/errors1 stillfails; nooriginalgetattrLoad/InvokeTypes/rewrap/fallback/retry. Packageorunknownsignaturefailsbeforehost; unknownpercasebinding/profileretainsfirstevidence/restoresowned.
- PASS10newcombinationtests and174allSTEP in8.290s, including164old. Newtestscoverall3geometryroundtrips/nullcarrier+singleInvoke/sourceprofileexact/oldfactorynotused/Noneerrors1noSave/noFallback/wrongID0native/health+reopenlength strict/prehostversion/signature/modeexclusivity/newfresh8/supervisor. Staticfullb312sourceclassandactualpinnedTLBpreflightPASS zeroCOM; actionlint1.7.12/YAMLduplicates+soleparambyteproof/Pythoncompile/CLIhelp/diffPASS. Frozen431audit rerun byteidentical. Logsstep-null-sketch-all-step-final.log/static-preflight.json/wiring-check.json/help; nofullsuite/no targetrun.
- docs/step-null-sketch-combination-candidate.md givesexplicitrecipe/evidencebounds. ThiscandidatehasNOTprovedCIrootcause orNULLsuccessfornew8outputs; 459 differentenv/profile+twovariables cannotbe substituted. Old431 firstsolidpass/secondwirefailure/originalZIP permanent. Rootreviewexactnewhead+queue andauthorizeonefreshpublicCI later; WindowsVM remainsotherlane-owned anduntouched.

## 43217223437 original explicit-NULL failure and three-input comparison, offline only
- Root supplied nativeartifact13944637284/ZIP5aaf00aaf391020b21029106b1dcad9bfe0409b6e30a21f2b821c527fda0f8cd/job7b3e89477dc08d9eda912b77f55f79b93d8ededb18b446675a9ab07318fcc578. Independentpurefileaudit pinshead e039/API/106members/reports/raw8outputs/8nativeexports/sourcehash and firstsolidcomplete/secondwireNoneerrors1. Bothcasesexplicit227/VARIANT9None/mapsunchanged/originalreturnpolicycompleted, nofactoryargument. CurrentCI NULL is therefore insufficient underthisprofile; doNOTretryNULLunchanged.
- Sourceproofsixhashes match e039 fullCRLFcheckout reconstruction, NOTGitLFrawhash equality; noDLLmemoryclaim. Full8/CAS/restorationreadjournals96/12and88/11,owned5580vswriter7208/33.5.0/cleanup[]/ExitwaitcloseCoU. No nativewiregeometry/health/save; no globalPIDinventory invented. Originalfullcopyignoredpublic-original-43217223437, wrongZIPrefusalPASS; prior431 preserved.
- New comparison script pins459/f56/e039reportSHA+wireSHA andactualCAS. f56=e039all8;459diffsNeutralFreeTruevsFalse AND GeneralCurve1vs0 AND NeutralCurve1vs0. ThreeAP203wirebytes10595/10590/10600 differ, but entitycounts/SImm/12linearcurves/320/endpointgraph and per-edgeknot/multiplicity/orderedcontrols allsame. Notbyteequality/fullEXPRESS/nativeacceptance; donotclaimparametersdiffer frommerefirstentityorder.
- Re-extracted2025swconstCHM confirmsNeutralFreebool isdocumentedSTEP/IGES/ACIS freecurves+points-as-sketch entityselector;GeneralFreevalid3DIoff+GeneralCurve. NoformalGeneral/Neutralpriorityproof. Onlynextpreferencehypothesis: relativee039 changeNeutralFreefalse→true, bothcurveenumsstay0/NULLr8CAShealthgeometrysaveROhashowned6001800unchanged. Not459causalityproof orparametergrid; preselectbeforeonecall, nofallback. Audit+comparison+officialsource machine records andChinese doc saved. NOCI/VM/CAD/push/networkstatus/download this round.

## Single NeutralFree=true candidate over audited e039, local preparation only
- Root asked onlyoneevidence-backedpreferencecandidate, particularlyNeutralFree. New --neutral-free-null-sketch-candidate preselects ONLYNeutralFreefalse→true overactuale0398vector; curveenumsboth0 andsame227/NULL/r/binding/returnsource stay. OriginalfalseNULLmode andfactory/sketch modes retained/exclusive, noerrorfallback orNULLretry. Newouterevidencecomparisone039/changedvariablesonlyNeutral; innerbindinghistoricalf56comparison remainsaccurate, nosingle-nullcausality.
- NewNeutral setterjoins existingfull8typedCAS/VOIDcheckedwrite/fullreadback/ownedattemptjournal/reverserestore/thirdvalueandunknownprotection. Completeexpectedprofilemustmatche039plusNeutralTruebeforeanysetter; changed_from_e039 exactlyonekey, noenumorotherNeutralwrites/grid. Allhealth/12or18/fullvectors/physicalmetrics/saveROreopen/hashes/nativeWindows33.5/owned/firsterror/6001800 retained. ExistingpublicCIonlyreplacescandidateflag; replacingitback makesworkflowbyteidenticale039, inputs/guards/limitsunchanged.
- PASS9newcandidateand183allSTEP in9.585s, including174oldand13824selectors. CoverssameNULLsingleInvoke/all3geometryroundtrips/onefield/correctrestore, Noneerrors1stillfails/partialNeutralsetter/restorefailure-nongreen-firsterror/unknowncleanupnooverwrite/otherprofiledrift0writes/healthvectorhash/mode/supervisor/fresh8/prehost/soleCIarg. Directactionlint1.7.12exit0, duplicate-safeYAML/soleargbyteproof/Pythoncompile/help/diffPASS. Fullb312staticclasses+actualpinnedTLBpreflightnewmodePASS zeroCOM. Both431 and432audits rerun byteidentical; originals retained. Logsstep-neutral-free-all-step.log/static-preflight.json/wiring-check/help.
- docs/step-neutral-free-null-candidate.md explicitlyunexecuted/noGeneral-Neutralprecedenceproof/no459singlecause/nooldreportgreen. Sourceprep+localcommitONLY, NOCI/VM/CAD/push/native/container/oldrunquery. Rootpersonalexactheadreview beforeanyboundednewnativeacceptance; previouspublicsolidpasses/failedwirefacts immutable.


## STEP 统筹合并审查（2026-11-13）

- 422a123 / 43299699392 的 8 个公共 STEP 输出与 8 次唯一导入、原生保存、只读重开已独立严核，原件及失败历史均保留。见 docs/step-public-43299699392-acceptance.md。
- 原生能力限定为 Windows 2025 SP5 owned hidden 零件；原生专项通过不等于 main 整套通过，也不等于现代 API/GLB 迁移通过。
- 合并保留 main 现有 STL、单位、字体、表格、拓扑和 MCP/SDK；专项公共验证入口 step-export.yml 不新增 main 手动参数。历史原件诊断 CI 定义作为只读证据归档，不再加入 main 的手动菜单。
- 本系列未发布；GLB/旧 API/配合等现有未完成项仍需闭环，发布前由用户最终确认。

## 2026-11-15：主线基线上的active assembly全目标readonly候选

- 新持久worktree `/Users/YJBeetle/.codex/worktrees/swcli-assembly-mates-active/SWCLI`，branch codex/swcli-assembly-mates-active，精确origin/main31ad9c2起点；新worktree admin SWCLI20/config.worktree独立core.worktree绝对路径，未改shared/global或旧SWCLI12/mainSWCLI16。旧诊断分支c63c213和evidence保留，33/31有限证据复制JSON/MD，原件hash已复核。
- 不整体带回旧src/schema/daemon/SDK/校准写开关。仅新增私有完整targets observer、root-owned同STA readonly入口及两份测试；existing main source零改。每面原GetCorresponding→ASM typed reference→resolved IEntity唯一GetComponent非空+精确owner强证明，后台在实体/owner访问前AssemblyNotActive；两组件全部面成功与所有后置通过才返回私有bindings，不发token/CAS/write。
- 86关联测试通过，日志 /private/tmp/swcli-active-target-census-related-20261115.log；源码AST/diff检查通过。完整Git源码513项manifest SHA `997131942ca450239694c0db42eed3ffa81622fa1369ed96ad7dd03505d770f1`，提交后逐Git blob核验；全readonly原生尚未运行。
- 前台公共能力/typed句柄与CAS/写save-reopen三阶段设计见 assembly-mates-active-public-stages-2026-11-15.md，具体只读门禁见active-census-proposal；root外部owned parent/supervisor和600/1800需另审冻结，reader不创建资源。无VM/COM/CAD/CI/push/包/grant/main合并。

## 2026-11-15：新候选配置读取改现代属性链

- root亲审f379发现新configuration helper沿用了弃用GetActiveConfiguration；本次仅新候选改为ConfigurationManager.ActiveConfiguration.Name，保留names/count=1与严格值/缺失保护，属性错误原样停止且无旧API fallback。旧getter在fake中调用即失败，完整census/后置及无效配置/原异常反例通过。main已有windows_documents等旧调用不纳入范围。
- 88项相关通过，日志 /private/tmp/swcli-active-target-modern-configuration-related-20261115.log；AST与Python3.9/diff通过。513项新manifest SHA `e21fa957d3d5cfbb2a3d1f9ee308cbb2ba3144964d02590a577e48f61f0549c3`；旧9971319原字节保存f379023-original。未VM/CI/native33重跑。另已获root明确授权下一独立逻辑提交准备最小私有外层adapter，仍无执行授权。

## 2026-11-15：私有完整census外层adapter离线准备

- root明确授权后新增run-active-assembly-target-census.py及外层测试；按函数粒度来源收据复用b2e的Journal/clock/nested/held-exit基础，不导入旧mate产品或旧observer/runtime。当前main工厂/capture terminate_right=False；manager1840零COM、supervisor600/1800零COM、parent唯一STA/自然PRT→ASM/新reader一次/normal owned cleanup。
- 原始身份在准入前持久化，strict typed OpenDoc flags/warnings和same STA；deadline后只exact拥有Python，不kill CAD/不加CAD预算。所有原始/next-clock样本、completed-span600/终态完整trace、严格held rawexit和unknown None保留，report/trace/files次错及必要COM释放/traceback GC有反例。两层异步持久mirror和逐fileSHA收据，未知copy不成功。
- 110相关通过（adapter22+census/reader30+main58），日志 /private/tmp/swcli-active-target-adapter-related-20261115.log；AST/Python3.9/diff通过。新完整515项manifest SHA `a67792386c45ca0c9eb5dc11fe2e9850f16c45c2cee04963878379a17e5ea219`，旧现代cfg e21fa原字节保留，符号级来源原件SHA见adapter-provenance JSON。提交后逐Git blob核验。
- 仅本地代码/测试/文档/中文提交，无VM/COM/CAD/CI/push/包/grant或native33重跑；root亲审最终head后统一打包/排期。公共typed句柄/CAS/配合写与保存重开仍未实现/未验证，原31/33有限证据不改。
