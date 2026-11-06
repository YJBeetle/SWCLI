# 旋转凸台证据索引

证据保存在本持久worktree。日志与原始CI ZIP不提交为源码噪声，具体状态见 WORK_HANDOFF.md。

- 首阶段便携：portable-full.log，1834项通过、26项平台跳过；portable-targeted.log、sdk-types.log。
- 公开范围便携：portable-full-public.log，1841项通过、26项平台跳过；public-preflight.log，23项针对性通过；sdk-types-public.log，生成/严格类型及10项消费端拒绝通过。
- 内部原生：ci/42262911836/，head32812cb，原始ZIP SHA256 69aca5b8480ed3f14547ba36e85a23730b042068c32854b6e87541fa1eeb3ac1，独立72项检查通过；含真实SLDPRT、保存重开及trace。
- 公开原生：ci/42269057556/，head3dd23c8，正在执行，尚未验收完成。
- 公共写入仅对原生Windows / SOLIDWORKS33.5.0的已实证范围开放；其他平台/版本继续fail closed。merge-ready=false。

临时venv只作执行环境；tmp不作主证据。没有使用本地VM。
