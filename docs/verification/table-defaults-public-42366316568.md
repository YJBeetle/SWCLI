# 原生运行环境准入修复后的公开验收

[42366316568](https://github.com/YJBeetle/SWCLI/actions/runs/42366316568) 在 `5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b` 完成成功。该提交包含严格 native Windows 探针，CAD 前实际探针检查和公开 gate 均成功。新原始 ZIP 经独立审计通过，装配体/工程图候选 tip `5a4d861d9caf7c4b79ef9f288630aa06247e50d1` 的产品代码与该验收 head 一致，交由统筹本人 review 和合并。零件精确几何仍是系列待完成项。

## 新原件和完整路径

- Artifact ID `13571309953`，名称 `table-defaults-public-42366316568-1`。
- 官方 digest 和本地 ZIP SHA256 均为 `337b23a2c96913725b3281a12325d918c539753e7a96fe6da4fabca6ed74f17b`。
- 原始 ZIP `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42366316568/original.zip`。
- 完整解压原件 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42366316568/extracted/public/`。
- 官方 `run.json`、`artifact.json`、`artifacts.json` 和 `jobs.json` 位于同一 evidence 目录。
- 独立审核结果 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42366316568/independent-audit.json`。
- 所有保留 run 的 artifact/ZIP 路径和摘要 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42366316568/original-evidence-manifest.json`。

## 新 head 的自验结果

SOLIDWORKS 33.5.0，装配体和工程图共 8 项精确转换，包括目标值 no-op。独立审核重新从本轮 ZIP 提取并计算 57 个表格请求、8 次 setter、274 次偏好读取、120 条 CLI 事件及其 240 条 started/completed 日志、4 条 SDK 和 4 条 MCP bridge 回执。lease/stamp、完整 CAS、无关字段冲突、后台目标、另存、新 handle 只读重开和零件写入拒绝均符合预期。

全部 native trace 来自同一 worker，应用偏好 setter 为零。最长 native 调用约 1.847 秒，trace 组跨度约 39.400 秒，gate 历时约 40.101 秒。10 个创建/打开的 handle 全部关闭，最后 catalog 为空，wrapper 确认 daemon 退出。

8 项破坏/替换探针全部被拒绝，覆盖文件摘要、SDK 回执、case 完整性、trace 摘要及顺序、全局 setter、旧 ZIP 替代和错误 head。脚本和结果位于新 evidence 目录的 `audit-corruption-probes.py` 和 `audit-corruption-checks.json`。

本轮全部原始文件 SHA256 如下。

| 原始文件 | SHA256 |
| --- | --- |
| `public/daemon-stop.json` | `d0da863fef37ad6528eb12fd6ded544c6e714a8e27ef1223111bd9d3767623fa` |
| `public/daemon.native.stderr.jsonl` | `00815ec92f37720ff090c7e32e43cc411d43e940a4f0fc9e97177a30aacaf572` |
| `public/daemon.stdout.jsonl` | `57bf805d8c89e9b64dc99c8946bcd9474e15e429ceb557f8ef6e33b2606ec246` |
| `public/gate/public-table-defaults.SLDASM` | `cb168980f9a68205a6b89560128705cb57c03bc897044c63701fc8bafa487401` |
| `public/gate/public-table-defaults.SLDDRW` | `c3a186b5cf57f0f61fbd31995e9291a972c0f3857659599ca8560dfd502679d6` |
| `public/gate/table-defaults-public-events-modeling-smoke-d7934c97207b.jsonl` | `59f51087c36b8c06234f1efec912e2a382b9753b756d3fa363bdbdf18fb6d1c0` |
| `public/gate/table-defaults-public.json` | `2d93886d6ceeda7afb8ca911d50f848b5bfbf7ab7ed388e6efb39589b96bf958` |
| `public/gate.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `public/gate.stdout.log` | `2be1cf8b0ea582db1af849412cbf25bdf855bf21e3c306a2eb5bce187ac11573` |
| `public/wrapper-result.json` | `f25b7bea2105fa77f47c0edf95eb206be628bc0c3a02677bfce019623cdf8ae3` |

## 可复跑独立审计

本地忽略目录 `.venv` 已安装当前项目及 jsonschema。以下命令仅解压校验原件和比对源文件，输出本轮审核 JSON。

```sh
/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/.venv/bin/python \
  /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/audit-table-defaults-public-42366316568.py \
  --public-evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42366316568 \
  --internal-evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42301331238
```

审计固定本轮 run/head/artifact/digest，旧 ZIP 无法替代。内部 `42301331238` 原件仅作为被引用的 source fixture 和初值输入。`current_product_matches_audited_head` 单独报告当前产品树是否仍与已验 head 一致，后续零件校准脚本变动也会反映在此字段。

## 保留的全部原件链

所有目录均位于 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-<id>/`。

| Run | Artifact ID | 原始 ZIP SHA256 或日志摘要 |
| --- | --- | --- |
| `42261481759` | 13527120695 | `a482eb9aed4184ed6a6150130894dc8b29a3717c1d44d3bfaf4139181eb49375` |
| `42266161306` | 13528935364 | `2a6ba4b978bd84f2b2dd0f7db3b3ecfe6e5dbaf4b9b880151f14e609df2a556b` |
| `42269888379` | 13530843312 | `34b9c6fe5950da54da469db49db91990585dfec73a2dd08426a34ee6723acdd4` |
| `42279939696` | 13536576827 | `af6372f11df6322a14a254e3bec5d025fff5ce2ce294849e3d8f0e05bcb94894` |
| `42301331238` | 13545815581 | `7e473478064998f3e116329d29007f8f21c441be74d7827a7d3bfbc90fc2f4f6` |
| `42305463102` | 无 artifact，保存 failed-step.log | `fc1954faed7fdb6d394a0e2d0d88a957a788d355456ab44cfe29b52f97e982f0` |
| `42361458023` | 13569274991 | `f1877623dfc909900ba9784644e4266809d67afd68dd109feee49f42c82e66ad` |
| `42366316568` | 13571309953 | `337b23a2c96913725b3281a12325d918c539753e7a96fe6da4fabca6ed74f17b` |
