# 装机 GLB exporter 零 CAD 采集的有限原件审计

2026-11-12，独立离线复核统筹对 `e6fc46c577c3b654a397d2ae8cbb7f3b322dd3cf` 的单次固定文件采集。**采集已完成，不代表运行依赖、签名信任或 GLB 导出已通过。** 本路未操作 VM、CI 或 push。

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/glb-exporter-inventory-e6fc46c-01`。
report SHA-256：`1b98d95526854542c82ad533b0e6923d9ad3690df742e80267cb1d7710e82fb4`。launcher 的 Python／PS 文件 hash 均匹配精确提交；report、metadata request／response、两份空 stdout／stderr 和 launcher 已逐项核摘要。

| required DLL | PE | 实际 file/product version | 静态导入记录 |
| --- | --- | --- | ---: |
| sldgltfu.dll | AMD64 / PE32+ | 33.5.0.0053 | 26 |
| SPAXGLTFBase.dll | AMD64 / PE32+ | 6.427.0.25092 | 12 |
| SPAXGLTFVisualization.dll | AMD64 / PE32+ | 6.427.0.25092 | 16 |
| VisGltf.dll | AMD64 / PE32+ | 6.427.3.25060 | 19 |

路径均来自固定本地 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS`，后三项在 `spiop\files\code\bin`。各文件的实际大小、完整 SHA-256 见[结构化审计](../evidence/glb-exporter-native-inventory-audit-2026-11-12.json)，不从旧 CI 或 exe／PIA 的版本补填。SPAX／Vis 的版本号族不同，不据此判混装。

四文件 before／after 完整指纹（含 path stat、birthtime 和 handle_stat）相等；每次 stable_read 的 path→path、fstat→fstat 严格一致，8 个读取均按已证实的 Windows CPython 3.14.7 ctime 规则接受。metadata 的 before／after hash 和请求 hash 一致。collector 自身、helper、request 前后指纹也一致。两项旧背景文件 SWXRExporter.dll／tlb 明确不存在；不据此宣称核心导出器缺失。

PS helper exit=0，Desktop 5.1.26100.9711、64-bit；四个内嵌 CMS 条目都解码出一名签署者，但没有做签名、证书链、目录或联网信任验证。相应 metadata-only 声明保持不变。

73 条跨文件静态导入记录中，45 条在固定精确位置有普通文件匹配，28 条未匹配。它们包含跨文件重复名称；这些数字不是 73 个唯一的运行模块，也不是 loader 成败结论。每条 runtime_resolution 仍为 unknown_not_executed，静态未匹配不等于运行缺依赖。

launcher 记载语法预检和采集均 exit=0；五个 policy scope 原均 Undefined，RemoteSigned 仅用于统筹已审阅的 child environment，没有修改全局策略。采集脚本只读取文件和元数据，没有 CAD 创建、目标 DLL 执行装载或 GLB 保存。本路只重新核对这些原件，不重新执行采集。

本次补足“当前装机文件是否存在、什么版本、什么 hash、是否在读期间稳定”的缺口。它没有验证实际 GLB writer 的加载路径、动态／API-set 解析、跨进程 exporter 行为或输出网格。GLB 首次空 BIN 原件结论保持，下一步仅准备现有的 C# 同 owned host／同 document 单次现代 SaveAs3 调用层对照，仍待统筹亲审，不能把文件采集成功升级为 GLB 修复。
