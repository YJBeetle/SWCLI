# b50b603零GLB身份预检首错与只读共享候选

2026-11-12：统筹一次identity尝试已首错停止，report SHA `43fcdc2d3aac0db7a2ba5dfa79b78a1b991212ed63555ebf11e5f3bd7f686d4b`。本路独立读取原件，未重跑VM/helper/COM/GLB。[结构化审计](../evidence/glb-typed-identity-first-failure-2026-11-12.json)保留文件摘要与实际helper receipt。

实际首错为 `System.IO.IOException`，HRESULT `-2147024864`（0x80070020）：C#对自有SW仍打开的component.SLDPRT执行File.OpenRead时共享冲突。它发生在身份观察的源SHA读取，GLB SaveAs3=0；不能称存盘失败或GLB/BIN输出失败。producer的frame mismatch来自helper提前发送终止result，是后续症状；durable helper首错原件仍在。

已实际保留：PIA contract_accepted=true、三个NORMAL包各consumed一次、doc/Extension canonical IUnknown均true、foreground严格整数1。helper.before=null、identity_accepted=false；旧Observe直到全部读完才返回，C#其余局部字段没有写入receipt，不能根据读取顺序补填。Python实际exe路径为 `C:\PROGRA~1\SOLIDW~1\SOLIDW~1\SLDWORKS.exe`，但C#原始路径未保留，尚未观察到两方别名不匹配。

SW2416、实际Python worker6168、supervisor launch7988、helper8512。STL/3MF/AMF各有一次Python现代SaveAs3且文件有效；GLB现代调用0、helper trace为空、无GLB原件。helper正常exit1、helper/producer/fixture cleanup[]、marshal_cleanup_known=true，native前后清单[]，CloseDoc/ExitApp/WaitForOwnedProcess等均完整结束。源文件离线SHA仍与Python预保存SHA `092650e11ea2bc9bcdcc8c10e52b9be2e255d6684ba0fe6c00056fa0b6a64342` 一致；这不补作失败窗中C#未取得的SHA。

候选代码独立提交 `5c754ba98182279547fe899848241314667d0587`，交统筹亲审，尚未实际PIA编译/Windows运行：

- 仅源文件使用FileMode.Open、**FileAccess.Read**、FileShare.ReadWrite，不加Delete。共享策略允许与SW现有句柄共存；本句柄不能写。exe/PIA仍用原Hash/File.OpenRead策略。依据：[File.OpenRead](https://learn.microsoft.com/en-us/dotnet/api/system.io.file.openread?view=netframework-4.8.1)、[FileShare](https://learn.microsoft.com/en-us/dotnet/api/system.io.fileshare?view=netframework-4.8.1)。
- 源读取持有普通文件句柄，完整128位FileId及volume、size、creation/write/change时间与属性/links在读前后严格相同；读取后再打开原路径，须仍对应同一个持有文件及状态。未知、目录/reparse/delete-pending、截短/增长、身份/时间变化都拒绝；不通过删除共享或重试消除错误。使用[GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex)。不把读取自身可能改变的access时间用于稳定比较，也不改写或归一时间。
- 原保存前/后完整源hash、文档状态及SameSnapshot/SaveOnce门禁保持。新SourceRead evidence记录一次完整读的哈希与前/后元数据，complete=false时不冒充通过；源文件身份读取与exe物理身份方案分开，后者仍待审。
- Observe用带类型且仅包含已获取字段的observations保留raw路径/标量和失败字段；完整before/after仍只在全部读取成功后赋值。不会用默认0/false回填未知字段，也不把observation.complete当identity_accepted。
- Python仅对同nonce、合法无role的提前result保留helper首错/HRESULT并终止，不将它当identity ACK；提前success result同样拒绝。NORMAL消费ACK未知仍unknown，不重发/重连/回退。离线报告可从durable首错取失败统计，成功门禁不放宽。

本机Python23项、C#5整份候选对命名污染替身编译0警告0错误、70条纯断言通过，覆盖只读句柄不可写、文件状态/替换/长度拒绝、部分Observe序列化、提前result与ACK未知。Windows的共享行为、PInvoke和此新候选的实际PIA/COM仍未验证；没有新原生成功结论，也不自动再跑identity或invoke。
