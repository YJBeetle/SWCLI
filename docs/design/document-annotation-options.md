# A18 文档注释标量选项

A18 开发候选在 A17 长度显示选项之上，增加 `document.annotation-options`
只读列举和 `document.annotation-option-set` 单字段写入。它对应
“选项 → 文档属性 → 注释”的一个有限子集，不代表整个页面、全部文档选项或字体已开放。

| field | 公共值 | 文档级原生 API / swconst |
| --- | --- | --- |
| `arrow.edge_vertex` | 写 `closed` / `dot`；读保留其他原生样式 | Integer preference 38、option 0，`swDetailingArrowStyleForEdgeVertexAttachment` |
| `arrow.face_surface` | 写 `closed` / `dot` | Integer 39、option 0，`swDetailingArrowStyleForFaceAttachment` |
| `arrow.unattached` | 写 `closed` / `none` | Integer 40、option 0，`swDetailingArrowStyleForUnattached` |
| `bent_leader.enabled` | boolean | Toggle 375、option 0，`swDetailingAnnotationUseBentLeaders` |
| `bent_leader.length_mm` | 正有限毫米数 | Double 113、option 0，`swDetailingAnnotationBentLeaderLength`；原生米与公共毫米相互换算 |
| `zero.leading` | `standard` / `show` / `remove` | Integer 265、option 100 (`swDetailingAnnotation`)，`swDetailingLeadingZero` |
| `zero.trailing` | `show` / `remove` / `remove_only_on_zero` / `same_as_source` | Integer 15、option 100，`swDetailingDimTrailingZero` |

每个读回字段为 `{value, native_value}`，枚举保留原始整数；未认识的原生枚举
返回 `value="other"`，不据此开放写入。尾随零的已废弃 enum 0/3 和其他
preference option 使用的 6/7/8 不进入写入域。箭头的可读枚举表比写入域宽，
不能把 enum 存在解释成三种附着场景都已验证可写。

字段映射来自官方 [DP Annotations](https://help.solidworks.com/2024/english/api/swconst/DP_Annotations.htm)，
枚举来自 [ArrowStyle](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swArrowStyle_e.html)、
[LeadingZero](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDetailingLeadingZero_e.html)、
[DimTrailingZero](https://help.solidworks.com/2025/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swDetailingDimTrailingZero_e.html)。
[原生单位约定](https://help.solidworks.com/2024/english/api/sldworksapiprogguide/Overview/Units.htm)为米/弧度。

## 写入和失败契约

只调用目标文档 `IModelDocExtension.Get/SetUserPreferenceInteger/Toggle/Double`，
没有 `ISldWorks` 全局系统偏好 setter。写入继承 document/session/lease/update-stamp
约束，另强制提供 `expected_value`（CLI `--if-value`）比较所选字段的旧值。
已校准的原生 setter 不改变 update stamp，故 stamp 不能代替字段旧值比较。

先读取七字段、文档类型/stamp/dirty/configuration、foreground 和 active sketch 身份。
写入仅限可写文档；零件/装配存在活动草图时不更改字段，工程图只允许下述
已识别的普通sheet上下文；同值请求在状态检查后成功返回
`changed=false`，不调用 setter/SetSaveFlag。单次更改前将
`mutation.attempted` 与 `may_have_changed` 置 true；原生失败不重试、不回滚。
成功后立即完整读回七字段，验证请求值及未请求字段保持，再检查原生上下文。

Windows 2025 校准中 Integer、Double、Toggle（包含设置 false）均返回 True。
False 或非 bool 不视为成功，不用再次调用去“确认”。公开适配器采用此已证实行为，
不从目标值 false 推导 native 调用失败，也不把官方 Toggle 返回值描述的歧义隐去。
另参见 [SetUserPreferenceToggle](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SetUserPreferenceToggle.html)。

校准中 setter 后 dirty 仍为 false；公共适配器成功更改后调用文档 SetSaveFlag，
检查 dirty=true、上下文保持，并再次核对七字段。setter 后首次读回严格保持
post-setter state；标脏后末次读回严格保持 post-write state 和草图身份。
只读回阶段的 dirty/stamp/草图变化失败，不再次 SetSaveFlag 掩盖。
它不会隐式保存或重建，调用者需
显式 `document save` / `save-as`。失败响应保留 mutation 标记，表示打开的文档可能已改变。
长度的数值预检只验证正有限与米换算不下溢，不据两个校准值推定整个原生范围均可写；
每个实际请求仍须单次 native 成功和读回一致，原生不接受的值首失败停止。
毫米长度的预期值/读回比较使用 `rel_tol=1e-12, abs_tol=1e-12`，同值判断也采用这一容差。

## 私有原生校准证据（不是公共 CLI 验收）

2026-11-06 本地 Windows SOLIDWORKS 2025：单次 owned hidden PID 5160，
33.396 秒，同宿主依次新建零件、装配、工程图（真实 `gb_a4.drwdot` 模板）。
每类 14 次原生 setter，每次后读回七字段并检查其他字段未变；零件40×30×10毫米
实体的体积保持12000 mm³。每类另存新原生文件、关闭、只读重开、再次读取七字段，
检查 clean、源 baseline hash 不变。SetSaveFlag 前后 stamp 相同，dirty false→true。
各类字体 ITextFormat 全字段和总体标准只观测且保持；未调用字体/标准 setter。
前后原生进程为空、仅退出自有宿主一次、cleanup=[]。

重要边界：每类只有**最终一次保存重开**。箭头三字段和尾随零最终值不同于初值，
已证明这些改变后的持久化；水平折弯开关、长度、引头零在中间改变并读回后又恢复原值，
所以仅证明中间读回和最终恢复值重开，尚未证明其改变值保存重开。私有脚本同值分支
零 setter 是 harness 控制证据，不冒充公共 CLI 同值证明。三种箭头仅分别调用过
edge→dot、face→closed、unattached→none；白名单中的反向 edge→closed、face→dot、
unattached→closed 仍待公共门禁覆盖，不能把原生初始值当成反向 setter 证明。

- guest 原证据：`C:\Workspace\SWCLI-tests\a18-annotations-20261106-c197`
- Mac 原件：`/private/tmp/a18-annotations-native/evidence-c197`
- `report.json` SHA-256 `5cdf06db6d8d6b6ac6a0b3de8de09e8eb0e492d4630722ed9c2f3fcc2e714b42`
- `trace.jsonl` SHA-256 `03c54a0f6e53345996cd3015c5593cc911e6074c81013d4cf2e4ee63bcdcf8b4`
- 独立审计：`/private/tmp/a18-annotations-native/audit_calibration.py`，`/private/tmp/a18-annotations-native/audit-output.json` 明确 `full_acceptance_eligible=false`
- 保存零件 SHA-256 `f8034ac19ce17355958d0a5493edf1ac3f246da8960507352f32d03b9961140d`
- 保存装配 SHA-256 `45782dfbfc9fadb8919b80556dc8dc38217266be963dd07c71082a02e1bbdf34`
- 保存工程图 SHA-256 `93e0d34cf9aae07fe5c9f45bb2abf19920de5e91e48c3fdcba7d8432df82c036`

## 后续公共门禁（待完成）

同 owned 隐藏宿主，通过已安装的公共 daemon/CLI 对三类样件执行：读七字段、
每字段改为异值、旧值冲突/lease/stamp/readonly 拒绝、后台/session 当前文档保持、
同值零写入；补齐三种箭头白名单反向 setter，且各自改变后保存重开。
**使七字段均为相对初始的改变值再保存、关闭、只读重开**。核 fresh document IDs、
原文件 hash 不变、新文件 hash/size、读回七字段、零件解析几何、clean、宿主/清理。
须有实际公共回执后才标记已验收，不用本私有报告替代，也不额外建立手动 CI 校准。

注释字体需要 ITextFormat 原生对象，且可能联动各注释子类型；总体绘图标准也会
联动子标准。两者本阶段均不开放写入，另行设计和原生验证后再扩展。

## 公共门禁代码已准备（尚未执行原生验收）

独立脚本 `scripts/ci/verify-document-annotations.py` 不读取 COM，不创建/重启 daemon，
不触发 CI。需要已安装 A18 和开启 `SWCLI_TRACE_NATIVE_CALLS=1` 的自有隐藏 daemon，
以及三份明确的准备样件：`annotations.SLDPRT`、`annotations.SLDASM`、`annotations.SLDDRW`。
工程图缺失即失败，不以零件/装配替代；零件须有一个可测量实体。

```powershell
C:\Workspace\SWCLI\.venv\Scripts\python.exe -I C:\Workspace\SWCLI\scripts\ci\verify-document-annotations.py --fixture-dir C:\Workspace\SWCLI-tests\a18-fixtures --output-dir C:\Workspace\SWCLI-tests\a18-public-unique --native-trace C:\Workspace\SWCLI-tests\a18-daemon-stderr.log
```

样件来源可以是 c197 的三份原始 baseline，逐字节复制到独立 fixture 目录并更名，
保留原件和 SHA-256；这只是公共门禁输入，不把私有脚本当成公共回执。
门禁开始前要求空文档目录，固定请求600秒/组1800秒。它执行：

1. 后台、跨 session 且已有写租约时读七字段，精确比较先前文档描述符。
2. lease/stamp/每字段 expected_value 冲突，以及自身写入后的旧值冲突；均核零 native setter。
3. 三类各七字段改为与初值不同的值，检查其他字段保持，另存 `changed-annotations.*`。
4. clean 状态七次同值操作核零 setter/零 SetSaveFlag，然后关闭并用新只读 ID 重开，
   检查七个改变值和 readonly 拒绝，零件 V/S/质心保持。
5. 再次可写重开第一份副本，仅反向修改三箭头，另存 `reverse-annotations.*`，
   再以新只读 ID 重开核反向值及其余四字段保持。
   初始箭头样式若在写白名单外但可识别，只作为 CAS 前值；首次写入和第二份副本
   均选择白名单内的两个不同样式，不尝试写回只读初值，显式记录 `reverse_values`。
6. 核三类原始文件和两份副本 hash/size、同宿主、空文档/cleanup；不保存回原输入。

每个读/写/拒绝的 CLI request_id 与 daemon stderr 的 native-call begin/end/error 关联。
成功改变要求恰好一次 IModelDocExtension setter；同值/拒绝为零；SetSaveFlag最多一次，
同值/拒绝为零。还核 getter 数量：只读/同值/旧值冲突7次，成功改变21次（前读/首次读回/标脏后读回），
lease/stamp/readonly前置拒绝零次，并核三轮读取与单 setter/SetSaveFlag 的实际先后顺序。
缺失、重复或不完整 trace 即失败，
不只依据 mutation 回执声称零写入。
原生调用必须位于唯一的 operation begin/terminal 之间，按单调 sequence
逐一 begin→terminal，并始终来自同一 worker_pid；不能用 Counter 配对替代实际时序。
最终记录 stderr 的已消费前缀长度和 SHA-256，后续正常 daemon 退出追加日志不冒充旧前缀。

便携 FakeCLI 测试验证三类流程、30次实际改变、21次 clean 同值，以及丢持久化、
源文件改动、伪同值 setter、CAS误触setter、读脏状态、缺失/残缺trace、保存size错配、
首失败单次尝试、旧证据不覆盖和最终checkpoint首错保留。
这些便携测试只证明门禁控制代码，不替代真实原生回执。
以下记录首次专项的实际结果；完整三类门禁与 CI 仍待通过，
c197 的有限持久化范围保持前述限制。

## 首次安装版公共专项（整体失败，原证据保留）

精确开发提交 `14e187c709186952d99b11d208c1dff2176337fd` 在独立安装环境、
自有隐藏宿主上执行一次三类公共门禁。零件和装配完成七字段异值保存重开和
三箭头反向保存重开：实际 trace 共20次 setter、4次 SetSaveFlag、14次同值零 setter。
工程图首次实际改变前被 `annotation editing requires no active sketch` 拒绝，
mutation 两标记均 false，没有调用该 setter。整体状态仍为 failed，不据前两类成功
声明三类验收完成，也未原样重跑。

- 原件：`/private/tmp/a18-public-cli-native-14e187c-d84a/evidence`
- 公共回执 SHA-256：`7b68bfb3ff27de7cbaf6eb3a58b44c7ec2810ac4f9b63a3bb6d6714cb4555f44`
- 原生 stderr/prefix SHA-256：`acbdf3225784699dc56ea872dd6d81959919f624a41e7178db48dc2987c15da2`
- 首失败 request_id：`d5330db2-1b4d-42de-8065-37cf5f02cc40`
- 外层耗时154.05秒、daemon正常退出0、cleanup=[]，前后SW进程为空。

此轮运行的是14e187c版本的 verifier。随后修补的 trace 时序校验器在 Mac 上
对原回执的103条调用证明和同一6374033字节原日志离线逐条复核通过；没有重放
任何 CAD 请求，也不声称新 verifier 已在该轮实跑。
`/private/tmp/a18-public-cli-native-14e187c-d84a/strict-trace-audit.json`
明确 overall_gate_success=false、full_acceptance_eligible=false。
首失败后保留原检查并开展绘图上下文诊断，见下节。

### 绘图上下文诊断与针对性修复

一次独立只读诊断 `e76f` 在新建GBdrawing、原baseline只读重开两类样件的
active/background四组上下文中确认：`GetEditSheet=true`，`ActiveDrawingView=NULL`，
`ActiveSketch` 与 `GetActiveSketch2`、首个sheet pseudo-view的`GetSketch`原生身份一致，
与`ISheet.GetTemplateSketch`身份不同，首view的引用模型名为空。68次读取/身份比较
前后均保持文档状态、sheet、foreground和selection；没有注释偏好setter或编辑模式调用。
自有宿主正常退出，cleanup=[]，前后SW进程为空，原baseline hash不变。

- 原件：`/private/tmp/a18-drawing-context-e76f/evidence`
- report SHA-256：`a3b99b8d729c2f74dac9b272bdee022146c9b32f33d0a84c0b6a74727aa16921`
- trace SHA-256：`96a8756d72a216b69163a26b02de21c23a6f1c7d82e50b1f0b1b73dd646fb93c`

官方[GetFirstView](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~GetFirstView.html)
说明首view代表图纸自身；[ActiveDrawingView](https://help.solidworks.com/2017/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDrawingDoc~ActiveDrawingView.html)
在图纸激活时为空，[GetEditSheet](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDrawingDoc~GetEditSheet.html)
区分sheet和format编辑模式。

修复后不简单跳过工程图检查：可变更profile必须是sheet模式、没有活动模型view，
current sheet/首view/pseudoSketch/ActiveSketch均非空、名字非空、引用模型名为空，
ActiveSketch与pseudoSketch相同且不是templateSketch。只读不按可变更profile拒绝，
但所有读/写阶段均保存并核对sheet/view/sketch/template身份、mode、名称和引用模型名。
format/view/foreign sketch等不支持上下文在setter前失败；不调用EditSheet来修复上下文。
便携回归验证正常图纸读/写/同值、不支持或不完整上下文零写入、只读保持format模式，
以及三轮偏好读取发生mode/view/name/refmodel漂移时失败且不二次标脏。
该诊断不是写入证明，修复后的三类公共专项仍须独立通过。

## 交付边界

A18 完成后暂停，不自动推进下一版本。main/MCP 的最终合并由另一位
agent 负责，本候选不执行该合并；DockerSW 的跟进也不在本轮范围内。

## 修正后本地安装版公共专项

精确开发提交 `a3d70b18bb98e426442744ce40841a65d281e094`，
实际daemon/CLI均为`0.1.0a18.dev0`，在独立安装环境中执行一次完整三类门禁。
SLDPRT、SLDASM、SLDDRW均success，七字段异值与三箭头反向的两份副本均保存只读重开。
147条request_id原生证明包含30次偏好setter、6次SetSaveFlag，21次clean同值请求为零setter；
lease/stamp/字段旧值/readonly拒绝、fresh IDs、原件和副本hash、零件V/S/质心、后台上下文、
同一owned hidden宿主5992及清理均有原始回执。业务门禁168.845秒，外层196.49秒，
daemon正常退出0，cleanup=[]，前后SW进程为空。

- 原件：`/private/tmp/a18-public-cli-native-a3d70b1-g52c/evidence`
- public receipt SHA-256：`158afe7cecaa4e5e66898561bdb892c3e14587d31002d4a44b43578c39ef4efa`
- outer proof SHA-256：`8b40289c61d10803977631f7e18a3669c7713425bb2544bfa990f87815814da6`
- native trace/prefix SHA-256：`652c7e1d3894549f9249792514faa950ed97be7868464d510f486ed38f2122a2`

独立format-mode负例使用另一自有隐藏宿主8152：新建GBdrawing后只调用一次
EditTemplate（void返回不当作bool），通过GetEditSheet=false确认format模式。
受保护adapter的异值请求以明确上下文错误拒绝，before七字段齐全，mutation两flag false；
偏好setter和SetSaveFlag均0，读回和mode保持，未调用EditSheet切回或Save，关闭自建文档。
该报告保持`full_acceptance_eligible=false`，不冒充公共CLI或完整CI验收。

- 原件：`/private/tmp/a18-format-negative-a3d70b1-h28e/evidence`
- report SHA-256：`6f26f86b158043746a7e79d91b4d2956e3c4c1bc09a5aefc2a1668b305ddc85b`
- native trace SHA-256：`f3687f9c8a82ede0c2c9341c1325b8dcddf7f585a4151790ebce482d43396070`

精确`0.1.0a18`冻结仅版本字串与本文/发布说明变化，核心适配器保持a3d70b1字节。
最终完整Windows CI及其原始安装包仍待验，不以开发版专项替代。

## 首次最终CI的模板枚举差异

[42120377076](https://github.com/YJBeetle/SWCLI/actions/runs/42120377076)
在精确版本`46de584 / 0.1.0a18`的注释门禁中失败：part与assembly各自完成两轮
保存重开，工程图默认edge/unattached为可读的`open`（原生0），face为dot，
引线长6.25毫米。原门禁把“初始值可写”误当作开始条件，因此在drawing的首次setter
之前拒绝，writes=[]。两组成功不等于整条通过，后续完整19/20矩阵未执行。

原native artifact `13460246191`，ZIP SHA-256
`9e46ae3b06543ae4c06d2d48eb2a9edd6b4d4d518049f730e129bffc86001ea3`，
回执SHA-256 `d931e2fed68c27890eb5d56a6391ef13b01e66091cca13e6adbe8b45f5103b43`。
原件与日志保留`/private/tmp/a18-failure-42120377076`，cleanup=[]；99条原生证明
包含前两类的20次setter/4次SetSaveFlag，drawing没有annotation-option-set请求。

修复只调整门禁选值，不改产品或写白名单、不规范化模板：可识别枚举可以作为
`--if-value`前值；两轮目标仍限定writable中的不同值。已知但不可写的open不会作为
目标，包括readonly拒绝探针也使用可写目标，避免请求先被schema拒绝而未测到readonly。
未知`other`初值仍在首次setter前失败。实际hosted open→白名单两态的完整证明
仍待修正版最终CI，原失败不重跑、不伪装成功。

## 第二次最终CI的无格式图纸上下文

[42125076559](https://github.com/YJBeetle/SWCLI/actions/runs/42125076559)
已越过初值门禁。part/assembly完成，drawing的open→closed请求在setter前被
`_writable_context`拒绝，mutation两flag false，7次偏好getter、0setter/0标脏。
后续完整矩阵仍未执行，整体failed。原native artifact `13462389224`，ZIP SHA-256
`7ffd5dab343bf5f431528db13fbedfc973d4857c9ecc0e69c82d1f545632231c`。
原件保留`/private/tmp/a18-failure-42125076559`。

对该CI原始24519字节SLDDRW（SHA-256
`1048ec31d968763a4e07abeb1a47af57d16c9f980140fa28a7eed6b5335a15be`）
执行一次只读VM对照探针，与旧GB baseline分别active/background比较。
CI图纸format_path=`*.drt`且无可用图纸格式；唯一不满足旧profile的条件是
`template_sketch_nonnull`。active/GetActiveSketch2/pseudo sketch仍全部非空且身份相同，
mode=true、active view为空、引用模型名为空，sheet/view名字均非空。
84次原始观测前后状态、图纸、foreground、selection保持；源/副本hash不变，
0偏好setter/0编辑模式调用/0Save，自有SW8800正常退出，cleanup=[]，前后SW进程为空。
诊断结束后不再使用VM，避免与另一agent并用冲突。

- 原件：`/private/tmp/a18-ci-context-42125076559-j73d/evidence`
- report SHA-256：`62434aa6a5c2138fe777bc73e7e0311cd0054579f31b7c75a10944020c7ad60b`
- trace SHA-256：`bc37d97c2e8db3c985432517a00adbd3bcce98638565b87a659d7cf91918944e`
- 独立审计 SHA-256：`3964901c11d7e516eaae6207b5564e8bddd941b8aec0c2cd3a1a02b7bc07e4cd`

最小修复只移除template sketch必须存在的要求，保留其前后身份/空值稳定检查。
普通sheet不依赖图纸格式存在，仍须模式true、无active model view、非空且匹配的
active/pseudo sketch、无引用模型及完整稳定上下文。format缺失不能绕过mode/view/
foreign sketch保护；五类负例零写，known open前值CAS和同值不写回归已过。
此只读诊断不替代实际写入和两轮保存重开，仍待修正后完整CI。
