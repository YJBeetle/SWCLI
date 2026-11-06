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
- 提交/推送：待记录。
- CI：待通过便携测试/接线检查后，仅触发当前head的 `ci.yml`，`dimension_format_calibration=true`，`native_full=false`。原生600秒、组1800秒、首失败停止。
- 未完成边界：内部原生校准与安装后公开CLI验收严格区分；即使内部成功仍需公开入口全链路证据后另行开放写入，不合并、不发布。
