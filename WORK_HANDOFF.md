# 尺寸显示格式交接

- 工作树：`/Users/YJBeetle/.codex/worktrees/docprops-dimension-format/SWCLI`
- 分支：`codex/docprops-dimension-format`
- 基线：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`
- 范围：`dual_display`、`dual_position`、`parentheses`，CLI/协议/SDK、完整值CAS、背景/readonly/lease/更新戳/身份与部分mutation保护。
- 零显示沿用已有注解操作；单位转换与公差不涉及。
- 原生写入 fail closed：`CALIBRATED_DOCUMENT_TYPES` 为空；内部 `_calibration` 仅适配器自有夹具入口，不能通过协议/CLI启用。
- 当前详细契约与官方映射：`docs/dimension-format.md`。
- 未操作本地 Windows VM、SOLIDWORKS、DockerSW 或 MacSW；仅只读查看 MacSW 中已有官方 SDK 头文件以核数字ID。
- 便携测试：Python3.15 当前wheel安装后完整套件1834项通过、32项平台跳过（51.377秒）；最后补充原有dirty保护后定向16项通过；SDK生成检查、严格类型检查（mypy1.18.2）、安装资源检查、YAML解析、git diff --check均通过。最初未安装wheel导致隔离导入失败，安装后已消除。
- 原始便携日志：工作树同级 ../evidence/portable-tests.log、dimension-focused-tests.log、wheel-build.log，不依赖tmp。
- 操作/CLI：document.dimension-format（swcli document dimension-format）；document.dimension-format-set（swcli document dimension-format-set FIELD VALUE --if-format JSON）。
- schema：reader空参数；setter的field=dual_display/dual_position/parentheses，value为严格布尔或位置枚举，expected_format是完整原生三字段（dual_position原生整数）；setter context的document_id/expected_update_stamp/lease_id均required。
- 共享文件修改：.github/workflows/ci.yml（专属模式跳过test/package；原full/native发布门保留）、src/swcli/cli.py、daemon/operations.py、operation_schemas.py、result_schemas.py和生成的sdk/_generated.py、sdk/models.py。新增catalog/adapter/校准脚本/16项定向测试/说明文档。无新运行依赖。
- 实现提交 `4a2b4f461539cd4c5c80505a5172c2fcc3d071f2`（中文提交）已推送 origin/codex/docprops-dimension-format。
- CI：仅手动触发一次 https://github.com/YJBeetle/SWCLI/actions/runs/42260887789 ，head=`4a2b4f461539cd4c5c80505a5172c2fcc3d071f2`，ci.yml，dimension_format_calibration=true、native_full=false，其余安装参数默认。初始状态in_progress（2026-11-07 01:21北京时间），并非通过。原生600秒、组1800秒、首失败停止；禁止无修复重跑。
- CI artifacts：远端 dimension-format-42260887789-1；下载后原样保存到 ../evidence/native-42260887789/。当前尚未有完成证据。
- 远端已核实为公开仓库 https://github.com/YJBeetle/SWCLI，当前身份ADMIN；初始导出审批因缺少远端信任信息被拒，经只读验证后本次提交/推送与校准触发获准。
- 未完成边界：内部原生校准与安装后公开CLI验收严格区分；即使内部成功仍需公开入口全链路证据后另行开放写入，不合并、不发布。

## Windows便携CI补充

- 同一实现head `4a2b4f461539cd4c5c80505a5172c2fcc3d071f2` 的推送CI通过：https://github.com/YJBeetle/SWCLI/actions/runs/42260858025 。Windows/Python3.9、Windows/Python3.14、wheel构建均success；native/full/release均skipped。这不是原生验收。
- 原始job快照：../evidence/portable-ci-42260858025.json。
- 原生专属运行42260887789最近快照仍in_progress，处于runner磁盘准备，未到CAD校准。跟踪输出保存在 ../evidence/native-watch-42260887789.log（120秒间隔）。没有重复dispatch。
- 原生未完成边界：需要完成后保存远端原始artifact、核report/supervisor/trace的第一个真实失败；仅有相关修复后再开验证。当前没有原生成功证据、没有安装后公开CLI写入验收证据；新写入继续fail closed。

## 内部校准42260887789首失败（已保留原产物）

- 结论failure，非通过；host revision 33.5.0，part的API映射/readback、lease/stamp/CAS与受保护单位/注解检查均走到，但未通过几何比较，未到保存重开；assembly/drawing未运行。
- 原始artifact ID13524834970，digest sha256:cb43e60375da1814624f47d8a4708ae832fd05ff3031cee53a18548b995f211c，head4a2b4f461539cd4c5c80505a5172c2fcc3d071f2。下载ZIP和GitHub digest一致。
- 持久证据 ../evidence/native-42260887789/original.zip、artifacts.json、integrity.json、extracted/dimension-format/report.json、trace.jsonl、source.SLDPRT、supervisor.json。原件未修改。
- 第一真实失败：display writes changed geometry。volume11999.999999999998、area3799.9999999999995前后相同；centroid Y从5.514537417020185e-16变为8.271806125530278e-16 mm。当前不能据此宣称几何通过或完成验收。
- 相关修复：把比较基线从“未保存/前台”移到“已保存/后台”，新增无写入重复测量及状态控制；保留原有逐值精确的写后/重开比较，不放宽容差。无写入控制若不稳定则在setter前失败。
- 按最新统筹口径，已准备安装后公开CLI/daemon gate、确切host revision门禁、独立fixture摘要绑定、SDK/MCP上下文测试；公开模式默认关闭。当前白名单仍空，不标merge-ready，未运行公共验收。
- 新增共享修改 scripts/ci/windows/smoke-solidworks.ps1：仅显式DimensionFormatFixtureDirectory时提前运行专属gate并验证owned daemon退出；默认full流程保持原路由。CI新增dimension_format_public默认false，与internal模式互斥。
