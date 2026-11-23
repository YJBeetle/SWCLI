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

## 后续GLB首失败原字节保留与验证状态

新增内部诊断开关`SWCLI_PRESERVE_REJECTED_GLB=1`，仅在GLB已经由内容门禁拒绝之后，把这一次保存的原临时文件复制为同目录`<output-stem>.invalid-native.glb`，以`xb`独占创建。不会变更既有`.stem.uuid.swcli.GLB`暂存名称，不新增保存、重试、回退或模型写入；不会把拒绝文件发布成成功artifact。原目标及已有诊断文件均保持；复制失败附加`diagnostic_recording_error`，原ExportVerificationFailed仍为首业务错误，原临时文件按既有finally清理。正向成功/非GLB不记录。后续原件审计从上传原始文件计算hash并读BIN/mesh；开关本身不构成GLB修复或字节结论。

统筹后续组合head的既有full入口可同时设`SWCLI_TRACE_DEFINITION_INTERFACES=1`、`SWCLI_PRESERVE_REJECTED_GLB=1`，保留继承进程环境及正常上传目录即可；没有增加workflow_dispatch输入、独立native job或同head重试。原run42369257219不受后续开关和代码影响。

本轮全部新增诊断/保留逻辑的便携回归：2156项，35项平台/可选依赖跳过，45.493s，日志`portable-diagnostics-ready.log`。其中两项新反例覆盖不改暂存命名/单次保存以及已有诊断文件不被覆盖，十项身份反例覆盖原对象/首错与官方身份匹配边界。SDK生成器、strict6源文件及11个消费者拒绝检查通过，日志`sdk-diagnostics-compatible.log`；本轮使用mypy1.18.2，符合现有CI的`>=1.15,<2`。起初重建临时环境时误装无上限mypy2.4.1，其拒绝Python3.9目标的日志`sdk-diagnostics-ready.log`原样保留，已换回兼容版本，未改产品或CI版本约束。便携首轮隔离入口因重建环境未安装本地包而失败，也保留`portable-diagnostics.log`；安装本地包后完整回归如上。当前诊断只获便携验证，尚无新的Windows原生身份或GLB原字节结果。

## 2026-11-08 三项现代API组合验收候选

按统筹指令，在当前SaveAs分支合入getter精确tip `e801a95b1402f22d0638c74809125ff7add3f4da`，保留`aecd560a9c0293f1a97d33d91ab400dbb2b651f9`配置和`1cdbff41a0594440eda17e068c3d42e1fb24579c`尺寸迁移历史。合入提交为`5c102541e3040a77455d07da6ee64e66ccfe500e`，唯一冲突为windows_documents导入块，两个helper均保留。先检查main `ce6606fa879e4c611d15d98a8ce4985e74d45881`：仅新增弃用API审计文档，没有新生产依赖，未修改或合并main。

已先读取getter线程当前接线审查和其独立交接`1cc16f3`中的建议，原路径为`/Users/YJBeetle/.codex/worktrees/native-api-observation-modern/SWCLI/docs/verification/native-observation-saveas3-wiring.md`。本次仅合指定e801a95，不把后续审查文档冒充产品变更。采纳下列组合补强：

- full仍为原有19个完整组、原有步骤各一次。顺序前置为native-model、continuation-front-diameter、rectangle-front、assemblies，然后其余原组；连续宿主的modeling+diameter两步不拆组。这样两种Get3读取不再必然被已知GLB首失败挡住。同步本版汇总canonical顺序；未到达仍SKIP、首业务错误仍优先。core计划不改，历史原件不重写。
- 已有annotation drawing夹具在首次保存前和只读重开后，仅读取`_inspect_configurations`并分别留原结果；严格要求active=None、names=[]、count为实际int0。没有新增fixture、保存或host。同样补在较后公开drawing结构前后，未对兼用于part source的结构函数套工程图断言。便携反例拒绝缺键、非空及bool count；旧mock分开零件和工程图配置，不放宽断言。
- 本分支既有full的native_tests步骤继承三项内部诊断环境：`SWCLI_TRACE_NATIVE_CALLS=1`、`SWCLI_TRACE_DEFINITION_INTERFACES=1`、`SWCLI_PRESERVE_REJECTED_GLB=1`。无新增dispatch输入或安装job；runtime新daemon因此保留方法trace和接口身份。原Get3返回另发只含return_type/container_length的`swcli.native-return-shape`事件，取同一次原返回，不再查询，不写入或记录尺寸数值；实际配置/数值/mm由公共回执及固定源码对应。
- 同一既有native job增加10分钟上限的只读类型库预检，不启动CAD。保存sldworks/swconst原文件hash、library GUID/version、官方接口IID与方法参数名。严格核SaveAs3七参、GetSystemValue3两参、ActiveConfiguration零参及actual integer swThisConfiguration=1/swSpecifyConfiguration=3。缺失/冲突即首失败停止；报告明确native_binding_accepted=false，类型库存在不能替代真实绑定。

最终便携2172项通过、35项平台/可选依赖跳过，45.252s；SDK generator/strict6文件和11消费者拒绝例通过；actionlint1.7.12与统一CI路由通过（只输入native_full=true）。日志根`/Users/YJBeetle/.codex/task-artifacts/saveas3-modern/20261108-combined`：最终`portable-combined-ready.log`、`sdk-final.log`、`actionlint-final.log`、`native-profile.log`、`dispatch-profile.log`。初次组合接线回归在`portable-ready.log`保留summary顺序及旧drawing mock错误；下一次`portable-final.log`保留旧位置索引断言；修正后最终回归如上，均没有为这些便携问题派发native。

后续只派发本候选精确head的一次必要native_full。派发请求、返回、单次初始快照与精确head/run链接放在该日志根，不更改运行中的产品head，不watch或循环查状态。若GLB仍true/0/0却内容失败，保留该首次错误与`*.invalid-native.glb`原字节，不换参数再试。多配置异值不从默认单配置样件外推；特征定义三类IID与box/装配中性导出均按实际到达范围审计。本次实现与portable通过不构成新组合原生验收通过；最终原件审查、main合并由统筹本人完成，发布仍需用户确认。
