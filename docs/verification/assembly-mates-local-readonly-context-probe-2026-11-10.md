# 原生 owner 只读对照，交 root 排 VM

## 精确来源与边界

- 运行时代码固定为 `b368fd401a947ac932323616b17d00d65b62a864`。本方案仅准备诊断，尚未在 VM 执行。
- 精确 wheel 为 `/Users/YJBeetle/.codex/worktrees/swcli-assembly-mates/SWCLI/evidence/run-42663685871/dist-original/swcli-0.2.4-py3-none-any.whl`，SHA-256 `049b7061c8e9603a8c7d60c10ca9f73c381f73a68c01b07a314e79f791b4743a`。此前该 wheel 的 83 个 Python 文件已逐一匹配代码提交。
- 使用 root 分配的干净 visible owned 测试 daemon，同一宿主/worker、同一 endpoint、同一 session 执行两种前台状态的观察。Native revision 需与 CI 的 `33.5.0` 一致。
- 只读范围包含 daemon status、document list、两个 document open --read-only、document use 和最多两次 assembly mate-targets。root 通过窗口切换控制前台。CAD 数据零写入，CreateMate / CreateMateData 均为 0 次。
- 不调用 document create、add-component、add-mate、rebuild、save、选择实体或任何失败后的替代 API。首个错误立即停止并保存原始输出，后续状态不继续。
- 每个请求 600 秒，总组 1800 秒，由 root 的执行监督器控制。保留原错误和现场，后续关闭由 root 单独处理，诊断流程无自动重启/回滚。
- 输入为已保存且含两条标准配合的装配。它与 CI 的新建、未保存、尚无配合的装配不同，因此本对照只用于缩小上下文因素。完整功能继续用 CI 证明。

## 输入文件

三个文件来自已核验的内部原件，同目录复制到 VM 的独立工作目录，保留文件名并标记文件系统只读。源目录为 `/Users/YJBeetle/.codex/worktrees/swcli-assembly-mates/SWCLI/evidence/run-42279916240/native-original/swcli-native-smoke/assembly-mates-calibration/native`。

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| coincident-aligned.SLDASM | 64069 | `b535588ae3ff2e7656178cea139e974542b3fa1eb82aba2da2b8ee2c6459a081` |
| coincident-aligned-component.SLDPRT | 56914 | `7a2867363b3e6022916cf039c0ddfab9f60df4dcf2e18064dac9a66dd8f629d8` |
| concentric-aligned-component.SLDPRT | 56852 | `9b6d73c3a85a5ae7df9bf0b24bdded7f6eb7bf760033b9921f5c7ce3f01bdf66` |

装配组件名为 `coincident-aligned-component-1`、`coincident-aligned-component-2`。前台对照零件使用 `concentric-aligned-component.SLDPRT`，与目标装配引用的零件不同。

## 进入前检查

1. root 先分配 VM/SW，确认测试 endpoint 属于独立 owned daemon 且无用户文档。已有文档或未知宿主时结束准备，交 root 处理。
2. 使用上列精确 wheel。启动 daemon 前设置 `SWCLI_TRACE_NATIVE_CALLS=1`，保留完整 daemon 日志。worker 保护与 native_api_sequence 使用正常公开路径。
3. 记录 Python、pywin32、SWCLI wheel hash 和宿主版本；与 CI 的差异需写入结论。核对三个文件复制后的 hash 与只读属性。为每个 CLI 调用分别保留 stdout、stderr、返回码及顺序，任何非零返回立即停止。

## 固定操作顺序

以下命令中的 Python/CLI 路径、endpoint 与 VM 文件路径由 root 在分配时填写；ASM_ID 和 FG_ID 只取本次 document open 返回值。共同前缀为：

```powershell
& $probeCli --endpoint $probeEndpoint --session mate-owner-readonly-probe --request-timeout 600
```

依次调用，逐条检查返回码和 JSON：

1. `daemon status --json`，确认 owned、非 shared、revision 33.5.0。
2. `document list --json`，确认空目录。
3. `document open <coincident-aligned.SLDASM完整路径> --read-only --json`，记 ASM_ID。API errors 必须 0，仅接受已知 read-only warning 0 或 2，文档 modified 必须 false。引用解析问题直接结束。
4. `document open <concentric-aligned-component.SLDPRT完整路径> --read-only --json`，记 FG_ID，同样核对错误/警告/modified。
5. `document use FG_ID --json`，把 session current 固定为 FG。该命令只改变 session current，不能用它代替 SW 窗口激活。
6. root 在 SW 窗口菜单激活 ASM。调用 `document list --json`，确认 ASM_ID active=true/current=false，FG_ID current=true；全部文档 ID、path 和 modified 保持预期。
7. 第一次且唯一一次前台观察：
   `assembly mate-targets coincident-aligned-component-1 coincident-aligned-component-2 --document ASM_ID --json`。
   若失败，保留首错并结束。若成功，保存完整 snapshot，特别是源文档 stamp、configuration、transform、faces、mates。
8. root 在窗口菜单激活已经打开的 FG 零件。调用 `document list --json`，确认同一 ASM_ID active=false/current=false，FG_ID active=true/current=true。宿主、worker、已打开文档集合保持一致。
9. 第二次且唯一一次后台观察，执行与第 7 步完全相同的 mate-targets 命令。失败立即结束，不回到 ASM 再读，不改变 CommandInProgress，不尝试别的映射接口。
10. 结束后只分析已有输出与 daemon trace，并用文件系统读取再次核对三个输入文件 hash。核对请求中的 QueryInterface.IEntity、BindOfficialTypeInfo.IEntity、原指针保留 guard、OriginalMapped.IsSame、IEntity(original-mapped).GetComponent、owner-IsSame 的到达状态，并确认全部日志 CreateMate / CreateMateData 为 0 次。

## 解释范围

- 前台成功、后台失败，可在该保存装配和同一公开 worker 中定位到前台状态变化的关联。
- 两者成功，仍需审计与新建未保存装配之间的差异。
- 第一次前台观察已失败，则记录该失败，不执行后台观察。
- 这些结果均不单独证明 CI 整组通过，也不自动改变组件归属、几何或后台保护契约。
