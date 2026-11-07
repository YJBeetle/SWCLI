# 线型 / 线宽默认设置交接

**收口状态：严格 native Windows 修复 code head `85ae6c1ec49baba86b2ee66d1aea84bb066bb3e6` 的唯一公开 run 42361465979 已 success，本轮原 ZIP/官方 digest/head、逐请求 trace、save/reopen 和前台状态首层审计全部通过。产品冻结，可交统筹本人最终 review/merge；不自行合 main 或发版。未新增代理、未扩范围、未重复 CI。整个系列完成后再发布，正式发布仍等待用户最终确认。**

最终交付分支：`codex/docprops-line-style`。已验产品 commit：`85ae6c1ec49baba86b2ee66d1aea84bb066bb3e6`；其后提交仅更新设计/交接文档，不改变产品、schema、测试或 gate。旧 `80b6133` 原件只是历史，不用于本轮通过结论。

## 本轮 exact-head 原件与独立首层审计（供统筹本人最终 review）

- [42361465979](https://github.com/YJBeetle/SWCLI/actions/runs/42361465979)，官方 head=`85ae6c1ec49baba86b2ee66d1aea84bb066bb3e6`，status=`completed`、conclusion=`success`。Windows Python 3.9/3.14、wheel、Public drawing Line Font acceptance 全部 success；release tag / publish jobs skipped，未发布。
- 唯一 dispatch 参数：`line_font_public=true`、`line_font_calibration=false`、`native_full=false`。本轮无新增 dispatch、watch、sleep、持续 poll 或自动化；收到统筹成功通知后只收集完成态原件。
- 官方 artifact id **13570840145**，name **`swcli-windows-hosted-42361465979-1`**，原 ZIP **186157 字节**。
- 官方 digest 与实际原 ZIP SHA256 逐字相同：**`477dda40f31f1bf691543f78b719761d4e8d3c117484a9743637dfb682fb3e43`**。
- 永久本地完整根目录：**`/Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI/artifacts/line-font/internal-public-42361465979/`**。
- 原件：`original.zip`、官方 `artifact-metadata.json`、完成态 `run-metadata.json`、完整 `expanded/`。报告/原 journal/daemon stderr/stdout/source.SLDDRW/changed.SLDDRW 在 `expanded/swcli-native-smoke/line-font-public/`。
- 独立首层脚本 **`audit.py`**、结果 **`audit.json`**、精确 git commit 提取的产品 adapter 快照 **`product-windows_document_line_font.py`**。脚本固定本轮 run/head/artifact/digest，重跑时重新核 ZIP hash/大小及每个解包文件逐字一致，独立从 CLI 参数和 SDK/MCP 回执计算请求预期，再与 raw trace 比较；不以 report 的自报 success 代替原件检查。
- 原 ZIP、native 日志、CAD 和本地审计均仅本地保存，远端只交代码/便携测试及本文摘要；未复用旧 run 内容。

可复跑命令（无 CAD、无网络、无 git、无需安装第三方依赖）：

```sh
/opt/homebrew/bin/python3.14 /Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI/artifacts/line-font/internal-public-42361465979/audit.py
```

本轮审计通过内容：

- 90 个 CLI event 与原 journal 成对逐条一致；27 个 CLI 请求 + SDK read/noop、MCP live bridge noop = 30 个唯一 Line Font request ID，全部与 raw trace 精确匹配。
- 4 个字段各 1 次 setter、140 次偏好 getter、1 次 SetSaveFlag；逐请求 CommandInProgress 进入/恢复严格配对、完整 child begin/end/sequence 匹配，单 worker、同一 daemon-owned hidden native host revision 33.5.0，预算内完成，无组内重启。
- 13 read、4 changed write、6 noop、4 完整 CAS 拒绝、1 lease 拒绝、1 stamp 拒绝、1 readonly 拒绝；所有 mutation receipt 与原生 setter 次数相符，无未知 COM 方法或全局系统偏好 setter。
- 30 次 foreground 完整 descriptor 稳定；目标仍为后台 drawing。source 和 changed 文件实际字节与报告大小/hash 一致，changed 以 fresh ID 只读重开后四项持久化且 dirty=false；readonly 拒绝未更改值/文件。
- 最终文档列表为空，daemon stop success、退出码 0。没有额外宣称独立 OS 进程 handle 退出审计。

| 本轮本地原件 | SHA256 |
| --- | --- |
| audit.py | `e5143cde73cc365c69355ee248faafcd41ac3821f34b37b0db9b22789cbdce48` |
| audit.json | `022331867bd7c114b4100ed580a578b0eda838537050fbd63241cd16142475e3` |
| exact-head adapter | `4d9e21c50593cc2c9d4b702ca213d9a0e83ae178076b2bd48fa2fe7af71a2d6c` |
| public report | `572d3235772454aaea4a64d267ed7355ed1a520cb363c7bbcd3ca0533ef92055` |
| events journal | `ceff002f2e6e2b8e9d04c30a0e187cf0ea166ca34937a35f7e4075c383188263` |
| daemon native trace | `d69abbf944d6bb6323ef5ff6750f1d2051dceffdcc381e4de22e7b111af29443` |
| source.SLDDRW（23838字节） | `a79dbf582819a3128bf4eef560514e51eca26d13b72b746c6d7721e86467e338` |
| changed.SLDDRW（23993字节） | `ee2f47d7c21a2f67855655bd0400eb2a8e1f5e9a9ef6921de19b1300a5c0a4b1` |

实际边界：修复代码运行于 exact-head Windows hosted gate；Wine/unknown 拒绝是便携 mock 证据，raw COM trace 不记录 Win32 GetProcAddress 每次查询。四个既定单向转换和 0/1 noop、健康后台 drawing/前台 part、SDK/MCP live bridge 为验收域；不宣称 MCP stdio、原生故障注入、其他 revision/文档模式、完整 modeling suite 或整个系列 release 已验收。统筹本人仍需最终 review/merge。

## Native host 修复与便携验证

- 参考 STL `f22b7a1` 的严格探针方式，仅只读对照，未合入其他分支：真实 `sys.platform == "win32"`；kernel32 `GetModuleHandleW` 必须找到 ntdll，`GetProcAddress` 必须找到已知 `NtClose`；清零 last error 后，`wine_get_version` 必须空地址且错误码恰为 127。仅查询地址，不调用导出。
- Wine 导出存在、模块/已知导出缺失、错误 0/5/126、异常、非 Windows 或未知值一律拒绝。包括 noop 与 private calibration；无 preference getter/setter、SetSaveFlag、Save3/SaveAs。读取不探测 OS，原 state/CAS/lease/stamp/foreground/identity/access/context/partial-receipt 保护全部保留。
- `tests/test_line_font_native_host.py`：8项 OS 边界测试及多组子例，既有 mock fixture 显式声明 native。与原 Line Font/回执保护共 42 项通过；日志 `artifacts/line-font/native-host-checks.log`。全量便携回归 **1861 项通过，32 skipped**（44.085s）；日志 `artifacts/line-font/native-host-full-portable.log`。`git diff --check` 通过。
- 修复 code head **`85ae6c1ec49baba86b2ee66d1aea84bb066bb3e6`**，中文提交 `fix(line-font): 严格限定原生 Windows 写入主机`；push 成功后先以 `git ls-remote` 核远端 SHA 一致，随后 dispatch，未提前触发。
## 历史 80b6133 公开原件（不作为本轮通过证据）

- [42282239432](https://github.com/YJBeetle/SWCLI/actions/runs/42282239432)，GitHub 已核 head=`80b61334537d9394b19da03dee9d7baa08da58e8`，conclusion=`success`；Windows 3.9 / 3.14 portable、wheel、Public drawing Line Font acceptance均success。正式发布job skipped，未发布。
- 参数：`line_font_public=true`、`line_font_calibration=false`、`native_full=false`；其余 media/assets/cleanup/vfs 参数默认。专属public gate真实执行success，internal/property/annotation/full矩阵均按目标模式skipped，非空绿。
- artifact id **13537021814**，name `swcli-windows-hosted-42282239432-1`，183722字节。
- 原ZIP SHA256（与GitHub digest逐字核对）：`268d916ec25155130455f508e172908a69de30adf39b1650092d2eb37ca3ab15`。
- 永久本地原件根：`/Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI/artifacts/line-font/internal-public-42282239432/`。
- 原ZIP `original.zip`；`artifact-metadata.json` / `run-metadata.json`；完整解包 `expanded/`；首层自验代码 `audit.py` 与结果 `audit.json`。原始native数据未推送远端。
- 完整公开报告：`expanded/swcli-native-smoke/line-font-public/line-font-public.json`；原journal、daemon stderr/stdout、source.SLDDRW / changed.SLDDRW 同目录。
- 无CAD/网络的复核命令：

```sh
/opt/homebrew/bin/python3.14 /Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI/artifacts/line-font/internal-public-42282239432/audit.py
```

首层复核摘要：

- 90个CLI事件与原journal逐条一致；27个CLI line-font请求 + 3个SDK/MCP请求 = 30个独立request ID，原始trace全部匹配。
- 4个字段各1次原生setter，140次preference getters、1次SetSaveFlag；逐请求进入/恢复CommandInProgress严格配对。无未知native方法或全局偏好setter，单Python worker / 同一native host，无组内重启。
- 13次read、4次changed write、6次noop、4次完整值CAS拒绝、1次lease拒绝、1次stamp拒绝、1次readonly拒绝；每个请求按实际CLI参数/完整snapshot/回执核对。四次写入实际顺序来自CLI JSON排序，不假定字段插入顺序。
- 30次前台完整descriptor比较稳定；两个阶段分别使用新建foreground part，各自title/path/stamp/dirty等完整字段不变。raw trace含已修复peer guard的GetActiveConfiguration/Name观察。
- source与changed copy实际字节hash匹配；changed关闭后readonly重开使用fresh document ID，四项值持久化且dirty=false，拒绝readonly写未改变值或文件字节。
- 最终原生文档列表为空；daemon stop成功，daemon退出码0；此处不额外宣称未执行的独立OS进程handle审计。

关键hash：

| 原件 | SHA256 |
| --- | --- |
| public report | `ecc42c3137857d28f60c9ee09bed119312f1f577e77aa316fe8a39e1218a44f0` |
| events journal | `957554fae6a836e39603961ce7d014482ccbb7b45a82617a445ba5ba4c253b54` |
| daemon native trace | `05aafca531dadc4c64d23ce036119a5635193f18d63a3e58c25f1eb3cb2d2d67` |
| source.SLDDRW（24956字节） | `890dbdb3b498065eaf43ca04ec42004d0c0afdf7aef5de104ebcda454cb9a6d2` |
| changed.SLDDRW（24144字节） | `d4437e37a6d133be9b88fdaeaf222841b9353e448b9386d452da863c0d0f7e2e` |

实际验收边界：revision 33.5.0、正常drawing目标+新建foreground part的健康public CLI/daemon链路、以下四个单向转换与0/1 noop；SDK typed read/noop与MCP live bridge execute/noop。peer注入的描述符失败/foreground漂移是生产handler/worker的portable mock证明，不是原生故障现场；不宣称MCP stdio、其他版本/文档模式、任意数值/实体、完整modeling suite或整个系列release已验收。未测域不得直接算作本系列已完成或擅自后置发版；由统筹本人按既定系列范围审查收口。


## 范围与接口 diff

- 唯一 worktree `/Users/YJBeetle/.codex/worktrees/docprops-line-style/SWCLI`，分支 `codex/docprops-line-style`，创建基线 `3bda2c00489dde6a3d1e4521c548f751b1d1c197`；初始干净，无 .codegraph。
- `document.line-font` / `swcli document line-font`：`options` 四字段完整 native integer map。
- `document.line-font-set` / `swcli document line-font-set FIELD VALUE --if-options JSON`：输入 `field`、`value`、完整 `expected_options`；沿用 document_id / expected_update_stamp / lease_id。
- 字段：visible_edges.style / visible_edges.weight / hidden_edges.style / hidden_edges.weight。仅 drawing 文档默认值。
- 开放域仅 revision **33.5.0**：visible style 0→1、visible weight 1→0、hidden style 1→0、hidden weight 0→1；0/1 noop无setter。逆转换、其他版本、weight 2、自定义厚度、线宽表、端帽、实体/层/组件覆盖、parts/assemblies、全局系统偏好均不开放。无网格/基准面/注释箭头字段扩展。
- 官方 API：IModelDocExtension Get/SetUserPreferenceInteger + swDetailingNoOptionSpecified，ID 从标准安装位置官方 swconst.tlb 按名解析；文档依据见 `docs/design/document-line-font.md`。
- 正常回执：field / before / options / changed / mutation；描述符收尾故障新增可选类型化 `finalization_error: {type,message}`，保留 mutation 与首 error 原值、已知session_id，不伪造无法取得的post descriptor。SDK models已同步。

## 两项 peer 产品阻断的现 head 证明（mock-only）

来源为只读 peer 报告 `docprops-coverage-ci/SWCLI/docs/verification/docprops-handler-peer-review-2026-11-07.md` 与原 `repro.py`，不是原生现场故障。

1. `operations.py:440 document_line_font_set` 捕获 `_with_document` 收尾异常，adapter receipt仍是唯一mutation事实。新增真实 `_worker_main -> execute_operation -> adapter -> handler -> result validator -> error envelope` 测试：native成功与首native失败后describe抛错，worker响应仍带mutation双true；SDK/MCP bridge也保留部分结果及首error。
2. `windows_document_line_font.py:76 _capture_guard / :84 _verify_guard` 保护目标title/path/access/仍打开，以及不同前台peer的kind/config/stamp/dirty/title/path/access/既有sketch-sheet上下文；同一ActiveDoc指针不再代表状态不变。拒绝漂移，不恢复/回滚；目标本身为前台时仍允许合法目标stamp/dirty变化。

- 在当前源码运行 peer 原 `repro.py docprops-line-style`：描述符异常现在返回mutation双true；同指针foreground stamp/dirty/title/path四项均拒绝，setter仍只调用一次。
- `tests/test_line_font_postconditions.py` 包含完整worker与SDK/MCP负例；额外保护configuration/access/sketch、目标身份/关闭、mutation前漂移。34项相关测试通过。
- 产品变化后完整便携回归 **1853 tests passed，32 skipped**；`artifacts/line-font/postcondition-full-portable.log`。SDK generator/strict typing/8项consumer拒绝通过。
- 本地持久 mock 原输出及精确源码/repro hashes：`artifacts/line-font/internal-peer-fix/`（implementation_commit=80b6133...）；不把 mocks 宣称为原生验收。
- 公开gate已增加逐次foreground完整descriptor比较；typed SDK read/noop 与 MCP live bridge execute/noop包含，**不宣称 MCP stdio transport 验收**。

## 已核内部原生证据（与公开证据分开）

- [42260712677](https://github.com/YJBeetle/SWCLI/actions/runs/42260712677)，head `6f531a595a50bbadeeab2c0f005d89c0246c7ee5`，success；line_font_calibration=true / native_full=false，其他默认。
- artifact id `13526587857`，SHA256 `5d8152062aea15f32d40c10f0947f36bceb0458702387fff0f2ef09b5ecc64e9` 已与GitHub digest核一致。
- 每字段1 setter / 12 preference getters，四项精确转换、背景文档、save/reopen、readonly拒绝与owned host清理通过；完整原ZIP/metadata/expanded本地保存在 `artifacts/line-font/internal-42260712677/`。
- 独立审计 `artifacts/line-font/internal-audit.json`，脚本 `scripts/ci/audit-line-font-calibration.py`；fixture SHA256 `92cae239235e0a5193ef0ff9577c48913cde3dc3137f5d8a30601c559cc08d98`；report `879d12f4821198e5d61fda9ebefb2e6c407dc93a95036a01fe43de1bb185ee6e`；trace `9bae5562b290c1b6865d14c768b68debae85d5bab23aa7d62833d059187a14e4`；process log `f17c814825db46044a9101cef0e054312b5949b648e3a494ff8cda8dae91248b`。
- 此证据建立叶API/值域，不代替最终保护修复 head 的公开验收。

## 已保存的真实公开失败与更正

- [42272391578](https://github.com/YJBeetle/SWCLI/actions/runs/42272391578)，head a783b498...，failure；artifact id 13533098590，SHA256 `a3064f349b415f4c7cc5f7435a7d3a5e7607f2821c66a2d36c46cf50fe4fddbb` 已核。
- 本地 `artifacts/line-font/internal-public-42272391578/` 保有原ZIP/metadata/expanded/job log；原job log 63876字节，SHA256 `af8a37335d586d9126774387337bd3d049f4ce6e922d4beb69ad11c31aca660e`。
- 第一真实失败为 gate `KeyError: health`，还未进入line-font读写；未预建summary导致final checkpoint报stat失败，原job log仍保存首错。二者均已在 c377d4f 修复并联测。
- **撤回先前错误的“共享 ModelingSmoke.health 不兼容”提醒**：普通 CLI `daemon status` 走 `daemon.health`，基类helper与该路径兼容；只有 `--details` / DaemonManager.status 走嵌套runtime-status。是本分支先前混淆路由，不要把那条提醒应用到其他分支。
- 其他取消/误触发仅历史，不算验收：42260403395（native前并发组修复）；42266835193（错误health判断后取消）；42269536427（真实worker命令scope parser修复前取消）；42272160735（GitHub拒绝push时误指旧head，立即取消）；42278005133（peer已mock证实产品缺陷，portable阶段取消）。无其他线程run被取消。
- Parser现在严格核真实owned worker CommandInProgress进入/恢复，再核业务pref读写、状态观察与request边界；没有放宽状态/几何断言。

## CI路由、共享文件与权限

- bc619f3 修复真实空绿路由：portable安装前拒绝 native_full / line_font_calibration / line_font_public 多选，以及线型开关错误branch；56组组合、CLI env解码与YAML接线测试通过。默认portable、单独full及合法tag-policy路径保留。
- 共享修改：cli.py、daemon/operations.py、operation_schemas.py、result_schemas.py、SDK _generated.py/models.py、.github/workflows/ci.yml；其余线型专属文件。复用annotation的上下文保护helper，未改其字段。最终冲突由统筹处理。
- 保留 main 已有0e72beb，不为本轮rebase/合其他未验收分支；未操作占用VM、DockerSW/MacSW、main或发布。
- 曾被自动审批拒绝：将原native ZIP/metadata/audit一并推送至可见性未核的远端，因可能含内部日志/测试文件。已采用获准安全替代：原件仅本地持久保留；远端仅推代码、便携测试与hash/永久run引用摘要。未绕过审批，当前无待审批动作。
