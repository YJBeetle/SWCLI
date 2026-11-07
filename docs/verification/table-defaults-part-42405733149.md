# 零件首写前严格几何对照阻断

[42405733149](https://github.com/YJBeetle/SWCLI/actions/runs/42405733149) / `6396034fe941b28d90ced2b941ae0d6c26907be9` completed/failure。首错为 `verify-part-before-first-table-write` 内的 exact geometry dict equality，报告错误 `table fixture exact geometry comparison failed at before-first-table-write`。

测量成功、原有解析体积/面积检查和 context 校验均通过。candidate field 循环尚未进入，`writes=[]`。native trace 中文档表格 setter 为 0、偏好 getter 为 3、显式 SetSaveFlag 为 0。原有 fixture 草图推断开关 disable/restore 共 2 次，均位于表格读取之前。原始 trace 中 error frame 为 0，唯一失败的 harness stage 是精确数值比较。

## 几何 metrics 原值

| 阶段 | 体积 mm³ | 面积 mm² | 质心 x mm | 质心 y mm | 质心 z mm |
| --- | --- | --- | --- | --- | --- |
| 创建后 | `11999.999999999998` | `3799.9999999999995` | `-7.058607893785837e-16` | `5.514537417020185e-16` | `5.0` |
| 保存后只读重开 | `11999.999999999998` | `3799.9999999999995` | `-7.058607893785837e-16` | `6.286572655403011e-16` | `5.0` |
| 可写重开/后台首写前 | `11999.999999999998` | `3799.9999999999995` | `-7.058607893785837e-16` | `8.271806125530278e-16` | `5.0` |

三次实体数均为 1。只读基线到首写前的 y 差值为 `1.9852334701272664e-16 mm`，完整 metrics 不相等，按原断言失败。以上是原报告中换算为毫米后的 metrics，原生 GetMassProperties 的 12 元组没有保存。

首写前目标 metadata 为 `[type=1, stamp=163, modified=false, configuration=Default]`，前台 peer 为 `[type=1, stamp=159, modified=false, configuration=Default]`，现有 context 校验完成。cleanup errors 为空，单一 owned host 的 ExitApp 和 WaitForOwnedProcess 均完成。wrapper 实际 exit code 为 1，600/1800 秒限制已记录。

## 已定位与仍不明部分

本轮已排除 table setter 作为此次差异的原因，因为失败发生在第一个 candidate setter 之前。直接阻断是跨只读/可写重开及前台/后台测量的 centroid 输出不完全相同。为何这些读数变化，现有证据尚未分离重开、读写访问或前后台求值等因素，也未定位底层 kernel 原因。

目前没有在保留既有 exact equality 和测量语义的前提下已证实有效的产品修复。零件 profile 保持关闭，本轮原件作为失败证据保留。下一次零件验证需要实际相关修复及测试，当前不做无差异重跑，也不应用其他系列的质心例外。

## 原件、摘要与复跑

- Artifact ID `13588160547`，名称 `table-defaults-internal-42405733149-1`。
- GitHub digest 与本地 ZIP SHA256 均为 `3a1d78b525c62488eb75d82324dd9551d8700333d74f0e2a623850e586876d92`。
- 原始 ZIP `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42405733149/original.zip`。
- 官方 `run.json`、`artifact.json`、`artifacts.json` 和解压原件 `extracted/` 位于同一目录。
- 失败原件核验 JSON `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42405733149/independent-failure-audit.json`，其中 `audit_passed=true`、`calibration_success=false`、`blocked=true`。

```sh
/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/.venv/bin/python \
  /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/audit-table-defaults-part-42405733149.py \
  --evidence /Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI/docs/verification/table-defaults-evidence/run-42405733149
```

全部原始文件摘要如下。

| 原始文件 | SHA256 |
| --- | --- |
| `calibration/annotations.SLDPRT` | `9218bf1b05235d8d549e03a7ecb9d40547b4c108ab0cf6d1e78ef92b46cd5a48` |
| `calibration/geometry-observations.jsonl` | `f9e4ca3709be1658b251a321fd874a4afbd09e00c2fdcbf051ab589bdfab8dbd` |
| `calibration/report.json` | `a1a5d33211e674172e0c3f22400c79ed61aecaa19d3ed798a94d7bba519dcdf5` |
| `calibration/trace.jsonl` | `981371f0b35077207f46986d39082ac85ae0ade93f658dc1b5e07fc0900e6134` |
| `worker.native.stderr.jsonl` | `ed962e6589c048798dadb6942320ca60227f3b9a08fc7ca450ff719b9652518d` |
| `worker.stdout.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `wrapper-result.json` | `a856348ba8a9d330d54ea4520205734b0ca4599e98b559a923a79824a47a18bd` |
