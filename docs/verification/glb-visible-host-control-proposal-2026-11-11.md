# GLB 可见启动模式局部对照候选

状态：**仅完成离线方案、driver 副本和正反 trap 测试；未执行 VM／CI**。由统筹亲审并独占调度一次运行。本候选不实现 C# bridge、不改变产品、工作流或导出参数，不据此承诺公共 GLB 支持。

## 变量及契约边界

按统筹指定，复用持久 `local-glb-host-control.py` 的 fixture、固定源码和导出路径，仅把 owned harness 的启动参数从 `visible=False` 改为 `visible=True`。原 driver 保持不动，新副本为 `scripts/diagnostics/glb-visible-host-control.py`；逐项变化见 [相对原 driver 的 diff](../evidence/glb-visible-host-control-driver.diff)。

**这是一个启动选项的对照，但不是仅写一个 Visible 属性的物理单变量。** 固定源码的 `configure_resident_app` 中，隐藏分支设置 `UserControlBackground=True`、`Visible=False`；可见分支设置 `UserControl=True`、`Visible=True`。候选如实记录 `only_visible_property_changed=false`，同时只读两种 UserControl 属性，防止将模式差异误写成纯 Visible 因果。

官方 [UserControlBackground](https://help.solidworks.com/2022/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControlBackground.html) 和 [UserControl](https://help.solidworks.com/2019/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~usercontrol.html) 说明这两个属性分别控制后台隐藏与前台可见模式。[Visible](https://help.solidworks.com/2016/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~Visible.html) 还区分显示状态与程序退出后的生命周期。没有据此推导“GLB 必须可见”。

## 固定条件与最低成本操作

- 基线源码：`70d8c9ecf3c02b099ca9c2cc64fe1880061cea44`；源码 ZIP SHA-256：`06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53`。
- 原 driver SHA-256：`282d75cb4a4097dac4077bb7e70af68d8278c351880d0887ce8220ba46cd36d2`。原件位于 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/local-glb-host-control.py`。
- fresh owned app，拒绝附着已有 SOLIDWORKS；仅一份 front 矩形 40×30 mm、拉伸 10 mm 的新零件。
- 保持 `component.SLDPRT`、`component-export.<format>` 命名及原产品内部随机暂存命名规则。
- 保持 STL→3MF→AMF→GLB，每格式一次，GLB 仅一次。创建、矩形、拉伸、原生保存和导出五类 API 调用表达式的 AST 与原 driver 相同。
- 仍使用固定源码的 Python modern `IModelDocExtension.SaveAs3`：原路径、Version=0、Options=1、两个空 IDispatch、Errors/Warnings 显式 BYREF Int32。没有更换绑定或参数。
- 原有运行超时、输出拒绝覆盖、owned 清理、严格网格解析及 GLB runtime manifest／拒绝原件保留开关保持。主进程与 worker 在载入 pinned 源码前都核对源码包摘要及解压文件字节。
- 启动 flag 之外新增的 CAD 操作只有读取和身份检查；0 偏好 setter、0 新增 CommandInProgress setter，不加入相机、缩放、重绘、DocumentVisible 或重试。

脚本设计为由统筹审阅后复制到现有 Windows 系列目录 `C:\Workspace\SWCLI-series-20261110`，与 `source-70d8c9e`、`getter-source-70d8c9e.zip` 并列。不得覆盖原持久 driver。新输出目录固定为 `glb-visible-startup-70d8c9e-01`；已存在即停止。本次提交不运行该脚本。

## 读取与判据

创建 fixture 前记录实际 `app.Visible`、`CommandInProgress`、`UserControl`、`UserControlBackground` 与 PID。每次导出前后独立只读记录这些值，以及前台文档 IsSame、文档类型／stamp／dirty／当前配置／路径／标题／只读状态、非编辑状态和实际源文件 SHA-256。

要求 Visible 实际为 true，宿主状态与初始读值一致，每次导出前后文档状态、配置、前台身份及源文件哈希一致。Popen/venv 启动 PID 与实际 native worker PID 分开保存。

任何首个原生异常、内容拒绝或前置断言失败即停止；不重试、不自动第二轮、不改期望。内容拒绝后不增加 CAD 状态读取，只有原有 cleanup；相应 `after` 缺失是未观测，不能写作状态保持。worker 结束后再离线收集原始 GLB、实际 chunk/BIN、buffer 声明、manifest 与文件哈希；诊断解析错误不替换首个业务错误。

成功还必须保留原严格 mesh 解析结果，并离线核对四个导出 request 各一次现代 SaveAs3、同一实际 worker、0 trace 可见偏好 setter、0 CommandInProgress 写入。缺少调用、重复调用、错误 worker 或旧 API 不能通过。此审计只覆盖记录到的 trace；不以原生返回 true 代替有效 BIN／网格。

基线报告没有实际读取导出时 Visible 或 CommandInProgress。因此新运行即使读到 false CIP，也不能宣称旧基线同值已经实测。该缺口不通过额外写入 CIP 或自动补跑隐藏对照来弥补。[CommandInProgress 官方说明](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~CommandInProgress.html?format=P&value=) 仅说明其减少进程外 API 序列期间的更新，不能据此判定 GLB 失败根因。

## 历史反例与限制

更早原始 ZIP 已重新核哈希和实际网格，详见 [结构化历史证据](../evidence/glb-visible-host-control-offline-2026-11-11.json)：

| 运行 | hidden 模式中的 part GLB | 同组 assembly GLB |
| --- | --- | --- |
| 42173065847 | 3800 B，BIN=0，无效 | 4748 B，有效，12 三角形、24 positions／normals |
| 42199134982 | 相同无效原件 | 相同有效原件 |

两次 assembly 原件 SHA-256 均为 `4091246c9af29a4c858ba73e815c9150dbc37d4c4f9e52d6dabbc4f71e345421`，严格解析得到约 40×30×10 mm 的盒子。part 原件 SHA-256 为 `2d49602f1bbd443d60b8975d249b4ed8defb5a5948b869eabfddacb1974a2c5c`，与现代 42405530053 的失败 part 相同。

这些是旧 `IModelDoc2.SaveAs3` 路径的 hidden 模式成功记录；不能当成现代 part 的同条件成功。更重要的是，host.visible=false 来自启动时读取，后续 status 返回的是缓存 host，导出瞬间没有重新读取。组日志也未保留这些 GLB 请求的 native-call trace；CommandInProgress=true 只能由固定源码的 owned scope 推断，不能写作原始布尔实测。

因此历史证据说明：不能把所有 hidden 模式 GLB 一概记为失败，也不能仅凭缓存 flag 证明导出瞬间绝对隐藏。现代 42405530053 有进入／恢复 CIP 的请求轨迹但 part 仍为空 BIN；其 `visible-open` 成功报告没有任何 GLB 导出。已检查集合没有有效 hidden 模式 part GLB，也没有可见 GLB 导出成功证据。

若新对照产生有效 part 网格，只支持“该固定样件的可见启动模式可成功”，不证明 Visible 单独的因果或官方必要条件；若仍为空 BIN，则说明该模式单独不足以修复此路径。出现其他首错就只记录该首错，不继续另做实验。

## 离线验证

九项正反 trap 测试涵盖只读观察、Visible／CIP 类型、PID／文档身份／配置／源哈希／编辑状态、首错后不读 CAD、不重试、单一固定 fixture、模式设置的两个属性、原始空 BIN／坏文件／manifest 保留、包与解压源码篡改，以及调用次数／旧 API／偏好 setter／CIP 写入的拒绝。测试未创建 SOLIDWORKS 实例，不能替代一次真实局部对照。
