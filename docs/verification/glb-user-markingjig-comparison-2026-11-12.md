# 用户真实Blender成功原件与下一步取舍

用户确认曾在Blender使用的真实原件现已对应到MarkingJig。以下只保存hash、统计与生成线索；GLB/SLDASM业务二进制留在原目录，没有复制进SWCLI、修改、重新导出或启动CAD/Blender。本路只读重算SHA、严格解码并核Git LFS对象指针；未运行该业务仓的git status、LFS修复或认证修改。

| 原件 | 大小 | SHA256 |
| --- | --- | --- |
| `/Volumes/Data/Workspace/Inclinometer/COT/ASM/Casing/MarkingJig/MarkingJig.REND.GLB` | 1858504B | `375b01a84bd4ca1f9100f9caea44782fb84f228a82a9becd0236186a3315cb6c` |
| 同目录 `MarkingJig.REND.SLDASM` | 924679B | `80bfa9d4bc453277dc0ba4dd9dbdf8f0d315a090aa3bab429843b1f9bc308530` |

实际GLB为JSON21756/BIN1836720，当前严格inspect_glb可解码6mesh/8primitives、42432三角形、55314 positions及55314 normals；8materials、1camera，无texture/extensions/Draco。该文件具有实际网格，用户确认的Blender成功不再仅是未对应文件的线索。[结构化元数据](../evidence/glb-user-markingjig-comparison-2026-11-12.json)关联统筹audit SHA `bd956b075f823a908042b73fa84a16581bb214204767ec54a61e73dba7d26811`。

两个原件与子仓HEAD `2f83058dbced4c1dd38fb21600864de17a67ca77` 的LFS oid/size一致。GLB生成提交message为 `CI 导出加工文件 (9af435e4) [skip ci]`；SLDASM及CI配置与输入 `9af435e46181fe46fbe92abc4264545a103c54b6` 相同。附近 `CI/ModelForRendering.txt` 明确列出MarkingJig.REND.SLDASM；`.gitlab-ci.yml`配置镜像tag `ghcr.io/yjbeetle/sw-executable:2025-zh-cn-cli`，配置流为document open（无readonly flag）→临时输出document export --strict。

用户随后直接确认：这份成功GLB目前使用 **DockerSW latest** 导出，这是实际使用环境标签的用户观察，应与上述静态2025-zh-cn-cli配置分开保留。latest可移动，不能用现在解析出的标签补作当时digest；本轮不解析/拉取镜像或操作容器。实际job/生成时image digest、SWCLI版本、保存API与参数、SW/Wine版本和导出时host flags仍未知。在已查看的顶层/CI目录没有取得实际运行receipt；不能把配置tag或SOLIDWORKSGLTF标签当已执行环境的证明，也不据此归因Docker/Wine、版本或可见状态。

| 对照 | 已知差异与限制 |
| --- | --- |
| 用户MarkingJig真实成功 | 已有SLDASM装配源及渲染配置，6mesh/8primitives；用户确认DockerSW latest，精确digest/API/SWCLI/SW/Wine及RO/加载状态未证实 |
| 历史box assembly成功 | type2，单组件盒子，BIN720/12tris；save-as/in-place save后、首次close/reopen前导出，旧三参API源码线索 |
| 历史/现代part失败 | type1盒子；旧/现代CI为RO reopen，近期现代局部为新建保存后可写；现有BIN0事实成立，不能泛化所有GLB一直失败 |
| 当前typed part实际对照 | 267a34c身份/状态/清理通过，C#单次True/0/0仍为空BIN；与hidden Python baseline字节相同，未证明底层原因 |

## 简短条件方案：不实施、不执行

若typed part得到有效BIN，无需为这条假设追加assembly对照；若仍停在身份/取证/COM首错，先保留首错，不能跳过门禁转assembly。**只有统筹得到typed part实际BIN0原件后仍需要区分文档/源上下文时**，才考虑一次现代assembly对照，优先使用这份用户已确认成功的现有MarkingJig源及其现有完整引用，不先新建/重建CAD，也不排一串模型或参数试验。旧generated.SLDASM保留作已核辅助证据，不替代真实成功模型作为重点。

届时固定源/引用hash、完整加载/无缺失引用与原strict状态、保存前后原件不变；沿用刚试过的绑定和现代七参/暂存规则，唯一一次输出到另选诊断位置，保留完整BIN/accessor/mesh与首次错误。现helper是type1专用，未来type2夹具及生命周期必须由统筹明确亲审，不能直接放宽通用doctype/readonly/源状态门禁。统筹最新方案改为[独立只读工作副本及OpenDoc7候选](glb-markingjig-readonly-control-plan-2026-11-12.md)，允许其亲审后只读复制必要源/引用到私有C:\Workspace；本路不复制VM，业务二进制不入仓/CI，原项目和既有GLB始终不动。完整引用仍未知，不能猜齐或fallback box。

新增变量至少包括type2、真实复杂源与渲染/装配上下文、已有文件打开/解析引用/轻化状态及重开生命周期，不能称只改doctype。若成功，只能说明该现代路径/环境可导出这一assembly，排除“当前环境所有现代GLB都必定BIN0”的泛化；不能单独证明doctype、某个参数、Docker/版本或C#封送是part失败首因。若同样BIN0，只能证明当前这组条件也失败，不能否定旧GLB及用户Blender成功；还需区分加载/状态/版本/API/实际依赖等尚未知条件，不能直接定性导出器缺陷。加载/原件状态失败则在0保存停止，不接第二次调用或其他API。

另行取得的[当前本地Docker缓存版本与API来源](glb-current-docker-cache-2026-11-12.md)只代表当前cache：latest源码0.1.0a2、2025源码0.1.0a13，均旧三参SaveAs3。没有把这些缓存与历史MarkingJig job关联，以上历史unknown保持，不因当前cache回填版本/digest或判定原因。
