# 现代保存与getter组合原件审计

仅审计 [42405530053](https://github.com/YJBeetle/SWCLI/actions/runs/42405530053) 的精确产品head
`0a00751e44823ca46237000479754634bf50a418`，不追认到后续文档tip或main。
原生宿主为owned hidden Windows SOLIDWORKS 2025 SP5 / revision 33.5.0。
整体full为failure；Windows Python3.9/3.14便携、SDK、wheel及范围验证均success。
下列子集有独立原生证据，但不是full通过、全部路径验收或发布结论。

## 原件与来源

- 官方artifact `13587729372`：`swcli-windows-hosted-42405530053-1`，9159929 bytes。
- 官方与实际ZIP SHA256一致：`a55c00d7e4b7d07cbece2acd0ef5847138efc074f9ddaa3bfead0aef9e967ec9`。
- 原ZIP、官方artifact/run JSON、下载回执、原workflow日志ZIP、203个逐文件比对一致的解包原件、精确head源码均在
  `/Users/YJBeetle/.codex/task-artifacts/saveas3-modern/20261108-combined/run-42405530053`。
- 原workflow日志ZIP的**本地计算**SHA256为`fe3fd79938986aec3c7ae5dc72ca78df94f3d4186b9cac026fd6650a5be5355b`；
  该日志API没有提供官方digest，不将此值称为官方摘要。
- [结构化审计](../evidence/saveas3-getters-native-2026-11-08.json)包含8个原head生产模块SHA256、报告及trace路径、请求ID、文件hash、原生容器形状和首失败。
  离线脚本为上述run目录上级的`audit-combined-original.py`，脚本SHA256也写入回执；不调用CAD、不联网、不修改或修复原件。

## 独立可成立的执行范围

| 项目 | 实际状态 | 原件与限制 |
| --- | --- | --- |
| 配置观察：零件/装配 | 已执行通过 | property preparation原state分别为`[1,159,false,"Default"]`和`[2,120,false,"Default"]`，观察前后完全相同；公共配置属性及保存重开保留相同原始属性值，fresh ID、read-only重开和保存文件hash均核对；summary仅自动保存时间saved_at随保存改变，其他字段持久 |
| 配置观察：工程图空值 | 已执行通过 | 原有annotation DRW夹具保存前、只读重开后均明确`active=null,names=[],count=0`且count为实际integer；没有把“两次相同非空值”视为通过 |
| GetSystemValue3：直径 | 已执行通过 | 前置continuation-front-diameter完整组成功；真实直径16→20 mm，驱动几何及保存重开检查成功；两步使用同一owned宿主 |
| GetSystemValue3：矩形宽/高 | 已执行通过 | 前置rectangle-front完整组成功；width40→50、height30→35 mm，创建、发现、inspect、编辑及保存重开路径到达 |
| 现代SaveAs3：PRT/ASM/DRW | 已执行通过，限到达路径 | annotation准备三类各一次、公共annotation正反六次均保存重开、clean/type/hash一致；P/A公共metadata另存重开也通过。ASM/DRW为已到达的owned夹具子集，不能外推带组件装配或全部工程图业务 |
| 现代SaveAs3：零件STEP/STL/3MF/AMF | 已执行通过 | 保留文件经原head内容解析器重新读取；不是GLB通过证据 |
| 现代SaveAs3：零件GLB | 已执行但内容失败 | 首个实际业务错误是ExportVerificationFailed，尽管native bool=true/errors=0/warnings=0；无效原字节已经保留，详见下节 |
| 带组件装配中性导出、part.create-box保存包装 | 未到达 | assemblies组先在component零件GLB失败；不能把它描述为装配GLB失败或这些后续路径成功 |
| 特征定义typeinfo/IID | 诊断已执行但未证实身份 | 300条swcli.native-interface全部unavailable/com_error；没有任何成功自报typeinfo/IID。revolve与simple-fillet组未到达；不推断v1或v2 |

1263次`ConfigurationManager`和1263次`ActiveConfiguration`原始begin记录，旧`GetActiveConfiguration`记录0次。
33次`IDimension.GetSystemValue3`调用均有匹配begin/end，且同一sequence原生返回形状均为`tuple`、长度1；
13次dimension.inspect、6次dimension.set、2次dimension-diameter、2次discover-diameter、6次dimension-rectangle、4次discover-rectangle。
这些计数包含既有创建/读回/保护流程，**不**声称一个复杂请求只能调用一次Get3；每条返回形状都关联其原始调用。
没有把Python tuple推断为已观测的底层VARIANT/VARTYPE标签。

所有已测尺寸配置均为`Default`。**没有两配置异值原件，不能外推多配置覆盖。**
安装sldworks.tlb实际GetSystemValue3参数名为WhichConfigurations/Config_names；swconst.tlb实际integer
swThisConfiguration=1、swSpecifyConfiguration=3；相关类型库hash、GUID/version、IDimension/ConfigurationManager/Extension IID见JSON。
类型库契约存在与真实getter返回相互独立，前者本身不证明对象绑定；这里另有已到达的33次实际调用和公共值。

## 保存回执、字节与清理

- 两份daemon原trace合计68个保存请求，每请求恰好一次`IModelDocExtension.SaveAs3`，均有begin/end且真实bool=true/errors=0/warnings=0。
  旧ModelDoc2/Extension SaveAs系列为0；GetSystemValue2 trace为0。
- 68份保存/导出回执均按原head schema核对，其中67个成功文件和一个被内容拒绝的GLB。
  另有annotation/property原生准备报告，属于直接owned夹具路径，不把它们混算为68个daemon trace请求。
- 公共annotation三类型正/反共6份保存副本size/hash及原始options重开一致，各类型四个document ID新鲜，host前后相同。
- `native-model/modeling/model.SLDPRT`和Unicode零件后来又做了正常`document.save`，最终大小分别86850/89221，
  与首次SaveAs回执86042/88839不同。原始后续save回执、clean状态和native_in_place_saves最终size能对应；
  JSON明确标成after-subsequent-in-place-save，**不**把最终hash冒充首次SaveAs的字节hash。
- runtime四个到达组分别为native-model success、continuation-front-diameter success、rectangle-front success、assemblies failure。
  四组cleanup均无错误，server_exit_code=0，after_stop实际native_process_ids=[]、verified=true。
- 剩余15组未执行，仍是未到达/SKIP：exports、drawing-save、drawing-save-as、reverse-cut、feature-depth、fillets、drawings、
  center-front、diameter-top、center-top、rectangle-top、diameter-right、center-right、rectangle-right、toolbox。
  annotation DRW重开通过不能替代后续drawing-save/drawings完整组。

## GLB首失败原件（保留，后续由既有STL路线调查）

首失败request `7712054a-7f17-495b-a30a-7d37690bd042`；源为document type1的`component.SLDPRT`，
发生在assemblies组**创建/验证装配之前**。回执ExportVerificationFailed：non_empty=true/signature_valid=false；
真实api_saved=true/save_errors=0/save_warnings=0，无finalization_error替换首错。

原文件为：
`.../original/swcli-native-smoke/hidden/runtime-sets/assemblies/modeling/component-export.invalid-native.glb`，
完整根目录见“原件与来源”。
3800 bytes，SHA256 `2d49602f1bbd443d60b8975d249b4ed8defb5a5948b869eabfddacb1974a2c5c`。
GLB2 header长度3800，JSON chunk3772 bytes，BIN chunk存在但长度0；JSON声明buffers[0].byteLength=720，
bufferViews分别144/288/288 bytes，accessors声明36 indices、24 positions、24 normals。
原head严格mesh解析器拒绝`external or invalid GLB buffer`，没有可读取的实际mesh。
这些是本次现代API的真实原字节结论，不借用旧API失败或把JSON声明的三角形数当作解码几何。

不修改、填补或重封装该BIN；不换参数/绑定重试、不回退旧API、不跳过或放宽GLB断言。
按统筹最新分工，既有STL线程负责GLB原字节/sidecar/官方选项首因及必要实现修复；本路不重复实现或派发CI。

## 特征定义身份诊断的明确缺口

300条均只有diagnostic_error_type=com_error，returned_typeinfo缺失，returned_typeinfo_matches_v2=false。
按业务operation分布：feature.extrude58、feature.cut-extrude25、feature.inspect105、feature.set-depth112。
诊断没有影响业务结果，native-model仍成功；它也**没有**证明已有v2，或证明实际绑定v1。
这个精确head没有保存HRESULT或异常发生的typeinfo子步骤，不能离线猜出是GetTypeInfo、GetTypeAttr还是GetDocumentation。
安装库预检中的IDimension/ConfigurationManager/Extension IID也不能替代这三种FeatureData返回对象的IID。
revolve/simple-fillet未到达，继续待证。没有因此盲CastTo、QueryInterface、换接口调用或新建模型。

## 分工与未来集成

本次仅提交审计文档与JSON，不改变产品head0a00751的行为，不新增Windows验证。
原生写入、保存、首错与原件不重写；GLB修复路线与本路审计分别推进。
最终是否先合已证实的getter/SaveAs子集、main集成及发布由统筹本人审查决定。

已只读检查统筹所报main `960839e52d0c433c817e71e02493a27681f7e858` 的Windows便携修复：
YAML测试依赖、trace关闭先于目录清理、LF/CRLF精确hash断言。后续合并必须保留这些修复，
并保留main新增三组文档偏好、SDK/schema与worker保护；不能用本分支旧整文件覆盖main。
尤其daemon operations/server的本路保存首错保护必须与main偏好保护合并保留；SDK派生文件须按合并后的源生成。
此处没有自行合入或修改main，也未使用VM、DockerSW或MacSW。
