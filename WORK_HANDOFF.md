# 文档属性覆盖 / CI 交接

- 唯一工作树：`/Users/YJBeetle/.codex/worktrees/docprops-coverage-ci/SWCLI`
- 分支：`codex/docprops-coverage-ci`；基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 只读盘点 main、主集成树和另外9个工作树。盘点时主集成树存在未提交修改；没有修改、合并或验收它们。快照见 `docs/verification/docprops-worktree-inventory.json`。
- 版本化矩阵 `docs/verification/docprops-capabilities-v1.json` 覆盖11个基线公共操作和10项独立分工；新分支全部未验收。`1593330` 仅本地未验收快照。
- 新增固定计划 baseline-properties 的单次驱动、600秒 native/1800秒整体看门狗、严格原件审计器、可复用独立workflow模板。
- 现有 CI 新增默认关闭 `docprops_targeted` / `docprops_expected_head`；仅本分支手动运行；启用时跳过 test/package，禁止与 native_full 同时运行，沿用既有原生安装器。没有更改现有PR机密隔离规则。
- 原始 report/trace/保存副本/stdout/stderr/driver 与 hash 审计保留90天；基础设施清理回执单列，不能冒充原生正常退出。内部校准始终 `full_acceptance_eligible=false`。
- 没有修改产品功能/写入边界，没有操作Windows VM、SOLIDWORKS用户实例、DockerSW或MacSW，没有发布/合入main。

## 便携验证

本机 Python 3.15，独立临时venv：新增8项（11个操作跨CLI/SDK/MCP上下文），文档97项，SDK11项，MCP18项（2项可选SDK跳过），annotation CI接线4项（2项可选SDK跳过）均通过。JSON/YAML解析、diff --check通过。
看门狗测试模拟 native/整体超时，确认只启动一次并终止子驱动、不重试、不宣称宿主退出。
这些是便携/接线证据，不是公共原生验收。

## 提交与原生校准

代码提交将用中文说明并推送本分支；为避免push自动触发无关CI使用 `[skip ci]`。
随后只手动调用一次现有 ci.yml，参数 docprops_targeted=true、native_full=false、docprops_expected_head=精确代码提交。
CI链接/head/最终状态和持久产物将在本节续记。未取得报告前，原生校准与新增写入验收均不成立。
