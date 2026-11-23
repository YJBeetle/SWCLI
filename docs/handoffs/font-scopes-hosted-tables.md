# Hosted 表格字体原生验证

本候选在 `codex/docprops-font-scopes-next` 保留尺寸和表格字体历史，合入现行主线 `5b2a71a43bbf33cf1b0b4e3f48def8feab045d45`。表格使用 GitHub 的 `windows-2025`、SOLIDWORKS 33.5.0 和精确候选 wheel。尺寸仍用[手工夹具](font-scopes-next-fixtures.md#尺寸手工建夹具清单)，公开写入仍限 Notes。

## 入口状态

旧字体工作流只在 `codex/docprops-font-scopes` 接受 `internal` 和 `public-notes`。Hosted 表格步骤及回执检查已准备，候选分支要调用原有 Windows 安装作业，需先获准让这个精确分支的 `next-tables` profile 共用安装机密 `RCLONE_CONFIG_B64`。旧分支的批准未覆盖该路径。当前二级分支守卫和机密映射保持原范围，常规 push 仅运行便携检查。

获准后，使用现有默认分支已登记的 `ci.yml`，在候选 ref 选择 `calibrate_font_scopes=true` 和 `font_scopes_profile=next-tables`。两层策略应只接受这一对选择与精确仓库及分支，拒绝与 full、单位或其他原生 profile 混用。直接派发专属 reusable 文件的选项仍限旧 profile。由统筹核对远端精确 head 后派发。GitHub 支持将已登记工作流派发到指定 ref。[手动派发](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow) · [可复用工作流的调用上下文](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#github-context)

## 执行与原件

1. 从精确 checkout 构建 wheel，在 Python 3.14 venv 安装并比对包内 Python 和 schema。先验证实际 Windows 父子进程链，再访问安装机密。
2. 复用现有 hosted 安装和私有输入。用 owned 宿主与官方 GB 模板创建 1×2 General 表。整表与左格继承，右格为局部 Courier New 20 pt。保存后实际只读重开并核对完整快照。
3. 校验 `fixture/native/font-tables-fixture.SLDDRW` 与成功回执中的 SHA-256。用这份夹具跑表格 `internal`，须观察毫米、磅两轮保存重开后的继承变化与局部格式保持。零件、装配和图纸三类内部写入与读回都须通过。该组检查仍沿用五种 linked defaults 默认值 witness。
4. 失败保留首错，跳过后续验证。看门狗每次原生调用限 600 秒，每个原生组限 1800 秒。GitHub 探针步限 2 分钟，夹具和内部组各限 31 分钟。调度预留两组共 60 分钟及安装，实际耗时待首跑。
5. owned 宿主由诊断进程清理。工作流始终清理私有安装输入与服务，始终尝试上传 `font-scopes-next-tables` 目录内的 wheel、离线回执、原始 watchdog、stdout/stderr、trace、详细报告、linked JSONL 和已有 SOLIDWORKS 文件。安装步骤首次错误可在对应 GitHub 步骤日志查看。

两份真实夹具和 SOLIDWORKS 原生结果仍待取得。当前离线测试覆盖虚假探针、夹具哈希变化、范围守卫、首错停止、仅私有输入清理和证据路径。
