# SWCLI

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](README.md) | [简体中文](README.CN.md)

SWCLI 是一个独立、跨平台的自动化协议、命令行客户端与智能体运行时，用于控制原生 Windows 或基于 Wine 的主机上的 SOLIDWORKS。

项目围绕稳定的自动化契约设计，而不是依赖原始 GUI 操作。主要面向需要可重复执行模型创建、检查、验证、渲染和导出流程的 AI 智能体、CI 系统及工程师。

> [!IMPORTANT]
> SWCLI 是独立的开源项目，与 Dassault Systèmes 或 SOLIDWORKS 没有关联，也未获得其认可或支持。

## 目标宿主

- 安装了原生 SOLIDWORKS 的 Windows
- 通过 Wine 运行 SOLIDWORKS 的 macOS
- 通过 Wine 运行 SOLIDWORKS 的 Linux
- 默认安装并固定 SWCLI 版本的 DockerSW

## 命名

- 项目：**SWCLI**
- 命令：`sw-cli`
- Python 包：`swcli`
- 常驻服务：`swclid`，通过 `sw-cli daemon` 管理
- 协议：**SWCLI Protocol**

## 当前状态

SWCLI 目前处于 pre-alpha 阶段，但已实现带版本的本地协议、常驻 daemon 生命周期、原生 Windows 探测、文档打开/检查/保存/关闭、重建诊断、确定性 BMP 渲染、经过验证的 STEP/GLB/PDF/DWG 导出，以及首个类型化零件建模操作。公开的类型化命令只通过 daemon 执行，不提供直接调用 COM 的后备模式。

目前建模词汇仍有意保持精简。通用草图、特征、稳定实体引用、事务、SDK 和 MCP 仍属于后续工作。daemon 已通过能力发现发布每个受支持操作实际用于请求校验的 JSON Schema。

## 安装

### Windows 平台

要求：

- Python 3.9 或更高版本；
- 已安装原生 SOLIDWORKS，且 COM 注册工作正常；
- pywin32；软件包元数据会在 Windows 上自动安装它。

请从 GitHub Releases 安装固定的 `v0.1.0a1` 预发行 wheel。安装完成后，命令不依赖源码工作区，也不会在后续协议变化时被静默升级：

```powershell
python -m pip install "swcli[windows] @ https://github.com/YJBeetle/SWCLI/releases/download/v0.1.0a1/swcli-0.1.0a1-py3-none-any.whl"
```

只有 `v0.1.0a1` 需要 `[windows]` 后缀；该版本之后的开发版本会在 Windows 上自动安装 pywin32。

`v0.1.0a1` 是预发行版本；命令和 `swcli/v1` 协议在 `v0.1.0` 之前仍可能调整。

安装会在 Python scripts 目录中生成 `sw-cli.exe`。如果新终端找不到 `sw-cli`，请把该目录加入用户 `PATH`，然后重新打开终端：

```powershell
$scripts = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $scripts) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User")
}
```

验证软件包安装和宿主探测：

```powershell
sw-cli version --json
sw-cli doctor --json
sw-cli daemon status --json
```

`daemon status` 可能提示服务尚未运行，这不代表安装失败。在原生 Windows 上，首个类型化 `document` 或 `part` 命令会自动启动本地 daemon。如果需要明确控制启动时机或可见性，可主动执行 `sw-cli daemon start`。

当 scripts 目录尚未加入 `PATH` 时，也可使用等价形式 `python -m swcli`：

```powershell
python -m swcli version --json
```

### DockerSW

DockerSW 镜像会安装并固定经过测试的 SWCLI 版本，请勿在容器内重复安装。可用以下命令验证内置客户端：

```bash
sw-cli version --json
sw-cli doctor --json
```

在 DockerSW 中，`sw-cli` 客户端由 Linux Python 运行，daemon/COM worker 则由 Wine 下的 Windows Python 运行。DockerSW 负责这套分离运行时、Wine 配置、SOLIDWORKS 注册和进程生命周期。

### 开发工作区

希望源码修改立即生效的贡献者可以使用 editable 安装：

```powershell
python -m pip install --editable .
```

Editable 安装依赖 checkout 始终处于原路径。对于重启后可能无法挂载共享源码盘的虚拟机或部署环境，请勿采用这种方式。在 macOS 或 Linux 上使用同一条命令时，平台条件会自动跳过 pywin32，只安装可移植客户端和协议工具：

```bash
python3 -m pip install --editable .
```

Wine 宿主通常由 DockerSW 或其他宿主集成项目安装。只安装可移植客户端并不会自动配置 Wine、Windows Python、pywin32、SOLIDWORKS 或 COM 注册。

## 快速开始

安装后，可按以下流程只读处理源文件：

```bash
sw-cli version --json
sw-cli protocol show request
sw-cli doctor --json
sw-cli document open model.SLDPRT --read-only --json
sw-cli document inspect --json
sw-cli document inspect --detail structure --json
sw-cli document diagnose --json
sw-cli document render view.bmp --view isometric \
  --width 1024 --height 768 --json
sw-cli document export model.step --strict --json
sw-cli document close --json
```

在另一套流程中创建并验证新零件：

```bash
sw-cli part create-box box.SLDPRT \
  --width-mm 100 --height-mm 50 --depth-mm 20 --json
sw-cli document inspect --detail structure --json
sw-cli document diagnose --json
sw-cli document close --json
```

修改类操作（例如 `save` 和 `rebuild`）可通过 `sw-cli document --help` 查看。

在 Windows 上，`doctor` 会报告 Python 架构、已注册的 SOLIDWORKS 版本和可执行文件、已安装版本、pywin32 可用性、活动 `SldWorks.Application` COM 对象信息以及 `swclid` 健康状态。它不会启动、停止或以其他方式修改 SOLIDWORKS 或 daemon。

## 常驻服务

开发或查看日志时，可在前台运行常驻服务：

```powershell
sw-cli daemon serve
```

服务默认监听 `127.0.0.1:18495`。Supervisor 接收带版本的本地 JSON 请求，由一个派生的 COM worker 独占 `SldWorks.Application` 实例，并在单个 COM apartment 中串行执行操作。`sw-cli daemon start` 会在后台启动同一套 `serve` 实现，并且可安全重复调用。`sw-cli daemon status` 报告 worker 和宿主状态；`sw-cli daemon stop` 请求优雅关闭。操作超时后会终止 worker 及 daemon 所有的 SOLIDWORKS 进程树，下一个请求再启动干净的独占宿主。

daemon 默认要求独占 SOLIDWORKS。如果用户已经启动 SOLIDWORKS，`sw-cli daemon start` 会返回 `ExistingHostRequiresAttach`，不会静默共享该实例。此时可以关闭已有实例，或者明确选择交互式共享会话：

```powershell
sw-cli daemon start --attach-existing
```

显式附着会保留现有实例的可见性，并报告 `owned_by_daemon: false` 和 `shared_interactive: true`；daemon 停止或超时恢复时都不会关闭或强制终止它。由于 COM 调用超时后共享实例的状态未知，swclid 会以 `SharedHostRecoveryRequired` 拒绝后续类型化操作，直到用户检查 SOLIDWORKS 并重启 daemon。Windows 平台上的类型化命令自动启动始终采用独占模式，不会隐式选择共享。

TCP 建连使用独立的 3 秒超时，使本地 daemon 不存在时能够及时启动，同时不压缩 CAD 操作的执行预算。可用 `--connect-timeout` 覆盖该值；`--request-timeout` 只控制连接建立后的 CAD 操作。

所有类型化的 `sw-cli document` 和 `sw-cli part` 命令都使用该服务。默认端点是 `127.0.0.1:18495`，可通过 `--endpoint HOST:PORT` 或 `SWCLI_ENDPOINT` 选择其他 daemon。无法连接 daemon 时会直接报错，绝不会回退到第二套直接 COM 执行模式。在原生 Windows 上，如果所选本地端点未运行，类型化命令会使用与 `sw-cli daemon start` 相同的后台启动逻辑；远程端点绝不会被隐式启动。当前协议没有传输层认证，因此 `daemon serve` 默认拒绝监听非回环地址；只有明确传入 `--allow-remote` 才会放行。该参数不会增加任何认证，只能在可信网络边界或已认证隧道后使用。`doctor` 始终是只读操作。

可以查询已经运行的 daemon 所声明的版本化能力，而不会隐式启动 SOLIDWORKS：

```bash
sw-cli capabilities --json
```

成功时，JSON 输出直接符合公开的 capabilities schema，包含协议与服务版本、操作列表、每个操作的参数 schema 与可用请求上下文、worker 与恢复状态及当前宿主描述。服务端使用同一份操作目录校验请求。daemon 未运行或版本过旧时会明确报错，不会自动启动或静默接受不兼容结构。

## 文档操作

`document open` 支持原生零件、装配体和工程图文件，并返回准确的 `OpenDoc6` 错误与警告位掩码。每次打开或创建都会返回 `d-k7m2q9` 形式的短期 ID，并把该文档设为所选 CLI session 的 `current`。文档关闭或 worker 重启后 ID 即失效。`document list` 返回全部打开文档及各自的 `active`、`current` 状态；`document use ID` 用于明确修改 session 的 `current`。

省略 `--document` 时，命令操作 session 的 `current`；`--document ID` 仅为本次命令指定确切文档，`--document active` 仅为本次命令选择 SOLIDWORKS 前台文档，两者都不会改变 `current`。并发客户端可以通过 `--session NAME` 或 `SWCLI_SESSION_ID` 隔离各自的当前文档；不指定时使用共享的 `default` session，方便编写线性脚本：

```powershell
sw-cli document open model.SLDPRT
sw-cli document rebuild
sw-cli document export output.STEP --strict
sw-cli document close
```

`document inspect` 报告所选文档的类型、路径、标题、修改状态、SOLIDWORKS `GetUpdateStamp` 值及重建状态。该更新戳会跟踪模型状态和几何变化，但不是覆盖外观或命名修改的完整 revision。JSON 输出始终采用 UTF-8，使远程 runner 也能可靠读取路径和模型名称。

调用方读取文档后再执行操作时，可以给任意选中文档的命令添加 `--if-update-stamp N`。daemon 会在进入 COM 操作前立即比较原生更新戳；如果文档已经变化，则返回 `DocumentUpdateConflict`，且不执行该操作。省略此选项时保持原有的宽容行为：

```powershell
sw-cli document inspect --json
sw-cli document rebuild --if-update-stamp 106 --json
```

需要执行较长多步流程的客户端可以获取短期文档 lease。lease 有效期间，关闭、保存、重建、渲染和导出操作必须携带它的 token；其他 session 仍可执行检查和诊断。默认 TTL 为 60 秒，可设置为 1 至 3600 秒：

```powershell
$lease = sw-cli --session agent-a document lease acquire --ttl-seconds 120 --json |
    ConvertFrom-Json
sw-cli --session agent-a document rebuild --lease $lease.lease.lease_id
sw-cli --session agent-a document lease release $lease.lease.lease_id
```

`lease status` 返回持有状态和剩余时间，`lease renew` 用于延长本 session 持有的 lease。lease 到期后自动失效，文档关闭时也会被清理；它用于客户端协作，不是身份认证机制。

lease 的边界有意保持狭窄：

- lease 只属于一个 daemon/worker 进程。即使多个 SWCLI daemon 或容器挂载并打开同一文件，它们之间也不会协调；这不是分布式文件锁。
- 持有者未释放就退出时，文档会继续受到保护，直到 TTL 到期。CI 应选择够用但较短的 TTL，并在长操作期间续租。
- lease 保护修改以及视图/产物操作，不阻止读取。其他 session 仍可重新打开同一路径、检查和诊断文档。
- `lease status` 会向其他 session 隐藏 token，但为了协作会报告持有方的 `session_id`；它不是多租户隐私边界。

`document close` 遵循保守的生命周期策略：除非明确传入 `--discard`，否则拒绝关闭已修改的文档。

结构检查还会返回活动配置、全部配置名称、明确的文档单位、按模型定义顺序进行的有界顶层特征遍历，以及零件实体的拓扑摘要。特征名称用于人类阅读，特征类型才是面向机器的判别字段；调用方不能假定编辑后名称或位置仍然稳定。

`document diagnose` 是只读操作，报告 `NeedsRebuild2` 以及每个特征非零的 `GetErrorCode2` 结果。`document rebuild` 默认只重建过期特征，`--force` 则执行完整重建。两者都返回同一种有界诊断结构，便于智能体比较操作前后状态。

`document save` 使用 `Save3` 原位保存所选原生文档。响应包含原始 SOLIDWORKS 保存错误/警告位掩码、每个已置位 bit 的稳定名称，以及保存前后的文档状态。只有 API 调用成功且保存后文档处于 clean 状态，操作才算成功。

`document render` 会使所选模型适合其视口，并按明确的像素尺寸导出 BMP。默认拒绝覆盖文件，并在返回图像产物前验证 BMP 头和尺寸。渲染始终先写入目标目录内的临时文件，验证通过后才替换正式输出。`--view` 支持与本地化无关的确定性方向：`front`、`back`、`left`、`right`、`top`、`bottom`、`isometric`、`trimetric` 或 `dimetric`；默认值 `current` 保留当前 UI 视角。

`document export` 可将所选零件或装配体转换为 STEP、所选装配体转换为 GLB，或将所选工程图转换为 PDF/DWG。它会清除选择以导出完整文档，默认拒绝覆盖，并验证结果文件签名及非空内容。默认模式是宽容的：即使源文档需要保存、需要重建，或导出过程中状态发生变化，也会完成导出，但只在发现这些问题时返回结构化警告。`--strict` 会在调用 SOLIDWORKS 前拒绝需要保存或重建的源文件，并在导出导致源状态变化时判定失败。两种模式都先写入目标目录内的临时文件，通过文件验证及严格模式检查后才替换正式输出。核心导出操作只按明确的输出扩展名选择格式，不解释源文件命名约定。

`part create-box` 是首个类型化建模操作。它会创建中心矩形草图并拉伸，重建和诊断结果，保存原生零件，再返回实体拓扑与近似轴对齐包围盒。该操作使用明确的 `.PRTDOT` 路径创建文档，而非调用交互式 `NewPart` 命令：`--template` 优先，其次是配置的默认模板，最后在已安装 SOLIDWORKS 根目录下进行确定性搜索。如果找不到可用模板，它会返回结构化错误，而不是等待隐藏的模板选择对话框。

保存前，请求尺寸会以较小的冒烟测试容差与包围盒对比。CLI 中的尺寸明确采用毫米，内部转换为 SOLIDWORKS 系统单位。SOLIDWORKS 将 body box 定义为近似值，因此这项证据不能当作精密测量结果。

已实现的边界和长期执行模型请参阅[架构说明](docs/architecture.md)。

## 开发

```bash
python -m unittest discover -s tests -v
```

无需安装即可直接从 checkout 运行测试，只需把源码目录加入模块路径：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

CI 会在 Windows 2025 上使用 Python 3.9 和 3.14 运行单元测试，并在 Linux 上构建和检查发行包；这两类任务都不声称能够证明 Wine 兼容性。真实 SOLIDWORKS 建模会在一次性的 GitHub-hosted Windows runner 上，使用带版本的安装缓存进行验证；经过补丁的 Wine 集成仍由 DockerSW 和 MacSW 负责。另一个手动 probe 用于诊断磁盘清理和 Google Drive ISO 流式访问，但不会宣称 Windows Server 是受支持的 SOLIDWORKS 客户端环境。详见 [Windows CI](docs/windows-ci.md)。

## 许可证

SWCLI 采用 [MIT License](LICENSE) 开源。
