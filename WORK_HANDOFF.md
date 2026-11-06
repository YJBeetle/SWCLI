# 有界旋转凸台工作交接

## Scope
- 分支 codex/swcli-revolve-feature；基线 3bda2c00489dde6a3d1e4521c548f751b1d1c197。
- 最小候选：空零件、单个草图局部轴对齐矩形、独立且共面直线轴、单方向实心旋转凸台。
- 不支持任意曲线、切除、扫描/放样、多实体、已有实体合并。原生校准前公共写入 fail closed。
- 不占用本地 VM，不修改 DockerSW/MacSW/main/版本。

## 文件/接口
- 将新增 feature.revolve 的 CLI/protocol/SDK/MCP 契约和 COM worker 内部校准路径；不改变现有操作。
- 新增明确手动 targeted CI 输入（默认 false），保留默认门禁和 PR 秘密隔离。
- 现有共享文件的变更在本分支独立实现，统筹应按最终 diff 协调。

## 测试与证据
- 初始 status 干净；HEAD 为基线；无 .codegraph 目录。
- 官方 API 已定位 FeatureRevolve2 / IRevolveFeatureData2，尚待类型库及实际读回。
- 便携：待执行。内部校准：待执行。公开验收：未通过，不应发布。

## Commit / CI
- 尚无功能提交或 dispatch。

## 未完成边界
- 实现、便携验证、一次对应 head 的 Windows 原生校准，保存重开/输出证据。

## 实现阶段更新
- 已完成最小候选：矩形边为明确轴、显式整圈360°、空零件/单配置；标准平面刚体变换及圆柱体积/面积/质心解析断言。
- 公共 feature.revolve 契约覆盖 CLI/protocol/SDK/MCP，但公开写入明确返回 RevolveNotCalibrated；结果契约不允许 ok=true；无绕过开关。
- 内部候选读官方 TLB 枚举与签名、验证精确轴身份/定义、partial mutation/cleanup，校准保存重开3个平面；非法轴穿越和多实体拒绝。
- 已新增手动 targeted CI 输入 native_revolve_calibration，默认false，仅当前分支可执行；与native_full互斥。默认门禁保留。
- 根据统筹反馈：targeted concurrency 改为 swcli-revolve-calibration-${github.ref}，cancel-in-progress=false；默认full/release组仍为 swcli-hosted-windows-solidworks。不取消他人run、不为等待重复dispatch。
- 正在安装独立临时便携测试环境（系统 Python 缺 jsonschema），尚未提交/push/dispatch；证据主目录 evidence/revolve。
- 便携阶段：15项针对性测试及 SDK 严格类型通过。全套回归发现新增 x-swcli-write-gate 元数据不符合既有严格能力 schema，已改为现有 title + failure-only result 表达，避免扩大共享 capability 接口；必填 document/stamp 仍保留。

## 便携阶段完成（2026-11-07）
- 15 项旋转针对性测试通过；全套 1834 项通过、26 项平台条件跳过（本地 Python 3.15）。
- SDK 生成一致性、严格实现类型和8项消费端拒绝通过；YAML解析、targeted并发接线与git diff --check通过。
- 本地 venv 已 editable 安装，隔离 -I 子进程契约也通过。完整日志见 evidence/revolve/*.log（持久保留，不提交噪声日志）。
- 公开范围仍未开放，merge-ready=false。内部校准后继续公开 CLI→daemon→COM 验收，不以候选/内部成功代替公开完成。
- 准备中文功能提交并push自己分支；随后仅对该head dispatch一次 native_revolve_calibration=true/native_full=false。
