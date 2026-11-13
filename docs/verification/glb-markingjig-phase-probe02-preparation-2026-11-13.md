# Windows MarkingJig probe02 完整审查包（仅准备，2026-11-13）

状态：**主机侧准备完成，VM/COM/CAD 新操作均为 0**。新 CAD 票尚未签发，不能执行。候选票名仅预留 `VM-20261113-MARKINGJIG-PHASE-PROBE-02`；未写中央调度文件、未操作 VM、未扩展 Docker 准备、未读取或复制业务原件。本地材料与离线验证不构成 native probe 或导出验收。

完整原件目录：
`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-c9846f6-02`

| 审查原件 | SHA256 |
| --- | --- |
| `markingjig-code-c9846f6.zip` | `c1bf4c6a2edf19faa680b18b30115170a6bf121ce65d1cdcb7fe9daeff7a54ae` |
| `launch-probe.py` 完整 launcher | `f20bdac98ea70c71b3c3b9b61ff577bdfec04340a05edc9751b723868a4e799e` |
| 相邻 `launcher_receipts.py` | `eee85b44ae188233f5b65994c6ef4e26c745f214e24893c80ddc874467b329e0` |
| `proposal.json` 全部路径、源码 SHA、模式与待办 | `0804ed66558aec91e614fb4b480a1ce9f317674a9a64a7357eb23a8eb78d63b0` |
| `preparation-audit.json` | `5d7786afee75a707c5f434cc316c5fb1199de8aed58c1a3bdda40d4cdda31c78` |
| `review-manifest.json` 所有原件逐文件 SHA/大小 | `709badd7fd3bd262ecccd3f7f041767ef6a38b284ca83ef72584750290dc8676` |

完整 launcher 的仓库审查副本为 [markingjig-phase-probe02-launcher.py.txt](markingjig-phase-probe02-launcher.py.txt)，不是历史 925 launcher 的局部补丁。新布局固定为 `C:\Workspace\SWCLI-series-20261113\markingjig-c9846f6-probe02\{code,input,output}`；拒绝已存在 base 或已有启动/结果原件。代码与输入分离，仅复制批准的十份原生文件，历史 GLB 不进入私有输入。

## 固定源码与依赖

代码 ZIP 的八个成员全部直接取自 `c9846f6aad4312cc8bf97195deaa6c4f880fda6f`，每个 Git blob SHA256 写入 proposal 与 audit：五个 MarkingJig 运行模块（control、runner、file_forensics、opening_phases、launcher_receipts）、typed loader、bridge_control、批准的 inventory。没有混入 tests、历史审查 launcher、业务二进制或 C# 产物。

`launcher_receipts` 同时存在于 ZIP 内和 launcher 相邻目录，并分别受同一 SHA 固定。离线导入检查实际从解包目录导入 supervisor，确认其 `runner.receipts.__file__` 是 ZIP 中的 helper，不能依赖主机环境或相邻私有 helper 掩盖缺失依赖。

control、file_forensics、opening_phases、typed loader、bridge_control 五份源码与 925 提交逐字相同。c984 回执修复原样保留；没有改产品或 harness。产品固定 `70d8c9ecf3c02b099ca9c2cc64fe1880061cea44`，原 driver SHA `282d75cb4a4097dac4077bb7e70af68d8278c351880d0887ce8220ba46cd36d2`，产品 archive SHA `06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53`。原 native 600 秒、group 1800 秒与外层 1840 秒界限保留。

模式只准 `probe` / `opening-transition-probe` / 零 export。原严格默认值、不可变 WorkingCopy.before、SHA/大小/全文件身份、完整 raw metadata/derived summary、完整模型/引用图/状态/配置/编辑/只读/dirty/几何观察、唯一 loaded seal 与第二次观察均保留。只使用原已审阶段规则；没有放宽未知字段或非顶层文件变化。

## 入口与真实会话检查

只准备以下短 Python 入口，**没有执行**：

```text
prlctl exec {da36dd51-bd6d-4e7a-995b-547464583302} --current-user C:\Users\YJBeetle\AppData\Local\Python\pythoncore-3.14-64\python.exe -I -B \\Mac\AllFiles\Users\YJBeetle\.codex\task-artifacts\document-properties-parallel\vm-series-20261113\markingjig-phase-probe-c9846f6-02\launch-probe.py --execute
```

不再使用长 EncodedCommand 或 PowerShell -File，不修改 execution policy。launcher 在任何私有副本准备和原生启动前，调用 root 已审 OS-only `ProcessIdToSessionId` 原型查询 **自身 PID**，保留 `ok` bool、`last_error`、实际 session，必须成功且 **SessionId==1**。这不是从 argv/USERPROFILE 推断。

相邻 `query-context.py` 逐字复制 root 已成功的 `os-python-short-04/query.py`，SHA `6755763784ae703dbed26525ec732e6c22ec9c31e504d8998ebd26d1e37cc458`。它只读查询 Python session/identity hash、未显式指定身份的 PowerShell child 实际 SID/session 与现有 native 清单，不调用 COM/WMI、不改策略。首次、紧邻 probe 前以及两次收尾均使用该固定源；原始 stdout/stderr base64 与解析数据同时保留。launcher 自身 token SID **没有直接查询**；此处明确区分自身 SessionId 与继承 child 的 SID 证据。SID/user/session 与统筹审核值不同或 native 非空，停止且不附着/清理其他工作。

## 待统筹审源后完成的前置

`proposal.json.authorized_for_CAD=false` 永远只是准备材料。默认启动或 `--check-package` 只读取、核对并编译包，不连接 VM、不初始化 NativeBackend/COM。

执行还要求 root 亲审后另建 `coordinator-cad-grant.json`，当前**没有该文件**。仅有 `coordinator-cad-grant.example.json`，其中 `authorized_for_CAD=false`、票号/用户/SID/session/时间为空，不能用作许可。正式票需绑定完整 proposal/launcher/package/helper SHA、已审核用户/SID/session1、root 的空闲确认以及新鲜原件证明。旧 OS 查询票不能通过此检查。

host 原件守护脚本审查副本为 [markingjig-phase-probe02-host-original-guard.py.txt](markingjig-phase-probe02-host-original-guard.py.txt)。统筹在新窗口明确运行 `host-original-guard.py --phase before`，对十 native 加历史 GLB 全十一份 `stable_file`/SHA/大小/完整指纹逐份核对并留新原件；每份失败都记错继续余下文件。此读操作本轮未执行。root 已有的 `source-preflight-before-phase-02.json` 是独立历史前置原件，不改写或冒充本脚本输出。

即使 guest launcher 失败，统筹仍需独立运行 `--phase after`，比较十一原件与批准 inventory 和本窗口 before 的完整指纹。私有 launcher 的 success 不代替 Mac 原件 after 与完整窗口审计；后者没有被补造。

## 离线验证

- 新包与完整 launcher 15 项通过。覆盖默认零 native、缺 helper、错 hash、重复 ZIP 成员、漏掉包内 helper、旧目录、invoke、准备文件试图自授权、缺 CAD grant、过期/错源码绑定，以及实际自身 SessionId 查询代码的成功/会话0/API失败原始回执。
- 在临时目录解包并实际导入 supervisor/typed loader 与依赖，确认包内 helper 的路径与 SHA；不调用 pinned()、worker()、NativeBackend() 或 COM。
- 执行 **新完整 launcher 的 finally AST**，注入空 case 原 acquire fatal 与 raw capture 失败。验证 fatal 保留、capture/compare secondary 分开、十输入与全部候选代码/相邻准备源码 hash 均完成，最终 inventory 与原证据复制仍发生；不制造 case 或 native 成功。
- 现有 MarkingJig 117 项、typed bridge 23 项全部通过。最终真实包 `--check-package` 返回 `package_valid=true/native_operations=0/runtime_members=8`。
- 未运行 prlctl、VM 查询/恢复/设置、COM、SW、OpenDoc、probe 或 export；没有 push/CI。

## swconst 材料已找到

用户授权向统筹询问后，统筹确认已采集目录 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-installed-swconst-20261112`。本路仅在主机重 hash：TLB `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`、PIA `1afe845af233292fe22e58a2b893d6065f36cd85f2728866011ad10771b98fa9`、copy receipt `ea1f43c24683d395c4dfd2bd42ea8f94c91fba47ecff7fd57cb4a1a1006ea2cc` 均吻合。TLB 正文未在本准备轮重新解析，实际 native 枚举 gate 仍保留，不能把主机文件验证当 native probe。
