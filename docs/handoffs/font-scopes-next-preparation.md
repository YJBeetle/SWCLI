# 字体 next 离线准备增量

本轮只补原 dimensions/tables 范围的证据、复现与离线请求门禁，没有运行 COM/VM、原生 CI，也没有开放公开白名单、合 main 或发布。Notes 已交付部分和旧原件保持。当前发布范围不包含本路。

## 精确提交与入口

- 分支：`codex/docprops-font-scopes-next`。
- 本轮实现提交：`c108af1ca97b9f07c7379a0d2dfa0f41dc00f4d6`；上一轮候选 `466035fee5f056f6c88f6afd486ed8d36d28ce8f` 和交接 tip `f5a62cfcc525e885fefe7694dc7fabfa2f407d61` 均保留为祖先。
- 源码包：`artifacts/font-scopes/next-source-package-c108af1ca97b/`；包内 `manifest.json` 锁定完整 Git 提交与 600/1800 秒预算、三文档类型、原七字段、两独立 scope、每组 21 变化/21 同值/六保存文件。
- 源 ZIP SHA-256：`80e67900f9be1d3d139fa3642940feae3a0857988289fa9ec74a40d14674bcb5`。两个不同目录生成的 ZIP 与 manifest 逐字节相同；复现记录见 `artifacts/font-scopes/next-preparation-reproducibility.json`。

## 五类 witness 的原值、变化与首失败

`font_scope_evidence.LinkedFontJournal` 记录 BOM/general/hole/revision/title-block 五类完整的归一化和原生 17 字段。每个文档 case 独立 `native/linked-fonts-part|assembly|drawing.jsonl`，边界固定为初始、七字段变化及两次保存重开。

每个边界先写 begin，带上一完整边界的五类原值和当前 mutation 回执；随后每个 getter 完成就写该类型的 before/after 原值及显式旧值/新值变化；五类齐备且目标/前台守护通过才写 complete。每条记录 flush+fsync 成功后才继续。初始 before=null 表示正在采集真实基线，不伪造原值；其逐类型 after 和 complete 保存完整基线。

第三 getter、磁盘写入或 fsync 失败时，已写前缀和之前完整边界保留，失败边界不标 complete，不跳过、不重试或截断重建。记录失败后 journal 禁止继续写入。所有行均标记 public_acceptance=false、inheritance_acceptance=false，完整 witness 也不是对象/单元格继承证明。

只读 getter 使用完整的目标身份/状态/编辑上下文、前台指针和前台文档状态守护。故障注入证明前台切到第三个文档、dirty 改变或目标路径漂移都会拒绝成功，不激活或回滚。

新 `--source-head` 必须为完整 40 位提交且与已设置的 GITHUB_SHA 相同；next scope 缺少精确来源时在创建 worker 前拒绝。旧入口不提供新参数时保留原行为。子 worker 获得同一 GITHUB_SHA，journal/watchdog 来源一致。

## 可独立核验的源码包

`prepare-font-scopes-next.py` 只读取干净 checkout 的指定 HEAD，不安装依赖或执行原生命令。固定顺序、时间、模式和 ZIP_STORED 使包不依赖输出目录、当前时间或压缩库版本。

清单逐文件列出大小、SHA-256、Git blob 和模式，并保存原始 commit 对象。验证器重新计算 blob、递归 Git tree 和 commit，绑定统筹提供的精确 head。即使篡改文件后重算 ZIP 和清单自述哈希，也不能匹配原 commit tree。额外路径、重复条目、符号链接/子模块、错误计划和错误 head 均拒绝。不自动解包、安装或运行。

```text
python scripts/ci/prepare-font-scopes-next.py build --head c108af1ca97b9f07c7379a0d2dfa0f41dc00f4d6 --output-dir <fresh-output>
python scripts/ci/prepare-font-scopes-next.py verify --head c108af1ca97b9f07c7379a0d2dfa0f41dc00f4d6 --package-dir <fresh-output>
```

依赖 wheel、SOLIDWORKS、模板、运行环境与执行授权不包含在包中。运行计划仅供 root 统一排程，生成/验证源码包不等于获准执行 native。

## 离线公开请求合同门禁

`verify-font-scopes-next-offline.py` 核对已安装 Python/schema 文件与源目录的相对路径集合及逐文件字节一致，再用合成传输验证两 scope×七字段的 CLI 解析、SDK、MCP，共 42 个前端检查。另有 10 类非法参数/缺少上下文的传输前拒绝，以及 SDK/MCP 两条 partial 首错回执保留且一次调用的检查。

门禁在网络和进程启动被禁止的边界内初始化前端，传输全部 mock。结果为 offline-synthetic-font-requests，明确 native_executed=false、public_acceptance=false、inheritance_acceptance=false；不能当公开 daemon/worker 验收。它要求公开 profile 仍只有 Notes，没有增加校准协议开关。

```text
python -I scripts/ci/verify-font-scopes-next-offline.py --source-head c108af1ca97b9f07c7379a0d2dfa0f41dc00f4d6 --output <fresh-offline-report.json>
```

source-head 来自调用者；完整源码绑定由上面的包验证器负责，门禁额外防止仅版本号相同但实际安装了旧 Python/schema 文件。

## 本轮验证

- 字体专项 90 项通过，其中本轮新增 16 项准备/故障注入测试。
- 完整便携回归：运行 2,992 项，OK（39 skipped），118.616 秒。
- SDK 生成、Python 3.9 语法、diff 检查通过。
- 实际两包均包含 1,050 个文件，Git blob/tree/commit 独立验证通过；已安装 Python/schema 逐文件核对 124 个。
- 精确提交离线请求结果：`artifacts/font-scopes/next-preparation-offline-requests.json`。
- 完整日志：`artifacts/font-scopes/next-preparation-final-with-foreground.log`；机器摘要与双包复现：`artifacts/font-scopes/next-preparation-reproducibility.json`。

## root 下一步与未验收边界

root 亲审后按原计划安排两个独立 owned-hidden-host 组：dimensions、tables。使用包 manifest 中的命令，显式传入上述精确 source-head；预算仍为 native 600 秒/每组 1800 秒。没有自行 dispatch、扩展旧单机密路径、占用 VM 或同步等待 CI。

本轮没有新 native 原件或真实公开成功。表格 witness 仍只有五类，模板/对象/单元格继承、其余表格类型、尺寸子类型、视觉效果和其他版本均未验收；公开 dimensions/tables 写入继续关闭。需要实际内部结果和后续有限公开 CLI→daemon→worker/只读继承门禁才能推进，不自动晋升或混入当前发布。
