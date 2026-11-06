# 有界旋转凸台工作交接

当前：**merge-ready=true**。产品代码冻结于3922bee798b0b5b33dc6aa7a4bf34b01dc0e79ad；最终run42273047248 success，原始artifact13533039600、ZIP digest/head及内部85项/公开84项审计和两组trace全部通过。后续tip只追加证据docs，无产品代码改变；无待授权动作。

## Scope / 实现
- 唯一worktree：/Users/YJBeetle/.codex/worktrees/swcli-revolve-feature/SWCLI；分支codex/swcli-revolve-feature；基线3bda2c00489dde6a3d1e4521c548f751b1d1c197。
- 仅原生Windows / SOLIDWORKS revision 33.5.0；Wine、其他版本或未知平台继续RevolveNotCalibrated。
- 空零件、单配置、已注册未吸收2D中心矩形、三标准原点平面；截面[0,min_y,radius,max_y]，明确左边轴[0,min_y,0,max_y]，显式360度。无任意曲线/切除/薄壁/部分角/多实体/已有实体合并。
- 保持CLI→daemon→COM worker，CLI/protocol/生成SDK/MCP共用契约。document/stamp必填、lease保护、完整轮廓CAS、只读/配置/选择保护、后台临时激活恢复。
- 原生创建尝试前设置partial mutation；首错误与返回句柄保留，注册/释放错误单独记录；几何实体作用域退休；不重试或自动CAD回滚。
- feature.list/inspect既有契约仍只观察拉伸；旋转创建结果返回原生定义/轴/角度/exact feature_id，保存重开通过原生特征树、吸收轮廓和质量属性验证。

## 文件/接口
- 新增src/swcli/revolve_geometry.py、hosts/windows_revolves.py；修改daemon/operations.py、operation_schemas.py、result_schemas.py、cli.py、SDK生成文件、使用说明。
- 新增内部verify-revolve-calibration.py、公开verify-revolve-public.py与针对性/消费端类型测试。
- CI仅本分支明确手动targeted输入，默认false；internal/public/full互斥，保留PR秘密隔离、原有完整/发布门禁。
- targeted独立concurrency：swcli-revolve-calibration-${github.ref} / swcli-revolve-public-${github.ref}，cancel-in-progress=false。默认full/release仍swcli-hosted-windows-solidworks；不取消他人run、不因排队重复dispatch。

## 便携验证
- 首提交：1834项全套通过、26项平台跳过；15项旋转针对性及8项SDK类型负例通过。
- 公开开门提交预检：1841项全套通过、26项平台跳过；23项旋转针对性通过（含其后新增的一项未知平面拒绝测试）；生成SDK严格类型及10项消费端拒绝通过；YAML/并发接线、py_compile、diff --check通过。
- 持久日志：evidence/revolve/*.log；本地Python3.15隔离venv执行，临时环境不作主证据。未使用本地VM。

## 内部原生证据（已核验）
- commit/head 32812cb0cf296918def0a9e34cb5a89335abdd3a（feat: 新增有界旋转凸台候选与独立原生校准），已push。
- Run https://github.com/YJBeetle/SWCLI/actions/runs/42262911836，attempt1，success。
- 参数ci.yml / ref codex/swcli-revolve-feature / native_revolve_calibration=true / native_full=false，其余既有默认。
- 官方TLB实读：swEndCondBlind=0、swThinWallOneDirection=0、swRevolveTypeOneDirection=0、swSelSKETCHSEGS=10；20参数FeatureRevolve2签名与定义成员核对通过。
- swconst.tlb SHA256 95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6；sldworks.tlb 585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159。
- Windows artifact13526809695，原始ZIP SHA256 69aca5b8480ed3f14547ba36e85a23730b042068c32854b6e87541fa1eeb3ac1；run/artifact/report head一致，独立72项内容检查通过。
- front/top/right三原生Revolution：2π、精确轴、boss/nonthin/merge/one-direction、单圆柱体积/表面积/质心全部符合；保存后实际文件字节哈希与只读重开定义/轮廓/质量属性/干净状态一致。
- front.SLDPRT SHA256 d6a6c91eb55ef77c74615e9954e6857224178ab974c6605f834809bcdc9523f6；top e3f6076063e46a8a9edf5ebdd4998bb685b0373a3a262215be0dd28939275c75；right f32999f56a9ac9bce5c8900a1c3eaf461ca2ec8187a8f67f0629eee4419583b8。
- 轴穿越实际轮廓、非矩形、多实体在原生创建前拒绝且状态不变。单宿主、无重试/组内重启；100操作边界/1270原生trace边界全部闭合，整组22.877秒，600/1800未放宽。
- 原始ZIP/metadata/independent-review.json/extracted实际模型保存在evidence/revolve/ci/42262911836/；trace-review.json位于其run证据目录。
- distribution artifact13526180904 digest3ac6ee654d2d2ce23b4ec809bb8f0e0b6878bc77ae5cfd2791a6d67ef687f794；wheel核心5模块字节与git head完全一致。package/portable3.9/3.14原始ZIP及digest也均已独立核。

## 公开验收 / 未完成边界
- 脚本只用公开CLI及现有daemon生命周期；独立单宿主、600秒请求/1800秒组，无组内重启/重试。
- 计划三平面成功、lease/stamp/foreign sketch/完整值CAS拒绝、只读拒绝、轴穿越/非矩形/多实体拒绝、实际输出字节hash、只读重开特征树/吸收轮廓/质量属性/健康状态。
- 待本次中文提交与push后，仅dispatch对应head一次：native_revolve_public=true、native_revolve_calibration=false、native_full=false。
- 尚未形成公开原生通过证据，不能合入或宣布完成。通过后核原ZIP/head/digest/trace/save-reopen并给统筹精确可合commit；本对话不合main/改版本/发版，不修改DockerSW/MacSW/指针。

## 公开验收已触发
- commit/head 3dd23c842e63857da13afa3fb6ec18640cd3b735（feat: 开放实证旋转范围并接入公开链路验收），已push。
- Run https://github.com/YJBeetle/SWCLI/actions/runs/42269057556，已核精确head。
- 参数：native_revolve_public=true、native_revolve_calibration=false、native_full=false，其余既有默认；这是公开阶段唯一dispatch，不是重跑内部校准。
- 持久记录：evidence/revolve/ci/42269057556/dispatch.json；等待原始ZIP/trace/输出内容核验。merge-ready=false。

## 公开run执行期间发现并修复的便携失败边界
- 失效元数据测试首次失败已保留：evidence/revolve/metadata-first-failure.log。
- 创建返回句柄但Name不可读时，原实现可能返回ok=true后被结果schema整体拒绝；意外非Revolution类型在失败结果中也会被过严的type常量拒绝，导致丢partial证据。
- 已在工作树修复：不可读名称/类型立即报告RevolveFeatureMetadataUnavailable并保留句柄/partial；失败响应允许保留实际特征type，成功响应仍严格const Revolution且所有几何断言未放宽。24项针对性测试通过。
- 修复已在29bd9e33ad15bb02dc651c74bd2de123d4c3cc1a提交并push；当前3dd23c8公开run继续执行，不取消、不重放CAD调用。其结果将按原head独立保留；最终代码修复后需对应head公开验收。
- 同类定义读回无值(None)的8个边界也复现响应schema覆盖原始partial错误，首失败日志readback-first-failure.log已保留。失败分支允许这些无值读回作为证据，成功分支仍要求原生角度number、精确类型/轴/方向/凸台等常量及严格解析几何，不放宽任何成功断言；25项针对性测试通过。
- 最终公开标记也已移到自有宿主成功停止/清理/证据checkpoint检查之后；关闭失败不能标记public_acceptance=true，且首错误与二次关闭错误分开保留。对应行为测试通过。
- 修复预检完成：全套1845项通过、26项平台跳过；26项旋转针对性通过；SDK生成/严格类型/10项消费端拒绝通过；diff --check通过。
- 当前3dd23c8原公开run仍继续执行，不能视作最终修复代码的验收。下一次dispatch是已复现缺陷修复后的新head必要验收，不是排队重试或同head重复触发。

## 最终原生partial控制准备
- 在既有内部校准脚本新增明确标记的 injected-postcreation-observation-failure：对真实创建返回的原生对象注入一次后续观察失败，核首错误/partial/精确句柄，立即独立测量保留模型并保存重开。
- 不把该注入当作真实CAD内核故障。内部控制与公开CLI分别目录、分别自有宿主及600/1800预算，组内不重启；无公共调试开关或直接COM公共旁路。
- 最终public targeted job会先运行此独立内部控制组，再运行公开CLI组；默认full/release仍不运行它。现有3dd23c8 run不改动、不取消。
- 26项针对性、Python/YAML解析及接线检查通过；准备将此控制与失效读回修复作为最终head的必要验收，等现有公开结果确认后仅dispatch最终head一次。

## 首个公开原始证据核验完成 / 最终run执行中
- 首公开run42269057556，head3dd23c842e63857da13afa3fb6ec18640cd3b735，success；原始artifact13530365438，ZIP SHA256 0a35f8a224076c6b1ee7784ca8463bef77fe37e92760925d2fcc44911da562ef。
- 独立public review成功：run/artifact/report head一致、实际SLDPRT hash、三平面解析几何/原生特征/吸收轮廓/只读重开/lease-stamp-CAS-foreign/只读与非法范围拒绝、单宿主/完整关闭、trace闭合及恰好3次FeatureRevolve2创建无重试均通过。记录在evidence/revolve/ci/42269057556/independent-review.json。
- 但它不是最终修复代码验收：29bd9e33ad15bb02dc651c74bd2de123d4c3cc1a修复失效读回partial契约；3922bee798b0b5b33dc6aa7a4bf34b01dc0e79ad加入真实模型内部partial故障控制，均已push。
- 最终run https://github.com/YJBeetle/SWCLI/actions/runs/42273047248，head3922bee798b0b5b33dc6aa7a4bf34b01dc0e79ad，已核对应。
- 输入native_revolve_public=true / native_revolve_calibration=false / native_full=false；最终head仅此一次必要dispatch，不取消/重复其他run。
- 最新授权已沿用；无等待审批或授权的动作。继续等待最终原生及原始ZIP/head/digest/trace/partial保存重开核验；通过后给主对话精确可合commit，自己不合main/发版。

## 统筹独立预审（最终原件待齐）
- 统筹已提前独立审查3922bee最终head，26项关联便携检查通过，Windows/revision边界、单次FeatureRevolve2、partial handle和失败控制未见代码阻断。
- 仍仅等待42273047248最终原件审计；不沿用旧3dd23c8成功作最终代码验收。结果齐后提供精确tip/run/artifact/hash与原报告给统筹优先集成，自己不合main。

## 最终可交付 / 立即供统筹集成
- 产品验收head：3922bee798b0b5b33dc6aa7a4bf34b01dc0e79ad；最终run https://github.com/YJBeetle/SWCLI/actions/runs/42273047248，success。
- Windows artifact13533039600，原始ZIP SHA256 13c3a4695603e33875acb9a64c639baec056c48bdb7416b75b65664b89a29365。run/artifact/两份原报告source_commit一致。
- 内部85项、公开84项独立原件检查通过；内部trace120/1510边界、22.684秒、单宿主/4次单次创建/唯一明确注入观察错误，公开34228边界/同worker与宿主/3次单次创建全部闭合，无重试或组内重启。
- 真实partial模型保留首RuntimeError、三个mutation标记true、精确对象、立即测量和保存只读重开；partial文件hash707d7b14060610bf5543dee31adfca1fa794683df802e9f33f8e75984c57cb1f。明确是观察故障注入，不宣称真实CAD内核故障覆盖。
- 三公开文件实际字节SHA：front 3f23304871651a33a8ece12a0b75bba6d7efb2340e30d244fd97059bb6577461；top 81c0498c0e3480a7b53106d91718b7d72bd1095e59e4b60149f707c4ae281e4a；right a3cc51bf22d2512af0a3980a6ae173f1c57aad4c726708ddcdd2d09f85824763。
- 七个wheel核心/SDK模块与产品head字节一致；dist digest a30cf934daa222c7112b4e0207628f3569724ffb4398c29a56432cca39384723。
- 详尽审计摘要：evidence/revolve/ci/42273047248/final-audit-summary.json；两份审计internal-control-review.json/independent-review.json；原件original.zip与artifact-metadata.json。
- 原报告：evidence/revolve/ci/42273047248/extracted/swcli-native-smoke/revolve-partial-control/report.json；同目录revolve-public/revolve-public.json与runtime-sets.json；相应trace/实际SLDPRT均已安全提取。
- 仓库证据文档：docs/verification/revolve-2026-11-07.md。按统筹要求仅追加证据docs提交；可合tip由其后git rev-parse HEAD给出，产品代码与已验收3922bee完全一致。
- 无其他未完成的本路实现/验收步骤；main集成/冲突协调由统筹办理，不自行merge或release。既有feature.list/inspect仍仅拉伸，部分角/任意曲线/切除/薄壁/已有实体合并及未验证平台/版本继续不支持。
