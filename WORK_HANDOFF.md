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

提交与唯一必要原生 CI 的链接/head/参数待推送后补充。
