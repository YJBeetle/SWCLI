# MarkingJig probe03：仅新目录与入口到达观察（2026-11-13）

**prepared / 未执行。** 本路本轮 VM、COM、CAD、业务原件读取/复制均为 0。probe02 的七份冻结准备文件逐份与原 manifest 重 hash 相同，原失败与 root 后续对照原件均保留。未写中央调度或签发 CAD grant。

新包目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-c9846f6-03`

| 文件 | SHA256 |
| --- | --- |
| 完整 `launch-probe.py` | `0526dd21e9699be7f737861e4c66efe273fa6f547f3cec657894c041f4e2b968` |
| `proposal.json` | `d62fcf8648089a8de683e45c505b502917bace0fb91cdefd835d690756fc7276` |
| `markingjig-code-c9846f6.zip` | `c1bf4c6a2edf19faa680b18b30115170a6bf121ce65d1cdcb7fe9daeff7a54ae` |
| 独立与包内 `launcher_receipts.py` | `eee85b44ae188233f5b65994c6ef4e26c745f214e24893c80ddc874467b329e0` |
| `preparation-audit.json` | `5002847e034ae5e451261b42487dcdfdb0bf25ef5e68e654252f057402b0f73b` |
| `review-manifest.json` | `4c15f8999211fa7ed021d15ac96bcb939185435a5791898b04f23f0f8081651c` |

完整差异：[launcher diff](markingjig-phase-probe03-launcher.diff)；完整源：[launcher](markingjig-phase-probe03-launcher.py.txt)；离线入口：[18 项检查](check-markingjig-phase-probe03.py)。

仅将 proposal/host share/guest base 与票尾号换成03，并新增 `write_entry_arrival`：显式 `--execute` 时在读取 proposal 和 grant 前，以 `open('x')` 写 `entry-arrived.json`。字段只含自身 PID、实际 argv、入口源码 SHA、UTC，以及既有 Win32 `ProcessIdToSessionId` 查询的 bool/last_error/session 或原始异常。无 COM，不能借该记录授权 CAD。默认或 `--check-package` 不写入口回执。

入口到达回执存在证明该 Python 入口已到达；回执缺失不能单独证明 Python 未启动，因为标准库导入、源码读取或回执写入也可能先失败。原 actual session1 gate、grant、独立 postchecks、600/1800/1840 预算和十私有输入/十一 Mac 原件保护均未改变。runtime ZIP 与 probe02 **逐字相同**，仍是 c984 八文件包；产品与原 driver 仍固定70d8c9e与原SHA。未改模型 API、phase 或 harness。

## 已有运输层证据

Root 的 probe02 envelope 在0.165秒返回 `PrlJob_GetResult: Invalid argument`，无 launcher-context、native marker 或输出。原十一份 before/after 证明通过，idle 已恢复。只确认 envelope 失败与未观察到 launcher/native 执行，不归因为某次 COM 调用。

Root 的 `os-argument-envelope-05/report.json` 中，无参数与追加 `--execute` 两条 OS-only 入口都 exit0/session1；同目录 `exact-launcher-check-package.json` 显示 **probe02 精确 launcher 路径** 加 `--check-package` 也 exit0、八成员、native_operations0。故不能宣称 `--execute` 本身不被支持、路径不可访问或已定位唯一根因。原件 SHA 全部写入本包 audit；未改原件。本轮没有进行任何新的运输层/原生重试。

## 交统筹的命令（均未执行）

主机离线验证：

```text
python3 -I -B /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-c9846f6-03/launch-probe.py --check-package
python3 -I -B /Users/YJBeetle/.codex/worktrees/glb-export-repair/SWCLI/docs/verification/check-markingjig-phase-probe03.py
```

统筹亲审后，另行签发新短时 CAD grant 并完成 fresh 原件/空闲/用户会话前置，才可由统筹执行以下唯一入口：

```text
prlctl exec {da36dd51-bd6d-4e7a-995b-547464583302} --current-user C:\Users\YJBeetle\AppData\Local\Python\pythoncore-3.14-64\python.exe -I -B \\Mac\AllFiles\Users\YJBeetle\.codex\task-artifacts\document-properties-parallel\vm-series-20261113\markingjig-phase-probe-c9846f6-03\launch-probe.py --execute
```

当前仅有 `coordinator-cad-grant.example.json`，其 authorized_for_CAD=false、票号为空；没有正式 grant 或 arrival/native 回执。拟议票号 `VM-20261113-MARKINGJIG-PHASE-PROBE-03` 只作审查建议。

## 离线结果

18 项全部通过：复用原15项并适配新入口，包括缺 grant 时入口步骤先发生且仍拒绝 CAD；新增 proposal 读取失败前入口顺序、API失败 raw bool/last_error 与独占回执不覆盖、API加载异常保留。临时目录中实际导入精确包内 helper，并对新完整 finally AST 注入空 case 原 fatal 与 capture 失败，独立 hash/最终清单/原件复制仍完成。原 runtime 源码没有改动，没有把之前117+23单元测试或这里18项离线结果称为 native probe 通过。

实际主机 `--check-package` 返回 `package_valid=true/native_operations=0/runtime_members=8`。probe03运行源码及相邻准备文件现已固定，供统筹亲审；本路不碰 VM。
