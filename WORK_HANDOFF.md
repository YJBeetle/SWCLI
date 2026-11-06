# 稳定实体引用与拓扑变化检测

## 阶段 1：范围与共享接口（2026-11-07）
- 分支：`codex/swcli-topology-references`；建立基线与当前 HEAD：`3bda2c00489dde6a3d1e4521c548f751b1d1c197`，初始 worktree 干净，无 `.codegraph/`、无仓库 AGENTS.md（遵循父目录 CodeGraph 条款）。
- 仅本 worktree；不修改 DockerSW、MacSW、main、版本或发布，不使用本地 VM。
- 计划新增只读 `entity.reference-create` / `entity.reference-resolve`，CLI `entity reference-create` / `entity reference-resolve`；由现有客户端 → daemon → COM worker 路由，自动生成 SDK/MCP 契约。
- 与既有 `e-*` 短 ID 分离：不延长旧 ID 生命周期。解析成功只发布当前观察范围的新/现有短 ID，不提供写入权限旁路。
- 显式 scope：已保存 `.SLDPRT` 的 Windows 规范化绝对路径、精确配置、单 solid 无 surface body、完整 face/edge census（各 1–64）。拒绝未保存、另一路径、另一配置、缺失/非 OK 原生状态、重复映射、拓扑 census 非双射；不进行最近几何重绑定。
- 保守边界：不是跨任意修改永久稳定标识；路径不是不可伪造的文档 UUID，序列化引用不是授权凭证；不证明未观察到的编辑历史。只承诺原生引用当前可唯一解析且完整已记录拓扑仍能对应。
- 官方依据：IModelDocExtension.GetPersistReference3 / GetObjectByPersistReference3 / Persistent Reference IDs（SOLIDWORKS 官方 API Help）；真实 swconst + sldworks 类型库及保存重开证明留待本分支 Windows targeted 校准。
- 将触及共享文件：operation_schemas.py、result_schemas.py、daemon/operations.py、cli.py、SDK 生成文件；新增隔离的 contracts/host helper/test/CI 校准脚本。与主对话合并时需按契约处理冲突。
- CI：仅新增显式 workflow_dispatch targeted 选项，默认 false；保留既有 PR/secret/default gate。计划便携与 CI 接线测试后仅 dispatch 本分支对应 head 一次；600s/native call、1800s/group，无组内重启/失败原生操作重试。
- 测试/提交/CI run/原生证据：尚未执行或产生。内部校准和公开验收分别记录，未满足保存重开前不声明完成。

## 阶段 2：实现与便携检查完成，待本分支原生校准
- 实际新增 `entity.reference-create` / `entity.reference-resolve`、CLI `--reference-file`、生成式 SDK 方法/TypedDict；MCP 通过既有 capabilities/execute 路由，未新增 COM 公共入口。
- 新增 contracts：`src/swcli/topology_references.py`；COM 身份双射：`hosts/windows_topology_references.py`；worker 公共编排：`daemon/topology_references.py`。共享接口改动：operation_schemas/result_schemas/cli/daemon.operations/sdk generated；既有短 ID registry 不修改。
- 保存路径＋配置精确 scope、完整 faces/edges 双射；原生非零/未知/未写状态、重复映射、跨文档、CAS、最终状态变化均拒绝。失败无 usable handle/reference；首原生错误在最终状态/descriptor 再失败时仍保留。仅新增只读操作，无未知写入白名单。
- 文档：`docs/design/topology-references.md` 与 README；公开限制包括不证明所有几何/邻接/编辑历史不变、路径不是不可伪造文档 UUID、复制/替换/移动不承诺存活。
- 便携：Python 3.14 全套 1839 tests，32 skipped，PASS；包含新增 20 targeted checks。SDK generator/strict mypy 和 11 consumer typing refusals PASS；installed commands/schemas/skill PASS；workflow YAML parse / diff whitespace PASS。
- 持久原始便携证据：`.task-evidence/portable/unit-final.log`、`sdk-types.log`、`targeted.log`（targeted.log 为 descriptor 最终保护测试加入前 19 tests；全套日志包含最终 20 项），未使用 tmp 作为主证据。
- 内部原生脚本：`verify-topology-calibration.py`（实际 swconst 与 IModelDocExtension 签名；hole 删除、notch 面分裂/合并；重建、保存重开、体积及 SHA256）。公开脚本：`verify-topology-references.py`（CLI/SDK/MCP、后台/lease/CAS/另文档、face/edge 保存只读重开、公开 cut 后拒绝与实际输出体积）。`run-topology-targeted.py` 分开记录内部和公开，均非 full release evidence。
- CI：新增默认 false 的 `native_topology_targeted`；仅本分支 workflow_dispatch 且 native_full=false；test/package 前提保留；专属 `swcli-topology-targeted-${github.ref}` concurrency、cancel-in-progress=false；默认 full/release group 仍为 swcli-hosted-windows-solidworks。600s 原生/请求、1800s 每组，无组内重启和失败 CAD 重试；不取消他人 run、不为排队重复 dispatch。
- 提交：本阶段功能提交（精确 SHA 在提交/dispatch 后补记）。CI run/head/参数与原生证据：尚未产生。**未达到 merge-ready，不声明 Windows 原生或公开验收通过。**
