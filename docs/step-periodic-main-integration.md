# STEP 周期面主线集成候选

候选从 `8d49069ba5b8f19f3470ada9f8e57c91826a243d` 集成。显式布尔拆分参数通过生产 CLI、daemon 操作和 SDK 到达 STEP 导出。其范围为原生 Windows SOLIDWORKS 2025 SP5.0（33.5.0）、daemon 自有隐藏宿主、实际语言 `english`、可写 part、AP203/AP214 solid-surface。语言不可确认或非英文时在任何 STEP 偏好读取、setter 或 SaveAs3 前拒绝。三项偏好 CAS、旧目标保护和原生状态检查沿用原验收实现。

## 已发布路径

省略拆分布尔值时，沿用主线两项 STEP 偏好、默认 `C:\Program Files\SOLIDWORKS\swconst.tlb` 和原 ASCII 校验、实体/结果验证。显式 `false` 仍进入新路径，与显式 `true` 一样按宿主可执行文件安装目录寻找 `swconst.tlb` 并用严格 Part 21 校验。严格校验仅在引号文本边界内允许有效 UTF-8，拒绝损坏片段及结构位置的非 ASCII，并核对真实 schema 和实体族。旧 wire 审计保持原样。

两版验证器均接受历史英文 9570 字节纯 ASCII AP214 原件，及含复杂单位实体的离线样例。在独立样例中，主线拒绝引号内 UTF-8 并接受 ASCII schema 子串，显式校验接受前者并拒绝后者。旧路径的安装和解析行为保留，以免将这一差异扩大到已发布的调用。

## 已采证据和下一次原生复验

原生通过的提交为 `e6371ffed59e55dcba75caf8ecc230c002e97afa`。其英文 writer 经生产 CLI 导出四项，独立宿主导入、保存并只读重开，简中 false/true 均在偏好和 SaveAs3 前拒绝。原生审计 SHA-256 为 `59ef09dbe8033c6bf4e62e5052fcf03e37f1c7baf064771ee3799c1de00b950b`，168 文件终态清单为 `22607a8568a975e6d5a733b4716ab1bcd42c6655777fedb902d9308d97311c99`。旧分支在该次原生验收中也使用了宿主 TLB，不能替代集成候选的已发布路径对照。原生证据限于同一固定 r10/h30 圆柱。

从核对过的源码与 wheel 独立安装后，在排定窗口用不同目录依次执行以下业务阶段。退出后收取报告和原 STEP，保留实际退出值、首错与文件摘要。所有命令使用各自安装的精确完整提交。

- 英文显式 writer。`verify-step-export-public.py --periodic-host english --source-commit FULL_SHA --output-dir WRITER`。
- 独立英文 reader。`verify-step-periodic-readback.py --source-commit FULL_SHA --swconst ABSOLUTE_SWCONST --public-writer-report WRITER/report.json REPORT_SHA256 --output-dir READER`。只接受同一提交已退出的四项 writer 原件，读取 SHA、实际导出/导入、保存只读重开与宿主退出。
- 简中显式拒绝。`verify-step-export-public.py --periodic-host chinese-simplified --source-commit FULL_SHA --output-dir CHINESE`。核对两个值的专用拒绝、实际 trace、零偏好、零 SaveAs3 及已有输出不变。
- 单独的英文旧路径。`verify-step-export-public.py --periodic-host english --periodic-legacy-only --source-commit FULL_SHA --output-dir LEGACY`。同一环境分别确证 `8d49069` 和集成候选，记录默认 TLB 是否存在。可用集成候选的 gate 脚本运行已安装的精确基线 wheel，源码标签使用基线 SHA。若默认 TLB 缺失，分别保留真实拒绝，禁止复制或伪造安装路径。旧路径和显式四项各有独立终态。

候选尚未进行原生复验。发布线和 CI 调度保持原状。
