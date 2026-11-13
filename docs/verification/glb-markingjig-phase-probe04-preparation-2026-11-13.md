# MarkingJig probe04 完整冻结审查包（2026-11-13）

**prepared / 未执行。** 本路本轮 VM/COM/CAD、业务原件读取/复制、push/新CI均为0。Root亲审执行；此包不签发CAD票，也不允许invoke。冻结02/03的七份准备文件均按各自原manifest重hash相同，旧03配置首错不改绿。

持久目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-a7ecb97-04`

| 文件 | SHA256 |
| --- | --- |
| `proposal.json` | `6207272a6b64ac8c002b02f90514d14f6f6c1904b9f12ffa62f64daa22f2db07` |
| 完整 `launch-probe.py` | `d0213bbdc6ae58f38fe9f360e38f1b9f5c78b9c41e2279cc10f14ba355b685d6` |
| `markingjig-code-a7ecb97.zip` | `c2bfad896fdf0205548b1e9534377d9d459fb2b961a43f6c616dfbe01cc9196a` |
| 独立与包内 `launcher_receipts.py` | `eee85b44ae188233f5b65994c6ef4e26c745f214e24893c80ddc874467b329e0` |
| `preparation-audit.json` | `3ca13d69451ba5854ff9a6b83888df80a63b739f4c9060d6833d91d1d2e5924a` |
| `review-manifest.json` | `75ce7f86d017c179cd3e3ab19d0f5c730482d2c9090a3e46bb5f9c8334fc1970` |

完整源：[launcher](markingjig-phase-probe04-launcher.py.txt)；对冻结03的差异：[零上下文diff](markingjig-phase-probe04-launcher.diff)（应用需 `--unidiff-zero`）；[22项离线检查](check-markingjig-phase-probe04.py)。manifest包含全部准备源、测试、diff与audit的逐文件hash/大小；proposal包含全部8个Git blob的SHA。

## 固定范围

八成员ZIP逐份独立与 `a7ecb97d30f0913105080d93e1725acea6e67ce7` 精确Git blobs比对一致；未从可变工作树拼包。产品仍 `70d8c9ecf3c02b099ca9c2cc64fe1880061cea44`，原driver SHA `282d75cb4a4097dac4077bb7e70af68d8278c351880d0887ce8220ba46cd36d2`，产品archive SHA `06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53`。

新guest base：`C:\Workspace\SWCLI-series-20261113\markingjig-a7ecb97-probe04\{code,input,output}`。旧03路径和票尾号已换为04。source runtime未修改；full launcher仅更新head/路径/ZIP，并将新组件策略绑定到proposal、grant、记录和唯一candidate argv：

```text
--mode probe --phase-policy opening-transition-probe --component-context-policy component-bodies-probe
```

proposal必须 `authorized_for_CAD=false`、export_permitted=false。正式grant另由Root创建，必须精确绑定proposal/完整launcher/package/helper SHA，以及modeprobe、opening-transition phase、component-bodies-probe、export_permitted=false；缺policy、strictpolicy、invoke或export许可均拒绝。示例grant仍false/空票号，不能授权CAD。

沿03全部保护保留：读取proposal/grant前独占entry marker、真实自身SessionId1与raw bool/last_error、固定短current-user Python入口与继承child SID/session检查、新鲜空闲native[]、11Mac原件独立before/after、10普通独立readonly copies及全SHA/完整身份、source/产品固定、原模型/全图/geometry/CAS/phase门禁、独立收尾和全部hash继续、600/1800/1840预算。没有另加CAD入口、API fallback或重试。

## 离线结果

实际持久检查脚本 **22项全部通过**，实际包 `--check-package` 返回 `package_valid=true/native_operations=0/runtime_members=8/component_context_policy=component-bodies-probe`。独立再核ZIP所有成员与a7源码逐字相同。

沿原18项检查，并补proposal policy缺失/错值、完整合成grant的纯metadata正例、grant漏policy/错policy/invoke/错phase/export拒绝，以及从完整源码AST选择实际candidate argv、断言唯一、逐项验证三种policy仅出现一次。AST根据常量 `--component-context-policy` 精确选择，不能误取内部OS查询argv。测试只复制七份固定准备文件到临时目录，不复制后续native原件或把原件当测试回执。

实际导入包内supervisor/receipt helper/phase/forensic/typed loader，验证包内helper路径与SHA；不调用worker/pinned/NativeBackend或COM。完整新launcher finally AST仍用假OS与临时文件验证空case原fatal、capture/compare失败后全部输入/代码/准备源hash、最终清单和原证据复制继续。所有合成身份/proof仅在临时测试目录，不写正式grant或native marker。

## GetBodies3 native类型证据边界

已核已有主机归档：`document-properties-parallel` 下JSON/TXT回执（排除庞大launcher-context）没有GetBodies3 native类型描述记录；TLB/OLB文件名中只找到swconst.tlb，它是枚举来源，不能当GetBodies3接口native TYPEDESC证据。此结论限该已知归档范围。

已有证据为 [固定装机PIA契约](../evidence/glb-markingjig-component-PIA-contract-2026-11-13.json)，SHA `d768a8ed4ba49402518cded01011310846e6f2380c71f0d9a14b502cd68730a3`：33.5.0.53、GetBodies3 DispId124、Object& IsOut SafeArray，SafeArraySubType0未指定。它与合成binding AST测试均不证明实际Python封送已通过。没有取得GetBodies3 native TYPEDESC/IDispatch type metadata，没有新增任何VM/COM metadata动作或另试参数。按Root当前决定，仅供亲审现有明确BYREF候选，实际失败仍首错停止。

## 可复现检查与待审入口

主机离线检查（已运行）：

```text
python3 -I -B /Users/YJBeetle/.codex/worktrees/glb-export-repair/SWCLI/docs/verification/check-markingjig-phase-probe04.py
python3 -I -B /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-a7ecb97-04/launch-probe.py --check-package
```

Root完成fresh原件/OS/空闲/身份前置、亲审并签发新短时grant后，才由Root执行下列短入口；本路没有运行：

```text
prlctl exec {da36dd51-bd6d-4e7a-995b-547464583302} --current-user C:\Users\YJBeetle\AppData\Local\Python\pythoncore-3.14-64\python.exe -I -B \\Mac\AllFiles\Users\YJBeetle\.codex\task-artifacts\document-properties-parallel\vm-series-20261113\markingjig-phase-probe-a7ecb97-04\launch-probe.py --execute
```

拟议 `VM-20261113-MARKINGJIG-PHASE-PROBE-04` 不是现成许可。即使private launcher返回成功，仍需Root独立Mac after与全窗口审计；probe也不是导出验收。

## 后续实际前置失败（保留上方准备快照）

Root执行04前置时，guest check-package通过，但host original guard仍引用旧c984ZIP，FileNotFoundError发生在十一原件采集循环之前。candidate执行0、无grant/entry/native回执、idle恢复on；04没有新的十一原件前后证明。22项离线checks与包hash通过只覆盖准备快照，不能称完整前置通过。冻结执行文件不改；Root另建05处理唯一接线修复。详见[原首错与独立审计](glb-markingjig-probe04-preflight-failure-2026-11-13.md)。
