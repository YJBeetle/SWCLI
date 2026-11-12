# MarkingJig 分阶段 probe 原生首错审计（2026-11-13）

结果：一次受控流程失败在获取 SOLIDWORKS 实例，未进入 case runner；**OpenDoc7=0、export/SaveAs=0、完整模型观察=0、opening/loaded 阶段帧=0、loaded baseline 未建立**。因此本次没有验收分阶段模型合同、warning2 诊断枚举准入、引用或几何。没有重试、修复、resolve/rebuild、参数变更、fallback、新一轮启动或 CI。

- 配额：`VM-20261113-MARKINGJIG-PHASE-PROBE-01`。
- 固定源码：`92563fcf2a887a984d6d309812b2169313ec8fec`；原产品 `70d8c9ecf3c02b099ca9c2cc64fe1880061cea44`，原 driver SHA `282d75cb4a4097dac4077bb7e70af68d8278c351880d0887ce8220ba46cd36d2`，产品 ZIP SHA `06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53`。代码 ZIP、复制后代码文件及产品 pin 在启动前均校验。
- 显式选择 `--mode probe --phase-policy opening-transition-probe`，collector 的 access time policy 为 record-only。新代码、10 份普通独立只读输入、新输出均在新的 `C:\Workspace\SWCLI-series-20261113` 目录。没有向仓库或 CI 复制业务二进制。
- 主机窗口：北京时间 04:32:30 至 04:34:45；进程正常返回退出码 1，未触发 600/1800 秒 watchdog。

## 原始首错与实际到达边界

`read-official-swconst` 正常返回后，唯一 `acquire-owned-host` 调用发生致命错误：

```text
com_error: (-2146959355, 'Server execution failed', None, None)
HRESULT: 0x80080005
```

原错误栈保留固定产品中的 GetActiveObject → DispatchEx 分支；前者的 `-2147221021 / Operation unavailable` 是被原代码处理的 ROT 上下文，最终致命错误为后者的 Server execution failed。没有更换调用路径或再做一次获取。获取窗口约 120.122885 秒，随后 `CoUninitialize` begin/end 正常。

报告 `cases=[]` 且没有 host 字段，说明 COM 应用对象和 owned process handle 没有取得。`CloseDoc`、`ExitApp` 和 owned wait receipt 均没有发生。一次纯 OS 进度快照观察到启动中的 SLDWORKS PID 4860、session0；它不等于已验证的 owned COM 实例，也没有该进程的正常退出码回执。launcher 在候选返回后及最终输入检查后均观察到全局 SLDWORKS PID 列表为空，supervisor 前后也为空。**这些是进程端点证据，不可改称 SOLIDWORKS 正常退出已证。**

来宾预检记录执行身份为 SYSTEM/session0，Explorer 在 session1；这是观察到的环境，尚未证明为错误原因。本轮未继续采集事件日志、改身份或修复环境。

## 内容、身份与元数据

- 主机独立检查 Mac 10 个 native 文件及既有 GLB，共 11 份：窗口前后完整原 `stable_file` 指纹和 SHA 均与固定 inventory 逐值相等。inventory SHA `d7db20f8041424115a97b91376001be759b32fad6e5faa2cc405fe971a13185d` 不变。
- 10 个新私有输入均为普通文件、只读、nlink=1，与原件不为 samefile；SHA/size 与批准库存相等。
- launcher 在 native 流程前和 worker 返回后分别采齐 10 个文件的完整三渠道/全 SHA 原件。每份均有读取前后的两轮 Python path/held、Win32 held/重新打开路径、Basic/Standard、完整 volume+128-bit FileID、原始 opened path、完整 raw 差异、句柄关闭及策略结果。
- 独立离线审计核对全部 raw：10 份内容与完整 native ID 跨窗口保持一致。raw 差异共 80 项，全部是 Python st_atime_ns 和 Win32 LastAccessTime；Creation/Write/Change、原 stable_file 全部字段、attrs、size、links、allocation、目录/删除标志及路径等逐字段不变，record-only 投影后差异为空。保留原值，不转换时间、不设容差，也不推断没有中间写入。
- top Native FileID：volume `4217245827768940497`，完整 bytes hex `25340500000004000000000000000000`。Win32 CreationTime=`134389891537806625`、LastWriteTime/ChangeTime=`134389891537840158` 跨窗口均相同。LastAccessTime 从 `134389891540391013` 变为 `134389892836250218`，仅作记录。

上述前后 raw frame 只证明本次失败获取窗口的文件端点。原始 post frame 的固定 label 虽包含 CloseDoc/ExitApp，但本次二者根本未调用；不能从 label 推定关闭文档窗口已经执行或被验收。

## 次级错误和保留的缺口

原 native report、supervisor 和 launcher 原件均不改：

1. supervisor `audit` 直接取 `report['cases'][0]`，在空列表上触发 `IndexError`。首个 COM 错误已在 report 中保留，不能被这个整理错误替代。
2. 私有 launcher 已采完退出后的全部 raw frame，随后同样取 cases[0] 触发 `IndexError`，未完成在线比较；同一个 try 中后续的代码退出后哈希检查也被跳过。**代码只证启动前固定 SHA，退出后代码哈希未采得，保留该缺口。**
3. 独立离线审计从既有完整 pre/post raw frame 完成输入内容/身份/策略检查，未再执行 VM/CAD，没有改写原生失败状态。首次离线审计错误地假定 code_hashes_after 一定存在而触发 KeyError；已保留初版审计源，修订版明确标记不可用，不补造这个证据。

## 启动预检和 VM 状态

初始 VM 关闭、idle pause=on；只启动了一次，没有重启。初始主机受限状态查询未执行 VM 操作；紧接启动的短执行路径预检返回255 Invalid argument，原件保留。当时过早恢复 idle pause 后 VM 自动暂停，后续预检查询超时。随后只恢复同一 boot 并把 idle pause 保持 off 到本窗口结束，完整路径预检确认没有 SOLIDWORKS，固定 Python 与 UNC 原件/证据路径均可访问。不存在实际 probe 的第二次尝试。

H: 与 python PATH 快捷入口在 SYSTEM 环境没有恢复，使用已存在且核验过的固定 Python 绝对路径和原共享 UNC 路径；未安装软件或更换产品。一次进度快照意外展开 Get-Content 的 PowerShell ETS 元数据，原大文件保留，只另外提取文本值，没有再次触碰模型。

结束时 idle pause 已恢复 on，VM 记录为 running；原生 PID 空列表是当时的快照，不是未来可用性承诺。本路已停止所有 VM 操作，配额交还统筹处理；未编辑中央台账，任何后续执行仍需重新分配和新鲜预检。

## 复核入口

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-92563fc-01`。

- 原 native report SHA：`357ddef4f407b0bd75d383c4570ec0848b04ed016e2f6f840080507a37a1fa1a`。
- 60 份原始文件 manifest SHA：`a5959dc1aa414a40b45fee0369a3811471750013a7e7b1718b1fc7928cf21ddf`；原始 manifest 不覆盖其后产生的审计结果，补充记录另列。
- 独立审计 JSON SHA：`9fe75af82baf3749fbe6c49e5da61d84982f0a928d23c8f3ebcfb3b17eaa0e00`。
- 运行 `audit-glb-phase-probe-92563fc.py <原件目录>` 可离线重放全部断言并生成逐字节相同的 JSON；无 VM、COM 或 CAD 调用。原始 `cases=[]`、次级 IndexError、退出后代码 hash 缺口以及未证正常 SW 退出均保留为失败边界。

本次未修改产品、诊断 runtime、CI 或旧失败证据，仅新增离线审计及文档；未 push/派 CI。
