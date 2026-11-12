# 43217223437：明确NULL仍未恢复wire；三份原件的逐字段比较

本轮仅原件审计、只读文档核对和候选准备，不执行新CI、VM或CAD。原失败永久保留，不能把本地459或静态几何相同变成当前公共通过。

## 新公共原件审计

[独立机器审计](evidence/step-public-43217223437-audit.json)核对 run43217223437/head `e039ae596d20d870752c6de7b02c8e1b283d5d62`、artifact13944637284、原ZIP SHA256 `5aaf00aaf391020b21029106b1dcad9bfe0409b6e30a21f2b821c527fda0f8cd`、job日志 SHA256 `7b3e89477dc08d9eda912b77f55f79b93d8ededb18b446675a9ab07318fcc578` 和106个展开文件。writer8份输出/hash/实际8次native SaveAs3、source/foreground与cleanup均通过。

reader再次计划8、开始2、完成1：case0实体返回文档/errors0，物理量、native保存46343bytes/SHA `02a1fcf58d8fc3c3834f150dbc86bd9b7957865077a777b4dbcb9c46f1073eb8`、只读重开errors/warnings0、clean/hash通过；save_warnings仍null，不虚构0。case1 AP203wire返回None/errors1，未测任何草图/长度/健康，也未保存或重开；剩余6项未尝试。

这次两个case均记录：一次227名称映射、唯一预选显式Invoke、VARIANT9/None、原map无变、原返回策略完成；工厂仅只读观察、未传入。第二个raw返回也是None，故不再是factory误传或Python返回包装遗漏。完整八值读回与两owned偏好反序恢复通过，journal分别96reads/12stages和88reads/11stages。主trace512行/256配对、观察74行/37配对均结束且无error行；严格业务错误仍在正常Load返回后被报告。owned reader5580、writer7208均rev33.5.0，Exit/wait/handleclose/CoUninitialize完成、cleanup[]；没有全局进程目录证据，不推断全局native[]。

六项源码指纹已核：它们**不等于Git原始LF字节hash**，但都精确匹配e039对应Git文件转换为CRLF的完整checkout字节hash。此差异有明确证据，不当成源码漂移，也不声称native DLL内存证明。

当前CI的明确结论是：**在该文件/环境/完整偏好下，显式NULL没有单独恢复wire导入**。这不是“NULL仍待校准”，不再重跑相同NULL组合。

## 导入前实际八值

下表来自原report的完整CAS检查点，不是期望常量推算；f56与e039完全相同。459取其候选读回及绑定前后两次CAS。

| 偏好 | 本地459 | 公共f56 | 公共e039 |
| --- | --- | --- | --- |
| 3DInterconnect | false | false | false |
| General SolidSurface | true | true | true |
| General FreeCurves | true | true | true |
| Neutral SolidandSurface | true | true | true |
| **Neutral FreeCurvesAndPoints** | **true** | **false** | **false** |
| StepConfigData | false | false | false |
| General CurvePreference | 1 | 0 | 0 |
| Neutral CurvesAndPointsOption | 1 | 0 | 0 |

459相差**三项**，不能声称它隔离证明NeutralFree是根因。f56与e039则在相同八值下分别factory与NULL都未返回wire文档；e039已经排除了本次调用仍误用factory参数的解释。[可复现比较](evidence/step-import-459-f56-e039-comparison.json)保存全部检查点。

## 文件内容、单位和参数

| 输入 | 字节数 | SHA256 |
| --- | --- | --- |
| 459固定原件 | 10595 | 3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90 |
| f56公开wire | 10590 | e2637338686a7aa7b817372c187b10514ddea4eb0b4c6039f517d7f7050e9966 |
| e039公开wire | 10600 | 9e2fe322e280929f5530b9a625fda8d94f845034be6cdd5232b91a01c57d43c6 |

三份都AP203 CONFIG_CONTROL_DESIGN、SI毫米、同一套实体类型/数量，root可达12条两控制点的一次B_SPLINE_CURVE_WITH_KNOTS，25个CartesianPoint，12段/320mm（10/30/40各4），8顶点/degree3/一个连通分量。规范化端点几何signature均 `07a2060bb7d3091434d7c23d5c6bcf292d6d4f019a047671519a15d5af35511e`。

按每条端点边配对后，degree、closed/self-intersect、multiplicity、knot区间以及**有序控制点**也全部相同；不能因为导出顺序/实体ID不同而误报参数化不同。字节仍不同，没有声称全EXPRESS/全部metadata语义等价，更不能用纯文件结果替代native import。不同宿主/文件布局等边界仍存在。

## 官方Neutral开关的适用性与唯一候选

已重新只读解包安装2025 swconst.chm并核hash；[来源记录](evidence/step-neutral-free-source-check.json)与公开[STEP/IGES/ACIS参数表](https://help.solidworks.com/2023/English/api/swconst/FileOpenOptionsSTEPIGESACIS.htm)一致：实体导入中的“自由曲线和点作为草图”映射到bool `swImportNeutral_FreeCurvesAndPoints`。General表则说明关闭3DI时，`swImportFreeCurves`须与`swImportCurvePreference`一起使用。两表没有证明2025 LoadFile4内部的General/Neutral优先关系，不把开关名当作路线已确诊。

唯一有直接语义和原件差异支持的下一偏好候选是：**相对e039仅NeutralFreeCurvesAndPoints=false→true**。保留General/Neutral曲线枚举均0（已审AsSketches合同），不把459另两个枚举1一并移植，不扫描组合。仍使用同一已证227/NULL、r、完整八值CAS、owned恢复、严格健康/12或18向量、native保存只读重开/hash/首失败与600/1800保护。它是可辨别单一偏好差异的假设，尚未证明translator读取优先级或修复成功。

下一候选须在调用前明确选定，绝不先按旧false调用失败再切true；若以后经统筹亲审安排，也须新head的新八文件writer+reader。当前任务只准备审阅代码，不新增CI/VM运行。
