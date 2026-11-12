# STEP 公共导出选项独立验收（2026-11-13）

原生运行 [43299699392](https://github.com/YJBeetle/SWCLI/actions/runs/43299699392) 在 `422a123fbef25c8a89fbcacbd7ba5db06a74b02c` 上成功。Windows Python 3.9/3.14、原包构建和公共 STEP 验收均通过。统筹对 GitHub 原始 run/artifact 元数据、ZIP 和原始回执独立核验，未重跑 CAD。

- 原生 artifact `13983045935`，ZIP SHA-256 `56e7b5405c587be62a86461024a9567fb7382edb1696680c6b335d78c9d85656`，与 GitHub 摘要一致。
- 6 个真实 CLI 导出覆盖 AP203/AP214 × 实体/线框/含草图线框；另有 SDK AP214 实体与 MCP AP203 线框，共 8 个实际输出。文件 schema、几何实体类别、非空内容和 SHA 均核验。
- 8 个输出分别唯一导入、保存为原生零件，再只读重开；错误均为 0，保存警告为旧接口无法提供的 null，不将 null 写成 0。
- 实体 V=12000 mm³、S=3800 mm²、质心=(0,0,5)；重开前后 V/S/实体数相同，质心沿用原有 STEP 解析门禁 1e-9 mm。线框 12 段/320 mm，含草图线框 18 段/560 mm；完整长度向量、全部草图健康码、原生保存哈希均核验，未放宽判据。
- 8 个读回用例的原生空 IDispatch 参数、安装 TLB 声明、原返回包装链及完整 8 项导入偏好 CAS/恢复均核验；每个用例只调用一次 LoadFile4。原生 trace 中保存/只读重开各 8 次，退出和等待 owned 进程各 1 次，cleanup=[]。
- 写入宿主与读回宿主分别独立 owned/hidden。后台目标、前台文档与会话状态保持；过期 stamp、外 session 租约、只读源与非法协议均拒绝，源文件哈希保持。

## 能力与证据边界

本次批准范围为原生 Windows SOLIDWORKS 2025 SP5（33.5.0）的零件 STEP/STP 显式协议与几何导出。必须使用 daemon-owned hidden 宿主、已保存干净的源、租约和 stamp；Wine、装配与其他版本未开放这组新选项。默认不带选项的旧导出行为保留。

读回 harness 标记 `full_acceptance_eligible=false`，这是专项公共写入加独立原生读回证明，不是完整 19 组系列验收。没有提供全机进程清空证明，只有 owned 退出/等待回执。8 次公共导出仍调用旧 `IModelDoc2.SaveAs3`；旧 API 迁移与 GLB 另行验收，不能把本次结果当成现代 API 的通过证明。历史失败原件与报告保留，不改写为成功。

合并时保留 main 的 STL、单位、字体、表格、拓扑和 MCP/SDK 保护；STEP 公共验证放在独立 `step-export.yml` 手动工作流，仅允许 main 或 STEP 分支执行、没有发布步骤，避免超过主工作流 25 项手动输入上限。历史校准/原件诊断的精确 CI 定义保留为只读证据；不扩展 main 现有手动参数。最终集成 main 的原生系列与发布验收仍需另算，当前不建 tag、不发布。

复核入口：`python3 scripts/ci/audit-step-public-43299699392.py <原件目录>`；结果见 `docs/evidence/step-public-43299699392-audit.json`。原件目录包含 run-api.json、artifacts-api.json、native.zip 和 native/swcli-native-smoke；业务二进制原件仅本地保留。

## 合并回归

最终本地完整回归 2966 项、39 skip，104.425 秒通过；SDK 生成一致、严格类型检查与 33 项消费者拒绝通过。main 原有 ci.yml 和统一路由按字节保留。独立 STEP 工作流及其与已有单位/文档属性 CI 的上限、路由和凭据保护检查通过；合并过程中发现的参数超限和旧文件名测试失败日志保留，修正接线后复验，不改动原生判据。见 docs/evidence/step-merge-validation.json。
