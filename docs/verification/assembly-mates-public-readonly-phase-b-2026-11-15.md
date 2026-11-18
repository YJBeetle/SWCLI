# Phase B：公共 typed handles 与完整只读 compare 候选

基线为已推送 main `d8922aa907ea66385d0f786db6114182b2074c2a`，工作分支先精确快进到该基线，不混入本机其它 lane 的 main 提交。此轮只做本地代码、反例与设计；未使用 VM/COM/CAD/CI，也未推送或合并。private native37 的 core、诊断及冻结包保持原字节；新增公共能力还没有独立原生验收，不能复用37的 PASS 声明公共通过。

## 两项公共契约

`assembly.targets.list` 要求显式 `d-` document_id、非负整数 expected_update_stamp 和两个精确实例名称（先 fixed 后 floating）；lease 可选，但已有租约时必须给出。仅支持已保存、clean、non-view-only、实际 readonly 的活动 ASM 和 readonly 外部 PRT：两实例、单配置、resolved/nonvirtual、每实例一 solid/no surface、每实例1..64个 plane/cylinder面，版本仍为 33.5.0。没有扩大37的观察政策。

`assembly.targets.validate` 要求旧 `as-` snapshot_id、1..128个唯一 `at-` target_ids、同一显式 document/stamp 和必需的 live lease。选择子集不缩小观察范围，每请求只安排一次完整新 census：所有组件、所有面各有自己的 typed roundtrip 和唯一 resolved IEntity.GetComponent；不按hash/index/近似几何替代owner，不在失败后重跑/换receiver，不发新token。结果明确 `mate_tree_compared=false`、`write_authorized=false`，是只读全目标 compare，不是写域 CAS 完成证据。

## 句柄与原子边界

新增独立 AssemblyTargetRegistry，不借 part EntityRegistry 的种类或持久引用 token。快照保留完整 plain value、原始 reference bytes、精确 ASM native 对象、每个 component/source-face/original-mapped/resolved/body 和 source-document 原生对象；只在 owning worker 同一线程使用。文档 close/reopen、新 worker、错误 session/document/snapshot/kind 都不能解析旧token；同一session再次list整批换代。16个活跃session和16384个worker生命周期issued tokens上限，随机分配最多32次碰撞尝试，失败零partial publication。

list 在完整census之前保留计划组件和source-document原生对象，census结束后及最后守卫再次核它们，防止同路径/配置/stamp的源文档关闭重开把旧face绑到新source。只有完整结果schema/语义校验、最后活动/所有source/config/stamp/pose/fixed/suppression/edit检查及最终lease复核通过后才整批publish，客户端值与registry内部快照深拷贝分离。

validate先做协议、类型、文档/lease与已知scope检查；后台、已知旧stamp/config/source/pose或错误句柄在owner或写setup前拒绝。再执行一次完整新native观察，比较完整JSON值和所有旧/新原生对象的一对一映射，逐项比较原始reference bytes；正确body/ref/hash也不能替代exact component/face/source身份。任何观察到的scope变化或新观察失败都永久retire全部已有batch；其它session也不能在值回到旧状态后复活旧token。普通错误kind/session/lease拒绝不授予权限或重试；lease在census期间到期也不得返回有效compare或publish。

## 主线接线

catalog/result schema、owning DocumentRegistry生命周期、worker handler、CLI与生成SDK均从当前主线窄接线。新operation追加到catalog末尾，保持既有SDK model类型名；MCP沿用现有execute与同一catalog，不造另一个入口。

worker在 native_api_sequence 的 CommandInProgress setter之前执行协议/lease/known-target/active/known-scope检查，handler入口再核，读取及compare最后再核活动和状态。后台错误保留core的 `AssemblyNotActive` code；原生第一异常不包装成重试成功。其它operation的sequence和暂时激活政策不变。

新契约的jsonschema依赖只在实际census校验时导入，保留源码-only `-I -S --help` bootstrap可用；既有识别不同CLI源码的frontend identity守卫未放宽。

## 原生门禁尚待主协调独立执行

下一次公共门禁必须走真实 CLI/SDK/MCP→daemon→owning worker，留原始逐request/trace：list、同scope validate、子集仍完整逐面、后台在CommandInProgress/owner前拒绝、part错误kind、其它session/document/worker、旧snapshot与close/reopen、已知ASM/source/config/stamp/pose变化，以及正确hash但native身份不一致的拒绝。对照六面source/typed resolve/owner/read次数，保留原Warning、first error、全部source输入hash、held真实退出、native前后、双层传输与资源释放证据。不得写模型、修改只读属性或把37旧许可复用为公共许可。

本地测试和来源清单结果另存同轮 inputs JSON；日志记录原始首跑环境问题与修复，不将缺依赖或旧editable路径错误称为产品通过。完整portable、SDK生成/strict类型、原始37 core/blob不变均需核定后交root亲审。

## 已完成的本地验证与交接

持久独立环境位于 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/mates-public-b-offline-20261115/test-env`，Python3.15.2，jsonschema4.26.0、PyYAML6.0.3、mypy1.20.2、setuptools84.2.1。仅把root测试依赖目录作为普通路径读取，未执行其editable .pth映射；用 `--no-cache-dir --no-deps --no-build-isolation --ignore-installed --editable .` 在新env安装当前候选，`-I` 实测cli.__file__精确指向此worktree。未修改root/旧lane环境，未安装新网络依赖。

最初 d80727e 候选的完整命令为 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src <上述env>/bin/python -B -m unittest discover -s tests`：3047项、39skip，108.609秒，真实退出0。较原3018项新增29项公共反例；57项公共/bootstrap定向回归和此前164项关联亦通过。`scripts/ci/verify-sdk-types.py` 在新env退出0：生成器一致，SDK strict通过，38条消费者类型拒绝精确通过。修改Python均按3.9语法解析，diff-check通过。

第一次完整运行保留为 `initial-portable.log`：3046项/32skip，1failure+19errors。唯一新增产品回归是契约模块顶层jsonschema导入破坏无site-package的源码-only帮助入口，已改延迟导入并用原断言复测；其它错误来自旧3.14env缺PyYAML和-I子进程正确拒绝旧editable CLI身份。中间tmp环境尝试引入系统site目录时，又碰到外部regular tests包遮蔽本仓库namespace的一项错误，该环境放弃。未改这些身份、源码-only或测试断言来消除错误。最终完整通过使用上面独立、无系统site目录的持久env。

最初520项清单及当时六份源码不变证明已原字节归档为 inputs-d80727e-original；最终526项清单、两项测试例外、原包15项冻结不变证明和最终日志SHA见更新后的同轮 inputs JSON。原始日志在 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/mates-public-b-offline-20261115`，不是native证据。

main `9f4a2d1` 的 Windows readonly unlink 测试准备修复已按协调要求 cherry-pick 为 `fdea8fa`；后续 `28d5f2c` 只收束两个 deadline 测试的镜像线程。生产观察 core/reader/adapter 原字节不变，详情及最终门禁边界见 [2026-11-19 离线门禁说明](assembly-mates-public-readonly-gate-2026-11-19.md)。
