# 仅NeutralFree=false→true：下一单偏好候选（未执行）

依据是[43217223437原件与三份输入比较](step-public-43217223437-neutral-comparison.md)。当前已明确：公共e039在227/NULL、原包装完成、八值已读回的情况下，第二AP203wire仍None/errors1，不能继续把“误传factory”当解释或重跑原NULL组合。459虽返回过wire，但其NeutralFree和两个曲线枚举共三项不同，环境也不同，不是Neutral单因果证明。

官方STEP/IGES/ACIS参数表把NeutralFree映射为自由曲线/点作为草图的实体导入选择；General表另述关闭3DI时的GeneralFree/Curve参数，未给出两族在2025 LoadFile4中的优先级。三份文件字节不同，但毫米单位、实体数量、12线/320mm、端点、有序控制点、degree/knots/multiplicity均一致；不宣称全EXPRESS等价。由此只提出一个有明确语义和原件差异支持的候选，不能声称根因或成功已证。

## 预选与唯一差异

新 `--neutral-free-null-sketch-candidate` 与原factory/sketch、原NULL/sketch两模式互斥，仍只能接受fresh same-head公开8文件报告。模式在宿主获取前确定。

相对e039实际导入前八值，仅 `swImportNeutral_FreeCurvesAndPoints` **false→true**；GeneralCurve和NeutralCurve都保持0，另外五字段不变。完整新向量按既有顺序为 `(False,True,True,True,True,False,0,0)`。不移植459的两个枚举1，不扫组合，不改Map，也不遇错后补试。

新模式构建完整期望向量，若其余字段不能与e039基线一致，任何setter前即拒绝。journal保存e039八值基线和changed_from_e039，必须恰好一个NeutralFree字段。新Neutral toggle纳入同一owned设置顺序（General设置后），VOID setter仍要求None，写后核完整八值；原值、尝试写入和可能部分生效完整记录。只反序恢复owned attempted字段，外部/未知值保护、首错分离、全八值原状核验不变。

调用路由复用e039已执行的同一代码：同安装签名与b312证明、同精确原指针/返回策略、每case一次GetIDs227与一次显式 `Invoke(227,0,1,1,path,'r',VARIANT(9,None),Errors)`。不重新“校准NULL”或换绑定；这里只是在原路由上改变一个预选偏好。证据外层以e039为比较head，changed_variables仅列NeutralFree，NULL单因果声明仍false；内层保留相对历史f56的绑定比较说明，不冒充跨宿主指针身份相同。

## 原验收边界保持

完整8值typed CAS在每setter前、写后和实际调用前执行，输入hash在绑定前后复核。factory/QI/Map仅观察，NULL为实际参数。原node表/绑定准入、健康码精确int0、空/混合/未知类型拒绝、12或18段/320或560mm和原全部向量/阈值、实体物理量、native保存、只读重开与二次health/几何/hash全部不变。任何None/errors1仍严格失败且只调用一次。

原native Windows33.5.0、hidden owned宿主、独立writer/reader及source/foreground/lease/CAS、清理和600秒调用/1800秒组/31分钟外层保护不变。只将现有public readback的唯一CLI参数从旧NULL/sketch候选替换为新Neutral候选；换回此参数后ci.yml与e039逐字节相同，没有新workflow inputs、PR入口、默认值、条件或时限。原false模式保留供历史解释，不自动回放。

这是待统筹亲审的本地源码和接线，不是执行授权；本轮没有push、dispatch、VM/CAD、容器或旧run网络状态查询。若统筹后续安排，仍须新head、新八文件、新原件，首失败停止并保留证据。两次公共失败及459的严格reference失败不覆盖、不转绿。

## 便携与静态验证

新增9项候选测试，全部相关STEP **183项通过**（9.585秒）。覆盖三种几何的严格保存只读重开、仅一个偏好差异、同一NULL载体/227且单Invoke、None/errors1不fallback、Neutral部分setter错误恢复、恢复失败不绿且保留原首错、其余八值漂移零setter拒绝、清理unknown不覆写、health/长度/hash拒绝、互斥与父子flag、同head8文件与prehost选项、唯一公开CI参数。

原174项继续通过，含既有13,824选择组合。actionlint1.7.12直接exit0，重复键拒绝YAML、唯一参数字节差异、Python编译/CLI help/diff检查通过；全b312源码类与固定本机安装TLB静态preflight通过，没有COM/CAD调用。前两次固定失败审计复跑与提交输出逐字节一致。记录位于ignored `step-evidence/step-neutral-free-*`。

真实目标结果仍未知；便携测试和文档不能证明Neutral优先关系或wire已恢复。由统筹亲审精确head后决定下一次有限执行。
