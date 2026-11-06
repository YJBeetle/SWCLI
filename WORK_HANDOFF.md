# 线型 / 线宽默认设置交接

- 工作树：`/Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI`
- 分支：`codex/docprops-line-style`；起点 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 初始 git status 干净；无 `.codegraph`，已读取适用 AGENTS 指令。
- 范围：drawing 文档级可见边/隐藏边的 style / weight 四字段；独立 operation、CLI、SDK、MCP schemas。
- 原生 API 已核官方 Line Font 文档：IModelDocExtension 整数偏好，NoOptionSpecified；ID 在 Windows 从官方 swconst.tlb 按名称读取。
- 完整四字段 native integer CAS；沿用 lease、expected_update_stamp、readonly/viewonly、背景/文档上下文保护；单 setter、部分 mutation 回执；无重试/回滚。
- 公开写入 fail closed (`DocumentLineFontUncalibrated`)；内部 adapter 校准能力不通过协议开放。未获得公开原生端到端证据前不得宣称写入已验收。
- 排除零件/装配、自定义厚度、线宽表、端帽、实体覆盖、全局选项、网格/基准面与注释箭头。
- 原生校准：CI / workflow_dispatch / 本分支 / line_font_calibration=true / native_full=false；600s stage、1800s group，首失败停止。校准保留 report/trace/process log 和 fixture，不作为公开验收。
- 无本地 VM 操作、无 main 合并、无发布；DockerSW / MacSW 未修改。

## 便携验证

- 完整 unittest：1831 项，全部通过，32 项按环境跳过；原始日志 `artifacts/line-font/portable-tests.log`。
- 新增 12 项保护/失败测试通过。
- SDK 生成一致性、严格类型检查及 8 项消费者类型拒绝测试通过。
- 安装包资源检查通过（无 COM 激活）；workflow YAML 与校准脚本语法检查通过；git diff --check 通过。
- 首次完整运行的 CI 接线断言失败已修复；isolated Python 未安装包的问题通过 editable 安装解决，最终完整运行通过。

## 操作 / schema / 共享文件

- `document.line-font` → `swcli document line-font`；结果 `options` 是四字段完整 native integer map。
- `document.line-font-set` → `swcli document line-font-set FIELD VALUE --if-options JSON`；输入 `field`、`value`、`expected_options`，context 沿用 document_id / expected_update_stamp / lease_id；回执 field / before / options / changed / mutation。
- 四字段：visible_edges.style / visible_edges.weight / hidden_edges.style / hidden_edges.weight。
- 共享修改：`src/swcli/operation_schemas.py`、`result_schemas.py`、`cli.py`、`daemon/operations.py`、生成 SDK `_generated.py` / `models.py`、`.github/workflows/ci.yml`；其余为线型专属新增文件。
- 借用已有 annotation adapter 的 sheet/sketch 上下文保护函数，未扩大其字段范围；无其他未验收分支依赖。

## 提交和原生 CI

- 实现提交：`216ebec0f6e80231f566dce0c351d7ff140e29c9`，已推送。
- 初次必要 dispatch：[42260403395](https://github.com/YJBeetle/SWCLI/actions/runs/42260403395)，head=上述提交；参数 line_font_calibration=true / native_full=false，其余默认。
- 在 Windows portable jobs 仍进行、原生校准尚未开始时主动取消：检查发现共享 concurrency group 可能挤掉其他线程待运行作业。修为本范围独立并发组后才允许新校准；不是因排队重复 dispatch。未动其他线程 run。
- 并发隔离修复提交：`6f531a595a50bbadeeab2c0f005d89c0246c7ee5`，已推送；接线测试 12 项（1 skip）与摘要策略测试 22 项通过，日志 `artifacts/line-font/workflow-checks.log`。
- 修复后必要 dispatch：[42260712677](https://github.com/YJBeetle/SWCLI/actions/runs/42260712677)，head=`6f531a595a50bbadeeab2c0f005d89c0246c7ee5`；line_font_calibration=true / native_full=false；media_path、assets_path、cleanup_profile、vfs_cache_gib 均 workflow 默认。独立并发组 `swcli-hosted-windows-line-font-calibration`，不会替换其他分支 pending 作业。
- 当前 run 进行中：Build wheel 已通过，Windows 3.9 / 3.14 便携 jobs 正运行；尚无原生校准完成证据。不因等待再次 dispatch。
- 后续只需跟踪此 run：若失败先下载 `swcli-windows-hosted-42260712677-*` 原产物，查看 line-font-calibration/report.json、trace.jsonl、process.log 与第一真实失败；如果未到原生阶段则读取失败 portable job。必要相关修复后才新验证。
- 未完成边界：Windows 原生内部校准结果待回收；即使内部校准通过，公开 CLI 写入端到端验收仍缺，本分支公开 setter 保持 fail closed。不得将该 run 当成完整原生基础门禁或公开验收。
- 交接记录后续文档提交不改变上述待校准代码 head；主对话可统一读取并处理集成。

## 公开验收续作（统筹授权后）

- 已准备 `scripts/ci/verify-line-font-public.py`：installed public CLI + 独立隐藏 daemon，完整 CAS/lease/stamp/readonly 拒绝、每字段单次修改、noop、source hash、save/reopen/fresh ID、SDK typed read/noop 及 MCP live bridge execute noop。MCP stdio transport 不在该 gate 的证据范围。
- 新开关 `line_font_public=false` 默认关闭，只允许本分支手动；专属 `swcli-hosted-windows-line-font-public` 并发组，不进入默认 full/release 流程。
- 已准备 `scripts/ci/audit-line-font-calibration.py` 对原产物独立核验：内部结果、四字段值变化、12 getter / 1 setter 顺序、save/reopen、fixture/report/trace/process-log SHA256。
- 对应 16 项线型/证据检查便携测试通过，日志 `artifacts/line-font/public-gate-portable.log`；未重复全套检查。公开门禁仍关闭，只有拿到原生内部证据后才能开放已证实的精确 transition 并触发公共验收。
- 现有原生作业仍在 disposable runner 磁盘清理阶段，未产生原生校准结果；不重复 dispatch。
