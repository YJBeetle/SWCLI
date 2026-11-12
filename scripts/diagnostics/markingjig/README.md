# MarkingJig只读副本现代Python候选

只供统筹亲审。用户确认成功assembly使用DockerSW latest；该实际使用标签与静态2025-zh-cn-cli配置分开，生成时digest/SWCLI/SW/Wine仍未知。本轮只以固定旧缓存ID新建只读元数据容器核PIA，已确认删除；未pull/更新镜像或触发DockerCI，不干扰现有容器。此前e3d9bd9单次只读probe已在OpenDoc7 warning2首停且held ctime后核失败；本轮新候选仅本地准备、未再操作VM/CAD或导出；原项目和既有GLB不动，业务二进制不入仓/CI。本目录不扩part专用C#。完整业务引用图目前仍未知，不能把附近10份原生文件当已证明齐全。

- `markingjig_control.py`：固定来源名单与hash、只读独立副本检查、OpenDoc7规格及实际resolved/完整引用/源状态/几何窗口、一次现有Python现代导出。全模块导入不碰COM。
- `run-markingjig-control.py`：metadata inventory/原件复核模式不启动CAD；原生probe/invoke必须显式参数、Windows C:\Workspace私有copy与新输出、拒绝附着已有SW。复用固定70d8c9e owned harness和原600/1800监督边界，版本/进程身份及实际host状态保留。
- `test_markingjig_control.py`：45项便携正反测试，未证明Windows COM或业务引用齐全。

固定库存只表示已有候选文件。统筹须明确批准selected名单并准备独立副本；代码不复制或自动补齐模型。路径/句柄跨渠道严格比较fingerprint全部字段，仅已核CPython3.14.7/Windows的ctime跨渠道不互比；两条渠道内部ctime原值仍严格前后比较，其他版本不套用例外。copy必须是普通只读文件，拒绝symlink/reparse文件、硬链接、非名单原生文件；逐文件SHA/size匹配批准inventory且本地path/handle指纹稳定。inventory另保护现有GLB的hash/原件状态，原件复核应在原Mac侧前后执行。Windows worker只接私有copy路径，输出与inputs分离，不碰原项目。

OpenDoc7请求及readback：DocumentType2、ReadOnly=true、Silent=true、UseLightWeightDefault=false、LightWeight=false、ViewOnly=false、LoadModel=true、AutoRepair=false。仅设置临时DocumentSpecification，不写全局偏好。当前已对装机33.5 PIA用本机.NET6/C#5静态编译核这些成员和组件/依赖查询，未执行合约方法；旧probe已实际验证八规格readback，但新版warning语义/完整引用未原生通过。

完整性不是只看顶层打开成功：要求OpenDoc7 error严格int0，warning0或已核装机精确ReadOnly2且实际readonly/clean/view-only三状态严格符合，top实际readonly/无编辑/dirty/rebuild/view-only，轻化计数0；GetComponents(False)长度与GetComponentCount(False)相等，每个组件初始suppression为装机resolved枚举2/3、无suppressed/unloaded、加载模型非空、引用配置与其实际模型配置相同，不激活配置。所有外部加载文件必须物理对应批准copy且hash稳定；虚拟组件须明确IsVirtual并证明归属某个已固定assembly，不能凭同名文件猜作外部来源。变换、模型状态、body bounds/area/volume/face/edge等只读几何都记录并比较。缺失、轻化、未知归属/配置/模型/几何即停。

依赖读取已改为现代`IModelDocExtension.GetDependencies`五参：固定两次只读census分别为`(true,false,false,true,true)`和`(true,false,false,false,true)`。第一份包含broken、derived/suppressed及导入来源，第二份只用于比较broken差异，非失败回退/重试；两份原始数组及实际长度均保留，成对结构、多重集或初始loaded外部图覆盖不符就0保存。Search=false，不设置搜索目录；AddReadOnlyInfo=false保持name/path成对，实际文件只读状态由原有模型/文件检查证明。AppendImportedPaths=true不隐藏导入源；含`|imported_path`原文保留后因未批准额外输入而0保存，不剥离后继续。derived不在完整已加载图、名单外、未知虚拟归属都停。`GetNumDependencies`官方只计旧GetDependencies2，未证明与新五参尤其broken/import可比，已移除调用，不补造独立native count。None/非数组返回不强当0；即使合法偶数数组也必须覆盖已加载外部组件。无独立计数保证，完整性只指现代API合同与双向可观察图，不能声称证明所有隐藏/材质资源。见[接口依据及限制](../../../docs/verification/glb-markingjig-modern-dependencies-2026-11-12.md)。

只有完整before成功才允许invoke一次现有`export_active_windows_document(... strict=True)`；仍为原IModelDocExtension.SaveAs3(Name,0,1,null IDispatch,null IDispatch,BYREF I4,BYREF I4)，原暂存/manifest/严格BIN/accessor/mesh保持，失败字节只留新诊断目录。失败后只做原清理及OS hash，不新增CAD后状态读；成功才比较完整after和strict mesh。probe模式只到完整只读snapshot，GLB0，不作为导出通过。没有Resolve/Rebuild/换配置/修引用/重试/旧SaveAs/新建CAD。

当前准备依据与局限：原始MarkingJig GLB可严格解码，10份邻近原生文件仅作固定available列表；直接未压缩字符串检查没有找到可靠引用路径，不能据此推断无引用。本机45项含初始轻化/缺失/未加载/计数错误、只读/原件替换、虚拟归属、未知状态、一次保存及失败后不读CAD。实际Python Automation成员调用、OpenDoc7行为、完整依赖及几何仍待统筹原生验证；无法证明就停，不fallback box。

统筹后续步骤：

1. 审阅源码、元数据inventory及固定参数，明确可复制的selected名单。原件前后核hash，私有副本须只读且来源可追溯；不把available名单当required清单，未知依赖不自动补拷。
2. 审阅通过后才在全新目录显式运行probe或invoke。若probe/打开/引用失败，保留首错及已获得字段，不自动第二轮；是否另行修正须统筹根据原件决定。
3. 若选择invoke，仅一次GLB并保留严格结果及owned退出。Python/上次C#、复杂type2/part、OpenDoc7 readonly已有源/fresh writable part等变量都明确，不当单变量因果；无法保留历史fresh assembly首次关闭前生命周期。

本机纯测试：`python3 -B scripts/diagnostics/markingjig/test_markingjig_control.py`。

接口说明及有限结论见 [方案](../../../docs/verification/glb-markingjig-readonly-control-plan-2026-11-12.md)与[typed part实际审计](../../../docs/verification/glb-typed-control-native-audit-2026-11-12.md)。

当前仅新增供亲审的[预期warning2窄候选](../../../docs/verification/glb-readonly-warning-preparation-2026-11-12.md)及独立[三渠道零CAD取证工具](../../../docs/verification/glb-file-forensics-plan-2026-11-12.md)。Windows VM swconst离线副本仍缺；另已核固定旧Docker缓存安装PIA的精确int2，不替代VM原件；运行前仍强制装机int2，不能用文档值替代。本轮45项MarkingJig/21项forensic假后端测试及23项typed测试通过，无新Windows/VM/CAD执行；原6a25a56失败与held-ctime门禁保留，不把当前候选当已原生通过。
