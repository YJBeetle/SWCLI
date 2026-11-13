# MarkingJig probe04 原件前置 ZIP 接线首错（2026-11-13）

**04 停止于主机 original guard 的 ZIP 查找，candidate尚未执行。** Root原context记guest_execution_attempts=0，未建立正式grant、entry-arrived、native marker、launcher-context或native-output；没有GetBodies3/CAD尝试。20:08后的原host receipt显示running、Pause idle:on，cleanup_errors=[]。这些是04历史回执，不表示后来实时VM状态。

打包时沿用的 `host-original-guard.py` 第35行仍打开 `markingjig-code-c9846f6.zip`，而04唯一源码包已改名为 `markingjig-code-a7ecb97.zip`。缺失旧ZIP导致原 `FileNotFoundError`。它发生在第38行 `for name,pinned in protected.items()` 读取十一原件之前，因此 **没有完成04的新十一原件before/after证明**，不能借03旧结果补成04原件守恒。

我在04打包时漏改这一跨文件引用。22项离线检查确实通过了已有测试，source blob/hash核验也一致，但只编译/校验guard源，未实际执行其ZIP路径解析。这些结果不能证明host original前置可用。来宾 `--check-package` 成功、8members/native_operations0 与此缺口同时成立，不能把它升级为整个前置通过。

Root此次实际运行了一个OS-only guest查询与一次guest `--check-package`；**0 guest candidate execute不等于0 guest commands**。该首错是主机包引用接线失败，不能写成GetBodies3封送或native API失败，也没有新的模型/配置/几何或导出结论。

## 原件与独立审计

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-a7ecb97-04`，未改其中任何文件。

- 原 `host-execution-context.json` SHA `dab0890bf6f960ade03f097b9c734c6d7059540a493cd8e0d1f2e2c9d7cd1a48`；其中外层首错仍是 `RuntimeError: host-originals-before exit 1`，原traceback完整保留。
- guard原stderr SHA `d7b7a6753768016637000359c95b8cc5873d6101600f13f069537bd2abaedfc3`，内层原 `FileNotFoundError` 与旧ZIP绝对路径保留。
- guest包检查stdout SHA `f41ae813eb1508c5debd8b68b567fbdc09a974112222700dba66b250dc6e1cf8`；idle恢复成功与host-after原件SHA均在审计JSON。
- [独立审计JSON](../evidence/glb-markingjig-probe04-preflight-failure-2026-11-13.json) SHA `a6daac3b96e70d9f76e8ce5d0390b6ee5a1aa117e1c778a4c2490be3841c682e`；[可复现只读审计](audit-glb-markingjig-probe04-preflight-failure.py)。只读现有host原件与guard AST，不执行guard、导入runtime、读取业务原件或连接VM。

审计重hash确认冻结02/03/04各七份准备文件与各自原manifest一致。04 proposal仍 `6207272a6b64ac8c002b02f90514d14f6f6c1904b9f12ffa62f64daa22f2db07`、launcher仍 `d0213bbdc6ae58f38fe9f360e38f1b9f5c78b9c41e2279cc10f14ba355b685d6`、ZIP仍 `c2bfad896fdf0205548b1e9534377d9d459fb2b961a43f6c616dfbe01cc9196a`。原source a7及产品70d8c9e不变。

## 接手边界

本路只归档本次首错与覆盖缺口，没有修改冻结04、重复修复、VM/COM/CAD动作、push或新CI。Root另建全新05，仅修正guard ZIP引用并补实际ZIP解析前置，沿用a7 runtime与全部原保护；05的修复、前置、签票、执行和结果由Root单独审阅归档。本审计不为05出具执行许可或通过结论。
