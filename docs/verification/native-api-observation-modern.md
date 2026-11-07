# Native API观察入口迁移（尚待2025原生验证）

基线 `2d83afdc6c5c56b1a72157a84d54ee15cde770ab`，独立分支
`codex/native-api-observation-modern`。不新增功能或旧版本兼容，不切换配置、不回退弃用接口。

## 配置观察

[官方2025弃用声明](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~GetActiveConfiguration.html)
指向[ConfigurationManager.ActiveConfiguration只读属性](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IConfigurationManager~ActiveConfiguration.html)。
共享helper只取当前对象Name，保留原字符串；对象缺失、空/全空白/非字符串拒绝。
仅工程图结构观察显式允许无配置。metadata状态及STL前/后/finally仍沿原调用点
比较配置、stamp、identity、readonly及foreground，不增加配置激活或异常后的其他COM绑定重试。
现有dimensions已经使用现代入口，尺寸迁移将继续复用其严格配置检查。

活跃fixture与line-font trace observation白名单随本版迁移为ConfigurationManager、
ActiveConfiguration、Name；getter/setter和几何计数不放宽。历史原件及原有audit输出不改写，
历史trace审阅须使用其来源提交对应的审计器，不能用本版白名单改造旧报告或翻绿。

## 验证边界

便携Mock不是2025COM校准。关联+完整portable、SDK、安装资源检查完成后记录精确提交和日志。
待统筹与SaveAs3线程协调最终精确组合head的一次full/gate，避免重复安装。
已有full `42369257219` 不变更、不重复dispatch。发布仍需用户最终确认。
