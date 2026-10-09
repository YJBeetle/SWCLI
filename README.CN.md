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

SWCLI 目前处于 pre-alpha 阶段，但已实现带版本的本地协议、常驻 daemon 生命周期、原生 Windows 探测、文档打开/检查/保存/关闭、重建诊断、确定性 BMP 渲染、经过验证的 STEP/GLB/PDF/DWG 导出，以及可复用的原生零件建模闭环。公开的类型化命令只通过 daemon 执行，不提供直接调用 COM 的后备模式。

目前建模词汇仍有意保持精简。通用草图编辑、更多特征及编辑、稳定实体引用、事务、SDK 和 MCP 仍属于后续工作。daemon 已通过能力发现发布每个受支持操作实际用于请求校验的 JSON Schema。自 `v0.1.0a4` 起还发布 `operation_result_schemas`，并在 worker 返回结果前校验输出契约。a4 新增未保存零件创建、经过验证的矩形与圆草图、定深拉伸与切除、原生体积/面积观测及新文件名零件另存为。自 `v0.1.0a5` 起支持单圆驱动直径的创建、修改，以及原生保存重开后的尺寸发现。`v0.1.0a6` 新增显式矩形中心固定、驱动宽高创建和修改，以及保存后的宽高对发现；这不代表通用尺寸编辑或草图完全定义。

**a7 开发工作区**还提供只读 `feature list` 和 `feature inspect`，返回准确的短特征句柄。
这些命令不在已发布的 a6 wheel 中，深度编辑也尚未实现。设计与验证边界见
[特征深度计划](docs/design/feature-depth-editing.md) 和
[只读层验证记录](docs/verification/a7-feature-observation-2026-10-10.md)。

## 安装

### Windows 平台

要求：

- Python 3.9 或更高版本；
- 已安装原生 SOLIDWORKS，且 COM 注册工作正常；
- pywin32；软件包元数据会在 Windows 上自动安装它。

请从 GitHub Releases 安装固定的 `v0.1.0a6` 预发行 wheel。安装完成后，命令不依赖源码工作区，也不会在后续协议变化时被静默升级：

```powershell
python -m pip install --upgrade "swcli @ https://github.com/YJBeetle/SWCLI/releases/download/v0.1.0a6/swcli-0.1.0a6-py3-none-any.whl"
```

软件包会在 Windows 上自动安装 pywin32；`v0.1.0a1` 说明中的 `[windows]` 后缀已不再需要。

`v0.1.0a6` 是预发行版本；命令和 `swcli/v1` 协议在 `v0.1.0` 之前仍可能调整。

升级前先停止旧 daemon，安装后明确启动同版本服务。临时文档、草图、尺寸、特征句柄和 lease
会在重启后失效。跨平台客户端安装命令、确切验证证据及限制见
[a6 发行说明](docs/releases/v0.1.0a6.md)。

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

`daemon status` 可能提示服务尚未运行，这不代表安装失败。执行 `document` 或 `part` 前须显式运行 `sw-cli daemon start`（默认隐藏）或 `sw-cli daemon start --visible`。启动命令会等待 SOLIDWORKS 就绪。若 SOLIDWORKS 已经运行，请改用 `sw-cli daemon start --attach-existing`。

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
sw-cli daemon start --visible --json
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
sw-cli daemon start --json
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

服务默认监听 `127.0.0.1:18495`。Supervisor 接收带版本的本地 JSON 请求，由一个派生的 COM worker 独占 `SldWorks.Application` 实例，并在单个 COM apartment 中串行执行操作。`sw-cli daemon start` 会在后台启动同一套 `serve` 实现，并且可安全重复调用。`sw-cli daemon status` 会报告 worker 与宿主状态，包括明确的 `host_connected` 字段；`sw-cli daemon stop` 请求优雅关闭，即使 SOLIDWORKS 已经退出也会成功。worker 空闲时每秒在所属 COM apartment 内探测一次轻量属性：明确的断连 HRESULT 会立即生效，暂时性的 COM call rejection 会重试，未知异常则必须连续发生 3 次才判定宿主断开。SOLIDWORKS 被外部关闭后，daemon 会清除过期宿主、报告 `HostDisconnected` 并拒绝类型化操作，不会静默启动另一个会话。恢复必须显式执行：

```powershell
sw-cli daemon restart
```

操作超时后会终止 worker 及 daemon 所有的 SOLIDWORKS 进程树，后续请求可以再启动干净的独占宿主；该超时恢复策略与宿主被外部关闭是两个独立情形。

daemon 默认要求独占 SOLIDWORKS。如果用户已经启动 SOLIDWORKS，`sw-cli daemon start` 会返回 `ExistingHostRequiresAttach`，不会静默共享该实例。此时可以关闭已有实例，或者明确选择交互式共享会话：

```powershell
sw-cli daemon start --attach-existing
```

显式附着会保留现有实例的可见性，并报告 `owned_by_daemon: false` 和 `shared_interactive: true`；daemon 停止或超时恢复时都不会关闭或强制终止它。由于 COM 调用超时后共享实例的状态未知，swclid 会以 `SharedHostRecoveryRequired` 拒绝后续类型化操作，直到用户检查 SOLIDWORKS 并重启 daemon。类型化命令不会隐式启动或附着宿主。`--attach-existing` 要求已有活动 COM 宿主；不存在时返回 `ExistingHostNotFound`，绝不会退化为创建 daemon-owned 实例。附着的宿主退出后，应先由用户启动 SOLIDWORKS，再执行 `sw-cli daemon restart --attach-existing`。

TCP 建连使用独立的 3 秒超时，使 daemon 不存在时能够及时报错，同时不压缩 CAD 操作的执行预算。可用 `--connect-timeout` 覆盖该值；`--request-timeout` 只控制连接建立后的 CAD 操作。

连接、请求和启动超时必须为正数、有限值，且在平台计时器支持范围内。`daemon restart` 会在停止现有服务前检查本地启动条件；参数无效不会关闭正在运行的服务。这是前置检查，不保证随后 COM 启动一定成功。

每个类型化 CLI 请求默认使用随机请求 ID。可能重试状态不确定请求的自动化可以明确提供稳定键：

```bash
sw-cli --request-id export-build-42 document export output.STEP --strict --json
```

在同一个正在运行的 daemon 内，swclid 会缓存最近完成的响应，包括失败和超时。使用相同 ID 重复完全相同的语义请求时，不会再次进入 SOLIDWORKS，而是返回首次终局结果并报告 `replayed: true`；失败后若要再次执行，必须使用新的 request ID。除非显式传入 `--request-id`，CLI 每次调用都会生成新的 UUID。如果复用该 ID 时改变了操作、参数、session、文档、更新戳或 lease，则返回 `RequestIdConflict`。超时预算不属于请求语义，因此重试时可以调整等待时间。能力发现会报告重放缓存的大小与作用域。该缓存容量有限，且 daemon 重启后会丢失，因此它用于保护紧邻的传输重试，并不承诺跨 daemon 故障的持久化 exactly-once 执行。

所有类型化的 `sw-cli document`、`sw-cli sketch`、`sw-cli feature` 和 `sw-cli part` 命令都使用该服务。默认端点是 `127.0.0.1:18495`，可通过 `--endpoint HOST:PORT` 或 `SWCLI_ENDPOINT` 选择其他 daemon。无法连接 daemon 时会直接报错，绝不会回退到第二套直接 COM 执行模式。本地和远程端点都不会被隐式启动；本地端点不可用时返回带显式启动提示的 `DaemonUnavailable`。当前协议没有传输层认证，因此 `daemon serve` 默认拒绝监听非回环地址；只有明确传入 `--allow-remote` 才会放行。该参数不会增加任何认证，只能在可信网络边界或已认证隧道后使用。`doctor` 始终是只读操作。

可以查询已经运行的 daemon 所声明的版本化能力，而不会隐式启动 SOLIDWORKS：

```bash
sw-cli capabilities --json
```

成功时，JSON 输出直接符合公开的 capabilities schema，包含协议与服务版本、操作列表、每个操作的参数 schema 与可用请求上下文、worker 与恢复状态、请求重放策略及当前宿主描述。服务端使用同一份操作目录校验请求。daemon 未运行或版本过旧时会明确报错，不会自动启动或静默接受不兼容结构。

`v0.1.0a4` 在操作目录中统一声明 handler、文档选择、lease 守卫、临时前台激活和输出契约。结果 Schema 描述协议响应中的 `result`；类型化 CLI JSON 将它展开，并可能添加 `request_id` 和 `replayed`。适配器输出违反契约时返回 `OperationResultInvalid`；此时 CAD 操作可能已经改变了状态，发起新请求重试前应先检查文档。

## 文档操作

`v0.1.0a4` 新增 `document create`，通过真实 `.PRTDOT` 模板创建**未保存的零件**，不生成几何、不重建、不隐式保存。daemon 登记 `NewDocument` 返回的准确对象，为尚无文件路径的文档分配短期 ID，并设为本 session 的 `current`。目前仅支持 `--type part`（默认值）。模板解析与 `part create-box` 一致：显式路径、配置的默认模板、已安装模板搜索；模板不可用时返回错误，不弹出模板选择对话框。

```powershell
sw-cli document create --type part --json
# 或：sw-cli document create --template C:\Templates\Part.PRTDOT --json
sw-cli document inspect --detail structure --json
sw-cli document close --discard
```

通用草图编辑仍待实现；`document save-as` 可为新零件指定文件名，现有 `document save` 则原位保存已有文件名的文档。新建后若后续检查失败，不会自动回滚或悄悄关档；已取得且可读取的文档对象仍会登记，便于明确检查和清理。

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

需要执行较长多步流程的客户端可以获取短期文档 lease。lease 有效期间，建模、关闭、保存、另存为、重建、渲染和导出操作必须携带它的 token；其他 session 仍可执行检查和诊断。默认 TTL 为 60 秒，可设置为 1 至 3600 秒：

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

`document measure --json`（自 v0.1.0a4 起）读取所选零件全部实体（包括隐藏实体）的原生几何属性，返回体积 mm³、表面积 mm²、零件模型坐标中的体积加权几何中心 mm 及逐实体证据。它不改变选择，不激活、重建或保存文档；其他 session 的 lease 不阻止这项只读操作。`--max-bodies` 默认为 1000，超过上限时明确失败，不会只测一部分并当作总量。总量是**各实体的求和，不是几何并集**：重叠体积及接触/内部表面仍逐实体计入。它不报告基于材料的真实质量，暂不支持装配体/工程图；数值几何属性也不等于设计意图正确。

自 `v0.1.0a4` 起，`document save-as new-part.SLDPRT` 为所选零件指定文件名并保存到**全新目标**。已有目标（包括当前文件名）会被拒绝；原位保存请使用 `document save`。暂不支持装配体/工程图另存为或不改名的副本保存。改名后保留同一文档 ID、session current、lease 和存活的草图句柄。响应检查原生保存结果、采用的路径、未保存状态和最小文件大小，不声称验证专有文件格式或完整几何正确性。标量原生调用不提供 warnings 输出，因此 `save_warnings` 为 `null`。更强验证应关闭重开并检查模型。原生另存为会改变 COM 文档的文件名，不能套用中性格式导出的临时文件重命名策略；失败后可能仍留下已改名的活动文档，请检查返回状态与清理 warnings。

`document render` 会使所选模型适合其视口，并按明确的像素尺寸导出 BMP。默认拒绝覆盖文件，并在返回图像产物前验证 BMP 头和尺寸。渲染始终先写入目标目录内的临时文件，验证通过后才替换正式输出。`--view` 支持与本地化无关的确定性方向：`front`、`back`、`left`、`right`、`top`、`bottom`、`isometric`、`trimetric` 或 `dimetric`；默认值 `current` 保留当前 UI 视角。

`document export` 可将所选零件或装配体转换为 STEP、所选装配体转换为 GLB，或将所选工程图转换为 PDF/DWG。它会清除选择以导出完整文档，默认拒绝覆盖，并验证结果文件签名及非空内容。默认模式是宽容的：即使源文档需要保存、需要重建，或导出过程中状态发生变化，也会完成导出，但只在发现这些问题时返回结构化警告。`--strict` 会在调用 SOLIDWORKS 前拒绝需要保存或重建的源文件，并在导出导致源状态变化时判定失败。两种模式都先写入目标目录内的临时文件，通过文件验证及严格模式检查后才替换正式输出。核心导出操作只按明确的输出扩展名选择格式，不解释源文件命名约定。

## 草图操作（自 v0.1.0a4 起）

```powershell
sw-cli document create --json
sw-cli sketch rectangle --plane front --width-mm 100 --height-mm 50 --json
sw-cli document inspect --detail structure --json
sw-cli document close --discard
```

`sketch rectangle` 在零件的 `front`、`top` 或 `right` 原点基准面上新建二维草图，不依赖本地化的基准面名称。宽、高及可选的 `--center-x-mm` / `--center-y-mm`（默认零）均使用**草图局部坐标中的毫米**。响应包含原生 `model_to_sketch_transform`（平移分量单位为米）、经过验证的四条轮廓边界、原生约束状态及 `s-ab12cd` 形式的短草图 ID。ID 绑定本次文档与 worker 内的准确草图特征对象，关档或 worker 重启后失效，不是跨保存、重开或拓扑变化的持久引用。

创建会验证真实中心点及其与两条构造对角线的重合约束。如果原生隐藏模式工具省略中心点，SWCLI 会在本次新建草图中显式创建该点和两条约束；不会放宽中心约束检查，也不会修复带额外原点约束的导入草图。

命令退出草图编辑后才验证最终几何，不添加驱动尺寸，也不保证草图完全定义。已有草图处于编辑状态时明确拒绝，不接管编辑。`--document`、`--lease` 和 `--if-update-stamp` 与文档写操作使用相同守卫；临时激活后台文档不会改变 session 的 `current`。失败时只尝试退出本次操作开启的草图编辑，不回滚已生成的部分几何；退出清理失败会返回 warnings。

`sketch circle --plane front --radius-mm 8` 使用与矩形相同的文档守卫和关闭编辑生命周期，新建完整圆草图。可选的 `--center-x-mm`、`--center-y-mm` 默认为草图局部坐标中的零；`radius` 是半径，不是直径。验证会读取最终原生圆弧的完整圆标志、半径与圆心，拒绝局部圆弧或多余轮廓，并返回可供拉伸的文档内草图 ID。它不添加驱动尺寸，也不保证完全定义。

`sw-cli sketch inspect SKETCH_ID --json` 可在创建后重新读取登记的二维草图，也可观察
已经被拉伸或切除吸收的草图。返回当前原生约束状态枚举值 `swConstrainedStatus_e`、
编辑/吸收状态和所属特征，直线端点、圆弧/完整圆的圆心半径采用草图局部毫米坐标，
构造线同样返回并标记。原生坐标变换中的平移分量仍为米。
其他类型只返回类型元数据、`geometry: null`，同时明确报告 `geometry_complete: false`
和 warning；这不是完整几何或全约束认证。`--max-segments` 默认 1000，超限失败而非悄悄截断。

这是只读命令，不选取、不进入编辑、不重建/保存/激活文档，不要求写入 lease，支持文档选择和
更新戳检查，保持 session current 和前台不变。只能使用本 worker 登记且仍有效的草图 ID，
不能用名称或序号代替；关闭重开后原 ID 失效。

自 `v0.1.0a5` 起，
`sw-cli sketch list --document DOCUMENT_ID --json` 可以发现打开或重开的零件内仍存活的
二维草图，包括被特征吸收的草图，返回新的文档/worker 内短句柄及原生约束、归属元数据。
重复列举同一个存活原生草图会复用其 ID；不会复活过期 ID，也不按名称猜对象。
用返回的 ID 调用 `sketch inspect`。列举只读，支持文档/更新戳上下文但不接受 lease，
保持前台和 session current 不变。`--max-sketches` 默认 1000；超限或遍历失败会报错，
不会把部分列表当成功返回。列举本身不发现尺寸，也不覆盖三维草图。

## 驱动直径（自 v0.1.0a5 起）

调用前请核对当前 daemon 的 capabilities；旧版 a4 宿主尚无这些命令：

```powershell
sw-cli document create --json
$circle = sw-cli sketch circle --plane front --radius-mm 5 --json | ConvertFrom-Json
$diameter = sw-cli sketch dimension-diameter $circle.sketch.sketch_id --diameter-mm 16 --json | ConvertFrom-Json
sw-cli dimension inspect $diameter.dimension.dimension_id --json
sw-cli feature extrude $circle.sketch.sketch_id --depth-mm 10 --json
sw-cli dimension set $diameter.dimension.dimension_id --value-mm 20 --json
```

创建要求尚未被特征吸收、没有已有尺寸的单个完整圆。返回的 `m-xxxxxx` 是文档/worker 内准确原生直径及其所属草图的短期句柄，关闭重开即失效。inspect 只读；set **仅修改当前配置**，支持草图被特征吸收后继续修改。它拒绝从动、只读、方程或设计表控制的尺寸及已有草图编辑状态，不强行接管这些参数。

写操作遵守文档、session、lease 和 update-stamp 守卫。验证包含原生值、保持不变的圆心、半径、重建诊断及下游实体测量，但不保证任意设计意图或草图完全定义。失败可能保留部分修改及句柄；恢复原前台文档失败时，会保留修改证据并报告失败，不伪装成成功。

保存重开的零件可先用 `sketch list` 获取新草图 ID，再只读恢复该单圆草图可观察的直径：

```powershell
$found = sw-cli dimension discover-diameter SKETCH_ID --document DOCUMENT_ID --json | ConvertFrom-Json
sw-cli dimension inspect $found.dimension.dimension_id --document DOCUMENT_ID --json
```

发现支持被特征吸收的草图，重复观察同一个存活原生尺寸会复用其 ID，保持前台、session current、配置、编辑状态和更新戳不变，不创建尺寸也不开启尺寸显示。显示链为空意味着无法观察，不意味着文件没有尺寸；有歧义、遍历不完整或原生状态不一致时会失败，不发布句柄。当前仅支持当前配置中单个完整圆的直径，不覆盖任意尺寸或持久 ID。获得句柄不代表获得修改、保存源文件的授权，`dimension set` 仍遵守参数归属和写操作守卫。

Windows 已安装 wheel、全新托管可见/隐藏双模式验证，以及独立的 DockerSW 隐藏 Wine 交付通过记录，见 [a5 验证记录](docs/verification/a5-2026-10-07.md)。[a5 发行说明](docs/releases/v0.1.0a5.md) 区分开发候选与正式版本验证；两者都不代表 MacSW 实际运行验证。

## 矩形定位与驱动宽高（自 v0.1.0a6 起）

这些命令需要匹配且通过 capabilities 发布 a6 操作的 daemon；a5 wheel 不包含它们。正式版本已通过 Windows 可见/隐藏双模式及 DockerSW 隐藏 Wine 门禁。各宿主的证据与限制见 [a6 发行说明](docs/releases/v0.1.0a6.md)。

```powershell
sw-cli document create --json
$rectangle = sw-cli sketch rectangle --plane front --width-mm 40 --height-mm 30 --center-x-mm 3 --center-y-mm 4 --json | ConvertFrom-Json
sw-cli sketch fix-center $rectangle.sketch.sketch_id --json
$size = sw-cli sketch dimension-rectangle $rectangle.sketch.sketch_id --width-mm 40 --height-mm 30 --json | ConvertFrom-Json
sw-cli feature extrude $rectangle.sketch.sketch_id --depth-mm 10 --json
sw-cli dimension inspect $size.dimensions.width.dimension_id --json
sw-cli dimension set $size.dimensions.width.dimension_id --value-mm 50 --json
sw-cli dimension set $size.dimensions.height.dimension_id --value-mm 35 --json
sw-cli document measure --json
```

定位是显式选择：`fix-center` 只固定受支持、尚未被吸收的中心矩形的准确原生中心；宽高创建**不会隐式调用它**。准确已有固定关系会成为经过验证的无操作；额外、被抑制或原点关系会被拒绝，不会被删除。中心坐标为 (0,0) 本身不证明已有原点约束。宽高验证通过不代表通用约束求解或机械设计审批。

返回的 `.dimensions.width` 与 `.dimensions.height` 是准确原生轴尺寸的存活句柄。inspect 只读；set 只修改当前配置，保持另一轴与中心，检查原生读回、重建诊断及适用的下游实体证据。不会覆盖从动、只读、方程或设计表控制，写操作仍遵守文档、session、lease 与更新戳守卫。失败可能留下部分原生尺寸但没有公开句柄对，不保证回滚。

在获准保存原生零件并关闭重开后，先用 `sketch list` 取得新草图，再发现宽高：

```powershell
$found = sw-cli dimension discover-rectangle --document DOCUMENT_ID SKETCH_ID --json | ConvertFrom-Json
sw-cli dimension inspect --document DOCUMENT_ID $found.dimensions.width.dimension_id --json
sw-cli dimension inspect --document DOCUMENT_ID $found.dimensions.height.dimension_id --json
```

请把占位符换成返回的 ID。发现要求唯一可观察的准确原生宽高对，与独立几何及保持不变的配置、编辑状态、更新戳一致。它保持前台和 session current，不选择、激活或改变显示；对同一存活对象重复发现会复用 ID。显示链为空表示无法观察，不证明没有尺寸；不完整或歧义观察不会发布 ID，已关闭文档的旧 ID 始终失效。发现句柄不代表获得修改或保存源文件的授权。确切正式版本证据见 [a6 验证记录](docs/verification/a6-2026-10-10.md)。

## 特征操作（自 v0.1.0a4 起）

```powershell
sw-cli document create --json
$rectangle = sw-cli sketch rectangle --plane front --width-mm 100 --height-mm 50 --json | ConvertFrom-Json
sw-cli feature extrude $rectangle.sketch.sketch_id --depth-mm 20 --json
sw-cli document inspect --detail structure --json
sw-cli document save-as new-part.SLDPRT --json
sw-cli document close --json
sw-cli document open new-part.SLDPRT --read-only --json
sw-cli document diagnose --json
```

`feature extrude SKETCH_ID` 从所选零件内登记的、尚未被吸收的二维草图创建单方向定深实体拉伸，深度使用毫米；`--reverse` 反转草图法线方向，`--no-merge` 保留独立实体。它解析准确的原生草图，拒绝缺失、删除、已吸收的草图及已有草图编辑状态，然后重建并诊断模型。响应验证原生深度、方向、合并与终止条件，并报告实体证据，不只是回显输入；它不会验证全部设计尺寸，也不保存原生文档。选择清理和前台恢复遵循文档守卫；失败不代表已创建特征会自动回滚。

### 只读特征发现（a7 开发版）

当匹配的开发版客户端与 daemon 广告这些操作时：

```powershell
$features = sw-cli feature list --document DOCUMENT_ID --json | ConvertFrom-Json
sw-cli feature inspect $features.features[0].feature_id --document DOCUMENT_ID --json
```

把 `DOCUMENT_ID` 换成所选零件的 ID。列举仅涵盖受支持的实体拉伸和切除，不是整棵特征树；
`--max-features` 超出限制时失败，不返回被截断的成功列表。句柄指向准确原生特征，重命名及
重复存活观察会复用 ID，关闭重开后失效。只读操作不激活、选择、回滚或重建，可在不携带
写 token 的情况下读取受租或只读零件，仍支持 `--if-update-stamp`。检查报告原生定义标志
和以毫米计的正向深度参数，不代表允许编辑、实际材料厚度或非定深终止的行程。
切除的原生 `reverse_direction` 与创建命令归一化后的 `--reverse` 不是同一语义。

## 零件建模

SWCLI 的 JSON stdout 使用 UTF-8。Windows PowerShell 5.1 中，将 CLI JSON 交给 `ConvertFrom-Json` 前应设置原生命令管道的解码方式：

```powershell
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
sw-cli document status --json | ConvertFrom-Json
```

案例会在每次 CLI 调用期间设置 UTF-8，并在成功或失败后恢复调用者原编码。PowerShell 7 通常已默认使用 UTF-8。

[`examples/model-plate.ps1`](examples/model-plate.ps1) 是可读的 Windows 完整案例，
只组合 typed CLI：创建 100×60×8 mm 四孔板（孔半径 4 mm），检查解析体积/表面积和重建诊断，
保存新 SLDPRT、严格导出 STEP、渲染 BMP，并关闭重开验证几何。它需要运行中的 a4 daemon
及匹配的 client，输出目录必须是已存在的新本地目录，不允许覆盖已有产物：

```powershell
sw-cli daemon start --visible --json
.\examples\model-plate.ps1 -OutputDirectory C:\Models\NewPlate
```

失败立即停止并释放 lease，不悄悄丢弃/保存部分模型，也不重启 daemon。
生成原生可编辑草图和特征，但尚无驱动尺寸/全约束保证；这是本机 Windows 案例，不是远程文件传输或容器启动脚本。

`feature cut-extrude SKETCH_ID --depth-mm 20`（自 v0.1.0a4 起）从未吸收的二维轮廓创建单方向定深切除，移除轮廓内部材料。与 `feature extrude` 一致，CLI 默认**沿草图法线**，`--reverse` 表示反法线；adapter 会转换 SOLIDWORKS 原生切除相反的默认方向。切除作用于全部相交实体，不猜测已选实体范围，暂不支持贯穿、拔模、薄壁或钣金法向选项。它重建模型、核对原生深度/方向/终止条件，并要求实体求和体积实际减少，超过 `max(1e-6 mm³, 原体积 × 1e-12)`。没有可测实体或切除后不再有可测实体的零件，不能通过这版验收契约。响应提供前后几何证据，不承诺自动回滚或完整孔形验证；失败时特征可能已创建。

```powershell
$hole = sw-cli sketch circle --plane front --radius-mm 4 --json | ConvertFrom-Json
sw-cli feature cut-extrude $hole.sketch.sketch_id --depth-mm 20 --json
sw-cli document measure --json
```

应在实体与轮廓/深度相交的零件中运行，而不是空文档；文档选择、lease 与更新戳守卫均适用。

`part create-box` 是首个类型化建模操作。它会创建中心矩形草图并拉伸，重建和诊断结果，保存原生零件，再返回实体拓扑与近似轴对齐包围盒。该操作使用明确的 `.PRTDOT` 路径创建文档，而非调用交互式 `NewPart` 命令：`--template` 优先，其次是配置的默认模板，最后在已安装 SOLIDWORKS 根目录下进行确定性搜索。如果找不到可用模板，它会返回结构化错误，而不是等待隐藏的模板选择对话框。

保存前，请求尺寸会以较小的冒烟测试容差与包围盒对比。CLI 中的尺寸明确采用毫米，内部转换为 SOLIDWORKS 系统单位。SOLIDWORKS 将 body box 定义为近似值，因此这项证据不能当作精密测量结果。

已实现的边界和长期执行模型请参阅[架构说明](docs/architecture.md)。

## 供 AI agent 使用

项目自带可移植的 [SWCLI skill](src/swcli/skills/swcli/SKILL.md) 和 [agent 使用指南](src/swcli/skills/swcli/references/usage.md)，说明能力发现、文档/session 选择、并发守卫、单位、导出检查和失败恢复。这是面向**使用 SWCLI 产品**的 agent，不是仓库维护交接说明。通过所用 agent 工具自己的技能机制加载或安装完整的 `swcli` skill 文件夹即可。Python 安装包包含这些文件，但不会修改 agent 配置；Python 3.9+ 可通过 `importlib.resources.files("swcli")` 访问其中的 `skills/swcli`。

## 开发

源码发行包包含中英文 README、架构/路线图/发行说明、可执行案例及验证脚本。
wheel 只安装运行代码、Schema 和可移植产品 skill，不安装仓库的 CI/案例文件。

已完成的开发能力、后续建模与协议工作以及发布验收边界见[产品路线图](docs/roadmap.md)。

```bash
python -m unittest discover -s tests -v
```

无需安装即可直接从 checkout 运行测试，只需把源码目录加入模块路径：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

CI 会在 Windows 2025 上使用 Python 3.9 和 3.14 运行单元测试，并在 Linux 上构建和检查发行包；这两类任务都不声称能够证明 Wine 兼容性。真实 SOLIDWORKS 建模会在一次性的 GitHub-hosted Windows runner 上，通过官方介质全新安装一次，分别在可见和隐藏宿主模式下验证；经过补丁的 Wine 集成仍由 DockerSW 和 MacSW 负责。这不代表 Windows Server 是官方支持的 SOLIDWORKS 工作站。详见 [Windows CI](docs/windows-ci.md) 和 [共享运行时测试](docs/runtime-tests.md)，后者说明通用建模与驱动尺寸脚本，以及离线契约测试和真实宿主证据的区别。

## 许可证

SWCLI 采用 [MIT License](LICENSE) 开源。
