# 单次C#现代part对照：身份通过，GLB仍空BIN

2026-11-12：统筹按267a34c快照先编译、一次identity，再一次invoke；本路仅离线独立复核全部原件，不执行VM/CI/helper/CAD，不重跑part或扫描API。可重放[审计脚本](audit-glb-typed-control-267a34c.py)与[结构化证据](../evidence/glb-typed-control-native-audit-2026-11-12.json)固定编译字节、源码、源读取、完整快照、trace、manifest和原GLB。

| 阶段 | 观察及有限判定 |
| --- | --- |
| 实际PIA编译 | source267a34c，五份源码与Git blob相同，C#前后hash相同；装机PIA原SHA匹配。helper SHA `dd7567afb7f16233a62101712acea31d9e9bbfc0cde6e8ef191b83572c59aede`，实际PE为AMD64/PE32+，编译exit0；编译本身0CAD/0helper执行 |
| identity单次 | report SHA `1bde576e93376b971451834c2e810b879ba3a22c11ee0a994cd49c3115612aaa`；完整契约/身份和一轮完整SourceRead通过、helper exit0，GLB调用0。独立预检audit成功，原fixture按设计失败停止，不当导出成功 |
| invoke单次 | report SHA `a1a482bf9c3070b2ea7854281e6f2bf32cb8efda484247fa6ea1dce3ad3f4d42`；同一次实验的Python app/document/Extension明确交给C#，三轮canonical IUnknown、foreground严格int1、raw完整快照、源hash一致；C#七参SaveAs3一次True/0/0 |
| 输出内容 | 3732B，JSON3704、BIN0，声明无URI buffer720；当前严格校验拒绝，原始拒绝文件及manifest复制字节相同。不是桥接/身份错误，也不因native True/0/0就通过 |

invoke的SW592、实际Python worker708、helper5736、launch6176分别保留。STL/3MF/AMF由原Python helper各导出一次且当前严格校验通过；GLB Python现代调用0、C#真实trace begin/end各1，无旧API/偏好/CIP setter。参数仍Name=原完整staging字符串、Version0/Options1、两个PIA null对象及ref Int32输出。helper读取的三个阶段handshake/before-save/after-normal-return，其全部22个raw标量/配置字段逐项等于完整before，after==before；三次源Read访问/ReadWrite共享均完整，128位ID/volume/size/creation/write/change时间、path-after和hash严格稳定。

双端实际exe raw路径均为 `C:\PROGRA~1\SOLIDW~1\SOLIDW~1\SLDWORKS.exe`，不需要路径改变。本轮没有引入额外exe文件ID采集前置。PIA contract、NORMAL三包一次consumed及helper/producer/owned清理均有成功原件，native前后[]、CloseDoc/ExitApp/WaitForOwnedProcess等完整结束。

失败GLB SHA `04b83d8e0a2ebccd297fc116d17964e183eb081717ef27e1049d6340abcda2ba`，与原hidden Python baseline逐字节一致。两次是各自新建host/新保存原生文件，source原字节不同：本invoke SLDPRT SHA `72d3f2cb0d91bd0ba607278527d414aca4c7e0b1d9343f016d6672e9127ca605`，旧baseline为 `4f975836ffbf38a58d05802c943701c8bab67f0ae0388b1e913e0a8f1df0f7b5`；不能把历史已退出host或文件实例写成复用。本次“同host/document”指该次Python持有者与C#消费者。

结论限于：对这个固定part场景，仅将保存调用从Python动态路径换成装机PIA强类型C#，仍未恢复GLB；Python特有保存绑定不是唯一解释。不认定底层API/导出器/安装/渲染状态根因，也不证明所有Python调用无问题。当前严格内容拒绝继续有效，不补BIN、不重试part或换API。模块清单仍仅保存过滤结果，文件访问监控unknown，不用它们证明运行依赖齐全。

后续按统筹最新收敛准备[MarkingJig独立只读工作副本的现代Python对照](glb-markingjig-readonly-control-plan-2026-11-12.md)：不扩part专用C#，先明确完整引用。历史单组件assembly仅作辅助已核证据，业务原件不动；实际执行仍由统筹亲审。
