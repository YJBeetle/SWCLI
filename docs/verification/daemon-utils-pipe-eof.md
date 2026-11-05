# 宿主启动器输出管道 EOF 回归证据

DockerSW push CI [42116004763](https://github.com/YJBeetle/DockerSW/actions/runs/42116004763)（882cc96409a6b0b9505bf1738c401379feb63815）原生步骤失败。宿主已经启动并运行属性/建模验证，但入口在启动预算 300+30 秒后报告 HostLauncherTimeout，容器退出后 docker exec 返回 137。这个退出码本身不能证明 OOM 或 Wine 原生 API 失败。

原因是外部 daemon utils 已退出，常驻 Wine 子进程仍继承 stdout/stderr。subprocess.run(capture_output=True) 等待管道 EOF，误把常驻子进程生命周期当成启动器生命周期。修复把两路输出写入私有临时文件，只等待启动器进程退出，再有界读取生命周期 JSON；保留原启动预算、未知结果保护、不重试和原生宿主生命周期。

## 独立验证

- POSIX 真实子进程回归：修复前启动等待后台子进程 10 秒退出；修复后启动返回时该子进程仍存活，再由测试私有 marker 正常结束。
- SSH workspaceroot 隔离 Podman / Wine 11.16 / Windows Python 3.11.9 最小复现，使用 daemon 相同的 detached 创建参数，未启动 SOLIDWORKS：PIPE 的 leader 0.816 秒退出，但调用到 4.060 秒才返回；文件 stdio 在 0.616 秒返回，后台子进程仍运行。临时容器已经正常退出并删除。
- 修复后源码完整单元测试：1600 项，21 skip，通过，32.569 秒。此处不是 SOLIDWORKS 完整功能验收。

## 原始证据 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| Docker 原始 job log | 323ecc83184662e139a1c5ecec4a37a36d668654d036a50e4a6b1b43536763b8 |
| Docker 原始 artifact 13458160476 ZIP | 644e5fbd235cfe57125946c2edcba7556d69df6810a2b1e33afe1021ddc59053 |
| SSH Wine probe-results.json | eccc915099d1f980764fde8ec8a97ad305d58ec100b9f0b53a9800f2bdb8e21d |
| 源码完整单元测试 log | 14a9098c172878d03e73943e81a1c13060197f3a553d03f4d1fced44266a48a3 |

MacSW / Linux Wine 实际 MCP 启停验收和后续完整 CI 结论单独记录，不能由这份最小复现推定通过。
