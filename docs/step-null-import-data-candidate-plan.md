# 显式 NULL IDispatch：窄诊断候选，待统筹亲审

本轮仅实现准备入口及便携测试，没有执行VM、CAD、CI或推送。官方2025参数表和STEP示例的[合同冲突](step-loadfile4-contract-2025.md)仍保留，不宣称旧调用错误。60f1cf8原件仍是两个草图、严格表示失败；不能把12段/320mm的草图当参考曲线通过。

## 固定范围与唯一语义变量

新显式模式：`--null-import-data-candidate`，与历史 `--neutral-3d-candidate` 互斥。它保留60f全部八值：3DI=false、GeneralSolid=true、GeneralFree=true、GeneralCurve=1、NeutralSolid=true、NeutralFree=true、NeutralCurve=1、globalStepConfig=false。准备完成后逐键与固定向量核对，`changed_from_60f1cf8=[]`，不只依靠某一个字段推测其他值。仍按原实际八值快照/CAS准备，五项尝试写入从已知本地原值反序恢复；外部第三值不覆盖，失败首错优先。

固定只读原件为 `C:\Workspace\SWCLI-series-20261111\step-qi-input\ap203-wireframe.step`，SHA256 `3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90`。原文件metadata/READONLY、TLB hash、原生Windows/pywin32312/33.5.0、单owned host和空初始目录条件不变。

仍一次GetImportFileData、单STEP IID安全QI、一次只读MapConfigurationData取证。factory结果标为**仅观察，不是实际ImportData参数**。只有实际LoadFile4第三实参的语义改为明确空IDispatch；路径、小写r、同一次绑定方法、errors BYREF I4、其他全部向量不变。不重放60f基线，不改Map，不额外保存/新建/选择/导出/打开、重建或回退。

## 绑定合同：保留原路径，不人工切换 Invoke / InvokeTypes

新 `gate_support/step_null_binding.py` 只检查绑定，不自行调用Invoke或InvokeTypes。取得的是原raw host正常属性查找生成/缓存的同一个bound LoadFile4方法，验证之后直接调用它；不会另建Dispatch/DumbDispatch、EnsureDispatch/makepy、强制InvokeTypes或换host。**如果现有包装不是受支持的原dynamic.CDispatch，候选零LoadFile4拒绝，不为让它运行而换包装。**

依据为已核的安装TLB：DISPID227、BSTR/BSTR/输入DISPATCH/in-out BYREF I4。实际Python调用元数据通过如下检查：

1. 在原harness读常量阶段（启动host之前），验证已安装dynamic.py、build.py、client/__init__.py与官方b312源码的SHA256完全相同，只允许CRLF转LF归一化。运行时CDispatch的`__getattr__`、`_LazyAddAttr_`、`_make_method_`、`_ApplyTypes_`字节码与这些已验证源码在**同一解释器**编译出的函数一致，包含参数/常量/异常表，忽略文件名/行表。源码文件hash或运行时方法未知/不同就零host/零Load停止，不能仅凭版本号继续。
2. host建立后、factory/QI/getter之后，先读取已有Python方法表。LoadFile4尚未出现在表中时，只允许原b312的只读`_LazyAddAttr_`类型元数据步骤。未得到已知方法表项立即停；**不继续未知成员属性查找**，避免其可能通过一次无参数Invoke探测LoadFile4。类型元数据步骤也受原外层600秒监督。
3. 验证MapEntry、DISPID、方法名。类型化表项必须实际声明前四项为BSTR/BSTR/DISPATCH/BYREF I4，输入标志1/1/1/3、INVOKE_FUNC、无可选参数；允许已知retval投影形态并记录原始签名。通用路径仅接受已有、已知DISPID227但desc=None的原方法表项，不把typed表改成generic，也不反向改写。
4. 按原MakeFuncMethod生成源码，**只编译用于比较，不执行另一份方法**。正常getattr得到原bound method后，验证receiver、原缓存函数身份和其实际code与原生成器一致。类型化路径须是原`_ApplyTypes_`，通用路径须是原`_oleobj_.Invoke`，其他代码、代理或实例覆写都拒绝。类型化转换函数须仍是原已核CDispatch函数。调用前再次检查函数/处理函数/载体，改变即拒绝并锁死本候选，不允许换另一拼写再试。

两种已有路径各自只有一种允许的空值表达：

| 实际已有绑定 | 唯一实参 | 转换依据与实际可读证据 |
| --- | --- | --- |
| 已知typed DISPATCH | Python None | 实际签名第三项9/FIN、bound code一致；b312 typed helper按VT_DISPATCH调用接口转换，None且NoneOK产生NULL指针 |
| 已知generic Invoke | 同一个`VARIANT(VT_DISPATCH,None)`载体 | 实际carrier类型、varianttype=9、value is None；b312显式VARIANT解包后按DISPATCH作接口转换 |
| 未知/其他 | 无调用 | 不选猜测值、不用Empty/Missing/Nothing替代、不尝试另一条调用路径 |

公开主来源为[dynamic b312](https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/dynamic.py)、[build b312](https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/build.py)、[客户端VARIANT定义](https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/__init__.py)、[参数转换](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/oleargs.cpp)及[接口转换](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyComHelpers.cpp)。源码SHA和转换来源SHA在package证据中固定，未向仓库复制整份第三方源码。

以上是原normal method的提前只读解析/缓存，未替换其调用路径。但60f旧报告没有记录具体绑定分支，所以本候选不会声称它已独立证明“上次实际用了哪一分支”；它只观察并保留本次宿主原有分支。若root要求证明跨运行路径也绝对相同，现有历史证据不足，应在亲审时拒绝/先澄清，不能暗中切换或重放baseline。

## 证据与错误处理

新增 `null-binding-package.json` 和report.context.binding_package：安装源码路径/hash、四个运行时处理函数指纹及转换来源。case.null_binding记录包装类型、实际签名、生成源码/hash、实际bound code指纹/receiver一致、路由和实际参数：typed时None身份+签名VARTYPE9；generic时载体实际varianttype9/value=None。

`null_dispatch_pointer_by_conversion_proof=true` 的含义是：**实际Python参数/签名，加已核b312转换源码，证明传出空DISPATCH指针**。它不是本轮已观察到原生地址或在原生Invoke边界读取了VARIANT内存；`pointer_evidence_kind`明确这一层次。没有插入原生钩子或改C扩展。若root要求原生内存实测，这份证据不冒充满足该额外要求，须先另审附加变量。

`bound_method_invocation_attempted`只记录原bound方法是否尝试调用，不把转换前异常伪装成已观察到原生调用；原生LoadFile4上界仍为1。未知绑定在该标志false和原LoadFile4调用前拒绝，load_return保持not-attempted。准备/验证只许一次；任何拒绝后同一实例不可重新准备或更换实参恢复运行。

Load返回模型先交owned清理责任，错误码/空模型/异常原样保留。无论null候选成败，严格参考曲线类型、恰好12段/320mm/原长度向量与阈值不变。草图即使12/320仍失败，geometry unavailable/null与raw partial保留。原偏好恢复、CloseDoc/Exit/wait/句柄/CoUninitialize、输入metadata和剩余进程复核不变。主/观察/部分激活trace仍600秒调用/1800秒分组；超时只停自有Pythonworker，owned退出unknown交统筹，不全局杀CAD。

## root亲审后的唯一执行方式（本轮未执行）

root决定静态转换证明/实际绑定证据是否充分，亲审精确提交和相关测试后，再自行协调VM独占、独立源码快照归档/hash/成员清单。新增helper也必须在runtime归档中，report代码指纹已纳入它。不要复用上次快照、不覆盖生产包、不运行隐藏worker绕过监督。

新证据父目录固定 `C:\Workspace\SWCLI-series-20261111\step-wire-null-data-evidence`，输出只能是尚不存在的直接子目录。

```powershell
python -I C:\Workspace\SWCLI-series-20261111\step-wire-null-data-code\scripts\ci\diagnose-step-wire-import-once.py `
  --null-import-data-candidate `
  --output-dir C:\Workspace\SWCLI-series-20261111\step-wire-null-data-evidence\null-data-once-01 `
  --swconst "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swconst.tlb"
```

不得额外同时传历史neutral候选标志；null模式自动保留其完整八值而不导入baseline。源码hash不符、未支持包装、未知签名/转换或任何前置失败都停止，不现场换参数拼写/包装。全部原件与stdout/stderr保存，无重试。无论结果如何，都不能据单份本地原件证明公开八文件验收、保存重开、全局参数优先级或解决厂商文档矛盾。

便携验证：新增12项绑定/转换保护测试，现有入口25项测试（含5项null模式完整流程）通过，相关STEP合计107项通过（5.189秒）。覆盖typed/generic原路由、非空/错误VARTYPE/未知元数据零调用拒绝、源码hash和运行时处理函数差异、缓存/载体改变、拒绝后禁止换值再试、首错/恢复/关闭错误分记、草图12/320仍失败、新证据目录/父子标志及原600/1800保护。另用固定的官方b312完整模块编译类代码完成静态处理函数字节码自检；未导入pythoncom或执行COM。本轮按要求没有重复全量便携套件或任何原生运行；这些是fake/静态证明，不是候选实际导入结果。

## 811bb97 首次实际候选运行之后

统筹已亲审并单次运行811bb97，gate因实际包装为client.CDispatch（而非精确dynamic.CDispatch）在零LoadFile4处停止；原八值恢复、退出正常。详见[原件独立审计与获取链源码核对](step-null-811bb97-audit.md)。前文“未执行”是准备阶段状态；未测到null转换或几何。后续只准备精确支持原client.CDispatch，不重放、不换包装，交统筹亲审。
