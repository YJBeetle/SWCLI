# Typed GLB 装机编译首错、修正通过与路径身份分析

2026-11-12：统筹对精确919a83e首次装机PIA零CAD编译exit=1；最小修正b50b603另一次实际装机PIA编译已通过，独立核对如下。两次编译作业均helper执行/CAD调用为0；后续identity尝试另见[源读取首错审计](glb-typed-identity-first-failure-2026-11-12.md)。首错原件保留；通过结论仅到编译/静态PE，不提升为运行时绑定、管道/COM或GLB。本路仍只离线修正/测试/分析及原件审计，不操作VM/CI/push。

## 实际首错与修正范围

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/glb-typed-build-919a83e-01`。

- Framework64 compiler4.8.9221.0，PIA33.5.0.53，PIA原字节SHA与既有装机审计一致。build/launcher源前后hash与919a83e Git blob相同；PowerShell syntax_exit=0，build exit=1，cad_calls=0/helper_executions=0。
- `compile.stdout.log` 是UTF-16LE原件。首CS0104在TypedGlbBridge.cs45：System.Attribute与SW.Attribute歧义；另一CS0104在139：System.Environment与SW.Environment歧义。原错误不被后续测试覆盖。
- 最小修正只有**两处** `System.Attribute.GetCustomAttribute` 与**一处** `System.Environment.Exit`。不改PIA声明、ref参数、SaveAs3、路径/身份准入、管道或超时预算。
- PortablePiaStub新增同名Attribute/Environment占位类，模拟已观测命名空间污染，不仿造真实COM接口。先用旧源码+新替身本地编译，CS0104可复现于45/54/139；全限定名后编译0警告/0错误、36条纯断言通过。Python原19项通过。修正代码已单独提交为 `b50b603bae15af295f9fb8b78799d8f31c441d90`；实际装机编译后续通过见下一节。

原件SHA、解码首错、红/绿测试和新源码摘要见[结构化回执](../evidence/glb-typed-namespace-and-path-audit-2026-11-12.json)。919a83e的[原准备回执](../evidence/glb-typed-control-preparation-2026-11-12.json)保持历史原值，不覆盖成后来的结果。

## b50b603实际PIA零CAD编译通过的独立核对

统筹只执行一次，原件目录 `glb-typed-build-b50b603-01`，与上述首次失败目录并列。原失败不覆盖，无helper执行。

| 原件/检查 | 独立观察 |
| --- | --- |
| build.json | 1366B，SHA `9993fb5b64200a6095084f5a95d49cbb5fe1e5e810af0b7d3bd2f8948e7a38c9`；success=true、compiler_exit=0 |
| TypedGlbBridge.exe | 24576B，SHA `ec22173924cbb8851d877775e67c2e7556e754aba21d9c85f48facc434d3eb64` |
| 实际PE字节 | MZ/PE头成立，Machine0x8664 AMD64，OptionalHeader0x20b PE32+，有72B CLI头、ILONLY且无32BITREQUIRED；只解析原字节，不执行入口 |
| PIA | 2800000B，原SHA `a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1` 一致，记录版本33.5.0.53 |
| 源码 | launcher固定的Core/helper/builder/Python producer/wrapper五份源码SHA逐项等于b50b603 Git blob；两份C#编译前后hash相同 |
| 日志/启动器 | compile stdout/stderr均0B；syntax_exit=0、launcher exit=0；cad_calls=0、helper_executions=0 |

该证据支持：真实装机PIA引用下，三处全限定名消除了此轮实际编译错误，强类型调用可被现存Framework64 compiler编译为AMD64 helper。它**没有执行**CheckContract或SaveAs3；不能证明CLR将从预期位置加载同字节PIA、null/输出参数运行封送正确、管道DACL/PID检查、NORMAL包所有权/COM身份通过，也不能证明GLB有效。该编译原件仅绑定b50b603，不能覆盖后续源码变化。后来零GLB身份预检由统筹单次执行，源只读共享取证首错停止；5c754ba共享读取候选另行交审，尚未实际PIA编译。本路不执行原生操作。

## 路径风险：已确认代码事实，尚无桥接运行失败

Python `process_identity` 用持有的进程句柄读GetProcessTimes与QueryFullProcessImageNameW(flags0)，保留原始exe_path并按该字符串读SHA；C# Observe用Process.MainModule.FileName并读SHA。Core.SameSnapshot对整个DataContract序列化字节严格比较，包含原始exe_path，之后才设置identity_accepted、发送identity或进入SaveAs3。

官方[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)的flags0指定Win32路径格式；[ProcessModule.FileName](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.processmodule.filename?view=netframework-4.8.1)给出模块完整路径。这些合同不能推出两种来源总是具有逐字符相同的短/长名称和大小写。

因此，若两方取得不同别名，当前代码会**在GLB保存0次时严格拒绝**，不会因SHA相同就接受。新增的合成快照反例固定同一SHA、其余字段相同，仅8.3样式字符串与长路径不同，SameSnapshot仍抛错，原字符串未改动。这只是离线反例，不是当前Windows现场已返回某种路径的证据；此分析最初尚未执行helper；后来b50身份预检已保留Python实际8.3路径，但C#完整before仍null、raw路径丢失，依然没有两方实际别名不匹配的证据，不能断言C#必定返回长路径。

当前候选只有路径字符串/哈希及PID/创建时间，**没有物理文件ID的双端证据**。SHA相同只能证明读到的内容相同，不能把复制件认作同一个原生文件；路径相同也不等于整个读取窗口都没有替换。当前GetProcessTimes/进程句柄与文件读取不是同一种句柄，不补写成已持有exe文件身份。这是未采集的额外证据，不能补写为已验证；不构成本轮零GLB身份预检或单次对照的新增完成要求。本轮按统筹明确的既有保护执行：owned进程句柄/PID/精确FILETIME、双端raw快照严格相等、固定exe/PIA hash，以及canonical文档/Extension身份。

## 实际路径不匹配后的可选物理文件证明设计（非本轮前置）

本轮保持原始路径严格比较及现有代码不变，不加lower/resolve/字符串替换，不忽略exe_path，不以SHA单独放行，也不静默调用长路径转换。目前没有两方raw路径实际不匹配的原件；不提前增加采集链。只有以后实际发生不匹配、统筹依据原始数据认为需要额外物理文件证明时，下列设计才供审阅选择，不自动成为任何阶段的完成门槛：

1. 保留producer与helper两种实际路径的原值、来源、长度，以及PID/原始FILETIME。先确认它们指向同一个仍被owned driver持有的进程实例；不能用数字PID单独防复用。
2. 对两种原始路径及已审计安装的SLDWORKS.exe路径，打开只读普通文件句柄，保持至比较完成，明确拒绝未知/截断/非本地/无法解释的重解析路径。不能只对字符串做转换后再丢弃原始观察。
3. 从这些**文件句柄**统一取得volume serial + FileIdInfo完整128位FileId，要求有效且逐项一致，同时在句柄上读实际SHA、大小及必要stat指纹。两方类型/编码约定一致，完整ID不截成64位。官方[FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)明确以volume serial和file ID的组合比较两个打开句柄是否是同一文件。
4. 比较结束前复核原始路径仍解析为持有的文件ID，并复核进程仍为原PID/FILETIME；保存/身份窗口前后保留证据和句柄生命周期。权限、文件ID、路径替换或任一步未知即止步，不能回退成仅hash或仅字符串。
5. 若只是解释短/长名称，[GetLongPathNameW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getlongpathnamew)只能作为**额外展示字段**：有长度上限/成功返回值检查，原值保留；其成功也可能原样返回输入，不能当物理身份检查。是否采用此方案或其他有界修复，须在实际不匹配原件出现后由统筹判断；不提前预定新字段或采集，也不在本轮改变raw比较。

这套方案证明的是该时刻**本机磁盘文件身份**及对应owned进程实例；不冒充读取了整个进程已映射镜像的字节或全部运行时依赖。当前候选尚未实现/原生验证此证据采集，本轮不把它写成已通过准入。严格字符串不符仍0 GLB失败；即使未来字符串相同，也不能将缺失的物理文件证明填为true。额外双端exe文件ID不是本轮identity/invoke的前置要求；既有保护通过后，由统筹按已审范围安排后续，不因这份条件设计扩大门槛。5c754ba已审的源文件稳定读取检查是另一项保护，保持原样。

历史Blender成功线索及有效assembly BIN720/12tris、失败part BIN0的原件对照继续保留于[历史审计](glb-history-offline-2026-11-12.md)；本次编译修正和潜在路径问题都不能作为其历史结果的成因。
