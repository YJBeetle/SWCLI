# 三类表格内部校准原件核验

[42415716434](https://github.com/YJBeetle/SWCLI/actions/runs/42415716434) / `f1881a7421200e46028652538892c15a366f2ef8` completed/success。Artifact `13591813168`，`table-defaults-internal-42415716434-1`。原 ZIP 与官方 digest 均为 `7e1d8fcd8c1d8b26346024305c0f30a0c77536b2ea4ade06f3c694e382db9e8e`。这是内部 candidate 校准，不是公开 CLI/daemon 验收。

独立完整原 ZIP 核验通过：requested/completed `[1,2,3]`，11项 real changed / 11项 no-op / 11项完整 CAS refusal；11次表格 setter、237次 getter，逐字段核对前读→单 setter→两轮完整回读，no-op/conflict 无 preference 或 dirty setter。每类型首次写入显式 SetSaveFlag 一次，其余字段零次，三份 distinct save-as/只读 reopen 均完成。原件与保存文件共6份哈希逐一符合。

SOLIDWORKS `33.5.0`，单一 worker `4192`、owned host `8968`，唯一 acquire/ExitApp/WaitForOwnedProcess；cleanup errors空，wrapper worker_exit_code=0。单阶段最大约 `3.711325秒`，native trace整组约 `27.843395秒`；wrapper `native_seconds=600`、`group_seconds=1800`。无原生 error frame、无重试、回滚或 host 重启。仅 analytic fixture 准备前的原有草图推断开关 disable/restore 两次，不属于表格偏好写入；表格阶段全局偏好 setter为0。

## 精确域与写入保护证据

| 类型 | Template toggle | 适用边框 | 同值请求 |
| --- | --- | --- | --- |
| part | `True→False` | BOM box/grid `0→1` | toggle False / border1 |
| assembly | `True→False` | BOM box/grid `0→1` | toggle False / border1 |
| drawing | `False→True` | BOM+General box/grid `0→1` | toggle True / border1 |

装配体/工程图仍仅原有8项转换，没有新增逆向、粗线或其他 revision。零件只新增3项实测方向及目标 self-pair，General仍不适用于模型。profile/pin按以上人工核定值更新；原件核心审核派生的整图必须与运行白名单严格相同。

受测 head 包含目标和 peer Extension/identity/edit-context/permissions保护。逐个真实 preference setter 和显式 dirty setter 前，trace均有完整身份、文档成员、writable、前台与状态观测；成功结果意味着该精确源代码中的完整 guard 已返回。changed/noop descriptor保留相同目标 ID、title/path/type/stamp、inactive/current=false；仅 dirty由false变true。冲突失败按协议不追加descriptor，保留before和零mutation；后续检查完成。此处是健康原生路径证据，readonly-after-setter/peer-drift 等故障仍由 portable 注入验证，没有声称做过原生故障注入。

公开验证需要重新走完整 CLI→daemon→worker，覆盖这11项、lease/stamp/CAS、SDK/MCP、readonly、新句柄save/reopen、同host及空目录/daemon退出；不得把本轮内部ok作为publicok。

## 几何原值和仅表格质心界限

所有观测实体数1、体积 `11999.999999999998 mm³`、面积 `3799.9999999999995 mm²` 完全一致；x恒 `-7.058607893785837e-16 mm`，z恒 `5.0 mm`。只读基线y=`7.058607893785837e-16 mm`。所有before/after原值、hex、delta、exact_equal=false均原样保留，JSONL与report逐行相同。审核重新计算，而非信任passed标志。仅xyz逐轴绝对差 `<=1e-12 mm`；V/S/实体数、其他结构和finite规则严格不变。

| 阶段 | before y mm | after y mm | delta y mm |
| --- | --- | --- | --- |
| `fixture-readonly-reopen` | `5.514537417020185e-16` | `7.058607893785837e-16` | `1.5440704767656523e-16` |
| `before-first-table-write` | `7.058607893785837e-16` | `5.514537417020185e-16` | `-1.5440704767656523e-16` |
| `all.use_template_settings` | `7.058607893785837e-16` | `5.514537417020185e-16` | `-1.5440704767656523e-16` |
| `bom.box_border` | `7.058607893785837e-16` | `6.286572655403011e-16` | `-7.720352383828262e-17` |
| `bom.grid_border` | `7.058607893785837e-16` | `6.286572655403011e-16` | `-7.720352383828262e-17` |
| `saved-reopen` | `7.058607893785837e-16` | `5.514537417020185e-16` | `-1.5440704767656523e-16` |

最大质心差 `1.5440704767656523e-16 mm`。按本轮明确许可通过；先前精确规则失败的 `42405733149` 等原件和失败结论保持，没有改写或追认。

## 原件位置和复跑命令

原 ZIP：`/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42415716434/original.zip`。
官方 completion-run/artifact metadata、extracted原件、独立审核JSON均在同目录。完整审核脚本固定run/head/ZIP/report/trace摘要，直接从original.zip临时解压核验，不依赖已解压副本：

```sh
/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/.venv/bin/python \
  /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/audit-table-defaults-internal-42415716434.py \
  --evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42415716434
```

本次白名单更新后：完整1881项测试通过、33项平台跳过，相关72项通过，SDK生成/strict mypy 6文件/8项negative consumers通过。日志在同一ignored run目录的promotion相关文件。remote/local preflight均通过。

公开运行前另执行 `scripts/ci/verify-table-defaults-proof.py remote` 和 `local --directory docs/verification/table-defaults-evidence/run-42415716434/extracted`；remote官方来源、local精确profile对齐与trace/report摘要均要求通过。

| 原始文件 | SHA256 |
| --- | --- |
| `calibration/annotations.SLDASM` | `f2fafa0febf30e55c0a6d7221a52b3946e292a11be1d7ba1023085db49641488` |
| `calibration/annotations.SLDDRW` | `32179ea395743a5430d7da2d769740e94416eedd8491129167e8687794b0c7d5` |
| `calibration/annotations.SLDPRT` | `ebc48778d0dc2230f6d86aab256b2c31588f4d0ee101ece09391a740b4c9b437` |
| `calibration/geometry-observations.jsonl` | `b91e86094b138005c94da7dc603e5dd780fda325d0df340c364719f02330ebdb` |
| `calibration/report.json` | `9e4c61044958cbe5ae6964820e8e800e87f003871ca419850e56c319dfd566cf` |
| `calibration/table-defaults.SLDASM` | `daad099892a17373f87ed2fd0a2b7df3f4104d6c74e3f414b0d0bd148729d9e5` |
| `calibration/table-defaults.SLDDRW` | `21d3d57486d9c58f7b23af3088804912f168a1bc8fdfa514d9a7cc6351d402e9` |
| `calibration/table-defaults.SLDPRT` | `9ddd65460166db449a1b965d8035a1639f505dd4ce96b6ae6d7a6e5e1b82c323` |
| `calibration/trace.jsonl` | `3926c138fae2f4747ff53ecbd6608c9a61960d3e3a132a7eea2f51a6231d6af9` |
| `worker.native.stderr.jsonl` | `0ceb9245963abf13eeaef13162c3ef6318fbd405d16fa8096ee69260684d0127` |
| `worker.stdout.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `wrapper-result.json` | `c56a059a1bb5ff09ff85c03e0f90645c7c06ac07cfcdabc0a6d8df8a9017b625` |
