# 安装类型库约束的显式调用＋空参数候选（本地准备）

本候选同时改变**调用绑定**和**ImportData 值**，以 `--installed-tlb-null-binding-candidate` 单独命名。不是保留旧绑定的单变量实验，也不是已证实的导入修复。只完成源码、静态检查、便携测试与本地提交；未执行 VM、CAD、CI、推送或基线重放。后续是否值得单次执行，交统筹亲审具体提交后决定。

## 保留原失败与未知项

[8c6cdc9 原件审计](step-null-8c6cdc9-audit.md)仍成立：原 client.CDispatch 包装与继承策略已通过，但 LoadFile4 没有可用方法表项或 lazy 元数据，故零导入保护停止。没有真实 null 转换或导入结果。原报告、完整 428 文件归档与原始输入保留，不覆盖。

已核 b312 源码会在获取 TypeInfo、TypeComp 或构建 Python 方法表示时吞掉部分错误。旧报告未记录这些构造阶段的原生结果，不能从空 Python 缓存推出 GetTypeInfoCount=0、唯一注册故障或某个确定 HRESULT。正常未知成员 getattr 还可能作零参数 PROPERTYGET Invoke 探测；禁止用该路径探测 LoadFile4 后再声称原绑定不变。

旧候选的保护未放宽。新增 Python-only state 快照区分 key 缺失/None，记录已知方法/属性表、目标项和方法缓存；不调用 COM repr/str，也不访问未知业务属性。另有有界只读 `collect_native_metadata` 函数，最多各一次 GetIDsOfNames、GetTypeInfoCount，以及 count=1 时的 GetTypeInfo(0,0)、GetTypeAttr、GetTypeComp，首错停止、零 Invoke；**此函数未接入入口或自动宿主重放**。不为收集这些信息重复启动旧候选。

## 显式新绑定的依据与边界

宿主启动前，用既有纯文件 MSFT 解码器读取同一安装 `sldworks.tlb`，必须匹配 SHA256 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`。核对 ISldWorks IID、LoadFile4 DISPID227、零可选参数、两个输入 BSTR、输入 IDispatch、in/out LONG 指针、out/retval IModelDoc2 双指针和 native HRESULT。不加载类型库来猜调用签名，不扫描 IID，不尝试多组参数。

原 owned 获取链和 app 对象保持。准入只允许精确 dynamic.CDispatch 或精确 client.CDispatch；已有 b312 三文件 hash、四个核心运行时处理函数和 client 继承/工厂/返回策略证明继续有效。新增三个 dynamic 返回辅助函数与完整已核源码的运行时代码比较。原 `_oleobj_` 必须是 pythoncom 注册的精确 PyIDispatch 类型；不 QueryInterface 或重包装宿主来生成另一指针。

实际调用前，仅对这个原指针作一次 `GetIDsOfNames(0,'LoadFile4')`，结果必须是精确 int227。该 C API 不含业务 Invoke；未知、bool、错误 ID 或异常立即停止。前后 Python 方法/属性/缓存快照须一致；不读取 LoadFile4 getattr，不填方法表，不用 FlagAsMethod、EnsureDispatch、重包装或 InvokeTypes。

通过后采用已明确选择的新调用：

```python
existing_ole.Invoke(227, 0, 1, 1, fixed_path, 'r', VARIANT(9, None), errors)
# errors 为原来的 VARIANT(VT_BYREF | VT_I4, 0)，即 16387。
```

此处是通用 IDispatch Invoke，不把 HRESULT 原生 ABI 误当 Python 返回声明；out/retval 由 IDispatch 返回值处理，Errors 显式 BYREF。返回值交原对象已核 `_get_good_object_`，保留 client 原返回包装策略。原生返回转成 Python 后、进入该包装前先保存 returned/type；包装失败时仍保留原返回引用和首错，没有再次 Invoke 或另一种绑定。

依据是已核 b312 [PyIDispatch.cpp](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyIDispatch.cpp)（SHA256 `8cb132de33fdbfeaaf42085687ce74d4a973f813d98f6f88e7284be9cb229fff`）及已核 [oleargs.cpp](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/oleargs.cpp)、[PyComHelpers.cpp](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyComHelpers.cpp)。前者的通用参数转换会识别显式 VARIANT，并回填 BYREF 载体；DISPATCH9/None 的空接口语义来自既有转换证明。这里没有测量 native VARIANT 内存或地址，也没有以源码 hash 冒充已加载 C++ 二进制的身份校验。

`explicit_invoke_attempted=true` 只说明 Python 进入该一次 Invoke；若封送或返回转换失败，不能据此断言已执行了一次原生 CAD 方法。直接调用点无重试；拒绝后终止，不能换载体、换签名或走原绑定补试。报告明确 `original_bound_method_used=false`、`single_null_causal_claim=false`，两项 changed_variables 同时列出。相对旧 60f1cf8 的真实绑定分支仍未知，未补造跨运行的绑定一致性。

## 同一输入、设置与保护

- 固定原始 AP203 线框路径、10595 字节与 SHA256 `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`；沿用只读/文件身份/属性/时间/无链接与重解析点检查，输入前后相同。
- 完整保留 60f1cf8 的八值，按 TOGGLES+INTEGERS 顺序为 `(False,True,True,True,True,False,1,1)`。记录 changed_from_60f1cf8=[]；每次 setter 前完整 CAS、写后读回、仅恢复 owned attempted 字段，反序且保护外部第三值。原始八值最终核验，恢复失败与业务首错分开。
- 一次 GetImportFileData、一次既定 STEP IID 的安全 QI、一次只读 MapConfigurationData 作为观察；实际 ImportData 不使用该工厂对象。计数是外层脚本操作次数，不虚构普通动态属性解析在底层实际发生的 Invoke 次数。
- 至多一次 LoadFile4，固定小写 r；不重试、回退、重建、导出、保存、新建、选择或额外打开。原严格 reference-curve 表示、12 段、320 mm、十/三十/四十毫米各四段与既有阈值不变。草图即使 12/320 也失败；未知几何保留 unavailable/null，已有 raw partial 不丢失。
- 原 hidden owned host、单文档、一次 owned CloseDoc/Exit/wait/handle-close/CoUninitialize 与首错保护不变。仍监督三条 trace，单调用 600 秒/整组 1800 秒；不全局终止 CAD，不占用 VM。原 zero-import 入口、公开 reader、owned harness、生产适配器、CI 配置不变。

使用独立证据父目录 `C:\Workspace\SWCLI-series-20261111\step-wire-installed-binding-evidence`，子目录必须全新。三个历史候选和新候选互斥，父监督只向子进程传递所选模式。本轮没有在该目录创建原生运行。

## 审阅结果与下一步

便携测试共 **139 项通过**：原绑定 18 项、入口 34 项、新绑定/观察 17 项，以及其余 STEP 检查 70 项。新测试覆盖错误/未知 DISPID 零 Invoke、原 map/lazy 缺失仍保持原样、实际单一 NULL 载体、BYREF Errors、实例/指针/返回处理函数漂移、终止后不可重试、首错与恢复/关闭错误分离，以及严格拒绝草图和错误长度。只读观察覆盖 count0 不查询 index0、count1 的有界读取、未知类型/数量、首错停止与无未知对象字符串探测。

完整已核 b312 模块编译的类/函数静态自检通过；同一固定安装 TLB 的纯文件解码与坏 hash 拒绝通过。139 项日志 `step-evidence/step-installed-all-step.log`，静态证明 `step-installed-b312-static-source-selfcheck.json`、`step-installed-tlb-static-contract.json` 保留在 ignored 证据目录。没有用便携或静态结果替代原生证据，也未重复全量便携套件或无信息宿主诊断。

统筹亲审须接受“两变量且不作单一 null 因果结论”的边界，再决定是否在空闲 VM 上按新提交完整源码、新证据目录执行一次。若不能接受这项信息增益，保持未执行；不自动转公开验收。即使未来单次导入成功，也只证明这个固定输入与明确调用方式，不自动完成八文件公开 save/reopen 验收。官方 2025 文档的条件冲突仍未解决。
