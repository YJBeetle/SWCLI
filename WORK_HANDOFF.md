# 基础装配配合第一批

- Scope: 当前装配配置中两个不同顶层已解析零件的平面重合、圆柱同心标准配合；不包含高级/机械配合、子装配、自动浮动、自动求解重试或回滚。
- Baseline: `3bda2c00489dde6a3d1e4521c548f751b1d1c197`; branch `codex/swcli-assembly-mates`。初始工作树干净，无 `.codegraph/`、无仓库内部 AGENTS.md。
- Proposed interfaces: `assembly.mate-targets` 读取当前组件/配置与面几何快照；`assembly.add-mate` 使用完整 `expected_value` 快照、显式面描述、公共 lease / expected_update_stamp。仅以组件名称+路径+配置+当前面序号及完整读回几何作受限瞬时目标，不发布稳定引用，也不依赖未验收引用分支。
- Shared files planned: operation/result schemas, daemon operations, CLI, generated SDK; 新增独立 adapter、测试与手动 targeted CI 入口。原有默认门禁保持。
- Safety: 尚未原生校准的 public mate 写入 fail closed；仅内部 owned calibration 可传内部许可。首次失败保留原错误与 partial mutation，不自动 CAD 回滚/重试。
- Tests/commit/CI: 尚未运行；原生 API 文档调查中。未占用本地 VM。
- Boundaries: 本分支未合入、未发版，尚无原生保存重开证据。

## 阶段：实现与便携测试
- 已实现 `assembly.mate-targets` / `assembly.add-mate`，完整 schema、CLI、生成 SDK、daemon handler。瞬时目标要求固定组件在前、浮动组件在后；恰好两个顶层单实体零件，ASM/PRT 均只有一个配置，面仅平面/圆柱。私有持久引用仅用于本次读回身份校验，不发布稳定句柄。
- COM adapter 首次调用创建后即标记 partial mutation，原生失败/求解失败不重试、不回滚。公开写入仍返回 `MateWriteNotCalibrated`。
- 本地首轮 14 项针对性测试通过（Python 3.14）；尚未原生验证，不能称功能验收完成。
- 已新增 owned 内部校准：两种配合×两种对齐，类型库成员/枚举校验、几何残差、实体归属、源文件 hash、关闭所有引用后 ASM 保存重开。公开验收独立标记未运行。
- 根据统筹并发纠正，新增专用 `assembly-mates-calibration` job，手动 bool 默认 false，仅本开发分支和 workflow_dispatch 可触发，concurrency=`swcli-assembly-mates-${{ github.ref }}`、cancel-in-progress=false。原 full/release job 未修改。
- 外部 supervisor 限原生调用组 600 秒/总组 1800 秒，失败保留原始 report/trace/文件，不重建 host。
- 未 commit/push/dispatch；正在接线测试和整体便携校验。

## 阶段：提交前验证
- 最新便携全套：`1837 tests`, `OK (skipped=26)`，Python 3.14，日志 `evidence/portable/all-tests.log`。本功能独立 18 项通过，日志 `evidence/portable/assembly-mates-tests.log`。
- SDK 生成一致性、strict mypy 与 8 个负向消费类型场景通过；wheel/sdist 构建和源包内容验证通过；actionlint v1.7.12 通过（无语法问题，日志含依赖下载信息）。
- 手动输入最终名 `assembly_mates_calibration`。独立 job 并发按功能+ref 隔离，未修改 full/release 的并发组和执行体，未放宽现有测试断言。
- 原生/公开边界：尚无 Windows 原生证据；本 head 公开写入仍 fail closed。内部校准后将继续单独公开 CLI→daemon→worker 验收，再提出精确开放范围，不以内部脚本代替公开验收。
