# 42865595677：身份准入首错、缺失观测与最小诊断修复

本run [42865595677](https://github.com/YJBeetle/SWCLI/actions/runs/42865595677) / head `085ae73570f023706319738d1130fd21256e4144` 保持 **failure**。两Windows portable、SDK/轮包/route前置成功，公共native job首失败于wrapper `capture_early -> owned_native.capture -> validate_identity`：`native full image differs from this CI installation`。不是CLI helper的expected Python路径校验，不是1800秒预算或native setter失败。

## 原件与实际覆盖

官方native artifact `13790060166`，10930120 bytes；下载与官方ZIP SHA256均为 `207a75330e6bb35b368f2d5ba054ec908bfa661205e068c3c8f275a32d246c75`。官方install-log artifact `13789251418`，3215896 bytes；SHA256 `2a52d351cc9f74cbc4be2e94a761a591748f3dceedbe6981c6a72f6f2b0f4cec`。各下载一次并核digest；统筹原失败日志直接复制，SHA256 `38c14c1bdb3cc942bbf702b71231bb205afc0833816be7d3e9d9a02ae2d101be`，不重复下载/状态poll。

原件绝对目录 `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-stdio-42865595677/`：`original-native.zip`、`original-install-logs.zip`、安全解压 `original/` 与 `install-logs/`、`failed.original.log`。官方terminal metadata/审计在同名 `docs/evidence/`；原initial snapshot/dispatch/旧473b失败不修改。

| 范围 | 本run真实到达 |
| --- | --- |
| 内部private | 46/46/47共139步骤，259.579秒，正常owned退出 |
| 公共CLI | 1个case开始，0/139完整；source-open请求在途 |
| 公共SDK/MCP | 0/139、0/139，未到达 |
| 额外独立cold probes | 0/3，未到达 |

独立标准库审计核内部139的完整9/raw5/linkage19后态与readonly持久化、278份source/target原生文件hash、92次part几何比较（67次保留nonexact raw/delta/hex；V/S/body严格，质心仅原批准逐轴绝对≤1e-12mm）。内部证据独立，不补公共registry/lease/417缺口。

公共raw journal只有status/list完成及source-open请求started；82条public native trace、单worker6536、setter0/error0，source-open operation在native侧结束1078ms，但frontend回复未持久记录，不能算完成。语义报告停在CLI1 source-preflight，没有read/write/noop。CLI list的原B64字节/CRLF/text/result相等，真实隔离stderr codec=cp1252，和成功Windows portable共同证明上次stdio修复已越过前置，但不是公共417通过。

wrapper持续5.813秒，full-image准入失败前未留下实际返回image/len/size/creation。候选handle未成功移交；单次daemon stop被ActiveDocument拒绝，daemon随后终止，native/helper退出未确认、pids_after缺失，没有对未知native强制终止。helper回复pipe的OSError22是父进程终止路径下的次生错误，不替代先发生的wrapper首错。

## 不能把未观测的路径差异判成安装错误或截断

本run原MSI `INSTALLDIR`、LocalServer32路径值和安装脚本的COM注册核实记录与失败head的expected常量归一化后相符，见 `installation-path-evidence.json`。所以目前不认定安装路径错误；也不能在actual returned image缺失时认定短路径、别名、设备前缀或字符串截断。缺的是第一差异原值，不靠basename或允许未知别名绕过。

现有 `QueryFullProcessImageNameW` 声明为HANDLE/DWORD/LPWSTR/PDWORD、BOOL返回，WinDLL调用、flags=0、32768字符buffer。[Microsoft原定义](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)规定size输入是字符容量，成功输出是不含NUL的字符数；[ctypes](https://docs.python.org/3.12/library/ctypes.html)的unicode buffer使用平台wchar。代码表面没有足以认定的ABI错误，但macOS mock（wchar宽度不同）不构成Windows实际调用证明。底层差异仍未定案。

## 已批准的最小观测修复，准入策略不变

只改单位identity helper/wrapper及其测试：

- `process_identity`保持原四个稳定字段pid/image/creation_utc/creation_timestamp。可选独立diagnostic记录Query API/flags/声明类型/实际宽度、input capacity、returned chars、原image/repr、Python字符与UTF16单元长度、返回位置NUL、原wchar buffer有界base64与字节序。最多32768 wchar，不读越界内存、不记录其他命令行。
- `capture`在原PID/image/creation谓词执行前，先由wrapper把requested PID、observed完整identity、expected原值/repr及比较输入flush/fsync。回调只收到deepcopy的JSON数据，没有可kill handle，也不能修改稳定identity使其他镜像获准。失败仍关闭候选句柄，不返回可终止引用、不重新OpenProcess找替代PID。
- 观测写入失败在validation之前停止；API/校验首错不被观测/关句柄次错替换，wrapper保存`identity_capture_failure`及原始观测。normalization/完整路径/PID/时间窗、同一已持有handle重核及终止逻辑完全不改。AST验证validate_identity/terminate/exited/EXPECTED_CI_IMAGE与失败head相同。
- 新Windows-only portable test只读当前Python进程，独立用GetModuleFileNameW对照真实image、核自身PID、DWORD/BOOL/wchar宽度及返回size/NUL，原始观测在任何断言前/异常finally中输出。sys.executable和sys._base_executable仅记录，不用venv入口/launchPID冒充实际进程image，也不借自身Python合法差异放宽native SLDWORKS准入。没有CAD、别PID或VM操作。

本补丁修的是**首差异观测丢失**，不是已解决底层路径差异。expected仍是原策略，路径修法及可信安装/注册receipt绑定方式等待真实observed数据再由统筹选择；没有native dispatch授权，不派新的private/public CAD运行。

## 验证和下一步

关联97项/25.036秒通过（Windows真实自身API探针1项在macOS跳过）；完整1973项/78.009秒通过（27skipped）；SDK generator、strict6文件及8 consumer拒绝通过；三文件Python3.9 AST/diff检查通过。覆盖校验前持久化顺序、持久化失败在predicate前停止、验证/close同时失败首错保留、回调不能篡改identity或获得handle、wrapper保存raw/error、稳定与诊断字段分离。最终源码/原日志SHA在 `identity-observer-validation.json`。

统筹已批准该最小观察范围和轻量Windows自身进程测试；中文提交后给出精确diff/head并push轻量Windows检查。Windows实际API观察仍待这次轻量结果，本机mock不替代。不会自动派native，417/三cold probe/原合法域/geometry/600-1800均不变；VM/main/release未动。

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
python3 docs/verification/audit-units-image-failure-42865595677.py --metadata-dir docs/evidence/units-profile/public-stdio-42865595677 --raw-dir evidence/units-profile/public-stdio-42865595677
PYTHONPATH=src:tests /private/tmp/swcli-units-write-env/bin/python -m unittest tests.test_unit_profile_public_runner -q
```
