# 42902927609：Windows 自身映像原件核验与下一步提案

[官方 push run 42902927609](https://github.com/YJBeetle/SWCLI/actions/runs/42902927609)，source `e2f787666c504e72c289825a7753f27f6bdbb049`，attempt 1，terminal **success**。Windows Python 3.9、3.14 和 wheel 成功，其余四 job skipped，包含 native。只取一次 terminal run/jobs/artifacts metadata；两个 summary ZIP 各下载一次，原始 Windows job 日志各保存一份。首次 gh 输出保护拒绝含控制字符的日志，随后仅同日志端点加允许原字符参数保存，不是状态重查。原件未经文本替换；详见 retrieval.json。

## 两 Windows 实际观察

| 项目 | Python 3.9 | Python 3.14 |
| --- | --- | --- |
| Job ID | 130133366083 | 130133365639 |
| 完整 portable | 1973 tests / 160.412s / 11 skipped | 1973 tests / 202.445s / 4 skipped |
| 自身 API 测试 | 实际执行 ok | 实际执行 ok |
| Query 与 module image | `C:\hostedtoolcache\windows\Python\3.9.13\x64\python.exe` | `C:\hostedtoolcache\windows\Python\3.14.10\x64\python.exe` |
| PID | 2064 | 9984 |
| Creation UTC | 2026-11-10T21:14:24.198000+00:00 | 2026-11-10T21:14:15.860000+00:00 |
| Query / module 返回字符数 | 55 / 55 | 56 / 56 |
| HANDLE / DWORD / BOOL / wchar 字节数 | 8 / 4 / 4 / 2 | 8 / 4 / 4 / 2 |
| buffer capacity / flags / 字节序 | 32768 / 0 / little | 32768 / 0 / little |
| NUL at returned index | true | true |
| Query success / error | true / null | true / null |

完整 observed identity、sys.executable、sys._base_executable、image/repr、Py chars/UTF16 units、module error、原 buffer base64 和带时标原日志行来自原件。两端原 buffer 均独立解码为完整 UTF16LE image 加唯一末尾 NUL；raw query 与 module path 逐字相等。原 Windows 测试通过证明其 os.getpid 和 os.path.samefile 断言实际通过；独立审计不在 macOS 假调用 Windows API。两次 sys.executable/base 恰与实际 image 相同，仅描述本次事实，不扩展为 venv 或未来宿主的准入假设。

| 原件 | ID / 大小 | SHA256 |
| --- | --- | --- |
| 3.9 summary ZIP | 13802729441 / 1073 bytes | `7ba0026806436d58fff9fde2ec198f357e7ada1719367e9f9e8c03aabea3f92e` |
| 3.14 summary ZIP | 13803896789 / 1062 bytes | `bf74b4ff67491c2db9b7f82eb88ebca2057b579981ab48b3d6b9c4ee4e01a03f` |
| 3.9 原 job 日志 | 397553 bytes | `21d684e0b8ef896ab098e1461bc3b5bf31d9022b134ded04aa72494dd1123a31` |
| 3.14 原 job 日志 | 525630 bytes | `470b0e2ace5ab8d0037cb0b3004d1d5ff80c555ec5d985914e812afe70e04dc9` |

ZIP SHA 与官方 artifact digest 及大小一致；日志 SHA 是本地原件固定值，官方 job-log API 未提供相同 digest 字段，不混称官方核验。summary 源 head/run/scope 均一致；3.9 phases PASS3/SKIP3（SDK/parser/public skip），3.14 PASS5/SKIP1（public skip），不将阶段计数混为测试项数。

原件绝对目录：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/identity-observer-push-42902927609/`。terminal metadata、原件 hash 清单和完整提取 `current-process-image-audit.json` 在同名 `docs/evidence/`。独立标准库审计 `docs/verification/audit-units-identity-push-42902927609.py` 固定 run/head/job/artifact/ZIP/log，验证 B64/字符数/ABI/模块对照/实际测试通过及 source binding，无产品/gate/COM import。

## 仍未证明的部分

此 push 没有 SOLIDWORKS；没有新增 private/public CAD 结果，公共 CLI/SDK/MCP 完成各 0。42865595677 原 native ZIP 和 host-report 仍没有 actual SW image；其独立原件审计复跑保持 actual_returned_image_available=false / deeper_mismatch_cause_established=false，公共 0/139 x3，native/helper 退出未确认。Python 自身 API 通过只排除了本次两个 portable 环境的声明/长度/NUL/读取错误，不能证明实际 SW 路径差异消失或不存在 native 环境特定问题。

## 交 root 审阅的最小下一步，仅提案，尚未实施或运行

后续：root已批准最小wrapper同步预检实现，详见 `units-synchronous-identity-preflight-review.md`；本节保留当时提案，未获得新的native派发授权。

当前 wrapper 在启动 public 子进程后以 1 秒间隔观察其 report；child 的 health、list 和 source-open 可在 wrapper 获取 native handle 前连续发生。42865595677 即是在 source-open 途中失败，继而 normal stop 遇到 ActiveDocument。下一步应把身份观察同步提前到 **public 子进程启动之前**，让取证首错不会因为本 wrapper 已经发出文档 open 而触发该收尾问题。

建议只改 CI units wrapper 和其关联测试：

1. 在自有 daemon readiness 之后、public worker Popen 之前，用一次真实 CLI `daemon status --json` 读当前 endpoint；完整原 stdout/stderr/returncode 和解析结果先 durable 保存。沿用 health 的 host_connected=true、recovery_required=false、整数正 PID，以及原 owned/hidden/unshared、PID 不在 prior inventory 的要求。status 的现有 server health 读取进程/生命周期缓存，不派 document.open/原生 setter，不重启/替代宿主。
2. 对该唯一 PID 调用现有 e2f `capture(..., observe=...)`，先 fsync 实际 full image/size/ABI/raw buffer/expected/comparison，再原封不动执行完整路径、PID 和 creation-window 谓词。没有通过不启动 public worker；不得从 observed image 自动更新 expected，也不把 MSI/注册期望替代实际 Query 输出。若再次不同，即保留当前首错作本次取证结果，不重试。
3. 若身份成功，则保留同一 verified handle，让后续 public health report 必须与预检 PID 相等且仍具 owned/hidden/unshared，并保持原身份/worker/lease/CAS/417/三额外 cold probes。不能以已有 handle 为由跳过后续 host 相同性检查。不同 PID/host 仍立即拒绝，不重新开句柄或换宿主。
4. 失败仍只一次 normal stop，保留 stop raw/daemon wait/原库存差异；未验证 native handle 不强杀、不重新打开。前移可避免由 public open 造成 ActiveDocument，但不保证正常 stop 一定成功或 native 退出可确认；没有 verified handle 时必须如实保留退出证据边界，不以 stop exit0 翻绿首错。
5. 关联测试应断言 status 原件 fsync -> identity 原件 fsync -> 原准入 -> worker Popen 的顺序；mismatch/观测落盘失败均零 public Popen、零 document.open/setter、正常 stop 至多一次、未验证不 terminate、首错保留。验证成功则同 handle 交接，后续 PID 改变拒绝。原 validate_identity/terminate/exited/EXPECTED_CI_IMAGE AST 必须与 e2f/085ae 相同。

root 若批准补丁，先完成本地关联检查并交精确 diff/source hash 复核；**新的 native/diagnostic dispatch 仍需 root 另行明确授权**。本提案不新增 workflow flag、预算、路径别名或 product 变更；不自行安排新的内部139/公共417运行。root 可在该同步 preflight 已可审阅后决定单次取证运行的具体路由；本路不先派再说明，不用 VM。

```sh
python3 docs/verification/audit-units-identity-push-42902927609.py --metadata-dir docs/evidence/units-profile/identity-observer-push-42902927609 --raw-dir evidence/units-profile/identity-observer-push-42902927609
```

本次新增仅独立审计、原证据和提案文档；业务 head 保持 e2f7876，未 dispatch、未用 VM、未 push 新提交。
