# 出详图 next 首轮交接

- 唯一工作树 `/Users/YJBeetle/.codex/worktrees/docprops-detailing/SWCLI`；分支 `codex/docprops-detailing-next`；基线远端 main `31ad9c256a5a106bc94a627cd41dfd6277bb6f00`，创建前已核一致、工作树 clean、无 `.codegraph`。
- 候选生产代码 head：`32fc9ff0797e224795415e03a343746516462cc8`；尚未取得新字段原生验收，不可当作本次发布内容或 merge-ready 提交。
- 上一批分支 `codex/docprops-detailing` 的 `613ba98` / 验收 `85f99da` 未改写；旧 handoff 及原 ZIP hash 再核记录在 `artifacts/detailing/frozen-20261114/`；原件仍在原持久 evidence 目录。
- **本批排除当前发布，NATIVE_ACCEPTED=false、MERGE_READY=false。** 无待审批动作；首轮不使用 VM/COM、不手动 dispatch 原生 CI、不合 main、不改版本/tag/release，也不修改 DockerSW/MacSW。

## 已实现

- 新增中心线自动插入和孔阵列中心标记连接线两个文档默认 Toggle，官方依据/边界/CLI 示例及目标原生计划见 `docs/design/document-detailing-lines-next.md`。
- 新 `document.detailing-line-options` / `document.detailing-line-option-set`，CLI 同名入口，SDK/MCP 合同接线。
- 快照含两个新值及两个旧只读保护值，完整四布尔 CAS；新 writer 仅接受两个新字段，显式文档、stamp、lease 必需。
- 新白名单为空，所有新 set/no-op 返回 write_enabled=false / mutation 未尝试；不继承旧 33.5.0 放行。
- 候选原生路径已实现只读/后台/身份/编辑模式/dirty/stamp/未请求字段保护、单次 setter/dirty 标记及首失败/partial 回执。worker 恢复失败退休，late validation 不丢可信 mutation。
- 旧两字段合同不变；共享类型库 resolver 按 profile 解析，旧接口不依赖新枚举；不修改旧原生白名单。

## 首轮便携验证与提交

- 新增 18 项便携测试；连同旧出详图测试共 38 项关联检查通过。
- 完整便携回归 2984 项通过，39 项按环境跳过；Python 3.14/macOS，未调用真实 COM。
- SDK 生成一致、6 个源文件 strict 检查及 38 个类型拒绝用例通过（沿用主 CI 的 mypy 1.x 约束；本地 1.20.2）。首次工具 2.x/Python 3.9 不兼容及新增类型用例作用域问题已在类型检查内解决，不涉及原生 API。
- `git diff --check` 通过，旧 catalog、旧交接/验收 JSON、所有 CI workflow、版本文件与指定 main 相同。
- 日志与 SHA256 回执持久保存在 `artifacts/detailing-next/portable/` 及 `portable/receipt.json`。候选源码为 `32fc9ff0797e224795415e03a343746516462cc8`；code/contract patch SHA256 `f7091b508cee7c999e2349cc39df4e85e5673406ca4abbdcde8c6ed7f3f09a3f`，原 patch 位于 `artifacts/detailing-next/code-and-contracts.patch`。
- 测试均为假宿主、假 COM 模块或模拟传输，不属于原生证据；没有新 run/artifact/digest 可冒充原生验收。

共享修改：`document_detailing.py` 的旧 catalog 不变；`hosts/windows_document_detailing.py` 仅增加 profile 参数，旧默认逻辑保持；新增独立 catalog/adapter；CLI、operation/result schemas、daemon handlers、worker preference receipt allowlist、生成 SDK 和类型用例。

现有 CI workflow、版本文件和 release 逻辑保持原样。源码推送可能触发仓库既有自动便携 CI；本线程不手动调度、轮询或等待新的原生运行。

## 未验收与所需排程

- 新枚举的真实 ID、原生 getter/真假 setter 返回语义、完整四值独立持久化及真实公开链路均未验证；写入继续关闭。
- 原生计划为单 host/worker，8 条新布尔有向转换、旧两个标量不变、逐次独立保存/只读重开，600 秒 native/1800 秒组预算，首失败原件保留。详见设计文档；独立目标脚本已在后续增量补齐。
- 无新的 run/artifact/digest；上一批 run/原件只证明旧两项，不得借用来放行新字段。
- 不验证具体视图/实体自动标记效果；大装配条件的实际插线行为、其他字段/版本/Wine、完整发布均在范围外。


## 独立原生门禁准备增量

统筹后续授权限定为实现和离线验证，继续同一 next 分支；无 VM/COM、无原生 CI、无白名单放行。新增 internal-only 计划、原生后端及 600/1800s 有界包装器；具体入口/约束见设计文档最后一节。没有新增 workflow 或公开门禁。

计划从实际初始值遍历 8 条有向边，旧两值保持；每次保存独立原件，关闭须证明 native catalog 和旧 ID 失效，只读/可写重开均需全新 ID，核完整四值、布局/前台/dirty 与文件摘要。原始错误/partial 回执在校验之前持久保存；后续清理故障单列，首错停止且不重试。门禁不读取旧成功报告，缺任何新字段或 trace 一律失败。

新增离线测试包括全部 16 种初始四值组合和多种失败注入，以及真实 registry/handler/adapter/result schema 配合模拟对象的拒绝/trace 检查。新增 11 项 gate 测试，关联 49 项已通过；完整便携回归 2995 项完成，39 项按环境跳过。完整回归后最后补强的 trace/零 stamp/请求回执约束由最终 49 项关联复跑通过；生产源码未变。日志独立保存在 `artifacts/detailing-next/portable/gate-*.log`，不替代首轮原日志。第一轮新增 gate 测试发现的是假宿主初始值共享引用，已修正；该失败日志保留，不是原生失败。

当前 `NATIVE_ACCEPTED=false`、`MERGE_READY=false` 和排除当前发布范围不变。下一步由统筹亲审新增门禁，并决定未来是否授权执行；本轮不等待 CI，也不创建自动化。

门禁准备代码 head：`6945b23d5b9b1cf57e731cc3a5afdf0cdba2c973`；生产候选仍为 `32fc9ff0797e224795415e03a343746516462cc8`。增量 patch `artifacts/detailing-next/gate-preparation.patch`，SHA256 `c48c6257d05dc8145f3926aa0de6b2c2526888ea1c7cab71cff9cbdcf1be922a`；本轮日志和源文件摘要记录在 `artifacts/detailing-next/portable/gate-receipt.json`。四个新增 Python 文件均通过 Python 3.9 语法解析，两个入口的 isolated `--help` 通过；未调用原生入口。旧两份原 ZIP 摘要再次核同。


## 2026-11-21 现行基线复审

候选已纳入复审期间更新的远端 main `2e18509d1bc055bb630f63b43a5a81cd23123679`，保留此前分支提交和原件。此次代码候选为 `02fd2802082a64b15427d5a65a6c9cf58fcd63a4`。装配只读查询和出详图两路类型检查用例均并入联合 SDK。门禁支持将实际安装的 wheel、候选 checkout 和报告绑定到同一份包内容。每次重开另用原生文档路径核对同一保存文件，轨迹按实际 getter、setter 和 dirty 顺序核验，报告采用原子替换保存。首个诊断故障保留操作结果和 partial 回执，watchdog 同时核对已完成的阶段耗时。

两个新默认选项写入仍关闭。官方 2025 文档将 setter 返回值描述为 on/off，原生阶段须重点核实 false 方向。候选遇到非严格 True 会在首个失败点停止并保留返回及回执。安装型内部命令、证据归档要求和预计 35–40 分钟独占窗口见[设计与验证计划](../design/document-detailing-lines-next.md)。

Python 3.14.10/macOS 便携回归 3113 项完成，31 项跳过。关联 49 项、SDK 严格检查及 43 个类型拒绝用例、Python 3.9 语法和隔离入口帮助检查通过。最终 wheel 的 138 个包内文件与 checkout 和安装字节一致，离线注入额外文件或错误内容均被拒绝。初次全量因重建环境缺少 PyYAML 出现 5 项环境错误，补装主线 CI 所需依赖后全量通过。日志、候选差异和轮包摘要存于 `artifacts/detailing-next/review-20261121/`。本次候选仍需 Windows 原生证据，生产写入白名单为空。

## Windows 首次启动诊断与监督修复

首次尝试使用 `2f56038f2ad785b95816cb2330e656755c16fe5e`。原 `watchdog.json` 记录 `Popen.pid=7796`、worker 退出码 2、耗时约 1.04 秒。原 stderr 来自 COM 前的直接父 PID 检查，进程退出后没有 SOLIDWORKS 残留。原始证据位于 `document-properties-parallel/vm-native-20261121/detailing/guest/evidence/`。原报告未记录当次完整 PID 链。

随后单独的 Windows 只读启动探针记录了监督器 PID 5252、由 Popen 启动的 venv 重定向器 PID 6464，以及父 PID 为 6464 的实际 worker PID 4324。两个解释器均保留了相同的 venv。原探针 `vm-native-20261121/parent-pid-probe.log` 的 SHA256 为 `8ba4043da67c59dfef577dcecb9fb2d03fcd10be89585c9326dc235a118d0b29`。

候选按 CPython Windows multiprocessing 的启动方式直接创建基础解释器，保留 venv 路径初始化。worker 核对实际和声明的父 PID、管道中的 Popen PID 与自身 PID，以及 Windows 报告的实际进程映像。缺少启动管道时拒绝直接执行。正式门禁与无 COM 的 `--supervision-probe` 使用同一校验。仍按 600 秒阶段、1800 秒组上限执行。

macOS 关联离线测试 51 项通过，Windows 进程专测 1 项跳过。首跑一项离线夹具缺少管道上下文管理器，修正后重跑通过。下一次验证须使用新候选 head 和新的证据目录。产品写入仍关闭。

## Windows 内部验收通过与公开候选准备

统筹单次执行精确 `34baf8e862eaf2d991b3d1082407eb660581a872`，独立复核实机报告和原件。Windows SOLIDWORKS `33.5.0`，监督器生命周期约 57.60 秒，正常退出。八次 setter 都返回 True，四次写入 false；八份原图各作只读和可写重开，四值一致，16 个身份各不相同，经重算 SHA256 与原报告和独立审计一致。旧孔标记 true、旧圆角标记 false。摘要见 [实测清单](../evidence/detailing-lines-internal-20261121.json)。原件保留独立的 `batch-02/detailing/guest`，不覆盖上次 pre-COM 错误。

公开候选在此独立分支按上述精确 revision 和旧值组合启用两个 scoped setter。所有其他旧值组合、其他 revision 及 Wine 仍拒绝。联合四值 CAS、原生调用严格 True、部分修改回执均保留。新增 `--public-gate`，通过安装型 CLI 做八次写入和保存重开，通过 SDK/MCP 检查读取、能力及同值请求。实机公共门禁由统筹分配 Windows 资源。证据和执行方式在[设计与验收计划](../design/document-detailing-lines-next.md)中，本候选排除当前发布。
