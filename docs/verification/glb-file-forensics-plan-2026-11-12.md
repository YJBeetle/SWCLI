# 顶层副本文件三渠道零CAD取证候选

仅交静态源码/测试/方案，未执行新Windows/VM/CAD；另有独立的固定缓存PIA只读元数据工作，不是本工具的Windows取证执行。原6a25a56失败记录及其审计输出不改，原stable_file、geometry/CAS/readonly/owned identity门禁源码保持。该工具与诊断主流程独立，没有接入OpenDoc7、任何导出、resolve/rebuild、任意command hook或自动重试；运行仍须统筹安排零CAD资源。

## 已有事实与源码语义

已有probe的Mac11份原件不变、10副本SHA不变，仅顶层Python held渠道ctime前后改变。[旧记录离线分析](../evidence/glb-existing-file-channel-analysis-2026-11-12.json)确认path ctime在前后均等于birthtime，held ctime改变；没有历史Win32 Basic/Standard/ID快照，不能补填其值或据此确定是谁做了什么操作。

精确版本[CPython v3.14.7 win32_xstat](https://github.com/python/cpython/blob/v3.14.7/Modules/posixmodule.c#L2290)在路径stat后用birthtime填ctime；同版[fileutils.c](https://github.com/python/cpython/blob/v3.14.7/Python/fileutils.c#L1105)把Win32 CreationTime和ChangeTime分别填入birthtime和ctime，[_Py_fstat_noraise](https://github.com/python/cpython/blob/v3.14.7/Python/fileutils.c#L1233)直接使用该映射，fstat不走路径覆盖步骤。源码依据解释了两渠道可能含不同语义，不证明每个运行二进制、文件系统或缓存行为都已实测。Python3.14滚动文档目前可能是较新补丁版，本方案不把它代替3.14.7源码。

微软[FILE_BASIC_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info)区分ChangeTime的元数据语义与LastWriteTime的数据流语义。改变ctime不能直接等同内容写入；同样，前后SHA相同不能排除中间写入后恢复，也不能解释元数据变化原因。本方案不接受容差、不归一化或换成birthtime，不关闭/伪造访问时间更新，更不改现有CAS。

## 字段与同一文件

[源码](../../scripts/diagnostics/markingjig/file_forensics.py)只在明确Windows CPython3.14.7/64位参数下绑定kernel32。输入限固定SHA的`C:\Workspace`顶层MarkingJig.REND.SLDASM普通只读独立副本，拒绝reparse/symlink、硬链接、ADS/UNC/设备路径。新输出为私有JSON，不改源文件。

| 渠道 | 保留字段 | 绑定与限制 |
| --- | --- | --- |
| Python pathname | dev/ino/mode/size、atime/mtime/ctime/birthtime_ns、attrs/reparse_tag/nlink | os.stat(follow_symlinks=False)，原值不改 |
| Python held fd | 同上 | 同一个从只读Win32句柄转交的CRT fd，所有前后字段严格比较 |
| Win32 | Basic、Standard、FileID全部下列字段 | 同一held OS HANDLE加独立pathname重开HANDLE；前后完整卷+128位ID必须一致 |

[Basic](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info)：CreationTime、LastAccessTime、LastWriteTime、ChangeTime（原始signed100ns FILETIME ticks，1601 UTC epoch）、FileAttributes。没有转成Unix ns来凑相等。Python `*_ns`和Win32 ticks各保留自身单位，说明不充当转换器。

[Standard](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info)：AllocationSize、EndOfFile、NumberOfLinks、DeletePending、Directory。AllocationSize不硬假设等于或大于EOF（压缩/稀疏有不同语义），仍保留并严格比较其前后值；EOF/links/attrs与Python对应字段逐字比较。

[FileID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)：64位VolumeSerialNumber及完整16字节FileId128原始hex，不截低64位、不删前导0。held与pathname重开、每组native读取前后ID均须匹配；另按CPython该版本的128位整数布局核Pythondev/ino，失败不回退旧ID/API。原始打开路径用FILE_NAME_OPENED保留，不通过字符串大小写/8.3/路径归一化宣称同一文件。

使用[GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex)的0/1/18类。CreateFileW只请求GENERIC_READ、READ|WRITE共享、不共享DELETE、OPEN_EXISTING、OPEN_REPARSE_POINT；不请求任何写入、创建、删除权限。CRT接管成功后只由fd close一次，转交失败保留首错及独立CloseHandle错误。

## 固定时序与判读边界

只做两组固定快照，夹一遍有界SHA读取。每组依次记录Pythonpath、held fstat、Win32 held的ID→Basic→Standard→打开路径→ID，再独立重开pathname核相同native信息并关闭。逐次记录wall Unix ns与monotonic ns的调用起止/错误时刻；不是原子快照，不掩盖跨调用变化。不睡眠、不等待外部CAD、不启动子进程。

所有时间和其他字段前后变化（包括一单位ctime/access time）均留原始差异，并拒绝把它视为稳定窗口，绝不解释为已证明内容写入。完整SHA、大小、EOF、普通文件/只读/链接数/全部物理ID亦保持严格；任何失败保留部分字段并停止后续业务读取，只关闭本工具拥有的句柄，清理错误与首错分开。读取本身可能使系统更新访问时间；它也原样记录，不调用SetFileTime等写操作消除观察效应。

这是独立取证，`complete`只指该有界读取契约完成，不是新的模型/CAS准入或GLB验收，不能拿其跨渠道ctime差异记录绕过原stable_file。同一held渠道变化仍被拒绝。已完成的旧probe缺少Win32原始前后值；本工具即使未来运行，也只能得到当时新窗口，不能重建旧事件原因。未来若需与CAD动作配对，须另行审阅和授权；本工具目前没有该能力。

## 静态验证与交审

20项假后端/便携负例及Win64 ABI大小/offset测试通过：完整ID/卷错配、字段缺失、readonly/link/reparse、目录/delete pending/size、1单位各类时间变化、截断/增长、部分native读取失败、源SHA不符、第一次错误与句柄关闭错误分离。Ctypes结构为固定宽度，Basic40B、Standard24B、ID24B，避免宿主c_ulong宽度差异。真实Win32调用/句柄转交/错误码和该私有副本当前三渠道值尚未执行验证，不能以替身测试冒充。

[旧记录分析器](../../scripts/diagnostics/markingjig/summarize_file_probe.py)已只读重放保存的JSON，不改旧report或模型；[准备证据](../evidence/glb-file-forensics-preparation-2026-11-12.json)记录源码tag/SHA、工具摘要与边界。运行命令形状供审阅：`file_forensics.py --path <批准的C:\Workspace顶层副本> --sha256 <固定80bfa9d4...> --output <新的私有.json>`，不是本轮执行安排。
