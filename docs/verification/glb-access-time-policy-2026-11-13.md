# MarkingJig 显式访问时间策略候选（2026-11-13）

状态：继 `2b024c18436939c81ca9305c1d032620f9bcad65` 初版之后，按统筹明确的阶段合同做源码和离线测试修订。仅交精确提交亲审，未获得/执行新 VM、CAD、OpenDoc 或导出；未改产品或 CI。初版方案中“访问时间仍严格拒绝”的保守边界由本页明确策略替代；旧失败原件保持不变。

## 策略范围

- 公共 `file_forensics.collect(..., access_time_policy='strict')` 通过一个 keyword-only 参数复用原取证代码，默认 strict。独立旧工具的 CLI 没有增加 record-only 开关，仍走默认严格策略；相同访问时间变化仍失败，原始错误语义及自身句柄清理保持。
- 只有显式分阶段 `--mode probe --phase-policy opening-transition-probe` 路径选择 `access_time_policy='record-only'`。只投影掉比较副本中 Python path/held 的 `st_atime_ns`、Win32 held/reopened 的 `basic.LastAccessTime`，以及与这些原值一致的派生 Python cross-channel 差异摘要里的 atime 项。原始记录、原始差异及全部访问时间原值均保留；不清除或替换原记录、不转换单位、不设容差，不抑制 OS 访问时间更新。
- 此投影覆盖建立句柄期间、单次读取前后、不同读取渠道、打开前后、模型完整准入、封存已加载基线、后续观察及失败后 OS 检查。访问时间变化只记录，不能单独导致模型阶段准入或稳定性失败。
- 全部既有 `stable_file` 字段保持原严格比较；这些字段本来不包含访问时间。Win32 完整卷序号/128-bit ID、CreationTime、LastWriteTime、ChangeTime、attrs、大小、链接数、allocation、delete/directory 标志、原始 opened path 及未知新增字段均未豁免。同名字段出现在未列出的结构中也不被投影。
- 原跨 Python path/held ctime 特例保持已审合同。开阶段仅 top held ctime/Win32 ChangeTime 的完整窄证据可以标记 `opening-metadata-transition`；record-only atime 不计入该完整证据，也不能补足缺失的 ctime/ChangeTime。任何非 top 的非访问时间变化、已加载阶段 ctime 漂移仍失败。
- readonly warning2、完整引用/模型/几何准入、原始 copy 基线不可替换、已加载基线只能封存一次、0 export 与 invoke 提前拒绝，均保持初版合同。Mac 11 原件整窗口检查仍须由主机侧独立归档，本轮未重新验收这些原件。

## 原始记录与比较结果

`file_phases` 使用 v2 schema，明确 `access_time_policy='record-only'`，每个 frame 和每份 collector 记录也标明策略。

| 记录位置 | 含义 |
| --- | --- |
| collector `python_path_before_open`、`snapshots` | 完整原值，访问时间原样保留 |
| collector `path_establishment_changes` | 建立句柄期间的完整 raw 变化 |
| collector `same_channel_changes` | 一次全 SHA 读取前后，各渠道完整 raw 差异 |
| collector `stability_same_channel_changes` | 按明确策略投影后的准入比较结果 |
| snapshot `raw_python_cross_channel_differences` | 完整 raw path/held 差异；阶段检查再次核实与原值一致 |
| frame `native_channel_changes` | Win32 held/reopened 的完整 raw 差异 |
| `file_phases.opening_raw_changes` | 开前/开后完整 raw 差异，含访问时间和原始派生摘要 |
| `file_phases.opening_changes` | 仅按策略投影后的变化，执行 top ctime 窄准入规则 |
| frame `baseline_raw_changes` / `baseline_changes` | 相对临时或已加载基线的 raw 差异 / 策略投影比较结果 |

用于比较的副本不写回 raw。未知字典字段变化也完整保留 before/after 并拒绝，不能借新增字段扩展允许集。CLI 的阶段策略和回执审查要求一致；缺失或错误 access_time_policy、未完整准入/封存、raw frame 不完整及出现 SaveAs 都不能形成成功回执。

## 离线验证

- MarkingJig **103 项**通过，0.335 秒：原控制 45、取证 26、阶段 32。原有 21 项独立取证严格测试继续通过。
- typed bridge **23 项**通过，0.010 秒。
- 同一组访问时间变化：旧默认 strict 失败，新阶段 capture 成功；两次所有 raw snapshot 和完整 raw delta 逐值相等，访问时间前后值完整保留，新策略的 stability delta 为空。
- 模拟建立句柄前后、Python path/held 访问时间不一致，以及 Win32 held/reopened 访问时间不一致，record-only 均保留原值和差异；未知策略在任何打开前拒绝。
- 完整零导出模拟 probe 中，每次采集均产生访问时间漂移，仍经过完整模型/引用/几何检查和唯一封存的已加载基线；所有 raw drift 可见，策略投影后非访问字段必须不变。随后 ctime 漂移仍失败。
- 逐项故障注入覆盖其余全部 Python stat 字段、Win32 Basic/Standard/完整 ID、同名未知字段、top ctime 缺项、非 top 变化、伪造原始差异摘要、失败回执及 invoke 拒绝。投影不修改 raw 对象。
- 原 NativeBackend、Win32 ABI 结构/只读标志、旧 standalone CLI、`open_readonly` 和控制逻辑均未改变；没有复制旧 collector 或在执行路径 monkeypatch 策略。
- 当前 collector 源码 SHA256 为 `7a1fd66ded00560187d36dfead6cca82911d610cdbfd73631ff9fbfa92c737f5`。旧源码 SHA `ef1fc427b36f8fcbd05972515db8580cc1c50e8447e444941c6fd1fda86e07c5` 仅属于既有历史执行及初版记录，不再冒称当前源码。
- 首次 probe audit SHA 仍为 `f6c8b96197916a504a2705b7888ed877ffad3fac383bc17af1c09029ba47081b`；OS audit SHA 仍为 `03b6f24ecd4817e5db15421ce3280b09b20c7764eb24eba6cb2ab0cfa9c26fb3`。未重写旧证据或重复独立 OS-only 试验。

这些是明确阶段合同的源码与模拟验证，尚非实际装配体完整引用、原生 OpenDoc 或 GLB 导出验收。
