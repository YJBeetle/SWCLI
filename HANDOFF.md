# 扩展文档单位工作树交接

当前状态：按root于2026-11-07的新安排停止开发，交由独立侧边对话接管。所有改动未提交。没有push、dispatch、VM、COM、Docker或MacSW操作。禁止把此交接当作功能或原生验收完成。

## 工作树与边界

- 持久worktree：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI`
- 分支：`codex/docprops-units-expanded`
- clean起点：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`；目前HEAD未变。
- `.codegraph/`不存在，按用户规则不运行CodeGraph。
- 用户此前授权本分支后续独立中文提交/推送/真实GitHub校准CI；最新root要求本agent停止，故这些动作尚未执行，应由接管对话继续协调。不得推main、tag或release，不汇入main，不触碰VM。
- 当前main基线没有另一个文档属性批次的font/display/standards新helper；这里没有从那个未合入批次引入依赖。

## 已落盘但尚未验证的实现

1. `src/swcli/document_unit_profile.py`：九字段纯catalog和完整源snapshot，原GetUnits五short，以及19个只读unit linkage watcher；未知原生值读出保留为other/native_value。system263、linear47/precision49、angular51/precision52、massprop258/259/260/precision261，均Extension/option0。三个massprop单位字段才是官方Custom_only，其余首批scalar也暂限已有Custom是保守候选边界。`CALIBRATED_UNIT_WRITES=()`保持空，公共changed write拒绝，不自动切Custom；system公共改变也拒绝。
2. `src/swcli/hosts/windows_document_unit_profile.py`：`document.unit-profile`读取，`document.unit-profile-set`整snapshot CAS；复用A18编辑context、原state/foreground、readonly/viewonly保护。单次setter/原生返回值/partial flags/dirty once/完整读回。公共写wrapper没有私有参数；`_calibrate_unit_profile`仅内部校准入口，可绕过空证据域以做预定诊断，绝不可注册或暴露给公共参数。它尚未由任何脚本或原生执行调用。
3. `src/swcli/document_unit_profile_schemas.py`、`operation_schemas.py`、`result_schemas.py`：新读写schema和成功结果语义检查；新set必须lease与stamp，完整expected_snapshot必填。`_operation`的lease_guarded计算由仅optional扩成optional/required，原有optional模式不变。这是新必填lease能真正进入registry检查所需，但还须回归验证。
4. `daemon/operations.py`：两handler使用所选context.entry.document，沿原_with_document路径；无COM实例附着/激活操作。
5. `cli.py`：新增`document unit-profile`与`unit-profile-set FIELD VALUE --if-snapshot JSON`，沿原selector、lease、stamp入口。保留A17 `units/units-set`原实现与行为。
6. `sdk/models.py`与`_generated.py`：已运行现有generator重生，新操作随catalog生成。生成命令完成只说明schema可以导入/生成，不代表SDK、CLI或host测试已通过。

所有实现都属于候选代码。尚未写本组专属测试；不要依靠草稿的14项测试替代新代码测试。亦未改旧A17 `_read_units`，其中原有嵌套native_trace问题留在原代码，新增reader自行用flat GetUnits边界。

## 已执行的本地检查

- 起始git status clean、branch/base/noCodeGraph核对。
- 只读核已有A17/A18 schema/CLI/daemon/SDK-generator/原CI安装接线。
- 执行 `PYTHONPATH=src /private/tmp/swcli-a14-test-env/bin/python scripts/dev/generate-sdk.py`，exit0。
- **未运行**本分支单测、全套测试、SDK mypy、generated --check、安装/打包、GitHub任何CI。
- 未修改 `.github/workflows/ci.yml`、未新增校准脚本、未dispatch、未取得本组任何原生证据。

## 来源与持久证据

原研究草稿曾在`/private/tmp/docprops-unit-profile-draft`（含DESIGN/catalog/14纯草稿测试），不要将tmp作为后续主存。已把既有原生swconst导出的相关枚举摘录保存到：

`/Users/YJBeetle/.codex/task-artifacts/docprops-units-expanded/source-evidence/swconst-export-reference.json`

它包含原enum导出JSON SHA `a526d78c856b3efa294c1a5379ee23cec09334fd23ef27c7dcb42784a4751eec`，原TLB SHA `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`，完整相关枚举和preference符号。它只证明数字来自已导出TLB，不证明新组getter逐类型适用性或任何新增写入。

官方主源：

- [DP_Units](https://help.solidworks.com/2024/english/api/swconst/DP_Units.htm)：九项映射、精度0..8，258/259/260只能Custom设置。
- [SetUserPreferenceInteger](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IModelDocExtension~SetUserPreferenceInteger.html)：文档Extension整数入口，bool返回；False不可重试。
- [GetUnits](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetUnits.html)：LengthUnit/FractionBase/FractionValue/SignificantDigits/RoundToFraction五short。

官方DP页面的energy precision行写Toggle，但本地TLB将swUnitsEnergyDecimalPlaces归Integer enum；当前linkage读取按TLB的Integer，尚缺真实native核对，失败必须原件保留并停，不能补0或临时换API重试。

## 接管后的必要工作

- 先只读diff和实际分支状态，确认没有其他对话开始编辑；本agent此后不再修改。
- 审查新增schema/结果语义：partial error中的observed/native_return_value保留、snapshot字段canonical/type敏感、同值不Set/不dirty、readonly拒绝、必填lease+stamp真实route、拒绝后状态/前台一致。
- 为纯catalog/host写有意义测试，特别是未知read保留；每种CAS非目标成员漂移；public空domain零mutation；私有calibration单Set+False停；前读转readonly/前台/config变化零Set；Set后getter引入stamp/dirty漂移不得被当新baseline；mark-dirty前守护；dirty/noop；模型mm语义不变。暂未测试drawing context。
- CLI/schema/SDK/MCP generic execute与原A17单测一起验证，运行generated --check、SDK types及完整portable suite；修复失败后再准备提交。不要先推送让push CI替代本地验证。
- 将本组设计和source-evidence移入明确版本化文档/测试fixture（需要时引用持久task-artifacts），不得让产品运行依赖/tmp或task-artifacts JSON。

## 原生CI计划与缺口（尚未实现）

当前ci.yml只有native_full，没有新单位校准step。我已向root报告拟新增显式`units_calibration` workflow_dispatch输入与真正执行`calibrate-document-unit-profile.py`的step；root尚未给出额外命名约束。必须由接管对话先完成并测试工作流接线，再只dispatch一次，不把已有full当作新组校准。

建议按有限阶段拆组：

1. read阶段各新part/assembly/drawing读raw9/GetUnits5/19linkage，实际导出当前swconst符号及各值enum，记录模板源hash/readonly状态/context/foreground。缺getter先失败，不填default。
2. scalar阶段在自己新fixture上**显式**system→Custom，读完整联动；对八个scalar各有限目标（mm/in、degree/rad、质量长度mm/m、质量g/kg、体积mm³/m³、precision0/8）逐次单Set，完整before/after/final、bool返回、其余成员保持、每不同目标独立保存/关闭/RO重开、需要继续时writable重开自己的新文件。
3. system阶段是独立联动诊断，源模板系统必须实测冻结，有限预定MMGS↔CGS/MKS/IPS/Custom；不能自行把任意源改成MMGS掩盖输入。全linkage纳入CAS/保存比较，但不声称覆盖整个单位页或任意标准对。可先收part组，再明确扩ASM/DRW，避免无界批次。
4. 每组固定native600秒/group1800秒、父watchdog、每call durable begin/end/error、mutation前报告、原件及时flush/完整报告相同bytes才跳过。首因/partial保留，无API/IO失败重试、无rollback、无host组内重启。不得盲复用旧through-all harness的无预算/无fsync实现。
5. CI只拥有新DispatchEx host：before PID集合不含新PID且空catalog才操作；绝不误认已有实例为owned。只关自己的unique identity/title；owned Exit一次+processwait，保留源码/模板/输入/新native文件hash。part核V/S/质心三轴，保持模型输入mm。
6. 真实原件审阅后，才手动制定有限公共domain；CI成功不得自动写生产白名单或宣称整页单位完成。

没有任何新增校准或CI运行正在由本agent持有，交接后可安全接管本worktree。
