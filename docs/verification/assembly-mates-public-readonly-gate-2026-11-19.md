# Phase B 公共只读门禁：离线候选与 CI 接线提案

接线补记（统筹）：下文离线记录冻结于 `45a06e8`。此后已在候选分支应用所述 CI 路由，仍未执行公共 native 验收。新的执行清单为 `docs/verification/assembly-mates-public-readonly-ci-inputs-2026-11-19.json`（SHA256 `0e8f73db74af3d919b0babe551f7a4d9dccf31ccf920758ef9b917f1f72a46ee`）；原526项离线清单保留原字节。执行源码仅新增 CI selector 分支，102项关联测试通过；原3081项完整结果仍明确属于接线前候选，当前 selector 的完整 CI 结果待证。最终 Git head 与 workflow 字节由统筹外部核验，未把自身 commit SHA 写进 workflow。

本轮只完成源码、portable 测试、固定样件校验及一次性执行计划。未使用 VM/COM/CAD，未 dispatch 或轮询 CI，未写真实执行许可，未推送、合并或修改真实工作流。公共 native 验收仍未完成；private native37 的通过只属于其原始冻结候选。公共写入、mate 树 CAS、writable-read、save/reopen 写后持久性均未实现或验证。

## 文件与固定样件

`fetch-assembly-targets-public-fixture.py` 每个元数据/归档请求只调用一次 gh，保留原始 stdout/stderr、命令、真实退出码及超时部分输出。`prepare-assembly-targets-public.py` 离线校验归档并向全新目录提取三份 chmod444 样件；计划保留元数据原件与重写副本各自摘要、preparer/module 摘要，`authorized_to_execute=false`。旧 prepared/prepared-v2 是历史草稿，最终准备件为证据目录的 `prepared-20261119`。

固定 artifact 为 13535673155，run 42279916240，原始 head `ac9e54f9e533c60ae6af49476ca71aa94b9b0fe2`，733282 字节 ZIP SHA256 `5d5a85844241e6db86d2074e832659340c3c30a7564b65aa0089db581d4095c7`。2026-11-19 只读刷新仍为 expired=false，到期 UTC 2026-11-20 19:49:09（北京时间 11 月 21 日 03:49:09）。实际准备和执行入口都复核当前到期时间；过期停止，不重建样件或复用旧许可。ZIP 拒绝重复、越界、绝对路径、反斜线、盘符与符号链接，再核三份原件 SHA。三份精确摘要见 plan 模块及 inputs JSON。

## 两个预先声明的公共生命周期

`verify-assembly-targets-public.py` 与 `gate_support/assembly_target_public_evidence.py` 组成零 COM supervisor / 单 parent / 两阶段公共 daemon。每阶段只启动一个 daemon 和一个 owned host，同阶段不换宿主。A 必须先完成全部请求、逐条原件审计、daemon 退出0、held native handle 严格整数退出0及 nativeafter=[]，才准许 B 开始。两个阶段用于既定跨 worker 旧句柄拒绝，并非失败恢复或重试；关闭文档和换 worker 同时变化，不能宣称已单独隔离 worker 的因果。

组预算1800秒，单个 native/public request600秒，外层1840秒；按原始 trace/intent 在读完字节后取时钟，缺少 native begin 也受 intent 预算约束，拒绝 NaN/bool/future/partial terminal。不额外给 CAD 清理等待。supervisor 只可停止已持有正确身份的 parent Python；native handle 无 terminate 权限。原始第一错误与清理/证据错误分开保留，不将 unknown/None/bool 非零退出解释为0。

公开计划固定17项，其中5次完整 census、总计30次六面 native owner 读取：

| 阶段 | 固定目标用例 | census / owner |
| --- | --- | --- |
| A | CLI list、SDK validate、MCP 子集 validate | 3 / 18 |
| A | part kind、持久引用摘要冒充 handle、跨文档、跨session、过期lease、后台拒绝 | 0 / 0 |
| A | MCP close/reopen 后 list | 1 / 6 |
| A | reopened 旧snapshot、旧target配新snapshot、错误stamp、stale不复活 | 0 / 0 |
| B | 新 worker SDK list | 1 / 6 |
| B | 上一 worker 的 snapshot、target 拒绝 | 0 / 0 |

每个成功批次六个 typed handles 完整且新鲜；reopen、新 worker 与此前所有相关批次的六个 at-ID 集合均不相交，doc-ID/as-ID 也换代。原始持久引用摘要可保持相同，不作为新鲜句柄的替代品。未知 IsSame、原生 binding mismatch、中途故障注入只能通过 portable 反例覆盖，不能在纯公共只读门禁中伪称真实制造成功。

每条请求前先 fsync 一次性 intent，唯一 UUID/标签和精确 operation/params/context 必须属于有限计划；本地 WireProxy 只原样转发一次，先保存完整或部分字节再解析。保留 CLI 真正命令/stdout/stderr/退出码、SDK/MCP 客户端呈现、原始协议、逐 request native trace、阶段审计。CLI refusal 必须原始退出1，成功必须0，不用 wire 成功覆盖客户端失败。MCP 每阶段独立目录，显式跨session，不覆盖 stderr。阶段审计从更早的原始 wire 结果推导后续参数，不信调用方自填摘要；核全部17项、30次 owner begin/end、5次完整结果schema、每次负例零owner/零写setup，无写入或激活调用。外层重算阶段审计并比对原件后，才可报告资源已释放；此字段仅覆盖本门禁 parent/daemon/native，runner/bootstrap 清理由外层另证。

## CI 路由提案与接入边界

仓库真实 ci.yml 已有25个 workflow_dispatch inputs。随附 patch 仅作可审查提案，没有应用。它复用已有 native_topology_targeted selector，并改为明确描述：原 part 分支仍解析原 profile；仅精确 `refs/heads/codex/swcli-assembly-mates-active` 解析独立 `assembly-targets-readonly-public`。错误 event/ref、混合 feature 或 units flags 均拒绝。旧 part step 原字节保留；B 有独立 job title、concurrency、public gate step 和有限 summary scope，不接 full acceptance。固定 artifact 验证位于 private setup 之前。

独立小 workflow 可以让 selector 更直观、避开25项输入限制，但会复制 hosted-Windows/bootstrap/cleanup 接线，长期容易漂移；当前复用方案保留已有基础设施，代价是同一 selector 需靠精确分支解析区分。root可在正式接入时选择；本提案不授权 dispatch。

源码清单排除 docs/workflow，防止 commit SHA 自引用。提案只冻结 `ROOT_REVIEWED_SOURCE_MANIFEST_SHA256_REQUIRED`，实际 grant 记录 GITHUB_SHA 和当前 workflow SHA。协调者必须在 dispatch 之前外部核验完整最终 head 与 workflow 字节，并在实际 run 核对 run.head_sha；运行中自己记录的 SHA 不能替代这一外部亲审。应用 patch 会改变清单覆盖的 validate-native-profile.py，因此必须先重新生成完整源清单，再替换 reviewed manifest 常量，另作 CI 接线提交。禁止把当前526项旧清单直接用于已接线源码。

语义测试既能离线渲染未应用 patch，也能直接验证已应用的 workflow/profile；只应用一半直接失败，已应用时不会重复套 patch。验证25输入、旧 part step、精确新旧分支、冲突拒绝及无最终HEAD自引用。最终渲染件使用 proposed-20261119-*，旧 proposed-* 仅保留历史。

## 失败记录、测试来源与 native37 边界

首次本轮完整 portable 日志 `review-20261119-complete-portable.log` 原样保留：3079项、39skip、1error，108.389秒，SHA256 `6ad4501659d46d8ea30ce707355d4d0de4fd56798c025a46713c68c3affedbfa`。业务断言已过，TemporaryDirectory 删除时真实测试镜像线程仍写文件造成竞态。该次未预先冻结全部未跟踪源文件，事后 current-source-snapshot 不能冒充 run-start 证明。

root独立用 Event 屏障复现并批准最小 test-only 修复 `28d5f2c`：两个 deadline 用例在 SUT 返回及原断言完成后，仅于 fixture finally 中 join 已创建的 mirror thread，再删临时目录；不调用 SUT finish/tick/process.wait，不改生产预算或 native37 诊断。22项执行器测试通过，首个失败日志仍保留。最终 full 在运行前单独冻结526项精确源字节，详情见 inputs JSON 的 final validation 与日志摘要。

native37 的生产观察 core、reader、adapter 三份与原始1b5cbdc逐字不变，observation 测试也不变；两份测试存在明确例外：main9f4a2d1/fdea8fa 的 Windows chmod644-before-unlink，以及28d5f2c的测试镜像线程收尾。不得再声称六份私有源文件全部不变。native37 原包15份冻结文件只读重核，未更改、重跑或扩展其验收声明。

最终完整 portable：3081项、39skip、110.656秒，原始退出0；SDK strict六个源文件通过，38条消费者拒绝通过。运行前526项清单与运行后文件逐字一致。MCP依赖在该离线环境不可用，39skip保留原样，不将portable假对象覆盖当作真实三传输/native通过。

## 44367787267 源件生命周期修复

运行 `44367787267` 在 `7377529ce6410955b0f4cdaa1131117689b39d8a` 通过 Windows 的原字节准入并进入阶段 A。原 artifact `14459855901` SHA256 为 `a900a8c262f04fdb7f7a40538f9bc73adee4019718b1e05368cba44c12445590`。31 条业务回执中有 14 项目标用例，4 次六面 census 与 24 次 owner 读取。阶段 A 没完成，阶段 B 没启动，公共 native 验收仍待完成。

源件 `d-58y265` 最迟在最后关闭装配后的下一次 registry sync 已从原生目录缺席。按 `DocumentRegistry.sync` 对每个文档两次读取 key，以及关闭 handler 的一次选中文档 descriptor，尾部三次 `GetDocuments` 可复核为 3 → 1 → 0。第一次后已调用原生 CloseDoc 关闭装配，第二次只剩可由请求 ID 解析的隔离件，随后成功关闭。第三次目录为空，`85f4c988-a0e0-419c-8535-682047390730` 在 resolve 返回 `DocumentNotFound`，没有实际调用源件的原生 CloseDoc。旧 ID 最后一次正面核到是 `p1-part-lease`，`p1-part-release` 回显同一个租约。trace 没记录早前枚举对象的路径或 IsSame 值，无法区分旧 ID 是在装配 reopen 时换代，还是在最终同步时与源件一起被回收。原生目录的卸载边界已可定位，现有证据不支持修改产品的 `DocumentNotFound` 语义。

补丁只改验收。每阶段的既定关闭之后做一次 SDK `document.list`，以成功回执、`documents=[]`、`count=0`、无 current ID 证明空目录和原路径/ID 缺席。如果唯一剩余项是原路径、原 ID、未修改的源件，则只调用一次确切 ID 的 `document.close(discard=false)`，再要求第二次公开 list 为空。新 ID、错路径、其它文档、未证实关闭和任何失败均停止。阶段审计复核原始意图顺序、wire 请求与响应、同 worker 上 `GetDocuments` / `CloseDoc` 的配对及持有句柄证据。17 项目标用例及 600/1800/1840 秒预算保持原值。

原失败后没发公开 daemon stop，没读到 held host/daemon 退出码，也没有 gate 的 native after 快照。supervisor 的 Python parent 退出是整数 1，`resource_released=false` 是证据未成立。外围 disposable runner 清理 PASS 属于另一路径，不能代替 held host 与 daemon 的正常退出证据。

同一原件的后续审计还发现两条 CLI 错误句柄确实通过 TCP 到达 daemon，分别为 part face handle 和持久引用摘要。daemon ingress 按请求 schema 返回 `ValueError`，两条都没有 worker trace。旧审计错误地排除了它们的真实 wire 原件。本次按原件要求各有一次 wire 请求与精确错误，CLI 真实退出 1，stdout 对应 wire 响应，worker trace 为空。重放原件通过了 14 条目标意图、6 条 CLI argv/stdout/原始退出、两条 ingress 拒绝与两条确切关闭回执。原运行缺成功的最终目录和退出证明，仍不能通过阶段 A 审计。
