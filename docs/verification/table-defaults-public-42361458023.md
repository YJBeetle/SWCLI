# 表格默认设置公开原件审计

公开运行 [42361458023](https://github.com/YJBeetle/SWCLI/actions/runs/42361458023) 在 `c95ecdefa40689b2c8723a2e85998bbde2b6633f` 完成成功。其新原件已独立审核。随后统筹发现该 head 缺少 adapter 内的原生 Windows 准入证明，已加入严格探针并等待修复后公开 gate，因此合并状态仍由后续验收和统筹 review 决定。

## 本轮原件

- Artifact ID `13569274991`，名称 `table-defaults-public-42361458023-1`。
- GitHub digest 和本地原始 ZIP SHA256 均为 `f1877623dfc909900ba9784644e4266809d67afd68dd109feee49f42c82e66ad`。
- 原始 ZIP 完整路径 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42361458023/original.zip`。
- 同目录 `run.json`、`artifact.json`、`artifacts.json` 保存官方 head、完成状态、artifact 所属 run 和摘要。`extracted/public/` 保存完整新报告、CLI journal、native trace、两个 CAD 文件和 daemon 退出回执。
- 本轮报告 SHA256 `23793828a6e4eadb663d7d0eb84a9d3cad95eb17c5750c115d2aa06b1a44ce15`。
- 本轮 native trace SHA256 `13ff702fb4dc4124e64a8d9ee66454967e66a997decef61ade01dbb329042ea8`。

## 独立审核结果

SOLIDWORKS `33.5.0` 的装配体和工程图共 8 项写入完成。装配体 template toggle 为 true→false，工程图为 false→true，适用边框均为 thin→normal，并验证目标值 no-op。公开结果保存后以新 handle 只读重开，值和文件哈希匹配。

离线审计从本轮原 ZIP 重新解压，核对 120 条 CLI 事件与 240 条 started/completed journal，重算 57 个表格请求的完整 native 边界、顺序和计数，共 8 setters、274 preference getters，应用偏好 setter 为零。全部 trace 属于同一 worker。最长 native 请求约 1.271 秒，原始 native trace 跨度约 30.157 秒，gate 报告约 30.708 秒，符合 600/1800 秒限制。

审计逐项核对 lease/stamp 请求、完整 CAS 参数及无关字段冲突、后台目标、changed/no-op 回执、distinct save-as、新 handle readonly reopen、4 条 SDK 和 4 条 MCP bridge 回执。10 个创建/打开的文档 handle 全部关闭，最后 catalog 为空，wrapper 确认 daemon 退出。零件读取和拒绝写入单独核对。

原件中的两个公开 CAD 文件为以下 SHA256。

- `public-table-defaults.SLDASM` 为 `6de5cbd349b384ebcd994cd2cbb6a58d3d9fe2d084c08f6ec160e59d17214696`。
- `public-table-defaults.SLDDRW` 为 `18c2ea1be6aed8d499b8e0ae431526bbcd8771369221277beb99b84d8bcf21ce`。

内部 `42301331238` 原 ZIP 仅提供 pinned source fixture 和初值。其 SHA256 为 `7e473478064998f3e116329d29007f8f21c441be74d7827a7d3bfbc90fc2f4f6`。公开审计固定本轮 run/head/artifact/digest，替换旧 ZIP 或其他 head 会失败。

## 可复跑命令

在当前工作树及已保存的原件下执行以下命令，仅进行本地原件和 Git/source 校验。

```sh
/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/.venv/bin/python \
  /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/audit-table-defaults-public-42361458023.py \
  --public-evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42361458023 \
  --internal-evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42301331238
```

结果另存于 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42361458023/independent-audit.json`。审计要求使用的三份 schema/profile 源文件与本轮 head 一致，并报告 `current_product_matches_audited_head`。当前严格 runtime guard 已改变产品代码，该值为 false，修复后的提交需要其自身公开 gate。

8 项原件破坏探针均被拒绝，覆盖 CAD 文件修改、SDK mutation 回执篡改、缺失 case、native trace 摘要或顺序破坏、应用偏好 setter、旧 ZIP 替代和错误 head。结果位于同目录 `audit-corruption-checks.json`，探针脚本为 `audit-corruption-probes.py`。

## 系列边界

本轮公开证据覆盖 Windows `33.5.0` 的装配体/工程图精确转换。原生 runtime guard 的新提交验收和零件精确几何问题继续阻断系列完成，正式发版由统筹在整组完成后请用户确认。
