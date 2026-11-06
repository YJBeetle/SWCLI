# 文档属性校准性能：当前接管与验收边界

工作树：`/Users/YJBeetle/.codex/worktrees/docprops-calibration-performance/SWCLI`
分支：`codex/docprops-calibration-performance`
基线：`1593330e6e757073d44c5bb9a04dc06deca10966`（parent `3bda2c00489dde6a3d1e4521c548f751b1d1c197`），仅批次本地 checkpoint，不是已发布/已验收版本。

## 范围与保护

接管 HANDOFF.md 中两个未提交文件，完成报告 revision 缓存、wrapper/预持久化/function body 计时拆分、每 checkpoint 的严格 native identity 双射。所有原生调用前仍 checkpoint；嵌套 row/list/dict 写点在赋值完成后提升 revision，保留原始 alias；显式 persist 仍强制完整观察/byte cache，replace 成功前不推进缓存。

没有跨 checkpoint 缓存原文档、前台、上下文或状态。每次 fresh GetDocuments/GetDocumentCount；先证明 expected 原生身份互异，再消耗 actual 匹配；重复 expected/actual、missing/foreign 均拒绝。原生身份仍由 IsSame 判断，不由 Python identity/title 替代。

新增计时中的 `elapsed_seconds` 保持原保守 wrapper 预算含义；`begin_trace_seconds`、`checkpoint_seconds`、`native_seconds` 分开。native_seconds 仅 function body，可能是多 COM SDK helper，不能全称纯 COM。计时不含 terminal trace 自身 fsync；begin/terminal 仍各 fsync。600/1800、首次失败、预原生持久化、部分 mutation 回执、几何/只读/身份/前台断言不放宽；没有原生重试、失败回滚或组内 host 重启。

不操作本地 Windows VM，不更改 DockerSW/MacSW、main、版本或空标准白名单，不合并其他未验收分支，不发布。

## 已完成 portable（非原生校准/非公开验收）

- `PYTHONPATH=src /private/tmp/swcli-a14-test-env/bin/python -m unittest discover -s tests -p 'test_document_properties_calibration*.py'`：107 tests 通过。新增 fault/permutation/count/CI 接线测试。
- 全仓 `python -m unittest discover -s tests`：2101 tests，84.096s，OK，skipped=32（环境条件），原件 `evidence/docprops-performance/full-tests.log`。
- `actionlint v1.7.12 -shellcheck= .github/workflows/ci.yml`：exit 0；PyYAML parse 通过；`git diff --check` 通过。
- 新脚本 `scripts/dev/benchmark-document-properties-calibration.py` 可重现计量：605840-byte synthetic report、250 unchanged read calls，原 pre-call 模式 dumps=250；revision 模式 dumps=0。报告原件 SHA 相同。稳定4对象比较16→10，全部24目录排列及重复/foreign故障矩阵通过。原件 `evidence/docprops-performance/portable-benchmark.json`，明确关闭 trace fsync，只是 portable CPU/count，不是 Windows 加速倍数。
- 预 persist replace 故障：只一次 replace、零 native、revision/bytes cache 不前进；native 原因遇次生 I/O 不被覆盖；嵌套 alias/读值在下一原生调用前 durable；AST 保守审计全部 subscript/container mutation 写点，防漏 invalidation。

## GitHub Windows 内部校准设计

已有 `ci.yml` 加默认关闭 `docprops_calibration` 与必需 exact `docprops_expected_head`，仅 `workflow_dispatch` + 本仓库 + 此分支 + `expected_head == github.sha == checkout HEAD` + `native_full=false` 才执行。校验在首个私有输入前；checkout `persist-credentials:false`。本分支 push/定向 dispatch 跳过无关 test/package/native full/release，避免占用无关完整 CI。

复用现有安装/私有 runtime；首 run 因同名全仓 concurrency 被排队替换取消，相关修复后改为本路专用 concurrency（见后节）。新增 `verify-document-properties-calibration.py` 复用 owned harness：仅新 host，require owned，捕获 process handle，设置本 owned 实例 UserControl=True（在 calibrator baseline 前），持有 STA 并 pump 等待 hardened driver。driver 在独立线程仅管自己 Popen worker，nonce/argv/exe/PID/-I -S 授权不变。finally 仍只 ExitApp owned + wait captured handle；cleanup 脚本新增显式 `-PrivateInputsOnly`，此路径不全局终止 SOLIDWORKS/daemon，仅清除私有输入/服务/挂载；原完整 CI 的默认行为未变。

本次选择**原单组完整36转换**（part/assembly/drawing各12，含每次保存、RO重开及profile/几何断言），仍1800秒，不是拆组。wrapper 对报告进行再次完整性拒绝检查，R4样式30 setter/29 roundtrip、profile漂移、重复setter、cleanup失败均不能成功。新原件生成 source/head/run/attempt/hash manifest，公开 artifact 仅本run校准输出，不上传私有配置/安装日志。

官方 API 已核实：
- [ISldWorks.UserControl（官方2024，true让应用可见并由用户控制）](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControl.html)
- [ISldWorks.IsSame（官方2021，返回 swObjectEquality）](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~IsSame.html)
- [ISldWorks.GetDocumentCount（官方2025）](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~GetDocumentCount.html)

2025 UserControl/IsSame直链在检索工具不可访问，使用可访问官方版本交叉核实；此次不更改这些既有 COM API 的生产实现，安装 TLB 仍须动态读取/核对全部所需常量。

## 历史失败与未完成边界

R4 原生整组1800秒超时：30 setter True，29完整保存/只读重开；不是标准校准通过。原始持久证据见历史 HANDOFF.md 与 `/Users/YJBeetle/.codex/task-artifacts/docprops-calibration-performance`。既有字体/显示诊断不重跑。

当前尚无本优化 head 的 Windows 成功证据。后续仅触发一次对应 head 定向校准；若失败先下载原 artifact、核 hash/第一真实失败，只有相关修复后才启动新验证。内部校准即使通过，也不是本批六个公开写接口（lease/expected_update_stamp/完整CAS/保护/partial receipt）的公开验收；空白名单保持 fail closed。

## 提交与 CI

实现提交、远端 head、dispatch 参数、run URL、原件/hash/第一失败会在此节追加。当前不创建 PR、不合 main、不发布。

## 主集成汇总字段（15路统筹）

- 新公开 operation / CLI / request-result schema：**无**；本路只改内部诊断/计量/CI，不新增协议或 SDK 参数。标准生产 whitelist 仍空。
- 内部 CLI：`scripts/dev/benchmark-document-properties-calibration.py --output ...`；`scripts/ci/verify-document-properties-calibration.py --expected-head <sha> [--check-context | --output-dir ... --swconst ... --drawing-template ...]`。
- trace 新字段：`begin_trace_seconds`、`checkpoint_seconds`、`native_seconds`（pre-native失败为null）、`native_started`、`native_completed`、`timing_scope`；旧 `elapsed_seconds` 保留。report revision 是进程内缓存，不是公共 schema。
- 共享文件修改：`.github/workflows/ci.yml`（专属 opt-in job/input，portable job branch guard）、`scripts/ci/windows/cleanup-hosted-solidworks.ps1`（可选 PrivateInputsOnly，原默认保留）、`scripts/dev/calibrate-document-properties.py`、既有校准测试一行 invalidation。其余新增脚本/测试/证据/交接文件；生产 src/schema/SDK 不改。
- 依赖：继承批次 checkpoint 的 fixed drafting-defaults-v1 reader、hardened driver 与 owned harness。最终 workflow 共享冲突由主集成处理；本路不读写其他 worktree、不等待其他分支。

- 实现已提交并推送：`81c32732a07ca0459c82955d2314e81ad2323857`；独立分支首次推送成功。提交标记 `[skip ci]` 避免无关 push CI。后续仅文档/receipt更新；实际绑定 head/run 见本目录持久 `evidence/docprops-performance/dispatch.json`（触发后生成）。

### 第一次独立 Windows dispatch（已接受，正在等待，非失败）

- 原生 source/head：`dabb91a3ba14c01013754307f9b73b334ee3188a`（实现提交 `81c32732a07ca0459c82955d2314e81ad2323857` + 交接文档）。
- [run 42260761081](https://github.com/YJBeetle/SWCLI/actions/runs/42260761081)，attempt 1，job `128039761043`；2026-11-07 01:20:39 Asia/Shanghai 创建。首次查询 pending；未重复 dispatch。
- 参数：`docprops_calibration=true`、`docprops_expected_head=dabb91a3ba14c01013754307f9b73b334ee3188a`、`native_full=false`；其余安装配置使用既有默认。
- 仅 Internal owned standards-36 performance calibration 待执行，portable/package/full/tag/release 全部 skipped。专用 job 使用现有 `swcli-hosted-windows-solidworks` concurrency；排队不代表失败，不保证15路同时执行。
- 当前无原生成功/失败产物；完整 Windows 36转换与本批公开验收仍未完成。

### 首次运行结论与相关修复

run 42260761081 / attempt 1 已 completed/cancelled，未分配 runner（runner_name空）、steps=[]，artifacts=[]，**零原生执行证据**。GitHub check annotation 原文：`Canceling since a higher priority waiting request for swcli-hosted-windows-solidworks exists`。不能归为标准 setter 失败、原生超时或校准通过。原始 run/job/check/annotations/artifacts JSON 及 SHA256 已存 `evidence/docprops-performance/run-42260761081-*`。

这证明全仓共享 concurrency 的单个 pending 槽会让独立线程互相取代。只修本路 job group 为 `swcli-docprops-performance-windows-${{ github.ref }}`，保留 cancel-in-progress=false；原完整 native job 的 group 不变。不同 hosted runner 不共享本地 owned host/runtime，实际并发仍受 GitHub 配额约束；不操作其他 run。接线回归/actionlint 再通过后才对新 head 发起新验证，不重试旧 head、不复跑原生 API。

### 相关修复后的新 head / 新验证

- `1c57948b7a22fb930bce5f5f3c0ef6b303a66034`：隔离本路 concurrency，附首 run 原件，已提交推送。
- 修复后的 CI portable 接线10 tests全过（0.031s），actionlint exit0；原 calibration/driver/生产源码未再改动，不需要重复 unrelated full CI。
- [run 42261401694](https://github.com/YJBeetle/SWCLI/actions/runs/42261401694)，attempt1，绑定 `1c57948b7a22fb930bce5f5f3c0ef6b303a66034`；2026-11-07 01:24:46 Asia/Shanghai 发起此 head 唯一一次 dispatch。
- 参数仍 `docprops_calibration=true`、`docprops_expected_head=1c57948b7a22fb930bce5f5f3c0ef6b303a66034`、`native_full=false`。完整回执 `evidence/docprops-performance/dispatch-r2.json`。这是相关队列修复后的新验证，不是重试旧 head 或原生 API。
- 等待当前 run；没有重新启动/使用本地 VM，没有对其他分支操作。

## 安装等待期间的离线核验准备

新增独立 `scripts/dev/audit-document-properties-calibration.py`（不在正在运行的1c57948原生源码中）：对下载原件 manifest/source/head/run/hash 做完整核对；报告计数必须与 trace 的36次 setter 和216次固定profile读取交叉一致；分开汇总 wrapper/begin trace/checkpoint/function body。缺失/篡改/额外原件、source/head漂移、不完整trace或29轮回读不能升格成功。新增5项 portable synthetic fault tests通过（含 Windows Git LF/CRLF 的明确预期源码字节哈希比对；原件字节不作归一化），原件 `offline-audit-tests.log`。这不改原生实现/白名单，不重新触发正在运行的校准。

最新主统筹要求已接收：内部校准后继续对应公开CLI/daemon/SDK/MCP契约验收；只有独立核原artifact/head/digest/trace/save-reopen且公开验证完成的精确范围才可merge-ready。本路当前仍在安装准备，不宣称完成；不得因本路只是性能优化而把空白名单/内部诊断当公共验收。

### R2 实际失败与独立核原件（不是性能/标准写失败）

[run 42261401694](https://github.com/YJBeetle/SWCLI/actions/runs/42261401694) attempt1 已 failure；安装与 runtime 成功。标准组只运行0.673秒，**0 cases、0 setter**。首真实原因是 `ROT exact PID moniker must match exactly once; no object bound`：owned SW PID 6608 / revision 33.5.0，仅枚举到 GUID moniker，缺少 `SolidWorks_PID_6608`，binding_attempted=false。没有回退绑定 GUID、没有 GetActiveObject 或 native retry。

- 原 artifact ID `13526632475`，ZIP SHA256 `e057d905a1e0887d89d429eed7319455a7e5608c060b584eef231436ce90cb40`，与 GitHub digest 相同，metadata head=`1c57948b7a22fb930bce5f5f3c0ef6b303a66034`。
- 原件持久保留在本 worktree `evidence/docprops-performance/run-42261401694-original.zip` 和 `run-42261401694-original/`（仅忽略 Git 索引，不删除、不依赖/tmp）。对应4文件 source snapshot `run-42261401694-source/` 由精确 git head 导出。
- `run-42261401694-audit.json`：全部原件hash和head/run/worker验证通过；Windows源码确为 git-CRLF，明确比对预期字节哈希，不归一化原件；native_group_complete=false，public_whitelist_updates=[]。原metadata/audit/首因摘要入Git；原ZIP和提取文件原样留存。

### R2 相关修复：只为 owned CI 使用显式 COM 接口传递

原手动 PID/ROT 路径不放宽。新 owned-only 路径使用父 STA 已确认 owned 的接口 `CoMarshalInterface(IID_IDispatch, MSHCTX_LOCAL, MSHLFLAGS_TABLESTRONG)`，只在 hardened worker 身份授权成功后经该 Popen 私有 stdin 发送，child 单次 `CoUnmarshalInterface` 后仍严格核 native PID。capability bytes 不写 argv/config/report/trace/文件/日志。nonce/exe/argv/size/parentPID 授权、-I -S、原生600/组1800和单个Popen终止规则保留；管道短写不重试，错误 fail closed。

父 STA 持续 pump；TABLESTRONG packet 在原 STA 的 finally 单次 CoReleaseMarshalData，不管 worker 拒绝/退出/被 watchdog 终止。次生释放错误不覆盖原 worker 原因，也不能成功；完整报告额外要求 owned binding/PID/传输成功，独立audit要求marshal释放及ExitApp/WaitForOwnedProcess/handle/COM清理的完整trace。不是任意 ROT moniker 回退，也不新增公共API。

官方依据（已核实接口签名、LOCAL跨进程与TABLESTRONG释放规则）：
- [Microsoft CoMarshalInterface](https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-comarshalinterface)
- [Microsoft MSHLFLAGS](https://learn.microsoft.com/en-us/windows/win32/api/wtypesbase/ne-wtypesbase-mshlflags)
- [Microsoft CoReleaseMarshalData（须原 apartment）](https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-coreleasemarshaldata)
- [pywin32 官方 PythonCOM.cpp 签名](https://github.com/mhammond/pywin32/blob/main/com/win32com/src/PythonCOM.cpp)

本修复关联121 tests通过（含9项新的owned/管道故障），完整便携2115 tests / 70.291秒 / skipped32，均OK。新增独立 `owned-interface-portable-benchmark.json` 仍证实250→0 dumps、字节相同；不是原生性能结论。仅相关修复提交后再对新head启动一次新验证。当前尚未得到标准36内部校准、公开CLI/daemon/SDK/MCP验收或merge-ready证据。

### R3 新 head / 单次新验证

- 相关修复提交并推送：`143f9d5691def3f4cb2b09d8e56feb3e53ca50a7`。
- [run 42267580008](https://github.com/YJBeetle/SWCLI/actions/runs/42267580008)，attempt1，2026-11-07 02:05:50 Asia/Shanghai 发起；该head唯一一次dispatch。
- 参数 `docprops_calibration=true`、`docprops_expected_head=143f9d5691def3f4cb2b09d8e56feb3e53ca50a7`、`native_full=false`；依旧仅standards-36，独立concurrency，不进默认full/release。
- 持久回执 `evidence/docprops-performance/dispatch-r3.json`。当前等待真实执行，不重复dispatch，不取消其他run。
- 本轮增加的共享文件修改包含 `scripts/dev/run-document-properties-calibration.py`（私有in-memory管道授权传递），除原calibrator/CI wrapper/auditor外无生产schema/SDK/MCP工具字段修改；手动CLI默认路径未改变。

## 对应公开验收入口准备（仍关闭，尚未执行公开CI）

新增 `scripts/ci/verify-document-properties-public.py`，复用现有 `verify-document-preferences.py` 的严格标准 CLI/daemon gate；该共享gate仅新增默认关闭的optional contract probe和明确有限kinds参数，默认仍全部三类，不改原 full CI。公开入口必须先存在**经独立核原件的真实成功 proof JSON**、API核实的success/run/head/attempt/artifact digest、精确36转换白名单；当前proof文件不存在/白名单空，启动前拒绝。没有制造成功placeholder，没有开放标准写。

公开计划定义为**三个明确独立的1800秒kind组（各12转换）**，同一owned hidden daemon在组间保持，首失败停止、不重启、不回滚；它不是内部单组36的替代或“旧单组通过”。直接复用内部已核baseline字节做本run独立fixture副本，逐次保存/RO、lease/foreign session/update stamp/完整snapshot CAS/只读/状态/身份/geometry/trace保护全部沿用原严格gate。额外每kind做typed SDK读取及MCP execute读取（无写、无host启动），验证真实结果schema、request ID、native reader trace和与CLI同一snapshot/state；MCP不调用daemon_start/stop。

当前10项公开入口portable故障测试通过，既有公开gate13项回归通过（原件 `public-gate-preparation-tests.log`、`existing-public-gate-regression.log`）。这只是准备；R3内部run仍在执行/安装，未触发公开CI。只有核实R3真实成功、精确Windows/revision范围和source/digest后，才写proof/白名单并接线一次必要公开验证。合入main/发布仍由主对话，不由本路执行。

### 公开CI接线（默认关闭，未dispatch）

已准备 `docprops_public=false` opt-in，与 `docprops_calibration` 互斥；同一专属分支/head guard与独立concurrency。公开模式在读取任何 RCLONE 私有输入前校验已提交成功proof、已安装精确白名单和GitHub run/head/attempt/artifact ID+digest；跨run下载仅actions:read，使用官方v8 `digest-mismatch:error`，名称须唯一且ID/digest匹配。PR/private secrets规则不扩展。Native模式仍原35分钟runner step；公开模式三个独立1800秒组/600秒native不变，105分钟step/170分钟总job仅容纳三组、startup/cleanup与安装，不是放宽组内预算。没有内部成功proof和白名单时公开preflight失败，尚未dispatch。

GitHub download-artifact v8输入签名已核实：[官方 action.yml](https://raw.githubusercontent.com/actions/download-artifact/v8/action.yml)。新workflow actionlint通过，相关接线10 tests通过。最终公开运行时才需要重新完成相应便携/契约检查与确切head提交；当前R3继续固定143f9d5。

### R3 核原件与GB模板相关修复（当前最新）

[run 42267580008](https://github.com/YJBeetle/SWCLI/actions/runs/42267580008) attempt1 已completed/failure。原 artifact `13528709614`，ZIP SHA256 `3dfb206fe5a497922ba3f6974c1062dcfda1a325c4ef80afc29cc9a93a8c9b08`，已逐字节核对GitHub digest/head=`143f9d5691def3f4cb2b09d8e56feb3e53ca50a7`；ZIP/原件/该head四文件source snapshot持久保存在 `run-42267580008-original.zip`、`run-42267580008-original/`、`run-42267580008-source/`（Git忽略但保留）。`run-42267580008-audit.json` 全部原件hash/source/head/worker核对通过，native_group_complete=false。

本次owned接口验证成功：单次unmarshal核PID，68-byte接口包只在内存传递，parent TABLESTRONG released=true，owned ExitApp/Wait等清理无错误。该结果只证明此 hosted 场景的接管链，不是标准转换通过。

首实际失败：全局默认模板路径均空，通用发现选择 `C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\MBD\part 0001mm and smaller.prtdot`，其overall为ANSI1，原GB7基线断言拒绝。只到part初始观测，**0 setter**，几何11999.999999999998 mm³/1 body符合现有box断言，native cleanup_errors=[]。未改GB断言、未通过Set强行初始化、不重试API、不改全局模板偏好。

相关修复：新增纯文件 `gate_support/document_property_templates.py`，仅挑明确安装的 `gb_part.prtdot`、`gb_assembly.asmdot`、`gb.drwdot`（或ProgramData唯一gb_a4）模板；不存在/重复/符号链接即拒绝。新增 `--part-template/--assembly-template` 内部诊断参数，包含在hardened worker完整授权argv中。每个实际输入仍原生校验GB7且hash不变；故意不接受MBD或任意首个模板。选择报告在success原manifest内保留；选择失败也保留独立失败原件，且artifact单root布局不变。

当前关联127 tests（含6项模板发现/参数绑定）通过，完整便携2131 tests / 66.887秒 / skipped32，OK，原件 `full-tests-exact-gb-and-public.log`；相关workflow actionlint exit0。公开入口仍缺成功proof/白名单并保持关闭；未触发公开CI。

当前待审批动作：无。已沿用用户/主统筹授权完成限定worktree的修复与own branch push/targeted CI；没有未解决的自动审批拒绝，不需要重复授权。下一步仅对提交后的相关修复新head启动一次内部标准36校准，记录确切head/run；公开门禁要等其真实证据。

### R4（本线程第4次dispatch，非历史VM的r4）

- 模板相关修复已提交推送：`ea45651b1afbd18e936ea5946c93c329c058bca0`。
- [run 42274393189](https://github.com/YJBeetle/SWCLI/actions/runs/42274393189)，attempt1，2026-11-07 02:50:53 Asia/Shanghai 对此head唯一一次dispatch。
- 参数 `docprops_calibration=true`、`docprops_public=false`、`docprops_expected_head=ea45651b1afbd18e936ea5946c93c329c058bca0`、`native_full=false`；仅内部标准36，未触发公开gate。持久回执 `dispatch-r4.json`。
- 这仍是单个1800秒组，须三类各12、全部36保存/RO及216固定profile；选择GB模板不替代原生断言。没有本地VM操作，没有自动重试/rollback或组内重启。

### 公开写环境边界：仍关闭的补强

新增 `CALIBRATED_DRAFTING_WINDOWS_REVISIONS=()` 与标准writer的精确原生Windows/revision门禁；转换tuple和revision清单当前均空。即便后来具备转换数据，Wine、非Win32、无法判定的ntdll/未测RevisionNumber仍拒绝changed写；完整CAS同值no-op维持0 setter。新增5项host scope故障测试，标准相关共28 tests通过，公开准备10 tests通过；RevisionNumber单层native trace验证通过，未嵌套调用。官方RevisionNumber方法已核实：[SOLIDWORKS官方接口文档](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~RevisionNumber.html)。

这次src共享文件新增改动仅 `src/swcli/document_drafting_standard.py`（空revision数据）和 `src/swcli/hosts/windows_document_drafting_standard.py`（changed写前环境门禁），没有请求/result schema、SDK/MCP字段变化。8个固定reader/validator函数与正在运行的ea45651按AST逐项相同，持久指纹 `native-fixed-reader-parity.json`；不借旧校准证明新写gate。SDK生成、strict types及消费者正负类型检查已通过（`sdk-contract-types.log`）。R4仍固定ea45651；此补强不触发额外CI、不填白名单，后续必须以真实内部/公开证据收敛范围。
