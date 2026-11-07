# 文档偏好原 batch：公开原件自验收据

2026-11-08 自验；最终 source review、合并和全系列发版由统筹本人完成，本路不合并或发布。

- 实测代码：`b6d28f2a8f6fd549416ea5fac5aa12f538c9a9d6`。
- [GitHub run 42361904486](https://github.com/YJBeetle/SWCLI/actions/runs/42361904486)，attempt1，success；`docprops_public_scope=batch`，该 head 唯一 dispatch。
- Artifact `13571626572`，`swcli-docprops-public-42361904486-1`，10354958 bytes。
- 官方 digest / 本地原 ZIP SHA256：`460d32d13b9953604c5f6ed1246258725895d7579817b53084413236e2501d30`。
- ZIP 的97个原文件逐字节与解压目录一致；公开 manifest 的全部 hash/size 与文件集合一致；run/head/attempt/repository/workflow、context 均匹配。原件未修改。
- 统一 host：原生 Windows、SOLIDWORKS revision `33.5.0`、PID1000、owned=true、visible=false、shared_interactive=false。5组同一 host，逐 case 清空，全部 cleanup_errors=[]，最终 daemon shutdown 成功。

| 组 | 实际 changed 写 | dirty 同值零写 | clean 同值零写 | 值冲突拒绝 | lease / stamp拒绝 | RO拒绝 | 保存及RO |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 标准 | 36 | 36 | 36 | 36 | 3 / 3 | 36 | 36 |
| 总注释字体 | 21 | 21 | 21 | 21 | 3 / 3 | 21 | 21 |
| 显示 | 25 | 25 | 3 | 25 | 3 / 3 | 3 | 3 |

691个公共偏好请求逐条重放现有严格 PreferenceTrace 校验器，核全部固定getter周期、单次setter和必要字体属性赋值、SetSaveFlag数量、request ID/worker/600秒预算。公共结果再次通过业务schema；changed回执、完整CAS（font17字段、standard snapshot）/stamp/document/lease、请求目标值、未请求字段保持、字体模式和native_normalizations、before/after/final均对应。各次拒绝的下一次读取保持完整snapshot及document状态；同值零setter/属性赋值/dirty且描述符不变。此为首层自验，不代替统筹最终独立 review。

60个保存文件 hash/size保持，RO模式/零API错误、新鲜document ID、clean状态、完整profile持久化通过；继续以新writable ID读回并验证clean no-op。零件单实体box V/S/centroid保持，三类原输入hash不变。9个类型/profile组合分别执行typed SDK及MCP execute读取，共18读，schema/native trace/CLI snapshot和后台描述符一致。5组均在1800秒内：标准P/A/D为204.600/242.658/286.536秒，字体586.542秒，显示382.328秒；native/request预算600未改变。无失败重试、回滚或组内host重启。

## 可合范围与限制

候选范围是原batch三对operation：总字体七字段（P/A/D各7）、显示十字段（P/A各10，D仅grid4+virtual sharp1）、P/A/D的GB7↔ANSI/ISO/DIN/JIS/BSI/GOST共36 tuple / drafting-defaults-v1。精确原生Windows revision33.5.0，Wine/未知runtime/未测revision拒绝。严格Win32导出证明及peer/target身份保护为本head实际代码，portable故障矩阵已验证未知host零写、peer前后漂移、dirty前漂移、首错与partial receipt。

不推导：任意named→named、自定义`.sldstd`、其它字体子类型、既有注释传播、字形/颜色/网格实际渲染、任意复杂模型、Wine/未来revision或全Document Properties页面完成。工程图plane字段在本run不暴露且未尝试写入；其独立拒绝仅portable反例，不能称已做原生写拒绝试验。原生强制失败/partial mutation注入同样只具portable反例，本次成功运行不新增该实测结论。assembly是自有空assembly，drawing是自有GB base图纸；不外推任意复杂工程图。

三组既定字段及其适用类型公开验收已完成，供统筹审查后逐条合并；本收据不自行通过统筹source review或发布其他系列能力。

## 持久原件与复跑

工作树绝对路径：`/Users/YJBeetle/.codex/worktrees/docprops-calibration-performance/SWCLI`。

`evidence/docprops-performance/` 下：

- `run-42361904486-original.zip`、`run-42361904486-original/`：不可变原件。
- `run-42361904486-final.json`、`run-42361904486-artifacts.json`：GitHub原始metadata。
- `run-42361904486-audit.json`、`run-42361904486-audit.log`：首层自验结果。
- `review-guards-full-tests.log`：实测代码完整portable2164/skip32；`preferences-guard-tests.log`、`review-public-profile-tests.log`：补充故障；`review-guards-sdk.log`、`review-guards-actionlint.log`：SDK/actionlint。
- `public-audit-fault-tests.log`：本轮新增审计篡改/head/digest/拒绝零写4项测试。

审计仅需Python3.10+与jsonschema4；不执行COM、不启动daemon、不访问网络、不写原件。`--output`必须位于原件目录之外。在上述工作树执行：

```sh
python3 -m venv /private/tmp/swcli-docprops-audit-env
/private/tmp/swcli-docprops-audit-env/bin/python -m pip install 'jsonschema>=4,<5'
PYTHONPATH=src /private/tmp/swcli-docprops-audit-env/bin/python scripts/dev/audit-document-properties-public.py \
  --root evidence/docprops-performance/run-42361904486-original/public \
  --head b6d28f2a8f6fd549416ea5fac5aa12f538c9a9d6 \
  --archive evidence/docprops-performance/run-42361904486-original.zip \
  --run-metadata evidence/docprops-performance/run-42361904486-final.json \
  --artifact-metadata evidence/docprops-performance/run-42361904486-artifacts.json \
  --output /private/tmp/swcli-docprops-batch-audit.json
PYTHONPATH=src /private/tmp/swcli-docprops-audit-env/bin/python -m unittest discover -s tests -p 'test_document_preferences_public_audit.py'
```

原件审计提交e123388仅增强离线审计及补齐证据/文档。随后统筹review要求的三个setter postflight/worker late-fault修复已另做portable故障注入，详见[异常回执修复收据](docprops-preference-receipts-2026-11-08.md)。健康native证据仍绑定b6d28f2，不冒称新故障路径在SOLIDWORKS现场复现；按统筹要求不做无信息整套原生重跑。
