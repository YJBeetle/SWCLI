# GLB exporter collector 的 stat／fstat 原件与窄比较候选

2026-11-11。统筹仅运行一次 `17deb54629245a87ecbeb043cbc25a1631514132` collector，失败后未重试。本路只读核对原件、官方 v3.14.7 源码并准备候选，没有运行 collector、VM、CI 或 push。当前不是 exporter 文件元数据或 GLB 原生验收通过。

## 首轮失败保持原样

原件根：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/glb-exporter-inventory-17deb54-01`。
report SHA-256：`b9d35e64823d84d424be9045658cc81fd491b7d11fa2fd0912f3bd62b4e8fb24`。

collector 自身指纹读取通过，首 DLL `sldgltfu.dll` 的 presence_before 为 regular/non-reparse，size 1112960，随后 `stable_read` 在 path stat 与 opened fstat 的相等比较处抛出 `input changed between path stat and open`。它没有落盘该次 stable_read 的 first／opened 原值，不能事后补填这些未知值，也不能仅按错误文案断言原文件改变。

`metadata_attempted` 未到达、没有 metadata request／response 或辅助 stderr；辅助进程未启动，缺失这些文件不是新故障。launcher-context 记录 PowerShell 语法预检 exit=0，五个 policy scope 均 Undefined；RemoteSigned 仅在统筹已审阅 child environment，全局策略未改。辅助脚本实际版本／CMS 路径仍未执行。

## 后续独立 probe 的实际字段

另一个零 CAD probe 原件为 `glb-stat-probe-17deb54-01/observation.json`，SHA-256：`f22def2a220b20000384930fa76ffc50b6199f7abc0d0cb575a7f5b5764d4511`。源脚本 SHA-256：`a395430034f98e71293ab135364749a5974895043e8a18586b2c7372e03522db`。

| 字段 | path before／while-open／after | fstat opened／opened-again |
| --- | ---: | ---: |
| st_ctime_ns | 1758898084000000000 | 1780227286818338600 |
| st_birthtime_ns | 1758898084000000000 | 1758898084000000000 |

其余观测的 dev、file ID、mode、size、mtime、attributes、reparse tag、link count 均相同。三个 path 结果严格一致，两个 fstat 结果严格一致。大整数从原始 JSON 经 Python 读取和比较，没有转为浮点。

probe 对目标 DLL 没有内容读取、没有目标装载或 CAD 调用；它确实读取自身脚本以算 hash。`file_reads=0` 只能按目标内容读取计数解读，不能说所有文件零读取。这份后续 probe 与首次失败是不同观察，不回填首次缺失的 opened 值。

## 适用版本的官方实现

独立重新下载官方 v3.14.7 文件并核字节，与统筹原件哈希完全一致：

| 文件 | SHA-256 | 相关路径 |
| --- | --- | --- |
| Python/fileutils.c | `7141679d2d4d1ac7faa9f17b4fa3596e042bbd4d32bbab659bb5336c24b79d95` | `_Py_attribute_data_to_stat`、`_Py_fstat_noraise` |
| Modules/posixmodule.c | `436636d1ef1693d58e07cf80fc4aea58ad740e5d2e6b2f466164f66be5f8d43d` | `FSTAT`、`os_fstat_impl`、`win32_xstat` |

[v3.14.7 fileutils.c](https://github.com/python/cpython/blob/v3.14.7/Python/fileutils.c#L1107) 将 CreationTime 存为 birthtime、ChangeTime 存为 ctime；`_Py_fstat_noraise` 返回该结果。[同版 posixmodule.c](https://github.com/python/cpython/blob/v3.14.7/Modules/posixmodule.c#L402) 的 Windows FSTAT 直接指向它，`os_fstat_impl` 不重写时间；而 [win32_xstat](https://github.com/python/cpython/blob/v3.14.7/Modules/posixmodule.c#L2297) 为兼容将 path ctime 覆为 birthtime。

这与上述实际 probe 匹配。[Python 文档](https://docs.python.org/3.14/library/os.html#os.stat_result.st_ctime_ns) 的 Windows ctime 弃用说明提供语义背景；当前文档可能随 3.14 补丁更新，不替代固定 3.14.7 源码。[issue 157671](https://github.com/python/cpython/issues/157671) 仅作线索，不作为唯一判因依据。

因此该 runtime 的跨渠道 ctime 不能直接要求数值相等；不是一般时间误差或文件变化容差，也与 GLB 空 BIN 的根因分开。

## 本地候选的比较规则

完整投影仍相等时继续严格接受。只有下列条件**全部**满足，才允许 ctime_ns 这一项跨渠道不相等：

- 当前进程自读 os.name=nt、sys.platform=win32、implementation=cpython、version_info 精确 `[3,14,7,"final",0]`、64-bit；没有 CLI override。
- 原比较投影及新增 birthtime／link count／reparse tag 仅 ctime_ns 不同，所有原可比字段仍为精确整数并相等。
- 双方 birthtime_ns 可用、为相同正整数，且 path ctime_ns 正好等于该 birthtime；不改写 handle ctime。
- dev/file ID 为正且一致；mode、size、mtime、真实可读 attributes 严格一致，双方均 regular/non-reparse；link count 可读且相同为正，reparse tag 均为 0。

未知 runtime、缺失／非整数／零 birthtime、birthtime 不一致、path ctime 不符合该语义或任何其他差异继续拒绝。没有时间容差、四舍五入、删原字段、改值归一或备用身份判断。

读取期间 path→path、fstat→fstat 都比较完整同渠道投影，ctime 仍严格相等，另严格比较可得 birthtime／link count／reparse tag。返回指纹保留原 path stat、birthtime_ns 和 handle_stat；整个辅助元数据采集前后也因此严格比较 handle ChangeTime，即使内容 hash 与 path stat 未变也不放行。原文件 hash、原父目录身份检查、固定输入、读取边界、PS 参数与辅助代码均保持。

## observer 先记录再拒绝

每次 `recorded_read` 在 report 或 file row 的 `stable_reads` 内先挂上观察对象，再进入原 I/O。获得 parent／before／opened／after_handle／after_path 后先记录 raw_fields、comparison_fields、不可用字段和读取错误，再执行对应 guard。保存最后阶段、比较差异、规则／runtime／每项前置条件、原异常与 descriptor_closed；未到阶段的 stat 不伪造。

原 `st_ctime`／`st_ctime_ns`／birthtime 全值保留。comparison_fields 是显式比较投影，raw_fields 不补默认值；例如字段缺席写进 unavailable_fields。异常仍按原类型和消息抛出。observer 不添加 stat、fstat 或内容读取，成功数据／hash 不变，父目录比较 tuple 不变。

## 验证与边界

24 项离线测试通过（原 17 项加 7 组相关测试）。新增使用上述实际原始数值的正例、完整合成读取、未知 runtime／缺 birthtime／其他差异拒绝、同渠道 ctime／birthtime／link／tag 变化、first DLL 失败原值 JSON 落盘、跨整个 metadata 阶段的 handle ctime 变化拒绝，以及 observer 不新增文件 I/O 的对照。

另外离线把同一组 primitive stat 数值代入未修改的 17deb 逻辑，复现其跨渠道相等检查拒绝，未读取真实 DLL 内容。代码和测试只在本机合成文件上运行；当前候选没有 Windows 原生 collector 重跑结果，不能宣称导出器文件清单已采齐或已修复 GLB。

结构化原件、源码指纹、规则与测试回执见[证据](../evidence/glb-exporter-stat-ctime-2026-11-11.json)。统筹亲审后再决定一次新的零 CAD 运行。
