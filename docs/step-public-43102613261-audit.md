# 公共43102613261：实体完整通过，首失败在线框导入返回

固定原件独立审计通过，公共验收仍失败。head `f56f7929c6877248926ba2497523c8be9d65c5f4`，artifact `13895175070`，原 ZIP SHA256 `6b69d6b9671b9af4fd2220552d6d8b2939a706ac38181acc109aef00717cba18` 与保留的官方API元数据一致。原job日志SHA256 `c3ee4025692d2c0d8dcb748f9ab98a84fe308583974529c88a8c7f0cc8af4f0a` 已核；105个展开文件均与ZIP逐字节相同。没有重新查询状态、下载包或执行CAD/CI。

[机器审计](evidence/step-public-43102613261-audit.json)由纯文件 `audit-step-public-43102613261.py` 生成；原件位于统筹 task-artifacts/step-public-43102613261，完整副本保留在 ignored step-evidence/public-original-43102613261。错误ZIP拒绝检查通过，不修改任何原报告、trace或产物。

公共writer成功，8份输出齐全（6CLI+SDK+MCP），原daemon trace精确8次native SaveAs3 begin/end。所有实际STEP文件hash与报告一致，线框原字节解析出12/320或18/560完整向量；源native hash、前后台peer状态及host身份一致，cleanup[]。这些是导出证据，不能自动替代新reader通过。

reader计划8，开始2，完成1：

- **case0 AP203 solid-surface成功**。LoadFile4返回文档/errors0，解析体积12000mm³、面积3800mm²、质心(0,0,5)符合原阈值；保存save_errors0，标量API不提供warning所以保留null；只读重开errors/warnings0、modified=false，二次物理量与native hash通过。保存46785bytes/SHA256 `2d57ec4589ff7d8352ac5167f566d0b73062f58b6b86c45e3fb36f95dcfab828`。
- **case1 AP203 wireframe是第一真实失败**。同小写r/现factory对象的LoadFile4返回None/errors1，未创建几何、native保存或重开字段；剩余6项未尝试。不能把该错误改写成第一项solid失败、草图断言失败或物理0段。线框原STEP SHA256 `e2637338686a7aa7b817372c187b10514ddea4eb0b4c6039f517d7f7050e9966`，raw文件仍12段/320mm，但没有原生线段观察。

两case的实际factory均非空、STEP QItrue/MapConfigurationData=false，原生typeinfo count0已记录。完整八值在期望点精确读回：3DI=false、GeneralSolid=true、GeneralFree=true、GeneralCurve=AsSketches0；NeutralSolid=true、NeutralFree=false、StepConfig=false、NeutralCurve=0保持原值。各只有3DI与GeneralFree两个owned设置并反序verified恢复，原八值完全一致，无restore_errors。两个journal分别88reads/11stages与80reads/10stages。

reader主trace476行/238配对、observation74行/37配对均结束且error行[]。这不等于业务成功：Load返回正常而errors=1，严格返回断言在trace包裹的Load之后抛出。报告保留首业务错STEP geometry readback failed。总Load2、native保存/重开各1，GetSketchSegments/GetLength/GetErrorCode2均0。owned reader SW5980/rev33.5.0与writer SW1232独立；Exit/wait/handleclose/CoUninitialize各1、cleanup[]。没有捕获全局native进程目录，不虚构全局native[]。

head由artifact元数据、writer、input-identity及原job日志相互支持；本artifact没有加载源码逐文件指纹manifest，因此不冒充已取得完整runtime源码字节证据。installed swconst/sldworks TLB hash与已核版本一致；日志显示pywin32312。

最小后续仅准备另名“**预先选择显式NULL调用＋已审AsSketches0观察器**”：复用459已核安装签名/b312转换/原指针与返回策略，在第一次Load前确定唯一NULL表达和新显式绑定，保留全部八偏好、r、一次factory/QI/Map只读观察、严格健康/完整几何/保存只读重开/hash与owned首错保护。不得先factory失败再null补试；不扫描Neutral或曲线开关，不改几何/健康断言。459发生于本地、不同完整profile且是双变量实验，不能据它断言null是本次CI错误1的已证原因。新组合即使以后执行，也必须新head完整8文件，不复用本次失败改绿。代码候选先交统筹亲审，本轮不接触VM或发起CI。
