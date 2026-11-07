# GLB 首失败诊断与待证候选

## 运行时取证实现与组合验收前置

现代 API 产品 `0a00751e44823ca46237000479754634bf50a418` 已在本分支与 main `960839e52d0c433c817e71e02493a27681f7e858` 合并，merge 为 `0e288dd`。两侧 CI 分组、交接历史和 main 三组偏好晚期错误保护均保留。main 新增三偏好夹具已适配 ConfigurationManager.ActiveConfiguration，保留配置漂移、首错误与 worker receipt 断言。

`SWCLI_GLB_RUNTIME_DIAGNOSTICS=1` 才启用新增观测。它包围原来那一次现代 SaveAs3，生产暂存名仍沿用原始后缀。调用前后的 manifest 放在目标目录下可见的 `swcli-glb-diagnostics-<uuid>/`，与原 request_id、Python worker PID、SOLIDWORKS PID 对应。阶段分别为 pre-save 和 post-save-before-validation。

- 保存前后读取同一暂存 stem 前缀的目录项，包含点号/隐藏文件，记录 size、mtime、属性、SHA256 和复制文件映射。复制使用可见 `.bin` 文件名，保留内容原字节。每阶段最多 128 个文件、64 MiB，单项观测 15 秒，目录项为非普通文件/reparse、发生竞态或超过边界时明确标为 unknown/incomplete。
- 使用同一观测到的 SOLIDWORKS PID 打开只读进程句柄，前后枚举最多 2048 个模块，筛选 sldgltf/SPAXGLTF/VisGltf、Draco 与 XR exporter 的实际路径，读取实际文件及产品版本。句柄在 finally 关闭。
- 保存前从显式安装路径 `SWCLI_GLB_DIAGNOSTICS_SWCONST` 读取 swconst.tlb、SHA256 与版本，要求 major 33。只对实际 GLTF/GLB/Draco/XR 相关枚举，依据已知全局 preference 枚举类型选取已有 getter。其他枚举仅记录原 ID，getter 不可读时记 unknown。保存后仅做文件与 OS 观察。
- 文件访问监控字段明确为 unknown，当前没有经过验证的本 PID 有界采集器。模块加载清单也可能记录 inaccessible/unknown。诊断收集、manifest 或 stderr 写入失败均不能改变保存结果或原错误。

CI 仅在 `codex/glb-export-repair` 的现有 native_full 步骤开启该开关，复用安装和所有原完整组。该 full 使用独立并发组，cancel-in-progress false。没有新 dispatch 输入。取证文件目录可被现有关闭隐藏文件上传的动作正常收集。

统筹补充的两配置异值 getter 与 STL 新配置入口 proof 仍是本次 full 的前置。原 getter 负责人准备精确门禁接线，待其提交与统筹本人审查完成后，才组合到同一必要运行中。当前未派发本轮 native_full。便携组合2567项OK（27跳过），新增10项取证测试、三偏好56项组合保护、SDK strict6文件/31类型拒绝例、actionlint及YAML检查通过。日志在 `/Users/YJBeetle/.codex/task-artifacts/glb-export-repair/20261108/`，首轮夹具不兼容和修复后的日志均保留。

首阶段离线审计已完成。当前可复核的内容失败是原生 GLB 声明 720 字节嵌入 buffer，实际 BIN 长度为 0。导致原生写器产生空 BIN 的上游首因仍缺运行时证据。当前生产容器校验正确拒绝该文件。

## 工作边界与来源

独立工作树为 `/Users/YJBeetle/.codex/worktrees/glb-export-repair/SWCLI`，分支 `codex/glb-export-repair`，基线为本次 fetch 后的 main `960839e52d0c433c817e71e02493a27681f7e858`。执行源码取自失败运行精确 head `0a00751e44823ca46237000479754634bf50a418`，以 git blob 的 SHA256 记录。现代 SaveAs3 迁移由原负责人处理。本阶段提交离线报告和验证方案。

本次原件根为 `/Users/YJBeetle/.codex/task-artifacts/saveas3-modern/20261108-combined/run-42405530053/`。原 native ZIP 为 9159929 字节，artifact `13587729372`，SHA256 `a55c00d7e4b7d07cbece2acd0ef5847138efc074f9ddaa3bfead0aef9e967ec9`，实际重算匹配原 metadata。[失败运行](https://github.com/YJBeetle/SWCLI/actions/runs/42405530053)

机器可读审计为 `docs/evidence/glb-export-failure-2026-11-08.json`。持久审计脚本、原 GLB 副本、选定 trace 和安装日志证据在 `/Users/YJBeetle/.codex/task-artifacts/glb-export-repair/20261108/`。

## 本次原件的直接结论

- 首失败来自 assemblies 组中的零件 `component.SLDPRT`，文档类型为 1。相同源先前的 STL、3MF、AMF 均通过当前容器校验。
- GLB 为 `component-export.invalid-native.glb`，3800 字节，SHA256 `2d49602f1bbd443d60b8975d249b4ed8defb5a5948b869eabfddacb1974a2c5c`。ZIP 成员与解压件逐字节一致，CRC32 为 `66faabfe`。头部声明总长也是 3800，JSON chunk 为 3772 字节，第二个 BIN chunk 长度为 0，恰好到文件末尾。归档压缩或解压未改变该成员。
- JSON 的唯一 buffer 无 URI，声明 byteLength 720。三个 bufferView 分别覆盖 `[0,144)`、`[144,432)`、`[432,720)`。JSON 声明了 36 个索引、24 个位置和法线，但文件没有这些数据。JSON 未声明 Draco 或其他压缩扩展。当前 main 的原容器校验独立重放返回 False。
- glTF 2.0 的无 URI 首 buffer 由 BIN 提供，其长度最多允许多 3 个对齐字节。该文件不满足这条规则。[Khronos 规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#glb-stored-buffer)
- 请求 `7712054a-7f17-495b-a30a-7d37690bd042` 的 108 条 native trace 位于 `hidden/runtime-sets/daemon.log`，包含 54 个完整 begin/end 对，同一 COM worker PID 为 936。`IModelDocExtension.SaveAs3` 只有一次，耗时约 16 ms，无 native error 事件。公共回执为 api_saved true、errors 0、warnings 0，随后返回 ExportVerificationFailed。原 trace 不记录方法参数。
- 精确执行源码调用 `SaveAs3(name, 0, 1, null-dispatch, null-dispatch, byref-I4-errors, byref-I4-warnings)`。本次 `modern-api-contract/report.json` 的 SW2025 typelib 实测也列出这七个参数。首参数是既有暂存路径，最终发布在内容校验后执行。

## 路径、暂存与大小写

本次请求目标为 `component-export.GLB`。精确源码的常规暂存模式为 `.component-export.<uuid>.swcli.GLB`，沿用用户后缀。该次普通 full 清除了内部 plain-staging 开关，工作流仅设置 rejected-GLB 保留开关。实际随机暂存名未记录在回执或 trace 中。目标路径为 ASCII，JSON 解码后的路径分隔符正常。

原 ZIP 中没有 `.bin` 或 `.gltf` 配套成员。不过本次上传步骤明确为 `include-hidden-files: false`，暂存文件又以点号开头。因此归档成员的缺席不足以排除运行时隐藏 sidecar 的存在、错误路径或中间文件丢失。GLB 的无 URI 声明仍要求嵌入数据，现有内容失败成立。

补查历史原件得到以下对照。历史 ZIP 均重新核 SHA256，只作为路径假设的辅助证据。

| Run | 保存 API | 由精确源码与诊断分支确认的暂存模式 | GLB 结果 |
| --- | --- | --- | --- |
| 42265919228 | IModelDoc2.SaveAs3 | `.cylinder-coarse.<uuid>.swcli.glb` | 3816 bytes，声明 3696，BIN 0 |
| 42301795947 | IModelDoc2.SaveAs3 | `swcli-<uuid>.glb`，ASCII 单扩展小写 | 同上，GLB SHA256 与前行完全相同 |
| 42405530053 | IModelDocExtension.SaveAs3 | `.component-export.<uuid>.swcli.GLB` | 3800 bytes，声明 720，BIN 0 |

当前现代 API 运行没有成功的小写对照。历史小写单扩展仍失败，使“单凭大小写或多扩展名解释全部失败”的依据不足。它也不能回答现代写器是否另有大小写分支。Windows 文件系统的大小写规则无法单独证明写器内部的字符串处理行为。

可审的最小待证候选仅规范内部 GLB 后缀，保留用户最终目标名称。它尚未作为生产修复应用或验证。

```python
staging_suffix = ".glb" if export_format == "GLB" else output_path.suffix
# 常规暂存文件仍使用既有 stem/uuid/.swcli 前缀，仅替换末尾后缀。
f".{output_path.stem}.{uuid4().hex}.swcli{staging_suffix}"
```

候选的便携验证应覆盖大写、混合大小写及小写目标，内部后缀、最终文件名、一次保存、失败时原目标保留、现有空 BIN 拒绝均需独立断言。真实 GLB 是否恢复需要原生字节证据。

## 官方 2025 说明与已装组件

SOLIDWORKS 2025 官方更新说明确认 SP2 把 XR 导出选项移入 System Options > Export > GLTF/GLB，列出场景、动画和 Draco 选项。它说明支持的导出入口和选项，未提供空 BIN 的成因。[官方 2025 更新说明，印刷页 172](https://files.solidworks.com/Supportfiles/Whats_new/2025/English/whatsnew.pdf)

2025 SaveAs3/枚举在线条目在本次访问中返回帮助站外壳或 403，未取得 GLB 专用数据对象或选项的可靠正文。API 参数契约依据本次安装的 2025 typelib 与精确调用源码。后续选项读取需从实际安装的 swconst.tlb 确认名称、类型和数值。

同次原安装日志 artifact `13588666282` 为 3278666 字节，SHA256 `eced0a0b91ec041025237d28aedc8cbe332b50f6df645ce2769355e9095c8055`，已核 GitHub digest。原件保存在上述独立诊断目录，相关非敏感行提取为 `installer-gltf-evidence.json`。

- `sldgltfu.dll` 的 MSI Action 为 Local，有 FileCopy 与 ComponentRegister，版本 33.5.0.53。
- `SPAXGLTFBase.dll`、`SPAXGLTFVisualization.dll` 同样有 Local/FileCopy，版本 6.427.0.25092。`VisGltf.dll` 为 6.427.3.25060。
- 旧 `SWXRExporter.dll`、`.tlb`、资源组件的 Action 为 Null，其安装/卸载条件均 false。结合 2025 架构变化，这些行不足以证明应启用旧 add-in 或把当前失败归为漏装插件。

这些安装记录发生在 runtime overlay 之前。当前仍缺实际导出时加载的模块路径、版本和依赖解析结果。

## 下一次必要验证应补足的证据

先准备以下观察，使一次新候选调用具有判别力。相同失败 API 的原参数重跑不提供对照价值。

1. 在保存前记录传给 SaveAs3 的精确暂存路径、后缀及目录快照，保存后、finally 清理前再次枚举，明确包含点号/隐藏文件。只保留该次暂存前缀对应的文件，记录每个文件长度、SHA256 和时间，并放入可见诊断目录供原样上传。归档缺席才能与“从未存在”区分。
2. 通过 OS 只读清单记录导出器与依赖的实际加载路径、版本，以及导出期间失败的文件访问路径。对未记录的加载/文件 I/O 状态明确保留 unknown。MSI 的 FileCopy 不能替代该运行时观察。
3. 从已装 2025 typelib 只读解析 GLTF/GLB/Draco/XR 相关 API 与选项名称、类型、值，再读取实际偏好。未知 ID 或文档缺口保留为缺口，不猜 enum、设置 ExportData 或改变全局偏好。
4. 若整合后的候选确有必要进行原生验证，使用原装配组的同一零件场景和现代 SaveAs3，保持单次保存。保留真实回执、完整 trace、失败原字节及上述观察，首失败结束该组。新增信息应能区分名称/sidecar、加载依赖和写器内部缺失数据，才有依据选择下一项最小实现修复。
5. 成功须同时满足原有容器/几何门禁、BIN 与 accessor 实际范围、源文件/文档状态、原目标发布及同组清理要求，并由统筹本人复验原件。此次离线阶段已完成原 GLB 拒绝重放、其余三种格式重放和完整 trace 配对检查。

本阶段未派发 CI。系列的最终 review 与 main 集成由统筹本人完成，正式发版仍需用户最终确认。
