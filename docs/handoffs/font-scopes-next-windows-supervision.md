# 字体表格首跑的 Windows 启动与安装

实现提交 `9d0240cce88eaf656eeb66e15a220aad9da062b9`，分支 `codex/docprops-font-scopes-next`。原 `39a0fe8` 的表格夹具入口及尺寸手工作图清单保留。当前轮没有 Windows 宿主或 COM 结果。

## Windows Python 3.14 看门狗

此前使用 `sys.executable` 启动 venv 重定向器，系统返回的 `Popen.pid` 可能不是执行工作代码的 PID。对照工程图 `34baf8e` 的 Windows 探针原证据和本地 CPython 3.14 的 `multiprocessing/popen_spawn_win32.py`，scoped Windows 工作进程现在由 `sys._base_executable` 直接启动，并通过 `__PYVENV_LAUNCHER__` 保持同一 venv 与 `-I`。工作进程在 COM 前比对实际父 PID、启动管道给出的 `Popen.pid`、自身 PID、venv 前缀及系统报告的进程映像。看门狗再根据实际启动结果核对子进程生成的 `native/supervision.json`。

预算保持 600 秒调用、1800 秒组。超时使用 `Popen.kill()` 终止这一精确 Python 子进程，保留原迹与报告。普通旧参数调用保持原路径。首次表格准备先跑下面同一路径的无 COM 探针，再进入已排程的 `next-fixture`。

## 精确包与原始摘要

持久证据根为 `artifacts/font-scopes/next-supervision-9d0240cce88e/`。从源码包 `source/` 构建 wheel。源包包含 1,059 个文件，部署应使用该 ZIP 中的脚本和同一行的 wheel。

| 文件 | SHA-256 |
| --- | --- |
| `dist/swcli-0.2.4-py3-none-any.whl` | `1124428e3e236efc7cc27fc9d9036d83389ab36131274f6f74fd3a86e713718a` |
| `source-package/font-scopes-next-source-9d0240cce88e.zip` | `0ecf80eb4233ea7efc088ad102f6b721e35a9d97482db4050d8c80e97b04d0db` |
| `source-package/manifest.json` | `9c33fe2c9e8b6bd27c622afc6b8354c6ce20003d434732eaddb67321462a4369` |

构建使用 Python 3.14.10 和 setuptools 80.9.0。独立 macOS venv 从这个 wheel 安装后，134 个包内文件与源 ZIP 和安装目录逐字节相同。首次联网安装的依赖下载遇到 PyPI TLS 中断，随后离线复用已有同架构 Python 3.14 依赖文件。实际 wheel 安装、`pip check`、SDK 生成检查、Python 3.9 语法及现有离线请求门禁通过。字体专项运行 105 项，104 项通过，一项真实 Windows 启动验证按环境跳过。构建、两次安装及字节核对见证据根 `wheel-build.log`、`wheel-install.log`、`wheel-install-offline.log`、`offline-requests.json` 及 `receipt.json`。

## 主线排程的安装与首跑命令

以下使用 Windows Python 3.14，`$art` 指向复制后的上述证据目录。设置 `$venv` 与 `$unpack` 为新目录，`$swconst`、`$gbTemplate` 取已安装 SOLIDWORKS 2025 SP5 的注册 TLB 和 GB 模板，`$probeEvidence`、`$tableEvidence` 是两个彼此独立的新持久输出目录。

```powershell
$head = "9d0240cce88eaf656eeb66e15a220aad9da062b9"
$wheel = Join-Path $art "dist\swcli-0.2.4-py3-none-any.whl"
$package = Join-Path $art "source-package"
$sourceZip = Join-Path $package "font-scopes-next-source-9d0240cce88e.zip"
$manifest = Join-Path $package "manifest.json"
$expected = @{
    $wheel = "1124428e3e236efc7cc27fc9d9036d83389ab36131274f6f74fd3a86e713718a"
    $sourceZip = "0ecf80eb4233ea7efc088ad102f6b721e35a9d97482db4050d8c80e97b04d0db"
    $manifest = "9c33fe2c9e8b6bd27c622afc6b8354c6ce20003d434732eaddb67321462a4369"
}
foreach ($file in $expected.Keys) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash -ne $expected[$file]) {
        throw "Pinned artifact SHA-256 differs for $file"
    }
}
if ((Test-Path -LiteralPath $unpack) -or (Test-Path -LiteralPath $venv)) {
    throw "New source and venv directories are required"
}
Expand-Archive -LiteralPath $sourceZip -DestinationPath $unpack
$src = Join-Path $unpack "source"
py -3.14 -m venv $venv
if ($LASTEXITCODE -ne 0) { throw "Python 3.14 venv creation failed" }
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install $wheel
if ($LASTEXITCODE -ne 0) { throw "Pinned SWCLI wheel install failed" }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw "Python dependencies are incomplete" }

& $python -I (Join-Path $src "scripts\ci\prepare-font-scopes-next.py") verify --head $head --package-dir $package
if ($LASTEXITCODE -ne 0) { throw "Pinned source-package verification failed" }
& $python -I (Join-Path $src "scripts\ci\verify-font-scopes-next-offline.py") --source-head $head
if ($LASTEXITCODE -ne 0) { throw "Installed SWCLI code differs from the pinned source" }
$watchdog = Join-Path $src "scripts\ci\run-font-scopes-calibration.py"
& $python -I $watchdog --profile next-fixture --scope tables --source-head $head --output-dir $probeEvidence --swconst $swconst --drawing-template $gbTemplate --supervision-probe
if ($LASTEXITCODE -ne 0) { throw "Windows child identity probe failed. Preserve the original evidence." }
$probe = Get-Content -Raw (Join-Path $probeEvidence "watchdog.json") | ConvertFrom-Json
if (-not $probe.supervision_verified -or $probe.native_executed -ne $false) {
    throw "Missing no-COM supervision proof"
}

# Only in the coordinator's scheduled native window.
& $python -I $watchdog --profile next-fixture --scope tables --source-head $head --output-dir $tableEvidence --swconst $swconst --drawing-template $gbTemplate
if ($LASTEXITCODE -ne 0) { throw "Table fixture preparation failed. Preserve the original evidence." }
```

在已配置了依赖且专用于本路的 Windows venv，可改用 `& $python -m pip install --no-index --no-deps --force-reinstall $wheel`，之后仍跑 `pip check` 与源码字节核对。此包只包含 SWCLI 的平台无关 wheel，Windows `pywin32` 和其他依赖由目标环境或预置 wheelhouse 提供。

真实 Windows 探针尚待排程，后续表格 `Text2` 写入与只读重开的原生证据也待取得。首跑仅为表格夹具准备。尺寸继续按[手工清单](font-scopes-next-fixtures.md)准备。成功创建夹具后使用原计划的内部校准验证继承变化。
