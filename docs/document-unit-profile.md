# 扩展文档单位 profile（候选接口）

新增 `document.unit-profile` 读取九字段及完整原始 GetUnits 五个 short、19 项有限联动观察。未知枚举以 `other/native_value` 保留；不填默认值。旧 A17 `document.units` / `document.units-set` 保留。

`document.unit-profile-set` 要求 lease、expected_update_stamp、完整 `expected_snapshot`，包括非目标字段、原始值和联动观察的类型敏感 CAS。相同目标不调用 setter、不标脏。原生 setter 单次执行；False、异常、联动变化或状态漂移保留部分 mutation 回执并停止，无重试或回滚。

**新增公开 changed-write 白名单为空。** 候选精度为 0..8，其余候选目标见 catalog；候选不等于原生验收。内部 `_calibrate_unit_profile` 不注册、不接受公共参数。system 与 scalar 原生写入、跨系统联动、保存重开写入持久性均未验收；不得凭 SDK 生成或 portable mock 成功开放。

## 原生校准分层

分支 `codex/docprops-units-expanded` 手动 `units_calibration=true,native_full=false` 只运行 `units-read-cas-v1`：fresh DispatchEx + PID 排他与空 catalog、part/assembly/drawing 新 fixture、九字段/五 short/联动读、后台拒写、保存 readonly 重开、完整 snapshot 和 part 几何保持。part 输入 40×30×10 mm，独立核 V=12000 mm³、S=3800 mm²、质心 (0,0,5) mm。首失败停止，父看门狗每 native boundary 600s、全组1800s；无组内重启或失败重试。

这个阶段是内部读/CAS 校准，不是公共 CLI 端到端验收，也不产生新的写入授权。后续 scalar/system 诊断应单独制定有限来源与目标，保留 setter 返回值和保存重开证据后，再人工审核精确 domain。不可自动更新白名单。

报告/逐调用 trace/原始 native 文件由 Actions 原产物保存。`swconst-export-reference.json` 仅为既有 TLB 导出参考，不是当前分支 native 测试证据；本轮脚本重新导出与比对字段 IDs。

## 官方来源（2026-11-07 复核）

- [Document Properties > Units](https://help.solidworks.com/2024/english/api/swconst/DP_Units.htm)：九字段映射；三个 mass-property 单位仅允许 Custom。
- [GetUnits](https://help.solidworks.com/2016/English/Api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~GetUnits.html)：LengthUnit/FractionBase/FractionValue/SignificantDigits/RoundToFraction 五 short。
- [SetUserPreferenceInteger](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SetUserPreferenceInteger.html)：文档 Extension 整数 setter，bool 返回。

DP 页面 energy precision 标成 Toggle，与既有 swconst Integer 导出不一致；当前遵循 TLB 读取并在原生阶段校准，不对失败换 API 重试。


## 已批准的单位路线几何复测界限

仅本单位内部校准与public CLI两条路径共用：质心x/y/z逐轴绝对差≤1e-12 mm，不使用相对容差；体积、面积、实体数严格相等并拒绝非有限值。原解析V/S/质心判据不变。raw/hex/delta及exact_equal原样保存，accepted_under_units_centroid_bound单独记录，不把数值非精确相等伪装成精确相等。所有state/identity/lease/stamp/完整profile CAS仍精确；其他路线与通用kernel判据未修改。旧失败原件不翻绿，最终验收依新head实际结果。

## 原定真实写入校准已接入（2026-11-08，未验收开放）

`units_calibration=true,units_write_calibration=true` 显式运行 private 八 scalar/system 有限诊断，精度覆盖已有候选0..8，逐目标记录 before/after/raw5/linkage、native bool/partial 与保存重开原件。公共生产域和system完整后态证据表仍空；CI不会自动填表。只有原件审阅后人工录入精确源/目标域，才可追加 `units_public_acceptance=true` 运行新的公开 changed-write 入口；空表在私有native setup前拒绝。公共system的host与结果语义均要求完整受审后态精确匹配，scalar非目标保持规则不变。

详见 [本轮实现、路由和剩余验收](verification/units-write-calibration-2026-11-08.md)。实现和portable通过不等于本路真实写入、写持久性或全系列发布完成。
