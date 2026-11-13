# 部分角度方向单例：准备完成，原生未执行

此增量沿用 `codex/swcli-revolve-feature-next`，承接首轮
`02e55ca7a77ec5abb216648c23efc43a3b21f4ee`。仅补充 harness、定向路由、离线失败控制，
不改变产品代码、公开白名单或现有360°原件。实现授权不等于原生运行许可；本轮没有VM、COM或原生dispatch。

## 独立范围与入口

- `native_revolve_direction` 默认 false；开启时只接受 `workflow_dispatch`、
  `refs/heads/codex/swcli-revolve-feature-next`、`revolve_direction_head` 的完整40位小写SHA与所选 `GITHUB_SHA` 精确一致。
  `native-profile` 无secret前置先拒绝错误ref/head及任何其他已知native/units组合，之后才能进入私有安装流程。
- 独立 `.github/workflows/revolve-direction-next.yml` 复用既有安装/清理脚本与原件约定，主 `ci.yml` 原文不变，单例有独立 `swcli-revolve-direction-${github.ref}` 并发组，
  `cancel-in-progress=false`。普通push只运行无secret的route job，prepare/native均被手动条件挡住；full/tag/旧360°路径与原并发组保持原条件。
  独立workflow只有两个dispatch输入，现有CI的25输入不增，仓库权限只有contents:read，没有release job。
- 新入口 `scripts/ci/verify-revolve-partial-next.py`。parent/worker均核checkout head、相关源码及harness工作树干净、
  已安装SWCLI整个Python模块集合及各文件SHA256与checkout一致。错误源在native backend导入前拒绝。
- **唯一假设**：front原点平面、bounds `[0,-5,10,15]` mm、左边轴从 `(0,-5,0)` 指向 `(0,15,0)`、
  90°、局部从+X转向-Z（rotation_sign=-1、axis_direction=+1）。这是预声明数学假设，尚非SW实测结论。
  在host获取前fsync落盘；无参数可切换符号/角度/平面，无矩阵循环。若轴实际反向或质心不符，停止并保留原件。

统筹后续明确许可运行后，才可在上述分支以精确**最终head**选择：

```
workflow: revolve-direction-next.yml
native_revolve_direction: true
revolve_direction_head: <完整最终head>
native_full: false
```

其他native/units输入保持false；本轮没有执行该dispatch。单例原件成功并经过统筹亲审后，
才另外准备四角度×三平面以及拒写/partial的原生矩阵；当前没有矩阵入口，也没有公共写入开放。

## 执行与证据协议

`gate_support/revolve_direction.py` 是可注入的单例协议；`revolve_direction_native.py` 的native依赖延迟到真实start。
实际backend先要求原生Windows、无Wine、空PID清单、独占fresh host、空文档catalog、SW33.5.0及安装TLB枚举/20参数。
进程身份复用既有 `unit_owned_native.py` 的OS完整路径、文件身份、创建时间和保留handle核验。
不会附着或替换其他host。

每个边界600秒，单例创建/保存/重开整体也有600秒边界，parent给整个worker1800秒。
31分钟step只包围1800秒执行及有界的进程退出观测，不延长CAD业务预算。
创建一次后验证定义、端点顺序、原有空part/单配置/中心矩形守护及sector V/S/有符号质心。
保存新SLDPRT并核字节hash，关闭，只读重开后核可编辑Revolution/被吸收矩形、bounds/frame/轴/定义、
单body、完整健康诊断、解析量、read-only/dirty/edit/selection/前台/原配置及文件hash。
实际回执和测量先落盘再断言。创建后失败保留feature存在性、完整mutation、原错误及cleanup。

- `report.json`：预声明、实际creation、save/reopen、测量与first failure；public/full资格恒false。
- `source-proof-parent.json` / `source-proof.json`：精确源与已安装包模块摘要。
- `boundaries.jsonl`：每个begin/end/error立即flush/fsync；stderr含既有底层native-call trace。
- `host-identity-observation.json` / `owned-host.json`：启动后保留handle及原始进程身份。
- `front-direction-90.SLDPRT`：仅本单例验证及保存到达时产生；report保存SHA256。
- `native-timeout.json` / `group-timeout.json`：超时首因；worker异常退出后的额外进程清理单独记录，
  不覆盖原report。超时落盘失败也不能阻止worker停止。

正常清理仅对本组拥有的文档/host/handle，分别记录异常；已失败的CloseDoc不再重试，继续独立ExitApp清理。
600秒硬退出或1800秒超时后，supervisor只对持久记录的PID重新核验**相同创建身份**再终止，
不搜索替代PID；没有身份或发生PID复用就拒绝终止，保留失败供统筹及runner清理审查。
没有API创建重试、符号回退、rollback、组内host重启或自动扩大域。

## 离线覆盖与限制

纯fake backend及plain-object测试覆盖单次成功协议、错误符号/角度/轴、重开体积/dirty/hash漂移、
创建后原生错误与cleanup叠加、初始/末端/timeout落盘失败、600/1800看门狗、PID复用拒绝、
无完整report的零退出拒绝、已正常清理的业务失败不做二次host清理、精确分支/head和已知scope互斥。
backend的重开定义错误用普通对象验证ReleaseSelectionAccess及部分actual保留；未调用真实COM。

首次全量检查发现共享workflow的25输入上限以及旧并发组顺序保护；最终改用独立workflow并恢复主CI原文，
没有放宽旧检查。[GitHub手动workflow文档](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
说明25输入限制；[事件文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
区分默认分支UI入口与已运行workflow的API/CLI dispatch。当前branch的push只用于轻量注册；实际注册/dispatch可用性
仍须统筹根据GitHub元数据核对，本轮没有通过原生dispatch测试它。

这些只证明离线接线和失败语义。实际SW旋转符号、保存只读重开、native API运行与进程退出仍无新增证据；
尤其不能把fake/backend协议成功视为单例原生通过、四角度矩阵通过或当前发布资格。


实现提交 `b841ef451a0aa671454c6bfee8c05c86bf275596`。
本地完整portable 3002项通过（39跳过，120.001秒）；旋转专项62项、CI回归56项（8跳过）、
旧units并发15项通过，SDK生成/严格类型/33负消费通过；6文件Python3.9语法及全部workflow YAML解析通过。
精确源守护以editable安装做纯文件正向检查，118个Python模块摘要匹配；不能把该结果当成原生wheel或COM验收。
摘要、被测文件与日志SHA256见 [准备证据](../evidence/revolve-direction-preparation-2026-11-14.json)，
原日志在 `evidence/revolve-partial-next/direction-harness-preparation/`（ignored）。
