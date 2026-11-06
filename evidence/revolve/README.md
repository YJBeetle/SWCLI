# 旋转凸台证据索引

此目录区分便携、内部原生校准和公开验收；日志与原始 CI ZIP 保存在本持久 worktree，不将内部结果标记为公开完成。

- 便携针对性：`portable-targeted.log`，15项（意图/几何/CLI/SDK/MCP/daemon保护/partial mutation/CI接线）。
- 便携全量：`portable-full.log`，最终结果见 WORK_HANDOFF.md。
- SDK：`sdk-types.log`，生成一致、严格实现和8项消费端类型拒绝。
- 内部原生校准：待 dispatch。预期保存 report、trace、三个原生模型及原始 ZIP。
- 公开验收：未完成，公共写入保持关闭。

临时 venv 只用于执行；主证据不以 tmp 为存放地。没有使用本地 VM。
