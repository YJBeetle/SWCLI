# 单位扩展：交统筹最终review的精确可合子集

工作树：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI`，分支`codex/docprops-units-expanded`。最终可合tip为本次完整审计/交接docs提交（精确SHA随本轮最终回复给出）；业务验收head为`577309005a858c11543b5def253dca36e5d0c598`。其后的变化仅审计/原件/交接文档与本次本地原件忽略规则；src、scripts/ci、workflow均与验收head相同，独立命令会强制核验，不能在未审计的新业务源上冒用此通过记录。

## 本轮新证据（不引用旧原件作通过）

- Run [42361728509](https://github.com/YJBeetle/SWCLI/actions/runs/42361728509)，workflow_dispatch，精确head如上，conclusion=success。
- GitHub artifact ID `13571025062`，name=`swcli-windows-hosted-42361728509-1`，373398 bytes。
- 官方digest及下载原ZIP SHA256均为`92c718be6f704c350075ce4de8fbce5e621d81de40e77ae5b915d95d8e882e6c`。
- [官方artifact元数据](https://api.github.com/repos/YJBeetle/SWCLI/actions/artifacts/13571025062)保存于本工作树`docs/evidence/units-profile/lease-exit-42361728509/artifacts.json`，含workflow_run.id/head_sha绑定；run-completed/jobs-completed原件同目录。
- 本地原ZIP：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/lease-exit-42361728509/original.zip`。
- 原始解压目录：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/lease-exit-42361728509/original/`。ZIP/native文件持久本地、不入git，不依赖/tmp。
- 内部原report SHA256=`97aa3d8a0732687da4ea3dd26fbdf41f94a3d47df642e6b3425912226e0a5a56`。
- public原report SHA256=`cbd7e2bf7840557cd7e861c8bfcefcaff94dac700700203fbc845c74fc97a3e9`。
- host原report SHA256=`01a32737fddbd4af13744533faae50fdf89ad8bac8210346565a0c5079a32f8d`。

## 可独立复跑审计

审计器仅Python标准库，不导入产品/gate代码，不调用COM/网络，不触发CI或写CAD文件。它从**原ZIP字节**读取全部业务证据，固定本轮run/head/artifact/digest，不能拿旧ZIP替代；另核当前操作源相同、写白名单仍空。metadata是本轮GitHub原始响应，内嵌官方digest亦固定在审计器中。

```sh
python3 /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/verification/audit-units-42361728509.py \
  --archive /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/lease-exit-42361728509/original.zip \
  --metadata-dir /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/evidence/units-profile/lease-exit-42361728509 \
  --repo-root /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
```

退出0且`audit_success=true`才是通过。固定结果：`/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/docs/evidence/units-profile/lease-exit-42361728509/independent-audit.json`。若当前操作源被改动，该命令会拒绝复用原head证明。也可只读刷新官方artifact元数据（不启动任务）：

```sh
gh api repos/YJBeetle/SWCLI/actions/artifacts/13571025062 --jq '{id,digest,workflow_run}'
```

## 本轮真正通过的精确范围

Windows-2025 hosted、SOLIDWORKS 33.5.0，public实际Python3.12.10。Windows Python3.9/3.14前置portable与SDK、package/installed-wheel检查也均success，不能混称为所有Python版本的native证明。

- part（40×30×10 mm box）、空assembly、模板drawing三类新fixture；九字段profile、raw GetUnits五short及19项linkage。native read/readonly-reopen/public read全snapshot严格一致。
- 字段为system、linear.unit/precision、angular.unit/precision、mass_properties.length_unit/mass_unit/volume_unit/precision；part/assembly源MMGS，drawing源IPS。
- 公开`document unit-profile`读；`unit-profile-set linear.precision 2`同值noop：无setter/不dirty；目标保持background，文档ID/path/title/stamp/dirty/current/active按记录严格保持。
- 每类各5个预期拒绝：真实合法owner-token配竞争session的DocumentLeaseConflict、stale stamp的DocumentUpdateConflict、非目标linkage完整CAS冲突、未校准changed请求（此三源均ValueError）、readonly拒绝。除lease/stamp前置拒绝可无业务mutation外，其余均有双false回执。
- 98个完整CLI事件，15个仅预期错误；原stdout与事件result逐一一致。每份source/copy native字节SHA与原ZIP实际文件重算一致，fresh readonly handle及最后拒写后读数/状态严格保持。
- part独立V=12000/S=3800/质心(0,0,5)解析检查保留；本轮V/S/count精确，质心符合仅本路绝对≤1e-12 mm批准界限，raw/hex/delta/exact_equal标记保持。本轮三个part比较恰为exact_equal=true；边界/越界/NaN/Inf与V/S一ULP拒绝属于便携测试，不冒充native主动故障注入。
- 内部5656 native边界，max6.297s、group31.843s，无error事件。public5003边界，max2.016s、group36.109s，仅6个预期operation级lease/stamp错误，无native/API错误；单worker无替换。完整public宿主组44.359s。
- 独占hidden/unshared native PID9108来自新host；一次stop、保留句柄退出确认true、before/after PID库存均[]。无新增单位偏好setter调用、无API失败重试/回滚/组内重启。

## 不得扩大为已验收

`CALIBRATED_UNIT_WRITES=()`仍空。没有changed单位写入、scalar/system切换、其他source/target写域或写入持久性证据；不得把只读/noop/拒写public通过标作九字段写入完成。旧A17接口源码未改，兼容性portable证据不等于本run重测其全部native场景。P1描述符异常回执/同指针peer漂移有真实handler/worker便携故障注入与独立mock复现，本run是正常native正向/拒绝覆盖，不宣称已原生主动注入所有异常。Wine/macOS/Linux、全功能/发布gate未覆盖，release job skipped。

该精确子集交统筹本人最终review/merge；本线程未合main、未发版、未触碰VM/DockerSW/MacSW。系列其他未完能力与正式发布仍按用户要求处理，本次不作系列完成或发布授权。
