> 2026-11-07 接管说明：本文保留为前代理历史交接。后续用户已明确重新授权实现、中文提交/推送本分支及一次绑定 head 的 GitHub 定向校准；当前状态以 WORK_HANDOFF.md 为准。本文原有“停止、不提交/推送/dispatch”仅描述交接时状态。

# 第3路：文档属性校准性能与独立 Windows CI

## 当前状态与停止边界

用户改为10个独立侧边对话分别接管10个worktree。已停止继续实现，只保留未提交候选修改。本交接后**不commit/push/dispatch、不VM/native**；后续由新对话接管并遵循用户最新授权。没有改main、root原工作树、标准白名单、预算、版本、Docker或MacSW。

- 工作树：`/Users/YJBeetle/.codex/worktrees/docprops-calibration-performance/SWCLI`
- 分支：`codex/docprops-calibration-performance`
- 原clean base：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`
- 已非强制 `git merge --ff-only` 到共享快照：`1593330e6e757073d44c5bb9a04dc06deca10966`，继承6操作和最终SDK；没有新commit。
- 没有 `.codegraph/`，本次未使用CodeGraph。
- 停止前修改：`scripts/dev/calibrate-document-properties.py`、`tests/test_document_properties_calibration.py`，以及本交接文件。

## 性能证据（原生r4是失败证据）

持久证据主存：`/Users/YJBeetle/.codex/task-artifacts/docprops-calibration-performance`。
已从/tmp逐文件复制核字节/哈希：r4 report/trace/driver/SDK stderr/35native文件、r5冻结包、TLB/templates及原文档输入副本、独立审计/摘要/审计脚本。`R4_EVIDENCE_MANIFEST.json`登记59文件，SHA256 `bb757afee4367563e0f4a89c5e644c2bb0af16e06c00ff62e11fde6aadd7747c`。不要继续把/tmp当证据主存。

- 独立审计：`docprops-batch-standards-r4-independent-audit.json` SHA256 `80d64d63f5d1a198c6d4bc191f11035981816b302d83fdd2923e53c6a68eb58e`，127项离线核对完成，但 `success=false/full_acceptance_eligible=false/white_list_updates=[]`。
- 中文摘要：`docprops-batch-standards-r4-independent-summary.md` SHA256 `f6bc1a3b1d6c50126cefa89a684c864f1607c49b874081130f9fdf23bc3cc21b`。
- driver整组1800.041秒超时，只终止授权Python worker2284，未终止SW，无retry/rollback/restart。wrapper43277条=21638完整pairs+1begin，零error。
- 30个标准Set严格True，SDK实际合计**0.915488秒**，不是setter耗30分钟。part12、assembly12完整；drawing5保存/只读重开完整，第6仅SetTrue/poststate，after/final/save不完整。不能以part/assembly子集开放白名单。
- wrapper耗时（包含记录器，不是纯COM）：其它保护7735次611.122秒；IsSame9853次461.924秒；原文档保护3166次266.989秒；完整固定profile176次160.005秒；文件操作209次145.200秒；其余469次62.235秒；setter wrapper30次2.184秒。合计1709.659秒；完整跨度1799.436秒，间隔89.777秒。report177个reader条目，最后条目无snapshot，不能算完整。
- r5 `persist`原先每call先完整json_evidence/json.dumps/UTF8再比较byte cache；最终report3.19MB。IsSame wrapper季度均值20.6→49.2→70.2→80.9ms，仅支持记录器/保护热点判断，不能把461.9秒全归于COM或承诺某加速倍数。

## 已写但未提交的候选实现

### report revision/checkpoint

`Calibration.report_changed()`提升证据revision；`checkpoint()`在**序列化前**比较已落盘revision；`call`的pre-native入口由`persist()`改为`checkpoint()`。显式`persist()`仍强制序列化并保留byte cache语义。

每个nested subscript赋值、append/update/setdefault等写点后显式标脏，保留现有plain dict/list/row alias关系，避免用tracked-container复制导致本地row alias不再指向report。标记是在赋值**完成后**，RHS可能调用native时不能提前清掉尚未发生的修改。缓存revision仅在成功replace或已证明byte相同后前进；replace失败不前进。first-cause、次生I/O、begin/end/error与fsync、600/1800未变。

当前标记由AST辅助生成后修正了纯静态helper：`standard_diff`/`standard_key`等不含self的方法没有revision副作用。现有方法约161个写点有标记；**还需专项人工审阅及AST防漏回归**。当前策略保守地也对一些局部非report dict/list变更标脏（例如templates局部result），可能造成额外序列化但不丢证据；后续若缩减须证明不是report alias。不要跨checkpoint缓存原文档/foreground/state。

测试中唯一现有改动：外部测试直接向`c.report['mutation_intent']`写入后显式调用`c.report_changed()`，再断言pre-native intent已durable。私有report不是自动追踪容器，未来代码写新nested字段必须标脏。

### 同checkpoint身份双射

`identity_catalog`保持新GetDocuments/GetDocumentCount和长度检查；每个checkpoint先native IsSame证明expected身份两两互异，然后在fresh actual的unmatched列表中做完整匹配，每项只消费一次且不准遗留。native IsSame仍唯一身份依据，不用Python identity或title替代；不跨checkpoint缓存。

此版故意选择更易证明的**每checkpoint重新查expected互异**，不是仅检查斜对角：稳定4对象16次降至10次（6次expected互异+4次匹配），不是4次。重复expected/actual、foreign/missing、同title异native对象应拒绝；目录重排可成功。需要新fault tests严格验证。

## 已验证与尚未验证

已运行（portable/fake，不是native）：

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-calibration-performance/SWCLI
PYTHONPATH=src /private/tmp/swcli-a14-test-env/bin/python -m unittest discover -s tests -p 'test_document_properties_calibration*.py'
```

最终83tests全过（59calibration+24watchdog，1.188秒）。`git diff --check`通过。开发中曾误给staticmethod添加self标记，已移除并重新通过上述83tests。

**未完成**：新增revision/alias/遗漏标记AST回归；强制新nested观测/intent在native前落盘、prepersist失败零native、次生I/O保首因的新故障注入；严格duplicate/reorder/foreign身份计数测试；可重复数字计量；完整repo tests；Windows CI wiring及其安全回归；任何新native成功证据。不得把83个既有tests当作性能方案验收。

## 接下来优先工作

1. 审阅当前diff，再补专项fault注入测试。尤其动态row aliases、setdefault返回值、nested list/dict、RHS native返回后赋值的标脏顺序；检查所有报告修改点无漏，且纯readonly连续call零序列化（trace begin/terminal各fsync仍有）。
2. 计量应分开验证序列化调用次数、catalog IsSame次数以及portable walltime；不要用Mac基准冒充Windows加速。建议4对象稳定匹配应10次；重排/重复/foreign故障矩阵必须保留完整断言。
3. 保留单组完整36个转换：三类各12、每次保存/RO，176+后的完整profile覆盖；优先优化后整组1800内跑完。若确有依据选择按kind分成各1800新诊断组，必须明确是新设计并汇总完整36，绝不称旧30分钟整组通过。

## Windows CI建议（尚未改workflow/接线）

目标仅GitHub独立分支，不手工attach、不操作VM、不开放任何未校准标准转换。

- 现有已注册 `.github/workflows/ci.yml`有`workflow_dispatch`、`contents: read`、Windows安装/私有runtime/同名concurrency和artifact/cleanup链；只给branch加入明确的calibration opt-in和required expected_head更便于不改main时dispatch（新增workflow不一定已注册默认分支）。当前文件**未改**。
- 首个有secrets之前校验`workflow_dispatch`、仓库`YJBeetle/SWCLI`、固定本分支ref、expected_head==github.sha==checkout HEAD；checkout该head并persist-credentials:false。禁止PR/pull_request_target路径取私有secrets；native_full/tag/release流程不借此次校准放宽。
- 私有配置只用step env，不打印/上传，复用当前Google Drive安装/prepare-test-runtime/cleanup-hosted-solidworks步骤，不复制私有目录到public artifacts。
- 复用已有owned harness：`scripts/ci/verify-through-all-calibration.py`的`run`会`acquire_resident_app`且require owned、等待ready、抓owned process handle，finally只关闭本run fixture并ExitApp owned、WaitForOwnedProcess、CoUninitialize。现有property/annotation fixture脚本同样复用它。
- 新CI wrapper可在owned harness的单个case_runner里设置**自己**新实例的UserControl=True（calibrator要求baseline已True），然后运行safe driver+calibrator全standards组；不改用户host，不复用`GetActiveObject`找到的任意实例。parent等driver时应pump COM消息；driver继续唯一持有/终止自己授权worker，600/1800不变。owned harness负责最后退出自己host，calibrator内部仍不start/ExitApp。
- safe driver：`scripts/dev/run-document-properties-calibration.py`，实际Python身份nonce/args/exe/Popen绑定，-I -S授权前不执行SWCLI/COM，固定10s授权、600/1800、首因；不要退回/tmp旧`docprops-driver-handshake.py`（其早期版本与最终r5不同）。
- 校准使用当前branch明确source_root，输出新`C:\Workspace\...`目录满足现calibrator/driver限制；root GitHub runner安装路径一般`C:\Program Files\SOLIDWORKS\swconst.tlb`，drawing template用现有`gate_support/drawing_template.py`发现。别照搬VM的Corp路径。
- 不调用旧`/private/tmp/docprops-native-plan.py`：会重跑fonts/display，与本任务standards-only不符。
- 后续若重新获用户执行授权：中文逻辑commit、push此分支，不merge main/tag/release；只单次dispatch绑定确定head并记录run URL/head/run_attempt/artifact hash/原件结果。旧授权被最新“交接后停止、不commit/push/dispatch”覆盖，当前代理没有执行这些动作。

## 持久证据索引与源码

持久目录的 `audit-docprops-write-groups-independent.py`、`audit-docprops-standards-r4-timeout.py`及r4 summary仅作为既有r4离线审计；它们pin旧r5 source hash，不应未经更新拿来审新优化源。新native实验应生成新manifest和版本，分清r4失败、portable候选、新Windows验证三种证据。

当前所有更改只在本分支，root原工作树保留。交接完成后停止编辑。
