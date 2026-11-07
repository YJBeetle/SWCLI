# 三类型内部写原件审核与精确公共域交接

本轮固定内部run [42414478796](https://github.com/YJBeetle/SWCLI/actions/runs/42414478796)，head `68b05c98e0a13000b4ac06002163d01820fba7b7`。内部成功已经原件复审；**公共CLI/SDK/MCP native验收尚未完成，不合main、不发布、不称全系列完成。**

## 官方原件与可复跑审核

- artifact `13591264000` / `swcli-windows-hosted-42414478796-1`，10944652 bytes。官方与下载ZIP SHA256均为 `fdf66026e457ff035652acb0fde3d4929b8b0cadde41f0dbc2ca855ebf43e4f0`。
- 本地原ZIP：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/write-checkpoints-42414478796/original.zip`；安全解压在同目录 `original/`。官方日志原ZIP同目录 `actions-logs.zip`，原文件未改写。
- 原report SHA256：`13a4b243b6362436ab200ee6db03928b0671ffbf1c5d31062467874838f68fd2`。完整run/job/artifact元数据及独立审核JSON在 `docs/evidence/units-profile/write-checkpoints-42414478796/`。
- 审核器仅标准库，不导入产品/gate，不调用COM/网络。固定原ZIP/head/artifact/digest，逐项重算源/目标文件、类型敏感snapshot/hash、真实回执、非目标精确保持、system原始联动、配置/身份/peer/dirty、保存及RO/writable重开、raw/hex/delta、native预算、单host退出。已两次得到相同审核结果。

```sh
python3 /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/verification/audit-units-write-42414478796.py \
  --archive /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/write-checkpoints-42414478796/original.zip \
  --metadata-dir /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/evidence/units-profile/write-checkpoints-42414478796 \
  --repo-root /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
```

## 原生实证范围

| 类型 | 实际步骤 | scalar | system有限方向 | Custom准备 | 已测配置 |
| --- | ---: | ---: | ---: | --- | --- |
| part | 46 | 37 | 8 | MMGS→Custom | Default |
| assembly | 46 | 37 | 8 | MMGS→Custom | Default |
| drawing | 47 | 37 | 8 | IPS→MMGS→Custom，保留真实初始IPS | 无模型configuration，正常sheet上下文guard |

八scalar为linear unit/precision、angular unit/precision、mass-properties length/mass/volume/precision；单位仅既定mm/in、degrees/radians、mm/m、g/kg、mm³/m³，三精度均逐值0..8。system仅MMGS双向连接CGS/MKS/IPS/Custom。每个目标都是真实非同值单Set True，完整九值/raw5/19 linkage读回、独立保存/关闭/RO重开/拒写/计划内writable重开均有原件，共281份原生文件hash重算一致。没有跳过未到达类型或拿旧run替代。

421302条trace、210651个完成边界、0 error，最大3.4529999999999745秒；整组357.297秒，仍为600/1800预算。host PID7892、一次DispatchEx、一次owned Exit和句柄等待退出，前后PID库存均[]，无cleanup error。Windows-2025 / SOLIDWORKS33.5.0，Win3.9/3.14是portable前置，不冒称两个版本都跑native。

part 92次几何比较：V/S/body严格；40次保留exact_equal=false，最大质心逐轴绝对delta `3.970466940254533e-16` mm。只有已批准的≤1e-12 mm，无relative或V/S容差；原始double/hex/delta和解析盒体检查保留。模板hash有记录；模板原字节未入该ZIP，不能声称从ZIP重新计算模板文件本身。

**内部调用私有adapter，没有经过registry lease路由。** 真实公共lease/session/CAS拒绝不能由该成功推定；留给本轮公共验收。此前失败run42406393957仍failure，其part已完成/assembly部分原件完整保留，不翻绿、不清空。

## 审核后人工开放的范围

在完成上面审核后，本分支手动录入 `src/swcli/document_unit_write_domains.py`：139个真实步骤去重为**137个精确域**（part45、assembly45、drawing47），其中26个system域各绑定完整after-snapshot SHA。表内同时固定原件run/head/artifact/ZIP/report SHA，CI和校准脚本没有生成/更新生产表的通道。测试逐条核对该静态表与独立审核结果，任何新增或改值必须重新审阅。

域仍为 `(document_type, complete_source_snapshot_sha256, field, native_target)`；仅已测SOLIDWORKS `33.5.0`、part/assembly的 `Default` 模型配置及drawing无模型配置的正常编辑上下文可做changed写，其他版本/配置拒绝。读取/noop语义保留。一个值在某个源通过，不代表同值在别的源也可写；不开放任意单位组合、任意标准对或整页设置。scalar非目标/raw5/linkage严格规则、system完整受审后态、state/identity/peer/lease/stamp/完整CAS保护均未放宽。

## 一次必要公共CLI/SDK/MCP验证

新gate对**每一条原定139步骤分别跑CLI、SDK、MCP，共417个case**。三通路都必须经过同一个独立owned daemon/worker/hidden CAD host，SDK用实际 `Client.document.unit_profile_set`，其余typed控制操作用 `Client.execute`；MCP启动一个真实stdio frontend并调用原生 `execute` tool，先initialize/list-tools/capabilities，不隐式启动/恢复CAD。没有COM捷径或假daemon；假daemon只用于明确标注的portable传输测试。

每通路每case保留真实owner lease、竞争session配合法owner token拒绝、stale stamp、非目标linkage完整CAS冲突、Custom源未校准域拒绝、noop、changed native True、后台/身份/config/dirty、保存/关闭/fresh readonly重开、只读拒绝及原始几何。SDK/MCP原始request/response、MCP structured/text结果都持久记录。读取daemon status仍用既有CLI，明确标注实际通路。

公共组仍是**同一个1800秒组**，request/native原预算600秒，不按三通路重置、不拆组、少测或恢复host。新write专用日志把每个原始请求/结果以JSONL flush+fsync，显式语义/意图/最终检查点仍写完整报告，避免每条事件重新序列化整份增长报告；日志失败时禁止再发写请求，已成功回执保留不重试。MCP frontend结束不停止CAD；最后只有原wrapper一次daemon stop与保留的native进程句柄退出确认。

CI仅在显式 `units_write_calibration && units_public_acceptance` 时从本轮wheel安装它已有的`[mcp]` extra，其他模式不变。源分支未覆盖main960839e修复的两个property测试或矩阵PyYAML依赖；统筹集成时保留main这些修复，不整文件拷贝旧CI。

本轮输入为 `units_calibration=true,units_write_calibration=true,units_public_acceptance=true,native_full=false`。先提交/推送精确新head，仅触发一次必要公共验证；正常一次快照即停。真实public原件审阅及CLI/SDK/MCP全部通过前，公共验收仍未完成，不能用内部139步、合成417步或本地连接测试代替。

本地待提交源最终验证：完整1933项/59.706秒通过（26 skipped，临时环境有MCP extra）；47项最终关联通过，真实SDK TCP/MCP stdio对假daemon4项通过；SDK generated/strict6源文件及8负向typing通过；全部src/CI/tests Python3.9 AST、workflow YAML与isolated help导入通过。原日志持久路径/hash在 `admission-validation.json`。这些均不冒充公共CAD原件。

最终失败回执补强：SDK ProtocolError及MCP结构化/文本不一致时，保留可用raw response/CallToolResult及outcome_unknown，不重试。追加该路径后48项/8.874秒关联通过；1933项是此前完整基线，两者精确区分记录于validation JSON。
