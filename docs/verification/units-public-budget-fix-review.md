# 公共预算修复：供统筹审核的实现与本地证据

原失败仍是 [42664223806](https://github.com/YJBeetle/SWCLI/actions/runs/42664223806) / `64af40c908c01ca20027d06799eaec702627e5ee`：CLI139、SDK15、MCP0，1800秒组超时，owned native退出未确认。完整原件/digest、154case独立审核、时间分布与历史提案见 `units-public-budget-42664223806-review.md`。本次未用VM或新的CAD运行验证纯进程开销。

统筹亲审后批准以下实现；目前仅本地portable/TCP/进程证据，尚未派新公共验收，不宣称原生整组通过。

## 仅单位WriteGate的CLI前端与报告保存

`unit_cli_worker.py` 是一个CI专用 `python -I <helper>` 子进程，导入已安装的 `swcli.cli.main`。每个frame调用一次真实main、每次重新解析原argv、一次真实TCP RPC，保留原stdout/stderr/returncode；产品公共CLI/SDK/COM和其他门禁均未改。它没有新的公开batch命令，也没有借SDK/daemon handler替代CLI。

验收策略明确变成 **139次真实CLI main/parser/RPC调用，复用一个隔离CLI进程**；失去每command冷启动/进程隔离覆盖，绝不称为139次独立进程CLI。真实SDK/MCP仍各139，共417同一个owned host/worker、同一1800秒整组，600秒请求边界和原grace不变。既有完整main/native其他门禁仍走原逐次CLI subprocess。

每文档类型另做一次真正 `python -I -m swcli` 的只读unit-profile探针，与同文档刚完成的helper读做完整返回/快照/文档状态比较；三次额外探针不并入417，也不当作139次冷启动。原始两份stdout分别留在 `cold_start_coverage.probes`，差异即停止，不写setter。

报告明确 `cli_process_strategy`、`cold_start_coverage` 和 `cli_frontend`：helper路径/SHA、准确启动命令、PID、已安装CLI路径/版本/SHA、开始时间、命令数、一次退出wait及确认。每个helper请求JSON原文、解析对象、完整原reply frame与原CLI stdout/stderr/returncode在transport-events.jsonl每次flush/fsync。序号/帧边界/身份不符、EOF、异常、超时均保留原字节/partial/unknown outcome，禁止重发或启动替代helper。退出EOF/已持有子进程只等待一次；异常只终止自己的保留Python子进程。

完整semantic报告保留相同字段、全部历史、相同检查点、flush/fsync，只移除JSON缩进。没有改其他durable helper、没有证据格式分片/省字段或削减guards。读后合法noop、lease竞争owner token/stamp/完整CAS、closed域、只读、后台上下文、保存RO与完整几何原件都保留。

## 仅本run、持续持有且证明身份的宿主句柄

增强收尾只作用于单位write模式。读取本次新报告的owned/hidden/unshared证明，要求PID不在前置库存；在public仍运行时打开一次句柄，并用同一handle核GetProcessId、CreationTime落在daemon启动UTC至观测时刻之间、完整Win32镜像路径等于本CI安装器/COM注册核实的 `C:\Program Files\SOLIDWORKS\SLDWORKS.exe`。镜像查询使用QueryFullProcessImageNameW；后续持续持有这个handle，不在失败后重新OpenProcess寻找替代PID。

正常daemon stop一次，然后确认native退出、库存恢复。若预算等首错导致stop失败（如ActiveDocument），保留首错与stop原stdout/stderr，停止已持有的Python父进程后，仅可对同一已验证native handle重新核准确identity并最多一次TerminateProcess，再wait和核库存。没有按名、进程树或未知PID扩大终止，没有重启CAD或业务重试/回滚。无可靠身份时拒绝终止native，报告unconfirmed。

`forced_native_termination_attempted/returned`、完整creation identity、owned_native_exit_confirmed、库存和全部cleanup次错均保留。强制结束即使确认退出也保留cleanup错误和原失败，绝不翻绿。句柄关闭或保留Python进程终止失败也不覆盖首错；SDK/MCP与CLI前端同时关闭失败时两个次错均保留，抛出第一个关闭错误。三类原件中的旧unconfirmed状态不改。

CLI helper正常/异常退出由其保留Popen对象等待一次；wrapper运行中还可核其准确helper路径/hash/命令/PID/创建窗并持有**只含查询/等待、没有TERMINATE权限**的Python handle。公共父进程被kill后，只用该handle确认helper因管道EOF退出，不寻找或终止未知Python进程；如无法确认仍失败。

Windows API依据：[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)、[process handle生命周期](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers)、[TerminateProcess及等待要求](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess)、[pywin32 GetProcessTimes/GetProcessId实现](https://github.com/mhammond/pywin32/blob/main/win32/src/win32process.i)。以上是实现依据，portable mock不构成Windows实际强制退出证据。

## 已完成验证与剩余边界

- 最终关联84项/23.473秒通过；包括真实fresh CLI subprocess和真实隔离helper经真实TCP对假daemon逐字节对照：读取、changed/native回执、非法enum、lease/stamp/CAS/readonly/closed拒绝和partial原始double/hex/错误。解析拒绝不发RPC；协议拒绝一次RPC；EOF/乱序/异常/超时、intent/reply持久化失败无重发/重启，原始回执保留，helper一次关闭等待。
- 增加三类型额外独立冷启动只读探针的合成417流程；探针快照漂移即零setter停止。完整417 synthetic仍不是原生验收。
- wrapper正常路径、1800首错+ActiveDocument后同一句柄一次终止/等待且保持失败、身份捕获失败、共享/未知宿主、前置PID、旧/未来CreationTime、错误PID、其他完整安装路径、identity变化均有portable反例。CLI Python句柄没有TERMINATE权限；Win32查询形参与数据在portable中核过。
- 最终完整1960项/75.689秒通过（26skipped）；SDK generator、strict6文件及8个consumer typing拒绝通过；8个改动CI/test文件Python3.9 AST、差异检查通过。日志/hash与8文件源码SHA在 `docs/evidence/units-profile/public-noop-42664223806/implementation-validation.json`。
- 已实现的真实隔离helper额外离线基准：40个真实TCP请求（fresh/helper各20），逐字节stdout/stderr/returncode相等；本机中位约0.143092/0.006465秒，helper starts=1、exit_waits=1、exit_code=0/确认退出。原JSON journal及摘要 `actual-frontend-benchmark.json`。这是macOS进程/协议证据，不是Windows耗时或1800秒可完成保证。

产品src、公共合法域/137域/26后态、schema、workflow、main property/PyYAML、几何标准（V/S/body/state/CAS严格，仅原质心逐轴绝对≤1e-12mm）均未动。root统一占用VM，本路未使用VM、未合main、未发布。下一步先交root审核精确新head；确认后才一次必要新公共CI，正常启动快照即停，不持续poll。不用旧CLI139或本地1960项补未完成的SDK/MCP原生覆盖。
