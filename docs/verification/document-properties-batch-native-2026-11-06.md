# 文档属性批次：本地原生证据（开发中）

本批在独立分支 `codex/document-properties-batch` 开发；起始基线为 `60c6f463560b2541a17f91e0d6c5d84fe317b8bd`，随后按用户要求先整合 0.2.3，再整合 0.2.4 冻结提交 `a4df72120a951f851e13d1cde569cbc3f754a197`。私有原生组仍各自绑定下文记录的冻结源码，未热替换运行中的校准。本记录不是发布回执；六个新增公共操作及 CLI/MCP/Typed SDK 接线已准备，尚未通过本批安装后的公共原生门禁和完整 CI 验收。字体、总体绘图标准及十项显示设置分别校准，不能由一组通过推定其他页面完成。

## 只读原生校准 read-r1

用户明确要求使用手动启动的 SOLIDWORKS。脚本仅附着精确 PID `2940`，`UserControl=True`、`Visible=True`，不调用 DispatchEx、ConfigureResidentApp、ExitApp 或可见性 setter。初始原有文档为空，本轮只创建、另存及关闭自己的六份临时文档，不将其当作非空用户文档保持的真实验证。

零件、装配、工程图均完成总注释字体17个原生成员、总体标准及A18七项设置读取；显示设置按类型为10/10/5项，工程图不读取基准面字段。偏好读取前后状态和上下文保持，配置模板、实际模板、swconst及生成文件哈希保持，结束仍为同一可见用户宿主、空文档，cleanup=[]。

- 原件：`/private/tmp/docprops-batch-read-r1`；guest：`C:\Workspace\SWCLI-tests\document-properties-batch-20261106-r1\read-r1`。
- read脚本SHA-256：`b7e0ef4b11477958425c543dba64c6ba87f0dbfd4f4e242de2a529f052603119`。
- 84文件源快照ZIP：`177bc43d3a074ec3c430b8eba344e482c88dda2f0e0a41ac09ea0f8c2f5d096d`。
- report：`57b41f4539f1a7c15878987eb5b1ac9bc8dd59138c22b003e1aa40724bd62eea`。
- 独立审计：`4438204e26dea18b6350e7a54e68019858d01150dc9040554a53b7d210407822`，26项通过。
- 实际trace1002条、501组完整begin/end、零error；这是包裹调用计数，不宣称helper内部每个COM调用都独立标记。
- 硬driver固定单次600秒、整组1800秒，退出0，用时31.36秒，不终止SW；r1 driver末次flush前计数1001不替代原trace实际1002条。后续driver已补最终flush计数及空/残缺/error/缺耗时证据拒绝，不改原件。

独立审计逐字节核对84份源码、6份原生baseline、实际TLB和三个模板。原type library的SHA-256为 `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`，常量直接从其导出：Toggle 57/138，Double 30，Integer 42/43/41/145/146/148/147，全部option0。原始 `grid.major_spacing_mm` 键在私有报告中保留原生0.1米，规范公共值应为100毫米；不把该原始数当作0.1毫米。

本轮没有偏好setter，没有证明改变值持久化、公共lease/CAS/no-op、颜色渲染或字体子类型独立。全部这些边界继续待对应门禁。

## 后续统一验收

先在同一明确指定的手动宿主内完成字体、显示及有限标准转换的本地原生校准，保留每次改变后的保存只读重开证据；随后接入公共CLI/MCP路由、请求/结果Schema和字段目录，再集中完成便携回归与一次完整Windows验收。不得重试失败原生调用、自动回滚、组内重启或关闭用户SW。正式发布另需明确授权。

## 首次字体写入诊断 fonts-r1（整体失败，原件保留）

本轮源ZIP `ad8bcee045a9be3a7d8bba66d7d9d1aa543d3128878f55dab7d8880a0ceb9592`、脚本 `21905da7201d281398dbf8991ff7a116cc5bceefd0deacbbe90255829081649e`。part第一项字体名 `汉仪长仿宋体`→`Arial`：ITextFormat属性赋值一次，独立Get仍是before；随后文档Set一次并严格返回True。after只有字体名和备用 `CharHeightInPts` 从12→14变化，生效 `CharHeight=0.0035` 和毫米模式不变，其余成员保持；stamp144/dirty=false未变。

原读回保护把非当前字号表示也当作必须不变，因而明确失败，未SetSaveFlag、未保存改变值，后续display组未执行。不是成功验收，也不推断所有ITextFormat属性或文档类型均为detached。

- 原件：`/private/tmp/docprops-batch-fonts-r1`；driver同前缀加`-driver`。
- report SHA-256：`2cdf2603bf787c87c87ccc7b3de835885a599106b21bc5542ca7ee170b826c1e`。
- 474组trace完整，无COM调用异常，只有两个baseline另存；host2940、UserControl/可见性/原目录保持，cleanup=[]，无SW退出或重启。

[官方字号模式说明](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITextFormat~IsHeightSpecifiedInPts.html)区分CharHeight与CharHeightInPts的当前指定模式，但不承诺两者固定换算，也不解释本轮12→14的原因。本批针对性修复为：非字号写必须保持模式及生效字号原生值，只有备用表示变化能以明确的`native_normalizations`记录；其余成员仍严格保持。完整17字段CAS及最终保存只读重开的raw值比较不放宽。修改后的便携回归已过，新真实写入证明仍待完成；不会无差异重跑此失败组。

## 字体单次新诊断 fonts-r2（私有全组通过）

仅在正规化合同最小修复和便携测试通过后启动新组，不重放fonts-r1。字体、显示、标准三组预先声明顺序，首失败停止，附着用户同一PID2940；源快照ZIP `0a713028d562e616b6d710c5207e2cfe1f4e130f53ba52c4a5a75e1c2796b85d`，执行脚本 `8742a907555ea38cba9ccd978984f433f2a8fc9ddaa6548e7886313c8be4500f`，driver `92d3eb7c4e997845fc1f3aa999e779fa391b0ccb06b4772772e3a6ee427877d0`。

fonts-r2完成三类各七字段，21次ITextFormat属性赋值、21次唯一final Set；每一字段修改均单独保存副本并只读重开，未以最后一次字号覆盖前一次尚未持久化的证明。完整raw17、指定字号模式/生效高度及相关状态核对通过；每个属性赋值后的独立Get均未看到目标属性改变，本结论只针对这21次调用，不推定所有字体对象都detached。

- 原始report：`/private/tmp/docprops-batch-fonts-r2/report.json`，SHA-256 `b30213b0cfd24dcf65aeccf91447d6f9ea682c30bc125146497e62df90a3708b`。
- 离线独立审计仅stdlib，不以producer验证函数为oracle：`/private/tmp/audit-docprops-fonts-r2.py`，173项检查、0失败。
- 审计JSON `/private/tmp/docprops-batch-fonts-r2-independent-audit/audit.json`：`642ad57795aa242a6dfeaa96ecfd6ce774e5187faae5099022548b335422794f`；摘要TXT：`78d9457ee6159670fe9c0d5fc24e46a4f5dfae948bdda5b7d888b342ded4d5ca`。
- 28648条trace、14324组完整begin/end、0error，单次包裹调用最大18.3293秒；硬driver退出0、1358.37秒，在600/1800预算内，没有终止SW或Python子进程。
- 39次实际路径/类型/access/clean重开，45次仅owned文档关闭；27个输出文件hash/size、TLB和模板hash保持。零件V/S/质心保持。原有文档目录为空，结束仍空；同宿主UserControl/可见性保持、cleanup=[]。
- 备用字号真实正规化共9条（点数6条、米表示3条），独立逐条检查模式、生效字号和其余未请求字段，不推断固定换算公式。

此组仍为 `full_acceptance_eligible=false` 的本地私有诊断；没有证明安装版公共lease/CAS/noop/MCP路径、字体子类型独立、实际字形、Wine或发布。后续公共接线代码增加了最后一刻只读保护、显式租约要求及精确显示CAS，冻结私有源快照未被改写，后续验收必须采用最终公共源码。

## 公共接线与便携回归状态

六项新操作已接CLI/daemon/Schema/同一MCP generic execute；三新写操作要求租约及版本戳，旧A18租约策略不变。第一次集成便携全套1974项通过、27项平台skip；随后针对最后一刻只读变化、必填租约、capabilities兼容和精确Double CAS补充关联测试均通过。最后源码尚待最终完整回归与安装后公共Windows门禁，不能把较早全套结果套用为最终CI结论。显示和标准私有组尚未在本记录中声明完成。

## 显示私有组 display-r1（通过）

同一r3源和用户宿主，P/A/D共25次单字段Set均严格True；全部适用值在最终保存点仍与各自初值不同，三份改变副本完整只读重开保持，原输入、其他字段、零件V/S/质心保持。

- 原件 `/private/tmp/docprops-batch-display-r1` 和 `-driver`；report SHA `06eca71043c2eeb86b5ad51ef7145d582b846c0e8748c980e0023475533c557b`。
- 15674条trace、7837完整pair、0error；driver退出0、598.68秒、cleanup=[]、同2940/UserControl/Visible，9个原生文件与source/TLB/templates逐字节核验。
- 独立stdlib审计141项通过：JSON `/private/tmp/docprops-batch-display-r1-independent-audit.json` SHA `3bd55d3fbba6f9cae7af5d4eaee1e9ab66657fc2f877f7e0e767c52033c8ec86`；TXT SHA `2dacbe13aff1c4a897d1224f6be9093bf360268c6293d255d70dab4a47a6f2c8`。

此组证明原生标量及持久化，非公共CLI完成，也不证明颜色通道、渲染、交互捕捉或虚拟交点实体显示。raw spacing以米记录，公共字段以毫米表达。当前公共代码又将expected Double CAS收紧为精确旧值，未修改这份私有原件。

## 标准私有组 standards-r1（失败，不开放转换）

真实首因是本任务观察器用PowerShell Get-Content读取运行中的report.json，与Windows原子替换report.tmp→report.json发生WinError5文件锁冲突。r3 `Calibration.call`在try外执行persist，留下UserControl调用begin而native callable尚未执行；finally清理又写begin，外层监控因overlap停止Python。不是CAD setter失败，不重试API，也不将部分结果当整组成功。

- 原件 `/private/tmp/docprops-batch-standards-r1` / `-driver`；report `3660898f663efccbb7b4e0ad734f50daad6bf9e9b94b41d6141a7378f0a46169`，trace `954f82a9fcc3f4dcf14edb263a9a14deba391b76d529acf768583a3c0dd3c1c0`。
- 11186条trace，5592完整pair加两个未结束begin；driver消费11185条后因overlap停止，797.598秒、child_termination_attempted=true、cleanup=incomplete。未改600/1800预算。
- 14次native Set均True，14份改变副本及只读完整profile核对保留；零件12行完成，装配仅第1行完整完成，第2行在continuation原始不变量检查中断，工程图未执行。18份原生文件hash匹配。
- SDK trace8556条、99个完整request、14setter、无nativeerror；仍不代表组完成。
- 独立失败审计129核对，`success=false`、`audit_completed=true`、`full_acceptance_eligible=false`、`white_list_updates=[]`；JSON `/private/tmp/docprops-batch-standards-r1-independent-audit.json` SHA `44ba5ebb42ea912936a05f18cc90d5c84e0959ab1fcd79192e630e32bb9f9b8f`，TXT `07ccf516e19eff30f3f849d5be2f36b8a2e5400d2e1f73976a3e50d938d6885b`。

原生worker4076与Popen代理4340不同，不能用终止代理证明worker已终止；本任务随后独立Win32进程清单确认两者均不存在、手动SW2940仍在。针对性修复将真实基础解释器和启动授权握手绑定实际PID，保持只终止自己的Popen，不用进程树/全局kill。依赖纯预检已通过：真实base interpreter的Popen6036等于actual6036，现有venv中的pythoncom/win32com可加载，零SW COM调用。

观察器已保留旧源码并取消运行中report读取；后续仅在driver终态后读报告。producer已修pre-call I/O异常终止边界及相同内容重复报告I/O，保留每call trace fsync、每新观察/变更意图的完整快照和原始首因；45项校准及13项watchdog便携检查、独立源码复审通过。新标准组只有在真实worker硬预算和遗留owned文档清理核对完成后才会单独运行，不重跑已通过的字体/显示组。当前标准转换白名单继续为空。

## 0.2.4 SDK integration and resumed main-window calibration

已整合 0.2.4 Typed SDK，六项偏好操作保持字段和值关联、完整快照类型；SDK 17 项测试、生成一致性、严格类型检查及 25 个拒绝样例通过。整批便携回归 2074 项、32 项跳过，日志 `/private/tmp/docprops-batch-v024-full-tests-r1.log`。随后仅同步 main `3bda2c00489dde6a3d1e4521c548f751b1d1c197` 的四个发布流程修复文件，27 项关联测试通过；运行中的 r5 校准源码保持原冻结字节。

独立实例预检在默认 prlctl 的 SYSTEM/session0 上得到空 ROT；改用现有用户/session1 后，主 PID10040 与精确 moniker `SolidWorks_PID_10040` 核对成功。用户授权独占主窗口后，R2 只读基线保存于 `/private/tmp/docprops-batch-preflight/main-10040-resume-20261107T001915/`；两份既有文档中装配体原本 modified=true，不能当成 clean 或擅自保存。

standards-r4 仅启动一次，r5 ZIP SHA-256 `9cf6014c11d809f445e619f7c66098c39cf9f416687a4408394190f2be4ed3c7`，manifest `15d60aab674f9e9b644d0c4288d0402f900a1c98ffe2173aee4eba28b88da4d0`，基于 a4df721、103 个文件含最终 SDK。目标10040/Visible=true、600秒单调用/1800秒整组；保留原两份文档、原前台及磁盘文件哈希。此处仅记录启动和来源，尚不声明整组校准或公共完整验收通过。
