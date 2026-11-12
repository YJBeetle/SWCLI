# 预期只读warning2的窄诊断候选

只准备源码/测试供亲审，尚未执行新CAD或重新probe。原e3d9bd9 probe及6a25a56失败审计原样保留；不能把本候选解释为旧probe通过，原held渠道ctime窗口失败也仍独立存在。

2025[官方枚举](https://help.solidworks.com/2025/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swFileLoadWarning_e.html)将ReadOnly定义为2。新诊断额外要求装机swconst中`swFileLoadWarning_ReadOnly`为严格int2，缺失、bool或不同值在OpenDoc7前拒绝，并将本次读取的实际诊断枚举写入case。当前Windows VM归档只有sldworks PIA，未找到其swconst PIA/TLB原件；另按既有只读Docker授权采集了固定旧缓存安装PIA，实读值2，不能将缓存当VM原件、registry当前latest或MarkingJig历史生成环境。已准备[离线PIA检查器](../../scripts/diagnostics/markingjig/enum_metadata/Program.cs)，要求明确文件名、批准SHA及正确swconst程序集/enum/literal/int32形状，只读GetRawConstantValue，无COM创建或目标方法执行。本机.NET6/C#5编译零警告错误，错误PIA负例拒绝；固定缓存真实swconst正例返回System.Int32的2，版本33.5.0.53、PIA SHA `1afe845af233292fe22e58a2b893d6065f36cd85f2728866011ad10771b98fa9`。缓存image ID `377e9edd59f86333740cc1e3b049d546997b826907b5ce9851b571ebc205ecab`，新建无网络只读元数据容器已确认删除，没有执行Wine/CAD或拉取镜像。Windows VM的swconst身份仍未补核。未来实际候选仍由原装机TLB读取器强制核值，不跳过该条件。

warning0保持原路径。唯一允许的非零值是精确2：Error必须是int0，原临时ReadOnly setter/readback必须true，doc非空；2与任意其他位混合、未知/负数/类型错误及任意非零error都拒绝。只有已识别的预期2才继续读取实际`IsOpenedReadOnly is True`、`GetSaveFlag is False`、`IsOpenedViewOnly is False`三项严格bool，逐值保留，未知即停；此时只标记provisional，不称完整打开/源状态准入通过。

随后原copy.unchanged、owned身份、top readonly/clean/view-only/rebuild、配置/编辑、initial resolved完整组件/依赖/几何、原before/after比较及一次SaveAs3门禁全部保持。没有新容限、位掩码宽放、ctime忽略、自动repair/resolve/rebuild、旧API或失败重试。错误/warning未知时不追加这些CAD读取，仅保留原清理；该候选不自动获得probe或invoke授权。

45项MarkingJig便携正反测试通过，含精确2+clean正例、混合位/未知error/未知enum/脏或view-only模型/原rebuild拒绝，以及已知2也不能绕过copy held-ctime失败。相关typed桥接23项保持。本机测试不是新Windows实际readonly语义或GLB验收。原失败report SHA仍为`a729e16e746a8bac64ea6e51d45df9074d1de68002129f36d04b87d30d0cb42f`。

actual-model三项bool方法另对已归档装机sldworks PIA静态C#5编译零警告/错误，目标方法未执行；具体源、摘要和缓存安装枚举来源见[准备证据](../evidence/glb-readonly-warning-preparation-2026-11-12.json)。
