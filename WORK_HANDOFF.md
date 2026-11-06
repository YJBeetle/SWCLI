# 尺寸显示格式交接

当前状态：前两轮内部校准失败，原始产物均已核验；精确盒形边界观测器修复后的内部运行42272595406进行中；公开CLI/daemon gate未触发；不merge-ready，写入白名单仍空。

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
- 追加公开gate/host范围/trace顺序后定向35项通过；SDK回归11项通过，MCP18项通过（2平台/可选包跳过），wrapper回归4项通过（2因本机无PowerShell跳过）。
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
- 仅一次相关内部运行 https://github.com/YJBeetle/SWCLI/actions/runs/42272595406 ，head=e08feb1f37fcf19fe06d630a029191645c7a8a87，dimension_format_calibration=true、dimension_format_public=false、native_full=false，目前in_progress。
- 低频跟踪 ../evidence/native-watch-42272595406.log；结构化总状态 ../evidence/calibration-state.json。尚无成功结论，未开放白名单、未触发公共验收。

## 当前授权与身份保护补充

- 当前无待审批动作。既有实现、中文提交/推送到YJBeetle/SWCLI及定向Windows校准/公开gate授权继续有效；独立核验后可在开发分支开放确切范围，合main仍由主对话办理。此前远端信任审批问题已核公开仓库与ADMIN权限后解决，不重复操作，不绕过自动审批。
- 公开候选进一步在任何偏好读取前拒绝不可读标题/路径/Extension；正向原生调用顺序不变，新增定向用例通过。当前仍未开放写入，不影响运行中的e08feb1校准head。
