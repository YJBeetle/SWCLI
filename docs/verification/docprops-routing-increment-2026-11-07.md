# 线型/STEP路由增量复核

旧315组报告保持历史快照，不用它判当前分支缺陷。本轮无CAD、无dispatch、不改其他worktree。

## 线型：精确提交通过路由复核

- source SHA：`bc619f372f9863c9654080e3a0492d994a3898e0`。
- 按此提交导出workflow、纯路由校验器和测试到本worktree；56组manual/default/tag/PR布尔组合均符合拒绝/接受策略，复制的4项owner测试通过。
- portable test的route步骤在Install SWCLI前执行，无continue-on-error；native job仍强制needs.test.result==success。因此错误ref、full+internal/public、internal+public均在无私有runtime阶段拒绝，不能再使native job空绿。
- exclusive full和无manual输入的版本tag保留full CAD路径；专属模式仍受owner ref限制。这里仅通过路由审查，不是产品原生验收，也不覆盖另报的handler/foreground缺陷。
- 原件与hash：`artifacts/docprops-coverage-ci/routing-increment-bc619f3/`。

## STEP：工作区修复测试通过，尚无可绑定的新提交

- 截至本次读取，owner HEAD仍为`2c7108fa5c6c22ebfc9a6c98bdb0a9f67acac58f`；route修改在workflow和测试的未提交diff中。owner交接说明拟随下个实质/public head提交，不为接线修复重复当前合法参数run。
- 在本worktree复制这两个文件，仅执行纯路由测试：3456组event/ref/全开关/tag-policy/仓库归属/test+package结果组合通过。
- 测试核每个实际可进入的job恰有一个full/internal/public CAD模式；混合full不会被忽略；public读回与public写入口配对；name/scope/concurrency匹配模式；版本tag保留full默认组与CAD路径。
- 两个文件SHA256固定在`artifacts/docprops-coverage-ci/routing-increment-step/result.json`。`source_sha=null`、status=working-patch-only-until-exact-commit-matches，不能将此结果绑定旧2c7108f或宣称某个尚未提交head已通过。
- 待owner提交后，只需核精确commit的workflow/tests字节与已测试hash一致；不同则重做纯路由增量检查，不新增CAD。

路线检查不修改主集成对原生/public验收、83c4830 detailing及78ebaf6修复的保留要求。
