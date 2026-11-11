# 装机 GLB exporter 定点零 CAD 文件采集器

状态更新（2026-11-12）：统筹对 e6fc46c 的一次零 CAD 采集已完成，四 required DLL 元数据和前后指纹经[独立审计](glb-exporter-native-inventory-audit-2026-11-12.md)核对。仍不是运行依赖、签名信任或 GLB 验收。17deb54 首次失败及后续 stat probe 保留在[ctime 审计](glb-exporter-stat-ctime-2026-11-11.md)，不覆盖原失败。

## 固定输入来源

用户／统筹批准的安装根固定为 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS`，没有改根、递归查找、PATH 或全机搜索参数。代码常量 `SOURCE` 保留原始 CI 42405530053 安装 ZIP 的 SHA-256 和相关 MSI 行号，来源仅解释为何选择这些文件，不能代替本地实际存在性。

| 固定相对路径 | 用途 |
| --- | --- |
| sldgltfu.dll | 读取完整文件、PE machine、版本、内嵌签名元数据与静态导入 |
| spiop/files/code/bin/SPAXGLTFBase.dll | 同上 |
| spiop/files/code/bin/SPAXGLTFVisualization.dll | 同上 |
| spiop/files/code/bin/VisGltf.dll | 同上 |
| SWXRExporter.dll | 仅存在性背景；若存在则读取身份、hash、PE 和版本／内嵌签名元数据，不扩展依赖检查 |
| SWXRExporter.tlb | 仅存在性背景；若存在则读取身份、hash 和可得版本，明确不是 PE 签名表 |

四个 DLL 的每个普通／延迟导入名，只在“该 DLL 所在目录、固定安装根、`C:\Windows\System32`、`C:\Windows\SysWOW64`”组成的唯一精确路径列表查存在；相同目录去重。没有递归目录枚举，没有 PATH／当前目录／注册表查找，不读取任意导入路径。含目录分隔、冒号、`..`、非支持 ASCII 或非 `.dll` 的名字拒绝查找并留下 unknown。

## 只读零 CAD 合同

入口为 `scripts/ci/inspect-installed-glb-exporter.py`，旁边必须保留 `inspect-installed-glb-exporter-metadata.ps1`。入口仅接受一个新的绝对 `--output-dir`；输出目录不能位于输入安装根或上述系统目录，已存在即拒绝。由统筹另行决定执行时间；本提交不执行下例。

```text
python -I C:\Workspace\glb-exporter-inspection\inspect-installed-glb-exporter.py --output-dir C:\Workspace\glb-exporter-inventory-01
```

需要已存在的原生 64-bit Windows Python，以及固定 `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`。拒绝 32-bit 重定向或其他平台，不安装解释器、包、框架或工具，不改 ExecutionPolicy，不使用 Bypass，也没有另一连接／执行路径回退。框架 `System.Security` 仅用于离线 CMS 解码。

没有 CAD 创建／连接／调用、COM、注册、目标 DLL 的执行装载、LoadLibrary 或网络安装。Python 只解析文件字节；PowerShell 仅用 `FileVersionInfo.GetVersionInfo` 读版本、用 `SignedCms.Decode` 解码已经从该 PE 文件取得的内嵌 PKCS#7。没有 Get-AuthenticodeSignature、CheckSignature、证书链构建或联网信任检查。系统框架的正常运行不是对被检查 exporter DLL 的装载。

Microsoft 依据：[PE 格式／导入／延迟导入／证书表](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)、[FileVersionInfo.GetVersionInfo](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.fileversioninfo.getversioninfo?view=netframework-4.8.1)、[SignedCms.Decode](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.pkcs.signedcms.decode?view=netframework-4.8.1)。Decode 与签名验证是不同步骤；本工具不执行后者。

## 身份及变化门禁

每个存在的固定输入都记录绝对路径、regular／no-reparse 状态、device／file ID、mode、size、mtime_ns、ctime_ns、Windows 属性及 SHA-256。各级父目录也必须为非 reparse 真目录且身份可读。使用新鲜 no-follow stat，拒绝 symlink／junction／其他 reparse 和零文件身份，不用 Windows DirEntry 的缓存标识。

打开文件后执行带版本限定的跨渠道比较（详见上述审计）：只有已证实的 64-bit Windows CPython 3.14.7、相等 birthtime 与严格身份等全部条件满足时，才允许唯一 ctime_ns 语义差；raw 值不归一。path→path、fstat→fstat 及整个采集前后的双渠道指纹仍严格；有界读取后检查句柄、路径和父目录身份。版本／签名采集结束，再读取原文件并要求 stat 与 hash 均和之前相同。PowerShell 自身也比较目标数据前后 hash、大小、mtime 和属性，且 hash 必须匹配 Python 传入的值。父目录只核身份和属性，不把目录内其他文件变动误作原文件修改；原文件 mtime／ctime／hash 仍必须一致。

辅助脚本、元数据请求和响应是工具自身／本次输出的完整性读取，不是新安装扫描。请求前后也核 stat/hash，防止签名数据包被另一写入替换后错贴到文件。输出和日志只写新的输出目录，PowerShell 元数据响应以 CreateNew 写入，不覆盖既有文件。

任何身份、字节或辅助契约不符都会使采集不能完成。若辅助过程先失败、之后文件检查也失败，保留辅助的首错，另存 postcheck_error，不以清理／检查错误替换首错，不重试。普通缺项则明确记录 `not_present_at_checked_path`；不可读／不安全／解析不支持均为 `unknown`，不伪装成不存在或稳定有效。

## 元数据及判读边界

PE 解析记录原始 Machine 数值、I386／AMD64／ARM64／unknown 和 PE32／PE32+。普通与延迟导入分开，RVA 只映射到唯一实际文件区间；拒绝越界、重叠歧义、未终止表和不支持的延迟属性。证书表地址按 **文件偏移** 处理，不当成 RVA；拒绝与映像内容重叠的表。

版本保留文字、固定数字部分、描述与公司；无文字或不可读明确记状态，不凭 exe／PIA 版本补填 exporter 版本。内嵌签名保留 WIN_CERTIFICATE 类型／revision／内容摘要，以及可解码签署者的 subject、issuer、thumbprint、serial、有效期和 digest OID。thumbprint 是标识，不是信任结论；`cryptographic_validity=unknown_not_verified`、`catalog_signature=unknown_not_queried` 始终明确。无内嵌条目不等于文件未签名或无目录签名。

静态依赖路径逐一记录双次 stat 存在性；变化或访问错误记 unknown。`static_path_match` 只说明固定位置存在普通文件；`runtime_resolution=unknown_not_executed`，并明确 `not_found_is_not_runtime_missing=true`。API-set 名称也不能因找不到同名实体 DLL 就判缺失。本工具不模拟实际 Windows loader 顺序、动态加载、延迟执行、搜索路径、转发或其他进程。

固定输入每个最多 256 MiB，PE sections≤96、普通＋延迟导入总数≤256、名字≤255 bytes、证书表≤1 MiB／16 条、CMS signer≤16／certificates≤64、请求／响应≤16 MiB；辅助过程限 120 秒。静态依赖仅按最多四个目录精确查找，不扩展为依赖树。

`collection_completed=true` 仅表示本次固定观察完成，不代表文件齐全、解析无 unknown 或 exporter 可用；另看 `required_files_all_present` 和每项状态。`exporter_runtime_accepted=false` 始终保持。缺项、版本差异或静态未命中均交统筹判读，不自行修安装，不实施 typed bridge 或新 GLB 保存。

## 离线验证及未覆盖部分

反例测试使用合成 PE32／PE32+、临时文件和替代 runner，不读取真实 SOLIDWORKS 安装，也不运行 PowerShell。覆盖普通／延迟 RVA 与 VA32 导入、证书文件偏移、坏 header／RVA／目录／计数、危险名称、空表、文件／父目录 symlink 与 reparse、零 ID、stat-open 竞态、打开后替换、辅助调用后字节／身份变化、原缺项出现、请求篡改、首错保留、伪造辅助契约／文件集合／hash、固定工具缺失以及无搜索／COM／网络／目标 loader 的静态合同。

24 项可移植反例测试之后，统筹单次装机采集已完成，PowerShell helper 实际版本读取与 CMS 解码已观察；签名信任、运行依赖解析和 GLB 输出仍未验证。后续零 CAD 原件须保留 report、metadata request／response、stdout／stderr 和精确执行源码，不将本次测试回执当成装机结果。
