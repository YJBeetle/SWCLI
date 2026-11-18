# Phase B 公共只读门禁：离线候选与 CI 接线提案

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
