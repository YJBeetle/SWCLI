# 文档属性独立覆盖与校准（v1）

基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`；机器矩阵见
`docprops-capabilities-v1.json`，只读工作树快照见 `docprops-worktree-inventory.json`。
主集成树包含未提交文件；`1593330` 是本地未验收快照，不是发布来源。
本分支不导入其中产品功能，也不判定其他分支通过。

## 公共能力边界

| 范围 | 基线公共入口 | 本分支验证 |
| --- | --- | --- |
| 文件摘要/自定义属性 | summary、summary-set、properties、property-summary、property-add/set/delete | CLI 参数→SDK 参数→MCP execute，含 Unicode、空串、0、配置作用域及上下文 |
| 长度显示单位 | units、units-set | mm/inch、0–8位十进制的既有契约；不代表完整单位系统 |
| 注释七标量 | annotation-options、annotation-option-set | bool/enum/数值传递；不代表字体与子类型 |
| 字体、显示、标准批次 | 主集成树六操作 | 本分支未导入；未独立验收 |
| 九个并行工作范围 | 详见版本化矩阵 | 全部保持 unaccepted；不能靠 SDK 方法存在认定原生支持 |

既有公开验收来源是仓库 `a18-final-windows-2026-11-06.md`，本分支未重跑其完整矩阵。
本次便携检查只证明公共参数接线；内部校准只证明其记录的样件和宿主；公开验收需要
installed CLI/SDK/MCP 的实际结果、原生状态及保存重开证据，三者不可互相替代。

## 手动模板

`.github/workflows/ci.yml` 新增 docprops_targeted=false 默认关闭开关，只有 workflow_dispatch
和本分支白名单可运行，docprops_expected_head 在读取私有输入前必须精确匹配。
启用时跳过 test/package，禁止 native_full 同时启用；无 PR、push、发布入口。
可独立复用模板在 `scripts/ci/templates/docprops-targeted.yml`。使用已有 CI workflow ID
让尚未合入默认分支的校准入口也能按 ref 分派。
安装部分沿用已有 hosted Windows 流程；不调用完整基础CI或完整功能门禁。
并发沿用 hosted SOLIDWORKS 组，排队是正常状态，不保证十作业同时运行。

本版唯一允许计划是 baseline-properties：新建一个 owned 隐藏宿主，零件和装配属性样件，
保存副本、只读重开。使用既有脚本，不添加或重试写入 API。
run-docprops-targeted.py 只启动一次；native trace 调用600秒、整体1800秒，首次真实失败后
仅允许样件/宿主清理，不重试/回滚/组内重启。超时终止子驱动，记录宿主退出未证实；
后续 disposable runner 清理不算原生成功退出。

其他分支复用时须在自己的分支改白名单，建立固定计划与严格的专用审计器，先通过便携检查，
再手动校准一次对应精确 head。不得用此 properties 专用审计器审核其他功能报告。
新写入还必须证明 lease、stamp、完整值CAS、readonly/后台/文档身份、部分 mutation、
同值零写、几何/状态不变、完整相关字段读回和保存重开；缺少原生证据时 fail closed。

## 原件和失败审计

产物保留90天：native/report.json、native/trace.jsonl、原生保存副本、驱动stdout/stderr、
driver.json 和 audit.json。审计记录各原件字节数/SHA256、实际宿主PID/版本、严格调用配对、
单次宿主获取、ExitApp/WaitForOwnedProcess/CloseProcessHandle/CoUninitialize 清理序列、
两个样件的保存hash和只读重开值。audit永远 full_acceptance_eligible=false。
trace首个error优先于后续清理错误；报告失败另保留原始traceback。
报告或trace缺失、截断、预算/head不符、保存副本篡改、宿主退出缺失都阻止通过。
原件不被摘要覆盖。失败先下载原始artifact ZIP并记录SHA256、run/head/参数与首次真实失败；
只有相关修复后才能发起新一轮校准。持久证据应置于本工作树 artifacts/ 下，不依赖 /tmp。


## 15个独立对话的扩展边界

机器矩阵的 assigned_threads 来自主对话指定索引，仅记录负责人/分支/工作树，全部未验收。
新增加的稳定引用、基础配合、旋转、STL、STEP不属于此分支产品实现范围。
引用须拒绝不可唯一解析后的静默重绑；配合与旋转须各自提供求解/几何及保存重开证据。
STL和STEP使用格式专属结构，GLB/image-quality仍由原分工负责；涉及全局偏好的出口须
证明宿主独占、会话隔离、保存原值、设置读回、单次业务调用和finally恢复核验，保留首次业务失败。
这些是待验证条件，不代表已核实官方API支持或已完成原生验收。
