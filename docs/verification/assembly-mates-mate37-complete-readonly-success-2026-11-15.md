# native37：活动装配体全部六个面的私有只读验证通过

2026-11-15，主协调聊天亲审并执行一次 `VM-20261115-MATE-CENSUS-37`，随后独立核对原生结果并释放 VM。本路只读取原件、复核哈希并记录文档，没有运行 VM、COM、CAD 或 CI。本提交只新增两份证据文档，515 个 `src/scripts/tests` 源码文件与实测候选逐字相同。

## 精确候选和执行原件

实测候选 HEAD 为 `1b5cbdc336b65fc7c89e0775601594b40c2ac3ba`，基线为 `31ad9c256a5a106bc94a627cd41dfd6277bb6f00`。完整 515 项源码清单为 `assembly-mates-active-census-inputs-2026-11-15.json`，SHA256 `a67792386c45ca0c9eb5dc11fe2e9850f16c45c2cee04963878379a17e5ea219`。证据提交的新 HEAD 不替换这一实测源码身份。

原件目录：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261115/mate-owner-37`。这是本机证据定位，不是仓库随附的完整运行产物。主协调独立审计 `coordinator-independent-audit.json` 原字节复制为本说明同名 JSON，SHA256 `29e43993d788af6b11e42bf1d42e1f8da7d45c8b001742a621183dab51b9b966`；其中保留全部 15 份核心原件 SHA。

| 冻结材料 | SHA256 |
| --- | --- |
| source.zip（1058 个 Git 文件） | `69156f6bc144b52eabdc2e1f8a16f57c30eacb2a733023e58b8e5ecfb7707885` |
| single-job-manifest.json（15 个冻结文件） | `bcb78c71973ddf40f6b682e4dc35b42e11abd1bacb0bc9a776a50fdca2001303` |
| proposal.json | `ff01eb2e5145e75c916831fdb8069f801a07ed13cbe6ef918d1d78820bc04592` |
| single-job-driver.py | `ecd44d7ffbb1537929e1b10b2c8b220c61736a9907abaa1110a8e064f9847583` |
| root-controller.py | `cf616cedc812d97a3c000e18ec2af72072028faf01fd2f5d36a34c06d089a752` |
| internal.zip | `5d5a85844241e6db86d2074e832659340c3c30a7564b65aa0089db581d4095c7` |
| public.zip | `5663a704e052633cffdbe909828576f99bb7ef1be876713bdd9c63bb434bacee` |

主协调执行前复核 110 项相关源码测试、14 项包自检、1058 个 Git 归档原件和 15 个冻结文件；`root-preexecution-review.json` 的 `native_executions: 0` 描述执行前状态。实际运行的 `root-result.json` 记录 management_attempts、CAD_grants、candidate_attempts 各 1，management_exit 和 candidate_exit 均为整数 0，first_error/candidate_first_error 均为空，cleanup_errors 为 `[]`。不把执行前的零次状态当作最终结果。

唯一 live job 的 OS 预检和即时准入核实同一 Python、非 SYSTEM 交互 session 1、SID、EXE 长短路径同文件/file ID 和 EXE/TLB 哈希，再由主协调写入绑定同一 job/nonce/PID/实际 manager argv 的许可。实际 manager argv SHA 为 `fd43cad9c1a9d631e31c99f356d67bd43721504c4c973cc4bc123819faf602b1`，由冻结源码的实际 `role_argv` 函数生成；记录的数组直接用于唯一 Popen。native/group/outer 预算仍为 600/1800/1840 秒。

## 全部目标面和 owner 的原生结果

只读自然打开独立 PRT，再打开 ASM，各一次 `OpenDoc7`，Error 都是 0，原始 Warning 都是 2，未抹成 0。目标 ASM 是原生身份一致的 ActiveDoc，没有 `Activate`。现代配置读取使用 `ConfigurationManager.ActiveConfiguration.Name`，trace 中 `GetActiveConfiguration` 为 0。

两个顶层实例均来自 `coincident-aligned-component.SLDPRT`，配置 Default，第一实例 fixed、第二实例 floating；每个 source 和 component 均为 3 个面：1 个圆柱面、2 个平面。六个面各执行一次来源映射、一次持久引用生成、一次 typed resolve，再由正式 resolved IEntity 读取唯一 `GetComponent`，以原生 `IsSame` 证明 owner 等于该精确计划实例；六个引用摘要互不重复。返回结果的 `all_faces_observed` 和每面的 `exact_native_owner` 均为 true。

| 组件实例 | 面索引 | 几何 | reference SHA256 |
| --- | --- | --- | --- |
| coincident-aligned-component-1 | 0 | cylinder | `f97ad7126321f2356586ce0cd9ae2ee69e6b82f6b93ea4bbac01e794d7781b01` |
| coincident-aligned-component-1 | 1 | plane | `3cf10015107235ae3a0d7bec79c5c1e1bd1875c51746a7cb2979dd8191a80af0` |
| coincident-aligned-component-1 | 2 | plane | `d3fefd586da8fe8885f49a03322e82fbcf8a3060548c2223cef92b2318ff6542` |
| coincident-aligned-component-2 | 0 | cylinder | `7b8411dfdb7d7879e7bcde06c043b0bb15949e5cf7ccd2dc5a5cc620faa86293` |
| coincident-aligned-component-2 | 1 | plane | `1d0010331ccbcf783005222a7e47251a214f1a08ed090c5a6851617e22282c5f` |
| coincident-aligned-component-2 | 2 | plane | `f856b3a8a002fb695a0fc6a30032221356a8f06bb436e8314acab3c331debcda` |

parent 与 observer 同为 PID 5256、thread 9728，owned SOLIDWORKS PID 7224。observer 的 1192 条 trace events 全部配对结束；`stage=read, call=GetComponent` 恰为 6 次原生读取，外层包装 span 不重复计算为原生调用。source/config/update stamp/pose/ASM/foreground 后置守卫通过，三个输入文件前后 SHA 不变。

| 输入文件 | SHA256 |
| --- | --- |
| coincident-aligned.SLDASM | `b535588ae3ff2e7656178cea139e974542b3fa1eb82aba2da2b8ee2c6459a081` |
| coincident-aligned-component.SLDPRT | `7a2867363b3e6022916cf039c0ddfab9f60df4dcf2e18064dac9a66dd8f629d8` |
| concentric-aligned-component.SLDPRT | `9b6d73c3a85a5ae7df9bf0b24bdded7f6eb7bf760033b9921f5c7ce3f01bdf66` |

## 清理、传输和结论边界

parent、supervisor、manager 均报告成功；supervisor 保存 parent 原始退出码 0，manager 保存 supervisor 原始退出码 0。held SOLIDWORKS handle 仅在 signaled 后读到严格整数退出码 0，`ExitApp` 恰好一次，cleanup_errors 和 trace_secondary_errors 均为 `[]`。native 前后均为 `[]`，主协调确认 idle pause 恢复 on 并释放 VM。适配器自身的 `resource_released: false` 保留原值，资源释放由主协调的外层证据确认，不从该字段推导。

两层 transfer receipt 已逐文件核对：run 侧 10 项、manager 侧 3 项；bootstrap、原 ZIP、源码和三个只读输入哈希不变。此文档记录阶段再次核对审计列出的 15 份原件 SHA、两层收据、全部 observer trace 配对，以及当前工作树/HEAD 的 515 项源码 SHA。

`Activate`、`Select`、`CreateMate` 和 `Save` 均为 0。`CommandInProgress` enter/restore 各一次是既有 API sequence 内部控制状态，不属于模型写入验收。

这次结果仅支持：精确冻结候选在这份已保存样件、活动 ASM、同一 owned STA 中，对两个实例全部六个面完成私有只读来源、typed roundtrip 和精确 native owner 验证。native31 的后台首面失败和 native33 的活动首面有限成功仍保留原结论；加载顺序也影响时序与缓存，37 不证明唯一根因，不外推任意装配体或所有 SOLIDWORKS 环境。

`public_acceptance`、`public_handles_issued`、`write_CAS_executed` 仍为 false。公共 typed handles、旧句柄失效/CAS、配合写入、保存重开仍待后续独立实现和验收。此文档提交不代表完整 portable、合并、推送或发布已完成；主协调亲审并跑完整 portable 后再决定基础修复的合并，阶段 B 按既定公共句柄/CAS 门禁继续，不能整体恢复旧分支公共模块。

此前准备文档中的“未执行/待原生验证”描述其生成时的状态；本记录追加 native37 的有限通过结果，原件和旧失败记录保持不变。
