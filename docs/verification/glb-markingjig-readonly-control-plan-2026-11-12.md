# MarkingJig独立只读副本的现代Python单次对照

状态：统筹已取得typed part实际BIN0原件，条件已满足；最新收敛为用户真实MarkingJig源，历史generated.SLDASM只作辅助。[候选代码与36项便携测试](../../scripts/diagnostics/markingjig/README.md)已准备，实际执行由统筹亲审；本路不复制业务模型到VM/仓库，不启动CAD/Blender，不派CI。part专用C#Core.Fixture保持，不扩成assembly。

实际更新：唯一批准VM probe已在OpenDoc7 Error0/Warning2首停，0保存；同时copy held-channel ctime窗口变化被严格拒绝，原件不变/owned退出/idle恢复均已核。见[实际有限结果](glb-markingjig-probe-native-audit-2026-11-12.md)，以下保留原准备方案，不当执行通过。

目标：原项目和既有GLB不动，统筹在C:\Workspace独立私有目录准备经批准固定名单的只读工作副本，保留逐文件原始hash/size及前后检查。附近原生文件只能作候选名单，不能据同目录/GLB mesh数猜定完整引用。原始二进制未检出可用的明文引用线索；目前完整依赖图仍未知。无法证完整就0保存停止，不换历史box或其他模型回退。

打开方案固定OpenDoc7/GetOpenDocSpec：ReadOnly=true、Silent=true、UseLightWeightDefault=false、LightWeight=false、ViewOnly=false、LoadModel=true；setter仅作用临时文档规格，不写全局偏好。源码准备先在本机以已核装机33.5 PIA作静态类型编译验证这些成员，不执行合约方法；这不是Windows COM调用验证。OpenDoc7仍受Large Assembly等环境影响，故必须检查实际初始轻化计数、全部组件suppression/loaded状态，而不能只信请求值。不开后再Resolve/Rebuild、切配置、修引用或重试。

完整性窗口必须覆盖：top与所有加载模型的类型/path/title/config/dirty/rebuild/RO/view-only/编辑状态，所有组件的实际路径、引用配置、suppression/虚拟属性、加载模型和变换/几何；native dependency数组与加载组件图相互核对，所有外部文件限定在已批准副本名单且hash/身份稳定。虚拟/派生/外部引用只要无法证归属或完整就明确unknown并停。业务源与引用前后hash、owned host/foreground以及读取状态保持；缺失/轻化/未知0保存，不通过额外采集或修复链掩盖。

只有上述门禁全通过才由**现有Python现代SaveAs3 helper**一次GLB，Version0/Options1/两个显式null IDispatch/BYREF I4不改；输出只入全新诊断目录，保留原暂存规则、manifest、原始字节、严格BIN/accessor/mesh和首错。清理使用同一owned host，不附着用户应用，不保存源；内容失败后不新增CAD状态读，仅清理/OS哈希复核。未证明完整引用时根本不调用导出。

新增变量明确：Python与上次C#调用层、type2/复杂真实源与fresh type1盒子、既有文件OpenDoc7只读/初始fully resolved与fresh writable part、引用/渲染/配置上下文。无法保留历史fresh assembly首次关闭前生命周期，也不能补造用户历史实际job/runtime/API状态。成功只支持当前现代Python路径可以导出这份assembly；失败只说明该组新条件也失败。两者都不能单独归因doctype、某个参数、Docker/Wine或版本；更不能否定已固定的用户历史成功GLB。

依据：[OpenDoc7](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.ISldWorks~OpenDoc7.html)、[LightWeight与UseLightWeightDefault](https://help.solidworks.com/2024/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDocumentSpecification~LightWeight.html)、[依赖数组包含递归和suppressed引用](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~GetDocumentDependencies2.html)。这些接口合同不能替代当前源模型的实际完整引用证据。

用户最新运行观察：成功assembly使用DockerSW **latest**，静态源repo的2025-zh-cn-cli配置仅为另一条配置线索；不能替代实际标签，更不能把当前latest解析结果当生成时digest。本轮不pull/更新镜像、不启动或重启容器、不触发DockerCI或晋升。对比失败的native Windows33.5.0 fresh part时，宿主和文档上下文同时不同，均不单独定因。

固定metadata库存见[候选输入名单](../evidence/glb-markingjig-input-inventory-2026-11-12.json)，SHA `d7db20f8041424115a97b91376001be759b32fad6e5faa2cc405fe971a13185d`；10份available原生文件及原GLB前后指纹/hash保持，仍不称required/complete依赖集。实际副本selected名单、完整引用证明和是否执行由统筹确定，代码不自动复制或扩名单。

亲审修正：依赖改用现代Extension五参及包含/排除broken的固定只读对照，Search=false、AppendImportedPaths=true，不拿旧GetNumDependencies作新数组计数。raw返回、broken差异、derived/import及加载图覆盖规则见[接口说明](glb-markingjig-modern-dependencies-2026-11-12.md)；未知结构（含未证明语义的None）0保存。文件跨渠道仅已核CPython3.14.7 Windows ctime例外，mode/attrs/birth/nlink等全量字段及同渠道ctime严格不变。
