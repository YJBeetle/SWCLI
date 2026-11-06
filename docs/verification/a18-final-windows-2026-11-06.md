# A18 最终 Windows 验收与发布审阅

状态：用户已批准，已公开发布 [v0.1.0a18](https://github.com/YJBeetle/SWCLI/releases/tag/v0.1.0a18)，非 draft、prerelease。最终原生/原包及五份公开资产匿名下载均已独立核验。

## 固定来源

- 产品版本：`0.1.0a18`。
- 验收/原包提交：`254d1ad11847d002f0af07d630beba3350b7f66d`。
- 分支：`codex/a18-document-annotations`。
- [Windows CI 42173065847](https://github.com/YJBeetle/SWCLI/actions/runs/42173065847)：`workflow_dispatch`、`native_full=true`，Python 3.9、Python 3.14、Build wheel 和完整 SOLIDWORKS 功能验证全部 success。
- 本文是后续证据提交，不替换上述产品源码、原包或镜像来源。

## 原生公共验收

零件、装配、工程图各完成七字段异值修改、保存和只读重开，以及三箭头反向修改后的第二份副本保存重开。147 个注释请求按原始 stderr trace 独立复核：30 次偏好 setter、6 次 SetSaveFlag、1365 次偏好 getter；21 次 clean 同值请求零写入。3 次 lease、3 次 stamp、42 次字段旧值和 6 次只读拒绝均在写入前停止。

工程图初始 edge/unattached 为可读但不可写的 open。本轮首次写入 closed，反向按回执 `reverse_values` 写 dot/dot/none，不把 open 作为目标。无图纸格式的普通 sheet 已真实完成两轮写入和保存重开；模式、view、active/pseudo sketch 原生身份及上下文保持检查继续生效。

六份保存副本均核实际大小、文件 SHA-256、只读重开 clean、fresh document IDs 和七字段读回。原输入哈希保持，零件解析体积/面积/质心保持；同一 owned hidden 宿主 `6620`、worker `5852`，cleanup=[]。私有三类 fixture 准备单独标为 diagnostic，`full_acceptance_eligible=false`，不替代公共验收。

继承能力也已独立复核：完整 19 组/20 步、48 polygon、4 次深度修改/4 次同深度、12 through-all、96 完整端点环、48 fresh sketch、96 旧句柄拒绝、15 份真实共享导出、visible、元数据及单位设置、各组宿主连续性与清理、正常退出和前后原生进程边界。14 份增量日志与 2778 条最终命令回执逐项一致。

## 原始产物与审计

| 证据 | ID/大小 | SHA-256 |
| --- | --- | --- |
| 原 native ZIP | artifact `13482849993`，17393128 B | `ef7dee25e3d995c5cc918d8a41d8d2cb4fc08a59f574fe6c941e12f8f4c323f4` |
| 原 dist ZIP | artifact `13481933297`，1181154 B | `803c0a3fe944b45ae04efccc9360738ced305fca57a5c94543eb5254820478da` |
| 原 wheel | 236427 B | `b9ffa6426e7be27005497c35c32a5a0a389976963fa0ee40da8cb8d80b0e068f` |
| 原 sdist | 949752 B | `6e9516670b59c1417809ba7bcdcae994e0a81b77d23056b99d8b095d26f746e5` |
| 注释公共回执 | `hidden/document-annotations/document-annotations.json` | `96daccc949ba79d604206960531d1812cdcda091740ce5c9339aa343de33dbff` |
| 完整矩阵回执 | `hidden/runtime-sets/runtime-sets.json` | `a7f8675ec91ab212540aa0c2054334d46a08305726339d46b5f712a60c089890` |
| 独立原生审计 | `a18-final-native-independent-audit.json` | `39ace908a8acd81388eb021ebe074e4f3faa254f73f3bec1fcdd374ce98745c6` |
| 独立原包审计 | `a18-final-original-package-audit.json` | `da4b2d3610ebee3464e371d5fb7799048e43b4181f067621b22460aa3d49388d` |

522 个解压原生文件逐字节匹配原 ZIP。原 wheel 的 68 个源码资源与 74 行 RECORD、sdist 的全部 314 个受跟踪文件逐字节匹配固定提交；Twine strict、sdist 校验、全新原 wheel 安装、隔离 CLI/指南资源、54 请求/54 结果/3 协议 Schema 和 pip check 全部通过。必需 skills 真实合并祖先保留。

本地原件目录：`/private/tmp/a18-final-42173065847`。独立审计脚本与结果位于 `/private/tmp/audit-a18-final-native-independent.py`、`/private/tmp/a18-final-native-independent-audit.json` 和 `/private/tmp/a18-final-original-package-audit.json`。

## 发布审阅和边界

最初审阅目录 `/private/tmp/swcli-a18-release-ready` 保留未发布快照。用户最终批准后，发布工作目录 `/private/tmp/swcli-a18-publication` 使用同一原始 CI wheel/sdist，公开五资产经两轮匿名逐字节与 SHA256SUMS 校验。provenance 当前为 `published-windows-verified`，`release_created=true`、`public_download_verified=true`、`owner_approved=true`。只在首次公开核验后更新 provenance/SHA256SUMS，原包始终保持字节。原包内冻结发布说明保留原字节，其历史 pending 文本不代表最终状态。

能力仅为三类箭头、水平折线开关、引线长度、前导零和尾随零七项标量。字体、总体绘图标准及完整文档属性页面尚未开放。原失败 CI `42120377076`（门禁初值选取）与 `42125076559`（无格式普通 sheet 守卫）和独立只读诊断原件继续保留，不把旧失败伪装成通过。

本轮不操作 VM、DockerSW、MacSW 或 main/MCP。A18 完成后暂停，不推进 A19；main/MCP 集成由另一位 agent 处理。正式发布已获得用户最终确认并完成。

## 公开发布回执

- Release ID：`436204657`，node：`RE_kwDOUhPI5s4Z__Rx`，公开时间：`2026-11-06T07:13:08Z`。
- 标签精确提交仍为 `254d1ad11847d002f0af07d630beba3350b7f66d`；后续文档提交不替代验收来源。
- 五份公开资产为原 wheel、原 sdist、RELEASE_NOTES.md、provenance.json 和 SHA256SUMS，匿名下载与发布目录逐字节一致。
- [机器可读公开校验回执](a18-publication.json)记录各资产大小与 SHA-256。
- CI 定时任务此前已删除，本次不再创建；按用户要求发布后暂停，不推进下一版，不合并 main/MCP。
