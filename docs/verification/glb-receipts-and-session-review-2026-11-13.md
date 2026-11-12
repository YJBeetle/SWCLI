# MarkingJig 回执修复与零 CAD 会话诊断方案（2026-11-13）

本离线修复阶段仅修改诊断回执、用已有原件做离线对照和故障注入测试。**新 VM/COM/SW/OpenDoc/probe 执行次数均为 0**。未改产品、`_owned_harness`、DCOM 注册/权限/RunAs，也未介入 STEP。

## 两处最小修复

1. `run-markingjig-control.audit` 使用显式单 case 解析：`cases=[]` 合法表示尚未进入 case，返回 `success=false`、`case_count=0` 和完整原 `native_failure`；不制造 case 或 loaded/cleanup 成功。只有唯一真实 case 才能参与原成功准入；即使空 case 的 report 或退出码矛盾地声称成功，回执也拒绝。
2. 新增纯 OS 回执模块 `launcher_receipts.py`，由私有 launcher 的修订收尾块调用。原 native report、原首错和 secondary 分开记录；每项检查有独立 try/except/finally 持久化，某一项失败不会跳过下一项。顺序为进程清单、原 report、退出后 raw 输入采集、独立比较、输入 hash、全部代码 hash、回执 helper hash、输入目录、原证据复制、最终进程清单。文件 hash 按文件隔离，一份不可读或不匹配不会跳过余下文件。
3. 无 case 时，只对已有 pre-CAD/退出后 raw 帧做文件比较，不建立新模型基线、不补写 case。新 post label 为 `after-candidate-worker-return`，不再暗示 CloseDoc/ExitApp 必然发生。最终成功还须有真实单 case、child success、输入/代码完整证明且无 secondary；不能只看 cleanup 没报错。
4. `markingjig-private-launcher-postchecks.patch` 是对归档私有 launcher 的精确回执差异；`markingjig-private-launcher-review.py.txt` 是其完整审查源。原母版 SHA `15251b8bd9c6ff70aea17c6dc7cf8a0a462129c5031277caab180f48fbbc9341`。补丁仅应用在临时副本核对，原文件从未修改。

完整审查源保留母版的旧路径/925 guard 作为差异基准，**不是本轮或下一轮可直接运行的 launcher**。未来如获执行许可，须先亲审新配额的全新目录、最新精确源码 head、代码包以及 helper SHA；新源还要求 `launcher_receipts_sha256` 并在任何写入前核对相邻 helper，旧归档 context 没有该字段，不能拿旧目录重跑。本轮没有填写新执行配额或启动命令。

## 已有传输证据对照

| 项目 | 2026-11-12 e3d9bd9 流程 | 2026-11-13 92563fc 流程 |
| --- | --- | --- |
| 外层实际 argv | `prlctl exec <VM> --current-user <绝对 Python> -I <UNC launcher>` | `prlctl exec <VM> <绝对 PowerShell> ... -EncodedCommand ...`，再启动绝对 Python |
| `--current-user` | 原 `prlctl-launch-exit.json.argv` 明确包含 | 原 `host-run-context.json.launcher_argv` 明确不含；不是被放进 guest 编码命令就能生效的参数 |
| 到达边界 | host PID 5336，revision33.5.0，OpenDoc7 正常返回 Error0/Warning2；整个 probe 仍未通过旧门槛 | acquire-owned-host / DispatchEx 返回 Server execution failed，cases=[]，OpenDoc7=0 |
| 独立 token/SID/session | 未归档 launcher/worker token SID 或 SW SessionId，不能补称已证 session1 | 同类无 flag 的 OS 预检测到 SYSTEM/session0；启动中 SW PID4860/session0。launcher/worker 自身 token SID 未独立采集 |
| 完整模型/导出验收 | 未通过 | 未到达 |

当前 `/usr/local/bin/prlctl` 解析到 `/Applications/Parallels Desktop.app/Contents/MacOS/parallels_wrapper`。静态源码最后是 `exec "${tool}" "$@"`，未发现参数改写；本机原生 CLI 的静态帮助字符串将 `--current-user` 描述为使用当前用户凭据登录指定 VM。只读取文件及二进制字符串，没有运行 prlctl、初始化服务或查询 VM。文件 SHA、帮助片段和原始 argv 来源 SHA 均在配套 JSON 中。

因此可以确认：**Nov13 是本路构造外层命令时漏了 `--current-user`，不是当前包装脚本把它剥掉。** 不过未记录旧 wrapper 的历史 hash，也没有旧 token/session 原件；不能把当前静态转发证明当成历史 token 证明。flag、PowerShell 层、诊断版本和新副本都发生变化，这不是单变量 COM 对照，尚不能断言漏参是 Server execution failed 的唯一原因。

## 下一步零 CAD 方案（仅待亲审，未执行）

不再重复已有 SYSTEM 基线。若统筹另行批准，只做一次显式 current-user 的 OS 上下文采集，外层 argv 中该参数必须位于 VM 标识后、Windows 可执行文件前；完整 argv、包装脚本/原生 CLI hash、采集器 hash 在执行前归档。先选择复用历史直接绝对 Python 入口，避免同时加入新的 shell 路由；如需审查 PowerShell→Python 链，须明确列为另一项 OS-only 检查，不自动追加。

采集器只用 kernel32/advapi32/WTS 的只读 OS 能力，禁止 pythoncom、win32com、WMI/CIM、SW/API、注册表修改、RunAs、凭据参数或 token impersonation。采集并逐项保留：

- launcher 与 Python 子进程的 PID/parent PID、实际 token 用户名及 SID、进程 SessionId、原始 exe/命令行、Python 版本与 exe hash；环境 USERPROFILE 仅作旁证，不能替代 token。
- active console session 与 Explorer 的 PID/SessionId，以及当次只读 SLDWORKS 进程清单；不附着、不关闭他人的进程或文档。
- 所有调用原始返回、首错、部分数据和自身 token/进程查询句柄关闭结果；不把接口拒绝转成预期用户或预期 session。

若 SID/session 不明、仍为非预期 SYSTEM/session0、登录会话有歧义或本路路径不可用，则停止回交，不删除 flag 改走 SYSTEM，不登录/重置用户、不变更 DCOM/RunAs，也不尝试 DispatchEx。即使 OS 上下文符合预期，也只交该原件亲审；任何后续 COM/OpenDoc/完整 probe 仍须单独新配额和明确授权。

## 离线验证与旧证据

- MarkingJig 117 项通过（新增回执 14 项），0.397 秒；typed bridge 23 项通过，0.012 秒。
- 注入 acquire 失败/空 case、比较失败、raw 采集/报告读取失败、持久化失败、单文件不可读/变更，均验证余下输入/代码检查继续，primary 与 secondary 分离。直接执行完整审查源的 finally AST，使用临时文件和假 OS 回调；预检和原生主体从未执行。
- 精确补丁在临时副本应用、结果逐字核对并编译；未执行其 launcher 主体。
- 新 supervisor audit 离线读取真实 925 失败原件，现返回 failed/case_count0 且保留原 acquire 首错，不再 IndexError。原 report 字节不变，原 supervisor 的 IndexError 原件仍保留，原代码退出后 hash 仍明确不可用，未补造正常 SW 退出或升级 native 结果。
- 原 925 report SHA `357ddef4f407b0bd75d383c4570ec0848b04ed016e2f6f840080507a37a1fa1a`、独立审计 SHA `9fe75af82baf3749fbe6c49e5da61d84982f0a928d23c8f3ebcfb3b17eaa0e00` 及全部旧原件未改。本离线修复阶段没有采集新 VM 数据、push 或派 CI。
