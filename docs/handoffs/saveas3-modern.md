# SW2025 现代 SaveAs3 迁移交接

## 当前结论（2026-11-08 原件审计）

精确产品head `5a1b48dd1e6abb43560c63466c7bed2b55bf91d3` 的 [必要full 42369257219](https://github.com/YJBeetle/SWCLI/actions/runs/42369257219) 已结束failure。现代API已真实返回bool/errors/warnings，PRT/ASM/DRW三类保存重开及公共回执通过；整套full未通过，GLB仍未解决。未派发同head重跑，未改该次原件。

官方原artifact `13574345669`，`swcli-windows-hosted-42369257219-1`，6006787 bytes，SHA256 `a18dec74a3f0e37a04197b241dc8b244c397a8f7b2eb4b8630c21d39de5827af`。本地原件、官方run/artifacts JSON、下载回执、精确head源码和离线审计位于 `/Users/YJBeetle/.codex/task-artifacts/saveas3-modern/20261107/run-42369257219`，原ZIP内163文件均逐一对比一致。[结构化审计回执](../evidence/saveas3-modern-native-2026-11-08.json)；复现脚本为该artifact根的上级`audit-modern-original.py`。

- annotation准备夹具三类各一次现代保存、只读重开、clean/type、上传文件size/hash一致；其report明确preparation_only，不能充当full完成。
- 公共annotation前缀PRT/ASM/DRW正向/反向共6次另存，各自原文件hash、原始options保存重开一致、四个document ID均新鲜，宿主PID/revision连续。加units两次、properties两次，共10个请求有原始trace：每请求恰好一次`IModelDocExtension.SaveAs3`，旧ModelDoc2/Extension SaveAs系列0次。
- native-model组完成：50次document.save-as、1次STEP导出；assemblies组到达component原生PRT另存，以及零件STL/3MF/AMF成功导出，GLB随后失败。全部66份到达的daemon保存/导出回执均通过精确head schema，实际bool=true/errors=0/warnings=0。保留的STEP59843、STL684、3MF11838、AMF1499 bytes均经精确head内容解析器重新读取。
- 首失败request `f3373180-51c4-4628-aea0-b5712326e01b`：component-export.GLB，ExportVerificationFailed，non_empty=true/signature_valid=false，真实api_saved=true/errors=0/warnings=0。它没有保留拒绝文件，无法对**本次现代保存**声称BIN=0。历史旧API原字节证据不能替代本次原件。
- runtime矩阵重启daemon没有继承旧native-call开关，因此上面的“单次现代trace”仅限前缀10次，不扩展到矩阵51+5次。矩阵清理无错误，已退出拥有的CAD进程。box包装路径、装配中性导出未到达；extrude/revolve/simple-fillet的接口IID没有在此head记录，均待原生证据。

后续必要full由统筹协调组合head，避免各分支重复安装CAD。此分支继续保留原head证据；不自动重跑，不合主线、不发布。

## 工作位置与范围

- 持久 worktree 为 `/Users/YJBeetle/.codex/worktrees/saveas3-modern/SWCLI`，分支 `codex/saveas3-modern`，基线 `2d83afdc6c5c56b1a72157a84d54ee15cde770ab`。
- 已核初始状态干净、没有 `.codegraph/`。新 worktree 的独立 `config.worktree` 修正了继承失效的相对路径。已合品质分支、旧原 ZIP 与历史回执均保留。
- 仅面向 SOLIDWORKS 2025。采用 `IModelDocExtension.SaveAs3`。原生另存、中性导出、盒体模型保存三条生产路径共用 `hosts/windows_save_as.py`，活跃drawing fixture也调用它。

## 调用绑定与回执

官方签名为 `(Name, Version, Options, ExportData, AdvancedSaveAsOptions, Errors, Warnings) -> bool`。[官方 SaveAs3 文档](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs3.html)

适配器使用 `DumbDispatch` 保留显式参数类型，并预先 `_FlagAsMethod("SaveAs3")`，避免动态属性get探测。两个对象参数分别构造 `VARIANT(VT_DISPATCH, None)`。Errors和Warnings分别使用 `VARIANT(VT_BYREF | VT_I4, sentinel)`，调用后检查确实写出。版本0、选项1，方法只调用一次。该模式依据本仓库selection的显式dispatch null和pywin32动态包装实现。[pywin32 dynamic.py](https://github.com/mhammond/pywin32/blob/main/com/win32com/client/dynamic.py)

- `api_saved` 为真实bool，不能用errors=0推导bool。False且errors=0仍为失败。
- `save_errors` / `save_warnings` 为真实integer。非零warning保留，正常clean门禁要求0。历史旧接口null不被改写，历史audit继续使用各自精确head源码/schema。
- `save_attempted` 在实际保存调用前设true。COM异常时保留已经写出的输出码。未写出的输出、非bool返回会失败。
- trace固定命名 `IModelDocExtension.SaveAs3`。STL原件审计器统计全部ModelDoc2/Extension的SaveAs系列，要求总数1且接口为现代SaveAs3。拒绝场景要求这些调用均为0。
- 既有租约、CAS、临时激活恢复、目标独占预留、格式校验与临时文件清理继续执行。registry、描述符或worker命令恢复晚期异常保留首业务错误与保存回执，附加finalization_error。

## 便携验证

测试包含显式VT/null/BYREF、单方法调用、bool/errors组合、真实warning值、异常部分输出、registry/worker晚期异常、文件内容/状态、目标保护与清理。当前gate和fake receipts同步integer warnings，SDK由生成器更新。

日志根为 `/Users/YJBeetle/.codex/task-artifacts/saveas3-modern/20261107`。首次迁移回归的`portable-first.log`保留missing api_saved的fake迁移失败。修复后`portable-modern.log`为2139项通过、33项跳过。最终追加收尾保护后的`portable-final.log`为2143项通过、33项跳过，47.379s。`sdk-final.log`确认生成器一致、strict实现及11个消费者拒绝检查通过。actionlint v1.7.12与diff-check通过。旧v1.7.7将既有21个dispatch输入按旧10个上限报错，因此改用main已采用的当前版本校验。

## 必要原生验证

首个可审实现提交便携/SDK通过后，只派发一次该精确head的`ci.yml`，仅输入`native_full=true`。本分支该full运行使用`swcli-saveas3-modern-${github.ref}`独立组，cancel-in-progress=false，其他full/release沿用既有组。

复用完整Windows安装与正式入口。其annotation fixture准备先覆盖PRT/ASM/DRW三类真实另存、只读重开、clean/type与文件hash。后续矩阵覆盖原生保存、中性导出、part.create-box及前台恢复。每个实际保存须按新接口trace和真实integer错误/警告核验，首个非预期失败停止，不补保存调用或重启组。若GLB仍缺BIN，保留失败原字节并明确实际到达的覆盖范围。

仅mock不构成COM绑定通过。是否解决GLB必须读取实际BIN/mesh，且格式专属参数仍以既有边界为准。正常运行后记录run/head/链接结束等待，由统筹本人最终review、合并。系列完成后的正式发布仍需用户确认。

## 首个可审提交与必要原生运行

首个实现提交为 `89d4119a372b223c3847f2e905ecba2d6eb6f3bf`，已推送到 `codex/saveas3-modern`。便携/SDK通过后只派发一次 [Windows native_full](https://github.com/YJBeetle/SWCLI/actions/runs/42368723031)，仅传 `native_full=true`，其他输入默认。派发请求与返回原件为 `dispatch-native-full-request.json`、`dispatch-native-full-result.json`。当前尚无原生绑定通过或GLB解决结论。后续文档tip不替代此精确source head。

### 原生启动前补齐的STL首错反例

首次实现89d4119的run42368723031在portable单测阶段取消，尚无native job/CAD调用。补测发现False/errors32或native异常与STL恢复异常并发时，原有catch会覆盖首保存错误。现把首保存异常在偏好scope内部捕获进receipt，scope退出恢复异常单独记finalization_error。原正常恢复/清理继续执行。仅取消本分支这一个未原生启动的run，原请求与取消回执保留。此为具体回归修复后的新head校准，真实原生调用仍未重试。

补测完整回归2144项中仅旧revolve的CI并发拼接字符串断言失败，其原先要求revolve分组直接紧邻默认fallback。已将断言同步为新增modern精确分支条件且保留最后默认组的完整表达式。2143项功能检查通过，最终重跑日志为`portable-ready.log`。

最终ready回归2144项通过、33项跳过，47.953s，日志`portable-ready.log`。SDK生成器、strict6源文件和11个消费者拒绝检查再次通过，日志`sdk-ready.log`。首次run completed/cancelled的官方JSON证明native job没有steps，保存在`run-42368723031-cancelled-before-native.json`。新实现提交和新run将在本记录下追加。

## 当前必要原生运行

完整修复head为 `5a1b48dd1e6abb43560c63466c7bed2b55bf91d3`，已推送。唯一当前必要原生运行 [Windows native_full](https://github.com/YJBeetle/SWCLI/actions/runs/42369257219) 仅传 `native_full=true`，继承本分支独立并发组。新请求/返回记录为`dispatch-native-first-error-fix-request.json`和`dispatch-native-first-error-fix-result.json`。首次取消run没有native steps，当前新run未重复任何已失败原生保存。后续将按该head下载原ZIP/digest，核真实null/BYREF调用结果、PRT/ASM/DRW保存重开、中性导出、真实errors/warnings、trace和首失败。GLB是否解决由实际字节判定。正常运行后记录链接结束等待，统筹本人review。

初次一次性快照状态为`in_progress`，head核一致，原JSON为`run-42369257219-initial-snapshot.json`。当前结束等待，不启动watch或定时。

## 后续已有门禁的只读接口身份观察（尚无原生结果）

已准备`hosts/windows_definition_identity.py`，只在`SWCLI_TRACE_DEFINITION_INTERFACES=1`时，观察公共请求原有`GetDefinition`成功返回对象。它读取原对象`_oleobj_.GetTypeInfo()`、`GetTypeAttr().iid/typekind`、typeinfo名称及containing typelib的GUID/版本/LCID；不替换返回对象，不CastTo/QueryInterface，不增模型创建、selection access或保存调用。

安装类型库从明确绝对路径读取，默认`C:\Program Files\SOLIDWORKS\sldworks.tlb`，可由`SWCLI_SLDWORKS_TYPELIB`指定**已有绝对文件路径**。仅收集官方`IExtrudeFeatureData2`、`IRevolveFeatureData2`、`ISimpleFilletFeatureData2`的interface/dispatch类型条目及其IID，并保留文件SHA256、库GUID/版本。只有原对象自报的名称、IID、typekind和库身份全部匹配，`returned_typeinfo_matches_v2`才为true。缺失、旧IID、同名不同IID、coclass或其他库保持unavailable/unmatched，不用同名可调用成员推断v2。这里核验的是返回IDispatch自报typeinfo，不推断未执行的调用或接口强转结果。

pywin32实际公开`LoadTypeLib`，未猜用不存在的`pythoncom.LoadTypeLibEx`。此处只传入验证过的绝对文件路径；[Microsoft明确说明指定路径的LoadTypeLib不会注册类型库](https://learn.microsoft.com/en-us/windows/win32/api/oleauto/nf-oleauto-loadtypelib)。实现依据[pywin32的ITypeInfo/ITypeLib包装源码](https://github.com/mhammond/pywin32/blob/main/com/win32com/src/extensions/PyIType.cpp)，未引入任何硬编码产品IID。

诊断事件为stderr NDJSON `event=swcli.native-interface`，含request_id/operation/sequence/worker_pid，异常仅记diagnostic_error_type，不替换业务返回或首错。身份开关可单独开启以保留请求关联，而不放大全部native-call日志；只在内层`stage=read/call=GetDefinition`记录，fillet外层同名边界不重复读取。默认关闭时不读取身份。当前便携反例覆盖三类名字、同名异IID、coclass/异库、typeinfo/文件不可读、路径拒绝、原对象和原业务异常保持、观察/日志失败与内外层去重。

统筹下一次**本来就需要**的组合head gate中，在既有入口的进程环境设置该开关即可，runtime-sets的新daemon会继承它。保留所有相关`swclid.stderr.log`与`daemon.log`；按实际到达的extrude/revolve/simple-fillet分别核官方条目和自报IID。若流程先停于GLB而未到达revolve/fillet，后二者仍待证据，不为收集身份额外建模或重试。此分支没有额外派发Windows验证；另一个coverage负责人在`codex/native-api-observation-modern`处理`GetActiveConfiguration/GetSystemValue2`，这里未修改这两个getter。
