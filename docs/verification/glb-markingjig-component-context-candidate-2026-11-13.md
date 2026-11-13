# MarkingJig 组件上下文几何候选（离线，2026-11-13）

**只完成源码、装机 PIA 元数据核对和离线测试，未运行本候选的 VM/COM/CAD。** 默认配置门禁保留；新增模式只准显式零导出 probe。未改产品、原 harness、阶段或文件保护，未改已冻结 probe02/03 的七份准备文件，没有新配额、launcher 或 native 重试。本候选尚未 push；CI43402895583 不覆盖它。

## 原实际首错不改写

Root 的 probe03 已真正进入 native：owned host PID1332 / revision33.5.0，OpenDoc7 error0/warning2；在第4个组件 `MarkingJig-1/MarkingJigBlock-1` 记录到引用配置 `渲染`，GetModelDoc2 文档 active 配置 `默认`，两者都在模型配置集合中。原门禁停止于 `component model represents different configuration; no activation`，没有完整观察或 loaded seal，SaveAs/export0。

原 report SHA `37349b946c7b92f4d8209fd8ac75b567f4dadbcb1127beb206f30b1c9ea6b940`。Root 原审计与全部列出的原件 SHA 已在主机独立重读核对；380条 trace begin/end 配对，owned CloseDoc/ExitApp/wait/CloseHandle/CoUninitialize、三次 OS after native[]、私有输入/代码/准备源码后核和11份Mac原件守恒由原件证明。**trace没有记录原 native 进程退出码，不能补称exit0**；完整图/几何/导出仍未验收。

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261113/markingjig-phase-probe-c9846f6-03`。没有用当前候选重解旧数据、补 case 或升级结果。

## 接口依据与装机契约

[GetModelDoc2 官方说明（可读的2024页）](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~getmodeldoc2.html) 明确区分 model 文档的保存/打开状态与组件实例的装配级信息。因此，active modelDoc 配置与组件引用配置不同，并不证明组件实例本身用错配置；也不能继续拿该 modelDoc 的 active part bodies 代替实例几何。

[2025 ActiveConfiguration](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IConfigurationManager~ActiveConfiguration.html) 说明装配配置中的组件、body、transform 可能随配置而变。[GetBodies3 官方方法页（可读的2018页）](https://help.solidworks.com/2018/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~GetBodies3.html) 规定它只支持 part component 的 solid/surface bodies，另返回 normal/user 信息；assembly 修改可形成 user bodies，surface不产生user bodies。[2025 官方示例](https://help.solidworks.com/2025/english/api/sldworksapi/Get_Bodies_in_Components_Example_VB.htm) 展示组件 body 与单独打开的原始 part 不同。本轮直接打开2025 GetBodies3/GetModelDoc2方法URL只得到站点壳，未冒称已读取其正文；以可读官方方法说明、2025上下文说明/示例和本机33.5装机PIA交叉核对。

离线 .NET6/C#5 仅读取固定 PIA 元数据，没有 COM 创建、目标方法或静态字段执行：

- sldworks PIA SHA `a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1`；swconst PIA SHA `1afe845af233292fe22e58a2b893d6065f36cd85f2728866011ad10771b98fa9`，两程序集版本均33.5.0.53。
- `IComponent2.GetBodies3` DispId124；输入 `System.Int32 BodyType`，输出 `System.Object& BodiesInfo` / IsOut=true，return和out均MarshalAs SafeArray。**SafeArraySubType=0未指定**，PIA本身不证明实际Python封送形式。
- 实际 literal `swUserBody_e=0`、`swNormalBody_e=1`，不是凭名称猜的相反映射；body类型 `swAllBodies=-1`、solid0、sheet1。新模式仍通过原 LoadTypeLib 枚举门禁按精确int核对这些值。

完整 metadata：[装机契约](../evidence/glb-markingjig-component-PIA-contract-2026-11-13.json)，SHA `d768a8ed4ba49402518cded01011310846e6f2380c71f0d9a14b502cd68730a3`；采集源 [inspect-markingjig-component-contract.cs](inspect-markingjig-component-contract.cs)。

## 显式候选与保持的保护

新模式需要同时指定：

```text
--mode probe --phase-policy opening-transition-probe --component-context-policy component-bodies-probe
```

默认仍为 `strict-model-configuration`，原 `referenced_configuration==model.configuration` 断言和错误原文保留，invoke不能借新模式绕过。无 phase guard、无明确 GetBodies3 binding、枚举错误、未知policy或invoke，均在 OpenDoc 前拒绝。

新模式逐组件保留两个来源：

1. 原 GetModelDoc2 文档状态及原 active-model geometry 完整保留，明确标为 active-document state；文档的readonly/clean/rebuild/edit、实际active配置、完整配置集合与现有body观察仍严格。引用配置必须非空且在独立模型配置集合内，原始引用/active值与匹配bool同时记录，不激活配置。
2. part component 使用一次明确 `GetBodies3(swAllBodies, BYREF VARIANT)` 候选，保留返回类型、body数、原body-info数组和逐body原生type、bounds、12项mass properties、area/volume/centroid、face/edge数。要求非空有界数组、信息数一一对应、精确int枚举、solid/sheet、有限几何、合法bounds/area/volume/拓扑计数。没有 GetBody/旧GetBodies2 fallback、类型强转或失败重试。普通modelDoc GetBodies2仍只是独立状态读，不作为实例几何替代。
3. 每次组件几何后用 IsSame 复核同一 modelDoc，重读原组件引用配置、完整modelDoc状态并严格比较。subassembly不调用part专用GetBodies3，但同样复核引用与modelDoc状态；其实际part实例仍由原完整平铺census覆盖。全图至少要有已完成的part实例几何，空subassembly集合不能冒充geometry通过。
4. 完整图、双modern dependency census、外部物理file identity/同file、virtual owner、catalog、foreground、原SHA/完整128-bit identity/metadata、原不可变WorkingCopy.before、phase opening分类、唯一loaded seal和第二完整观察的逐字比较全保留。模型/引用/身份/几何/CAS变化仍首错停止，任何字段未知都不猜；600/1800预算不变。

原 Transform2 仍单独完整记录；不对body施加变换，也不宣称这里已证明其坐标系与历史GLB对齐。几何是native读回指纹比较，不等于精确B-rep、mesh精度或导出验收。active-model geometry仍是额外严格观察，它不可读也会停，不能用实例body掩盖该失败。

supervisor audit显式绑定所请求policy，复算active/reference匹配bool、检查所有组件上下文完整与非空part几何、独立state-after、两个完整观察相同；不能把新模式回执当原strict模式通过。原空case/first_error/secondary独立回执修复保持。

## 离线验证与下一边界

MarkingJig **140项通过**（新增组件context23项），typed bridge23项通过；帮助入口可读新参数、无COM。新增用例覆盖默认 mismatch保留、显式Render/Default配置分别记录且两次实例几何一致、invoke/缺phase/缺binding/错枚举/缺配置先拒绝、None/空body/错info长度/bool/float/未知tag/unsupported type/surface-user拒绝、真实原getter首错与部分raw、引用/文档stamp/对象身份在几何读取期间变化、loaded阶段geometry变化不能重封、空图/不完整context/错policy审计拒绝，以及实际binding AST只调用一次GetBodies3并保留out数组。

其中 BYREF VARIANT 仅用假win32com模块执行实际binding AST；**没有实际 COM GetBodies3 封送、IBody2读取或业务几何证据**。也没有独立取得装机 GetBodies3 的 native TYPEDESC，本轮不能把PIA或fake binding测试当该证据。遇到真实binding错误或返回形状未知应原样首停，不换API或自动再跑。

Root亲审此源码与契约后，下一步仍须新精确源码包、完整全新launcher（包含此显式flag）、fresh原件/空闲/用户/会话检查和单独CAD票。没有新launcher或票号可直接拿本工作树启动。现有c39dade CI只证明便携fixturefix，不能背书本候选。
