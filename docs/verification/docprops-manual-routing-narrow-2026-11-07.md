# 手动native scope与ref窄审查

固定快照：`2026-11-06T18:56:27.255315+00:00`。15路仅只读，不修改其他worktree、不dispatch、不查询或轮询历史CI。

这是静态入口条件分析，假设test/package及非CAD安装、清理、上传成功；“可成功”表示没有必须执行的CAD/拒绝步骤阻止job成功，不表示真实运行已经成功，也不证明原生API行为。完整布尔组合与每步条件、源SHA、文件hash见 `artifacts/docprops-coverage-ci/manual-routing-narrow-20261107/truth-table.json`。

## P1：线型仍存在错误ref下零CAD可绿路径

捕获head `a783b498213597385bed2dfa41cc7cfa1dced2ed`。原路径 `/Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI/.github/workflows/ci.yml`；固定副本 `artifacts/docprops-coverage-ci/manual-routing-narrow-20261107/docprops-line-style.yml`。

精确条件与行号：

- 第248行，`solidworks-e2e.if` 中 `workflow_dispatch && inputs.native_full` 独立放行，无ref限制。test/package没有被线型开关跳过。
- 第396行，public步骤只要求 `inputs.line_font_public && github.ref == 'refs/heads/codex/docprops-line-style'`。
- 第407行，internal步骤只要求 `inputs.line_font_calibration && github.ref == 'refs/heads/codex/docprops-line-style'`。
- 第418、430、444行，property/annotation fixture及full smoke全部使用 `!inputs.line_font_calibration && !inputs.line_font_public`。
- 第477–485行，summary为 `always()` 且 `continue-on-error:true`；任一线型开关true时直接 `exit 0`。后续artifact还包含安装前/后的磁盘JSON，因此不必有CAD文件才能上传成功。

具体组合（静态，不dispatch；假设该workflow随合并/移植出现在非owner ref，不是说当前main已包含这些输入）：`event=workflow_dispatch`，`ref=refs/heads/main`或任意非owner分支，`native_full=true`，`line_font_calibration=true`或`line_font_public=true`。job因full条件执行；两个owner步骤因ref不符跳过；两个fixture与full因线型开关跳过；summary直接返回0。手动选择tag ref同样成立。

正确owner ref下full+任一targeted仍会运行targeted而跳过full；calibration+public同时true会选中两种scope，没有互斥拒绝。这不是“零CAD”情况，但full请求没有对应完整验收。建议私有输入前拒绝混合scope及targeted错误ref，并让job依赖成功的路由验证；保留默认full/tag和release并发策略。

## 公差：同类已知问题，交原owner修

快照head `ce147cba0ba43d57408e6ec12a616aea6c1559d1`。原路径 `/Users/YJBeetle/.codex/worktrees/docprops-tolerances/SWCLI/.github/workflows/ci.yml`，job-if第248行、internal第423行、public第440行、full第448行。

错误ref + native_full=true + calibrate_tolerances=true 时，job由full条件放行，但internal/public/full及两个fixture均不运行；summary直接退出且continue-on-error。这个快照仍复现主对话已报告的问题，未代owner修改，也不推定其稍后修复状态。

## 单位：本轮新提交已阻断旧路径

固定head `9d6b033a221082a515fc75bea3c53360df5a78cb`。原路径 `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/.github/workflows/ci.yml`。这次结果替代较早328cec4及本轮初看时的旧结论。

- 第247–264行新增 `units-route` job，通过 `scripts/ci/validate-units-route.py` 验证互斥、public依赖calibration、精确owner ref。
- 第268行native job的needs包含units-route；第269行要求 `(github.event_name != 'workflow_dispatch' || needs.units-route.result == 'success')`。
- 对应脚本第15–20行拒绝full与任一units开关同时true、孤立public开关、错误ref。已把该脚本按精确head保存为 `validate-units-route.py`，只在本路副本执行纯路由函数；没有在别人的worktree运行测试或写pycache。
- 有效public模式要求calibration=true + public=true + full=false；它不是错误的“双开关”组合。push tag没有manual单位输入，native job允许tag策略正常放行。

## STEP：scope不够明确，但未复现零CAD native-job成功

固定head `2c7108fa5c6c22ebfc9a6c98bdb0a9f67acac58f`。原路径 `/Users/YJBeetle/.codex/worktrees/swcli-step-export-options/SWCLI/.github/workflows/ci.yml`。

- 第248行full路径含 `native_full && !native_step_targeted && !native_step_public_targeted`；两条targeted路径有owner ref限制，internal/public彼此互斥。
- 但targeted job分支及第431、445、455行的targeted/public步骤均未要求 `!native_full`。因此正确owner ref下full+internal或full+public仍运行targeted，而第396、408、422行fixture/full被跳过：不是零CAD成功，但请求的full scope被忽略。
- 错误ref或manual tag上full+targeted：full子句被targeted否定、targeted子句被ref否定，native job整个skipped；internal+public同时true亦整个skipped。便携job成功不算native验收。建议也加私有输入前互斥/错误ref早拒，避免无声跳过。

## 其他分路与tag结论

| 分路（快照head） | 组合审查结果 |
| --- | --- |
| docprops-export-options (`0f4ba7b3d6`) | job-if排除混合scope并限制targeted ref；非法组合native job skipped，不作通过；未见零CAD native成功路径。 |
| swcli-topology-references (`c097909fe0`) | native job中有显式throw互斥拒绝，第266行；错误ref targeted-only不运行native；未见零CAD native成功路径。 |
| swcli-revolve-feature (`3922bee798`) | native job中有显式throw互斥拒绝，第263行；错误ref targeted-only不运行native；未见零CAD native成功路径。 |
| swcli-stl-export-options (`d8df4a874c`) | native job中有显式throw互斥拒绝，第263行；错误ref targeted-only不运行native；未见零CAD native成功路径。 |
| docprops-font-scopes (`e17d7bed81`) | 使用独立targeted job，full job本身保留无条件CAD smoke；未见本问题。错误ref或双开关可产生job skipped/portable-only，不能当native通过。 |
| docprops-dimension-format (`7fd5727b9c`) | 使用独立targeted job，full job本身保留无条件CAD smoke；未见本问题。错误ref或双开关可产生job skipped/portable-only，不能当native通过。 |
| docprops-table-defaults (`b4f79111dc`) | 使用独立targeted job，full job本身保留无条件CAD smoke；未见本问题。错误ref或双开关可产生job skipped/portable-only，不能当native通过。 |
| docprops-detailing (`613ba9861c`) | 使用独立targeted job，full job本身保留无条件CAD smoke；未见本问题。错误ref或双开关可产生job skipped/portable-only，不能当native通过。 |
| docprops-calibration-performance (`ea45651b1a`) | 使用独立targeted job，full job本身保留无条件CAD smoke；未见本问题。错误ref或双开关可产生job skipped/portable-only，不能当native通过。 |
| docprops-coverage-ci (`821ad55688`) | 使用独立targeted job，full job本身保留无条件CAD smoke；未见本问题。错误ref或双开关可产生job skipped/portable-only，不能当native通过。 |
| swcli-assembly-mates (`8a7095cee9`) | 使用独立targeted job，full job本身保留无条件CAD smoke；未见本问题。错误ref或双开关可产生job skipped/portable-only，不能当native通过。 |

实际 `push` tag（refs/tags/v*）没有workflow_dispatch inputs，targeted/public均为false；15路快照下，tag-policy/test/package成功时，full job仍选中property/annotation fixture和完整smoke。未发现由本批新开关造成的push-tag“零CAD成功”。这不等于实际tag或release门禁已执行通过。manual workflow_dispatch选择tag ref则仍带输入，线型/公差上述错误ref风险适用。

## 集成基线约束

只读GitHub commits/main确认远端main为 `83c48301414801540a29aefca2d7d1f9f174d3c1`，提交标题为合入已验收的工程图出详图默认选项；本地共享refs/heads/main仍停在78ebaf6，不在本线程fetch/reset或修改该引用。

主对话滚动合并待合分支时必须保留 `83c48301414801540a29aefca2d7d1f9f174d3c1` 的detailing及 `78ebaf6c24f697007afd8f39d9ea087c3df08257` 先前修复。本路未rebase、合并或验证集成组合，也不据远端提交说明替代原生验收审计。

本报告不改写较早时点矩阵中的历史观测，也不把静态分析、结构完整性、便携测试或job skipped标为内部原生校准/公共验收。
