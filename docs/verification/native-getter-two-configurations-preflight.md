# 双配置 getter 与现有 STL 参数保护的前置证据

实现精确提交 `b9c5e3cacc38d5aa0cef9d56160d9307285524d8`；原 getter 产品提交已在组合产品0a00751内，组合时只需取本次新增诊断提交及本文档，不要重复合入旧历史。

2026-11-08：仅在 `codex/native-api-observation-modern` 准备验收补缺；未派发 CI、未改 main/SaveAs3/GLB 分支、未操作本地 VM。供统筹与既有 GLB 负责人在已经必要的同一次组合 full 中使用。原产品 `0a00751` 和 run `42405530053` 原件保持；统筹已核的 Default 配置值不能替代两个配置异值证据。本补丁尚无原生成功结论。

## 交付内容

- `scripts/ci/verify-native-getter-configurations.py`：诊断夹具，不新增公共 CLI/SDK/MCP 旁路。复用现有 through-all harness 的新建独占隐藏宿主、首错误、CloseDoc/ExitApp/WaitForOwnedProcess/句柄释放/CoUninitialize 规则。
- 原始 A 配置准备一个直径 16 mm 的圆草图；`IConfigurationManager.AddConfiguration2` 新建独立 `Getter_B`，仅准备阶段用 `SetSystemValue3` 将 B 设为 20 mm，并重建 A/B。配置名、参数个数、返回码和配置数量必须符合预期，不提供旧接口或其他绑定重试。
- 保存一份 `.SLDPRT`，强制现代 SaveAs3 成功、errors/warnings 都为 0。保存改变 FullName 后重新读取精确名称。分别在保存态和同一文件只读重开态，按 A=16、B=20 读取四个窗口。每次仅在窗口**之前**用 ShowConfiguration2 选当前配置；窗口内使用生产 `_descriptor`，不激活其他配置、不写值、不重建、不保存。
- 每窗口单次生产 GetSystemValue3，记录真实 single-BSTR 参数类型/Name、真实 tuple/list 返回类型/元素数/原米值及 mm 描述符。硬核 Name/FullName、IDimension.GetType 的 double-linear 参数类型、driven=2、dimension ReadOnly=false，以及前后文档类型/修改戳/修改标志/配置名/路径/标题/打开只读状态、配置 COM 身份和前台 COM 身份不变。文档只读与 IDimension.ReadOnly 独立记录。每次读后及最后文件 SHA256 不变，宿主 PID 不变。
- 监督器严格 600 秒调用边界、1800 秒组预算，只创建一次 worker，不重试或重启 CAD。失败保留 report/trace；超时仅终止诊断 Python worker，宿主清理未证实就 `cleanup_proven=false`，组合组必须立即停止，不能继续 full 或另起宿主。
- 正常退出还需对四个原始请求 trace 校验 worker PID、begin/end 完整、每窗口恰一 Get3、两个对象身份比较、现代配置三连读。白名单禁止窗口中出现 ShowConfiguration2/Set/Save/Rebuild/旧 API 等额外调用。trace 开关由监督器对子进程强制启用。
- `verify-stl-options.py` 仅加强**已有合法请求**的证据断言：结果 stl_source_state 前后相等且 unchanged=true；同 request_id、同 worker、完整 trace 中至少两组相邻 ConfigurationManager → ActiveConfiguration → Name，不能出现旧 GetActiveConfiguration。既有内部 6 / public 8 个参数场景、精确参数、输出字节和恢复断言均不变，无新格式或选项。

## 给组合 full 的接线

本分支不改 workflow。GLB 负责人在其 `codex/glb-export-repair` 的现有 **full job** 中纳入本补丁后，使用同一次安装和 artifact 根：保持已有 installed modern API contract 步骤在前，在原 native_tests（含可能首失败的 GLB）之前顺序加下列两个步骤。每步只允许 full 且精确 GLB 分支，默认不触发；不新增 dispatch 参数或独立安装/job，不修改原 19 个 full 组，也不要打开另一个 stl_options_public dispatch。

```yaml
- name: Observe saved current dimensions in two configurations
  id: getter_two_configurations
  if: ${{ needs.native-profile.outputs.profile == 'full' && github.ref == 'refs/heads/codex/glb-export-repair' }}
  timeout-minutes: 31
  shell: powershell
  run: |
    python -I scripts/ci/verify-native-getter-configurations.py --output-dir "$env:SWCLI_SMOKE_ROOT\getter-two-configurations" --swconst "C:\Program Files\SOLIDWORKS\swconst.tlb"
    if ($LASTEXITCODE -ne 0) { throw "Two-configuration getter first failure; preserve original report/trace and stop" }

- name: Verify existing legal STL source configuration protection
  id: stl_configuration_observation
  if: ${{ needs.native-profile.outputs.profile == 'full' && github.ref == 'refs/heads/codex/glb-export-repair' }}
  timeout-minutes: 31
  shell: powershell
  run: |
    python -I scripts/ci/verify-stl-options.py --output-dir "$env:SWCLI_SMOKE_ROOT\stl-configuration-observation" --swconst "C:\Program Files\SOLIDWORKS\swconst.tlb" --phase public
    if ($LASTEXITCODE -ne 0) { throw "Existing STL source-configuration first failure; preserve original evidence and stop" }
```

public STL 脚本沿用原独占受限 worker、精确已校准选项与现有 8 场景，包含实际 STL 内容/偏好完整恢复/保存重开和后台文档恢复。脚本自身会启用现有必要环境开关。此步不会把 GLB 设置成 STL 或扩大 public 支持域。两步放在原 full 前，均须成功并证明清理后才能继续；任一失败不补跑剩余组。精确组合 head、派发时间和最终合并由统筹本人审查安排，本线程不派发。

现有 artifact 收集必须包含上述两个可见目录；不另改隐藏上传策略。关键原件：getter 的 `report.json`、`trace.jsonl`、`worker.stderr.log`、`supervisor.json`、`two-configurations.SLDPRT`；STL 的 `stl-calibration.json`、`daemon.stderr.log`、原生源文件和既有 STL 输出。下载原始 ZIP 后核 head/摘要与四窗口值、trace/cleanup，不因 job 其他步骤失败抹掉前置证据，也不将前置通过冒充 GLB/full 通过。

## 官方接口依据

- [AddConfiguration2](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IConfigurationManager~AddConfiguration2.html)：七参数、返回 Configuration，使用 modern 2 版本。官方 2025 动态页未获得正文；这里列出实际可读官方 2021 正文，不声称已核 2025 本机绑定。
- [SetSystemValue3](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IDimension~SetSystemValue3.html) 与 [swSetValueInConfiguration_e](https://help.solidworks.com/2025/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swSetValueInConfiguration_e.html)：准备阶段只指定 B；从安装 swconst 读取 swSetValue_InSpecificConfigurations，非猜常数。
- [ShowConfiguration2](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~ShowConfiguration2.html)：仅窗口之间准备当前配置。
- [IDimension.GetType](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetType.html) 返回 [swDimensionParamType_e](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDimensionParamType_e.html)，**并非** IDisplayDimension 的 swDimensionType_e。夹具从安装类型库读取并核 swDimensionParamTypeDoubleLinear=0。
- [IDimension.Name](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDimension~Name.html) 与 [FullName](https://help.solidworks.com/2017/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~FullName.html)：保留原名，保存后按实际完整名称绑定。
- Get3 与 current configuration 的原迁移官方依据见 [已有实现说明](native-api-observation-modern.md)。安装签名检查仍复用组合分支现有 verify-modern-api-contract.py；本夹具保留 swconst hash 与实际枚举读值，原生调用失败即停止。

## 本地验证边界

新增便携检查模拟保存后 FullName 变更、两个配置异值、只读重开和四个相关 trace；覆盖值/shape/Name/type/driven/readonly 错误、stamp/配置身份/前台漂移、首 getter 异常、类型库缺失/重复/错误枚举、STL 旧 API/不完整/跨 worker/非相邻配置链。它们是代码行为验证，不能代替 SOLIDWORKS 真实返回形状、配置持久化和原件验收。最终日志摘要见同目录 portable JSON 回执。

最终本地验证：新增9项；完整2153项OK（28环境跳过），SDK strict6文件/11消费者类型拒绝例及安装资源no-COM通过。机器回执和日志hash：[portable回执](native-getter-two-configurations-portable.json)。日志位于本工作树忽略的 `artifacts/native-api-observation/`，不把生成日志混入推送。
