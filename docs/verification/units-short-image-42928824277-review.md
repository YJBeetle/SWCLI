# 42928824277：同步预检首次留下实际短路径，公共进程未启动

[run 42928824277](https://github.com/YJBeetle/SWCLI/actions/runs/42928824277)，head `95a2edccd26dfa274e0f66468248838d71cf7e53`，attempt1，保持 **failure**。官方 terminal run/jobs/artifacts 各取一次；仅下载本 run native/install 两 ZIP 与原 native job 日志，不重查旧 CI、不重派。

native artifact13816502372，10937528 bytes，官方与下载 SHA256 `90fb3eb856a671a1cc5c98f56e3fc219d76208203d35a7934e14428cdaa4681b`；install artifact13816611572，3211059 bytes，SHA256 `76e85630997b8241e150d55ad7691803b800bc570fdac9e088b52c630e30643a`。原 native job130224083602 日志本地 SHA256 `8143e35f82298445213f362c7815632e16719e0d28935f4ec48d5dc1546f8bd3`，日志 API 无同名官方 digest，不混称。Windows3.9/3.14、wheel、route成功，native首失败步骤仍 Verify public document unit profile CLI。

## 原始首错

wrapper 4.891秒在同步 native-host 身份预检拒绝，首错仍 `native full image differs from this CI installation`。本次在 public worker Popen 前，原 JSON/Query/full expected/比较值均已持久化：

- actual `C:\PROGRA~1\SOLIDW~1\SLDWORKS.exe`，returned/Python chars/UTF16 units均33；Query success=true、last_error=null，capacity32768、flags0、HANDLE/DWORD/BOOL/wchar=8/4/4/2、little、返回位置NUL=true。
- 原 buffer B64 独立解码正好是完整 actual UTF16LE 加 NUL，不是字符串截断。expected 仍 `C:\Program Files\SOLIDWORKS\SLDWORKS.exe`；原 normcase/normpath 后两字符串不同，拒绝符合现有谓词。
- requested/observed/status PID均9980；creation1794357069.533位于launch1794357068.286687与observed1794357072.496984之间。仅确认这些原值满足窗口，原校验先因image失败，不能说creation谓词已执行。
- 原MSI `INSTALLDIR` 与expected长路径相符，MSI SHA256 `418bed1f830a46b42cc53a587ce668b769a4f62f8327c27ce067dd848789bc26`。本ZIP没有 GetLongPathName 或文件同一性证明；不能凭8.3外形断言 raw 与 expected 已证明同一文件。

## 覆盖及清理

public_command不存在，public stdout/stderr及cli目录不存在：公共worker未启动，CLI/SDK/MCP完整各0/139，额外fresh probes0/3，公共CAD trace/setter均0。不能把同步status或内部139算作公共覆盖。

正常stop一次，exit0/原JSON stopping=true，没有ActiveDocument，没有未知native强杀。cleanup记录到了 daemon.wait 成功之后的“owned native process handle unavailable”分支，说明 Python daemon wait返回0；这是代码路径与原错误的推断，不另造不存在的显式退出字段。候选native句柄准入失败后关闭，没有verified handle、native wait证明或pids_after，故native退出仍未确认；helper未启动。首错保持，stop成功不能翻绿。

独立内部139步骤（46/46/47）成功258.437秒，owned退出确认、before/after空、cleanup空；独立核278份原生source/target文件hash、92次part几何（67 nonexact保原raw/delta/hex与逐轴1e-12mm窄容差），完整后态/readonly profiles通过。与公共0严格分开。

原件绝对目录 `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-sync-preflight-42928824277/`，含 original-native.zip / original-install-logs.zip / native.original.log 和安全解压目录。terminal metadata与独立结果在同名 docs/evidence 的 preflight-failure-audit.json。标准库审计 `docs/verification/audit-units-sync-preflight-failure-42928824277.py` 只复用既有纯证据校验，不import产品/gate/COM。

## 获批准备的最小候选，尚无新的Windows/native证明

root批准准备并本地测试严格路径身份候选，提交供亲审，未授权新的native派发。候选必须以 Windows [GetLongPathNameW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getlongpathnamew) 一次展开 raw Query path，核返回长度/NUL/有界buffer，失败即拒绝；其成功也可能仍返回输入，不能只凭 API success 放行。展开后的**完整路径**必须满足原expected完整比较，另以 [os.path.samefile](https://docs.python.org/3/library/os.path.html#os.path.samefile) 和记录的stat device/inode证明 raw/expected 同一文件，失败/访问拒绝/不同文件都拒绝。

原raw identity仍四字段、同一保留process handle不换；候选只为准入形成明确标注的expanded image副本，原PID/creation窗口与同handle终止重核不变。raw/展开/API及stat/比较/异常须先fsync；不字符串替换、不basename/别名白名单、不盲realpath或兜底。下一步实现和Windows-only真实短长同文件probe仍待代码测试及root精确亲审，不在本失败run上补造证明。600/1800、417+3cold、域/几何/src/workflow均不变，VM/main/release未动。

## 已实现的候选，待 root 精确亲审

业务只改 CI `unit_owned_native.py`，原 runner 身份 mock 适配4行，并新增专门路径身份测试。wrapper、产品、workflow、公共WriteGate/CLI策略均无diff。

新 `image_path_identity` 一次 `GetLongPathNameW(raw, buffer32768, capacity)`，明确 LPCWSTR/LPWSTR/DWORD、DWORD返回，记录实际wchar宽度、返回字符数、完整展开值/repr、UTF16长度/NUL和有界原buffer。返回0、所需容量>=32768、长度/NUL不符均失败，不扩容重试。即使成功返回原短字符串也不会获准。`os.stat(raw)` / `os.stat(expected)` 的device/inode及一次 `os.path.samefile(raw, expected)` 结果均保存；除了samefile=true，还要求记录的文件标识相同且inode可用，不能用0或缺失标识补足证明。missing/denied/IO/API异常保原类型/errno/winerror，在候选句柄关闭前交原observer持久化；观测写入次错不覆盖首错。

路径收集不直接授权。capture先把原Query四字段、展开/API/stat/同文件判断、展开完整路径比较、明确标注的admission_identity副本，deepcopy给原observer fsync，再运行原 validate_identity 对副本检查完整expected/PID/creation窗口，且要求上述同文件证据全部为真。返回/持有的identity仍是**原raw Query四字段**，不会把短字符串悄悄改成长字符串。终止时 `process_identity(handle)==identity` 仍重核原raw四字段，同一handle，不重新开PID、不重新找替代、不接受另一representation。原 process_identity 与95a AST相同，原validate_identity/terminate/exited/expected常量与95a及085ae相同；改变的是经OS证明后的准入副本image，不宣称仍在做原raw字符串相等。

成功报告规则：`observed_identity.image` 及 wrapper返回的 `owned_native_identity.image` 保持raw；`admission_identity.image` 是OS展开，`identity_image_representation`/path representation明确两者，`expanded_matches_expected`及samefile/device+inode先落盘；observer的phase=persisting是校验前快照，wrapper仅在capture真正返回后记录持有identity。失败仍无verified handle，不强杀未知native；normal stop成功也不翻绿此前失败或未确认退出。

正反测试覆盖长短输入、完整展开+相同fileID、原串返回、wrong dir/错exe、不同inode/volume、samefile与记录标识矛盾/不可用、missing/denied/API/IO异常、单次大buffer/坏长度/NUL、>260字符原值、PID/旧或未来时间拒绝、落盘失败先停、回调不能伪造展开或samefile、终止重核raw且不重开handle。新增Windows-only真实探针在自己创建的临时文件上用真实GetShortPathNameW/GetLongPathNameW/stat/samefile核短长路径，记录finally原观测；若卷不提供不同短名明确skip，不冒充短名通过。另有真实Windows不同文件/缺失文件负向探针。没有CAD、其他PID、VM或文件替换。

最终关联105项/24.938秒（3 skip）、完整2008项/74.141秒（29 skip）、SDK生成/strict6/consumer8、3文件Python3.9 AST/diff均通过；源码/原日志SHA在 `docs/evidence/units-profile/public-sync-preflight-42928824277/short-path-candidate-validation.json`。Windows-only两项在本地macOS跳过，不能把mock中wchar4或本地stat当作Windows短长同文件的真实证明。本run原ZIP里仍没有同文件证明；候选尚无新的Windows/native执行结果，提交给root后等待亲审，不自动push/dispatch。
