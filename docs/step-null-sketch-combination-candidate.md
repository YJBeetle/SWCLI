# 预选显式 NULL＋AsSketches0：公共读回最小组合候选

这是针对[公共43102613261固定原件](step-public-43102613261-audit.md)的新候选，尚未原生执行。原门禁仍是失败：writer8/8；reader第一实体完整通过，第二AP203wire在LoadFile4返回None/errors1，未进入草图几何/健康检查。原report/ZIP、已通过实体和失败线框全部保留，不改判当前head已验收。

直接依据是两件不同边界的事实：本次CI仍把factory对象传入LoadFile4；此前459的本地显式NULL调用确实返回过wire模型，但它还改变了绑定、使用不同完整偏好且环境不同。459不能证明null单一变量是本次CI错误1的原因，也没有完成保存重开。此候选只提出明确、可审阅的下一组输入，不宣称供应商行为矛盾已解决或As3DCurves已修复。

## 唯一预选路线

新增 `--null-sketch-readback-candidate`，与原 `--sketch-readback-candidate` 互斥，二者都必须有完整公开writer的 `--export-report`。worker在启动宿主前就确定模式。内部六组合、旧原件诊断、默认reference路径以及原factory/sketch模式仍保留各自原行为，均不遇错后切换到NULL。

现有 public readback 的CI命令只将原候选flag替换为新组合flag，作为本次待审源码的一部分。把新flag换回旧flag后，整个工作流与f56逐字节相同；没有新workflow inputs、PR入口、guard、默认值、时限或并发改动。**未push或dispatch**；统筹须先亲审精确提交与队列，再决定是否授权一次新的八文件公共运行。

## 完整八值不变，改变项明确

新组合要求读回期望向量精确等于f56原件的实际期望值，不会为达到它而改写Neutral：

| 参数 | 固定值 |
| --- | --- |
| swMultiCAD_Enable3DInterconnect | false |
| swImportSolidSurface / swImportFreeCurves | true / true |
| swImportNeutral_SolidandSurface / swImportNeutral_FreeCurvesAndPoints | true / false |
| swImportStepConfigData | false |
| swImportCurvePreference / swImportNeutral_CurvesAndPointsOption | 0 / 0 |

General的官方AsSketches=0、As3dCurves=1仍按原精确owner/name解析并核验；其余八值由既有typed snapshot、完整CAS和原值恢复逻辑管理。若保留的Neutral原值导致整个期望向量不同，本组合拒绝零Load；不扫描开关或写它们补齐。与f56相比明确改变**调用绑定和实际ImportData值**两项；证据字段以f56为比较基线，single_null_causal_claim=false。旧459 helper的默认60f基线不变，只增加可信调用方可选的已知基线标签。

## 启动前与每次单调用

1. 原native Windows、hidden owned host、rev33.5.0限制、fresh same-head八文件writer、cleanup[]和唯一有序输出/hash要求原样保留。要求pywin32312；复用已审三份b312源码hash、运行时核心/返回/client/factory代码证明和固定安装sldworks.tlb纯文件签名核对。失败在宿主获取前停止，不安装/升级包、不重包装宿主。preflight保存package/contract和六个源码文件hash；源码文件hash不冒充native DLL内存证明。
2. 每case仍恰好一次原GetImportFileData及其只读STEP QI/Map观察，不设置Map。新路线核对已有观察为非空工厂、STEP QItrue、Map可读bool；**工厂仅观察，不是实际传参**。
3. 复用459的InstalledTlbNullInvoke，精确原client/dynamic包装、原注册PyIDispatch指针、原返回包装策略。仅一次直接GetIDsOfNames(0,LoadFile4)=精确int227，前后Python maps不变；不用LoadFile4 getattr、FlagAsMethod、EnsureDispatch、InvokeTypes或换宿主。绑定metadata不足不是错误的替代签名理由，未知即停止。
4. 绑定前后复核本case实际STEP字节hash；绑定后再核完整八值CAS，才进行唯一 `Invoke(227,0,1,1,path,'r',VARIANT(9,None),errors)`。Errors仍为原BYREF I4零载体。没有先调用factory参数版本再补试；此路线对八个已排定case预先统一适用，包括实体，不仅在wire失败后启用。
5. 原helper保留raw返回类型、原返回包装完成状态、NULL载体观测与来源证明；attempted只代表Python进入调用，不虚构C++封送后native调用边界或地址测量。任何准入/封送/调用/包装失败均终止，不重新准备、不换表达；真实None/errors1仍严格失败。返回文档即由原owned清理负责，不因错误码而丢弃责任。

native/public实际运行之前，package/runtime class和全八值仍可能保护拒绝；本地源码/便携验证不替代目标环境证据。

## 其余验收原样执行

已审的草图类型白名单、GetErrorCode2精确int0、非零warning/未知/空草图拒绝、完整top/sub ID去重、12/320或18/560原解析向量和所有阈值保持。混入reference/未知类型不fallback。实体体积/面积/质心、native save_errors0（标量warning仍null）、只读重开errors/warnings0和clean状态、第二次health/几何、native/STEP hash全部复用原流程。

完整八值CAS、每setter读回、仅owned attempted反序恢复、外部第三值保护、首错与恢复错误分离、恢复失败清除成功仍不变。writer source/foreground/lease/CAS和两owned宿主清理不变；每调用600秒、每组1800秒、外层31分钟与首失败停止不变。本地准备不接触Windows VM（当前另路占用），也没有操作Docker/CAD或CI。

## 验证与交回

新增 **10项组合测试**，全部相关STEP **174项通过**（8.290秒）。实际单个显式NULL载体/单Invoke、无原Load getattr/无factory参数调用、三种几何模式的保存只读重开、真实None/errors1无重试、错误nameID零Invoke、不同Neutral原值拒绝且不写它、health/长度复验、prehost版本/签名失败、新旧模式互斥、同head精确8文件、父子flag与监督均有覆盖。原164项包括既有绑定、恢复、类型、几何和CI选择保护继续通过。

b312完整源码类/函数的静态preflight与固定本机安装TLB解析通过；没有导入COM或运行CAD。actionlint1.7.12、重复键拒绝YAML及“唯一公开参数替换”字节证明、Python语法、CLI help和diff检查通过。固定43102613261审计复跑与已提交机器记录逐字节一致。

验证记录位于ignored `step-evidence/step-null-sketch-*`。后续由统筹亲审本候选及唯一CI替换；若决定单次运行，必须新提交的新writer八文件和新reader原件，保留第一真实失败和清理状态。不重复原head、复用旧report、放宽断言或以本地459替代新的公共8/8证明。

后续实际结果：43217223437/e039已明确NULL仍在线框None/errors1，第一实体完整通过。原件与逐字段比较见[固定审计](step-public-43217223437-neutral-comparison.md)。不再重复同NULL组合；新的[仅NeutralFree=true候选](step-neutral-free-null-candidate.md)保持该路由及两个枚举0，只改一个偏好，仍待审且未执行。
