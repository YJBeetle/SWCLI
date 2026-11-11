# GLB 导出器证据缺口与下一最小信息路径

状态更新（2026-11-12）：267a34c实际PIA/identity通过，C#单次True/0/0仍空BIN并与原Python baseline逐字节相同，[有限证据已审计](glb-typed-control-native-audit-2026-11-12.md)。下一步只准备MarkingJig只读工作副本/OpenDoc7/现有Python现代SaveAs3候选，完整引用未知就0保存停止。用户确认历史成功环境DockerSW latest；生成时digest/软件版本未知，不拿静态2025配置或当前tag补填，不操作镜像/容器/CI。以下早期评估保留，不当当前候选状态。

## 官方支持合同能说明什么

[2025 GLTF/GLB 文件类型正文](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_glb_gltf_extended_reality_files.htm?id=18.15.12)明确列出两种格式的输入／输出支持。它不是只有 Visualize 才支持的格式，不能用 Visualize 的另一套接口代替本问题。

[官方 SOLIDWORKS 2025 What's New，英文印刷页 172–173](https://files.solidworks.com/Supportfiles/Whats_new/2025/English/whatsnew.pdf)说明 SP2 把 XR 导出选项移至 System Options > Export，仍从模型的 Save As 选择 GLB／GLTF，选项保持不变。这是同版本的产品／UI 支持依据；不是任意自动化绑定、Silent 模式或每种 document 状态都已通过的保证。

可读的[现代 SaveAs3 API 正文为 2026 页](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs3.html?format=P&value=)，描述按后缀转换和七参签名，没有给出本问题所需的 GLB 专门封送约束；不能冒充已读取 2025 API 正文。已有装机 2025 typelib／PIA 反射验证只证明七参元数据匹配，不证明两种 null 的实际调用封送或 GLB 输出成功。

在本次已读官方资料中，没有找到“part 不支持 GLB”“必须 visible”“CIP 必须 false”或“必须重新启用 SWXRExporter add-in”的具体合同；不能将搜索未命中当成这些命题的反面证明，也不应凭猜测加开关。

## 实际 exporter：哪些有原件、哪些仍未知

旧 CI 42405530053 的原始安装 ZIP SHA-256 为 `eced0a0b91ec041025237d28aedc8cbe332b50f6df645ce2769355e9095c8055`。已按 UTF-16 解码 MSI 原件，逐行核实全部 25 条相关摘录，不能把安装前的 `Installed: Absent` 单独当作最终安装失败。

| CI 日志中的相对路径 | 日志复制版本 | 解释边界 |
| --- | --- | --- |
| sldgltfu.dll | 33.5.0.53 | 有 FileCopy 和 ComponentRegister |
| spiop/files/code/bin/SPAXGLTFBase.dll | 6.427.0.25092 | 有 FileCopy 和 ComponentRegister |
| spiop/files/code/bin/SPAXGLTFVisualization.dll | 6.427.0.25092 | 有 FileCopy 和 ComponentRegister |
| spiop/files/code/bin/VisGltf.dll | 6.427.3.25060 | 有 FileCopy 和 ComponentRegister |
| SWXRExporter.dll／tlb | Action: Null，安装条件 false | 不能据此断言整套 GLTF 导出器缺失或要求手动加载 |

这些记录属于 CI 的 `C:\Program Files\SOLIDWORKS`。本地装机反射记录的根路径是 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS`，exe 和 PIA 为 33.5.0.53，但没有上述四个 exporter 文件的实际哈希／版本／依赖清单。两次局部运行的 module 快照只保存筛选结果（448／443 项枚举后均无匹配），不包含完整模块路径，也不排除瞬时模块或其他进程参与。

GLB 中的 `asset.generator=SOLIDWORKSGLTF` 只能识别输出标签，不能反推出具体 DLL、加载路径、版本或许可证状态。已有旧 CI 安装日志及本地 exe／PIA 元数据不足以确认当前本地 exporter 与旧成功 assembly 使用的是同一套实际文件。

## 最低成本的下一步：先零 CAD 定点读取

建议先由统筹另行亲审一个仅文件读取的安装核验，不立即安排新的 GLB：

1. 固定为已有本地 exe 的安装根，逐一检查上述四个相对文件；另记录旧 SWXRExporter.dll／tlb 的存在与否作为背景。每项读取实际绝对路径、存在性、大小、SHA-256、文件／产品版本、PE machine 和签名信息；不递归扫描整机、不注册、不加载 DLL、不创建 COM、不改文件。
2. 对四个已存在文件只解析静态 PE import 名称。依赖是否可在同一已知安装目录及明确的系统目录找到，分别记 exists／missing／unknown；延迟、动态和运行时搜索路径依赖不能用静态结果宣称已解决。所有结果必须绑定安装根与原文件摘要。
3. 与旧 CI 日志中的版本作差异表，不能把不同产品版本号族（33.5 与 SPAX 的 6.427）误判为不配套，也不要求当前文件等于另一安装环境的未知哈希。

| 定点读取结果 | 下一决策 |
| --- | --- |
| 已知文件缺失、明确错误架构或可证的混装 | 先提交环境证据给统筹判断；不靠换 API 或重试掩盖，也不自行修复安装 |
| 文件完整但动态依赖／加载路径仍未知 | 明确保留 unknown；需要时设计有界只读加载取证，不能由空 filter 推断缺失 |
| 未发现可处理的安装差异，仍要区分 Python 动态封送与共享现代写器路径 | 再亲审 typed 传递已有引用的单次保存候选；不先做新参数扫描 |

这一步不能证明 exporter 一定正确，但能以零 CAD 保存的成本补足当前最具体的环境证据缺口。此前本节评估未授权新增桥接；2026-11-12 顶部状态已更新为统筹授权的既有 typed 源码准备，以下保留当时评估。

## part／assembly 及 typed 路径的信息增益

实际原件已证明旧同组 assembly 有 720 字节 BIN、part 为空；相同 buffer/accessor/mesh 声明不代表 part 的实际网格已存在。旧 API、宿主、文档上下文、安装环境和渲染历史都与当前现代 part 不完全一致。把 part 包成 assembly 再导出会新增文档类型、上下文、解析状态等变量；它能回答“现代 assembly 是否也失败”，但不能直接判定 Python 封送，所以不优先用新 CAD 保存换这个较弱结论。

若后续确实针对封送问题实施 typed 候选，继续采用现有[具体同 host 引用传递设计](glb-typed-same-host-control-plan.md)：固定 x64／装机 PIA，已有 app／document／Extension 经受限一次性跨进程 COM 封送包传递，STA 内验证 SW PID、文档与 Extension canonical IUnknown 身份，先做零保存握手；仅在门禁通过后用相同 Name、Version=0、Options=1、两个 null 和装机 [In,Out] `ref Int32` 执行唯一 GLB。无 ROT、新建 host、重开替代 document 或备用 API。

这里“同 host”指 Python 持有者与 typed 消费者在该次运行中确为同一应用和文档。旧局部基线宿主均已清理，新运行不可能复用它们；因此不能宣称历史 Python 失败与新 typed 成功是物理同一 host 的成对实验。严格的同 host 双绑定比较会需要另行设计两次保存及首错边界，不在当前单次调用授权内。

typed 有效 BIN 会支持该固定 typed 路径可成功，仍不能单凭它定位某个 VARIANT 参数；typed 同样为空 BIN 则使 Python 特有封送不再是唯一解释。任何握手、身份、原生或内容首错都停止，不在该轮继续换参数或重启。桥接实现与任何执行均留待统筹在安装证据评估后亲审。
