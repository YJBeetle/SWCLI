# current-user OS-only 查询回执（2026-11-13）

本票 `VM-20261113-OS-USER-CONTEXT-01` 只有一次只读 OS 查询，`CAD_execution_authorized=false`。**实际入口返回255，没有来宾 stdout/JSON，没有新用户/SID/SessionId 或进程数据，不能证明身份切换成功，也不能判断当前 CAD 是否空闲。** 没有重试、SYSTEM 回退、DispatchEx 或下一轮 probe。

## 实际命令与范围

外层原 argv 完整归档，明确为：

```text
prlctl exec <已分配VM> --current-user <固定绝对PowerShell> -NoProfile -NonInteractive -EncodedCommand <本路无凭据查询源>
```

`--current-user` 位于 VM 标识后、Windows 可执行文件前。所提交的编码内容与归档 PowerShell 源逐字一致；既不把 flag 放入来宾脚本冒充生效，也不删除它改走默认 SYSTEM。

查询源仅拟读取当前 PowerShell 的 token 用户名/SID、SessionId、exe 路径/版本/hash，以及已存在 Explorer/Python/SLDWORKS 的 PID/SessionId/ExecutablePath。Parent PID 没有引入额外采集器，明确留未采。没有采集任意进程命令行、环境全集或凭据；没有启动 Python 子进程，没有 COM/SW/文档接口、WMI/CIM、DCOM/注册/权限/RunAs 修改。如果发现 CAD，占用快照后就停止，不继续额外采集。本次未得到任何该 payload 的有效输出，不能把拟采字段当作实测结果。

## 原始结果

实际 guest `prlctl exec`：exit **255**，stdout **0 bytes**。stderr 原文：

```text
PrlVmGuest_RunProgram: Unable to open new session in this virtual machine. Make sure your virtual machine has finished booting, runs the latest version of Parallels Tools, and is not isolated from the host OS.
```

这只证明新 guest session 建立失败；消息中的启动/Tools/isolation 条件是通用提示，未验证为原因。本次没有升级 Tools、修改隔离或账户设置。主机归档脚本正常结束只表示记录写完，不能把它的退出状态当作查询成功。

原 VM 当时为 paused/idle pause on。为这一次只读查询恢复同一 boot 一次，未启动新 boot、未重启、未改 VM 配置或 idle pause；结束状态记录为 running/idle pause on。北京时间约 06:53:36–06:53:37，查询设定30秒上限并快速返回255，未走超时回退。没有任何后续 guest 命令；只追加主机侧状态快照，然后结束本路使用窗口。台账由统筹收口，不能据此承诺未来 VM 可用性。

## 可复核证据

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/os-user-context-01`。其中包含实际 argv、授权快照、主机前后状态、同 boot resume、PowerShell 源、空 stdout、原 stderr 和主机归档源。清单及独立 audit 可离线重放；不执行任何 VM/COM/CAD。

[回执修复与历史传输对照](glb-receipts-and-session-review-2026-11-13.md)仍成立：旧 e3 外层 argv 有 current-user，Nov13 PHASE-PROBE 外层漏参。本票修正了**所提交的参数**，但其入口没能建立 session，因此没有补足 actual token/session 证据，也不能据此宣称先前 COM 首错已解决。

回执源码修复固定在 `c9846f6aad4312cc8bf97195deaa6c4f880fda6f`；117 项诊断/23 项桥接测试均通过。本补充只收紧方案范围、修正补丁展示格式并记录这一 OS-only 失败票，未改 runtime 修复或原有失败原件。任何后续 OS/COM/OpenDoc/probe 均不自动获得授权。
