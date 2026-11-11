# MarkingJig现代依赖与窄文件指纹规则

仅本地候选修正；e1e33d4未原生执行。本次不连接宿主/VM，不修改业务原件，不改产品、现代SaveAs3或C#part夹具。

2025官方[旧接口页](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetDependencies2.html)标记废弃，替代为[Extension.GetDependencies](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetDependencies.html)。直接抓取正文的pageProps确认version=2025及精确filePath，而非仅看到网页壳。装机PIA文件SHA与既有267a34c原件相同；本地反射确认成员为System.Object返回、五个System.Boolean参数，按顺序为Traverseflag、Searchflag、AddReadOnlyInfo、ListBrokenRefs、AppendImportedPaths；DispId306。新五参强类型合约本机.NET6/C#5零警告/错误编译，未执行合约或COM方法，不能替代Windows实际Automation测试。

| 参数 | 包含broken的主查询 | 固定broken对照 | 理由 |
| --- | --- | --- | --- |
| Traverseflag | true | true | 保留递归、derived及suppressed引用，不能用显示组件代替全量依赖 |
| Searchflag | false | false | 读取as-saved位置，不触发搜索规则；不设置全局搜索目录 |
| AddReadOnlyInfo | false | false | 保持name/path成对；实际加载模型与物理文件仍严格检查readonly |
| ListBrokenRefs | true | false | 主查询不省略broken；第二次仅识别差异，出现差异即0保存 |
| AppendImportedPaths | true | true | 保留导入来源，不将其藏在普通native path之后 |

两次是固定只读census，不是在失败后换参数重试。第一份有效才读第二份；原始字符串、参数、数组长度与类型逐步入回执。比较成对多重集，保留重复条数，任一broken差异或不一致即停止。含`|imported_path`的原始路径保留；当前批准名单只有native模型，没有导入源，故零保存停止，不剥离/忽略后继续。derived若未加载或未在批准物理输入/完整图中，也停止。解析成功后要求顶层递归依赖覆盖所有已加载外部组件，避免接受遗漏组件的偶数数组。虚拟组件沿既有明确归属校验。

2025官方[GetNumDependencies](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetNumDependencies.html)仅约定旧GetDependencies2的字符串数。没有依据证明它与现代五参尤其broken/import集合可比，因此移除调用；没有捏造新计数API。returned_string_count仅是实际返回数组长度，不是独立native完整性证明。None/非数组的零依赖语义在当前原生环境未验证，不能假定0；会保留返回类型并零保存停止。合法空tuple/list只证明空数组，仍须通过外部图覆盖。这里的完整性限于现代API合同和可观察加载图；无法以此证明API未报告的隐藏源或全部材质资源。

stable_file对path/handle的dev、inode、mode、size、mtime_ns、birthtime_ns、file_attributes、nlink全部严格相同。唯一跨渠道例外是已观察CPython3.14.7/Windows的ctime语义差异；不转换、不补填，path前后与held handle前后各自全部字段严格相同。其他Python/平台ctime也必须跨渠道相同。反例逐字段覆盖mode/attrs/birth/nlink等，另验证ctime例外范围、两渠道内部改变仍拒绝。访问时间不在既有fingerprint中。

36项便携测试通过；相关typed桥接23项保持。本地PIA编译/反射与纯测试都不代表OpenDoc7、五参返回结构、完整业务引用或GLB原生验收。实际执行由统筹/资源安排另定，未申请VM，不复用已结束WR-01窗口。
