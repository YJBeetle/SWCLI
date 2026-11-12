# MarkingJig 分阶段零导出诊断候选（2026-11-13）

状态：仅方案、私有诊断代码和离线模拟测试。未执行新 VM、OpenDoc、CAD、导出或独立 OS-only 试验；未改产品、CI、typed bridge。需统筹亲审后另行决定是否分配执行窗口。元数据变化是取证结果，不单独归因为产品 API 失败。

## 原件与已知边界

- Mac 原件固定 10 个 native 文件及既有 GLB，共 11 个文件。原始 inventory 保留不改，SHA256 `d7db20f8041424115a97b91376001be759b32fad6e5faa2cc405fe971a13185d`。已有 `--verify-originals` 按原完整 `stable_file` 记录检查 SHA、大小、路径/句柄身份和所有既有元数据字段；未来试验必须由主机侧在整个窗口前后执行并归档结果，Windows runner 无法自行证明 Mac 原件状态。本轮没有新原件验收结果。
- 私有 Windows copy 的 `WorkingCopy.before` 永不替换。每个阶段采集完整 SHA 和三渠道原始数据，Python dev/ino 对应 Win32 卷序号和完整 128-bit FileID；身份和内容约束跨整个试验，不能在打开后重置。
- 原严格模式仍是默认 `--phase-policy strict`，旧失败证据未改。首次实际 probe 在 OpenDoc7 后观察到 top 的 held ctime 变化；独立零 CAD 试验只观察到 atime 变化，不能据此推定前一次变化原因或声称没有中间写入。
- 装机副本已由统筹提供，本地重核：`vm-installed-swconst-20261112/swconst.tlb` SHA `95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6`；PIA SHA `1afe845af233292fe22e58a2b893d6065f36cd85f2728866011ad10771b98fa9`。沿用已审 readonly warning2 窄准入；实际 TLB 枚举严格读取仍是将来执行时的前置检查。

## 预选模式与阶段合同

新增显式选择 `--mode probe --phase-policy opening-transition-probe`。此组合只能零导出；与 invoke 组合在任何原生加载前拒绝。既有 strict invoke 的旧路径保持原合同，不因本候选获得新执行授权。

1. **Prepared / 开前**：严格核对原 `WorkingCopy.before`；为每个选定文件记录两轮原始 Python path、Python held 和 Win32 held/重新按路径打开的信息，夹住一次有界全文件 SHA 读取。每份采集前后由既有 `stable_file` 完整记录包围，任何采样内变化、原始渠道不一致或关闭错误均拒绝。
2. **Opening**：一次原 `open_readonly` 序列，包括既有 spec 设置/读回、唯一 OpenDoc7、Error/Warning 及必要的 warning2 三项临时只读检查。之后立即进行同一 copy 的完整采集，在首次完整模型观察之前完成。即使打开返回失败或抛错，也尝试一次开后采集；元数据采集错误单列，保留原始打开首错。
3. **Opened, not admitted**：逐字段比较开前和开后。任何内容、物理身份、属性、birth、size、mtime、非 top 文件变化或未知新增字段均拒绝。top 仅允许已观察到的 held ctime 与 Win32 ChangeTime 同时变化：原 `stable_file` 的 handle_before/after ctime、两轮 Python held ctime、两轮 Win32 held/reopened ChangeTime 必须形成完整变化记录。raw path ctime 不在允许集。原始 Python 跨渠道差异摘要作为派生字段完整保留，并校验其与实际 raw 字段一致；支持开前两渠道 ctime 原本相等的情况。分类仅为 `opening-metadata-transition` 或 `opening-metadata-unchanged`，不归一化、不转换时间单位、不设容限、不推断原因或写入历史。
4. **Complete admission**：开后采集只作为临时检查点，尚未建立已加载基线。沿用完整 Observation：实际 readonly/clean/full、host 身份、配置、编辑状态、完整文档/组件/虚拟所属关系、现代依赖双清单及几何均必须通过。观察前后所有字段相对临时检查点严格不变；观察期间再次发生 ctime 变化也拒绝。失败不得建立已加载基线。
5. **Loaded baseline**：只有完整观察成功后才再次采集，必须与开后临时检查点逐字段严格一致，然后封存一个独立、完整的已加载基线。原开前基线和开后变化仍在报告内，不写回 `WorkingCopy.before`。随后再做一次完整 Observation，与首次完整模型观察逐字比较；所有 OS 检查及最终失败后 postcheck 都相对已加载基线全字段严格比较。
6. **Probe completion**：export_attempts=0，原生 trace 无 SaveAs；成功回执必须有两份完整模型观察、有效且完整的阶段记录、已封存基线和无清理错误。本候选无分阶段 invoke/export 实现；将来如获授权添加，其导出前后必须复用同一完整已加载基线，任何 export-stage ctime 漂移均失败，禁止重新封存基线。

## 访问时间的保守边界（需亲审）

原 `stable_file` 没有 atime 字段，但原始三渠道取证包含 Python atime 和 Win32 LastAccessTime。统筹合同仅明确允许 top held ctime/ChangeTime 的开阶段变化，因此本候选**没有自行扩大豁免**：直接复用已审 `file_forensics.collect`，原始访问时间在采样内、跨打开和已加载阶段仍全部严格比较。重读本身也可能伴随 OS 访问时间更新；本候选不会抑制这些更新，也不能保证越过上次的 atime 首停。

这是一处明确保留的保守边界：若统筹希望 atime 只做记录、而保护范围限定为原 `stable_file` 字段，需要先明确独立合同并亲审代码；当前候选没有这样放宽。没有修改旧取证器、抹掉 atime、重复 OS-only 试验或宣称稳定窗口已经通过。

## 离线验证

- MarkingJig 92 项（原控制 45 + 原取证 21 + 新阶段 26）通过，0.186 秒；新阶段测试含多组逐字段负例。
- 原 typed bridge 23 项通过，0.011 秒。
- 新阶段覆盖：完整 top 变化与初始 ctime 相等两种情况、非 top/内容/全身份变化、所有既有 stable 字段、原始 atime 和 native Basic/Standard 字段、缺项/新字段/不完整采样、模型 admission 失败、不完整 loaded 回执、已加载阶段 ctime 漂移、OpenDoc 首错与次级采集错误隔离、零导出与提前拒绝 invoke。
- `file_forensics.py` SHA 仍为 `ef1fc427b36f8fcbd05972515db8580cc1c50e8447e444941c6fd1fda86e07c5`。
- 首次 probe audit SHA 仍为 `f6c8b96197916a504a2705b7888ed877ffad3fac383bc17af1c09029ba47081b`；独立 OS audit SHA 仍为 `03b6f24ecd4817e5db15421ce3280b09b20c7764eb24eba6cb2ab0cfa9c26fb3`。
- 这些是源码/模拟合同验证，不是实际模型引用完整性、原生 OpenDoc、GLB 内容或导出验收。
