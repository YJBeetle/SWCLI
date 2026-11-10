# 两配置夹具的独立几何证明方案（2026-11-11）

状态：只读审查及下一次私有验证的候选设计；本轮不改fixture期望、产品Get3或setter，不操作VM/CI。零CADinterop工具另行提交，桥接不实现。

## 最新原件与未定边界

原件 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/getter-fixed-7119626-01/` 的report SHA256已重算为 `8217746e38b75b1a7b52cadc64d682760b91397d99f684feb5ffbf56a2ab695b`，匹配监督器。精确源码7119626，SW3012/runtime33.5.0，实际native-call worker84，监督器launch2604。身份准备所有必要比较均严格int1，两次重建bool True，现代SLDPRT保存true/0/0。

第一个saved-A窗口的实际配置为“默认”，单次 `GetSystemValue3(3, '默认')` 返回一元素tuple `(0.02,)`，descriptor为20mm，期望16；失败为native getter value/metadata mismatch。B的saved观察及只读重开均未到达。SLDPRT SHA256为 `80455d6d94ea72776e44605b20e56c1fcc09879d558250569db7f3cadd744257`。不能把A期望改成20，也不能仅凭这个结果断言seed写错或产品Get3选错。

统筹另有装机major33零CAD类型库原件 `installed-dimension-contract.json`，sldworks.tlb SHA为 `585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159`：SetSystemValue3 memid44为R8/I4/VARIANT→I4；GetSystemValue3 memid46为I4/VARIANT→VARIANT。此签名不证明某种Config_names运行时语义已通过，后续工具消费这份原件，不重复采集。

## 官方契约及源码绑定事实

[2025 SetSystemValue3官方正文](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IDimension~SetSystemValue3.html)明确允许Config_names使用BSTR array或single BSTR，只在SpecificConfigurations时使用。可读的[2020 GetSystemValue3官方正文](https://help.solidworks.com/2020/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetSystemValue3.html)同样允许两种形式。2025 Get3正文未取得，装机33签名已由统筹实际读取；不把其他年份页面冒充2025实测。

当前源码的事实：

- 生产直径创建器先在初始配置中创建完整圆，再用 `SetSystemValue3(.016, swSetValue_InThisConfiguration, VT_EMPTY)` 设置直径；退出编辑后既检查descriptor，也调用独立圆弧几何校验。fixture只保留了创建成功判断，没有将初始完整几何回执写入case，不能补填未保留的原读数。
- fixture的AddConfiguration2使用Options=0，新B自动激活已有本地证据。随后直接沿用创建器返回的IDimension handle，调用 `.SetSystemValue3(.020, 3, second_name)`，Config_names是普通Python str，返回严格int0后做重建。未再次按B重绑dimension，也没有独立记录写后A/B圆弧半径。
- 产品读取先取当前ConfigurationManager.Name，再把该str传入 `GetSystemValue3(3, configuration)`，要求唯一返回数组。新原件证明A窗口获得20，但尚无不依赖Get3的A/B预置证据。

因此单BSTR不是已证明的非法参数；显式SAFEARRAY(BSTR)仅是有依据的单变量封送对照候选。旧dimension handle跨配置的上下文也不能在缺测时当作已证首因。不要一次同时更换handle来源、数组形状、配置名称/模板或期望值而失去判别力。

## 优先的零写入原件对照

若统筹安排下一次小范围私有诊断，先使用原SLDPRT的工作副本、核原hash且只读打开，精确定位“默认”配置和原草图：在读窗外按既有严格配置选择规则选择A；不setter、不重建、不保存、不调用GetSystemValue3。

重新从该document按已保留的实际草图名解析Feature，核Name/类型为目标ProfileFeature，再读GetSpecificFeature2及GetSketchSegments；不要把跨配置缓存的旧arc当原生独立证据。可复用生产 `_diameter_circle_verification` / `_circle_geometry` 这条纯几何读取路径，它不调用_descriptor或GetSystemValue3。要求唯一完整、非构造圆，原生arc.GetRadius、中心坐标有限且z=0；保留实际半径、圆完整性、原配置/文档/foreground/编辑状态及trace。GetRadius在[官方2025成员表](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchArc_members.html?id=2.2.1.359.0)中是独立圆弧读取接口。

| A的实际半径 | 能支持的判断 |
| --- | --- |
| 10mm | A实际几何已为直径20，原Get3结果至少与几何一致；应先定位夹具seed/配置上下文，仍不能据此宣布Get3完整正确 |
| 8mm | A实际几何为直径16，与原Get3的20矛盾；优先查Get3名字选择、绑定或对应dimension的上下文，不能靠改fixture期望规避 |
| 无法读取、其他半径、上下文/对象身份未知 | 保留首错停止；不改用另一个getter、重建或保存来“修好”原件 |

这是对新设计的只读取证，不是重试原失败的Get3调用。任何步骤失败即停止；原件与新报告分目录保存。

## 后续新夹具的最小候选与独立预置证明

只有原件对照指向seed后，由统筹决定是否运行新夹具的一次显式数组seed候选：保持原handle来源、Options、名称、20mm目标、setter枚举3和其余代码，仅将Config_names显式构造成 `VARIANT(VT_ARRAY | VT_BSTR, (second_name,))`，且只调用一次；记录计划VT、实际Python对象类型、唯一名称及原始返回类型/值，仍严格int0，不失败后重试BSTR/current/all形式。这一候选在原生成功前不称修复。

预置证明必须独立于被测Get3：

1. 初始A在添加B前，保存创建回执及独立圆半径8mm/中心/完整性证明。
2. B单次seed及原既有重建之后，按当前document重新定位原草图，圆半径必须10mm；切回A后原重建照旧，重新定位圆半径必须8mm。失败发生在准备阶段，不能进入产品观察窗。
3. 在保存态及只读重开态的每个A/B选择之后、产品读窗之前，再做独立圆几何证明，A=8/B=10，并核文档/config/foreground和源文件hash稳定。只读阶段不得为得到预期几何而重建或保存。几何读取均使用独立准备request标签，不放入原Get3读窗。
4. 全部对应预置证明通过后，原产品Get3仍单次、单BSTR、唯一数组、A16/B20、原metadata及身份/状态断言不变。没有由Get3输出推导fixture期望，没有把几何证明当作Get3通过。

拟补离线反例：几何证明路径对GetSystemValue3/_descriptor/SetSystemValue3/保存/重建设置调用trap；半径10冒充A、8冒充B、非完整圆/多段/非finite/中心错误/草图或document漂移均在观察窗前拒绝；单元素BSTR数组seed必须一次、非零/类型非法/异常无fallback；保存/只读四窗及Get3原次数、请求标签、hash和身份保护保持。随后完整portable/SDK及统筹精确head审查，才进入其下一次小范围原生验证。当前未实现此fixture候选。
