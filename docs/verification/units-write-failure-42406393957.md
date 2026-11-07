# 单位写校准42406393957：首因、实际覆盖与最小修复

本轮仅处理 `42406393957 / 4f20723116103c6e5f43def9f3d42b5a91372903`。官方 workflow 最终 failure；Win3.9/3.14 portable、SDK、PowerShell解析、wheel 均通过，失败 step 为 `Calibrate bounded document unit profile`，public step skipped。

## 官方原件与独立审计

- 原artifact ID `13588889164`，`swcli-windows-hosted-42406393957-1`，5744172 bytes。官方digest与实际下载ZIP SHA256均为 `aa850757a3940f0d26ac6ccc8fc20a213842ad2ead2a21bab29b986d7dd5b7ad`。
- 本地官方原ZIP：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/write-native-42406393957/original.zip`。安全解压到同目录 `original/`，不修改任何原文件。
- 官方日志原ZIP同目录 `actions-logs.zip`，本地SHA256 `2ca35e8894fa6ebe161cdc23ef564e30379ab1f45751d8c7be4c961c5dfaed6c`；GitHub未提供该日志ZIP的独立官方digest，不把本地hash称为官方比对。相关step可读副本（仅LF/ANSI/行尾空白规范化，原字节及hash另存）和run/job/artifact完整元数据在 `docs/evidence/units-profile/write-native-42406393957/`。
- ZIP内原report SHA256 `98be23a6b37edef57dd63312fd9c13578621d4dd4b1a13313f1b4d5bdc3a2cab`。标准库审计不导入产品/gate、不调用COM，直接从固定原ZIP读数，核run/head/digest、已安装源码的LF/CRLF原字节形式、100份source/target原生hash、真实回执/状态、raw geometry及delta/hex。结果 `first-failure-audit.json`。

可复跑命令：

```sh
python3 /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/verification/audit-units-write-failure-42406393957.py \
  --archive /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/write-native-42406393957/original.zip \
  --metadata-dir /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/evidence/units-profile/write-native-42406393957 \
  --repo-root /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
```

## 第一个真实失败

**父watchdog判定1800秒整组预算耗尽并终止worker。没有已记录的native API失败或业务断言失败。** 不是便携测试问题，也不是V/S或质心超界。

原trace159548行、79772个已完成边界、0个error事件；已完成调用最大19.483999999999924秒，均未超过600秒。首尾monotonic差1800.297秒；watchdog保留4个进行中边界，最后trace时各自仅0至0.516秒。最后位置是assembly precision=0保存后 `reopen_readonly` / `describeDocument` / `GetTitle`，OpenDoc6已有end，完整readonly描述与profile未返回。原report没有业务failure对象，stdout/stderr为空；不能虚构某个SOLIDWORKS setter错误。

被父进程终止后没有owned Exit/进程句柄退出确认原件；`cleanup_errors=[]`不表示清理完成。报告PID4396、before库存[]；不据此断言持久泄漏，也不把退出未验收标成成功。

## 真实执行范围（不是139步合成结果）

| 类型 | 本次原件中已完成 | 未完成/未到达 |
| --- | --- | --- |
| part | 46个完整private步骤：1个显式Custom准备、37个scalar目标、8个MMGS双向system方向；单Set True、完整读回、独立保存/RO重开/拒写/writable重开与文件hash均有原件。八scalar各原定单位目标以及三精度0..8均到达。 | 整组/owned退出未通过，不能直接作为可启用公共域或完整验收。 |
| assembly | 3个完整private步骤：Custom准备、linear.unit inch和mm。 | 第4步linear.precision=0的Set True及保存已有原件，但readonly重开尚未完成；该字段不计完整。其余precision目标、angular、mass-properties、八system方向均未到达。 |
| drawing | 无。 | 全组未到达。 |
| public/domain | 未执行，白名单0条。 | public changed-write完成仍0/9。 |

共50个真实setter调用/成功回执，49个完整private步骤；第50步有写入与保存但持久性闭环未完成。不能把它改称50步通过，更不能借旧read/noop/拒写或合成139步补足。

part原始V=`11999.999999999998`、S=`3799.9999999999995`、body=1（完整double/hex见audit JSON和原ZIP）；92次几何比较V/S/body全严格保持。76次exact_equal=true，16次false，最大质心逐轴绝对delta=`3.970466940254533e-16` mm，仍保留原非精确标记、raw/delta/hex，只符合此前批准的≤1e-12 mm。没有扩展到relative、V/S或通用kernel容差。

## 仅相关修复

每native边界原来都会完整JSON序列化、读取比较整份增长报告；原组有近8万个边界，报告最终1293754 bytes，重复处理开销随步骤增长。修复仅把write诊断的**完整报告持久化放在显式语义检查点**，native journal每次begin/end/error仍flush+fsync，调用和状态/几何/CAS检查不减；默认read模式仍保留原来的每call完整报告检查。

写前完整source/target/身份/状态/hash意图仍必须先成功持久化；新setter回执、context after、target path/hash、RO读回、几何观察/对比及关闭前等都明确完整持久化。`durable`仍比较完整报告字节，相同才不重写；没有mtime/对象身份缓存，不跨getter吞掉新观察。报告或trace fsync失败时不得执行setter，False/异常仍只执行一次并保留首因。没有加预算、拆组重置时钟、跳字段、删守护、回滚或原生失败重试。

离线使用**此真实报告**重放1000个合成getter边界：原模式1002次完整报告序列化，新模式2次；两者均1000次getter和2000条durable trace，完整新观察均落盘。本机耗时3.6097秒与0.0763秒仅是离线I/O结果，不推断Windows或原生整组必过。原始结果 `offline-checkpoint-replay.json`，可复跑 `docs/verification/replay-units-report-checkpoints.py`。

关联70项/2.599秒通过，含旧read路径、新观察检查点、意图持久化失败零Set、trace fsync失败零Set、nested begin/end每条fsync、native异常单次/首因保留及V/S/count/质心既定边界；Python3.9 AST通过。原日志在本地原件目录，hash与验证记录 `fix-validation.json`。产品src、白名单、schema、workflow均未改；main `960839e`修好的PyYAML依赖和两个property测试文件未改动。统筹集成时应保留main这些修复，不从旧分支整文件覆盖tests/CI。

后续只对修复新head触发一次必要private校准，正常启动一次快照即停。此次失败保持failure；待新原件完成前仍无完整三类型写入/退出/public验收，不填生产白名单、不合main、不发布。
