# 出详图 next：自动中心线与中心标记连接线默认值

状态：后续批次候选，**不纳入当前发版，不是原生验收通过**。基线 SOLIDWORKS 2025；新写入白名单为空。

## 官方映射与有界选择

| 本轮可写候选字段 | 官方枚举 | 文档 API |
| --- | --- | --- |
| `auto_center_lines.enabled` | `swDetailingAutoInsertCenterLines` | `IModelDocExtension.Get/SetUserPreferenceToggle` |
| `auto_center_marks.hole_pattern_connection_lines` | `swDetailingConnectionLinesHolePatternsCenterMarks` | 同上 |

两者位于 Document Properties → Detailing → Auto insert on view creation，option 为 `swDetailingNoOptionSpecified`。数值仍从宿主旁的官方 `swconst.tlb` 按符号解析，未猜测新字段 ID。

依据：[官方 DP_Detailing API 映射](https://help.solidworks.com/2024/english/api/swconst/DP_Detailing.htm)、[2025 产品帮助](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_OPTIONS_DETAILING_NEW.htm?id=9c8376d44748461faca7f4583f830216)。2025 帮助说明，大装配设置/组件数量阈值可能阻止自动插入中心线。因此本轮只讨论默认值存储，不把开关 true 当成实际视图生成结果保证，也不调整全局大装配设置。

槽/装配中心标记开关暂缓；视图标签需另核具体 API，不纳入该两字段一致子集。字体、尺寸格式、公差、总体标准、表格均不在本轮范围；没有具体视图/实体/中心标记插入操作。

## 加法合同，保留旧验收范围

已有 `document.detailing-options` / `detailing-option-set` 的两字段合同、已核原件及 `33.5.0` 白名单不扩大。

新增操作：

- `document.detailing-line-options`：返回 `options` 四个布尔值及 `write_enabled`。
- `document.detailing-line-option-set`：`field` 只允许表中两个新字段；`value` 严格为 boolean；`expected_options` 必须是全部四值。显式 `document_id/expected_update_stamp/lease_id` 均必需。
- 四值中的 `auto_center_marks.part_holes` 和 `auto_center_marks.part_fillets` 是**只读 CAS/不变保护**，不能通过新 writer 修改。旧接口仍只返回旧两值。
- 新字段常量按该 profile 单独解析/缓存，不让旧字段读取依赖新枚举的存在。

```sh
swcli document detailing-line-options --document d-ab12cd --json
swcli document detailing-line-option-set auto_center_lines.enabled true \
  --if-options '{"auto_center_marks.part_holes":true,"auto_center_marks.part_fillets":false,"auto_center_lines.enabled":false,"auto_center_marks.hole_pattern_connection_lines":false}' \
  --document d-ab12cd --if-update-stamp 103 --lease l-ab12cd34ef56 --json
```

当前新 reader 可按合同读取，但没有原生证据；`write_enabled=false`。**所有新 set，包括同值 no-op，均拒绝**；不会继承旧两项的校准白名单，没有 wire 或环境变量绕过。只有后续受控校准临时允许的精确宿主才会进入候选 setter 路径。

候选路径保留完整四值 CAS、read-only/view-only、普通图纸模式、前后台/身份/dirty/stamp 和单字段读回检查；未请求的旧/新字段一旦变化就返回部分 mutation 失败，不重试或回滚。最多一次 setter、最多一次 SetSaveFlag，最终只读观察不能悄悄修复状态。descriptor/CommandInProgress 恢复/late validator 异常保留本请求可信 mutation 和第一业务错误；恢复失败退休 worker。

SDK 新方法 `document.detailing_line_options` / `document.detailing_line_option_set` 由 schema 生成；MCP 沿用 capabilities/execute。可发现合同不等于已完成原生验收。

## 首轮交接后由统筹排程的目标原生计划

本轮没有调用 COM、操作 VM 或 dispatch 手动原生 CI；目前也没有新专项 workflow/可直接执行的原生 gate。现有旧 `detailing_calibration/public_gate` 只覆盖旧两项，**不能当成新字段证明**。排程获准后再补新 profile 的目标脚本/入口，不增加本次发布内容。

1. 新建并独占一个原生 Windows SOLIDWORKS 2025 宿主，使用显式 GB A4 模板生成空工程图和前台零件。禁止 attach 用户实例；固定同一 host/worker，背景目标与当前文档分离。
2. 从安装的官方 swconst 读取两个新枚举、两个旧枚举与 NoOption；记录符号/实际 ID、revision、host PID、字段原始 boolean、完整四值和状态。缺枚举/非 bool/未知编辑上下文首失败停止。
3. 内部校准仅在该独占进程中临时设置新字段的 `CALIBRATED_LINE_REVISIONS` 为本次精确 revision，不改变旧 profile，不提供客户端旁路。通过实际 handler/registry/adapter 校准。
4. 两个新布尔共四种组合，建议遍历 8 条单字段有向边，使每个新字段在邻项 true/false 下均覆盖 true/false。每次变更前给出四值 CAS、lease 和当前 stamp；两个旧值必须保持原样。每次检查原生返回值、完整读回、普通图纸/草图/视图上下文、前台配置及 dirty/stamp、图纸布局/投影不变。
5. 每次保存到独立 SLDDRW，记录字节数/hash，关闭并只读重开后核四值、状态与文件 hash；禁止复用已退休文档身份。新增 set 的有效 trace 应有 12 个偏好 getter、1 个 setter、至多 1 个 SetSaveFlag；同值为 4 getter/0 setter（只在有临时原生校准的进程里），CAS 冲突 4/0，read-only 与 lease/stamp 拒绝 0 setter。
6. 单原生调用/请求 600 秒，整组 1800 秒；首个意外失败保留原包、report/journal/trace、部分 mutation 和第一真错，不重试、回滚或组内重启。若连接线字段耦合改变旧中心标记字段，保留失败而不是放宽不变断言；可只交付另一个已证实子集。
7. 独立核内部 run/head/原 ZIP digest/trace/逐文件保存重开后，才可在本分支开放已证实的精确字段/revision/转换。再准备一次必要的公开 CLI→daemon→worker gate、SDK/MCP 契约和相同持久化检查，公开 head 单独记录。没有证据的新写入继续关闭。

未覆盖实际新建模型视图时的插线效果、复杂工程图、字体/标准/表格、其他 revision/Wine，以及完整发布验收；不为凑齐而扩大本批。
