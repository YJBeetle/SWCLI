# 公共写入 42423042929 首错与最小门禁修复

旧运行 [42423042929](https://github.com/YJBeetle/SWCLI/actions/runs/42423042929)，精确业务 head `ac8e7f26ced8148d16fe236280082d4f78ec9290`，保持 **failure**。官方 artifact `13596036567` / `swcli-windows-hosted-42423042929-1` / 19290057 bytes，官方 digest 与下载 ZIP SHA256 同为 `924c3bab00df410f36761d0ddd4fc03bf2fb554fb8ae3f7d53f5eb58230c72d8`。公共 report SHA256 `6b8ed34c531bec9c4df8f8caae514bc16ed9743a66a24272d29a1881a2767c12`。

原始 ZIP、官方日志 ZIP、原解压及公共 step 原日志完整保存在 `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-writes-42423042929/`。版本化元数据、真实首错源快照与独立审计在同名 `docs/evidence/` 目录；不提交 ZIP 或原生二进制。

## 首因和真实边界

首失败是 CLI 第 117 个 case（drawing 第 25 步），字段 `mass_properties.length_unit`。真实源快照读到 `inch/native 3`，合法 changed target 为 `mm/native 0`。门禁错误地先用源值 `inch` 发 noop；本字段仅 `mm/m` 是已核可写候选，daemon 协议校验返回 `ValueError: unsupported candidate unit target`。请求到达 daemon validation，未进入业务 worker/native setter；此前“客户端前拒绝/零 daemon”描述有误，本说明更正，原件不改。

CLI 完成 116/139：part 46、assembly 46、drawing 24；第 117 个 case 已开始但没有 changed-write 回执。SDK 0/139、MCP 0/139。完成的 116 个真实 setter 都返回 True；lease/stamp/full CAS/readonly 各 116 个预期拒绝、closed domain 98 个拒绝有真实公共回执。独立审核重算 232 份公共 source/saved 文件、完整 profile/raw5/linkage19、92 次 part 几何比较；V/S/body count 精确，质心只采用既有逐轴绝对≤1e-12mm，38 次 nonexact 保留原始值。

公共 native trace 无 native API error，232 个预期 operation-level lease/stamp error；最大完成边界 2.047 秒，公共组 1487.031 秒。单 worker，owned native 一次 stop 后句柄确认退出，前后 PID []，cleanup_errors=[]。同一 run 的内部 139 步成功、503.75 秒，单独记录，不能填补公共未到达部分。整个公共验收尚未通过。

## 修复与保留标准

只改公共门禁：当前源值属于合法候选时保留原先前置 noop；可读而不可写时，先完成原计划合法 changed write 和完整 guarded read，再对已成功的合法目标做 noop。noop 必须零 mutation、完整 snapshot/raw/linkage/document/stamp/CAS 状态不变，包括已 dirty 状态。inch 不加入产品候选，137 精确域/26 system 后态不改。

合成 drawing fixture 保留真实 stored inch，回归覆盖 CLI/SDK/MCP 三路各一次后置 noop，changed 次数仍 417。另用官方 ZIP 的真实源快照，经真实 CLI 解析与 daemon request handler 校验，允许一次 daemon validation，请求以相同 ValueError 结束，worker manager 调用零次。该测试使用替身连接及真实协议层，不宣称本地 CAD 验证。

仅增加每 transport 调用/完整 case 耗时记录，便于后续预算失败交付时间分布；不调整执行方式、600 秒请求/1800 秒整组、原子组或 lease 策略。CLI/SDK/MCP 各139、同一 owned host、负向拒绝、完整后态/保存RO/几何和单次清理仍全部要求。产品 src、schema、workflow 和 main property/PyYAML 修复未修改。若后续触硬预算，先交原始分布，不拆组/少测/放宽阈值。

## 独立复现

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
python3 docs/verification/audit-units-public-failure-42423042929.py --archive /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-writes-42423042929/original.zip --metadata-dir /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/evidence/units-profile/public-writes-42423042929
```

此标准库审计器不导入产品、门禁或 COM，仅复用先前审计器的纯数据校验函数，并只读取本 run 新原件。摘要 `first-failure-audit.json` 明确 public_overall_accepted=false。

本地检查记录见 `docs/evidence/units-profile/public-writes-42423042929/fix-validation.json`。推送修复后仅一次必要新公共验证，正常一次 run/job 快照即停；不持续 poll，不动 VM/main/发布，不使用代理。
