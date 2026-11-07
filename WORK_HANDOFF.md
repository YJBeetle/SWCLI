# 逐路集成交接

- main 已合入工程图出详图两个默认标量；代码、验收范围与原件摘要见 [出详图交接](docs/handoffs/detailing.md) 和 docs/evidence/detailing-main-integration-2026-11-07.json。
- 有界旋转凸台已完成本地集成及 1871 项便携回归（32 跳过）、SDK 与 CI 参数检查；精确产品 head 3922bee798b0b5b33dc6aa7a4bf34b01dc0e79ad，最终公开 run 42273047248。最终原始证据已独立核对通过，见 docs/evidence/revolve-main-integration-2026-11-07.json；原分支历史交接见 [旋转交接](docs/handoffs/revolve.md)；最终集成审阅结果单独记录，不将历史待验收状态冒充最终结论。
- 文档为滚动集成记录；不代表创建发布标签、完整发布验收或 Docker/Wine 晋升。

- 线性尺寸文档默认公差：最终产品 head59f29e8、公开42277528349已核原件；本次组合1910项便携测试通过（32跳过），SDK及统一CI预检通过，见 docs/handoffs/tolerances.md。

- Notes字体七字段：最终15d32ce/公开42279469524原件已本人核验，组合1974项便携测试通过（32跳过），SDK通过；该Notes子集已完成集成，整个系列待完成后发布。

- STL 参数宿主限制修复提交 f22b7a1 已通过公开原生验收 42302254750。

- 工程图线型四字段：宿主修复85ae6c1/公开42361465979原件已本人独立核验，精确范围和哈希见docs/handoffs/line-font.md及docs/evidence/line-font-main-integration-2026-11-07.json。

- 尺寸格式三字段：严格宿主修复e1d1870/公开42361878938原件已本人独立核验；三类39次setter及保存重开通过，组合证据见docs/evidence/dimension-format-main-integration-2026-11-07.json。

- 集成收尾保护：线型/尺寸格式在CommandInProgress恢复或late validator异常后仍保留修改回执及首错；恢复失败退休worker。真实handler/adapter的便携故障注入48关联通过，组合2094项/33skip通过。不是原生故障现场证明，原健康native原件保持。

- 文档图像品质：严格native宿主修复950c833/公开42361573569由本人复核；仅已证实零件品质字段，GLB细分控制仍未解决，不能当作已完成功能。

# Native API observation现代化（2026-11-08）

本轮用户新授权：从main `2d83afdc6c5c56b1a72157a84d54ee15cde770ab` 建立持久worktree `/Users/YJBeetle/.codex/worktrees/native-api-observation-modern/SWCLI`，分支`codex/native-api-observation-modern`。不修改其他分支/main，不使用VM/MacSW/DockerSW，不派审查子代理。

第一逻辑提交迁移生产GetActiveConfiguration至ConfigurationManager.ActiveConfiguration：新增windows_configurations helper，接metadata _state、document结构和STL before/after/finally观察；Name严格保持，缺失/非法拒绝，不切换配置、不用旧API回退。同步活跃fixtures和line-font trace observation whitelist，历史原件/audit结果不改写。关联197文档+4新helper+42线型/trace测试通过；STL日志见`artifacts/native-api-observation/config-stl-tests.log`。

第二逻辑提交将迁移IDimension.GetSystemValue2到GetSystemValue3；需严格配置范围/单值数组/有限数值并保留原有单位与保护。尚未实施或原生验收；本轮先完成portable/SDK与可审提交，不触发重复安装。已有full42369257219不动。与SaveAs3线程的组合由统筹安排最终精确head一次必要gate，正式发布仍须用户最终确认。

官方来源、实现边界与后续原生验证计划：`docs/verification/native-api-observation-modern.md`。持久日志`artifacts/native-api-observation/`（忽略生成日志，不依赖tmp）。
