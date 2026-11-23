# 私有完整readonly census最小外层

当前新branch以31ad9c2为底，不改main或公共routes。现代配置窄修先单独提交 `c5e353eb4f43346de3931807a9ee89723364e8cf`，ConfigurationManager.ActiveConfiguration.Name与旧API触发即失败测试保留。此提交仅新增私有外层及离线边界测试；没有VM/COM/CAD/CI/打包/grant/push，原native33不重跑。

## 结构与精确来源

`run-active-assembly-target-census.py` 三角色：manager零COM守1840；supervisor零COM守600/1800并持有parent Popen；parent单一STA使用当前main acquire_resident_app(attach_existing=False)，然后当前main unit_owned_native.capture(terminate_right=False)。实际PID/创建时段/raw+OS-expanded image/samefile/file-ID证据在handle准入前持久保存；expected-host-image必须是root核准完整long path且与pinned EXE同一文件。工厂的GetActiveObject仅是既有实例准入检查，不用于observer重取或fallback。

只按函数粒度复用b2e7e4b的atomic_json/failure/Journal/readonly_open/pending_calls/budget及snapshot/mirror/Python identity和held exit基础；原Git blob与每个原符号/候选符号SHA和窄适配说明见 `assembly-mates-active-census-adapter-provenance-2026-11-15.json`。未导入旧mate公共模块/旧observer/runtime，未整份覆盖源。所有新运行路径在本候选源码清单中。

## 固定行为

1. manager在任何host acquisition前verify_candidate与expected image samefile/SHA校验，独立monotonic预算覆盖前置阶段；只创建已验证sys.executable的supervisor Popen。supervisor同样预检并设置guest group_started，再创建唯一parent Popen，记录并核其OS PID/creation/image/SHA。三个角色都无实例/模式重试。
2. parent只固定复制已审ZIP里的三个条目到新C:/Workspace子目录，哈希即核并设filesystem readonly，拒绝ZIP重复/越界名；仅readonly独立PRT→ASM各一次GetOpenDocSpec/OpenDoc7，逐typed flags/Error/Warning0或2留原件。完整catalog与ASM/ActiveDoc native身份、同Python/thread/STA、owned PID/handle后，仅直接调用新reader.run一次，零child observer/ROT再取/marshal/Activate/Select/Save/CreateMate。
3. Journal覆盖准备/获取/打开/身份/reader-stage/cleanup/COM释放；nested trace按path/request/sequence/stage/call配对，完整newline前不承认terminal。先读取全部pending与completed快照，再采now并存实际budget_sample；严格未知/future/NaN/bool拒绝，不加容差。已完成但轮询间跨600秒的span亦拒绝，终态重新核完整trace，不能在end后漏过600预算。
4. 600/native及1800/group保持；group deadline或stop在下一个CAD call前拒绝。supervisor超时只terminate自己Popen的exact Python，不kill CAD；manager1840还可持有经PID/image/SHA/creation核准的parent Python OS handle，至多一次停止它和自己创建的supervisor。1840仅外层传输/报告封顶，不给CAD加40秒。组耗尽没有额外等待或新ExitApp，未知host原code保留None。
5. 正常、明确owned且无uncertainty时ExitApp至多一次，OS等待最多剩余组预算；仅signaled后读GetExitCodeProcess，strict int0才支持正常清理。非零/未知/bool不补0，不以native[]或Python0发明SW0。所有part/ASM/target/app/异常traceback原生引用在CoUninitialize前清空并GC；报告I/O失败仍必要COM release恰好一次。原business首错、trace/report/file次错、cleanup和rawcode分开保存。
6. supervisor异步mirror run目录到独立artifact，最终source+逐fileSHA transfer-receipt。manager另存run兄弟`<run-name>-manager`原件并异步mirror到artifact/manager，以manager-transfer-receipt逐项校验；deadline/copy失败不称已持久化或成功。resource_released各层固定false，root仍独立核held exit/nativeafter/idle和释放窗口。

## 待root亲审的执行形态（不是执行许可）

```powershell
& <pinned-python3147.exe> -B scripts/diagnostics/run-active-assembly-target-census.py --role manager --ticket <root-new-ticket> --run-root C:\Workspace\<ticket>\run --artifact-dir <new-persistent-hostartifact-path> --source-manifest docs/verification/assembly-mates-active-census-inputs-2026-11-15.json --source-manifest-sha a67792386c45ca0c9eb5dc11fe2e9850f16c45c2cee04963878379a17e5ea219 --internal-zip <original-internal.zip> --public-zip <original-public.zip> --host-executable <pinned-SLDWORKS.exe> --host-type-library <beside-sldworks.tlb> --expected-host-image <OS-approved-full-long-SLDWORKS.exe>
```

manager应在root已批准的非SYSTEM、交互session1启动；adapter不切换token/session，parent在COM初始化前拒绝不符环境。

终态审计须同时要求parent/supervisor/manager成功、对应Python真实退出、strict held SW0/cleanup[]、完整515 Git source/ZIP/三文件/adapter来源、两个transfer receipt及全部逐面census trace/value/活动和后置守卫；不能仅信自述success。main已有OpenDoc6 helper、through-all整段harness、单active TraceProgress或taskkill /T没有拿来替代本适配。

## 离线验证与边界

110相关测试通过（外层22，新census/reader30，既有main58），日志 `/private/tmp/swcli-active-target-adapter-related-20261115.log`。反例覆盖同STA/owner/背景、exactPRT→ASM与warning类型、正常/业务失败/traceback代理生命周期、report/trace I/O次错不盖首错、nested/无newline尾行/clock采样顺序、已结束span600和1800/1840截止、exactPython停止且deadline无追加等待、unknown/非零/bool hostcode、当前mainfactory和terminate_right=False、readonlyZIP三副本、持久复制失败拒绝成功及manager逐file收据。新API能力/全census原生/公共句柄/CAS/写保存重开均未通过，阶段B/C仍仅设计。

完整source manifest SHA `a67792386c45ca0c9eb5dc11fe2e9850f16c45c2cee04963878379a17e5ea219`，515项最终Git源码；旧现代配置清单e21fa原字节另存。提交后逐Git blob与runtime集合核验。root亲审精确最终head后另行打包、新grant及排期，本路不执行。
