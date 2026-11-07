# 单位九字段：原定范围收口清单与最小剩余验证

本文件记录2026-11-07 / `73e25fca`的收口快照；后续实现见 [2026-11-08进展](units-write-calibration-2026-11-08.md)，尚未取得新增原生写入完成结论。

2026-11-07；分支 `codex/docprops-units-expanded`。本清单只展开原 `HANDOFF.md` 的 read → scalar → system → 人工有限 domain → public 验收步骤，不新增字段、linkage、候选值或任意系统组合。它是未完成工作的清单，不是新 native 通过记录，也不授权合 main 或发布。

## 当前结论

**本路尚未完成九字段有限读写，不能按本系列完成项发版。** 新 public run [42361728509](https://github.com/YJBeetle/SWCLI/actions/runs/42361728509) / 业务 head `577309005a858c11543b5def253dca36e5d0c598` 的原 ZIP 已独立复审通过；仅证明下面的已完成子集。`CALIBRATED_UNIT_WRITES=()` 仍空，九字段 changed-write 的公开完成数为 **0/9**。

此前“精确可合子集”仅指已验收只读/noop/拒写实现可交统筹技术 review；它不代表本路完整读写、全系列完成或可发布。原计划 scalar/system/写入持久性缺口仍属于本系列，不默认移到下次发布。

## 已完成、实现中与未完成

| 项目 | 当前状态与证据边界 |
| --- | --- |
| 九字段 + raw GetUnits 五 short + 19 linkage 读取 | 已完成本轮 Windows/SOLIDWORKS 2025 三个新 fixture 的原生/public 读取及 readonly 重开；part/assembly 源 MMGS，drawing 源 IPS，不外推任意文档状态。 |
| 公共同值 noop | 原生仅 `linear.precision=2`，三类各一次；零 setter、不 dirty。其他字段 noop 有 portable 实现检查，不能称已逐字段 native 验收。 |
| lease/stamp/完整 snapshot CAS/readonly/闭域拒绝 | 三类各五个预期 public 拒绝，拒绝后状态/profile 保持；本轮非 Custom 源的 changed 请求先被来源条件拒绝，并未原生走到 Custom 源的空白名单检查。 |
| 只读路径文件与宿主生命周期 | source/copy 原始 hash、保存/关闭/fresh readonly 重开及 owned PID 单次退出有原件；这不是 changed-write 的保存持久性。 |
| 单次写与 partial 回执等实现 | 既有 private setter primitive、公共路由与 portable/mock/真实 handler-worker 故障测试已实现；本轮未发生单位偏好 setter，不能当作原生写入或原生故障注入证明。 |
| 八个 scalar 的真实写入与保存重开 | 未完成。现有 CI `calibrate-document-unit-profile.py` 没有调用 `_calibrate_unit_profile`，只执行 read/CAS；不能靠重跑原 read gate 补齐。 |
| system 有限切换、联动与保存重开 | 未完成；private 当前只核目标 system round-trip，尚无经过校准的完整联动预期。公共调用还会在 `require_scalar_source` 无条件拒绝 system；仅填白名单不能完成功能。 |
| 人工启用有限 domain + public changed-write 验收 | 未完成；没有一个已启用或原生验收的新增 changed-write domain。 |
| 全系列集成/最终发布 | 未完成；交统筹本人 review/集成及最终 gate。本分支不合 main、不打 tag、不发布。 |

## 九字段逐项清单

以下九字段的读取均有上述三个 fixture 证据；**每行 changed-write、写后联动及保存重开、公共 changed-write 验收均未完成**。目标来自原交接计划/catalog，不能把“可解析候选值”写成已支持。

| 字段 | 原定有限写目标 | 余下的字段专属条件 |
| --- | --- | --- |
| `system` | MMGS ↔ CGS / MKS / IPS / Custom | 冻结实测源系统，独立校准每个已声明方向；完整九值/raw5/19 linkage 联动必须有受审预期，补齐公共有限 system 策略。不得外推任意标准对。 |
| `linear.unit` | `mm` / `inch` | 已有 Custom 源；其余八字段及 linkage 精确保持；raw5 仅 length_unit 可随目标变化。 |
| `linear.precision` | 原 native 计划端点 `0` / `8` | 已有 Custom 源；raw5 仅 significant_digits 可随目标变化，其余非目标精确保持。现有 `2` noop 不证明任何端点 changed-write。 |
| `angular.unit` | `degrees` / `radians` | 已有 Custom 源；其余八字段、raw5、linkage 全部精确保持。 |
| `angular.precision` | 原 native 计划端点 `0` / `8` | 已有 Custom 源；其余八字段、raw5、linkage 全部精确保持。 |
| `mass_properties.length_unit` | `mm` / `m` | 已有 Custom 源；其余八字段、raw5、linkage 全部精确保持。 |
| `mass_properties.mass_unit` | `g` / `kg` | 已有 Custom 源；其余八字段、raw5、linkage 全部精确保持。 |
| `mass_properties.volume_unit` | `mm3` / `m3` | 已有 Custom 源；其余八字段、raw5、linkage 全部精确保持。 |
| `mass_properties.precision` | 原 native 计划端点 `0` / `8` | 已有 Custom 源；其余八字段、raw5、linkage 全部精确保持。 |

catalog/schema 接受精度 `0..8`，原 native 计划的 `0/8` 是最低端点诊断；端点通过不能开放 `1..7`。若既定交付按 catalog 的 `0..8` 描述，则 `1..7` 在完整收口前仍缺各自的写入/持久性/public 证据，不能通过改称端点支持而悄悄缩减或后置。完成报告必须列精确可写值与源域，不能笼统称全部精度或九字段任意读写。三个 mass-properties 单位有 Custom 限制；当前其他 scalar 也按原保守计划限已有 Custom，绝不在 public 自动切 Custom。

## 原计划内最小剩余验证（按依赖顺序）

1. **把已有 private primitive 接入有限 scalar 诊断。** 在自己新建、独占的 fixture 上显式切 Custom，完整保存这个准备步骤的实测前后九值/raw5/linkage、身份/上下文和模板 hash；不能伪造默认源或隐去准备 mutation。八个 scalar 按上表每个预定目标实际发生一次 changed Set；源已等于目标的 noop 不计写入证据。每次冻结完整源 snapshot/type/fingerprint，单 setter、原生返回必须为 True，保留 before/observed/final/partial，非目标遵循现有精确规则。每个不同目标独立保存/关闭/readonly 重开核全 snapshot 和几何；若需继续，只 writable 重开自己的文件。无失败重试、回滚或用新 baseline 吞掉漂移。
2. **独立 system 联动诊断及有限公共策略。** 只用既定 MMGS 双向连接 CGS/MKS/IPS/Custom；输入系统以模板实测为准（本轮 drawing 为 IPS），不得先归一为 MMGS 再隐藏原输入。记录每个方向实际完整联动、setter bool、保存重开持久性；全部 19 linkage 均保留并参与完整 CAS。原 private system 的“只核目标 round-trip”不足以验收，公共路径也不能复用拒绝所有非目标变化的 scalar 规则。需依据已审原件制定精确源/目标允许的完整联动结果，保留状态/身份/CAS 守护；缺失或不符即拒绝，不能移除观察项或放宽比较。可按原计划先 part，再明确扩 assembly/drawing；part 通过不能代替另外两类，未测类型必须继续记未完成。
3. **审原件后人工启用精确 domain。** 每条绑定 `(document_type, source_snapshot_sha256, field, native_target)`，仅来自已确认的 native 文件/报告/源码 head 与对应完整联动，不从 CI 自动生成生产授权、不以类型或目标通配。对固定源的有限支持要写清楚；未覆盖源、未知枚举、不一致小数 raw5 仍拒绝。scalar/system 原件失败时保留首因和 partial，相关能力仍列本系列未完成，不能称其已做完再后置。
4. **在实际启用域上跑公开 changed-write。** 现有 `verify-document-unit-profile.py` 标明 `changed_write_acceptance=False`，只读 gate 不能替代此步。通过真实 CLI → daemon/registry → host，在合法 lease/stamp/完整 snapshot 下对每个要声明支持的有限 domain 做非同值写，核 changed/mutation/native bool/完整读回、后台及 peer/身份/config 守护、dirty、保存/关闭/fresh readonly 重开和几何。同 head 保留已有 noop、lease/stamp/CAS/readonly/未校准源域拒绝，特别补已有 Custom 的白名单外请求；所有拒绝保持零 mutation。需要声明三类型写入就必须有各类型各自证据，不能从 part 或 private 结果外推 public。
5. **绑定新 head 取原件并交完整清单。** 对实际业务改动跑关联 portable、已有 partial/guard 回归、SDK generated/type 与 CI 安装检查；只触发必要的精确 head 原生运行。下载该 run 的原 ZIP，核官方 artifact/head/digest、源码、模板/native hash、原报告/trace、有限域与 public 事件及预算/owned 退出；旧 read gate 原件仅保留其原用途。原件审计与公共逐域通过后，才逐项把上表改为完成并交统筹集成；不能用 workflow 绿灯替代缺失 case。

上述最小验证只覆盖原来预定的字段/端点/有限系统方向，不扩成整页、所有来源排列或全部单位枚举。新增实际写源后，旧审计器会按设计拒绝把新源绑定到旧只读 head；必须保留旧原件结论，并为新证据明确新的 run/head/domain 关联。

## 始终保持的约束

每 native call ≤600s、每组 ≤1800s；父 watchdog 与 durable begin/end/error、首失败停止、无 API 重试/回滚/组内重启。只操作自己新 DispatchEx、before PID 不含新 PID且空 catalog 的 host；一次 owned Exit/stop + retained process handle 退出确认，只关闭自己 unique identity 的文件。绝不接触占用中的本地 VM、其他 worktree、DockerSW/MacSW、main/tag/release。

V/S 严格数值相等、实体数严格 int 相等；仅单位路线质心 xyz 各轴绝对差 ≤1e-12 mm，无 relative tolerance。原解析几何检查、raw/hex/delta/exact_equal 保留，所有状态/身份/完整 CAS 精确守护不变。本清单不批准通用 kernel 宽容差，也不放宽任何 V/S、状态或联动断言。

本轮仅复审已有新 public 原件并澄清交接：标准库审计退出0、audit_success=true、10项负向/边界自检通过；当前操作源仍与验收 head 完全相同。没有新增 CI、轮询、代理或产品改动，不能把本清单当作上述剩余工作已经执行。
