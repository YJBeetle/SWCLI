# 当前Docker缓存的GLB来源线索

2026-11-12只读核当前workspaceroot root Podman缓存，来源head `7af1d01cb30c9ac358e3b87eac13050fc1ac6f78`。用户已撤销Docker全局占用锁，允许各路自建隔离环境；Windows VM仍须统筹分配。本次不复用WR-01窗口，不修改调度登记，不操作现有容器/daemon，不执行Wine、SOLIDWORKS、SWCLI或业务模型。

| 当前本地缓存tag | 镜像创建时间UTC | SWCLI源码版本 | Wine DEB/版本文件 | SOLIDWORKS静态文件版本 | 导出源码API |
| --- | --- | --- | --- | --- | --- |
| latest-zh-cn-cli | 2026-09-30 22:14 | 0.1.0a2 | 11.16~jammy-1 / 11.16 | 33.5.0.53 | IModelDoc2.SaveAs3，三参 |
| 2025-zh-cn-cli | 2026-10-30 04:29 | 0.1.0a13 | 11.16~jammy-1 / 11.16 | 33.5.0.53 | IModelDoc2.SaveAs3，三参 |

精确ID、缓存manifest digest、RepoDigests、文件SHA、旧调用源码行及证据SHA见[结构化回执](../evidence/glb-current-docker-cache-2026-11-12.json)。latest缓存ID `7823979a9862730bdc765113b1e751d366d9557787cd2bbdb350f22f608db926`，manifest `sha256:5b8068195179e7c95bc4cc15de31ab40bfdf9e468a66579ab828561fad7cb28b`。2025缓存ID `377e9edd59f86333740cc1e3b049d546997b826907b5ce9851b571ebc205ecab`，manifest `sha256:2a1ef42d6c7e908185ab895dd71ae138cf3fc22a90db36f3940b0be77d9d71a0`。未查询registry、拉取、更新、安装或晋升；RepoDigests仅列本地关联记录，不自行解释为最新远端/index身份。

两者SLDWORKS.exe均712576B、SHA `911309f7494e806f22914bab40aa65531c01b45888ec482ac555fbd8b4f0a18b`；静态版本来自对齐VS_VERSION_INFO/FIXEDFILEINFO签名读取，未装载执行EXE，不等同COM RevisionNumber运行观察。SWCLI版本来自源码`__version__`；导出模块分别SHA `3b432ab28134472b0e1eec04d09666a0fe51de67a1eb6c3dbcd6500e50385850`与`b96d94aab16d01dbcce90b3f3a33d322e5f6ce4c3fe079b474be848b58cb9060`，749/810行均为`document.SaveAs3(str(export_path),0,1)`。这只是缓存源码路径，与现代Extension七参候选存在差异，不授权执行旧保存或把它当失败回退。

取证只输出白名单镜像/进程字段及静态版本/源码行。先记录首次Podman `.Id`模板不支持错误并修正为`.ID`；第一次两个Python容器未附stdin，仅EOF退出0且无metadata，不能当验证成功，原回执保留。随后加`-i`和预期metadata标记校验，才取得文件结果。共6个自建容器（2个空输入、2个版本读取、2个源码读取），均固定image ID、--pull=never、无网络、只读根文件系统、去capability、覆盖入口为Linux Python；未启动原入口预热或Wine。每个exit0并单独确认已删除，其他容器/文件不动；运行前/版本读取后未观察到原生进程名匹配。完整原输出及采集脚本位于结构化回执的artifact路径。

不能据此补填MarkingJig历史生成时digest、SWCLI/Wine版本或实际API。用户确认DockerSW latest的事实继续保留；缓存老tag不保证registry新tag，二者也没有关联到该历史job。相同SW EXE不代表其余DLL、状态、配置或宿主相同，不能单独归因版本、旧/现代API或doctype。MarkingJig现代Windows候选的36项便携测试、原生引用未知和零保存停止边界保持，未静默移植为Wine支持，未申请/使用Windows VM。
