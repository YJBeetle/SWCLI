# GLB 强类型单次对照：同一 owned host / 同一文档

状态更新（2026-11-12）：[C# 同 host 候选源码、包装器与便携测试](../../scripts/diagnostics/typed_glb/README.md)已准备，尚未实际 Windows PIA 编译、管道/COM 身份握手或 GLB 调用。本路未操作 VM/CI/push，不改生产保存绑定、暂存命名、偏好或容器校验。统筹亲审后逐级安排，原600秒native/1800秒group边界保留。

2026-11-11：统筹先收敛为 [装机interop零CAD反射工具](installed-interop-metadata-check.md)，消费已有类型库原件，不重复采集；当时的跨进程桥接仅设计，暂不实现。2026-11-12 固定文件采集有限证据通过后，统筹授权按下述既有路线准备源码及便携测试，执行仍待其亲审。

用户补充的历史 Blender 实际可用线索已先行[复核现有成功/失败原件](glb-history-offline-2026-11-12.md)：真实 assembly BIN720 成功与 part BIN0 失败并存，不能泛化历史一直失败；用户当时文件 SHA 尚未对应，也不据此改换本候选样件/路径。

完整的源码摘要、离线检查和未执行边界见[准备回执](../evidence/glb-typed-control-preparation-2026-11-12.json)。

## 已核对的基准原件

统筹本地 `glb-host-control-70d8c9e-01` 位于 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/`。report SHA256为 `7bcb3bc4119a67e7576abd91548455aa7c85280ed0d95767634501431fded19f`，与local-supervisor记录匹配。40×30×10零件的SLDPRT SHA为 `4f975836ffbf38a58d05802c943701c8bab67f0ae0388b1e913e0a8f1df0f7b5`。STL684B、3MF10821B、AMF1476B均由当前严格校验重放通过。

唯一GLB调用原生返回true/0/0，但3732B文件JSON3704、BIN0，声明无URI buffer720。SHA256为 `04b83d8e0a2ebccd297fc116d17964e183eb081717ef27e1049d6340abcda2ba`，与可见after-1.bin逐字节一致，当前严格校验拒绝。SW PID8772、runtime33.5.0；实际native-call worker1780，监督器启动PID9332，必须分开记。两阶段module enumerated_count均448，保留的是筛选结果而非448项完整路径清单；筛选/prefs为空不能证明不存在。文件访问监控unknown。

## 第一阶段：仅检查装机interop及参数契约

在统筹指定 `C:\Workspace` 独立目录，由不创建COM对象的metadata/reflection工具检查装机DLL；不能为找库扫描任意机器位置或下载新interop替代装机版本。

- 记录SOLIDWORKS exe、sldworks.tlb、swconst.tlb和interop DLL实际绝对路径、SHA256、文件/产品版本、程序集FullName、GUID、ImportedFromTypeLib/TypeLibVersion、PE/运行架构。先核实际2025/major33配对，不能只看文件名。
- 对实际IModelDocExtension GUID解析的SaveAs3，记录DISPID、InvokeKind、返回原生类型及七参的TYPEDESC递归结果、参数flags；与装机interop的返回类型、每参ParameterType、IsIn/IsOut、MarshalAs（缺失也明确记录）、可选/default标记、PreserveSig/相关属性逐项对照。不是从其他接口复制DISPID或自行声明替代COM接口。
- 尤其确认Name BSTR、Version/Options整数、两个可空对象输入，以及Errors/Warnings的输出整数；明确C# null将依据哪些实际封送元数据处理。发现不匹配或无法解释的缺口，停在0次保存，不用Type.Missing/DBNull/整数0逐个尝试。
- 编译目标保持与原Python调用端相同x64；编译器、框架和interop使用前先确认已存在。helper编译阶段不创建/连接SOLIDWORKS。此阶段不取得导出器成功结论。

官方可读的[SaveAs3七参C#签名](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs3.html?format=P&value=)来自2026页面；它是设计参考，不能冒充已读2025正文或替代以上装机2025元数据验证。

## 第二阶段：把已有接口明确交给C#，不通过ROT查找

原Python诊断driver仍负责创建并持有唯一owned SW host、生成和保存同一40×30×10样件、完成STL→3MF→AMF前序各一次及最终清理。只替换随后那一次GLB调用绑定。C# helper不调用GetActiveObject、ROT、Activator/CoCreateInstance、OpenDoc或新建文档；任何绑定/身份缺口在0次GLB时停止。

1. Python从其仍存活的app、document和document.Extension引用各创建一个COM封送包，使用 `pythoncom.CoMarshalInterface(stream, IID_IDispatch, existing_oleobj, MSHCTX_LOCAL, MSHLFLAGS_NORMAL)`。它封送的是已有接口，不重新查找host。三个包经本次随机nonce、当前用户权限的私有管道传给唯一helper，每包限制1MiB；原始封送包只临时传输，不放入公共报告或仓库。附控制数据包含角色、预期SW PID及进程创建时间、文档路径/title/type/config和源文件hash。
2. C#在单一STA内将包恢复为IStream并从起始位置CoUnmarshalInterface一次，再用装机interop作QI/强类型转换。不能跨进程传一个数值指针后直接GetObjectForIUnknown；也不能用仅限同进程线程的CoMarshalInterThreadInterfaceInStream替代MSHCTX_LOCAL方案。Python保持原三引用与owned进程句柄，等待helper时按需泵送STA消息。
3. 每个NORMAL包仅允许一次解封并单独ACK；未消费包由发送者CoReleaseMarshalData，已消费包不重复释放封送数据。helper仅释放自己取得的引用，SW文档关闭/ExitApp/owned进程等待仍由原Python driver统一完成。失败保留首错及HRESULT，不用其他连接路径回退。

依据：[pythoncom.CoMarshalInterface](https://timgolden.me.uk/pywin32-docs/pythoncom__CoMarshalInterface_meth.html)、[Microsoft CoMarshalInterface跨进程上下文](https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-comarshalinterface)、[NORMAL一次消费及释放规则](https://learn.microsoft.com/en-us/windows/win32/api/wtypesbase/ne-wtypesbase-mshlflags)。对应候选源码已准备，Windows 实际管道/COM 所有权仍待验证。consume/ACK 丢失保留 consumption_uncertain，不盲目释放或重发；marshal 本身异常单列 unknown。详见候选说明。

## 保存前的host和document身份准入

helper获得的是发送者现有能力引用，但仍须逐项验真并记录实际值；任何未知严格拒绝。

- app.GetProcessID必须等于Python持有进程句柄的预期SW PID，进程创建时间、路径、版本匹配，文档数和runtime与原driver一致。记录supervisor launch PID、实际Python native-call PID、C# helper PID及SW PID，不能混称一个worker。
- 在C#自身同一STA，比较收到document和收到app.ActiveDoc的canonical IID_IUnknown身份，必须一致；同时app.IsSame(document, activeDoc)必须为真实整数swObjectSame。路径/title/type、当前精确配置名、配置集合和read-only/edit-context与Python传入的实际快照相符。
- 同样在C# STA比较收到Extension和收到document.Extension的canonical IUnknown身份。通过后只对收到的Extension作一次强类型SaveAs3；不自行从别的文档或host取得替代对象。
- canonical IUnknown地址仅可在helper自己的同一进程/STA内比较。不能把Python地址和C#地址数值相等当跨进程对象身份。若IUnknown比较或IsSame返回未知/unsupported，不换另一判定来吞错。

依据：[COM对象identity规则](https://learn.microsoft.com/en-us/windows/win32/com/rules-for-implementing-queryinterface)、[GetObjectForIUnknown引用语义](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.marshal.getobjectforiunknown)。上述只读身份准入本身先做0保存验证，不能边调绑定边反复导出。

## 唯一一次GLB与判读

全部契约和身份门禁通过才进入一次GLB，使用原staging完整字符串与原Version=0、Options=1（须装机swconst确认），两个对象输入为C# null，Errors/Warnings依实际装机 PIA 的 [In,Out] Int32& 以 `ref int` 接收并保留未写入哨兵值；早期文档参考的 out-only 写法不作为装机绑定依据。保存前的ClearSelection及状态检查沿用原流程，不写偏好，不改变hidden/visible，不调整扩展名，不使用旧保存接口。Python原有有界manifest观察包围这一次外部typed调用；C#记录调用开始/结束、实际参数类别、bool返回及out整数/异常HRESULT，不伪造生产Python native-call记录。

保留单次保存所有原始字节及同前缀隐藏文件快照、实际模块观察、typelib检查、源文件前后hash、文档/config/foreground状态及owned清理证据。仍以原严格BIN/accessor范围和输出发布要求判断，不修改或补齐GLB数据。

| 结果 | 能支持的结论 |
| --- | --- |
| 强类型调用得到有效BIN且全部门禁通过 | 差异指向Python动态绑定/参数封送路径，仍需有依据的最小产品修正及原生CI，不直接认定某一个VARIANT参数就是首因 |
| 同样true/0/0且BIN0 | Python特有封送不再是唯一解释；继续调查共享现代API/导出器环境，不能仅据此宣称导出器缺陷 |
| 契约/身份失败、COM异常、false或其他内容失败 | 保留首次原件并停止；不执行第二调用、参数扫描或新host回退 |

本次有19项 Python便携测试及34条 C#纯协议断言通过，没有实际 Windows/COM/GLB运行结果，不替代现有CI或公开验收。默认 identity 模式有原样件及前三格式 CAD 操作，但 GLB 保存为0；它不是零 CAD，且刻意保留原 fixture 的失败语义，仅独立预检回执可通过。生产仍使用原现代SaveAs3调用；后续操作由统筹安排。
