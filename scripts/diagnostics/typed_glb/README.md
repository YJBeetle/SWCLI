# 单次 typed GLB 调用候选

2026-11-12：b50b603实际PIA零CAD编译通过，随后一次零GLB身份预检在源SLDPRT共享读取首错停止。新[只读共享取证候选5c754ba](../../../docs/verification/glb-typed-identity-first-failure-2026-11-12.md)已准备，Python23项/C#70条断言通过，尚未实际PIA编译或原生运行。SaveAs3仍0次，完整身份准入没有通过；由统筹亲审，不自动重跑。编译首错/通过及严格路径分析见[独立原件审计](../../../docs/verification/glb-typed-namespace-and-path-audit-2026-11-12.md)。用户真实Blender成功原件已对应到[MarkingJig](../../../docs/verification/glb-user-markingjig-comparison-2026-11-12.md)，只保存hash/统计，不复制业务二进制，不否定其历史成功。

## 唯一调用层变量

`run-typed-glb-control.py` 校验并导入统筹原始 `local-glb-host-control.py`，其 SHA256 必须为 `282d75cb4a4097dac4077bb7e70af68d8278c351880d0887ce8220ba46cd36d2`。原 source ZIP SHA 必须为 `06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53`，每个解压源文件须与 ZIP 相同；代码固定为 `70d8c9ecf3c02b099ca9c2cc64fe1880061cea44`。

原 driver 仍拥有唯一 hidden host、40×30×10 新零件、源文件保存、STL→3MF→AMF→GLB 顺序和最终关闭/退出/owned 进程等待。包装器只在当前 Python 进程替换 `windows_documents.save_as3` 的 GLB 入口；前序三格式委托原函数，`windows_native_files.save_as3` 别名不变。完整 GLB staging 字符串不改名，Version=0、Options=1、两个对象参数 null，错误码初始 Int32.MinValue。原偏好、ClearSelection、manifest、失败字节保留和严格 BIN/accessor 校验照常执行。发现其他命名/画质/STL实验环境变量，在创建 host 前停止。

原 baseline 的 `BASE/SOURCE` 保持原值；仅把已加载模块的 `__file__` 指向包装器，使原监督器创建的隔离 worker 重入包装器。配置用进程环境传给 worker，监督器仍有原 600 秒 native / 1800 秒 group 边界。记录原 driver、包装器、桥接器和编译源码 hash。这不是把已经退出的历史 baseline host 重新打开：“同 host”只指**新的一次实验中 Python producer 与 C# consumer 共享同一个 owned host/document**。

唯一实验变量是现代 SaveAs3 调用路径（客户端进程/STA、强类型 PIA 和 CLR 封送也属于此路径）。不能由结果单独认定某一个 VARIANT 参数是首因。

## 文件与准入

- `build-typed-glb-bridge.ps1`：只用现存 Framework64 v4 compiler 与已审计装机 PIA，输出新目录；`/platform:x64 /langversion:5`，验证 AMD64 PE32+。拷贝原 PIA 到新输出目录并核前后 hash，不创建/连接 COM，不运行 helper，不安装软件。
- `TypedGlbBridge.cs` + `BridgeCore.cs`：单一 STA 的一次性私有管道服务；加载实际 PIA 后复核 hash、程序集、GUID、DISPID 315、七参 flags/MarshalAs/返回类型。装机 Errors/Warnings 同时 `[In,Out]`，代码用 **`ref int`**。便携替身编译无法替代这一步的实际 PIA 编译。
- `bridge_control.py`：现存 app/document/Extension 各一个 `CoMarshalInterface(... IID_IDispatch, MSHCTX_LOCAL, MSHLFLAGS_NORMAL)` 包。主 STA 负责 COM 和泵消息，I/O 线程仅传输字节。父引用保持到 helper 结束。未通过契约/身份或传输状态未知，都没有重试/其他接口/新 host 回退。
- `portable/`：只供本机语法、协议及纯门禁测试，含明确标记的 PIA **测试替身**。Windows builder 从不引用它。不能将便携生成物移到 VM 执行。

装机 PIA SHA `a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1`；完整程序集 `SolidWorks.Interop.sldworks, Version=33.5.0.53, Culture=neutral, PublicKeyToken=7c4797c3e4eeac03`。若 CLR 实际从 GAC 加载了不同字节，helper 在读取 COM 包之前拒绝，不能以旁边拷贝正确替代实际 loaded 检查。

## 管道与 NORMAL 所有权

管道名/nonce 每次随机，受当前用户 SID 的受保护 DACL、FIRST_PIPE_INSTANCE 和 REJECT_REMOTE_CLIENTS 限制。helper 核实际 client PID 等于 Python worker，Python 核实际 server PID 等于唯一启动 helper。控制帧最大 1,500,000B，解码后每个包最大 1MiB；三角色有序且各消费一次。包和 nonce 只在内存，不写日志/报告。

每包 `parcel → prepared → consume → consumed`：发送 consume 前即标记 `consumption_uncertain`。只有明确未允许消费的完整包，在原 Python STA 调用 CoReleaseMarshalData；明确 consumed 包不重复释放。consume/ACK 中途断连无法判定是否已消费，保留 unknown，不盲目释放或重发。marshal 本身异常也单列 unknown。若 I/O 线程无法确认退出，全部释放暂缓。`marshal_cleanup_known=false` 会拒绝成功；不能把强制退出当作 COM 包清理完成。

helper 仅释放自己取得的 RCW/stream 引用，不做 FinalRelease 循环、不关闭文档、不退出应用。父进程消失或 helper 会话到 600 秒时，独立 watchdog 终止 helper；实际 native 结果可能未知。Python 先给 helper 短暂清理机会，之后有界终止并记录，owned SW 清理仍由原 driver 完成。管道/超时/清理未确认一律不算验收。

## 身份与一次调用

从三个包取得实际装机 PIA 接口，helper 内 canonical IUnknown 比较 document↔app.ActiveDoc 及 Extension↔document.Extension，另核 app.IsSame==整数1；只记录结果布尔值，不跨进程比较地址。仅源文件采用FileAccess.Read/FileShare.ReadWrite（无Delete），以持有文件句柄的128位ID、size/time和原路径复核保证读取稳定，exe/PIA策略保持。Observe逐项留存已读取raw字段，部分观察不赋值完整before/after，identity失败不放行。记录实际 SW PID/精确进程 FILETIME、exe 路径/hash、runtime、文档数、四个实际 host 布尔值、路径/title/type/stamp/dirty/config/配置集合/read-only/view-only/active sketch、源文件 hash。须与 Python 快照及 harness owned PID 一致。

`--mode identity` 为默认：完成身份握手后 finish，GLB SaveAs3=0；原 fixture 会刻意报失败停止，原 `report.json`/`local-supervisor.json` 保持其失败语义，独立 `typed-control-audit.json` 只表示身份预检是否通过，绝非导出验收。

`--mode invoke`：在同一次会话握手后明确 invoke，再复读身份快照一致才调用一次 typed SaveAs3。bool=false、native error、异常、输出未写均不做后续 CAD 状态读。仅正常 true/Errors=0 后复核状态；这是**交回 Python 严格内容校验前**的读，不能宣称已知 BIN0 后仍无任何此前读取。未知内容仍会由原产品严格校验拒绝。异常记录 HRESULT 和 managed locals，异常时不把局部值冒充已接受的原生输出。

helper 的独立 trace 标记真实 helper PID。Python trace 只写 `CSharpBridge.SaveAs3`/`IdentityOnly`，不伪造 Python 直接调用 IModelDocExtension。离线审计核原件 hash、前三格式各一 Python modern 调用、GLB 零 Python modern 调用、helper零/一次实际调用、三个本地 IUnknown/IsSame 检查阶段、无偏好或CIP setter、无旧保存 API、owned 清理和原严格 mesh 结果。原始失败字节/manifest 保持原工具行为，不修补 BIN。

## 后续由统筹逐级安排，本文不授权执行

1. b50b603实际PIA零CAD编译已通过并保留原件；5c754ba取证/首错处理源码有变化，先交统筹亲审，不能沿用b50 helper冒充新candidate。实际PIA编译及下一阶段均由统筹安排，无替代声明/动态回退。
2. b50一次identity已在源读取首错停止；新candidate的编译receipt/source hash/架构及取证代码由统筹审阅后，才能决定下一次identity。它仍创建原 driver 的新样件并做前序 STL/3MF/AMF，**零 GLB 保存不是零 CAD**。未知项止步，保留原件。
3. 身份与清理原件通过后，另一个新 attempt 才可安排 `--mode invoke` 一次。两个 attempt 是不同新 host，不宣称复用了已经退出的前一 host。

参数要求：`--baseline` 是上述原 driver 的真实 Windows 路径，`--helper` 指新 Windows build 的 EXE，`--output` 是原 baseline 目录旁尚不存在的 sibling；例如选择全新 attempt 名，不能复用已有目录。不自动拷贝、执行 VM、发 CI、重跑或部署。

## 本机证据及限制

.NET SDK6.0.136 / runtime6.0.36，C#语言版本5，整个候选源码连同明确的测试替身编译；70条断言通过（含合成长短路径、只读共享取证状态、部分观察保留，非原生观察）：bool/错误/警告、COMException首错和未知输出、单调用/身份门禁、帧上限/截断/1MiB、精确快照。Python23项测试覆盖一用协议、ACK丢失保守所有权、nonce/role错配、身份失败零invoke、native收据类型和部分输出、原三格式委托/别名恢复/第二GLB拒绝及离线原件与清理审计。919a83e实际Windows/PIA编译首错保留；b50b603实际PIA编译通过；其后身份预检已完成contract、三包consumed和局部IUnknown检查，但完整身份因源读取首错未过，GLB0。当前5c754ba尚未实际PIA编译，Windows共享/PInvoke/新协议仍待验证。本机没有PowerShell；统筹原次syntax_exit=0，不能当helper编译通过。当前不改路径比较/归一化，物理文件ID证据仍缺，身份预检前先审阅上述分析。

本机纯测试（无网络依赖；SDK须已存在）：

```text
python3 -B scripts/diagnostics/typed_glb/test_bridge_control.py
dotnet build scripts/diagnostics/typed_glb/portable/PortableTests.csproj --configfile scripts/diagnostics/typed_glb/portable/NuGet.Config -p:BaseIntermediateOutputPath=/private/tmp/glb-typed-repo-obj/ -p:OutputPath=/private/tmp/glb-typed-repo-bin/
dotnet /private/tmp/glb-typed-repo-bin/PortableTests.dll
```

依据：[CoMarshalInterface](https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-comarshalinterface)、[pywin32五参契约](https://timgolden.me.uk/pywin32-docs/pythoncom__CoMarshalInterface_meth.html)、[CoReleaseMarshalData](https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-coreleasemarshaldata)、[IUnknown identity](https://learn.microsoft.com/en-us/windows/win32/com/rules-for-implementing-queryinterface)、[C# InAttribute 与 out-only 限制](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.inattribute)。装机元数据原件见既有 interop 审计，不以文档参考替代。
