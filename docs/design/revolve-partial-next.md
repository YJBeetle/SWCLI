# 部分角度旋转下一阶段：实现与原生计划

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

## 提议原生排期（尚未执行）

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

首轮交付只表示实现及 portable 检查可审阅；本文件不是原生完成、merge-ready 或 release 声明。
