# 有界旋转凸台工作交接

当前：内部原生校准与独立原始证据核验通过。公共范围已按实证开放，公开CLI/daemon验收run 42269057556执行中；merge-ready=false。

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
