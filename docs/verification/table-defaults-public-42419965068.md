# 三类型表格公开门禁原件审核通过

2026-11-10核验：[42419965068](https://github.com/YJBeetle/SWCLI/actions/runs/42419965068) / `9bb806b454cdcbcb225135886482a2e555044444` completed/success。官方 artifact `13593611864`，名称 `table-defaults-public-42419965068-1`。原始 ZIP 本地SHA256与官方digest均为 `413268d6b2a31d6426da517305b711408bc13e6164b5b2a4e6b2fe0f18d29906`。

本次独立审核通过完整 part/assembly/drawing 的公开 CLI→daemon→worker 路线，覆盖f188写入保护及全部11项精确转换。候选分支的 `src/scripts/.github/tests/pyproject.toml` 与受测head完全相同；本次只追加文档/审计器，无新增CI、产品/测试改动、main合并或发布。最终集成源代码与工作流静态复审、main合并由统筹本人负责。

## 精确范围

| 类型 | Template toggle | 边框 | 同值请求 |
| --- | --- | --- | --- |
| part | `True→False` | BOM box/grid `0→1` | False / 1 |
| assembly | `True→False` | BOM box/grid `0→1` | False / 1 |
| drawing | `False→True` | BOM+General box/grid `0→1` | True / 1 |

仅 SOLIDWORKS `33.5.0` 原生 Windows。装配体/工程图仍为原8项，零件仅3项，完整profile必须与已审核内部原件推导的11项及各目标self-pair严格相等。未注册逆向、thick、其他revision或Wine；没有新增计划或字段。内部proof来自 `42415716434` / `f1881a7421200e46028652538892c15a366f2ef8`、artifact `13591813168`、原ZIP `7e1d8fcd8c1d8b26346024305c0f30a0c77536b2ea4ade06f3c694e382db9e8e`。公开审计器先重新完整审核该内部原ZIP，再审核公开原ZIP，没有以内部成功替代公开证据。

## 逐请求核验

- 158个CLI completed事件、316条原始journal记录逐条对应stdout/命令/退出码；所有case摘要重新绑定真实CLI结果和目标ID。168个native请求组完整配对、嵌套顺序正确、request ID与operation匹配；只有前后两个daemon status不进入native worker。
- 77个表格请求独立派生出 **11 setters / 346 getters**，与report proof逐项一致。11次真实changed每次恰好一个preference setter，前一次完整读、后两次完整回读；其余字段保持。11个CLI同值、3个SDK同值、3个MCP同值均零setter/零dirty。只有每类型首写各一次SetSaveFlag，共3次。
- 每类型3类显式拒绝lease/stamp/readonly均零preference getter/setter；3项unrelated CAS及11项stale完整CAS拒绝均仅一次完整读取、零setter/零dirty，并由后续观测确认状态未变。lease所属目标/session和stamp实参均从原命令重建核对。
- 3个typed SDK read+3个noop，以及3个MCP bridge read+3个noop使用同一endpoint/session/真实daemon，request IDs不复用，结果与CLI最后一次写入的完整options/document一致；各请求原生轨迹属于同一worker。
- 三类目标所有表格成功请求始终 `active=false/current=false`。写前后title/path/type/stamp/ID保持，仅目标dirty按预期改变；同值及拒绝后的读取完整一致。六个foreground peer创建至关闭的ID/title/path/type/stamp/dirty原值一致。

## f188保护与首错边界

11个preference setter和3个显式SetSaveFlag共14处mutation前，真实trace都包含target和peer的身份、Extension、open membership、foreground、状态以及至少两组readonly/viewonly读取；绑定的精确产品源代码含 `_verify_before_mutation` 和目标state读取前后完整peer复核。全部14处都通过，不能用旧head的健康路径原件替代。

单一owned隐藏Windows host PID `808`、worker PID `4628`，启动仅一次，前后host完全一致，无recovery。最大原生请求约 `1.7346332秒`，native整组约 `59.5613414秒`，gate约 `60.288499秒`，独立预算native600/group1800秒均满足。trace中恰有6个预期的lease/stamp sequence0拒绝error帧，没有任何内部native调用error或意外首错；CAS/readonly返回预期失败而无mutation。无重试、回滚、host更换或预算扩大。

本轮是健康原生路径的真实guard执行证据；setter后readonly、peer漂移、worker late-fault等故障注入继续由既有portable测试证明，未冒称在原生host做过故障注入。完整portable1881项/33平台skip及SDK生成/strict/8 negative检查此前在同一产品head通过，本次产品未改，不重跑或新增CI。

## 保存、只读重开和清理

三份源fixture均与固定内部ZIP哈希一致，开始以可写新handle打开。所有另存文件均为distinct path，API save errors=0/warnings=None、保存后modified=false；新只读handle重开无API错误/警告，全部11字段持久化相同，readonly请求失败且零写。重新核对保存文件size/hash与实际ZIP内文件一致。

| 类型 | 原目标 ID | RO新目标 ID | 表格阶段stamp |
| --- | --- | --- | --- |
| 1 | `d-4g449d` | `d-pd3ek3` | `163` |
| 2 | `d-8wjwzt` | `d-w52hsz` | `120` |
| 3 | `d-0zkpxv` | `d-wags3m` | `103` |

6个目标open加6个peer create共12个live handle均关闭，无重复ID或重复close。开始/各case后4次document list均为空，3项case_cleanup分别为0文档/remaining IDs空，cleanup_errors空；daemon stop成功，wrapper `daemon_exit_confirmed=true`。

## 几何原值和许可边界

三次真实 `document.measure` 的metrics与摘要逐一绑定：实体数1、体积 `11999.999999999998 mm³`、面积 `3799.9999999999995 mm²` 严格一致。x恒 `-7.058607893785837e-16 mm`，z恒 `5.0 mm`。public初值还与固定internal source metrics按同一表格规则独立比较通过。

| 阶段 | before y mm | after y mm | delta y mm | exact_equal |
| --- | --- | --- | --- | --- |
| after-public-writes | `5.514537417020185e-16` | `8.271806125530278e-16` | `2.7572687085100926e-16` | false |
| saved-reopen | `5.514537417020185e-16` | `5.514537417020185e-16` | `0.0` | true |

原始before/after、hex、每轴delta及finite/non_centroid_equal均保留并重算。只允许2026-11-08用户明确批准的表格xyz各轴绝对差 `<=1e-12 mm`；V/S/实体数和其他结构严格不变。没有舍入、归零或改写旧失败。只在临时副本验证4项审计拒绝：体积1ULP、增大记录容差、删除writable guard观测、伪造noop摘要均被拒绝；原ZIP随后再次审核通过。

## 可复跑命令和永久原件路径

公开原ZIP：`/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42419965068/original.zip`。
原始completion-run/artifact/jobs元数据、extracted副本、`independent-audit.json` 和 `audit-refusal-checks.json`同目录保存。`original-evidence-manifest.json`核对保留的10份历史原ZIP与各自存档官方digest一致，没有覆盖旧失败或旧公开原件。审核脚本从两个original.zip安全临时解压，不信任已有extracted副本。

```sh
/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/.venv/bin/python \
  /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/audit-table-defaults-public-42419965068.py \
  --public-evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42419965068 \
  --internal-evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42415716434
```

| 本次公开ZIP原始文件 | SHA256 |
| --- | --- |
| `public/daemon-stop.json` | `1390d77aac81f23fb8918bc454644976fc30c22d5a7bd27c4c76eb7707d45abf` |
| `public/daemon.native.stderr.jsonl` | `05e9f85aee867ebf294a6cd7a36e6fabd9ed0060d419ad4fa29e982b9025b36e` |
| `public/daemon.stdout.jsonl` | `67288d7d4f43aa4a21c777a154fcbf4f7255fc040991c377962522d65bcd0590` |
| `public/gate.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `public/gate.stdout.log` | `d494316a9fd27cb826c280d454762395f4fc5aae8e09cc211e46dc231959556a` |
| `public/gate/public-table-defaults.SLDASM` | `d99276bc2499ca3fd1dfe9d1dfd8b68094407570c5113736cfb2e55b568fd534` |
| `public/gate/public-table-defaults.SLDDRW` | `756972ca86eb687670fbe5bbb0e9a240f7d084f7429cee372a716eefb83076a8` |
| `public/gate/public-table-defaults.SLDPRT` | `7f60f9fecf7bcb8a12118610852ed88b73589fdab3371fafcedb321061a51f95` |
| `public/gate/table-defaults-public-events-modeling-smoke-764b0bdd9eb4.jsonl` | `edce0d36b36c2cc523bbc1c7414a68d802f9ab7dbd6f4bc00b26ae2ab3289841` |
| `public/gate/table-defaults-public.json` | `988237e3201f9c40588e05cd96d1da48bc04cf9d61f6498dfd23f9d6d718fefe` |
| `public/wrapper-result.json` | `f25b7bea2105fa77f47c0edf95eb206be628bc0c3a02677bfce019623cdf8ae3` |

公开report SHA256 `988237e3201f9c40588e05cd96d1da48bc04cf9d61f6498dfd23f9d6d718fefe`；native trace SHA256 `05e9f85aee867ebf294a6cd7a36e6fabd9ed0060d419ad4fa29e982b9025b36e`。该证据只接受上述受测表格域，不是全建模套件或release验收。本分支现可交统筹本人做最终source/原件review和集成；没有自行merge main或发布。
