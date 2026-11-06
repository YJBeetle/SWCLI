# 尺寸显示格式交接

当前状态：内部校准修复后运行中；公开CLI/daemon gate已准备，未触发；不merge-ready，公开写入白名单仍空。

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
- 追加公开gate/host范围/trace顺序后定向27项通过；SDK回归11项通过，MCP18项通过（2平台/可选包跳过），wrapper回归4项通过（2因本机无PowerShell跳过）。
- 首版Windows CI https://github.com/YJBeetle/SWCLI/actions/runs/42260858025 ，head4a2b4f4，Python3.9/3.14和wheel success。
- 修复版Windows CI https://github.com/YJBeetle/SWCLI/actions/runs/42264284837 ，headf6bc634，Python3.9/3.14和wheel success。full/native/release均skipped。这些不是原生或公开写入验收。
- 原始日志在工作树同级 `../evidence/`：portable-tests.log、wheel-build.log、public-preparation-focused-tests.log、sdk-regression.log、mcp-regression.log、public-wrapper-regression.log及portable-ci-*.json，不依赖tmp。

## 原生内部校准

1. https://github.com/YJBeetle/SWCLI/actions/runs/42260887789 ，head4a2b4f461539cd4c5c80505a5172c2fcc3d071f2；dimension_format_calibration=true、native_full=false；failure。
   - host revision33.5.0。part八步API/readback、lease/stamp/CAS和单位/注解/全局偏好检查走到，但几何比较失败，未到保存重开；assembly/drawing未运行，不能算任何类型通过。
   - 第一真实失败 `display writes changed geometry`。体积11999.999999999998、面积3799.9999999999995完全相同，质心Y从5.514537417020185e-16变为8.271806125530278e-16 mm。
   - 原始artifact ID13524834970，SHA256 `cb43e60375da1814624f47d8a4708ae832fd05ff3031cee53a18548b995f211c`，ZIP与GitHub digest/head匹配。完整原件 `../evidence/native-42260887789/original.zip`、artifacts.json、integrity.json及extracted目录；未修改。
   - 相关修复把“未保存/前台”比较基线移到“已保存/后台”，增加无写入控制读和状态控制；保留原有写后/重开逐值精确比较，不放宽容差。若控制读不稳定，则在任何尺寸setter前失败。
2. https://github.com/YJBeetle/SWCLI/actions/runs/42264996931 ，headf6bc6342362ca658b4db2d58bd3e749e5ace940c；dimension_format_calibration=true、dimension_format_public=false、native_full=false；目前in_progress。
   - 这是相关修复后唯一一次必要验证，不是原样重跑。native600秒、组1800秒、首失败停止，无组内host重启。
   - 跟踪日志 `../evidence/native-watch-42264996931.log`（180秒间隔）。完成后先保存原ZIP/元数据并核digest/head/report/supervisor/trace/save-reopen，再决定下一步。

## 公开验收与未完成边界

- 公开gate已准备：独立fixture准备报告/源摘要绑定、安装CLI驱动单个隐藏daemon；完整CAS/lease/stamp拒绝、两种布尔方向、所有位置、同值不置脏、保存重开、只读拒绝、单位/零显示与几何保持、逐请求native trace及worker身份/调用次数/顺序验证、源/副本/trace摘要。
- 当前没有完整内部成功证据，也没有公开验收运行。不能开放白名单、不能宣称完成或merge-ready。
- 内部完整通过并独立核产物后，仅开放已证实的文档类型和确切revision，并继续一次必要公开CLI/daemon验收；失败仍先保存原产物/首失败，只在相关修复后再验证。
- 主对话统一审查集成；本分支不自行合main、不发布、不改DockerSW指针/分支/CI/镜像。

- 后续公开gate准备补充：争用lease token按请求schema编码；公开变更增加原生Windows/非Wine检测，检测失败即拒绝。内部运行42264996931仍使用已记录的f6bc634 head，未重发。
