# GLB 可见启动局部对照的原件审计

2026-11-11，统筹按 `1beaa471302ff6d1b75a9db656ea5c9b956e32a1` 的 driver 仅执行一次局部对照后停止。本路仅离线审计原件，没有操作 VM、重试、CI 或推送。

**结论：可见启动模式不足以修复固定 70d8c9e 新 part 的空 BIN。** 不将此结果解释成 Visible 或 CommandInProgress 的因果结论，也不改写产品支持范围。

## 固定来源及实际状态

原件根：`/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/glb-visible-startup-70d8c9e-01`。

- report SHA-256：`ddd7b9dbbde8de25bbe898366e1da6b692f3cabf0f6ceeaa4cb1207820cee5f2`。
- driver SHA-256：`53679ce7da4c44788e0a03d3d2a7953b6399dae9be17b12a27da5b75d65084b1`；持久副本逐字节匹配已审阅提交。
- 产品源码固定 `70d8c9ecf3c02b099ca9c2cc64fe1880061cea44`；源码 ZIP SHA-256 为 `06c09b895c1913435061676b13b1539c9a17e7afd4728ba886cfb878ee2b7f53`，全部 245 个文件逐字节匹配该提交。
- SOLIDWORKS 33.5.0，PID 1912；实际 native worker 8176；Popen/venv 启动 PID 8032，三者分开核对。
- 创建 fixture 前及四次导出前的实际值均为 Visible=true、CommandInProgress=false、UserControl=true、UserControlBackground=true。报告保存实际值，不用预期模式替代；也不为调整同时为 true 的 UserControl 属性而增加试验。

同一 fresh front 矩形 40×30 mm、拉伸 10 mm，新建和原生保存成功；保存 errors=0、warnings=0。源文件 68089 字节，SHA-256 为 `3eb244dd0d27f98a77f10838be6043a1aef70a24c17e6f07cbc69073189ec292`。

## 四次导出与首个失败

| 格式 | 内容独立重放 | 字节数 | 单次现代 SaveAs3 耗时 ms |
| --- | --- | ---: | ---: |
| STL | 通过 | 684 | 277.806 |
| 3MF | 通过 | 10822 | 590.207 |
| AMF | 通过 | 1476 | 294.311 |
| GLB | 严格校验拒绝：空 BIN | 3732 | 242.607 |

四个 `local-export-*` 请求均仅一次 `IModelDocExtension.SaveAs3`，原始 begin/end 按 sequence 完整配对，worker 均为 8176；没有旧保存 API。导出 trace 中偏好 setter=0、CommandInProgress 写入=0。这里统计的是四次导出，不是整个运行的所有原生保存。

前三种格式导出前后 host、文档类型／stamp／dirty／配置／路径／标题／只读状态、前台 IsSame、非编辑状态及源哈希保持。GLB 前记录文档 metadata `[1,144,false,"默认"]`、foreground identity=1、源哈希一致。GLB 内容拒绝后按首错停止，**没有 GLB after CAD snapshot**，原 trace 也没有该 after 请求；不能把缺失快照记作内存状态保持。

GLB runtime manifest 的实际原生回执为 `save_attempted=true`、`api_saved=true`、errors=0、warnings=0；随后严格校验报告 `ExportVerificationFailed`。拒绝原件 SHA-256 为 `7c4b0df7a4fd057b466207ae7af2e114ae38a101fa1777a9f7933a49ba1c75e9`。3732 字节由 JSON 3704、BIN 0 组成，JSON 声明无 URI buffer 720；没有 Draco/其他必需扩展。manifest 的 after-1.bin 与拒绝原件逐字节一致，未发现归档／复制造成数据丢失。

两个模块快照各枚举 443 项，但仅保存五种名称过滤后的空结果；不是完整 443 项路径清单，不能证明导出器缺席或排除瞬时加载／其他进程。swconst 相关偏好匹配为空，文件访问监控 unknown，均保留原样。

## 文件及清理

结束后离线重新计算实际 SLDPRT，仍等于保存后及四次导出前源哈希。这只证明磁盘文件字节未变，不补足 GLB 失败后的 CAD 内存状态观测。

worker 正常以失败状态 exit=1 结束，保留首个内容错误；cleanup_errors=[]，启动前及结束后原生进程列表为空，没有第二次 GLB 或自动第二轮。统筹报告 VM 已释放、idle pause 已恢复；本路未重新访问 VM。

完整文件摘要、调用相关性、module manifest、与旧原件的比较和安装日志原行核验见 [结构化证据](../evidence/glb-visible-startup-native-audit-2026-11-11.json)。本次文档仅离线校验，没有重新运行产品测试。

## 与历史原件比较

本地隐藏基线与本次可见模式的 GLB JSON 只在 `cameras` 和含相机矩阵的 `nodes` 不同，buffers、bufferViews、accessors、meshes 全等，均没有实际 BIN。相机差异不能据此认定为根因。

这四类几何声明也与早期 42173065847 同组的 part／assembly 全等；但早期 assembly 原件实际有 720 字节 BIN，解码为 12 三角形、24 positions／normals，part 原件无 BIN。声明相同不等于 part 具有可恢复的网格；禁止拼接历史 assembly 数据来补写 part。

早期成功来自旧 API 的 assembly、不同宿主／安装来源，且 visible 为启动缓存。它既不是当前现代 part 的匹配成功对照，也不能因其属于 hidden 模式就否定可见对照的信息价值。本次实际观察只缩小为：固定样件和绑定下，可见启动模式单独仍不足以修复。

下一信息路径见 [导出器与后续对照评估](glb-exporter-next-evidence-plan-2026-11-11.md)。
