# GLB 零 CAD 采集器 Windows 单测夹具修复（2026-11-13）

只改测试夹具，生产 collector 与失败 CI 的7d6858e **逐字相同**，SHA `be754a8ac64eaf56164bc3ecb45939d2401511ad337422f74692e373793c2cc8`。未放宽未知运行时、身份或时间保护，也未改冻结的 probe02/03。没有 VM/CAD 操作。

## 原失败

原 push CI [43332197803](https://github.com/YJBeetle/SWCLI/actions/runs/43332197803) 的 Windows3.9/3.14 单测失败；wheel成功、native SKIP。root已核原summary ZIP摘要，原失败日志 SHA `085927e40acfb935ffea927a8b61b50db8c25431b7dc45233404976f306cbc6a`。

两边的首个夹具错误是在第二次 fstat 回调内对仍被 os.open 持有的源文件做 replace，触发 WinError5，未到达原本要测试的最终 path identity gate。[Microsoft CreateFile 文档](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) 说明删除/重命名受共享模式约束。本修复不改采集器打开方式，也不引入允许删除共享的新 Win32 I/O 后端。

3.14 job 实际解释器为3.14.10；另有 request_before stat/open 拒绝，导致 mutation 测试还没到 runner 就停、预期错误字符串和 postcheck_error 断言不成立。原日志没有该次完整 raw 差异，不能把它补述成已观测的唯一 ctime 差异。[Python 官方 stat 文档](https://docs.python.org/3.14/library/os.html#os.stat_result) 也没有保证所有 Windows patch 的 stat/fstat 完全等价；现有例外只针对已有实际3.14.7证据，仍不扩大到3.14.10。

## 最小测试修复

- 集成场景显式声明 `runtime_identity` 为已有已审3.14.7夹具契约；保留每次真实 stat/fstat 的所有值，不改原始文件时间。该 mock 的 version 明写 portable fixture only，不能当成CI实际运行时或native证据。未知patch拒绝用单独负例明确覆盖3.14.10。
- 同字节替换场景先创建一个真实独立文件，验证不是 samefile；仅把最终 path stat 观察指向该文件。源 descriptor 和两个 held fstat 全程真实，不尝试替换仍打开的源文件。必须在 after_path_check 拒绝，并验证原/新文件身份原值、descriptor closed，且没有成功 hash。
- 补生成 metadata request/response 的合成 Windows 双 ctime 场景，验证 raw path/held 前后时间都保留，原全窗口请求比较仍严格。它只验证已审规则的执行，不证明其他 Windows 版本可接受。

没有删断言、扩大 raises、吞掉 WinError5、修改 production collector、去除 ctime/身份字段或修改原例外版本名单。原字节/替换/文件出现、helper首错、whole-window held time变化和全部拒绝用例继续通过。

本机 macOS CPython3.15.2 上该模块 **25 项通过**；`git diff --check` 通过。此证据快照没有新Windows CI结果。后续按统筹要求仅作一次相关分支 push，自动轻量CI需另核真实 head、两Windows job及原summary；不派 native、不将portable单测通过当CAD验收。
