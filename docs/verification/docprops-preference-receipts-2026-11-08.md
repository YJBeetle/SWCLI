# 三组文档偏好：postflight / worker late-fault 回执修复

此为统筹本人source review指出的合并阻断修复。只改三个setter的描述符收尾及worker late-fault错误路径，不新增operation/request/result schema，不修改COM setter、固定reader、校准范围或600/1800预算。未合main、未重新派发native CI。最终source review/合并/发版由统筹执行。

## 行为

- `daemon/operations.py` 的三个set handler采用 `_with_preference_receipt`。描述符在副本中收尾，成功后更新并返回原adapter receipt对象，保留既有对象身份及native原值；失败返回ok=false，原mutation两bool和首个native/业务error保留。描述符错误单列在既有extensible `error.descriptor_error`，不虚构descriptor。
- `daemon/server.py` 每个请求开始将局部result置None；仅当同一请求已经返回匹配operation/action、恰好两个真正bool的mutation时，`_preserve_preference_receipt`才保留它。late worker错误单列 `error.worker_error`；有原error时不替换首个type/message。
- late validator发现无效postflight字段时，只保留最小合法failure action/error和已知两bool；没有可信receipt、action不符、int冒充bool、操作未执行时不生成修改事实。
- 原有NativeCommandRestoreFailed退休路径保持：返回错误、发host-disconnected、退出请求循环。未知恢复状态不继续接收CAD任务、不重试、不回滚。
- 传输envelope的error仍报告worker故障；业务result.error保留首native/业务错误及secondary详情。这与统筹main既有line/dimension语义一致，但未覆盖/合并main。

## 证据

`tests/test_document_preferences_worker_receipts.py`走真实adapter、handler、DocumentRegistry、execute_operation和_worker_main。恢复故障使用真实native_api_sequence，假宿主CommandInProgress还原抛错，非伪造返回receipt。

6项测试方法覆盖三组的36个子场景：

- 实际setter成功、或首native失败后，描述符收尾失败仍保留mutation和首错；
- 成功后恢复失败、首native失败后恢复失败；setter仅一次，worker退休；
- late validator失败，包括已知真实写入后的损坏descriptor最小回执降级；
- descriptor在clean no-op后失败仍是两bool false且零setter/dirty；
- 下一请求进入scope即失败，前一请求曾成功，第二响应仍无虚假result，不复用上一receipt；
- 不可信/缺失/错action/非bool mutation拒绝保留。

最终完整portable：2177 tests / 61.704s / OK (skipped32)，`evidence/docprops-performance/preference-worker-full-tests.log`。SDK生成、strict6文件及25消费者负向类型通过，`preference-worker-sdk-types.log`；专用注入日志 `preference-worker-receipt-tests.log`。git diff --check通过。

复跑（在本worktree、安装本source且有jsonschema的Python环境）：

```sh
PYTHONPATH=src /private/tmp/swcli-docprops-audit-env/bin/python -m unittest discover -s tests -p 'test_document_preferences_worker_receipts.py'
PYTHONPATH=src /private/tmp/swcli-docprops-audit-env/bin/python -m unittest discover -s tests
PYTHONPATH=src /private/tmp/swcli-docprops-audit-env/bin/python scripts/ci/verify-sdk-types.py
```

临时env若消失可按健康原件收据的venv命令重建，然后 `python -m pip install --editable . 'mypy>=1.15,<2'`。原件/测试产物均在持久工作树，不依赖该env保存证据。

## 与healthy native原件的区别

[全batch公开收据](docprops-batch-public-2026-11-08.md)绑定healthy代码 `b6d28f2a8f6fd549416ea5fac5aa12f538c9a9d6`、run42361904486、artifact13571626572、官方ZIP SHA256 `460d32d13b9953604c5f6ed1246258725895d7579817b53084413236e2501d30`。三组实际82写、142no-op、160拒绝、60save/RO和18SDK/MCP读已完成原件自验。

本次故障保护是其后的portable source修复；不能称已在SOLIDWORKS现场注入了描述符/worker恢复故障。按统筹指令不做无信息整套native重跑；最终合并候选tip将包含healthy证据及此异常路径修复，具体hash见WORK_HANDOFF交接与最终回复。
