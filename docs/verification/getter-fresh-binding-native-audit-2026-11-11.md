# Fresh Parameter 预置句柄的局部原生审计

2026-11-11，独立离线复核统筹执行的单次私有 part/front fixture。测试源码固定为
`d2a8e606d0d251946583570510e6e0b1175fa355`。本次局部诊断通过，**不构成 CI、完整门禁或公共验收**；审计者未操作 VM、触发 CI 或推送。

## 来源与完整性

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/getter-fixed-d2a8e60-01`。

| 原件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| report.json | 45043 | `45be9ce0cbd91d1a34bfffeeeee8c9219e57cac9d091cfeefe4fcfab4dd65df4` |
| getter-source-d2a8e60.zip（父目录） | 见结构化证据 | `f90d4e03d65832310fe51d0f230b811ff9ae0a4b9cdab6fbd591480301ee9821` |
| two-configurations.SLDPRT | 86852 | `05cd3236eb41cb0417e43b810bc25cdece3708c94e1af0f4c34728b5097a6aee` |

源码 ZIP 的全部 247 个文件逐字节匹配上述 Git 提交。其余原始报告、trace、supervisor 与日志的大小和哈希见
[结构化审计](../evidence/getter-fresh-binding-native-audit-2026-11-11.json)。没有以副本或重新保存的文件替代原始 SLDPRT。

## 单变量与原生结果

上一轮 `d7fd6b7` 的 B seed 虽返回整数 0、重建 true，新取得的草图实体半径仍为 8 mm，未达到 B 所需 10 mm；该失败仍有效，不能改记为预置成功。

本候选只在 B 已激活并完成文档、配置、编辑状态检查后，用精确未保存 FullName 调用一次 `Parameter` 取得 B seed 句柄，并校验返回 FullName。原始创建句柄仍用于保存后的 FullName 读取；原有观察绑定和目标读窗保持。

本轮记录的 lookup/bound FullName 均为 `D1@草图1@零件1.Part`。B seed 仍为 0.020 m、scope 3、显式 VARIANT 类型 8200、单元素 `Getter_B`；返回整数 0。几何证明随后实际通过，才支持 B 预置完成。

| 独立几何窗口 | 实测半径 mm |
| --- | ---: |
| initial-A | 8 |
| seed-B | 10 |
| seed-A | 8 |
| saved-A | 8 |
| saved-B | 10 |
| reopened-readonly-A | 8 |
| reopened-readonly-B | 10 |

每个几何窗口均从 fresh `FeatureByName` 取得草图，核对单一完整圆、中心与半径；原始 trace 各有一次 `GetRadius`。七个窗口均无 Get3、写入、重建或保存调用，且文档状态、当前配置身份、前台对象与非编辑状态保持。保存后的四个几何窗口另核对源文件前后哈希不变。

| 目标观察窗口 | 配置 | GetSystemValue3 结果（m） |
| --- | --- | --- |
| saved-A | 默认 | tuple，长度 1，0.016 |
| saved-B | Getter_B | tuple，长度 1，0.020 |
| reopened-readonly-A | 默认 | tuple，长度 1，0.016 |
| reopened-readonly-B | Getter_B | tuple，长度 1，0.020 |

四个目标窗口各恰好一次 Get3，scope 3、单 BSTR 当前配置。返回形状事件与该次 native-call 的 sequence、请求和 worker 一一对应；前后状态、配置身份与前台对象保持，读窗内没有切换配置、写入、重建或保存。创建直径 helper 自身会读取 descriptor/Get3，不能把四个目标观察次数当作整个运行的 Get3 总次数。

现代原生保存 `api_saved=true`、errors=0、warnings=0；只读重开同样 errors=0、warnings=0、clean。实际 SLDPRT 哈希等于保存后及所有读窗最终哈希。

## 进程、清理和边界

SOLIDWORKS 33.5.0，Python 3.14.7。宿主 PID 2612，实际 native-call worker 6608；supervisor 的 Popen/venv 启动 PID 为 5244，二者分开记录。离线重放两个 trace 审计时均使用实际 worker 6608，七个几何窗口及四个目标窗口全部匹配。

supervisor 正常 exit=0、failure=null、cleanup_errors=[]，启动前和结束后原生进程列表均为空。宿主报告的 visible=false 是 harness 输入记录，不将其提升为导出或任意时刻的实时读值。

40 项相关离线测试已通过；新增缓存句柄回归在旧 d7fd 上按预期失败。该原生成功支持此固定 fixture 的 fresh seed binding 路径，不能据此宣称所有跨配置 dimension handle 都失效，也不替代更多文档类型、方向、完整门禁或公共发布验收。
