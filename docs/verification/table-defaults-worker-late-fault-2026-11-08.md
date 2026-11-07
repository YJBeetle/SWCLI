# 表格 worker late-fault 回执保护

`document.table-option-set` 在 adapter 返回已知 mutation 后，仍可能遇到 `CommandInProgress` 恢复故障或 worker 最终结果校验失败。此次修复把该请求的已知修改边界保留在失败 envelope 的 `result` 内，供调用方和统筹判断实际已发生的修改。

## 最小变更

`src/swcli/daemon/server.py` 只增加表格专用 `_preserve_table_receipt`、每请求 `result=None` 和 except 内的调用。

- 仅接纳当前请求 operation 和 result.action 都为 `document.table-option-set` 的结果。
- mutation 必须恰有 `attempted`、`may_have_changed` 两个字段，且类型均严格为 bool。
- 已有第一业务错误保留 type/message，晚到的 worker 故障放入 `error.worker_error`。顶层 envelope 继续报告 worker 错误，因此恢复不明仍触发既有 worker 退休和 supervisor recovery。
- 使用现有 `validate_operation_result` 验证完整失败结果，包括 finite UTF-8 JSON。描述符或其他字段不可信时，只保留 ok/action、两 bool mutation 和错误。错误文本复用 `_safe_error_text`，使非法 UTF-16 代理项可见且可传输。
- 每次取到新请求都先清空 result，执行前失败不会借用上一请求的回执。

参考 main `00f4538` 的回执语义。表格 helper 独立命名，合并时保留 main 其他偏好 helper。main 若已有每请求 result reset，合并时保留一次即可。

## 便携故障注入

`tests/test_table_defaults_worker_receipts.py` 新用例执行真实 `_worker_main`、`execute_operation`、表格 handler、public table adapter、`native_api_sequence` 和结果校验器。COM/bootstrap 与 native runtime 证明使用明确的 fake，故障在真实 command-state setter 或最终描述符/校验阶段注入。

验证覆盖以下路径。

- 成功写入后真实 command-state restore 抛错，保留双 true mutation、before/options、native_returned 和已观察值。queued 第二请求未被取出，worker 退休。
- native setter 已改变 fake 状态后抛错或返回 false，随后 restore 失败，第一 native 错误保留，worker_error 记录恢复错误，setter 仍只有一次。
- 实际 handler 最终描述符损坏，真实 validator 报错，回执降级为可序列化的最小失败。
- 第一 native 错误后 late validator 损坏描述符，最小失败仍保留第一错误及次级 worker_error。
- clean no-op 在正常及 restore 失败时均为双 false，setter/dirty 为零。
- 第二请求在 entry/restore 或参数构造阶段失败，执行次数仍为一次，第二响应没有借用第一响应的 result。
- action、字段数量或 bool 类型不符合接纳条件的 receipt 不被转移。非 JSON 字段和非法 native 错误文本安全降级或可见转义。

相关 126 项测试通过。复跑命令如下。

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI
/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/.venv/bin/python -m unittest \
  tests.test_table_defaults_worker_receipts \
  tests.test_native_sequence tests.test_daemon tests.test_document_tables -v
```

原始本地日志 `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/worker-late-fault-related.log`。

## 验收关系

正常装配体/工程图公开 native 原件仍对应 `42366316568` / `5ab5afce5fb4f19b41beda2a3e5c0fb629919f9b`。本次异常路径按统筹要求以便携故障注入验证，作为独立提交交统筹本人 review。

零件 run `42405733149` 继续使用原 head `6396034fe941b28d90ced2b941ae0d6c26907be9`，本次提交保持其历史不变。零件严格几何问题仍为系列待完成项。
