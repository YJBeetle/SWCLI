# 单次零CAD文件三渠道实际取证

VM-20261112-MARKINGJIG-OS-FORENSICS-01按统筹明确批准执行。审阅代码固定`2a0d52a25d52072f56d4a78503d489e431db5c8a`，file_forensics.py SHA `ef1fc427b36f8fcbd05972515db8580cc1c50e8447e444941c6fd1fda86e07c5`，独立C:\Workspace代码副本执行前后均匹配。目标仅为既有私有顶层只读副本，固定SHA80bfa9d4…308530，新普通JSON输出，不接触Mac业务原件或其他输入。

只读GENERIC_READ/share0瞬时占用预检成功、己方句柄已关闭；这说明该瞬间无冲突的data read/write/delete共享句柄，不是全局监控，也不证明绝无metadata-only活动。Windows SW进程前后均[]，未创建/连接COM、SW、文档、probe/invoke或导出，未修改属性、时间setter或idle配置。前后VM均running、idle pause on。配额交还统筹，不自动扩大/重跑。

工具实际执行一次，PID8252、正常exit1。两组快照均含Pythonpathname、同一held fd与Win32 held/独立pathname重开数据，完整卷+128位FileID均相同；所有47个已记录操作正常返回，第一次业务失败发生在最后严格同渠道稳定性比较，而非Windows API失败。first_error原文`source metadata changed; not inferred to be a content write`，complete=false，不是稳定窗口通过或CAD/GLB验收。

| 同渠道唯一变化 | before原值 | after原值 |
| --- | --- | --- |
| Python path/held st_atime_ns（Unix ns） | 1794498162053725000 | 1794498162643992600 |
| Win32 held/reopen LastAccessTime（1601 FILETIME100ns） | 134389717620537250 | 134389717626439926 |

其余记录字段均保持：两组CreationTime=134389581613139165、LastWriteTime=134389581613139165、ChangeTime=134389581835706297（原始FILETIME ticks）；Python path ctime/birthtime=1794484561313916500、held ctime=1794484583570629700（原始Unix ns）。上述不同epoch/单位未换算、归一化、设容差或替换。当前观察与已核CPython源码的字段语义一致；不能反推旧OpenDoc7时间窗里的Win32快照或确定其元数据变化触发者。

VolumeSerialNumber=4217245827768940497，完整FileID字节hex `6057020000000a000000000000000000`，Pythonino=2814749767260000，原始打开路径保留。attrs33、links1、delete/directory0、EOF924679、allocation925696均保持；读取924679B SHA仍为`80bfa9d4bc453277dc0ba4dd9dbdf8f0d315a090aa3bab429843b1f9bc308530`，launcher输入前后hash亦相同。访问时间变化与读取相容，但没有完整文件访问追踪，不独断触发者；相同SHA也不证明不存在中间写入后恢复。旧probe跨OpenDoc7的held ctime变化仍未解释，不据本结果放宽CAS或时间门禁。

before/after两个pathname重开句柄及held句柄各close正常，工具cleanup_errors=[]；占用预检句柄关闭正常，launcher cleanup_errors=[]，自有metadata进程已退出，无超时/强杀。未关闭任何用户SW进程。工具未调用WriteFile/SetFileTime/属性setter，OS访问时间变化原样记录且严格拒绝，不为获得通过而改代码或再运行。

首次直接prlctl入口返回255/`PrlJob_GetResult: Invalid argument`且无阶段输出。随后仅OS状态核查确认必需C工作目录/输出不存在、无Python残留，故工具尚未执行；改用已确认可用的encoded PowerShell/H入口完成第一次工具执行，审阅代码及参数不变。首次通道错误原stdout/stderr保留，工具exit1/局部稳定性错误另列。中间一条未encoded状态查询的引号错误不作为结论，保存的encoded核查才作为零工具执行证据。没有在工具失败后重新运行。

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261112/markingjig-os-forensics-2a0d52a-01`。metadata.json SHA `a6f9a1886bef4490d7946a766d02572ec5f1ff8dc3e6a56de846e0cf5d0d3c80`；[结构化审计](../evidence/glb-os-forensics-native-audit-2026-11-12.json)由[纯离线脚本](audit-glb-os-forensics-2a0d52a.py)重放。evidence_audit_passed仅指原件/边界可复核，tool_stable_window_passed仍false。warning2窄模型准入依旧只有静态/便携准备，未再次CAD验证，原6a25a56失败audit不改。
