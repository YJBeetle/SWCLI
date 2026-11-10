# 装机interop零CAD检查工具（2026-11-11）

入口为 `scripts/ci/inspect-installed-interop-contract.py`，仅启动同目录的 `inspect-installed-interop-metadata.ps1` 读取装机程序集元数据。原生产代码、getter夹具和CI均未修改；没有实现C#桥或跨进程COM封送。

工具直接消费统筹已保存的 `installed-dimension-contract.json`，核显式提供的sldworks.tlb文件SHA与原件一致，不再次LoadTypeLib、不连接ROT、不实例化或调用SOLIDWORKS。输入必须是已存在的绝对路径，输出必须是新目录。不得安装PowerShell、.NET、interop或其他依赖来完成本次检查。

PowerShell必须为已经存在的Windows PowerShell Desktop（ReflectionOnlyLoadFrom所用.NET Framework）。它仅使用reflection-only装载和CustomAttributeData；不使用目标程序集执行装载或实例化属性构造器。依赖仅从显式interop同目录或已知框架名字作reflection-only解析，记录路径/hash，缺失即停，无任意磁盘扫描/下载/执行装载回退。依据：[Microsoft reflection-only说明](https://learn.microsoft.com/en-us/dotnet/framework/reflection-and-codedom/how-to-load-assemblies-into-the-reflection-only-context)、[CustomAttributeData说明](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.customattributedata)。

报告保留exe/DLL路径、hash、版本、程序集FullName/架构/属性；IModelDocExtension.SaveAs3、IDimension.SetSystemValue3/GetSystemValue3的参数类型、位置、in/out/byref/optional、DISPID、返回类型及所有声明的MarshalAs元数据（缺失保留为空）。自动比较装机家族major33、type-library/interface GUID、DISPID、参数数量/类型与既有原件；不根据签名或缺失属性猜测null/BSTR的运行语义。即使success=true，native_binding_accepted和null_marshaling_accepted仍为false，marshaling_review_required=true。

统筹先确认实际文件路径，将脚本和既有原件放在其独立C:\Workspace目录。下列变量必须由统筹设为已核对的显式路径；没有默认猜测的interop/exe路径：

```powershell
& $TaskPythonExe "$TaskSourceRoot\scripts\ci\inspect-installed-interop-contract.py" `
  --output-dir $TaskNewOutputDirectory `
  --typelib-evidence $TaskRetainedTypelibJson `
  --sldworks $TaskInstalledSldworksTlb `
  --interop $TaskInstalledInteropDll `
  --solidworks-exe $TaskInstalledSolidworksExe `
  --powershell "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
```

120秒上限仅针对此次元数据子进程。输出report.json、reflection.json及原始stdout/stderr日志；首次失败和部分已取得证据保留，不换入口重试，不覆盖旧输出。输入结束时重新hash，发现中途变化即拒绝。反射成功不等于原生绑定或GLB导出通过。

本机无PowerShell Desktop，离线测试验证的是Python对照/边界和mock反射结果，没有执行.ps1或装机interop；目标端第一次执行须由统筹先审脚本后安排。本工具未接入CI，未在本路使用VM。
