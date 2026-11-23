# Native API观察入口迁移（尚待2025原生验证）

基线 `2d83afdc6c5c56b1a72157a84d54ee15cde770ab`，独立分支
`codex/native-api-observation-modern`。不新增功能或旧版本兼容，不切换配置、不回退弃用接口。

## 配置观察

[官方2025弃用声明](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~GetActiveConfiguration.html)
指向[ConfigurationManager.ActiveConfiguration只读属性](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IConfigurationManager~ActiveConfiguration.html)。
共享helper只取当前对象Name，保留原字符串；对象缺失、空/全空白/非字符串拒绝。
仅工程图结构观察显式允许无配置。metadata状态及STL前/后/finally仍沿原调用点
比较配置、stamp、identity、readonly及foreground，不增加配置激活或异常后的其他COM绑定重试。
现有dimensions已经使用现代入口，尺寸迁移将继续复用其严格配置检查。

活跃fixture与line-font trace observation白名单随本版迁移为ConfigurationManager、
ActiveConfiguration、Name；getter/setter和几何计数不放宽。历史原件及原有audit输出不改写，
历史trace审阅须使用其来源提交对应的审计器，不能用本版白名单改造旧报告或翻绿。

## 验证边界

便携Mock不是2025COM校准。关联+完整portable、SDK、安装资源检查完成后记录精确提交和日志。
待统筹与SaveAs3线程协调最终精确组合head的一次full/gate，避免重复安装。
已有full `42369257219` 不变更、不重复dispatch。发布仍需用户最终确认。

## 尺寸观察：GetSystemValue3

[官方2025 GetSystemValue2弃用说明](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetSystemValue2.html)
要求改用GetSystemValue3。2025 GetSystemValue3/enum动态页面在本次浏览只返回shell或抓取失败，
没有据此虚构已读正文；具体契约核对[官方GetSystemValue3正文（2023）](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetSystemValue3.html)，
枚举ID核对[官方swInConfigurationOpts_e正文（2022）](https://help.solidworks.com/2022/English/api/swconst/SOLIDWORKS.Interop.swconst~SolidWorks.Interop.swconst.swInConfigurationOpts_e.html)。
SOLIDWORKS2025实际typelib与pywin32绑定形状仍列原生必验，不宣称这些便携测试完成了它。

调用用已严格读取的当前Name，`swSpecifyConfiguration=3`，Config_names采用官方OLE允许的单BSTR。
该指定模式保留原GetSystemValue2按配置名查询语义；不使用忽略Config_names的swThisConfiguration，
不切换配置、不查询全部配置。只接受tuple/list中恰好一个int/float，严格拒绝bool、空/多值、
嵌套、标量、字符串、非finite、溢出及非正长度；在边界转换meters→millimeters。
原FullName、driven/readonly、配置一致性、几何/CAS/identity/前台及失败首因保护继续存在。
原生读用单次`IDimension.GetSystemValue3` trace边界，异常不调用Get2或其他绑定重试。
既有故障fixture只改Get3的双参数/单值返回形状，不改原几何断言。

## 一次最终组合原生验证方案（由统筹决定，不在本路重复dispatch）

1. 将本分支两个逻辑提交与SaveAs3修复组合到精确候选head，先关联+完整portable/SDK，
   再用已有full/gate单次运行。保留现有42369257219原始source/run，不取消、不追认到新head。
2. 在同一owned隐藏SW2025实例记录installed swconst.tlb hash并按名称核
   swInConfigurationOpts_e.swSpecifyConfiguration确为3，及GetSystemValue3的官方签名；不猜返回形状。
3. 至少两配置、不同尺寸值样件：当A为当前时仅读A；B当前时仅读B；显式记录输入Name、
   returned object/SAFEARRAY形状、唯一数值与mm换算、native FullName/driven/readonly，
   证明未激活另一配置且前后配置身份/stamp/foreground未变。
4. 复跑既有圆/矩形发现、长度读取、驱动编辑与保存只读重开、文档属性与STL源保护门禁，
   不放宽原有几何/状态断言（已有用户批准单位/公差例外只保持其原限定范围）。
5. 原report/trace/worker stdout/stderr/保存副本hash、实际宿主/清理与首次失败均持久留存。
   600秒native、1800秒组、首失败停止，不API重试/回滚/组内重启；正常CI只记链接/head后结束等待。

现阶段本分支没有2025原生通过证据、没有发布授权；正式发布仍须用户最终确认。


## 本机最终便携结果

Python3.15：完整2144项、28项环境跳过；尺寸关联202项，配置helper4项、文档197项、
line-font/trace42项、STL24项均通过。SDK生成一致、严格实现6文件及11个消费者拒绝例通过；
安装CLI/schema/skill检查通过，无COM激活。日志及hash见portable JSON回执。
初始SDK环境误装mypy2.4.1，不支持Python3.9 target，保留原日志；改用1.18.2后同一严格检查通过。
本分支没有workflow/版本/SDK公共schema变化，没有触发新CI，不构成新COM读回验收。
