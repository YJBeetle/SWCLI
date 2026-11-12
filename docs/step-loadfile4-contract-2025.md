# LoadFile4 的2025合同复核：类型已确认，条件语义仍有冲突

结论：已确认安装版2025参数表确实要求3DI关闭时ImportData为空，也确认同包STEP示例与条件表难以兼容；同页备注解释了关闭后的r分支，却没有裁定示例变量是否为空。静态TLB/Interop解决了**实际参数类型**，不能消除该行为文档矛盾。不能宣布旧调用已被证明错误，也不能据此继续扫枚举、把草图作为参考曲线通过。

60f1cf8唯一执行的[独立原件审计](step-wire-60f1cf8-audit.md)已完成：NeutralCurve实际为1，仍得到两个3D草图、raw12段/320mm；geometry保持unavailable/null，五项原值恢复、退出正常。本轮没有执行新的原生候选。

## 原始版本与证据层次

重新只读提取本机MacSW安装树 `Program Files/SOLIDWORKS/api` 的指定CHM成员，fresh hash与先前保留页逐一相同。安装库为33.5.0.53，TLB SHA256 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159` 与两次VM报告完全相同。CHM是本机2025安装副本，未声称VM CHM字节相同，也未启动Wine、COM、SOLIDWORKS或VM。

[研究机器记录](evidence/step-loadfile4-contract-research.json)包含每份CHM/指定成员的完整hash、公开绑定/格式解析源码URL和hash；[静态ABI记录](evidence/step-loadfile4-installed-metadata.json)保留实际TLB方法记录偏移/原始字节、类型描述和.NET参数marshal。关键帮助页：

| 安装版证据 | SHA256 |
| --- | --- |
| sldworksapi.chm | `3a46af7f0c11e958661beecc22158fedc360939193f5d967182724c9ddbec24e` |
| ISldWorks.LoadFile4页 | `6df55c42766892a65889160d6dcb166633d7a69795195dcfa3d56b1900c686c2` |
| STEP C#示例 | `7775a463f09b092e12aab9dd29c6dd13c5116582039288347133a56900044f10` |
| STEP VBA示例 | `193e996228527ea1dae0dd705f3ba44a4e66bd84cf9cdfe9e69617779b7d0d4a` |
| sldworksapivb6.chm | `9b7e43520947c90897a24e3b3478a937438b116ee213032824101a7993d3b321` |
| VBA LoadFile4签名页 | `7e11ab93bd661a707e16542dae152e3437a90dd2ea2c145d4ec93085078b73af` |

本轮也访问了[官方2025方法页](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~LoadFile4.html)、[STEP C#示例页](https://help.solidworks.com/2025/English/api/sldworksapi/Import_STEP_File_Example_CSharp.htm)、[VBA示例页](https://help.solidworks.com/2025/English/api/sldworksapi/Import_STEP_File_Example_VB.htm)。网页工具只返回导航空壳，不能当作本轮重新读到正文；以下行为结论来自有hash的安装版页面，不拿搜索到的2012资料冒充2025合同。

## 条件表、备注与示例到底说了什么

1. **参数表的字面条件已确认。** ImportData列包含IGES、DXF/DWG、STEP三种对象，并在3DI关闭条件下要求null/Nothing；ArgString列在3DI开启条件下要求空字符串。这不是此前误读或凭记忆推测，fresh安装版正文再次核对相同。方法总说明强调3DI，但后面的备注明确另列关闭后的行为，所以不能截取总说明就宣称关闭后方法不可用。
2. **同页备注给出r分支，不能据变量名证明非空。** 关闭3DI的分支中，非DXF/DWG、非Pro/E类别使用小写`r`导入到一个新SOLIDWORKS文档。IGES片段第三实参写为importData并链接IImportIgesData说明，但没有给出变量初始化/当时值；它可能为空，不能作为非空对象反例。明确的条件冲突应以随后完整STEP示例为依据，不能凭变量名夸大。
3. **`r`的含义有据可查。** 它位于上述关闭分支。STEP属于该非DXF/DWG、非Pro/E文件类别，这是按页面分类和扩展名作出的判断。`r`不是只读保证、不是参考曲线表示选择器，也不是开启3DI参数。Pro/E的`R`是另外一个特定选项，不能混同。开启3DI时的空字符串规则，不能直接搬到本次3DI=false来“修复”调用；备注还提示空串可能出现翻译对话框，隐藏host不能猜改为空串。
4. **同包STEP C#/VBA示例不是线框对照。** 两者都是先打开已有实心part、保存成STEP、关闭原part，随后取得STEP factory对象、显式设置MapConfigurationData=true，以`r`和该对象导入，最后ImportDiagnosis修复坏面。没有设置或核验3DI，也没有线框/参考曲线偏好、严格12/320检查或无修改承诺。示例路径仍含SOLIDWORKS2019样本名，不等于它已在2025的3DI=false下验证；不能复制它的保存/诊断/Map setter到本次最小只读诊断。
5. **仅补猜示例默认3DI状态仍无法消除冲突。** 若按表字面取true，示例的`r`不符合空串条件；取false，非空factory不符合null条件。没有证据可以任选一条规则忽略另一条。应将其标为官方文字不一致，不能自行宣布哪段是勘误。
6. **VBA和factory页没有补齐合同。** sldworksapivb6的LoadFile4页只有`String/String/Object/ByRef Long -> ModelDoc2`签名，没有解释上述条件。GetImportFileData页仍主要描述IGES/DXF，但STEP同包示例和实际QI证明本环境会返回STEP对象；该页还说明factory获取并不立即从输入文件计算所有默认信息。因此factory/QI成功不证明后续导入消费了哪些对象/曲线设置。

MapConfigurationData只控制配置映射，其示例显式true与本次只读观察false也是上下文差异，不扩张成曲线优先级或追加下一轮Map设置候选。

## 实际TLB和Interop参数类型

本轮以纯文件解析读取TLB的MSFT类型/方法/参数记录，另用dnfile0.18.0读取.NET元数据；没有调用Windows LoadTypeLib/GetFuncDesc。MSFT记录格式的解释依据[Wine类型结构](https://github.com/wine-mirror/wine/blob/master/dlls/oleaut32/typelib.h)及[静态dump解析器](https://github.com/wine-mirror/wine/blob/master/tools/winedump/tlb.c)，不是用Wine运行SOLIDWORKS的证据。两种独立元数据结果吻合：

| 参数/返回 | 实际TLB声明 | 本地Interop投影 |
| --- | --- | --- |
| FileName | 输入VT_BSTR | string，marshal `13`（BSTR） |
| ArgString | 输入VT_BSTR | string，marshal `13` |
| ImportData | 输入VT_DISPATCH，即IDispatch* | object，显式marshal `1a`（IDispatch） |
| Errors | 输入输出VT_PTR→VT_I4 | byref int32，In/Out均true |
| Retval | 输出/retval，VT_PTR→VT_PTR→IModelDoc2 | 返回ModelDoc2 |
| 原生返回 | VT_HRESULT | 由COM互操作处理 |

ISldWorks IID `83A33D22-27C5-11CE-BFD4-00400513BB57`，LoadFile4 DISPID227，TLB方法记录偏移941396，非可选参数，原生参数数5包含retval；.NET调用显示4个实参并把retval投影为返回值。GetImportFileData DISPID217，返回IDispatch**。`Errors`的原生输入输出方向与现有BYREF I4零初始化相容，不因文档C#写out就改原参数形态。

Interop版本33.5.0.53、DLL SHA256 `a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1`。该DLL是本地安装副本；VM报告未记录Interop DLL hash，所以只对TLB声明字节相同作确认，不能声称VM Interop DLL已经逐字节复验。marshal编号解释可对照[.NET运行时原生类型枚举](https://github.com/dotnet/runtime/blob/main/src/coreclr/inc/corhdr.h)。

类型结论特别重要：第三参数不是任意VARIANT。ABI中指针可以表示空值，不代表3DI=false时必须或不得传空的运行时语义已获解决；TLB没有编码这个条件规则。

## Python空值也必须区分

核对实际使用版本的[pywin32 b312参数转换](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/oleargs.cpp)和[接口转换](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PyComHelpers.cpp)：通用Invoke路径的Python None生成VT_NULL；已知VT_DISPATCH的类型化路径则可把None转换成空IDispatch指针。`pythoncom.Nothing`的通用转换与显式`VARIANT(VT_DISPATCH,None)`也有空dispatch语义，但不能假设它们可直接替代已知类型方法的实参：后者的转换器不一定解包这个VARIANT外壳。

本轮原件未记录LoadFile4的具体Python调用绑定分支，不能把“CDispatch类型”当成该分支的完整证明。不能在未来提案中仅写“换None”就声称已经满足ABI，也不使用Empty/Missing或省略一个非可选实参来冒充null。需要固定并核验实际绑定路径和传出的VARTYPE/空指针，不增加CAD调用来试探多种Python拼写。

## 只交审阅的最小提案，尚未实现

现有证据足够提出一个窄问题：在60f1cf8**完全相同八项向量**、同输入原字节、同小写`r`及同一次导入保护下，只把LoadFile4第三实参的语义从非空factory对象改为明确的NULL IDispatch，能否改变该原件表示？这仅依据有冲突的参数表和已核ABI构成候选，不是已证明修复。更优先的只读路径是请厂商澄清：2025关闭3DI时这项条件是否有勘误、STEP对象何时应传、格式专属曲线选项在哪条导入路径适用。本轮没有向外部发送消息。

若root认为该候选值得进一步准备，应先另行审阅绑定层的明确空值表达和最小保护差异。只改变第三实参；原GetImportFileData/QI/getter可保持一次只读取证但不能把factory当作实际已传参数；日志必须分别标明factory观察对象与LoadFile4实际null。现有控制器要求同factory非空，**本轮保持不动**，不能绕过它运行未审阅调用。

不得同时改`r`为空、开启3DI、改Map/导入偏好或重放baseline。最多一次LoadFile4，保留既有完整CAS/仅owned恢复、600/1800、首错和owned退出；无Save/New/Open/Select/Export/fallback。仍严格要求参考曲线表示、12段320mm/原向量；草图即使数值正确仍失败，unknown/错误保留unavailable及原始partial。若这些前提无法落实或信息增益不足，就停在厂商合同澄清，不安排新的原生尝试。

本文件只提出语义层面的单实参候选，没有新增可执行native模式或运行命令、没有执行/预约VM/CI、没有推送、没有宣称该矛盾已经解决。

## 离线复核方式

静态ABI检查仅依赖已有dnfile，不加载程序集；只写另一个证据文件：

```sh
.venv/bin/python scripts/ci/inspect-step-loadfile4-metadata.py \
  --tlb '/Users/YJBeetle/Library/Application Support/MacSW/bottle/drive_c/Program Files/SOLIDWORKS/sldworks.tlb' \
  --interop '/Users/YJBeetle/Library/Application Support/MacSW/bottle/drive_c/Program Files/SOLIDWORKS/SolidWorks.Interop.sldworks.dll' \
  --output step-evidence/loadfile4-metadata-repeat.json
```

安装文件前后hash必须相同，错误hash或输出覆盖输入均拒绝。fresh CHM成员可用已有7z只读输出核对，完整本地保留目录为 `step-evidence/loadfile4-contract-2025`。未把私有DLL/TLB/CHM或整页帮助正文提交到仓库。
