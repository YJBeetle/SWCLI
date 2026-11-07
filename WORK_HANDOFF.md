# GLB 首失败诊断交接

独立分支 `codex/glb-export-repair`，main 基线 `960839e52d0c433c817e71e02493a27681f7e858`。首阶段离线审计已完成，已确认本次原生 GLB 声明 720 字节 buffer 而 BIN 为 0。上游首因仍待实际暂存路径、隐藏 sidecar、导出时加载模块和文件 I/O 证据。

详见 [诊断与验证方案](docs/handoffs/glb-export-repair.md) 和 [机器可读审计](docs/evidence/glb-export-failure-2026-11-08.json)。本阶段变更为交接文档和审计记录，未派发新 CI。STL 与现代 SaveAs3 负责人的分支和原件保持原有状态。

## 继承的历史交接原文

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

- 持久拓扑引用：f325943/公开42361455599原件由本人复核，单实体零件完整面/边 census 双射；非任意拓扑永久稳定保证。组合2160项便携测试完成（34跳过），SDK及14个类型拒绝例通过。见 docs/handoffs/topology-references.md 与 docs/evidence/topology-references-main-integration-2026-11-08.json。

- 总注释字体七字段、显示十字段（工程图五项）及GB往返六标准36转换：42361904486原件由本人复核；三setter描述符和worker异常回执已补保护。组合2520项测试完成（34跳过），SDK及31类型拒绝例通过。主CI保持不变，手动专项迁至独立document-preferences.yml。见docs/handoffs/document-preferences.md及docs/evidence/document-preferences-main-integration-2026-11-08.json。

- main自动CI42406720872暴露Windows测试夹具句柄清理、CRLF分类假设和PyYAML未安装三类问题；仅测试/CI依赖修复，30关联与2520本地项（34skip）通过，新Windows CI待核。原日志及两摘要ZIP已核官方digest留存，详见docs/evidence/main-windows-portable-fixture-fix-2026-11-08.json。
