# 811bb97 显式空参数候选：包装检查首错，零导入

独立原件审计通过；此次实际运行在本地绑定白名单检查处失败，**没有调用LoadFile4，也没有几何测量**。首错为 `NULL binding refused: unsupported wrapper class; do not replace it`，原件实际wrapper_type为 `win32com.client.CDispatch`。它不是SOLIDWORKS导入结果，也不是已测得的null参数转换错误。

## 原件与完整源码

原件目录为 `/Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/wire-once-811bb97-01`。report SHA256 `297e635248a9473ee3f27fb6c29d0f87ec1ab36c3033275c2a27ea67067ce352`；source ZIP SHA256 `a6bf3df44e81cf057d58b10f2205e9cce96838c20ed8134d51d16c158300e80e`。这次归档的424文件集合及全部字节与提交 `811bb976a614cd9cda2660fe096b5fcc8ca8f197` 完全一致，是完整提交文件归档（不含.git），不是之前184文件runtime子集。七个实际关键加载代码hash均与归档相同。

七份原件原样复制到ignored `step-evidence/wire-original-811bb97-01`。[机器审计](evidence/step-null-811bb97-audit.json)保存逐文件SHA、实际返回状态和调用次数。[只读审计脚本](../scripts/ci/audit-step-null-811bb97.py)可复跑，不使用统筹摘要代替原件判断。

## 原生范围与恢复

- 隐藏owned PID7952 / revision33.5.0，Python3.14.7 / pywin32312。GetImportFileData/单STEP QI/只读Map各1；QItrue、Mapfalse，factory仅观察。
- b312三个Python源文件hash及四个dynamic处理函数的原运行时校验已通过，原null-binding-package.json与report完全相同。本审计核原记录和实现/hash，不声称在本轮重新执行了VM内字节码校验。
- null_binding.status=unknown，bound_method_invocation_attempted=false；load_return仍not-attempted，document_returned/errors均null。没有route、resolved_signature或actual_argument证据，不补造空VARTYPE/指针；geometry只有unavailable/value=null，没有raw几何，不记作零段/零长度。
- 主trace362行=181次配对，唯一error为verify-original-LoadFile4-binding；observation14行=7次配对全完成。LoadFile4、CloseDoc、GetSketchSegments、GetLength及read-imported均0；无Open/New/Save/Export/Select/重试、基线重放或host替换。未建立模型，故无CloseDoc需要。
- 五项owned setter及完整读回、反序恢复全部verified。154条读记录、18个完整向量阶段全observed，changed_from_60f1cf8=[]，最终原八值完全恢复，restore_errors=[]。
- 固定原件10595bytes/SHA3a4f0326...及preflight/case/report/final文件ID、大小、创建/修改时间、attributes33和路径完全相同，独立复核保留的输入原字节。未读取VM当前文件状态。
- ExitApp/WaitForOwnedProcess/CloseProcessHandle/CoUninitialize各1按序完成，cleanup_errors=[]，启动前/退出后native清单均空；无timeout或部分激活错误。嵌套observation ExitApp是同一次退出，不重复计数。

## 实际获取链源码复核

归档内 `diagnose-step-wire-import-once.py` 使用 `win32com.client`，其CheckedClient只转发一次DispatchEx；原owned harness导入 `swcli.daemon.server.acquire_resident_app`，该函数在已核ROT不存在后调用com_client.DispatchEx并配置同一个app，不替换包装。完整归档中的源字节已核。

原运行中实际安装client/__init__.py hash为 `a0fa92dcf3bd6cb6ce8bba38c6bee95b12b95a325852b1dbeb559464d431b36a`，与核对的[官方b312源码](https://github.com/mhammond/pywin32/blob/b312/com/win32com/client/__init__.py)一致。该源码链为DispatchEx→CoCreateInstanceEx→Dispatch→__WrapDispatch；已有生成类可被返回，否则WrapperClass默认是**client.CDispatch**并传给dynamic.Dispatch。原件的精确类型符合这条正常客户端包装链；旧记录没有保存gencache返回值，不能补写它已观察为None。

client.CDispatch明确继承dynamic.CDispatch，类中仅覆盖返回对象包装策略 `_wrap_dispatch_` 和 `__dir__`，没有另定义LoadFile4、__getattr__、_LazyAddAttr_、_make_method_或_ApplyTypes_。因此旧gate“精确类型必须是dynamic.CDispatch”排除了一个本来就在标准获取链上的原包装；这是诊断准入范围缺口，**不是已证明的CAD问题或导入修复**。

后续只允许准备对这一个原client.CDispatch的精确支持：核对源码/运行时代码、精确单继承和绑定处理函数继承身份，保留其返回对象包装策略，不改成泛化isinstance放行、不把已有app重包成dynamic。未知或generated/custom类仍零Load拒绝；未知签名/转换、r、八项向量、严格reference12/320、owned恢复和600/1800均不变。实际Load绑定分支仍未被本次读到，不能借继承关系回填成已测的Invoke/InvokeTypes。

## 复跑审计

```sh
.venv/bin/python scripts/ci/audit-step-null-811bb97.py \
  --bundle step-evidence/wire-original-811bb97-01 \
  --archive /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/step-wire-source-811bb97.zip \
  --input-file /Users/YJBeetle/.codex/task-artifacts/document-properties-parallel/vm-series-20261110/step-qi-ap203-wireframe.step \
  --output step-evidence/null-811bb97-audit-repeat.json
```

本轮只离线审计和源码核对，没有操作VM/CAD/CI或push，没有重放原候选或修改原件。旧60f几何表示失败保持，不将本次零导入的未知几何替代它。
