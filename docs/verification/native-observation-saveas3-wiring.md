# 给现代SaveAs3负责人的组合full接线交接

来源：getter分支 `codex/native-api-observation-modern` tip e801a95；两逻辑提交
aecd560a9c0293f1a97d33d91ab400dbb2b651f9、1cdbff41a0594440eda17e068c3d42e1fb24579c。
SaveAs3只读快照：`5c102541e3040a77455d07da6ee64e66ccfe500e`。文件hash见同名JSON；不把快照描述成已组合head。
不修改SaveAs3 worktree/main，不另起native run，不用VM，不派审查代理。

## 已有接线与实际边界

| 目标 | full路径 | 覆盖/缺口 |
| --- | --- | --- |
| 零件/装配配置 | ci.yml的property_fixtures -> verify-properties-calibration.py part/assembly；hidden preflight -> verify-properties.py exercise_metadata/check_metadata | getter提交后走现代helper，metadata state/当前Name、配置自定义属性、后台身份和save/reopen均有既有检查；在exports前 |
| 直径读取 | runtime_plan continuation-front-diameter -> verify-diameter-dimensions.py -> driving_diameter.inspect_diameter -> dimension.inspect/_descriptor；随后top/right | 真正走GetSystemValue3；包括创建/发现/读回/保存重开。位于exports后，若GLB首失败则未到达 |
| 线性宽/高读取 | runtime_plan rectangle-front/top/right -> verify-rectangle-dimensions.py -> driving_rectangle -> dimension.inspect/_descriptor | 与直径共享同一严格Get3适配层，width与height各自句柄/值；同样在exports后 |
| 工程图空配置 | runtime draws -> verify-drawings.py:124、134 的结构inspect与structure_signature | 新helper allow_absent会接空配置，但当前只比较两次configuration结构相等，不能排除“两次同样错误的非空配置”；缺明确active=None/names=[]/count=0断言 |
| 2025枚举/绑定 | 现有harness read_constants只核swThisConfiguration等，不核swSpecifyConfiguration；native_trace不输出原生参数/结果payload | Get3方法trace可证明到达，不能单独证明安装TLB枚举3或原生返回容器类型；需同次full留下installed symbol/typeinfo原件 |

## 最小接线补强（供owner在组合分支实施，不改产品能力/断言）

1. 合入两getter逻辑提交时，windows_documents.py只取ConfigurationManager helper替换与导入，
   保留SaveAs3分支自己的null/BYREF/真实errors-warnings、GLB原字节及首错修复，不能整文件覆盖。
   接受新的活跃fixture/line-font trace白名单；历史原件只按原source审阅，不回写旧trace。
2. 工程图增加只读断言：在verify-drawings.py已有保存前及reopen后的**drawing**结构上要求
   configurations.active is None、configurations.names == []、configurations.count == 0。
   不把它放到兼用于part source的泛用结构函数。保留现有features/几何/状态比较，给portable假样例加非空/缺键拒绝。
   若要在已知GLB失败之前也留证，可在现有annotation DRW fixture准备内，对其已有document调用一次
   _inspect_configurations并记录/断言上述三项；不另建fixture、不再保存、不启动新host。
3. 同次full的已有官方swconst读取增加swSpecifyConfiguration符号核验（必须int且等于实现用的3），
   记录原TLB hash；仍缺失/不匹配即停止，不猜ID、不开兼容fallback。Get3当前配置名和唯一值仍由实际
   public结果+source SHA+方法trace对应核对。若要记录容器shape，只增只读诊断字段，不能在失败后再调一次Get3。
4. 进程继承SWCLI_TRACE_NATIVE_CALLS=1，以及SaveAs负责人已有的
   SWCLI_TRACE_DEFINITION_INTERFACES=1、SWCLI_PRESERVE_REJECTED_GLB=1；保存daemon stderr/log及diagnostic原件。
   definition typeinfo/IID诊断当前只针对GetDefinition既有三类对象，不能把其结果当作IDimension/ConfigurationManager的接口证明。
5. 不为收集getter额外dispatch、重试或越过首失败：完整full若通过，既有直径/矩形组自然覆盖；
   若仍先停GLB，必须把这些组标未到达。若统筹要求本次先覆盖getter，只调整同一full内既有完整组顺序，
   保留continuation-front-diameter两步的宿主连续性与原断言；不复制组、不第二次运行失败组。
   不在本路擅改runtime_plan，是否重排由组合owner/统筹决定。

## 组合检查清单与收口

组合精确source SHA落盘，关联+完整portable/SDK/统一CI路由后只派发一次该head的native_full。
前后config、stamp、foreground保护与原几何断言均不放宽。默认新造尺寸样件通常仅当前配置，
不能据此外推多配置异值覆盖；若本次原件没有两配置样例，按实际已测子集交接。
600秒native/1800秒组、首次失败停止；无API重试/自动回滚/组内重启。
本路没有另派CI。旧run42369257219只保留其原source事实，不追认到组合head。
