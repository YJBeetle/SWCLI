# GLB 首失败诊断与待证候选

## 2026-11-12 历史 Blender 成功线索与原件对照

用户确认此前 SWCLI GLB 在 Blender 实际导入可用，具体文件/运行尚未知，不要求复测。已先行[独立核对现有历史原件](../verification/glb-history-offline-2026-11-12.md)：两次同组旧 API assembly 均为真实 BIN720/12三角形，part 均为 BIN0；保存/RO重开零件与首次关闭重开前装配体上下文不同，不能归因未证明的文档/版本/API因素。成功 GLB SHA `4091246c9af29a4c858ba73e815c9150dbc37d4c4f9e52d6dabbc4f71e345421` 与未改字节副本已固定；保留旧过宽校验曾误接受 part 与实际 assembly 成功并存的事实，不泛化历史一直失败。离线重放结果逐字节一致，本地提交 a40b77f；无新 CAD/Blender/CI 运行。

## 2026-11-12 固定文件采集已完成

统筹对 e6fc46c 仅执行一次零 CAD collector，四 required DLL 全为 AMD64，实际版本／hash／双渠道 stat 指纹稳定，metadata helper exit=0；两项旧 XR 背景文件缺失。73 条静态导入只作固定位置存在性观察，签名只解码不验信任。[独立审计](../verification/glb-exporter-native-inventory-audit-2026-11-12.md)不升级为运行依赖或 GLB 支持。既有 [C# 同 host／同 document 候选](../../scripts/diagnostics/typed_glb/README.md)现已准备，19项 Python 协议/包装器/原件审计测试及34条 C#纯断言通过；整份源码仅对测试替身做 C#5 编译。实际 Windows PIA 编译、管道/COM握手和GLB调用仍未执行；交统筹亲审后先零CAD编译，再零GLB保存身份预检，最后另行单次invoke。不扩路线、不回旧API、不修BIN，不把准备通过当GLB修复。


## 2026-11-11 局部证据与当时安排（历史）

- 固定 d2a8e606 的 fresh Parameter B seed 私有 part/front fixture 已由统筹单次运行通过；七个独立圆几何窗口及四个目标 Get3 观察窗口、保存只读重开、源哈希及清理均经[独立离线审计](../verification/getter-fresh-binding-native-audit-2026-11-11.md)。不替代 CI/full/public 验收。
- 已审阅 1beaa471 driver、固定 70d8c9e 的可见启动对照由统筹单次执行，实际 Visible=true/CIP=false 下 part GLB 仍为 JSON3704/BIN0，首错停止。[原件审计](../verification/glb-visible-startup-native-audit-2026-11-11.md)保留三个成功格式、四次现代导出、无 GLB after CAD 读取、原始文件和清理边界。
- 本路未操作 VM／CI／push。下一优先级为当前安装 exporter 的零 CAD 定点文件证据，见[信息增益评估](../verification/glb-exporter-next-evidence-plan-2026-11-11.md)；已准备[定点零 CAD collector](../verification/installed-glb-exporter-inventory.md)及反例测试；17deb54 首轮在 stat/fstat 比较处失败，metadata helper 未到。独立 probe 与固定 CPython v3.14.7 源码支持[窄 ctime 修正和原值 observer](../verification/glb-exporter-stat-ctime-2026-11-11.md)，新候选尚未原生重跑；typed bridge 未实施，不再盲试可见状态、CIP、参数、旧 API，也不补写 BIN。以下早期候选与门禁安排保留为历史记录，执行由统筹亲审调度。


## 2026-11-11 显式BSTR数组seed候选与独立几何门禁

统筹对原saved-A的独立几何原件已核report SHA256 `5a03ba2feea9c08c4513c04aabe21d1586bf922144d7de5d2587b0b5f011829c`：原SLDPRT hash `80455d6d94ea72776e44605b20e56c1fcc09879d558250569db7f3cadd744257` 前后相同，默认A实际为唯一完整非构造圆、半径10mm/直径20、中心0。前后state相同、config/foreground身份严格int1，原生trace独立重算GetRadius一次且0 Get3/Set/rebuild/save。原件路径 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/getter-geometry-7119626-02/`。该结果支持先定位fixture seed，不证明产品Get3整体通过；此前01 warning误拒绝仍保留，未据此改变本fixture原只读重开门禁。

经统筹授权，本次候选只将fixture B写入的Config_names从str改为 `VARIANT(VT_ARRAY | VT_BSTR, (second_name,))`。原creator返回的dimension handle、AddConfiguration2全部参数/Options=0、名称、20mm目标、装机枚举3及单次setter严格int0均保持。记录实际VARIANT类型/VT/唯一名称，以及setter原返回类型/值或首异常；不重试、无BSTR/current/all回退。官方允许两种配置名称形式，故此仍是待原生验证的封送对照候选，不称已修复。

新增7个独立几何准备窗：initial-A=半径8，seed-B=10、seed-A=8，saved A/B及readonly reopened A/B各8/10。每次按当前document与实际草图名重新定位ProfileFeature，调用既有严格圆弧几何校验，完全不调用_descriptor/GetSystemValue3。要求唯一完整非构造圆、中心0、有限半径、part/readonly/edit-context可观察且已退出编辑，前后document/config/foreground/state及保存文件hash保持。seed阶段预置不符在首次保存前停止；保存/重开后的几何不符则在对应产品Get3窗前停止。每个原Get3窗口本身及A16/B20期望、单BSTR/单次Get3、元数据和身份保护均未变。

监督器新增独立几何trace硬门禁：7个不同请求齐全，每窗GetRadius一次/同一worker，拒绝Get3、setter/rebuild/save或其他未知调用；原读窗口trace规则、process.pid身份绑定和600/1800预算保持。模拟B seed同时污染A为20会在seed-A几何证明处停止，0保存、0产品观察。

38项关联、2620项完整回归OK（27环境跳过，76.161s），SDK strict6文件/31类型拒绝例通过。observe_current/audit_read_trace等9个函数AST不变，产品src/CI/STL/interop工具字节不变。原件、源码及日志hash见 [候选回执](../evidence/getter-array-seed-geometry-candidate-2026-11-11.json)。本轮本地提交，不push/VM/CI；由统筹亲审后安排一次新小范围原生诊断，失败仍首停。

## 2026-11-11 saved-A数值首错与独立预置证明计划

统筹精确7119626本地单样件原件已核report SHA256 `8217746e38b75b1a7b52cadc64d682760b91397d99f684feb5ffbf56a2ab695b`。身份准备必要比较均严格int1，两次重建及现代SLDPRT保存true/0/0通过；第一个saved-A窗口实际GetSystemValue3(3,'默认')单次返回tuple[.02]，descriptor20mm，期望16，首错为native getter value/metadata mismatch。B及只读重开未到达；不得称四窗读取通过。原生调用worker84、监督器launch2604、SW3012，分别记录。

官方SetSystemValue3 2025正文与可读Get3正文均允许Config_names为single BSTR或BSTR array。装机33类型库实证两者该参数为VARIANT，并不证明具体封送语义。当前不能断言BSTR非法、seed一定写错或产品Get3一定选错；不调整A期望、不重试API。本路产品和夹具仍保持7119626源码。

建议先在原文件只读副本中、0 setter/Get3/rebuild/save地定位A草图，使用既有纯圆弧几何路径GetRadius：A半径10mm指向夹具真实几何为20；A半径8mm则与原Get3的20构成独立矛盾。若后续新夹具采用一次显式SAFEARRAY(BSTR) seed候选，必须先独立几何证明A半径8/B半径10，不能以被测Get3自证；每个saved/RO目标窗口前仍需独立几何检查，原Get3单次单BSTR及期望不变。此项只有方案，未实施。

原件及阶段边界见 [saved-A首失败回执](../evidence/getter-saved-A-value-first-failure-2026-11-11.json)，绑定事实、官方来源、最小单变量候选及拟补反例见 [独立几何证明方案](../verification/getter-independent-geometry-proof-plan.md)。本轮没有VM/CI操作。

## 2026-11-10 身份比较准入修正

统筹的精确 `28a1d0bda7a7efc96e92885f1def491464bc204f` 本地单样件报告已核SHA256 `02fb64ed05afdbeff0b89d405af1bfba59e2ab27e381bc94e64aa7aa93e2863c`。原件目录为 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/getter-fixed-28a1d0b-01/`。B重建已实测bool True，Show A单次返回bool True；随后旧夹具跨配置比较IsSame(B,A)的严格0/1检查报native identity is unreadable。原返回值/类型未保存，不能补写为int2。observations仍空，保存/四窗/STL/GLB均未到达。原件及cleanup结果保留，不把本地准备通过算公共验收。

统筹批准的修正仅在诊断夹具：每次IsSame先追加角色，逐项保存真实返回类型/值及分类，然后将完整report.json checkpoint写出，再严格判断；异常也记录并保持原异常，即使随后checkpoint失败仍不覆盖首错。准备字段按读取得到的顺序保存，消除dict.update参数求值失败导致after_name等已取得字段丢失。

跨B/A的负向身份比较不再调用或作为准入，也不会把Unsupported转False。准入改为前后精确两配置集合、目标Name、切换前绑定document与foreground相同、切换前后foreground身份相同、切后稳定active配置身份。已是当前配置时仍0Show且保留同配置对象恒等检查；需要切换时仍仅1Show且严格True，失败不通过读取后状态恢复。所有必须相同的比较对0、2、bool、None和未知值均不能放行。装机swconst新增核对NotSame=0/Same=1/Unsupported=2的严格int枚举。

读取窗口保留同配置和foreground恒等保护、原单次Get3/单BSTR/唯一数组/mm、metadata与状态比较；只为两个既有IsSame附加角色/原值和checkpoint。去掉这两个调用的新增证据参数后，整个observe_current函数AST与28a1d0b完全一致；audit_read_trace、supervise、600/1800预算及重建/编辑状态函数AST也保持。产品src、CI、原STL门禁逐字节不变。报告另记native_call_worker_pid=os.getpid，监督器启动PID与实际原生调用PID不混称；本次没有改变既有监督器PID准入条件。

旧函数先以合成int2复现误拒绝及after_name丢失；这不是回填旧现场。新增文档/配置集合/配置身份漂移、正向身份2/bool/None/未知/异常拒绝、晚期异常保留前字段及磁盘checkpoint、0Show/1Show与读取窗口保护反例。29项关联、2599项完整回归OK（27环境跳过，78.904s），SDK strict6文件/31类型拒绝例通过。详见 [身份准入回执](../evidence/getter-identity-admission-2026-11-10.json)。本轮本地提交，不push、不派CI或操作VM，交统筹按精确新head继续独立目录小范围诊断。

## 2026-11-10 本地首错：无参重建绑定

统筹在其独占Windows VM中，以精确 `70d8c9ecf3c02b099ca9c2cc64fe1880061cea44` 和明确local/private driver，仅运行一个两配置样件。原件目录为 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/getter-fixed-70d8c9e-01/`。原report SHA256已重算匹配 `5a607ed5119064a7e2c92c19cdbdcd0772723d9c810b26315ac49d36ea37c1a0`；SW33.5.0、owned host3928、worker2832，Python3.14.7 x64。运行31.386s首错停止，supervisor的pids before/after均空，worker_exit=1，report.cleanup_errors=[]。这是本地私有诊断，ci/public/full acceptance标记均false。

本次实际观察到AddConfiguration2后Getter_B已经current，show_attempted=false、前后Name相同、两次IsSame均true，active_sketch=false；70d的预先跳过路径在该宿主通过。该结果不补填旧CI42663675963缺失的current/raw return。prepare-B-value结束后，prepare-rebuild-B在 `document.EditRebuild3()` 产生 `TypeError: 'bool' object is not callable`：动态绑定已经返回bool，随后Python追加调用失败。布尔原值未保留，不能声称实际True或重建成功；保存及四个读取窗口仍未到达，没有新增STL/GLB验收。

本次仅将两处B/A无参重建统一交给项目既有 `_com_value(document, "EditRebuild3")`，与windows_documents重建惯例一致；不做bool强转，仍严格要求 `status is True`，每个边界仅一次求值。新增重建准备记录保留attempted、真实返回类型/值或首个异常，再原样失败；False/非法类型/异常无fallback、无重试。脚本其余无参SOLIDWORKS成员已使用_com_value；剩余直接无参调用只是显式类型库接口GetTypeInfoCount/GetTypeAttr，没有新增动态文档无参调用。

完整布尔绑定夹具在旧代码上先复现同一TypeError。修正后18项关联通过：布尔属性和真正callable各跑完整saved/RO四窗，B/A各仅一次重建；两种绑定的False/0/1/-1/None/string拒绝及原异常保留均通过。完整2588项OK（27环境跳过，79.421s），SDK strict6文件/31类型拒绝例通过，diff检查通过。产品src、CI和STL原门禁逐字节未变；读取窗口、配置选择、trace审核、常量和600/1800预算七个函数AST不变。原件/源码/日志hash详见 [无参绑定修正回执](../evidence/getter-rebuild-binding-2026-11-10.json)。

本路只完成离线修正与本地提交，不push或派CI，不操作VM。统筹继续安排精确新提交的小范围原生API验证；任何本地通过也不替代完整CI。原70d失败文件保留，后续结果写入独立目录，不覆盖原件。

## 2026-11-10 组合首失败与最小夹具修正

唯一一次组合运行 [42663675963](https://github.com/YJBeetle/SWCLI/actions/runs/42663675963)，精确 head `dd5a3ec5dd06594005d4b6f4b232c5460da1df13`，结论 failure。六份官方 artifact ZIP 已保存，尺寸、CRC 与 GitHub SHA256 digest 均匹配；安装原日志仅保留本地。native 原 ZIP 为 `original-native.zip`，184115 bytes，artifact `13697876346`，SHA256 `ab38c312bb92b06c5efbc443dba4f9cd98ebee1d40150c59ebedc31ca2f4b2c6`。原件根为 `/Users/YJBeetle/.codex/task-artifacts/glb-export-repair/20261110/run-42663675963/`，run/jobs/artifacts JSON、完整日志 ZIP 和解压报告均保留。dist wheel 的127个包文件与该 head 逐字节相同。

| 阶段 | 本次实际范围 |
| --- | --- |
| Windows Python3.9/3.14 portable、package | 通过，含之前 Windows 文件身份取证复制修复 |
| installed modern API contract | 通过；只读类型库，model_calls=0，native_binding_accepted=false |
| 两配置 getter | 准备阶段失败，四个 saved/RO A/B 读窗口均未进入 |
| 原 STL 八场景配置观察 | CI skipped |
| 原 full19组及 GLB 运行时取证 | CI skipped，没有新 GLB/BIN/manifest 证据 |

SW 为33.5.0、owned PID8652。`AddConfiguration2(..., Options=0, ...)` 返回非空对象且 Name=Getter_B 的检查已过；首错为随后 `prepare-select-Getter_B` 的返回值未满足 `is True`，报 `RuntimeError: fixture configuration selection failed`。旧原件没有记录返回原值/类型、切换前 current 和准备编辑状态，不能把它写成“实际False”或“当时B已经激活”。尚未到 B seed、保存、重开或本诊断的 Get3 观察窗；不据此判断产品 getter 绑定或 GLB 失败。清理 trace 的 CloseDoc/ExitApp/进程等待等均结束，report.cleanup_errors=[]；原 supervisor.cleanup_proven=false 保持原值，不提升为清理验收通过。

官方 [2025 configuration options](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swConfigurationOptions2_e.html) 说明 DontActivate 位为128，未设置时会激活新配置。因此“创建已激活B又重复Show”是有依据的候选解释，仍是推断。[ShowConfiguration2](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~ShowConfiguration2.html) 的官方 Boolean 契约未承诺已激活目标时的专门返回行为，不能用模拟False补填原现场。

最小修正提交 `70d8c9ecf3c02b099ca9c2cc64fe1880061cea44` 仅改诊断夹具和测试。选择前记录实际 current Name/编辑状态；已是目标时零Show并核对象身份，确需切换时仅一次Show且仍严格True，然后验证目标Name、稳定active对象和前后身份变化。False、非bool和异常均保留首错，不读后状态尝试恢复，不重试。记录原始返回类型/值、准备阶段及末尾编辑状态。产品Get3/SaveAs3/GLB、原STL计划、读窗口/trace审核和600/1800预算均保持不变；五个核心函数AST与七个产品/CI文件已比较不变。

合成已激活目标返回False的反例在旧夹具上先复现9项中1error；修正后14项关联通过。完整2584项OK（27环境跳过，74.208s）；SDK strict6源文件/31类型拒绝例、actionlint和安装资源no-COM通过。原件摘要、源码及日志hash见 [机器回执](../evidence/getter-preparation-first-failure-2026-11-10.json)。本次没有使用VM或派发新运行，main及其他路线未修改。

### 交统筹的小范围原生 API 验证方案

1. 由统筹统一启动并核对Windows VM、实际SOLIDWORKS版本、进程归属和已有文档；材料集中 `C:\Workspace`。本路不自行启动或抢占VM，不运行本地整套full。若VM版本与CI的33.5.0不同，记录差异，结果仅作该环境验证。
2. 用自有临时零件和精确修正代码，先验证创建B后的实际current和编辑状态；目标已经当前时必须0Show，切换至另一个配置时必须1Show、原始boolTrue及后Name/对象身份通过。任何失败保留首次报告/trace/原始类型值并停止，不通过重试/重启覆盖首错。启动入口由统筹选择，不能伪造GITHUB_ACTIONS绕过CI入口限制。
3. 若首项通过，沿用原夹具A16/B20、保存及只读重开四窗，原Get3次数/单BSTR/唯一数组/mm、Name/type/driven/readonly、配置/修改戳/前台和清理断言全部保留。准备时配置切换仍在读窗外，不扩大公共支持域。
4. 如统筹安排单独GLB验证，只使用保留的原零件输入并在调用前后核原件hash，单次现代SaveAs3与原暂存模式/参数保持，启用既有有界manifest/隐藏文件/模块/类型库只读观察。保留原GLB字节并照原严格BIN检查判定；未知状态明确unknown，不改偏好或扫描试探API。该步是新观察设计，不代表修复或公共验收。
5. 完成原件审查后，由统筹决定精确新head的一次必要组合CI；顺序仍为modern contract → 两配置 → STL → 原full。不得同head无信息重跑，原失败ZIP/运行结论保持。只有通过统筹亲审才进入后续main集成；发版仍需用户最终确认。

## 2026-11-10 修复与组合接线

Windows push 42420883808 的两版单元测试都在取证复制阶段失败。DirEntry.stat 在 Windows 返回零设备/文件ID，使原严格身份比较误拒绝并留下空副本。新代码改用新鲜 os.stat(..., follow_symlinks=False)，在源身份检查通过后才创建目标副本，保留原竞态拒绝逻辑。两个新回归先复现旧错误再验证修复。[Python 对该 Windows 行为的说明](https://docs.python.org/3/library/os.html#os.DirEntry.stat)

已纳入 getter 产品 b9c5e3c 与交接992c283，组合 full 在原 GLB 步骤前执行两配置A16/B20的saved/只读重开proof，以及原STL八场景现代配置trace门禁。顺序、精确分支、默认关闭、依赖及首错停止均有静态检查。完整2579项OK（27跳过），SDK strict6源文件/31拒绝例、actionlint和安装资源检查通过。原日志及逐文件hash见 [本次检查回执](../evidence/glb-runtime-portable-repair-2026-11-10.json)。

本轮将最终head交统筹亲审，尚未派发组合native_full。后续各节保留此前诊断与设计记录。

## 运行时取证实现与组合验收前置

现代 API 产品 `0a00751e44823ca46237000479754634bf50a418` 已在本分支与 main `960839e52d0c433c817e71e02493a27681f7e858` 合并，merge 为 `0e288dd`。两侧 CI 分组、交接历史和 main 三组偏好晚期错误保护均保留。main 新增三偏好夹具已适配 ConfigurationManager.ActiveConfiguration，保留配置漂移、首错误与 worker receipt 断言。

`SWCLI_GLB_RUNTIME_DIAGNOSTICS=1` 才启用新增观测。它包围原来那一次现代 SaveAs3，生产暂存名仍沿用原始后缀。调用前后的 manifest 放在目标目录下可见的 `swcli-glb-diagnostics-<uuid>/`，与原 request_id、Python worker PID、SOLIDWORKS PID 对应。阶段分别为 pre-save 和 post-save-before-validation。

- 保存前后读取同一暂存 stem 前缀的目录项，包含点号/隐藏文件，记录 size、mtime、属性、SHA256 和复制文件映射。复制使用可见 `.bin` 文件名，保留内容原字节。每阶段最多 128 个文件、64 MiB，单项观测 15 秒，目录项为非普通文件/reparse、发生竞态或超过边界时明确标为 unknown/incomplete。
- 使用同一观测到的 SOLIDWORKS PID 打开只读进程句柄，前后枚举最多 2048 个模块，筛选 sldgltf/SPAXGLTF/VisGltf、Draco 与 XR exporter 的实际路径，读取实际文件及产品版本。句柄在 finally 关闭。
- 保存前从显式安装路径 `SWCLI_GLB_DIAGNOSTICS_SWCONST` 读取 swconst.tlb、SHA256 与版本，要求 major 33。只对实际 GLTF/GLB/Draco/XR 相关枚举，依据已知全局 preference 枚举类型选取已有 getter。其他枚举仅记录原 ID，getter 不可读时记 unknown。保存后仅做文件与 OS 观察。
- 文件访问监控字段明确为 unknown，当前没有经过验证的本 PID 有界采集器。模块加载清单也可能记录 inaccessible/unknown。诊断收集、manifest 或 stderr 写入失败均不能改变保存结果或原错误。

CI 仅在 `codex/glb-export-repair` 的现有 native_full 步骤开启该开关，复用安装和所有原完整组。该 full 使用独立并发组，cancel-in-progress false。没有新 dispatch 输入。取证文件目录可被现有关闭隐藏文件上传的动作正常收集。

统筹补充的两配置异值 getter 与 STL 新配置入口 proof 仍是本次 full 的前置。原 getter 负责人准备精确门禁接线，待其提交与统筹本人审查完成后，才组合到同一必要运行中。当前未派发本轮 native_full。便携组合2567项OK（27跳过），新增10项取证测试、三偏好56项组合保护、SDK strict6文件/31类型拒绝例、actionlint及YAML检查通过。日志在 `/Users/YJBeetle/.codex/task-artifacts/glb-export-repair/20261108/`，首轮夹具不兼容和修复后的日志均保留。

首阶段离线审计已完成。当前可复核的内容失败是原生 GLB 声明 720 字节嵌入 buffer，实际 BIN 长度为 0。导致原生写器产生空 BIN 的上游首因仍缺运行时证据。当前生产容器校验正确拒绝该文件。

## 工作边界与来源

独立工作树为 `/Users/YJBeetle/.codex/worktrees/glb-export-repair/SWCLI`，分支 `codex/glb-export-repair`，基线为本次 fetch 后的 main `960839e52d0c433c817e71e02493a27681f7e858`。执行源码取自失败运行精确 head `0a00751e44823ca46237000479754634bf50a418`，以 git blob 的 SHA256 记录。现代 SaveAs3 迁移由原负责人处理。本阶段提交离线报告和验证方案。

本次原件根为 `/Users/YJBeetle/.codex/task-artifacts/saveas3-modern/20261108-combined/run-42405530053/`。原 native ZIP 为 9159929 字节，artifact `13587729372`，SHA256 `a55c00d7e4b7d07cbece2acd0ef5847138efc074f9ddaa3bfead0aef9e967ec9`，实际重算匹配原 metadata。[失败运行](https://github.com/YJBeetle/SWCLI/actions/runs/42405530053)

机器可读审计为 `docs/evidence/glb-export-failure-2026-11-08.json`。持久审计脚本、原 GLB 副本、选定 trace 和安装日志证据在 `/Users/YJBeetle/.codex/task-artifacts/glb-export-repair/20261108/`。

## 本次原件的直接结论

- 首失败来自 assemblies 组中的零件 `component.SLDPRT`，文档类型为 1。相同源先前的 STL、3MF、AMF 均通过当前容器校验。
- GLB 为 `component-export.invalid-native.glb`，3800 字节，SHA256 `2d49602f1bbd443d60b8975d249b4ed8defb5a5948b869eabfddacb1974a2c5c`。ZIP 成员与解压件逐字节一致，CRC32 为 `66faabfe`。头部声明总长也是 3800，JSON chunk 为 3772 字节，第二个 BIN chunk 长度为 0，恰好到文件末尾。归档压缩或解压未改变该成员。
- JSON 的唯一 buffer 无 URI，声明 byteLength 720。三个 bufferView 分别覆盖 `[0,144)`、`[144,432)`、`[432,720)`。JSON 声明了 36 个索引、24 个位置和法线，但文件没有这些数据。JSON 未声明 Draco 或其他压缩扩展。当前 main 的原容器校验独立重放返回 False。
- glTF 2.0 的无 URI 首 buffer 由 BIN 提供，其长度最多允许多 3 个对齐字节。该文件不满足这条规则。[Khronos 规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#glb-stored-buffer)
- 请求 `7712054a-7f17-495b-a30a-7d37690bd042` 的 108 条 native trace 位于 `hidden/runtime-sets/daemon.log`，包含 54 个完整 begin/end 对，同一 COM worker PID 为 936。`IModelDocExtension.SaveAs3` 只有一次，耗时约 16 ms，无 native error 事件。公共回执为 api_saved true、errors 0、warnings 0，随后返回 ExportVerificationFailed。原 trace 不记录方法参数。
- 精确执行源码调用 `SaveAs3(name, 0, 1, null-dispatch, null-dispatch, byref-I4-errors, byref-I4-warnings)`。本次 `modern-api-contract/report.json` 的 SW2025 typelib 实测也列出这七个参数。首参数是既有暂存路径，最终发布在内容校验后执行。

## 路径、暂存与大小写

本次请求目标为 `component-export.GLB`。精确源码的常规暂存模式为 `.component-export.<uuid>.swcli.GLB`，沿用用户后缀。该次普通 full 清除了内部 plain-staging 开关，工作流仅设置 rejected-GLB 保留开关。实际随机暂存名未记录在回执或 trace 中。目标路径为 ASCII，JSON 解码后的路径分隔符正常。

原 ZIP 中没有 `.bin` 或 `.gltf` 配套成员。不过本次上传步骤明确为 `include-hidden-files: false`，暂存文件又以点号开头。因此归档成员的缺席不足以排除运行时隐藏 sidecar 的存在、错误路径或中间文件丢失。GLB 的无 URI 声明仍要求嵌入数据，现有内容失败成立。

补查历史原件得到以下对照。历史 ZIP 均重新核 SHA256，只作为路径假设的辅助证据。

| Run | 保存 API | 由精确源码与诊断分支确认的暂存模式 | GLB 结果 |
| --- | --- | --- | --- |
| 42265919228 | IModelDoc2.SaveAs3 | `.cylinder-coarse.<uuid>.swcli.glb` | 3816 bytes，声明 3696，BIN 0 |
| 42301795947 | IModelDoc2.SaveAs3 | `swcli-<uuid>.glb`，ASCII 单扩展小写 | 同上，GLB SHA256 与前行完全相同 |
| 42405530053 | IModelDocExtension.SaveAs3 | `.component-export.<uuid>.swcli.GLB` | 3800 bytes，声明 720，BIN 0 |

当前现代 API 运行没有成功的小写对照。历史小写单扩展仍失败，使“单凭大小写或多扩展名解释全部失败”的依据不足。它也不能回答现代写器是否另有大小写分支。Windows 文件系统的大小写规则无法单独证明写器内部的字符串处理行为。

可审的最小待证候选仅规范内部 GLB 后缀，保留用户最终目标名称。它尚未作为生产修复应用或验证。

```python
staging_suffix = ".glb" if export_format == "GLB" else output_path.suffix
# 常规暂存文件仍使用既有 stem/uuid/.swcli 前缀，仅替换末尾后缀。
f".{output_path.stem}.{uuid4().hex}.swcli{staging_suffix}"
```

候选的便携验证应覆盖大写、混合大小写及小写目标，内部后缀、最终文件名、一次保存、失败时原目标保留、现有空 BIN 拒绝均需独立断言。真实 GLB 是否恢复需要原生字节证据。

## 官方 2025 说明与已装组件

SOLIDWORKS 2025 官方更新说明确认 SP2 把 XR 导出选项移入 System Options > Export > GLTF/GLB，列出场景、动画和 Draco 选项。它说明支持的导出入口和选项，未提供空 BIN 的成因。[官方 2025 更新说明，印刷页 172](https://files.solidworks.com/Supportfiles/Whats_new/2025/English/whatsnew.pdf)

2025 SaveAs3/枚举在线条目在本次访问中返回帮助站外壳或 403，未取得 GLB 专用数据对象或选项的可靠正文。API 参数契约依据本次安装的 2025 typelib 与精确调用源码。后续选项读取需从实际安装的 swconst.tlb 确认名称、类型和数值。

同次原安装日志 artifact `13588666282` 为 3278666 字节，SHA256 `eced0a0b91ec041025237d28aedc8cbe332b50f6df645ce2769355e9095c8055`，已核 GitHub digest。原件保存在上述独立诊断目录，相关非敏感行提取为 `installer-gltf-evidence.json`。

- `sldgltfu.dll` 的 MSI Action 为 Local，有 FileCopy 与 ComponentRegister，版本 33.5.0.53。
- `SPAXGLTFBase.dll`、`SPAXGLTFVisualization.dll` 同样有 Local/FileCopy，版本 6.427.0.25092。`VisGltf.dll` 为 6.427.3.25060。
- 旧 `SWXRExporter.dll`、`.tlb`、资源组件的 Action 为 Null，其安装/卸载条件均 false。结合 2025 架构变化，这些行不足以证明应启用旧 add-in 或把当前失败归为漏装插件。

这些安装记录发生在 runtime overlay 之前。当前仍缺实际导出时加载的模块路径、版本和依赖解析结果。

## 下一次必要验证应补足的证据

先准备以下观察，使一次新候选调用具有判别力。相同失败 API 的原参数重跑不提供对照价值。

1. 在保存前记录传给 SaveAs3 的精确暂存路径、后缀及目录快照，保存后、finally 清理前再次枚举，明确包含点号/隐藏文件。只保留该次暂存前缀对应的文件，记录每个文件长度、SHA256 和时间，并放入可见诊断目录供原样上传。归档缺席才能与“从未存在”区分。
2. 通过 OS 只读清单记录导出器与依赖的实际加载路径、版本，以及导出期间失败的文件访问路径。对未记录的加载/文件 I/O 状态明确保留 unknown。MSI 的 FileCopy 不能替代该运行时观察。
3. 从已装 2025 typelib 只读解析 GLTF/GLB/Draco/XR 相关 API 与选项名称、类型、值，再读取实际偏好。未知 ID 或文档缺口保留为缺口，不猜 enum、设置 ExportData 或改变全局偏好。
4. 若整合后的候选确有必要进行原生验证，使用原装配组的同一零件场景和现代 SaveAs3，保持单次保存。保留真实回执、完整 trace、失败原字节及上述观察，首失败结束该组。新增信息应能区分名称/sidecar、加载依赖和写器内部缺失数据，才有依据选择下一项最小实现修复。
5. 成功须同时满足原有容器/几何门禁、BIN 与 accessor 实际范围、源文件/文档状态、原目标发布及同组清理要求，并由统筹本人复验原件。此次离线阶段已完成原 GLB 拒绝重放、其余三种格式重放和完整 trace 配对检查。

本阶段未派发 CI。系列的最终 review 与 main 集成由统筹本人完成，正式发版仍需用户最终确认。
