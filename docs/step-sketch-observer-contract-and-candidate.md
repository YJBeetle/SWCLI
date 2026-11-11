# STEP 导出合同与显式草图读回候选

结论：**公共产品合同没有承诺 STEP 回读必须是 IReferenceCurve**。reference-curves 是 b363751 为替换不完整草图观察而新增的 test-only 选择。该选择的实际诊断仍失败，不能把 459ff87 的 12段/320mm 改判通过。本轮另备默认关闭、预先固定 AsSketches=官方0 的读回候选，需统筹亲审后安排新的完整八文件公开验收。

## 合同与历史依据

`src/swcli/operation_schemas.py` 的 document.export 仅公开 output、step_protocol、step_geometry 等导出参数；协议为 AP203/AP214，几何为 solid-surface/wireframe/wireframe-sketches。`windows_step_export.py` 将它们映射到 swStepAP/swStepExportPreference 与 swAcisOutputAs3DCurves 等导出枚举。没有导入表示参数，也没有对导入后的原生 feature class 作承诺。docs/step-export-options.md 把 General 导入参数明确限定为观察器设置，生产导出不修改导入选项。

[2025 STEP 导出帮助](https://help.solidworks.com/2025/english/SolidWorks/sldworks/HIDD_EXPORT_OPTIONS_STEP.htm)定义的是实体/曲面或线框几何，以及是否包括草图实体；这是文件内容的选择，不是导入后 feature interface 的保证。已只读解包安装的2025中文 sldworks.chm（SHA256及成员hash见[研究记录](evidence/step-observer-representation-contract.json)）。其中还说明 STEP 中草图分组不能直接保持，回读会重新组织直线/样条及圆锥曲线的草图；不能据此要求固定单个或两个草图分组。

| 历史点 | 已核原件/源码 | 不能推导的内容 |
| --- | --- | --- |
| 193ab6c，内部42278790303 | 原保留审计记录六组合通过；当时reader只测ProfileFeature/3DProfileFeature | 不证明后续head或更强错误检查已通过 |
| ee7f0ea，公开42303929271 | 本轮重核ZIP SHA4623ccc9...、原report member与提取件逐字节相同；8/8；五个wire case导入/保存后重开均12或18段 | 原报告无feature分组/类型清单和feature error code，不能补写具体草图种类或错误码0 |
| d6505f7，公开42365535291 | 本轮重核原ZIP SHAb2e70c07...及末case原report；第5项AP214 wire仅9段/260mm；完整top/sub图没有遗漏嵌套草图 | 没有保存实际草图错误码，不能断定求解器或导入器根因 |
| b363751 | git diff仅reader、便携测试、docs/handoff；新增As3DCurves选项、IReferenceCurve边读法及强制reference表示；无生产导出/公共schema改动 | 新表示尚未原生证明成功，不是产品新需求或已证根因修复 |
| 459ff87 | [独立原件审计](step-explicit-459ff87-audit.md)：part/errors0，两个3D草图12/320，严格reference失败 | 无保存/重开/草图错误码，不能替代新的八文件验收 |

b363751 的当时说明明确以 GetSketchSegments 对错误草图可能返回不完整数组为动机，改用参考曲线/边长观察。此前 d6505f7 的完整特征遍历已经反驳“只是漏扫子草图”。因此它是观察器实现路线的改动，而不是在产品合同里发现了“必须参考曲线”的要求。该动机合理地提出了诊断假设，但未建立实际故障根因；本轮不把它追认成已证修复。

## 三维曲线与三维草图分别有什么依据

[2025 General API 参数表](https://help.solidworks.com/2025/english/api/swconst/FileOpenOptionsGeneral.htm)的安装原件把关闭3D Interconnect后的 free-curve 导入关联到 swImportFreeCurves 和 swImportCurvePreference；AsSketches 与 As3dCurves 是不同选项。已核本机类型库和此前原生报告均为0/1；候选还会按精确枚举名/owner读取，并要求实际0/1，绝不猜ID。2026在线 General UI对两条路径的说明仅作补充，不代替2025安装文档。

[GetTypeName2接口表](https://help.solidworks.com/2022/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~GetTypeName2.html)及已解包2025 API原件分别映射：ProfileFeature/3DProfileFeature→ISketch；RefCurve、ImportedCurve、3DSplineCurve、CompositeCurve→IReferenceCurve或其对应FeatureData。因此“几何处于三维”不等于“原生参考曲线特征”。459的类型和GetSketchSegments证据支持ISketch表示，不支持IReferenceCurve；读回偏好1也不能推翻实际类型。

[GetSketchSegments说明](https://help.solidworks.com/2016/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISketch~GetSketchSegments.html)警告错误草图的数组可能不全。[GetErrorCode2](https://help.solidworks.com/2018/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~GetErrorCode2.html)提供特征错误码和out BOOL警告标记，标记仅在code非0时有意义；其2025安装原件和现有windows_documents.py的真实BYREF BOOL调用形态也已核。这个API覆盖许多What's Wrong错误，文档没有宣称它枚举全部潜在内部错误，所以仍同时要求精确段数/向量，不能只看code0。

## 源码候选与严格范围

候选入口是既有 reader 新增的 `--sketch-readback-candidate`，默认关闭，必须同时给 `--export-report`；内部六组合校准路径拒绝该模式。CI接线仅在既有 native_step_public_targeted 读回步骤显式添加该flag，既有输入仍默认false；内部/原件诊断和默认reference路径不变。主要逻辑在 `gate_support/step_sketch_readback_candidate.py`，原 `read_wireframe(...reference-curves)` 断言本体和默认调用路线不变。

- 只接受 native Windows、隐藏owned宿主和rev33.5.0；沿用原owned获取/退出及600秒调用、1800秒整组监督。无宿主替换、重试、自动fallback或回放459。
- writer必须成功且cleanup[]，source_commit精确等于当前GITHUB_SHA，并提供顺序固定的6 CLI+SDK AP214 solid+MCP AP203 wire共8个唯一输出和hash。旧head、诊断报告、7/8或重复路径拒绝；不是把旧ZIP改名作为新验收。
- 每个case完整读取六Toggle+两Integer，typed snapshot/CAS。预先固定General三布尔(False/True/True)和AsSketches0，其余四值保留原值；每次setter前完整CAS，写后完整读回，实际LoadFile4前再核完整向量。只反序恢复owned attempted字段，恢复前保护第三值；恢复错误与首错分开，任何恢复失败都清除case成功。
- 保留公开reader现有LoadFile4小写r、同factory对象与原调用方式，不把459的显式绑定/null实验混入本候选。实际返回模型立即交原owned清理；要求精确int错误码0和part类型，不得因459曾成功而跳过新导入。
- wire读回只接受已选ISketch的两个官方feature type；元数据/基准/灯光等有明确、有限白名单。参考曲线、混合或未知类型一律拒绝，不临时切换reader。完整top/sub遍历、按native ID去重；循环或上限拒绝。
- 每个草图先显式读取一次GetErrorCode2(BYREF BOOL)，只有精确int0才读线段；非零警告也失败，未知/调用异常失败。空草图拒绝。保留feature health和所有已观测的partial，再严格核12段/320mm或18段/560mm，完整排序长度向量与原1e-9mm逐段阈值；无缺段、NaN或放宽总长。该检查限定生成箱体与六线源草图fixture，不能宣称任意CAD几何等价。
- 沿用同一个原生保存、关闭、只读重开和第二次独立测量流程。要求保存实际save_errors=0；原标量SaveAs3没有warning输出，保留None而不伪造0。重开必须errors/warnings0、read_only=true、document.modified=false，重新核草图错误码与完整向量；对比两次几何、native/STEP字节hash和GetSaveFlag。实体case保留解析体积/面积/质心与原阈值。
- public writer的源文件hash、前后台状态、lease/CAS、负例、生产导出偏好恢复与两个owned宿主的清理要求全部保留。新reader不修改生产STEP保护、公开schema或writer。

显式feature错误读取是外层API操作，普通动态解析在底层是否有元数据/零参数探测未记录，不把外层次数伪装成native边界计数。未知API形态仍失败，不现场换绑定/参数或忽略错误。

## 验证与最小后续

**163项相关STEP便携测试通过**，其中24项新候选测试；日志 `step-evidence/step-sketch-all-step.log`（7.916秒）。新覆盖0/1枚举与完整八值CAS、部分setter失败恢复/外部第三值保护、首错独立、恢复失败禁止成功、精确12/18、真实9/260与缺对角线拒绝、错误/警告/未知feature code、空/嵌套/混合/未知特征、保存及只读重开错误、重开后长度/health/hash变化、同head精确8报告、非native拒绝和父进程单flag/监督。原139项也通过，包括原reference严格拒绝及旧候选保护。

统筹已亲审并接受这项**验收观察器边界修正**，本轮按指示完成最小CI接线并本地验证。待统筹亲审接线提交、核对队列并授权单次新公共CI后，才可产出该精确新head的完整8文件writer+reader原件；首失败保存ZIP并停止，没有实质修复不重跑。即使未来该验收通过，也只证明明确的sketch读回合同，**不宣称As3DCurves已修好，不覆盖b363或459失败，不复用旧成功放行当前head**。

本轮只有离线审计、只读研究、源码和便携测试；没有VM/CAD/CI/push，未启动原生八文件验收。官方LoadFile4条件文档的既有矛盾、原hosted None/errors1与本机环境差异仍保留为独立未解释事项。

接线验证：既有公开读回步骤仅新增一行 `--sketch-readback-candidate`。去掉该行后整个ci.yml与b55逐字节一致，重复键拒绝的YAML解析结果也相同；9个既有输入、默认false、guard、时限和并发保护均未变化。4项接线测试含13,824种选择组合通过，全部相关STEP **164项通过**（7.549秒）。actionlint1.7.12、PyYAML6.0.3、Python编译、CLI help和diff检查通过；PowerShell续行参数结构由本地测试核验，未执行原生PowerShell/CAD或CI。日志与机器检查保留在 `step-evidence/step-sketch-ci-*`。本提交仍须统筹亲审与队列调度，尚无该新head的原生验收结果。
