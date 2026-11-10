# 42664223806 超时原件与前端开销提案（待统筹审阅，未实施）

## 原件与真实首因

[42664223806](https://github.com/YJBeetle/SWCLI/actions/runs/42664223806) / head `64af40c908c01ca20027d06799eaec702627e5ee` 为 **failure**。官方 artifact `13698368440`，22180727 bytes，官方 digest 与下载 SHA256 同为 `5ac6169f03d869379d349e48c116d5ec7a204f7ab47d7fe68f7f933c875f34a9`。原报告 SHA256 `a3d4228f24e140e41fe9053c76b09c4152d06e6f3eb44c1f28d52b1a81e751ab`。

原 ZIP、官方日志 ZIP、解压原件及整作业日志在 `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-noop-42664223806/`；metadata、完整独立审计和时间分布在同名 `docs/evidence/`。原件不修改，旧失败不翻绿。

首因是公共组 watchdog `RuntimeError: public group exceeded 1800s`，最终组1801.344秒。154个完整 changed case：CLI139（part46/assembly46/drawing47），SDK15（part15），MCP0。SDK第16个case angular.precision=1：报告仅source-preflight；原始wire JSONL有source open成功回执，紧接document.create请求已持久记录。native trace有该create operation end，但wire响应未落盘，不能认为整个操作或case成功，也没有第155次setter。

上次 CLI117 drawing mass_properties.length_unit 的inch问题已在本次CLI真实通过：源仍inch/native3，合法mm/native0写入成功，后置noop changed=false、mutation=false，完整snapshot/document/stamp/dirty状态一致；不外推至未到达的SDK/MCP drawing。

独立审计逐项核154个完整源/完整后态/raw5/19linkage、fresh只读重开和状态、308份source/saved原生文件hash。实际lease/stamp/fullCAS/readonly各154个拒绝、closed域128个拒绝与真实owner token/不同session关联。122次part几何比较，68次nonexact原值保留；V/S/body count精确，质心仅原批准逐轴绝对≤1e-12mm，无relative。

633590条native trace、154个setter begin；308个error均为预期lease/stamp operation级拒绝，**native API error=0**，最大完成边界1.781秒，单worker。内部139成功466.906秒/owned正常退出，单独记录不补公共缺口。

公共超时kill验收进程后，一次daemon stop返回ActiveDocument（仍有打开文档）。随后只终止了保留的Python daemon进程，`owned_native_exit_confirmed`缺失、`pids_after`未采样；不能以公共CLI报告尚存cleanup_errors=[]宣称native退出或清理通过。这是首因后的清理次因，不替代1800秒首错。

## 已测时间分布

| 路径 | 完整case | case累计秒 | 调用数 | 调用累计秒 | case中位秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CLI | 139 | 1657.457 | 4677 | 1594.368 | 11.719 |
| SDK | 15 | 90.562 | 538 | 45.322 | 5.969 |
| MCP | 0 | 0 | 0 | 0 | 未到达 |

CLI lease1504次/416.779秒，unit-profile695次/236.298秒，unit-profile-set948次/324.464秒；完整逐operation统计以independent-audit.json为准。SDK对应lease164次/3.278秒、profile75次/6.172秒、set104次/9.432秒。CLI多次独立启动的非native成本显著，但此跨路径差值不是纯启动时间的直接测量。

SDK15的case时间比transport调用多约45.240秒，含完整报告检查点、json/校验/日志/调度等，不能全部归因序列化。完整报告已经25999056 bytes；当前每semantic checkpoint反复编码不断增长的完整历史。

若简单按SDK前15步平均外推139，仅CLI+SDK就约2496.7秒，尚不含MCP；这是解释当前策略不足的粗略推算，非未来Windows时长保证。没有调整600/1800、步骤、lease TTL或调用策略来掩盖该结果。

## 离线基准与证据限度

`offline-overhead-benchmark.json`：本机macOS/Python3.14，20次真实 `python -I -m swcli` subprocess调用与20次父进程直接 `swcli.cli.main` 函数调用，均重新构造真实parser，每次真实TCP到假daemon并检查完整CLI JSON和requestID。每模式20请求、零重发。中位数分别0.146257秒和0.005743秒。

**函数直调仅是开销下界。它不是CLI子进程，不是已经实现的常驻CLI前端，更不能作为逐次启动CLI或CAD验收证据。** 尚未证明常驻IPC协议、失败隔离/超时、Windows性能或417步总时长。

`offline-serialization-python312.json`：使用现有本机CPython3.12.16（hosted是Windows3.12.10，只匹配major/minor），对同一原报告各5次完整编码、写入、flush/fsync再回读。原缩进JSON中位0.349493秒、紧凑等价JSON中位0.083380秒；字节25999056→19307244，每次完整解码内容相等。Python3.14对应两者约0.09/0.08秒，差别远小于3.12，不能混用运行时结论。均是本机离线测量，不是Windows优化后的证明。

## 最小方案，尚未实施

1. **只在WriteGate完整semantic报告持久化中去掉JSON缩进**。相同检查点、相同全部字段/完整历史、相同flush/fsync，原始wire每次请求/响应仍独立fsync。最终报告也不省字段，不改raw数值/hex/partial回执；不做分片格式迁移、不删重复守护。其他read/native calibration/其他路线的durable helper不动。此项只改变文本空白和编码成本。
2. **CI专用、单个长寿命CLI前端子进程，待root决定是否接受验收策略变化**。原策略是每command独立 `python -I -m swcli`。候选策略是一个 `python -I <CI helper>` 子进程导入已安装wheel的 `swcli.cli.main`，每帧按原argv调用真实main，保留每次真实parser/参数处理、TCP RPC和原始stdout/stderr/returncode。它不是每command独立启动CLI：将失去每次冷启动/模块初始化与进程隔离的覆盖。不得标为逐次启动CLI，不改名SDK或父进程直调来冒充CLI。
3. 该helper只处理原CLI阶段/既有CLI清理命令，SDK仍真实typed Client、MCP仍真实stdio frontend。helper不调用SDK、daemon handler或COM；每个输入只执行一次原CLI main，不合并多个业务请求。保留第一次原生错误和不确定结果，无重试、无helper重启、无CAD重启/回滚。
4. IPC拟采用单请求单响应的显式序号/帧边界，记录前端PID、Python/wheel路径版本和helper SHA，EOF/畸形frame/序号不符/无回复一律停止并保留已读原始字节。stdout/stderr/退出码按原CLI捕获；异常/SystemExit也需回执，不能吞掉解析拒绝。600秒请求与现有CLI外层grace仍保留，整组1800从原点计时，前端创建/关闭也占同组预算。
5. 一个CLI前端保留到整个public cleanup结束，只关闭一次并等待持有进程退出，不在SDK/MCP失败时创建替代CLI前端。daemon生命周期仍由原owned wrapper负责。可保留一次真正独立进程的CLI启动/只读smoke，但它只证明该次启动，不可替代139次冷启动，也不新增setter或fixture组。

第2项必须由root明确接受这种前端策略边界后才可实施。若必须保留4677次独立CLI进程，则需要另审产品冷启动依赖/导入性能方案；单靠compact JSON不能证明可在1800秒完成。当前没有实施任何候选、没有新的portable修复或public dispatch，也未碰VM（root统一占用）、产品合法域、geometry、main或其他路线。

## 实施前后的验证约束

若root认可策略，先以真实TCP假daemon做独立子进程对照：同argv逐次进程/常驻helper的read、合法changed/native回执、非法enum、lease/stamp/CAS/RO/closed-domain返回完全一致；每输入恰一RPC；保留原始stdout/stderr/partial；验证异常、EOF/超时、协议帧破坏不重发或重启，前端一次关闭。证明实际使用真实CLI main而非SDK/handler替身，明确cold-start覆盖已变化。

报告编码需对原26MB报告和含raw double/hex/错误/未知结果数据做完整typed回读一致、持久化失败和原始首错保留检查。关联回归、完整portable、SDK生成/语法/diff检查通过后，才由必要新head启动一次公共139×3验收；正常一次快照即停。能否在原预算完整通过须以新Windows原件为准，离线基准不能承诺。

## 复现命令

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
python3 docs/verification/audit-units-public-budget-42664223806.py --archive /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-noop-42664223806/original.zip --metadata-dir /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/evidence/units-profile/public-noop-42664223806
PYTHONPATH=src /private/tmp/swcli-units-write-env/bin/python docs/verification/benchmark-units-public-overhead.py
/opt/homebrew/bin/python3.12 docs/verification/benchmark-units-public-serialization.py --report /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-noop-42664223806/original/swcli-native-smoke/units-public-acceptance/cli/public-unit-profile.json --output /private/tmp/units-serialization-replay.json
```


## 后续状态

以上是保留的原审阅提案。统筹随后已明确接受CI前端复用、额外三类真实冷启动只读探针及受限句柄清理方案；实施与最终本地验证见 `units-public-budget-fix-review.md`。旧失败、时间分布及离线测量不改变，仍无新公共通过证明。
