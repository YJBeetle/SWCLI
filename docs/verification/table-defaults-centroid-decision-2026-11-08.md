# 表格专属质心比较许可与写入保护

2026-11-08，统筹转达本次主对话的用户明确批准：“允许，仅限表格路线的质心界限”。本提交把该许可落实为表格内部校准、公开门禁及其原件审核共同使用的一条规则。

- x/y/z 各自 `abs(after - before) <= 1e-12 mm`，含边界；不使用相对容差、舍入或归零。
- 体积、面积、实体数严格相等；原字段结构、数值类型、有限值检查保持。V/S 仅差 1 ULP 也拒绝。身份、状态、编辑上下文、lease、完整 CAS 等保持严格。
- 新证据保留未经改写的 before/after、`exact_equal`、每轴有符号 delta、delta hex 与原浮点 hex。失败先记录原值再停组。
- 模块仅由表格路线3个验证/审核脚本引用。其他建模、注解、特征路线未改变。

内部校准对比创建→只读重开、可写后台首写前、每个字段写后、另存重开。公开门禁的写后和另存重开使用同一表格规则。独立解析尺寸的 fixture 初值检查维持既有语义，不能替代严格 before/after 比较。

## 旧失败保持原件与原结论

`42405733149` / `6396034fe941b28d90ced2b941ae0d6c26907be9` 在第一个表格 setter 前因旧 exact equality 失败，y 差 `1.9852334701272664e-16 mm`。旧 ZIP、report、trace、metrics 和失败核验脚本均未更改，不能按新许可追认为原校准成功。详细证据见 `table-defaults-part-42405733149.md`。

新规则只使后续一次真实校准可以检验剩余写入、保存与重开；没有证明 kernel 原因，也没有提前开放零件 public profile。

## 健康路径保护缺口和修复

统筹的 portable repro 使用实际已注册的 assembly toggle `True→False`：setter 后变为只读，或目标 GetSaveFlag 在 `_verify_metadata_state` 中令前台 peer 变脏。原 adapter 仍可进入 SetSaveFlag。复现失败日志分别保留在 ignored evidence 目录的 `postsetter-exact-public-profile-before-fix.log` 等文件。这些是 portable 注入证据，没有冒称 native 失败。

修复保持表格专用边界：捕获目标/peer Extension、peer permissions 和 edit context；完整 identity/peer 检查夹住纯目标 state 读取；绑定 preference setter 与 SetSaveFlag 后，在实际调用前再次验证 writable、context 和完整 peer。SetSaveFlag 仅一次，之后必须 dirty=true 且 type/config 不变。单个 preference setter、无 retry/rollback、首错及 partial mutation 回执保持。

新增实际 public profile 测试覆盖 setter 后 readonly/viewonly、target identity/config/sketch/extension、peer permission/sketch/extension、两处目标 state 读取引发的 peer drift，并确保 drift 后 SetSaveFlag=0。另覆盖 dirty setter 无效及改配置的失败，保留已发生的 partial mutation。worker late-fault 独立修复 `1d44a42` 保留。

## 验证与后续原生边界

质心测试覆盖三轴、零/界内、正负含边界、边外紧邻浮点、非有限值、布尔混入、有限输入差溢出、V/S 1 ULP 与实体数/额外字段拒绝；记录测试确认保留真实历史数值及 hex/delta。相关52项通过；最终完整回归1880项通过、33项平台相关跳过。完整日志位于 `docs/verification/table-defaults-evidence/approved-rule-guards-final-full-portable.log`。

旧 pinned internal `42301331238` 的本地 original preflight 复核通过，仍为 8 setters；旧原件不证明本次新 adapter。下一步仅启动一次 internal `all`，一个安装/host group，native 600秒/group1800秒、首错停组。装配体/工程图仅重验已有8项转换；零件3项为原计划内部 candidate，未测试的 public 值保持关闭。

成功原件必须独立核对 ZIP/GitHub digest、精确 head、完整 `[1,2,3]` 计划、11项写入及 noop/CAS、原始几何数值、save/reopen 和 cleanup，之后才更新完整 profile/pin 并运行一次 public all exact-head 验收。本阶段不 merge main、不发版。
