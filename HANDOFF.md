# 图像品质 / 格式专属导出选项：独立对话接管

已停止编辑，等待独立侧边对话接管。当前为未提交开发草案，不能视为已完成或已原生通过。

## 隔离位置与权限

- Worktree：`/Users/YJBeetle/.codex/worktrees/docprops-export-options/SWCLI`
- 分支：`codex/docprops-export-options`
- 起点：`3bda2c0`（当前任务创建时 main，v0.2.3 release API diagnostics merge）。未合入其他 docprops 分支。
- 持久证据目录：`/Users/YJBeetle/.codex/task-artifacts/docprops-export-options`
- 无 `.codegraph/`，所以跳过 CodeGraph。开始时 clean。
- 用户最终要求：独立持久 worktree / 分支开发，未来可独立中文 commit、push 与 GitHub CI；禁止 VM，不汇 main，不创建 tag/release，不动 Docker/MacSW。
- 最新接管指令优先：原代理停止编辑；本轮 **没有 commit/push/dispatch**。新对话重新核状态后继续。

## 需求与证据边界

用户截图明确指 `Save As → Extended Reality Binary (*.glb) → Options…`，真实首要需求是格式专属选项可由 CLI 设置，不是预设 Image Quality 等价于 GLB resolution。

官方 2025 XR 页面列六项：Export Views / Cameras / Lights / Motion Studies / Exploded Views / Use Draco；2025 SP2 将其移到 System Options Export → GLTF/GLB，选项不变。**还没有查实六项公开 API 映射**；不要臆造 IExportGltfData、常量或 dict ExportData。未知项保持明确 unsupported，不做假支持、空壳参数或直接注册表写入。

既有只读研究已持久保存到 artifact 目录 `glb-quality-research.md`，含官方链接、本地 TLB / header hashes、两控制域区分及最小验证计划。`swconst-2025.tlb` 与 `swconst-2025-sdk.h` 是离线证据；未加载 COM。

- `swconst-2025.tlb` SHA256 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`
- `swconst-2025-sdk.h` SHA256 `b4951b6c123a255d47d88fbcadc8f4b50cce8fd1ab637a37c2e5edbf388c7ce7`
- 官方新增核证：`GetUserPreferenceDoubleValueRange` status=0 表示 current/min/max；1 只有 current；-1 获取失败。官方正文 https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IModelDocExtension~GetUserPreferenceDoubleValueRange.html

## 当前未提交代码（6 文件）

1. 新 `src/swcli/document_image_quality.py`：纯 catalog / schema / full snapshot 验证 / exact CAS / shaded mode 联动 receipt 草案。
2. 新 `src/swcli/hosts/windows_document_image_quality.py`：part-only read/set adapter 草案。
3. `src/swcli/operation_schemas.py`：新增两操作及 required stamp/lease，constructor lease_guarded 现在同时覆盖 optional/required。
4. `src/swcli/result_schemas.py`：两结果 schema 与 snapshot/lifecycle 一致性检查草案。
5. `src/swcli/daemon/operations.py`：两 handler 接线。
6. `src/swcli/cli.py`：两命令及严格 JSON 完整 snapshot 参数解析草案。

操作：
- `document.image-quality`：当前限定 part 文档读取完整 snapshot。
- `document.image-quality-set`：`field`, typed `value`, `expected_quality` 完整 CAS；`expected_update_stamp` 与 `lease_id` required。

写字段：`shaded_mode`（coarse=1/fine=2/custom=3）、`shaded_deviation_mm`、`optimize_edge_length`。本轮只做 part profile，避免装配体设置向引用零件传播。snapshot 同时观察只读 `save_tessellation`、`apply_to_referenced_parts`，且保留 native 原值与 deviation range。

写 deviation 必须调用者先显式把 mode 设置为 custom，且实际 range status=0、值在原生范围内；不自动连调两个 setter。模式写允许 deviation/其 range 的显式 `linked_changes`，其他成员保持；**这个联动允许范围仍需独立审核和原生证据确认，不能冒称校准完成**。Double CAS 精确数值相等（JSON int/float等值允许，bool不混用）；目标 readback/noop 容差 1e-12。

生命周期复用当前 A18：foreground/edit 基线先于 state；观察后复核；setter/可能 SetSaveFlag 前重核 writable/context；native False/异常首错退出，无 retry / rollback / global setter。成功 readback 后最多一次 dirty 标记，标记后完整重读；失败保留 mutation。原 A18 文件未改。

CLI：`document image-quality [selector]`；`document image-quality-set FIELD VALUE --if-quality '<complete JSON>' --if-update-stamp N --lease TOKEN [--document ID]`。JSON 拒绝重复字段和 NaN/Infinity，并检查完整 normalized/native 一致性。schema仍需完整 portable tests。

## 已执行检查 / 尚未完成

已执行：
- 工作树状态/分支/HEAD，无 `.codegraph`。
- 新纯模块、catalog、result schemas、daemon handlers 可导入，无 COM。
- 两 request/result 与 quality schema 通过 `Draft202012Validator.check_schema`。
- 确认 set context required stamp/lease 且 `lease_guarded=True`。

尚未执行：
- **没有新增或运行本功能 portable tests**，也没跑现有回归；不要把“schema valid”说成行为通过。
- SDK generator 未修改、SDK 未重生成；现有 SDK reproducibility check 预期会因新增 catalog 两操作失败，需要接管者完成。
- MCP 无专用源码改动；既有 generic `execute` 可透传 operation，但必须补 schema discovery / exact typed payload / session-CAS-lease / single-send portable tests。
- README、随包 usage/skill、design docs 未更新；没有 native fixture/gate/workflow 接线。
- 未调用任何 VM/native API/设置，未实际创建 SW host/文档，未 dispatch GitHub Actions。

必须先修/审的具体点：
- `native_return` 当前 result schema 是 BOOL，但 adapter 在拒绝非 True 返回前记录原始值；若 native 返回 None/int，result validator 可能遮住首因。应以可序列化原始证据保留首错，而不是吞或重试。
- `_range` 使用一次显式 BYREF double 调用；真实 pywin32 包装返回形状/类型未校准。不能失败后换方法再试。
- mode 联动可以改 deviation/range；是否应收窄 range 的联动范围，要用真实证据决定。
- first profile 仅 part，不得直接放开 assembly/drawing 或 apply-to-referenced/save-tessellation 写入。
- 增补 post-property/read state drift、readonly 切换、foreground/edit/config 漂移、CAS nextafter、noop zero setter、native False/exception partial、unrequested field、完整 raw save/reopen 与非法 bool/int/nonfinite/nested JSON 反例。

## 精确 CI 后续建议（无 dispatch）

现有 `.github/workflows/ci.yml` 只有 `native_full` 开关；`solidworks-e2e` 安装完默认跑所有既有属性/annotation/visible/full gates。**不要用现有 full 来假装测到了新功能**。原代理已向 root 提出增加 targeted `native_profile=image-quality`（或独立复用安装的 workflow）建议，但尚未获共用接线决定/未修改 workflow。

需要接管者真正提交的新样件/验证：
1. 在 CI 自己拥有的全新 host 创建圆柱（circle sketch+extrude）与平面 box 对照，保存 native 基线；导出 installed swconst 的相关精确 IDs/modes，与 catalog 比对。
2. 使用已安装公共 CLI/daemon（和 SDK/MCP调用至少一个映射验证）读完整 image-quality；每个请求 timeout=600，整组 hard=1800，超时只按 owned 生命周期策略处理，绝不重试 API 或延长预算。
3. 每个字段分别单 setter、独立 Get/完整 snapshot CAS、unrequested 保持、native成功/False明确；变更另存 native，关闭自己文档后以新 handle 只读重开，核 actual type/path/access/clean/raw snapshot/hash/geometry。save/reopen 不放宽容差或漏项。
4. 在两个几何 fixture 上固定所有 XR格式选项/材质/配置，以粗/细/合法custom deviation 做 GLB A/B；解析 primitive modes、indices、POSITION/NORMAL、mesh 数、extensions。如使用 Draco，必须实际解码才计拓扑/位置/法线；不能把压缩体大小当细分成功。未具备解码器时明确这部分 unsupported / 未证明，不能写 true。
5. 要求曲面与平面控制的真实产物对比，记录“观察到什么”，**不预设 Image Quality 必然改变 GLB triangles**。截图不足以区分网格、法线、材质。
6. 所有 group/trace/cleanup 首因和部分修改原件上传 artifact；新 fixture/gate/control portable tests 通过并审阅 SHA 后，由 root 协调单次精确 branch dispatch。默认 full 行为需保持兼容。

## 恢复命令

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-export-options/SWCLI
git status --short
PYTHONPATH=src /private/tmp/swcli-a14-test-env/bin/python -m unittest discover -s tests -p 'test_document_image_quality*.py'
PYTHONPATH=src /private/tmp/swcli-a14-test-env/bin/python scripts/dev/generate-sdk.py --check
```

上面是待补测试后的建议命令；当前尚不存在 `test_document_image_quality*.py`，因此不能用空发现“0 tests OK”作为通过。
