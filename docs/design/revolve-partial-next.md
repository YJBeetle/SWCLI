# 部分角度旋转下一阶段：实现与原生计划

方向单例已在原生 Windows SOLIDWORKS 33.5.0 通过。本页保留原计划，并记录后续矩阵的实现与排程。

本路基线为 `31ad9c256a5a106bc94a627cd41dfd6277bb6f00`，工作分支
`codex/swcli-revolve-feature-next`。现有 360° 原生结论及原件保持独立；
旧 run 42273047248 不能证明部分角度的方向、表面积、保存持久性。

## 已实现与未验收边界

- 请求允许显式有限 `0 < angle_deg <= 360`，仍要求完整矩形 bounds CAS、左边轴、document/stamp/lease 保护。
- 部分角度公开写白名单为空。daemon 在 stamp、lease、草图引用检查后、临时激活前返回
  `RevolveNotCalibrated`，mutation 三值均 false；直接 worker 入口在版本检测及 COM 观察前拒绝。
  公共成功结果仍强制 `angle_deg=360`，没有内部候选参数或公开 bypass。
- 私有候选只接受 45/90/180/270°，显式预声明 `rotation_sign` 和 `axis_direction`（各为整数 ±1）。
  所有原有空 part、单配置、三原点平面、中心矩形、精确轴、无已有实体、完整健康诊断守护保留。
  angle 参数用弧度；定义回读检查请求角度、reverse=false、solid boss/nonthin、轴 identity，
  部分候选额外保存并核对创建前后轴端点顺序。创建后失败保留原 feature、mutation、首因与独立 cleanup，绝不重试或回滚。
- 同一读取 helper 可在重开后用新的轴 handle 与创建时保存的端点核对；这只是准备能力，
  **本轮未创建或保存任何原生部分角度模型，也没有原生 save/reopen 结果**。
- CLI、SDK、MCP 沿用同一契约。SDK 生成无需类型变化（角度原本就是 number）。
  没有修改默认 CI、原有 calibration/public profile 或发布范围。

## 独立解析检查

草图局部从 +X 径向出发、绕左边轴旋转，s 表示朝局部 +Z/-Z 的预声明符号，θ为正弧度：

```
V = θ r² h / 2
S = θ r (r+h) + 2 r h       (0 < θ < 2π)
x̄ = 2r sin(θ) / (3θ)
ȳ = (min_y + max_y) / 2
z̄ = s 2r (1-cos(θ)) / (3θ)
```

实际使用 half-angle sinc 避免小角度消减误差；质心通过已验证的 model-to-sketch 逆旋转映射到模型。
严格等于 360° 才使用原圆柱 V/S/质心，接近 360° 不得省略两片径向面。
V/S 保持 rel_tol=1e-8、abs_tol=1e-6，质心 abs_tol=1e-6 mm，不放宽旧容差。
解析可接受其他可表示角度，但私有 CAD 候选仍只有四个离散值；极小角度弧度/体积下溢明确拒绝。

## 官方依据与方向缺口

[FeatureRevolve2 官方文档](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeaturemanager~featurerevolve2.html)
列出 20 个参数及 Dir1Angle 的弧度单位。
[GetRevolutionAngle 官方文档](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IRevolveFeatureData2~GetRevolutionAngle.html)
定义 `True` 为方向一。
这些资料没有证明 `ReverseDir=False`、草图边端点顺序与模型旋转符号的对应关系。
因此不由测得质心挑选符号，也不把旧 full-turn 验收外推到部分角度。

## 初始原生排期

第一轮按统筹要求仅代码与 portable；没有本地 VM、COM、原生 dispatch。
现有 workflow 只绑定旧分支，不能拿旧开关给 next 分支空跑；新的定向 runner/默认关闭路由仍待后续准备。
统筹确认排期后，须先准备该精确 head 的独立 harness，沿用原有600秒单 native/case与1800秒整组预算，
原件写新目录 `evidence/revolve-partial-next/<run>/`，不覆盖旧原件。

1. **方向控制单例**：原生 Windows SW 33.5.0、安装 TLB 原件 hash/20参数/枚举、独占 fresh host。
   在报告中预先写入 front、r=10、h=20、y=-5..15、90°、轴预期 +Y、局部旋转符号 -1 的单一假设
   （右手 +Y 的数学假设，尚非 SW 实测结论）。只创建一次；轴顺序或质心不符即停止，保存首因和完整测量，
   不能在组内改符号、换角度、重试 API 或重启宿主。
2. 方向单例通过并审阅原件后，才安排 **45/90/180/270° × front/top/right**。
   每例独立空 part，预声明轴/旋转符号，检查精确 API 参数、定义、轴、V/S/三轴质心及完整健康诊断。
   需要分组时由统筹分配独立有界 run，不能提高1800秒预算掩盖超时。
3. 每例保存原生 SLDPRT、SHA256，关闭，再只读重开：恰好一个可编辑 Revolution、一个被吸收中心矩形、
   相同完整 bounds/transform/轴顺序、原定义、同一解析量；核 read-only、dirty=false、非编辑、零选择、
   foreground/配置、文件 hash 不变。先落盘实际测量再断言，不只存预期值。
4. 独立拒写/partial controls：公开部分角度零mutation、错误 stamp/lease/引用、profile CAS、readonly、
   已有实体、错误原点框架、预声明轴相反应在创建前拒绝；一次创建后注入观察失败时保留精确 feature 与首因，
   仍保存/只读重开 partial 证据。错误不得被 cleanup 覆盖。
5. 最后核 run/head/artifact 原 ZIP hash、逐请求 trace 的 begin/end 与创建次数、预算、清理/宿主退出。
   内部通过也不自动开放公共写域；另行准备 CLI→daemon→worker 的精确角度/平面公共验收。
   离散值原件不能代表整个连续区间，更不能代表任意曲线、cut/thin 或已有实体 merge。

## 2026-11-21 方向单例原件

统筹在 Windows VM 对 `116de8e8d1699ce72521dd5f38cf1701c0b110e1` 执行一次。原生报告和 stdout 成功，
确认 SW 33.5.0、前视 90° 的 +Y 轴与 −Z 旋转、一次 `FeatureRevolve2`、一个实体，创建与只读重开后物性相同。
体积 `1570.7963267948967 mm³`，面积 `871.238898038469 mm²`，质心约 `(4.244131816, 5, −4.244131816) mm`。
模型字节 SHA256 `2c6dc1ab25627a80c1aa3a3619863237104d08197ab0361739d837e85532664b`，退出后进程列表为空。
父子来源凭据及原生类型库记录均确认注册安装目录两份相邻的类型库。
已在持久目录复制并核对全部 15 个文件。外层 zsh 在复制结果后因只读变量 `status` 报错，传输退出码仍缺失。
详见 [方向单例证据摘要](../evidence/revolve-direction-vm-2026-11-21.json)。

## 矩阵调用与证据边界

安装准备包后，用已有本地入口添加 `--matrix-plane front`、`--matrix-plane top` 或 `--matrix-plane right`。
由统筹逐组安排，每组使用新的证据目录和一个独占宿主，每个角度新建一份空零件。
参数选择限定为单个平面，角度固定按 90°、45°、180°、270°。每组在启动宿主前落盘四例意图。
三种已校准原点平面的坐标系均为固定值，局部轴顺序预期为 +Y，局部扫掠预期从 +X 朝 −Z。
执行前以同一预声明方向作为断言。差异进入原报告并停止该组。

每组继续使用 1800 秒总预算，单例及各 native 边界 600 秒。报告 `planned_cases` 与 `cases` 按顺序保留；
每例一个唯一命名 SLDPRT，核定义、轴、V/S/质心、诊断及只读重开后状态和哈希，清理阶段核宿主退出。
进程退出码为零还要求四例完整顺序与成功回执。默认本地调用仍为 90° 单例；现有 GitHub 单例入口不接收矩阵参数。

## 2026-11-21 三平面矩阵原件

统筹在原生 Windows SOLIDWORKS 33.5.0 对 `ca0ea488a04137fe33a733ca69d26c3845cad166` 完成 front、top、right 三组。
每组按 90°、45°、180°、270°，各自有独占宿主和空的结束进程清单。驱动及传输的六个退出码都是 0。
逐字节归档 60 个原件，复核 12 份模型在原始报告、独立审计及重开报告中的 SHA256 一致。
每例的真实 `FeatureRevolve2` 仅一次，创建与只读重开分别符合定义、轴顺序、物性解析量、诊断与文档状态。
[矩阵原件摘要及哈希](../evidence/revolve-matrix-vm-2026-11-21.json)

## 拒写与创建后观察失败对照

本地 `--controls` 运行一组固定对照，意图为已校准的前视 90°。保护域始终关闭。由统筹排定独占 Windows 运行窗口，
每例及 native 边界 600 秒，单 worker 组 1800 秒。证据目录须为新路径。入口及安装条件沿用方向单例。

- 公开操作分派使用真实本地零件和注册表对象，检查部分角度关闭、过期 stamp、其他会话 lease、未登记的草图。
  记录真实拒绝及前后文档；这一步还没有使用公开 CLI、SDK 或 MCP 传输。
- 私有候选检查完整轮廓 CAS、真实原生文件只读重开、真实已有实体、10 mm 偏移面和相反的预声明轴。
  偏移面用安装 TLB 中实际读取的 distance 枚举创建，`InsertRefPlane` 使用 0.01 m。
  [SOLIDWORKS InsertRefPlane](https://help.solidworks.com/2022/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeatureManager~InsertRefPlane.html)
- 拒写前后比对活动身份、保存状态、配置、选择、特征、实体数及可用文件 SHA。公开分派的 stamp、lease 与引用守卫
  抛出对应异常，因请求未进 handler 而没有 mutation 回执。其余拒写要求三项 mutation 为 false。
- 最后一次真实创建后注入定义读取异常。记录三项 mutation 为 true、首因及原始 feature，并核对精确对象、
  单体物性、诊断、保存和关闭后只读重开。注入异常仅模拟观察失败。
- 完整报表须与计划逐例匹配。退出码为零还要求拒写 trace 无旋转选择或创建，partial trace 有恰好一次原生创建
  和已声明的观察异常。首个差异停止，宿主清理与原始回执均保留。对照当前仅完成离线准备，仍需原生执行和原件审阅。

既有 12 个原生正向模型属于有限角度与矩形夹具。它们尚不授权公共写域或当前发布。

## v0.2.5 基线上的对照复核（2026-11-23）

旋转候选分支已经合入发布基线 `8408b8a657b6fdfb05dd47422cd5cdea9010a056`。
原生矩阵仍定位到 `ca0ea488a04137fe33a733ca69d26c3845cad166`。
预先打包的 `46a3277e09be890b38f964f3bb4b6863d0338e35` 对照保留旧保存语义和独立来源。
本轮对照在新版基线上运行同一计划，通过 `IModelDocExtension.SaveAs3` 保存只读夹具和 partial 模型。
两次保存都要求 `save_attempted`、`api_saved` 为 true，以及此次调用实际写入的错误和警告整数均为 0。
发生保存或重开错误时，报告保留实际回执，其后才执行独占宿主清理。

Windows 包使用独立的 `C:\Workspace\revolve-controls-v025`，按包内 `WINDOWS.md` 安装并运行本地 `--controls`。
独立 GitHub 原生 workflow 仍只提供原先的方向单例，不纳入本次对照环境的排程。
