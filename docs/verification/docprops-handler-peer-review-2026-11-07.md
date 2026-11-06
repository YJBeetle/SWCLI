# 跨分路mutation回执与前台文档保护窄审查

范围：线型、尺寸显示、表格默认、单位扩展、图像品质/GLB五路优先检查；公差/字体由原owner修复，不重复指派。detailing main已有handler partial保护，不将旧分支模式外推到main。只读其他worktree，从下表精确提交导出隔离源码运行mock；没有COM/Windows VM/CAD、没有改他人代码或dispatch。

这里的“confirmed”仅指可重现的便携故障注入：真实源码handler/adapter配合Mock COM。不是原生现场错误或新能力验收。原件、脚本和源文件hash位于 `artifacts/docprops-coverage-ci/handler-peer-review/`；`results.json`保存每个输入/输出和相关既有测试名。

## P1：五路handler在setter返回后描述符失败时丢失mutation（mock实证）

调用链：`execute_operation -> registry选择/lease/stamp -> 对应setter handler -> adapter返回成功/partial receipt -> _with_document -> documents.describe`。本探针只对adapter返回与describe失败注入，不绕过生产allowlist或宣称实际native setter运行。真实handler收到 `mutation={attempted:true,may_have_changed:true}` 后，describe抛RuntimeError，handler直接抛出，没有返回原result。随后worker外层generic exception分支创建错误响应，不携带该result（这部分是源码核对，未运行worker）。

| 分路 / 精确head | handler（src/swcli/daemon/operations.py） | _with_document / worker错误分支 | 结果 |
| --- | --- | --- | --- |
| docprops-line-style / `bc619f372f9863c9654080e3a0492d994a3898e0` | `document_line_font_set` 第440–444行 | helper第126行；server.py第404行 | adapter调用1次、describe调用1次；异常传播，无mutation result |
| docprops-dimension-format / `441b45dc499de52f437a3e46ada3e62ab1694493` | `document_dimension_format_set` 第459–463行 | helper第126行；server.py第404行 | adapter调用1次、describe调用1次；异常传播，无mutation result |
| docprops-table-defaults / `b4f79111dce508ac6947b1b19bdc80e2e315cd73` | `document_table_option_set` 第440–444行 | helper第126行；server.py第404行 | adapter调用1次、describe调用1次；异常传播，无mutation result |
| docprops-units-expanded / `9d6b033a221082a515fc75bea3c53360df5a78cb` | `document_unit_profile_set` 第459–464行 | helper第126行；server.py第404行 | adapter调用1次、describe调用1次；异常传播，无mutation result |
| docprops-export-options / `0f4ba7b3d629993731966bfc0a31275d7010fc83` | `document_image_quality_set` 第442–446行 | helper第128行；server.py第404行 | adapter调用1次、describe调用1次；异常传播，无mutation result |

建议由各owner复用main detailing已存在的收尾模式：adapter原result为唯一mutation事实；在描述符/注册收尾失败时保留它，设ok=false并附加收尾失败详情，不覆盖首次native错误、不补偿写入、不重试。新增测试须覆盖成功/partial adapter结果后describe抛错，经过handler/worker仍有mutation；只测adapter自己的异常捕获不足。

## P1：四路仅保护ActiveDoc指针，遗漏同一个前台文档自身变化（adapter/handler mock实证）

在每次独立fixture里，保持app.ActiveDoc为同一对象，包装已有Mock原生setter：先完成原setter，再分别改peer的GetUpdateStamp、GetSaveFlag、GetTitle、GetPathName。四路20个探针中的16个返回ok=true，前台peer值确实改变；表格的4个返回ok=false且mutation保留。

| 分路 / head | 目标guard位置 | stamp/dirty/title/path注入结果 | 既有测试覆盖及缺口 |
| --- | --- | --- | --- |
| docprops-line-style / `bc619f372f` | `src/swcli/hosts/windows_document_line_font.py:83` | 4/4返回ok=true，peer drift未被拒绝（confirmed mock） | test_document_line_font.py:116测目标未请求字段/dirty失败，148测目标drawing上下文；未覆盖同指针peer自身变化或post-adapter describe故障。 |
| docprops-dimension-format / `441b45dc49` | `src/swcli/hosts/windows_dimension_format.py:59` | 4/4返回ok=true，peer drift未被拒绝（confirmed mock） | test_dimension_format.py:103/114/162测native失败、目标关联字段/dirty；255测目标dirty清除；未覆盖peer自身变化及handler收尾失败。 |
| docprops-table-defaults / `b4f79111dc` | `src/swcli/hosts/windows_document_tables.py:69` | 4/4返回ok=false，捕获peer drift（未发现该缺陷） | test_document_tables.py:178已有foreground指针和foreground_modified子场景；本次四种peer变化均被拒绝。post-adapter describe仍缺。 |
| docprops-units-expanded / `9d6b033a22` | `src/swcli/hosts/windows_document_unit_profile.py:31` | 4/4返回ok=true，peer drift未被拒绝（confirmed mock） | test_document_unit_profile.py:47只核ActiveDoc同指针，120测setter失败，148测目标linkage；未覆盖peer自身值变化及handler收尾失败。 |
| docprops-export-options / `0f4ba7b3d6` | `src/swcli/hosts/windows_document_image_quality.py:60` | 4/4返回ok=true，peer drift未被拒绝（confirmed mock） | test_document_image_quality.py:170/193/237测目标context/configuration/path/dirty；274测SDK partial传递；未覆盖peer自身值变化及post-adapter describe。 |

根因定位：四路在捕获时仅保存foreground对象，后续 `_verify_metadata_state(app,target,target_state,foreground,...)` 比较target状态和ActiveDoc身份；目标的path/title保护不代表另一个peer的身份保护。表格 `windows_document_tables.py:67–91` 已保存并校验foreground_state与foreground_identity，且只在foreground不同于target时使用严格不变检查，可供owner参考。

本探针没有核peer配置、只读/access、关闭重开/句柄替换的所有变化，因此不能因表格这4例通过宣称其完整前台保护已验收。

## 其他分路的边界检查（static-only）

- STL `d8df4a874cc0c8460cf8615964420e7e9c20ff7b` 与STEP `2c7108fa5c6c22ebfc9a6c98bdb0a9f67acac58f`：document_export在operations.py:619附近直接返回adapter结果，不调用_with_document；未发现“描述符收尾”这个同形点。没有对此轮global preference恢复或peer保护做完整mock证明，不能据此标安全。
- 配合 `8a7095cee900ec5023e58c20561f292ced52863f`：assembly_add_mate在operations.py:232直接返回adapter；没有同形_with_document收尾。写入guard要求target就是ActiveDoc，另一个前台文档场景不直接适用；其余配置/引用件保护未在本轮代验。
- 旋转 `3922bee798b0b5b33dc6aa7a4bf34b01dc0e79ad`：feature_revolve在operations.py:1231有register_feature异常保留result路径；不调用_with_document。adapter要求exact target active。这里只static检查，不宣称其所有retire_scope/partial路径都无缺陷。

## 可复现方式与证据

从对应仓库用git archive导出表内精确SHA的src/swcli与tests到本路临时隔离目录，设置PYTHONDONTWRITEBYTECODE=1、PYTHONPATH=<snapshot>/src:<snapshot>/tests，再以本路venv运行 `repro.py <分路名>`。脚本和stdout/stderr/result JSON永久保存在本worktree，结论不依赖临时目录。测试fixture的校准开关/白名单patch仅在独立进程中模拟候选adapter，不修改任何生产文件或公开请求。

本轮不改其他分支、不开启写白名单、不重跑CAD；发现项交主对话协调各owner修复，再按修复的精确head独立复核。
