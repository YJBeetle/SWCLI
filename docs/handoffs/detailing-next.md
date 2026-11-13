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
- 原生计划为单 host/worker，8 条新布尔有向转换、旧两个标量不变、逐次独立保存/只读重开，600 秒 native/1800 秒组预算，首失败原件保留。详见设计文档；统筹批准排程后再补目标脚本/入口。
- 无新的 run/artifact/digest；上一批 run/原件只证明旧两项，不得借用来放行新字段。
- 不验证具体视图/实体自动标记效果；大装配条件的实际插线行为、其他字段/版本/Wine、完整发布均在范围外。


## 独立原生门禁准备增量

统筹后续授权限定为实现和离线验证，继续同一 next 分支；无 VM/COM、无原生 CI、无白名单放行。新增 internal-only 计划、原生后端及 600/1800s 有界包装器；具体入口/约束见设计文档最后一节。没有新增 workflow 或公开门禁。

计划从实际初始值遍历 8 条有向边，旧两值保持；每次保存独立原件，关闭须证明 native catalog 和旧 ID 失效，只读/可写重开均需全新 ID，核完整四值、布局/前台/dirty 与文件摘要。原始错误/partial 回执在校验之前持久保存；后续清理故障单列，首错停止且不重试。门禁不读取旧成功报告，缺任何新字段或 trace 一律失败。

新增离线测试包括全部 16 种初始四值组合和多种失败注入，以及真实 registry/handler/adapter/result schema 配合模拟对象的拒绝/trace 检查。新增 11 项 gate 测试，关联 49 项已通过；完整便携回归 2995 项完成，39 项按环境跳过。完整回归后最后补强的 trace/零 stamp/请求回执约束由最终 49 项关联复跑通过；生产源码未变。日志独立保存在 `artifacts/detailing-next/portable/gate-*.log`，不替代首轮原日志。第一轮新增 gate 测试发现的是假宿主初始值共享引用，已修正；该失败日志保留，不是原生失败。

当前 `NATIVE_ACCEPTED=false`、`MERGE_READY=false` 和排除当前发布范围不变。下一步由统筹亲审新增门禁，并决定未来是否授权执行；本轮不等待 CI，也不创建自动化。

门禁准备代码 head：`6945b23d5b9b1cf57e731cc3a5afdf0cdba2c973`；生产候选仍为 `32fc9ff0797e224795415e03a343746516462cc8`。增量 patch `artifacts/detailing-next/gate-preparation.patch`，SHA256 `c48c6257d05dc8145f3926aa0de6b2c2526888ea1c7cab71cff9cbdcf1be922a`；本轮日志和源文件摘要记录在 `artifacts/detailing-next/portable/gate-receipt.json`。四个新增 Python 文件均通过 Python 3.9 语法解析，两个入口的 isolated `--help` 通过；未调用原生入口。旧两份原 ZIP 摘要再次核同。
