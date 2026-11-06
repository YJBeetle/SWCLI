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
