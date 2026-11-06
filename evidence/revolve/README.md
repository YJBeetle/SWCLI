# 旋转凸台证据索引

证据保存在本持久worktree。日志与原始CI ZIP不提交为源码噪声，具体状态见 WORK_HANDOFF.md。

- 首阶段便携：portable-full.log，1834项通过、26项平台跳过；portable-targeted.log、sdk-types.log。
- 公开范围便携：portable-full-public.log，1841项通过、26项平台跳过；public-preflight.log，23项针对性通过；sdk-types-public.log，生成/严格类型及10项消费端拒绝通过。
- 内部原生：ci/42262911836/，head32812cb，原始ZIP SHA256 69aca5b8480ed3f14547ba36e85a23730b042068c32854b6e87541fa1eeb3ac1，独立72项检查通过；含真实SLDPRT、保存重开及trace。
- 公开原生：ci/42269057556/，head3dd23c8，已通过并独立核验原始产物；该head早于partial契约修复。
- 公共写入仅对原生Windows / SOLIDWORKS33.5.0的已实证范围开放；其他平台/版本继续fail closed。merge-ready=false。

临时venv只作执行环境；tmp不作主证据。没有使用本地VM。

最终修复代码head3922bee，run42273047248执行中，含独立内部真实模型partial控制；最终merge-ready仍为false。


最终run42273047248及原件已核验通过：artifact13533039600，原始ZIP SHA256
13c3a4695603e33875acb9a64c639baec056c48bdb7416b75b65664b89a29365。
内部85项/公开84项独立检查及两组trace均通过。产品head3922bee冻结，merge-ready=true。
最终摘要final-audit-summary.json、原ZIP/metadata/报告/SLDPRT在ci/42273047248/。
仓库说明见docs/verification/revolve-2026-11-07.md；SDK/MCP为便携契约，真实公开原生走CLI/daemon。
