# 原 client.CDispatch 窄支持候选（仅本地准备）

811bb97在包装白名单处保护停止，零LoadFile4；[独立原件审计](step-null-811bb97-audit.md)已保存。实际对象是正常获取链中的`win32com.client.CDispatch`，此前精确dynamic.CDispatch限制过窄。本候选只修正诊断准入，不声称修复了null转换、SOLIDWORKS导入或参考曲线表示。

## 保留实际获取与绑定链

源码链为独立入口CheckedClient→既有owned acquire_resident_app→原win32com.client.DispatchEx→Dispatch→__WrapDispatch→正常client包装。root实际执行记录只确认wrapper_type，不回填它未记录的gencache结果或LoadFile4绑定分支。未改获取链、包装对象、宿主、调用方法生成器或返回对象包装策略，不调用Dispatch/EnsureDispatch来重包现有app，也不把方法强制改成Invoke/InvokeTypes。

[固定b312主源码](https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/__init__.py)中client.CDispatch直接继承dynamic.CDispatch，只定义`_wrap_dispatch_`和`__dir__`。前者保留客户端原有返回对象包装策略，后者委托原目录显示；LoadFile4及其核心绑定处理函数均继承。该源文件hash已由811bb97实际package证据核对；本轮另外将完整模块编译的类/函数代码与候选校验逻辑作静态自检，保留future annotations标志和实际编译上下文，未导入pythoncom或执行COM。

## 新增的精确证明

- host启动前：仍核dynamic/build/client三个已安装b312文件hash，仅CRLF归一化。原四个dynamic处理函数运行时代码证明保留；新增client类的两个覆盖函数，以及模块DispatchEx/Dispatch/__WrapDispatch三个获取/返回链函数与已核完整源码的字节码比较，记录`client_wrapper_handlers`、`client_factory_handlers`。
- 准入只允许`type(raw) is dynamic.CDispatch`或`type(raw) is client.CDispatch`。后者必须直接单继承dynamic，MRO恰为client→dynamic→object；不使用泛化isinstance放行任意子类，generated/custom/多继承类仍拒绝。
- client的四个绑定处理函数、默认属性读取、良好对象包装辅助函数须继承原dynamic身份；类中不得新增LoadFile4。两个client覆盖函数和三个客户端获取链函数须仍与预检指纹相同，不能在运行时另换策略；原dynamic属性查找也不得被替换。相关实例覆写拒绝。
- 仍只提前读取原方法表/必要只读LazyAddAttr_元数据，禁止未知成员Invoke探测。签名、方法生成器、原缓存函数/receiver、typed或generic路径与单一空值表达的证明全部沿用811bb97，不放宽。
- 调用前重核client继承/处理函数/返回策略、原对象的精确类、缓存方法和实际载体。包装类或处理函数变更即零调用拒绝并终止，禁止换拼写或换包装再试。

新增case证据含`wrapper_family`、实际`wrapper_mro`、`binding_handlers_inherited`和`return_wrapper_policy_preserved`；原wrapper_type保留。精确原对象仍是原bound method的receiver，未创建新的host或代理。不把这些Python元数据证明称为原生地址/VARIANT内存实测；`null_dispatch_pointer_by_conversion_proof`的证据边界维持[原执行计划](step-null-import-data-candidate-plan.md)。

## 完全保留的约束

本次只改绑定保护helper；独立入口代码未变。仍固定原811/60f八值、同只读原件/hash/metadata、小写r、一次factory/QI/只读Map取证；实际Load第三参数为空DISPATCH，factory不是实际传参。typed只在已证DISPATCH签名用None，generic只用显式VARIANT9/None；未知签名/包装/转换在零Load停止，无路径切换或fallback。

严格参考曲线表示、12段/320mm/原长度向量与阈值不变。草图即使数值正确仍失败，几何unknown/unavailable和raw partial不丢失。原CAS、仅owned尝试写入反序恢复、首错、单owned退出/输入复核、600/1800监督不变。无Save/Open/New/Select/Export、重建、基线重放或重试。

## 交统筹亲审

仍使用原`--null-import-data-candidate`，证据父目录不变，但亲审后若决定执行，必须用**新的审阅提交完整源码快照及新的证据子目录**，不能覆盖或复用811bb97原报告。先核已安装b312源码/运行时证明；未知情况停止，不现场改class白名单或改绑定方式。

本轮不运行VM/CAD/CI，不推送。没有实际LoadFile4绑定分支或null导入结果的新证据；当前只是原包装的窄支持准备。旧811包装失败、60f草图失败和官方2025条件矛盾均保持原样，未宣称任何原生业务修复或公开验收通过。

验证结果：18项绑定测试、28项入口测试通过，相关STEP合计116项通过（5.996秒）。新覆盖原client typed/generic同receiver、原返回策略不替换、custom/多继承拒绝、继承处理函数/返回策略/获取链代码改变、receiver类或属性读取改变、未知签名/非空零Load且无回退；入口验证原值恢复、原首错与restore错误分开、未知绑定零Load，以及草图12/320仍严格失败。官方b312完整模块的dynamic/client类与三个factory函数静态自检通过，未导入pythoncom；811原件审计复跑与已提交机器记录字节一致。未重跑无信息全量便携套件或原生运行。
