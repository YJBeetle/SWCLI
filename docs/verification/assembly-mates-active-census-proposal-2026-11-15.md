# 完整活动ASM readonly census执行提议

未运行VM/COM/CAD/CI、未打包/创建grant/push。root亲审最终head、完整source manifest与自身parent/supervisor对接后才可分配一次编号独占窗口。观察入口不获取/attach/初始化COM或管理资源，不能单独启动；不复用旧诊断分支runtime或旧manifest。当前main基线31ad9c2。

固定输入：`assembly-mates-active-census-inputs-2026-11-15.json` SHA `e21fa957d3d5cfbb2a3d1f9ee308cbb2ba3144964d02590a577e48f61f0549c3`、完整`513`项Git source；内部ZIP5d5a…95c7、公开失败ZIP5663…acee及三文件完整SHA见manifest。保留Python3.14.7 EXE4942…ac9、pywin312/jsonschema4.26.0、SW33.5.0 EXE9113…a18b/旁置TLB585e…1159。旧ZIP是原件/样件来源，不当作当前主线产品包；当前源码必须来自最终新commit。

1. root在CAD acquisition前核完整Git blob/path set、解释器/依赖、两ZIP/EXE/TLB原件，建立新隔离readonly三副本和持久hostartifact输出，确认独占/外部占用和精确root-owned进程政策。先调用下面verify_candidate；root自身以OS handle/image/creation/hash证明实际新宿主身份，无不明确attach。
2. root parent在同一owned STA预定自然readonly OpenDoc7两次：独立concentric PRT先、coincident ASM后。依旧保留真实flags/Error/Warning0或2和三catalog的clean/readonly/non-view-only/路径；ASM不自然活动即停。零ActivateDoc/Select/修引用/补开，不在33或其它失败case后切换重试。
3. root仅在该已拥有app上调用一次新reader `run`。options字段为 fixture_dir、expected_pid、source_manifest、source_manifest_sha、internal_zip、public_zip、host_executable、host_type_library；report预置唯一request_id。reader先复核source/环境与文件/census preflight，再一个native_api_sequence中执行完整targets；首错后无CAD业务后读或下一面，只文件审计和既有请求状态恢复。

```python
# module由root从新commit的scripts/diagnostics文件绝对路径加载；不是COM attach入口。
reader.verify_candidate(options)  # acquisition前，无COM导入
# root单次完成owned parent与两次预定自然打开后：
reader.run(app, options, report)  # 同parent owning STA；无child/ROT/ActivateDoc
```

4. 预置`SWCLI_TRACE_NATIVE_CALLS=1`。reader的request operation为`diagnostic-only.assembly.active-target-census`。每组件每面stage为`assembly-targets.component[i].face[j]`，按初始完整source/component count建立唯一计划，1..64面/组件；拒绝缺面、重复映射、reference歧义或unsupported surface，不能只跑先前首面。实际样件面数本轮没有CAD观察，不编造固定数。
5. 独立原件审计必须要求：两组件完整count、每个组件source_face_count==component_face_count==len(faces)，总face_count匹配且所有binding对应唯一native映射；每面map/capture/typed resolve/getter/exact-owner-IsSame各一次完整begin/end，getter前两次活动身份守卫完成，无多余面/调用/其它receiver；每面非空owner与精确组件IsSame由已审代码严格执行。所有成功后置和files_unchanged、root真实held host code0/cleanup[]/nativeafter[]与idle恢复均需原件。native trace不包含底层Invoke实参，不冒称直接观测其数值；严格typed状态来自已审接口解包及成功返回值验证。
6. root external supervisor原600秒native/1800秒组限和先读取pending后采clock保持，不因新完整census增加预算；原begin/error及first business error、cleanup与文件I/O次错分开持久保存。超时只停止精确拥有Python，不按名字kill CAD；身份不明/未知退出码保留现场交root。readonly native31失败和33有限成功不改写。
7. 成功只称该保存readonly样件的全目标census通过，不发公共token，不运行旧句柄/CAS、CreateMate/Save或产品公共验收；失败则原首错停止，不换API/receiver/上下文。公共前台契约/typed句柄/CAS/写/save-reopen仍按阶段另审。

本reader没有parent/supervisor实现，也不声称自身enforce600/1800或释放host；root必须审其持有的外部执行层并单独冻结该层来源。后续任何新增执行适配代码也须再入最终可审来源，不将未审root adapter隐含进本manifest。只读结果的resource_released固定false，实际资源释放由root的held process原件另证。
