# 尺寸显示格式交接

公开42305495076/head9fe8d9d成功原件的独立审计已过。统筹提出的严格原生探针修复e1d1870已推送，46项定向、1865项便携（32跳过）、打包安装和SDK生成检查通过。必要公开42361878938/head e1d1870唯一快照in_progress，同head便携42361857745也在运行。最新可合结论待该公开gate及统筹终审。

## 分支与范围

- 唯一工作树 `/Users/YJBeetle/.codex/worktrees/docprops-dimension-format/SWCLI`，分支 `codex/docprops-dimension-format`，基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`。
- 实现提交 `4a2b4f461539cd4c5c80505a5172c2fcc3d071f2`；相关修复及公开gate准备提交 `f6bc6342362ca658b4db2d58bd3e749e5ace940c`，均已推送。
- `document.dimension-format` / `swcli document dimension-format`：完整原生三字段只读快照。
- `document.dimension-format-set` / `swcli document dimension-format-set FIELD VALUE --if-format JSON`：`field`=dual_display/dual_position/parentheses；value严格布尔或right/top/left/bottom；expected_format为完整三字段（dual_position原生整数）。
- setter context中的document_id、expected_update_stamp、lease_id均required；完整值CAS、readonly/viewonly、身份/前台/配置/草图/图纸上下文与部分mutation保护。任何真正setter至多一次，无失败API重试/自动回滚。
- 零显示沿用已有document.annotation-options / annotation-option-set；单位转换、公差、字体、尺寸子类型不涉及。未操作本地VM/SOLIDWORKS、DockerSW或MacSW；仅只读查MacSW内官方2025 SDK头文件以核ID。
- 官方映射与边界见 `docs/dimension-format.md`。原生首轮同时核官方swconst.tlb：43/200 dual_display，14/200 dual_position（右1上2左3下4），48/0 parentheses。

## 共享文件与接口diff

- src/swcli/cli.py、daemon/operations.py、operation_schemas.py、result_schemas.py及生成的sdk/_generated.py、sdk/models.py新增上述两操作。
- `_operation` 的lease_guarded支持required（除原有optional）；新增setter确实执行lease校验。
- `.github/workflows/ci.yml`：dimension_format_calibration与dimension_format_public默认false，互斥，仅本分支手动；专属模式跳过test/package；不进入默认full/release共享concurrency，不扩PR secrets。
- scripts/ci/windows/smoke-solidworks.ps1：仅显式DimensionFormatFixtureDirectory时提前运行公开gate并核owned daemon退出；默认full流程保留。
- 新增catalog/adapter、内部及公开gate、定向测试；无新运行依赖。读取保留未知位置，实际变更拒绝未知位置；公开写入同时要求经证据确认的文档类型与确切host revision，同时要求原生Windows（Wine/检测失败拒绝），目前两集合均空。

## 便携证据

- 本机安装wheel后全套1834项通过、32项平台跳过；SDK生成检查、严格类型检查mypy1.18.2、安装资源检查通过。
- 追加公开gate/host范围/trace顺序后定向36项通过；SDK回归11项通过，MCP18项通过（2平台/可选包跳过），wrapper回归4项通过（2因本机无PowerShell跳过）。
- 首版Windows CI https://github.com/YJBeetle/SWCLI/actions/runs/42260858025 ，head4a2b4f4，Python3.9/3.14和wheel success。
- 修复版Windows CI https://github.com/YJBeetle/SWCLI/actions/runs/42264284837 ，headf6bc634，Python3.9/3.14和wheel success。full/native/release均skipped。这些不是原生或公开写入验收。
- 原始日志在工作树同级 `../evidence/`：portable-tests.log、wheel-build.log、public-preparation-focused-tests.log、sdk-regression.log、mcp-regression.log、public-wrapper-regression.log及portable-ci-*.json，不依赖tmp。

## 原生内部校准

1. https://github.com/YJBeetle/SWCLI/actions/runs/42260887789 ，head4a2b4f461539cd4c5c80505a5172c2fcc3d071f2；dimension_format_calibration=true、native_full=false；failure。
   - host revision33.5.0。part八步API/readback、lease/stamp/CAS和单位/注解/全局偏好检查走到，但几何比较失败，未到保存重开；assembly/drawing未运行，不能算任何类型通过。
   - 第一真实失败 `display writes changed geometry`。体积11999.999999999998、面积3799.9999999999995完全相同，质心Y从5.514537417020185e-16变为8.271806125530278e-16 mm。
   - 原始artifact ID13524834970，SHA256 `cb43e60375da1814624f47d8a4708ae832fd05ff3031cee53a18548b995f211c`，ZIP与GitHub digest/head匹配。完整原件 `../evidence/native-42260887789/original.zip`、artifacts.json、integrity.json及extracted目录；未修改。
   - 相关修复把“未保存/前台”比较基线移到“已保存/后台”，增加无写入控制读和状态控制；保留原有写后/重开逐值精确比较，不放宽容差。若控制读不稳定，则在任何尺寸setter前失败。
2. https://github.com/YJBeetle/SWCLI/actions/runs/42264996931 ，headf6bc6342362ca658b4db2d58bd3e749e5ace940c；dimension_format_calibration=true、dimension_format_public=false、native_full=false；failure。
   - 这是相关修复后唯一一次必要验证，不是原样重跑。native600秒、组1800秒、首失败停止，无组内host重启。
   - 跟踪日志 `../evidence/native-watch-42264996931.log`（180秒间隔）。完成后先保存原ZIP/元数据并核digest/head/report/supervisor/trace/save-reopen，再决定下一步。

## 公开验收与未完成边界

- 公开gate已准备：独立fixture准备报告/源摘要绑定、安装CLI驱动单个隐藏daemon；完整CAS/lease/stamp拒绝、两种布尔方向、所有位置、同值不置脏、保存重开、只读拒绝、单位/零显示与几何保持、逐请求native trace及worker身份/调用次数/顺序验证、源/副本/trace摘要。
- 当前没有完整内部成功证据，也没有公开验收运行。不能开放白名单、不能宣称完成或merge-ready。
- 内部完整通过并独立核产物后，仅开放已证实的文档类型和确切revision，并继续一次必要公开CLI/daemon验收；失败仍先保存原产物/首失败，只在相关修复后再验证。
- 主对话统一审查集成；本分支不自行合main、不发布、不改DockerSW指针/分支/CI/镜像。

- 后续公开gate准备补充：争用lease token按请求schema编码；公开变更增加原生Windows/非Wine检测，检测失败即拒绝。运行42264996931已失败；未原样重发。

## 第二轮首失败与相关观测器修复

- 42264996931的artifact ID13527773368，digest SHA256 `8959bbb4c6d924aacf5a641e12dc79100c6b32fd1ddb8d6f2ca0db6b08a490aa`；ZIP与GitHub digest、headf6bc634一致。原件 `../evidence/native-42264996931/original.zip`、artifacts.json、integrity.json、extracted目录均保留。
- 第一真实失败 `no-write geometry control is not bitwise stable; no display setter attempted`。同一保存后/后台文档连续只读质量属性，centroid Y仍从5.514537417020185e-16变为8.271806125530278e-16 mm；volume/area完全相同。writes=[]，trace无internal-set，源文件SHA256与报告一致（499521efbf5b66e9c515d34e1c2b8f8c135dcdb4bfad306a3cb5327b7481253d）。这证明原始数值积分质心不能充当精确不变指纹，不是尺寸setter的原生成功证据。
- 相关修复是更换错误的观测基元，不四舍五入或扩大几何/状态容差：自有盒形夹具完整8顶点、12直线边、6平面及闭合四边面边界构成精确几何指纹；几何质心由完整边界严格确定。所有顶点/边/平面、几何质心、native volume/area仍逐值精确比较。
- 每次原始native质量属性完整保存在geometry_native_samples；既有model_checks.unchanged_depth_metrics差分判据原样复用，原有解析volume/area 1e-7/1e-5界限保留，raw centroid继续按既有1e-6mm解析界限核验。没有静默删掉质心检查。
- 新helper `scripts/ci/gate_support/dimension_box.py` 仅为40x30x10自有夹具的只读oracle，不提供/修改稳定拓扑API。公开gate只复用已有entity.list完整边/面观察；不增加通用COM参数或拓扑操作。
- 公共保存gate现在确保每个位置都真正经过setter、布尔值两个方向均经过setter，最终三个字段全部与源初值不同，防止保存默认值掩盖写入未持久化。
- 34项定向测试覆盖真实控制组尾数差异、完整native假对象路径、缺失/重复/1e-12mm位移的边界拒绝、volume/area精确差分、解析错误、16种初始显示配置的完整setter和非默认保存目标。
- 额外Windows便携CI https://github.com/YJBeetle/SWCLI/actions/runs/42265414686 （0f01cf7）及 https://github.com/YJBeetle/SWCLI/actions/runs/42267416339 （79ab4e2）均success；都不是原生/公开验收。

## 精确边界修复的必要验证

- 实现/观测器提交 `e08feb1f37fcf19fe06d630a029191645c7a8a87` 已推送；对应Windows/Python3.9、3.14、wheel CI https://github.com/YJBeetle/SWCLI/actions/runs/42271747465 全部success，native/full/release skipped。
- 仅一次相关内部运行 https://github.com/YJBeetle/SWCLI/actions/runs/42272595406 ，head=e08feb1f37fcf19fe06d630a029191645c7a8a87，dimension_format_calibration=true、dimension_format_public=false、native_full=false，failure。
- 低频跟踪 ../evidence/native-watch-42272595406.log；结构化总状态 ../evidence/calibration-state.json。尚无成功结论，未开放白名单、未触发公共验收。

## 当前授权与身份保护补充

- 当前无待审批动作。既有实现、中文提交/推送到YJBeetle/SWCLI及定向Windows校准/公开gate授权继续有效；独立核验后可在开发分支开放确切范围，合main仍由主对话办理。此前远端信任审批问题已核公开仓库与ADMIN权限后解决，不重复操作，不绕过自动审批。
- 公开候选进一步在任何偏好读取前拒绝不可读标题/路径/Extension；正向原生调用顺序不变，新增定向用例通过。当前仍未开放写入，不影响运行中的e08feb1校准head。

## 第三轮首失败与最小保存路由修复

- 42272595406 completed/failure，artifact ID13531958597，SHA256 `efaa5f32970de1c5b0cc38739ad8523ca30732bd5abde7d9a5ba3c881f151193`，head e08feb1f37fcf19fe06d630a029191645c7a8a87，ZIP与GitHub digest/head完全一致。原件 `../evidence/native-42272595406/` 保留。
- 新oracle实际8顶点/12直线边/6平面和无写入控制、写后精确边界全部通过，raw质量属性及native边界原始数组完整记录。part八步尺寸API/readback/保护检查通过，save_copy api_saved=true、errors=0、warnings=null，保存文件实际51565字节；source原SHA一致。
- 第一真实失败是随后的clean-read `DocumentNotFound`：校准脚本直接调用底层SaveAs，绕过现有document.save-as处理器的refresh_key，原路径绑定被注册表正确拒绝。未完成same-value、重开/只读；assembly/drawing未运行。不能把这些阶段性结果当验收通过。
- 最小修复：校准save-copy通过已有execute_operation(document.save-as)路由，显式document_id/lease/stamp，沿用handler的finally refresh_key；不忽略路径身份检查、不重绑/重获lease、不改注册表实现。新增测试证明SaveAs后同一ID与原lease仍有效且可继续document.dimension-format。
- 当前定向36项通过。公开写入名单仍空，公开gate未触发。下一次只在该相关修复与Windows检查通过后执行必要内部验证。

## 保存路由修复验证

- 代码commit `6445c1375586d33eca13db0ffa0ee697c64ced89`；Windows CI https://github.com/YJBeetle/SWCLI/actions/runs/42277229594 （Python3.9、3.14、wheel）success。相关两项既有SaveAs/路径冲突回归也通过，日志 ../evidence/existing-save-routing-regression.log。
- 唯一相关内部运行 https://github.com/YJBeetle/SWCLI/actions/runs/42277961301 ，head6445c1375586d33eca13db0ffa0ee697c64ced89，dimension_format_calibration=true、dimension_format_public=false、native_full=false。提交快照queued，正常排队，不是失败，不重复dispatch。
- 低频跟踪 ../evidence/native-watch-42277961301.log（300秒间隔）；有完成结果时立即保存原产物并核首失败/完整成功链路。公开gate仍未运行，名单仍空，不merge-ready。当前无待审批动作。

## 处理链同行审查修复

- set handler捕获最终documents.describe故障：保留原始before/format/native_return/changed/mutation，返回ok=false；已有原生或CAS错误的type/message完整保留，最终观察故障另列DocumentObservationFailed warning。不重试setter或describe，不回滚。
- 后台读写捕获前台文档自身type/stamp/dirty/config/title/path/Extension，所有保护阶段核对；发现漂移拒绝并保留已尝试mutation，不恢复前台状态。目标本身为前台时沿用目标写入状态规则，不错误拒绝正常置脏。
- 新增真实execute_operation handler及_worker_main路径测试，覆盖成功setter后观察失败、首个native失败再观察失败、CAS首错再观察失败；同时覆盖六类前台漂移、读取/同值/SetSaveFlag阶段及前台目标正向路径。
- 当前定向41项通过；全套1860项通过、32项平台跳过；SDK生成检查与mypy1.18.2严格实现及8项consumer拒绝通过。这些均为便携测试，不能替代原生公开验收。
- 既有6445c13内部运行不因本次审查另起CAD运行。其完整证据核验后，最终产品head需要一次必要的安装公开CLI/daemon gate。

## 本轮最终收口（2026-11-07）

- 最新产品提交 `c062dd65336727780acede40c8c57045c2893315` 已推送，含两项P1保护；Windows Python3.9/3.14与wheel CI https://github.com/YJBeetle/SWCLI/actions/runs/42279488573 success。元数据 ../evidence/portable-ci-42279488573.json。
- 一次最终状态快照确认内部 https://github.com/YJBeetle/SWCLI/actions/runs/42277961301 completed/success；精确head `6445c1375586d33eca13db0ffa0ee697c64ced89`。artifact ID `13534904383`，name `dimension-format-42277961301-1`，SHA256 `b5bc069911527c77312c79dd3cba34c5ee6ddd5d8eb399eb569539d4a9826729`。原ZIP、GitHub元数据、integrity.json、解压原件、audit.log均在 ../evidence/native-42277961301/；摘要与GitHub digest/head一致。
- 精确内部范围：原生Windows SOLIDWORKS revision33.5.0，part/assembly/drawing各8步三字段API/readback；完整CAS/lease/stamp拒绝、单位/注解/全局偏好保持、同值清洁、真实保存重开与只读拒绝、源/副本SHA、part完整精确盒形边界及既有raw metrics判据均过。supervisor成功、worker_exit=0、600/1800秒、cleanup_errors=[]；trace成对完整，只有预期lease/stamp拒绝错误。
- 此运行先于P1修复c062dd6；且report/supervisor均full_acceptance_eligible=false。因此仅是该6445c13的内部校准，不是最终产品head的公开CLI/daemon验收，不提供已验收写入子集或可合并通过结论。
- 未完成：最终产品head必要的安装公开CLI/daemon验收；通过前不开放文档类型/revision白名单。当前两集合仍空，Wine仍拒绝实际变更。公开gate准备代码保留，未新增功能或计划。
- 按统筹转达的最新收口要求，已停止持续sleep/状态轮询并收回本地watch；无新dispatch/automation、无取消任何CI，无CAD失败重试/回滚/组内host重启。本轮交接后由统筹分次快照跟进，不自行合main或发布，不rebase main。

## 原计划公开gate候选

- 统筹随后澄清：收口不取消当前已实现范围原计划必要公开gate；真实内部证据过且已知P1修复后可继续一次必要公开验收。
- 仅在本开发分支开放内部已证实的原生Windows / revision33.5.0 / 文档类型1、2、3候选；Wine、其他版本仍拒绝实际写入。不是已通过公开验收的白名单，不提供合并通过结论。
- c062dd6两处P1保持；portable假host设为显式未知revision，保证未校准范围拒绝用例不依赖候选名单为空。公开运行将绑定本次精确产品head；记录一次状态后停止轮询。

- 候选本地检查：精确wheel构建安装及installed CLI/schema/product skill检查通过（不激活COM）；全套1860项通过、32项平台跳过，定向41项与SDK生成检查通过。原始便携日志 ../evidence/public-candidate-*.log。

## 公开验收运行交接（唯一快照）

- 最终产品head `7962b58eb64669fdad0a4ada151ffe0bd779158b`，已推送；不含新增字段或场景，含原计划受限候选和P1修复。
- 唯一必要公开运行 https://github.com/YJBeetle/SWCLI/actions/runs/42282493201 ：workflow_dispatch、head与候选完全相同；inputs dimension_format_public=true、dimension_format_calibration=false、native_full=false。唯一状态快照queued，是正常排队，不是失败；没有原样重发。公开产物尚不可用，无公开通过结论。
- 同head自动便携CI https://github.com/YJBeetle/SWCLI/actions/runs/42282468280 ，快照in_progress。c062dd6的Windows便携CI成功与候选本地1860/41项、打包安装检查均已过；不能把该前置证据当候选Windows或原生公开通过。
- 后续由统筹分次快照跟进：运行完成后先保存原ZIP、元数据并核head/digest、报告、逐请求trace、保存重开/源副本SHA、三类状态和part精确几何、worker/host不变、清理与600/1800秒边界；通过才有最终head已验收范围。已准备原计划gate，不因本轮结束永久搁置。
- 当前无可宣称已通过公开写入验收的子集，不提供可合通过tip。开发候选开启仅为该次公开gate，不等于可发布。没有新dispatch计划、automation或本地watch；不合main、不发布、不rebase，保留统筹main0e72beb。
- 总状态与运行参数保存在 ../evidence/calibration-state.json；内部成功原件见 ../evidence/native-42277961301/。本轮工作树文档提交仅补交接，不改变上述最终产品head。

## 公开首轮首因与最小修复

- 42282493201 head7962b58eb64669fdad0a4ada151ffe0bd779158b completed/failure。artifact13538195111，SHA256 `5d3cc268afc5a094588d856c43f89e10f409fb86e44aa901597ba45230e16b64` 与GitHub digest/head一致；原ZIP、元数据、integrity.json、audit.json、workflow-failure.log和完整解压原件保存在 ../evidence/public-42282493201/。
- fixture准备三类成功，源SHA逐一核对一致；公开part初始读取、单位/注解、完整边/面几何及lease拒绝完成；writes=[]，原生trace中preference setter总计0。报告cleanup_errors=[]，trace前缀摘要独立匹配。尚未验证任何实际公开写入，不计为通过。
- 首个真实失败：verify-modeling.ModelingSmoke.write显式将timeout_seconds=None传到本gate.command；min(600,remaining,None)抛TypeError，在stale-stamp CLI派发前停止。工作流traceback已核。
- 最小修复仅在本gate包装将None解释为既有600秒默认值，再与600和组剩余时间取最小；保留1800秒组界限和15秒清理预留，不修改产品、几何/状态判据、失败行为或字段范围。
- 两项新增回归经真实继承write路径验证None、显式300/900、组剩余50秒与过期拒绝；43项定向测试通过。同head7962b58的Windows便携CI42282468280已success。本次为相关修复后必要验收，不是原样重发；不重启失败组或重试CAD API。
- 用户最新澄清系列能力一起完成再发版，本系列公开缺口保持当前任务内处理；不据此扩新字段/计划或派审查代理。正常新运行仅保存一次快照后结束，由统筹后续继续。

## 超时修复后的必要公开运行交接

- 精确产品head `3153b2415cb0713f57f15e4fb2acff1d7a5c32ba` 已推送。仅修本gate的None默认超时及两项回归，三字段/三类场景/几何与状态判据不变。
- https://github.com/YJBeetle/SWCLI/actions/runs/42301046570 ：workflow_dispatch，head与修复一致，dimension_format_public=true、dimension_format_calibration=false、native_full=false。唯一快照in_progress，正常运行，无失败/成功结论，未重复dispatch。
- 同head自动便携CI https://github.com/YJBeetle/SWCLI/actions/runs/42301024325 ，唯一快照in_progress；先前7962b58的Windows便携CI42282468280已success。当前43项定向通过，本修复不涉及产品runtime/schema。
- 总状态 ../evidence/calibration-state.json；首轮原始artifact/digest/trace/fixture/生命周期审计 ../evidence/public-42282493201/。后续完成时仍需核新运行原件、精确head/digest及完整公开链后才能给可合范围。
- 按用户收口规则，正常运行记录后结束，无sleep/watch/automation、无CAD失败重试/回滚/组内host重启、无代理或新功能计划。当前系列公开缺口不后置出任务，也不宣称已完成发版门槛；由统筹后续分次快照继续。

## 嵌套 trace 首因与修复

- 42301046570在精确head 3153b2415cb0713f57f15e4fb2acff1d7a5c32ba完成并失败。artifact13544114350，SHA256 `c97921abdad7a83359720c0ea40b9e53a1b1f3c7e8346121d8f2df2b517a5fd7`，与GitHub digest/head一致。原件、trace及日志见 ../evidence/public-42301046570/。
- 公开part三类拒绝均通过，首个dual_display setter真实执行一次，回执及读回成功。验收器以相邻两行配对，错误拒绝合法嵌套的IModelDoc2.GetUnits和GetUnits边界。组在首错停止，清理报告无错误，生命周期对照通过。
- 最小修复使用栈配对并校验开始序号连续、结束匹配最近开始的序号/阶段/方法。保留原setter种类/次数、读写顺序、worker及几何和状态断言。44项定向测试通过，含合法嵌套与交叉终止拒绝。离线复验原件六条请求全部通过，实际setter一次、12次格式读取、一次SetSaveFlag。独立核验原始trace前缀和三份夹具SHA。
- 3153b24便携Windows CI 42301024325 已通过。离线复验仅覆盖已记录的六条请求。完整公开验收需要在修复后走到三类保存重开和清理结束。

修复后的公开运行 https://github.com/YJBeetle/SWCLI/actions/runs/42305495076 绑定 `9fe8d9d0fedc19eb47bdb4fee55c940b06238605`，唯一快照为in_progress。继续按原范围验收三类文档及保存重开，完成后核原件。当前仍待公开验收及统筹审查。

## 公开成功原件独立审计与统筹阻断修复

- 已核运行 https://github.com/YJBeetle/SWCLI/actions/runs/42305495076 ，精确head `9fe8d9d0fedc19eb47bdb4fee55c940b06238605`。artifact ID `13546644221`，原ZIP SHA256 `6e07e9d7d9bd45e5347e461bd684cbc0bb2a01b49ec09337545e17255210bfdd`，与GitHub digest/head完全一致；解压文件逐字节与ZIP条目核对一致。
- 原件目录 `../evidence/public-42305495076/` 包含original.zip、artifacts.json、integrity.json、run.json、extracted、audit_public.py与audit.json。审计命令从本工作树执行 `PYTHONPATH=src python ../evidence/public-42305495076/audit_public.py --evidence ../evidence/public-42305495076 --head 9fe8d9d0fedc19eb47bdb4fee55c940b06238605`。
- 审计复算208条CLI事件、78条尺寸请求、39次真实setter。part/assembly/drawing各16次计划请求中13次真实setter，覆盖两布尔方向及四位置；最终三字段均与源初值不同。逐条核完整CAS/lease/stamp和readonly拒绝、完整before/format链、native_return、mutation、同值清洁、后台/current=false、保存API成功与零错误/原生警告空值、同ID保存与新ID只读重开、源与副本实际SHA。保护单位及七项注解值的前后原始CLI回执一致。
- 全部78请求的原始trace逐层核开始序号与结束栈、调用次数/方法/顺序/600秒边界、request_id及同一worker2132，原生host10108和revision33.5.0保持，公开组74.145秒。trace前缀SHA256 `d224516a533084e5e34334314786d21b2ee9df14eb66c921a92555ae8561db89` 已核。
- part写前/写后/重开三份完整边/面观察重新计算相同精确8顶点/12直线边/6平面，native体积/面积精确一致，原有raw metric差分和解析判据通过。每类结束均零文档，cleanup_errors=[]；daemon停止成功、退出码0；完整生命周期对照无新增任务/进程。
- 同head Windows Python3.9/3.14及wheel CI https://github.com/YJBeetle/SWCLI/actions/runs/42305417447 success，原元数据 ../evidence/portable-ci-42305417447.json。该原件证明上述head的限定三字段/三类文档公开行为。
- 统筹随后发现合并前阻断。旧探针仅检查wine_get_version属性缺失，会把无可核导出的ntdll对象接受为原生。现按已合STL机制核GetModuleHandleW(ntdll.dll)、已知NtClose导出，清last_error后查询wine_get_version，只有缺失且error=127才接受；缺模块/已知导出、Wine、非127与异常全拒绝。
- 新正向测试经完整公开handler确认合法探针可写。反例经公开handler核零preference setter/dirty/save。当前46项定向与全套1865项便携通过，32项平台跳过；构建安装及installed CLI/schema/product skill、SDK生成检查通过。原日志 ../evidence/strict-native-*.log。
- 原成功原件已完成审计，最新探针修复需一次必要公开gate。当前可审查代码包括adapter与catalog、daemon handler、CLI/schema/SDK，以及scripts/ci/verify-dimension-format-public.py、verify-dimension-format-calibration.py、gate_support/dimension_box.py和tests/test_dimension_format*.py。最终可合tip以探针修复head公开验收及统筹本人review为准。

## 严格探针修复 head 交接

- 精确产品head `e1d18709587f5c62e6757caad81bd188c027dd99`，沿用已审计9fe8d9d三字段行为，仅收紧原生环境判定。必要公开运行 https://github.com/YJBeetle/SWCLI/actions/runs/42361878938 ，唯一快照in_progress，head完全匹配，public=true、internal=false、native_full=false。
- 同head自动Windows便携CI https://github.com/YJBeetle/SWCLI/actions/runs/42361857745 快照in_progress。本地1865项通过、32平台跳过；46项定向、打包安装与SDK生成检查通过。
- 已完成原件审计的head仍为 `9fe8d9d0fedc19eb47bdb4fee55c940b06238605`，最新探针修复head需上述gate完成后核新原件。故当前交付审查候选e1d1870，最终可合tip以其公开证据和统筹本人review为准。
- 本次交接文档提交在e1d1870之后，仅更新WORK_HANDOFF.md。相关审计脚本绝对路径 `/Users/YJBeetle/.codex/worktrees/docprops-dimension-format/evidence/public-42305495076/audit_public.py`，结果同目录audit.json，原件original.zip，公开回执extracted/dimension-public/dimension-format-public/dimension-format-public.json，trace为extracted/dimension-public/swclid.stderr.log。
- 正常运行已记录一次快照，当前系列继续通过统筹分次快照推进。
