# 文档属性校准性能：当前接管与验收边界

工作树：`/Users/YJBeetle/.codex/worktrees/docprops-calibration-performance/SWCLI`  
分支：`codex/docprops-calibration-performance`  
基线：`1593330e6e757073d44c5bb9a04dc06deca10966`（parent `3bda2c00489dde6a3d1e4521c548f751b1d1c197`），仅批次本地 checkpoint，不是已发布/已验收版本。

## 范围与保护

接管 HANDOFF.md 中两个未提交文件，完成报告 revision 缓存、wrapper/预持久化/function body 计时拆分、每 checkpoint 的严格 native identity 双射。所有原生调用前仍 checkpoint；嵌套 row/list/dict 写点在赋值完成后提升 revision，保留原始 alias；显式 persist 仍强制完整观察/byte cache，replace 成功前不推进缓存。

没有跨 checkpoint 缓存原文档、前台、上下文或状态。每次 fresh GetDocuments/GetDocumentCount；先证明 expected 原生身份互异，再消耗 actual 匹配；重复 expected/actual、missing/foreign 均拒绝。原生身份仍由 IsSame 判断，不由 Python identity/title 替代。

新增计时中的 `elapsed_seconds` 保持原保守 wrapper 预算含义；`begin_trace_seconds`、`checkpoint_seconds`、`native_seconds` 分开。native_seconds 仅 function body，可能是多 COM SDK helper，不能全称纯 COM。计时不含 terminal trace 自身 fsync；begin/terminal 仍各 fsync。600/1800、首次失败、预原生持久化、部分 mutation 回执、几何/只读/身份/前台断言不放宽；没有原生重试、失败回滚或组内 host 重启。

不操作本地 Windows VM，不更改 DockerSW/MacSW、main、版本或空标准白名单，不合并其他未验收分支，不发布。

## 已完成 portable（非原生校准/非公开验收）

- `PYTHONPATH=src /private/tmp/swcli-a14-test-env/bin/python -m unittest discover -s tests -p 'test_document_properties_calibration*.py'`：107 tests 通过。新增 fault/permutation/count/CI 接线测试。
- 全仓 `python -m unittest discover -s tests`：2101 tests，84.096s，OK，skipped=32（环境条件），原件 `evidence/docprops-performance/full-tests.log`。
- `actionlint v1.7.12 -shellcheck= .github/workflows/ci.yml`：exit 0；PyYAML parse 通过；`git diff --check` 通过。
- 新脚本 `scripts/dev/benchmark-document-properties-calibration.py` 可重现计量：605840-byte synthetic report、250 unchanged read calls，原 pre-call 模式 dumps=250；revision 模式 dumps=0。报告原件 SHA 相同。稳定4对象比较16→10，全部24目录排列及重复/foreign故障矩阵通过。原件 `evidence/docprops-performance/portable-benchmark.json`，明确关闭 trace fsync，只是 portable CPU/count，不是 Windows 加速倍数。
- 预 persist replace 故障：只一次 replace、零 native、revision/bytes cache 不前进；native 原因遇次生 I/O 不被覆盖；嵌套 alias/读值在下一原生调用前 durable；AST 保守审计全部 subscript/container mutation 写点，防漏 invalidation。

## GitHub Windows 内部校准设计

已有 `ci.yml` 加默认关闭 `docprops_calibration` 与必需 exact `docprops_expected_head`，仅 `workflow_dispatch` + 本仓库 + 此分支 + `expected_head == github.sha == checkout HEAD` + `native_full=false` 才执行。校验在首个私有输入前；checkout `persist-credentials:false`。本分支 push/定向 dispatch 跳过无关 test/package/native full/release，避免占用无关完整 CI。

复用现有安装/私有 runtime/同名 Windows concurrency。新增 `verify-document-properties-calibration.py` 复用 owned harness：仅新 host，require owned，捕获 process handle，设置本 owned 实例 UserControl=True（在 calibrator baseline 前），持有 STA 并 pump 等待 hardened driver。driver 在独立线程仅管自己 Popen worker，nonce/argv/exe/PID/-I -S 授权不变。finally 仍只 ExitApp owned + wait captured handle；cleanup 脚本新增显式 `-PrivateInputsOnly`，此路径不全局终止 SOLIDWORKS/daemon，仅清除私有输入/服务/挂载；原完整 CI 的默认行为未变。

本次选择**原单组完整36转换**（part/assembly/drawing各12，含每次保存、RO重开及profile/几何断言），仍1800秒，不是拆组。wrapper 对报告进行再次完整性拒绝检查，R4样式30 setter/29 roundtrip、profile漂移、重复setter、cleanup失败均不能成功。新原件生成 source/head/run/attempt/hash manifest，公开 artifact 仅本run校准输出，不上传私有配置/安装日志。

官方 API 已核实：
- [ISldWorks.UserControl（官方2024，true让应用可见并由用户控制）](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControl.html)
- [ISldWorks.IsSame（官方2021，返回 swObjectEquality）](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~IsSame.html)
- [ISldWorks.GetDocumentCount（官方2025）](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~GetDocumentCount.html)

2025 UserControl/IsSame直链在检索工具不可访问，使用可访问官方版本交叉核实；此次不更改这些既有 COM API 的生产实现，安装 TLB 仍须动态读取/核对全部所需常量。

## 历史失败与未完成边界

R4 原生整组1800秒超时：30 setter True，29完整保存/只读重开；不是标准校准通过。原始持久证据见历史 HANDOFF.md 与 `/Users/YJBeetle/.codex/task-artifacts/docprops-calibration-performance`。既有字体/显示诊断不重跑。

当前尚无本优化 head 的 Windows 成功证据。后续仅触发一次对应 head 定向校准；若失败先下载原 artifact、核 hash/第一真实失败，只有相关修复后才启动新验证。内部校准即使通过，也不是本批六个公开写接口（lease/expected_update_stamp/完整CAS/保护/partial receipt）的公开验收；空白名单保持 fail closed。

## 提交与 CI

实现提交、远端 head、dispatch 参数、run URL、原件/hash/第一失败会在此节追加。当前不创建 PR、不合 main、不发布。

## 主集成汇总字段（15路统筹）

- 新公开 operation / CLI / request-result schema：**无**；本路只改内部诊断/计量/CI，不新增协议或 SDK 参数。标准生产 whitelist 仍空。
- 内部 CLI：`scripts/dev/benchmark-document-properties-calibration.py --output ...`；`scripts/ci/verify-document-properties-calibration.py --expected-head <sha> [--check-context | --output-dir ... --swconst ... --drawing-template ...]`。
- trace 新字段：`begin_trace_seconds`、`checkpoint_seconds`、`native_seconds`（pre-native失败为null）、`native_started`、`native_completed`、`timing_scope`；旧 `elapsed_seconds` 保留。report revision 是进程内缓存，不是公共 schema。
- 共享文件修改：`.github/workflows/ci.yml`（专属 opt-in job/input，portable job branch guard）、`scripts/ci/windows/cleanup-hosted-solidworks.ps1`（可选 PrivateInputsOnly，原默认保留）、`scripts/dev/calibrate-document-properties.py`、既有校准测试一行 invalidation。其余新增脚本/测试/证据/交接文件；生产 src/schema/SDK 不改。
- 依赖：继承批次 checkpoint 的 fixed drafting-defaults-v1 reader、hardened driver 与 owned harness。最终 workflow 共享冲突由主集成处理；本路不读写其他 worktree、不等待其他分支。
