# 单位公共 wrapper：同步身份预检实现，待 root 亲审

统筹亲审 42902927609 的原件和提案后批准最小实现。本次业务只改 `scripts/ci/run-unit-profile-public.py` 与 `tests/test_unit_profile_public_runner.py`；`unit_owned_native.py`、产品 src、workflow、公共 WriteGate/CLI/SDK/MCP transport、候选域和几何规则均不改。旧 42865595677 仍失败、actual SW image 未知，不能凭 Python 自身映像测试通过认定底层差异已消失。

## 最终行为

仅 write-acceptance 增强路径在自有 daemon readiness 后、任何 public worker Popen 前，同步一次真正 `python -I -m swcli --endpoint ... --request-timeout 600 daemon status --json`。状态命令不创建/打开 CAD 文档；预检命令先落盘，原 stdout/stderr 分别写入 `identity-preflight.stdout` / `.stderr` 并 flush/fsync，returncode 保存 host-report，解析后的完整 JSON 再 durable 保存，然后才检查状态/原所有权并调用原 capture。坏 JSON 也保原 bytes；超时保 partial bytes、returncode=null/outcome_unknown，若证据落盘再失败也保最初 TimeoutExpired。

沿用 host_connected=true / recovery_required=false，及原整数正 PID、不在 prior inventory、owned_by_daemon=true、visible=false、shared_interactive=false。e2f capture 先 fsync 原 image/PID/creation/expected/Query/raw buffer 再执行原 exact path/PID/creation 谓词。capture 没成功或任一必要落盘失败，public worker 不启动，因此没有 public document.open/setter；不重试 status、不重开 native PID、不换宿主。

成功保留同一个 verified handle。原先一次 capture 后提前 return 的函数改为独立 `verify_public_host`：每次 public report 可读且带 host 时核原 owner 条件与保留 identity 的 PID，终局必须有可读带 host 的报告；不能因为 preflight 已捕获就跳过。初次匹配标记 `public_host_matches_preflight` 只是记录，不缓存后续核对结果；已经匹配后再出现 PID/owner 漂移仍拒绝，不打开另一个句柄。

预检从原 started 计时，CLI 参数请求值 requested_cli_timeout_seconds=600；当前产品 `swcli.daemon.main.run` 的不带 `--details` status 分支实际调用 `call_daemon("daemon.health", timeout_seconds=10.0, connect_timeout_seconds=1.0)`，不转发 CLI 的 args.request_timeout，因此 effective_health_rpc_timeout_seconds=10、effective_health_connect_timeout_seconds=1；来源契约保存在 health_rpc_timeout_contract。原生操作600秒预算不变。status 子进程总等待上限 min(600, 原1800剩余时间)，结束后及 capture 后、public Popen 前再检查整组预算，没有重置或额外组。原 public 139x3、三额外 cold probe、lease/CAS/完整状态/原生文件持久化、质心窄容差及其他几何规则均不动。

收尾策略保持原样：至多一次正常 stop；未验证 native handle 不终止、不重开；已验证同 handle 的应急终止仍保持原重核和失败不翻绿；公共宿主不匹配时绝不终止新发现的 PID。预检失败可以避免由本 public worker 开文档后造成的 ActiveDocument，但不保证 stop 必成功或无 verified handle 时 native 退出可确认；原首错/stop/daemon/native/helper退出边界都保留。

## 验证范围

runner 41项/0.125秒通过，Windows 当前进程 API 1项在 macOS 跳过。新增15项测试覆盖原件 fsync/JSON fsync/identity fsync -> public Popen 顺序、三处落盘失败、坏 JSON/失败回执原 bytes、失联/恢复、status partial timeout、timeout与落盘同时失败保首错、剩余预算及捕获耗时、public PID/owner 漂移、先匹配后漂移、最终 ownership report 缺失、identity失败同时stop失败；失败时零public Popen、一次stop、未验证不 terminate、不补开handle。

关联85项/26.421秒通过（1 skip），SDK generator/strict6文件/8 consumer拒绝通过。完整 portable 1988项/79.958秒通过（27 skip），最终源码/日志 hash 见 `docs/evidence/units-profile/identity-observer-push-42902927609/synchronous-preflight-validation.json`。两改动 Python 文件 Python3.9 AST/diff 通过；原 helper 整文件逐字等于 e2f，validate_identity/terminate/exited/EXPECTED_CI_IMAGE AST 与085ae及e2f相等，原 ownership predicate表达式 AST 相等。42902927609 独立原件审计复跑相等，不做新CI结果查询。

原件和本地日志在 `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/identity-observer-push-42902927609/`。先前纯docs审计已独立提交推送 `3a38693`；本同步实现只做本地中文提交供root审阅，未push实现、未新dispatch/native/VM。真实 Windows/SOLIDWORKS同步预检尚未运行，路径准入首差异仍待取证。root另行明确授权后才可启动新的原生运行。


## c6004a5 后的最小取证语义补正

root指出旧 report 的 request_timeout_seconds=600 容易被误读为实际 health RPC 等待；原文“CLI请求仍600”不准确。补正仅 wrapper 报告字段、关联测试和文档，不修改产品 CLI 或任何实际超时。现分别保存 requested_cli_timeout_seconds=600、effective_health_rpc_timeout_seconds=10、effective_health_connect_timeout_seconds=1 与来源契约；process_timeout_seconds=min(600,原1800剩余)保持不变。新增 portable proof 使用 wrapper 实际 command 进入真实 swcli.cli.main -> swcli.daemon.main.run，仅 mock 最终 call_daemon，确认一次 daemon.health 调用实际10/1，完整 JSON 原样输出；不以模拟 subprocess stdout 冒充路由证明。关联 runner+CLI 共78项/1.668秒通过（1 Windows skip），2文件Python3.9 AST/diff通过；wrapper完整AST除报告metadata dict外与c600相等，实际执行/超时/守护均无变化。最终验证和新源码SHA见 timeout-semantics-correction-validation.json，原 c600 完整测试结果保留为历史证据。本次仍未push实现/dispatch/native/VM。
