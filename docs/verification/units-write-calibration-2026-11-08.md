# 单位原定写入范围：实现与首轮原生诊断

2026-11-08；持久工作树 `docprops-units-expanded/SWCLI`，分支 `codex/docprops-units-expanded`。按统筹继续指令落实原清单，不再停在文档。当前仍没有新增原生写入通过结论，生产 changed-write 两份证据表均空；不合 main、不发布、不操作本地 VM。

## 本轮实现

- 原 calibration worker 增加显式 `--write-calibration`，共用既有 fresh DispatchEx/PID/空 catalog、600 秒 native /1800 秒整组 watchdog、durable 原件、首失败停止及单次 owned Exit/句柄确认。默认 read/CAS 路径保留。TLB 导出和单位 adapter 的 IsSame 同样逐边界记录；报告绑定实际运行源码 SHA、swconst SHA、原生模板及文件 SHA。
- 新 `scripts/ci/gate_support/unit_profile_writes.py` 真实调用已有 private setter：八 scalar 的既有候选逐目标 changed Set、完整九值/raw5/19 linkage、bool/partial 与上下文守护、每目标保存/关闭/readonly 重开、只读拒写、计划内 writable 重开及最终全文件 hash。mutation 前先持久化源完整快照/fingerprint、源文件复制/hash、身份/状态及预定目标；失败没有 API 重试、回滚或组内 host 重启。
- 精度诊断覆盖现有 catalog 的 **0..8**，不是凭 0/8 端点外推中间值；其他原定目标不变（mm/in、degree/rad、质量属性 mm/m、g/kg、mm³/m³）。每字段把当前目标排最后，避免把 noop 计为 changed-write。每类型 37 个 scalar 目标。
- system 只允许 MMGS 双向连接 CGS/MKS/IPS/Custom 的八个方向。Custom 准备步骤单独记录实测初始系统：MMGS→Custom；IPS/CGS/MKS 先走已声明的→MMGS，再→Custom；没有隐藏源模板系统。三类型分别跑完整原定方向，不从 part 外推另外两类。若模板仍为先前的 MMGS/MMGS/IPS，总计 139 个预定步骤（包含4个准备步骤），不是139项已通过。
- 公共 system 不再只有无条件拒绝的占位实现：必须同时有精确 `(document_type, source_snapshot_sha256, field, native_target)` 和人工受审的完整 after-snapshot SHA。host 与 result schema 都核精确完整联动；缺少、重复、不符或非 MMGS 有限方向均失败。当前两表仍空，未开放任何域。scalar 保留所有非目标精确不变，并补上目标与 GetUnits 对应成员必须一同 round-trip 的检查。
- 新 `verify-document-unit-writes.py` 接真实 installed CLI → daemon/registry → host 的公开验收入口。开启前检查三类型、原定 scalar 候选和八方向完整/不重复、源链、每步已审精确域/完整后态及原始文件 SHA；逐域核 noop、合法 token 的竞争 session、stamp、非目标 linkage CAS、实际 Custom 源白名单外拒绝、changed 写入、保存/readonly 重开与原始几何。完整通过前 `changed_write_acceptance=False`；合成单测不会写生产证据表。

## CI 路由与本轮顺序

| 输入 | 作用 |
| --- | --- |
| `units_calibration=true,units_write_calibration=false,units_public_acceptance=false` | 既有内部 read/CAS。 |
| `units_calibration=true,units_write_calibration=false,units_public_acceptance=true` | 既有公开 read/noop/CAS。 |
| `units_calibration=true,units_write_calibration=true,units_public_acceptance=false` | **本轮必要的 private finite write calibration**；没有公共授权。 |
| 三个 units 输入均 true | 仅在人工审原件并填生产精确域及 system 完整后态后，才可跑新的 public changed-write；空表会在 Ubuntu preflight、私有 native setup 前拒绝。 |

仍只允许本分支 workflow_dispatch，和 native_full 互斥，不扩大 PR secret 入口；manual units 继续使用本分支独立并发组，其他 full/tag/release 原规则保留。公开验收复用既有一次 owned daemon、单次 stop 和 retained native process handle 等待退出，不做失败重连/重启。

本轮先提交/推送实现，经便携检查后仅触发一轮 **private write calibration**；启动正常即保存一次 run/head/输入快照结束，不持续轮询。其原 ZIP 尚待后续实际完成时审阅。只有原件确认每域 setter、完整读回/联动、保存重开、严格几何与预算/退出后，才人工填写有限白名单，再对包含白名单的新业务 head 做一次必要公共验收。不能把内部校准或合成 gate 成功标为九字段 public 写入完成。

## 验证边界

- 新单测以实际 parser/protocol/schema/公共 gate 验证三类型139步骤，另有 native 端口模拟验证预先持久化、单 Set/False 首停、源覆盖/readonly 漂移、关闭后不查询旧 COM handle；system 完整后态每成员漂移、白名单缺失/重复/错域、scalar 目标/GetUnits 不一致均拒绝。这些都是 portable 合成证据。
- SDK generated/type 与 Python3.9 AST/YAML 检查有本地结果；完整 suite/精确 head/run 的最终记录追加到 `WORK_HANDOFF.md`。首次临时环境未安装 SWCLI 导致 isolated `-I` 子进程 import 失败，已通过安装当前 editable package修复环境；该首次环境失败保留了工具输出摘录，不冒充完整原 stdout；最终全套通过原始日志单独保存。
- V/S 严格相等，solid count 严格 int 相等；仅质心逐轴绝对差≤1e-12 mm，无相对容差。独立解析盒体 V=12000/S=3800/质心(0,0,5)、raw/hex/delta/exact_equal 及所有 state/identity/CAS 守护保持。

旧 run42361728509 的读/noop/拒写通过仍只绑定旧业务 head5773090；本轮产品/脚本已改，旧独立审计器按设计不能证明当前操作源。这不翻转旧原件，也不借用旧绿灯为本轮真实写入证明。九字段 public 写入及本系列完整交付继续列未完成，直至真实校准、人工域和新 head public 原件齐备。

本地最终验证：Python3.14.10，完整1918项/51.783秒通过（32 skipped），关联55项通过；SDK generated/strict6文件及8项负向typing通过；全部src/CI/tests以Python3.9 AST解析，workflow YAML解析及两个新模式`-I --help`导入通过。元数据与原始日志路径/hash见 `docs/evidence/units-profile/write-implementation-2026-11-08/validation.json`。这些证据均不代表native。

实现业务head `4f20723116103c6e5f43def9f3d42b5a91372903` 已推送；唯一private校准run [42406393957](https://github.com/YJBeetle/SWCLI/actions/runs/42406393957)。参数与原始一次快照在`docs/evidence/units-profile/write-native-42406393957/`：精确head已核，in_progress；route/wheel通过，Win3.9/3.14前置检查运行中，native尚无结果。本轮遵守正常一次快照即停；不持续查询。此后的交接提交仅docs/metadata，不改变该run操作源。
