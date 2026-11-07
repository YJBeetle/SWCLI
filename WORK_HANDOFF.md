# 当前任务：SW2025 IModelDocExtension.SaveAs3迁移

当前产品head `5a1b48dd1e6abb43560c63466c7bed2b55bf91d3` 的必要Windows full https://github.com/YJBeetle/SWCLI/actions/runs/42369257219 已完成failure：现代绑定、PRT/ASM/DRW保存重开通过，首失败为零件GLB严格内容检查，真实true/0/0；拒绝原字节未保留，不能对本次断言BIN=0。原ZIP官方SHA256已核，163文件逐一一致；详见 `docs/handoffs/saveas3-modern.md` 与 `docs/evidence/saveas3-modern-native-2026-11-08.json`。后续必要full由统筹协调组合head；未同head重跑、未合并或发布。

首个可审实现为 `89d4119a372b223c3847f2e905ecba2d6eb6f3bf`。初次run https://github.com/YJBeetle/SWCLI/actions/runs/42368723031 已在portable阶段取消，native job无steps。补齐保存与STL恢复双失败首错保护后，2144项回归通过、33skip，SDK11反例通过。新head及其原件审计见现代SaveAs3交接；现代COM绑定已有原生成功证据，GLB仍未解决。

持久worktree `/Users/YJBeetle/.codex/worktrees/saveas3-modern/SWCLI`，新分支 `codex/saveas3-modern`，基线 `2d83afdc6c5c56b1a72157a84d54ee15cde770ab`。实现、绑定、便携/原生校准方案见 [现代SaveAs3交接](docs/handoffs/saveas3-modern.md)。后续旧品质交接为继承历史，原证据保留。

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

第二逻辑提交将迁移IDimension.GetSystemValue2到GetSystemValue3；需严格配置范围/单值数组/有限数值并保留原有单位与保护。现已完成便携实现但尚未原生验收；本轮完成portable/SDK与可审提交，不触发重复安装。已有full42369257219不动。与SaveAs3线程的组合由统筹安排最终精确head一次必要gate，正式发布仍须用户最终确认。

官方来源、实现边界与后续原生验证计划：`docs/verification/native-api-observation-modern.md`。持久日志`artifacts/native-api-observation/`（忽略生成日志，不依赖tmp）。

## 最终可审实现与检查

- 第一逻辑提交`aecd560a9c0293f1a97d33d91ab400dbb2b651f9`：ConfigurationManager.ActiveConfiguration helper、metadata/STL/structure及活跃fixture/trace白名单。无旧API回退/配置激活。
- 第二逻辑提交：windows_dimensions._descriptor单次GetSystemValue3(swSpecifyConfiguration=3, 已核当前Name)，单BSTR；严格只收单元素tuple/list，拒绝空/多值/嵌套/标量/bool/非法/非finite/溢出/非正，meters转mm；保留nativeName/driven/readonly及原CAS/几何/状态/首失败。旧Get2不回退，其他绑定不重试。
- 枚举3据可读官方2022主文档，Get3参数/对象语义据可读官方2023正文，官方2025 Get2弃用页确认Get3替代；2025 Get3/enum动态正文未获取，未虚构已读或已校准2025typelib。实际typelib签名/ID/数组形状为原生必验。
- 完整portable2144通过/28环境跳过；dimension关联202、config helper4/document197/line trace42/STL24通过。SDK generator、严格6文件、11消费者拒绝及安装资源no-COM均过，mypy1.18.2。初始mypy2错误原日志保留；属测试环境修正，不是native失败或断言放宽。
- 持久日志artifacts/native-api-observation/；版本化回执docs/verification/native-api-observation-modern-portable.json。src与活跃scripts/ci无弃用API命中；负测试旧名仅不得调用trap，历史原件/audit输出不改写。
- 没有改workflow、公共CLI/SDK/MCP契约、版本、其他分支/main；无新dispatch，不操作VM/MacSW/DockerSW。full42369257219不动。SaveAs3也改windows_documents.py，统筹整合时同时保留两方局部修复；最终精确组合head一次必要full/gate的方案见说明文档。未取得本分支2025原生验收；正式发布仍需用户最终确认。

## 自动审批记录

组合的证据写入/本地commit/远端push命令在执行前被自动审批整体拒绝，理由为远端源码/日志外传目标与载荷缺乏可信用户明确批准。没有绕过或间接推送；先完成获准本地可审提交。只读核对origin=https://github.com/YJBeetle/SWCLI、repo isPrivate=false、当前viewerPermission=ADMIN，指定基线2d83afd确实已在该公开repo。实际待推送只包含上述来源的API修复、tests、说明与日志hash回执；原始生成日志被.gitignore排除。上述事实将供自动审批复核；若仍拒绝则保留本地成果交统筹，不将授权通报假装自动审批通过。

## 精确提交/远端回执（最终）

- 配置观察：`aecd560a9c0293f1a97d33d91ab400dbb2b651f9`。
- 单配置GetSystemValue3：`1cdbff41a0594440eda17e068c3d42e1fb24579c`。
- 两笔中文逻辑提交已成功push到公开`https://github.com/YJBeetle/SWCLI`的`codex/native-api-observation-modern`。针对最初自动审批拒绝，仅先完成获准本地工作，再提交公开repo/ADMIN/已公开base及实际无原始日志/机密payload的新只读证据；原始直接push复核通过，没有换路径或间接绕过。当前无待审批动作。
- 最终本地工作树干净（仅随后本交接记录commit）；配置helper+尺寸实现全部完成关联和完整portable/SDK，不包含原生成功声明。当前没有本分支run/artifact/native digest，原生计划尚待统筹的精确组合head；不取消、不重复已有SaveAs full42369257219。
