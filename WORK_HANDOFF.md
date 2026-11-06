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
