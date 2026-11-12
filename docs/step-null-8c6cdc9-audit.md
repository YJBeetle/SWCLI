# 8c6cdc9 原包装候选：现有方法元数据缺失，零导入

独立审计通过，运行仍在LoadFile4之前保护停止。report SHA256 `926102eaab43af5f2051b9ed44f6de5ad73dcb8e30ea35f946845fcb160cc85b`，源码archive SHA256 `c8258b64cc4a35252ba5090b21175c0ecb5261352e1580721ce4a726a66dcfae`。完整428文件归档及七项关键加载hash均与提交 `8c6cdc92b7e39224f464ccebb90acf3b200f92a3`逐字节一致。原件在统筹目录wire-once-8c6cdc9-01和ignored副本step-evidence/wire-original-8c6cdc9-01保留；[机器审计](evidence/step-null-8c6cdc9-audit.json)由本轮独立脚本产生。

首错是 `NULL binding refused: no known method and no readable lazy metadata`。实际client.CDispatch、MRO、继承处理函数/返回包装策略及b312文件/代码证明均已通过。失败点源码只证明LoadFile4不在当时mapFuncs中，而且state.get('_lazydata_')为None；**旧原件没有保存完整state、缓存方法、property maps、GetIDsOfNames或原生GetTypeInfo结果**。不能补写GetTypeInfoCount=0或某一个注册错误。

bound_method_invocation_attempted=false；load_return保持not-attempted、返回对象/errors均null。geometry仅unavailable/value=null，没有任何raw特征或长度。主trace362行=181次配对，唯一error是verify-original-LoadFile4-binding；observation14行=7次配对全部结束。LoadFile4、CloseDoc和几何测量均0，无保存/新建/导出/选择或重试。factory/QI/只读Map各有一次显式观察操作，QItrue/Mapfalse；此计数是脚本外层操作次数，不把未记录的CDispatch底层解析/探测次数伪装为已测得。

五项设置及反序恢复verified，154条读取、18个完整向量阶段通过，changed_from_60f1cf8=[]，原八值恢复，restore_errors=[]。固定输入原字节SHA3a4f0326...、10595bytes、attributes33和全部metadata检查点一致。SW PID1384/rev33.5.0隐藏owned；Exit/wait/handleclose/CoUninitialize各1，cleanup[]、启动前/退出后native[]。不是SOLIDWORKS导入失败或null转换结果。

## 离线获取链为何不能还原唯一原因

原获取链仍是独立入口CheckedClient→daemon.server.acquire_resident_app→client.DispatchEx→Dispatch→__WrapDispatch→client.CDispatch；未更换包装。已核b312 [dynamic.Dispatch/MakeOleRepr](https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/dynamic.py)在获取TypeInfo、TypeComp或构建表示时会捕获部分COM错误；无法构建表示时可回落到空DispatchItem。TypeComp失败也可能留下lazydata=None而尝试非lazy构建，名字/函数读取或构建失败还可能丢掉个别方法。因此缺少Python lazy缓存并不等于原生TypeInfo必然不存在。

已核源码还有一个重要边界：未知成员的正常getattr可先GetIDsOfNames，再以PROPERTYGET作无参数Invoke探测，遇到特定上下文错误后才建立通用方法。既有gate在缺少方法表/lazy时拒绝，避免了对LoadFile4进行这一步探测。不能通过_FlagAsMethod、重包装或强制InvokeTypes来回填“原绑定已证明”。原factory等普通动态访问也可能包含解析步骤，旧trace没有原生Invoke边界计数；本轮不据源码可能性虚构它实际发生过几次。

本轮先补Python-only既有state快照，准确区分key缺失/None、方法和属性map、cached method；另准备严格有界、只读GetIDsOfNames/TypeInfo取证函数，但不接入自动host重放。若无法在零业务调用下证明原绑定，应停止原路径候选；按统筹补充决策，另名准备“安装TLB约束的显式绑定＋null”，明确同时改变绑定与ImportData，不归因单一null。此处只准备，不执行。

复跑：原audit-step-null-811bb97.py新增 `--candidate-8c6cdc9`，输入本次原件目录/归档/相同原始STEP，输出另一路径。811旧审计复跑与已提交机器记录字节一致。本轮没有操作VM/CAD/CI、重放或push。
