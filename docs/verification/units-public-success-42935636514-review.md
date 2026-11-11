# 42935636514：公共417项与3个独立冷启动探针原件验收

[官方 run 42935636514](https://github.com/YJBeetle/SWCLI/actions/runs/42935636514)，source `459b0cf88892fe1af013156994568d6e52e6df2e`，attempt1，terminal **success**。本审计只承认该源版本、SOLIDWORKS33.5.0、part/assembly Default 与 drawing已观测配置、手工准入137个精确域；不宣称完整原生产品矩阵、整合后main的原生运行或发布完成。旧失败run原件及当时未确认退出保持原结论。

## 原件、来源及两项保留边界

terminal run/jobs/artifacts各取一次；未轮询、未重派。native artifact13820837309，47688318 bytes，官方与下载 SHA256 `c34b58cd4796d7778eae31b01d69bacc1108d9c9c12e22908b6d054c37fb7117`。724个安全解压成员，展开766595213 bytes。原 native job130247230662 日志本地 SHA256 `4b3c7a246f92db6825b176563050d05bcbad01c2636141e42acca104699babfb`；日志API无同名官方digest，不混称。两 portable summary ZIP也逐一核官方digest，清单见 terminal-retrieval.json 与审计结果。

**本success run没有installer ZIP。** 官方artifact列表无该项；精确459的workflow只在 `failure()` 上传安装日志，原job该上传步骤skipped。保留原nativejob日志与安装步骤success，但不借旧run的MSI、不捏造本run installer digest。

**原通用summary的 public-evidence仍是SKIP。** 它的RECEIPTS清单不识别 `public-unit-profile.json`，原detail为 `no public acceptance receipts found`；而实际units-calibration、units-public-acceptance、cleanup阶段均PASS。本次不改原summary或产品代码，单位结论来自下面完整原件审计，不能把该通用SKIP写成PASS。

原件绝对目录：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-short-path-42935636514/`，含 original-native.zip、安全解压original、原native/两Windows job日志和两summary ZIP。官方metadata、public-success-audit.json、独立验证hash在同名docs/evidence。原件目录不纳入git。

## 实际覆盖

| 范围 | Part / Assembly / Drawing | 完成 | 耗时 |
| --- | --- | --- | --- |
| 公共CLI | 46 / 46 / 47 | 139 | case合计330.936s |
| 公共SDK | 46 / 46 / 47 | 139 | case合计377.013s |
| 公共MCP | 46 / 46 / 47 | 139 | case合计483.555s |
| 额外真正fresh CLI | 各1 | 3 | 纳入同一公共组 |
| 内部private独立诊断 | 46 / 46 / 47 | 139 | 248.422s |

公共整组（启动、预检、417项、收尾）1355.766秒≤1800；每原生边界≤600，实际最大1.000秒。CLI策略明确是一个隔离helper复用真实cli.main/parser/RPC，4676条严格顺序命令、starts1、exit_waits1；不是139次独立冷进程。三cold确用另一次 `python -I -m swcli`，保留原stdout、独立request ID，仅去request_id后完整JSON/snapshot/document逐项相同，没有归一原bytes。SDK走真实typed writer，MCP走真实stdio initialize/tools/execute/capabilities；三路线共用相同endpoint与原生宿主。

每路线都覆盖137个完整before域与对应after hash，合计417次真实changed write、417次no-op、2010次零写负例（lease/stamp/CAS/readonly各417，关闭域342）。三次drawing原生可读inch的no-op在合法mm写后做；未扩大候选值。全部九字段、raw5、linkage19及类型都核完整；精度0..8、37 scalar目标与8条system spoke由内部完整计划和各路线139项对应绑定。

## 每次写入、持久化与原生调用绑定

独立标准库审计不import产品、门禁、COM，不调用CAD；只复用既有纯snapshot/geometry校验。它固定run/head/artifact/ZIP/log，再核：

- 417个changed/417个no-op/2010个拒写各自唯一绑定到原command、原reply/request ID、实际SDK/MCP wire上下文；完整snapshot/stamp/document/lease/owner/contender/value匹配。错误CAS只改变指定linkage项，stamp错误为原值+1，关闭目标确不在静态137表。每次负例后再读、changed前的完整profile/document都与原before相同；after/observed/guarded reread/readonly/final read精确匹配手工after fingerprint。
- 实际source open、readonly reopen、save命令及SDK/MCP wire路径共1251次绑定到本run hashed fixture和417份独立输出。保存零错误、未修改，RO新document ID、拒写零mutation、前后profile/原文件hash均核。417源引用绑定已hash原件，另417份保存文件逐一核hash；内部281份原件（3初始+278 source/target）独立核，不混为公共。
- 276次公共part几何比较（190 nonexact）与92次内部比较（59 nonexact）均保原raw/delta/hex；body/V/S严格相同，仅质心逐轴绝对≤1e-12mm。没有相对容差或全局放宽。
- 46764行durable journal连续且覆盖14031个完整命令，最终event逐字数据结构hash匹配。CLI原B64字节/UTF8与真实cp1252 stderr分别核对，序号连续且无异常frame。MCP structured/text及isError与raw envelope一致；实际客户端和helper源hash按Git LF/CRLF两种字节形式核精确459。
- 1,710,960个native frame全部begin/terminal嵌套配对，14,029个实际typed request逐ID关联到原CLI/SDK/MCP结果，单worker6088。417个changed各一次setter，其余unit请求均零setter；834个error仅是预期lease/stamp的operation级拒绝，没有原生API error或重复request。

lease TTL600由实际CLI/wire请求参数核对；`expires_in_seconds`是deadline减clock的剩余时间回执，原三种浮点值600.0/600.0000000000002/599.9999999999998及数量原样保留在结果中，不改为600，也不把它当九字段CAS或另加数值容差。

## 实际Windows路径及退出

Windows3.9/3.14各2008 tests通过：252.285s/11skip与178.279s/4skip。两端真实短长文件正例、不同/缺失文件反例均实际ok，不是skip；原日志finally观测含短名、完整长名、DWORD4/wchar2、长度/NUL、raw buffer、相同device/inode与samefile=true。

native Python3.12中原SW image仍是 `C:\PROGRA~1\SOLIDW~1\SLDWORKS.exe`（33），一次GetLongPathNameW真实展开为原expected `C:\Program Files\SOLIDWORKS\SLDWORKS.exe`（40），长度/NUL/原UTF16 buffer完整。两路径device9823700658284110452、inode844424930365935相同，samefile=true；raw四字段保留，expanded准入副本明确另列。公共PID9208、creation窗、早期保留handle及末次health同宿主均核过，三路线/所有native request只有worker6088。

一次normal stop exit0；native retained-handle wait确认退出，helper8500的只读保留句柄wait确认退出、正常EOF/exit0；前后native PID清单均空、cleanup空、无强制终止。具体数值handle未序列化；保留句柄流程依据精确源wrapper/identity helper与原成功wait字段，不伪造不存在的handle编号。内部PID2484单独正常退出，不替代公共。

## 重放与交接

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
python3 docs/verification/audit-units-public-success-42935636514.py \
  --metadata-dir docs/evidence/units-profile/public-short-path-42935636514 \
  --raw-dir evidence/units-profile/public-short-path-42935636514 \
  --repo-root . --output /private/tmp/units-public-success-replay.json
```

脚本及纯校验依赖SHA、结果SHA、五项篡改拒绝检查（错head、官方digest、samefile标记下fileID不符、原UTF16不符、九字段缺项）、Python3.9 AST/diff/import检查见 independent-audit-validation.json。产品/src/workflow/CI/tests对已验收459无diff；没有重复全套测试或CI。

按统筹后续指令，不继续合并分析、不改整合树。本提交仅本run纯证据/可重放审计，供统筹另并；主整合与其单独验证由统筹维护，不拿本459的原生成功冒充整合后main的原生运行。不自行push/main/VM/发布。
