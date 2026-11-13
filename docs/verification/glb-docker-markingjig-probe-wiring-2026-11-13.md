# Docker MarkingJig 只读 probe 接线准备（2026-11-13）

本轮完成运行面、镜像文件和现有宿主源码取证，**没有运行 Wine、sw-cli、COM、SOLIDWORKS、OpenDoc 或 SaveAs，没有复制业务模型**。仅三只本路隔离静态 Linux Python 容器，全部 exit0 并确认删除。其他11只既有容器保留，Windows VM/GUI 未访问。当前还没有可安全执行的 Wine 模型 probe：平台身份合同存在明确阻塞，不能把 Windows 候选只换路径后运行。

## 当前真实运行面与已安装内容

本机没有 Docker CLI；本机 Podman 默认连接拒绝，未初始化或启动其 VM。可用路径是原有 SSH alias `workspaceroot` → Linux amd64 / Debian13 / root Podman5.4.2。没有建立 docker→podman alias，也未改 SSH/context/daemon。

| 本地缓存 tag | 不可变 image/config ID（前缀） | 捆绑 SWCLI 源码 | 已安装 Wine 包 | SW 静态 PE 版本 |
| --- | --- | --- | --- | --- |
| latest-zh-cn-cli | `7823979a9862` | 0.1.0a2 | 11.16~jammy-1 | 33.5.0.53 |
| 2025-zh-cn-cli | `377e9edd59f8` | 0.1.0a13 | 11.16~jammy-1 | 33.5.0.53 |

完整 ID、RootFS diff IDs、当前 OCI manifest digest、所有本地 RepoDigests、文件 SHA、版本资源偏移和原输出见结构化审计。两者 SW EXE 都为712576B、SHA `911309f7494e806f22914bab40aa65531c01b45888ec482ac555fbd8b4f0a18b`；Wine版本文件也为11.16，Wine-Mono文件记录11.3.0。Windows Python位于 `C:\Python311\python.exe`，PE版本为 `[3,11,9150,1013]`，SHA `5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec`。这些是镜像内真实安装文件/包/源码证据，**不是执行 wine --version、SWCLI CLI 或 COM RevisionNumber 的结果**。

当前 `.Digest` 分别是 OCI manifest `sha256:070eb7d0423a49a79e1643ae7fc5ded5f9526d973d29765ff9eea78a53551c3c` 和 `sha256:b07bdac0aea38fc530e41ec8b299b2c0d2821a212787b6b6e4d6e2e0bb2dc5fc`。本地 RepoDigests 仍包含旧记录的5b8068…/2a1ef4…关联。原 image/config ID相同，但不能把多个digest字段混写、擅自解释转换原因或补作历史job digest。没有访问registry、pull、tag或晋升镜像。

本地正式 DockerSW `2025` checkout HEAD `3169b02bbd26d8c610a44106c480f3e2915bb08d`；gitlink为 `77be93d7d709cdc998f552ff715d75115f020114`，原有 `M swcli/SWCLI` 保持。其README声明Wine11.21，这与旧缓存安装11.16是不同证据层，不能把源树说明当缓存内容。正式分支、gitlink、用户文件、CI与aliases均未修改。

## 与历史成功对照的范围

用户确认过 MarkingJig 的现有 GLB 在 Blender 可用，并说明使用 DockerSW latest；现有 GLB 的严格网格统计及 source SHA 已归档。当前缓存没有与该生成job的实际manifest/API/加载状态绑定，故不能把今天0.1.0a2/11.16倒填成其历史环境。

当前两份缓存的 exporter 源分别在 windows_documents.py:749/:810 调用旧 `document.SaveAs3(str(export_path),0,1)`，源码 SHA 分别为3b432a…/b96d94…；这不是该API本轮被执行的证据。Windows候选的现代Extension七参保存也不能因此改回旧API。本轮只准备0保存probe，不用两个API或两个镜像轮流试。

缓存实际入口为 `/usr/local/bin/sw-cli`，不是当前源码树的 `/usr/local/bin/swcli`。静态入口明确：普通协议客户端走Linux Python；doctor/daemon走 Wine Windows Python。默认双entrypoint会运行runtime启动脚本及daemon预热，因此**任何仅做能力检查的步骤必须覆盖默认入口**；本轮均直接 `/usr/bin/python3 -I -B -`，从未运行这些别名、winepath或daemon。

latest缓存 server.py:191 的 `acquire_resident_app(... attach_existing=False)` 保留既有对象拒绝逻辑：只有原GetActiveObject不可用时才DispatchEx，发现现有host则要求显式attach而拒绝默认连接。未来可复用这个固定来源的owned获取语义，不得传attach_existing或复用默认预热出来的daemon。`_com_value` 的property/method读取语义也有静态原件。未据缺失的某个linux_wine.py文件推断整个镜像没有Wine支持。

## 最小接线差异：仅私有诊断，不改产品或 Windows harness

建议后续只选一份固定镜像；latest的 `7823979…` 仅作为贴近用户标签的提案，尚未批准模型执行。不是两镜像CAD矩阵。三个私有接缝如下：

| 接缝 | 可复用/必须保持 | Wine侧新增证明，缺失即停 |
| --- | --- | --- |
| 文件与路径 provider | 固定库存、普通独立只读副本、全SHA、`WorkingCopy.external` 的物理同一文件约束；所有既有字段严格比较 | Linux持有fd的dev/ino与Wine完整卷号/128-bit FileID如何对应；WinAPI Basic/Standard、birth/change/write/attrs/links及raw路径完整可读。不能只按basename、winepath文本或hash替代identity |
| owned host / process callback | 固定cached acquire helper、拒绝existing host、一次activation、实际revision/visible等读回、只清理owned对象 | Wine Windows PID、Creation FILETIME、实际loaded PE hash及私有容器Linux进程/前缀所属关系。`/proc/pid/exe`常是Wine loader，不能拿它冒充SLDWORKS.exe；不能把Wine PID当Linux PID |
| 外层生命周期 / source transport | core Observation/OpenDoc7规格/现代双依赖清单/完整图与几何/单次loaded seal/首错/独立postchecks保持 | 私有prefix、显示、许可证最小启动条件；独立输出、600/1800监督及真实退出证据。不能直接复用 Windows C:\Workspace loader、宿主句柄或session假设 |

未来私有launcher只允许mode=probe，exporter应为不可调用的拒绝入口；调用到它直接失败，不能借旧cached API产出文件。`Observation` 的copy和process_identity注入位置可以复用，Windows `file_forensics.NativeBackend` 和 `_owned_harness` 不应被改成“假装Wine也是同一Windows环境”。如要给capture显式注入Wine backend，须独立亲审，默认Windows实现/断言不变，不使用monkeypatch。

### 现存硬阻塞

- 当前严格Win32 backend明确钉住CPython3.14.7/64bit。已核的缓存默认解释器为Windows Python3.11，不把它外推成镜像绝无其他解释器，也不把静态版本当作某次实际daemon的选择。未来须显式固定解释器/源码路径与hash，不接受环境override偷偷替换。官方接口在3.12才增加Windows birthtime_ns，并改变Windows大文件标识的表示；因此不能把3.14.7的Python字段/Win32完整ID直接等同于3.11，更不能填造缺失birthtime、截断高64位或放宽None。Wine内实际字段尚未运行验证。[CPython官方stat接口](https://docs.python.org/3.12/library/os.html#os.stat_result)
- 既有3.14.7跨Python路径/句柄ctime特例和top开阶段完整 held-ctime/Win32-ChangeTime证据规则不自动授权给Wine。原值/单位保留，atime只按已审明确策略记录；如果只有一条ctime渠道变化或任一其他字段漂移，仍拒绝，不能删证据项凑通过。
- Wine实现的 FileIdInfo、Basic/ChangeTime、进程查询/等待及路径别名支持未在本轮执行验证。镜像里存在相同SW EXE/PIA线索不证明这些OS行为。必须先有另行批准的私有OS能力证据及不弱于原保护的明确合同；本轮不启动Wine来试。
- 静态SW版本不替代将来真实RevisionNumber；现有业务完整依赖/虚拟归属/几何也不能从邻近10份文件推定。本轮没有读模型或连接其COM。

不能通过换Python、升级Wine、改声明平台或跳过校验强行打通。本系列不扩新功能；在等价identity与metadata保护未明确前，**执行ready=false**。

## 若以后另行批准，输入/容器边界必须如此

1. 在Mac侧先后独立核原11份文件与固定inventory `d7db20…`；既有GLB始终保留。只向本路remote私有目录复制批准10个native文件，不复制整业务目录、不把原Mac目录暴露给Wine、不把二进制加入仓库/CI。本轮复制数为0。
2. container daemon在远端，不能把Mac路径当其bind源。只bind本路remote新副本为只读、代码为只读、新输出分离；source的Linux与Wine视角都须物理验证，源nlink1/no symlink/reparse/unlisted规则不变。
3. private Wineprefix必须与别人完全隔离，保持cached布局的同一路径/反向DLL链接语义。不能共享用户prefix或默认daemon，不能修改正式镜像/tag/alias/CI。若需要写prefix以运行，只能是明确批准的新私有副本，不能因此把模型输入变可写；不自动运行注册/修复脚本。
4. Xvfb/display/许可证启动需要独立审查。静态容器network=none不证明CAD在无网络下可获许可证；不得自动改host network、开放VNC/端口或安装更新。Windows VM已有用户CAD，完全不作为这条路线的资源或依赖。
5. 原readonly/clean/full、configuration/edit/unloaded/suppression、host flags、现代GetDependencies五参双多重集、external/virtual所属关系、完整catalog与几何全部保持。未知或缺引用即0保存停，不resolve/rebuild/换配置/补拷/换API。成功probe也只是当前loaded源的只读观察，不授权导出或声称重现历史成功。
6. 原始首错与所有post证明独立，未取得owned COM handle不补造正常SW退出。只关闭owned文档/实例并记录真实wait；不能用全局wineserver kill清理别人，也不能把强制终止算正常通过。失败不接第二次activation或另一镜像。

## 本轮隔离与推送回执

三只静态容器均固定完整image ID、pull=never、network=none、rootfs只读、忽略image volumes、cap-drop=all/no-new-privileges、未请求host PID/IPC、有限CPU/内存/pids、覆盖Linux Python入口，无host bind。两份版本读取各验证root只读且有效capability mask=0；PID/IPC未另取namespace inspect原件，未来模型容器须显式设置private。第三只只读静态源码，全部确认删除。无镜像/正式仓库/用户容器变更。原始stdout及采集源保留，独立audit可离线重放。

已按授权非force推进本GLB备份分支 `8232447… → 7d6858e65d089ec4f49f2fd9cbcdfd9258c05270`，post-push ls-remote一致，未push main。自动push CI只取一次快照：[43332197803](https://github.com/YJBeetle/SWCLI/actions/runs/43332197803)，当时in_progress；未手动dispatch，也未后查终态。当前Docker接线准备是新本地审查材料，不自动推送或晋升。
