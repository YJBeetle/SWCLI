# 有界旋转凸台：第一步候选与校准

状态：公共写入 **关闭**。`feature.revolve` 当前只能返回
`RevolveNotCalibrated`，`ok=true` 不符合结果契约。内部校准成功也不等于公开验收。
未改变版本、正式分支、发布门禁或默认完整验收集合。

## 最小范围

候选只接受空零件、一个配置、已注册且尚未被吸收的 2D 中心矩形。
完整截面边界为 `[0, min_y, radius, max_y]`（mm）；显式轴为
`[0,min_y,0,max_y]`，即原矩形左边；角度必须显式 `360`（degree）。
轮廓的四条实线必须构成简单闭合矩形，不能仅凭包围盒判断。
允许现有矩形创建器生成的两条构造对角线。没有隐式轴创建、草图编辑或轮廓修补。
不支持任意曲线、非整圈、旋转切除、薄壁、已有实体合并、多实体、多配置或曲面。

公共 CLI 候选契约：

```sh
swcli feature revolve s-abcdef --document d-abcdef --if-update-stamp 12 \
  --expected-profile-mm 0 -5 10 15 --axis-mm 0 -5 0 15 --angle-deg 360 --json
```

SDK 的 `client.feature.revolve`、协议与 MCP `execute` 使用同一契约。
完整 `expected_profile_mm` 用作轮廓值 CAS；`document_id` 和
`expected_update_stamp` 必填，沿用 daemon lease 检查。关闭的公共调用不会临时激活
后台文档；也没有公共开关、环境变量或请求参数能绕过写入门禁。

## 官方接口依据

- [FeatureRevolve2](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeaturemanager~featurerevolve2.html)：20 参数；轮廓 mark 0、轴 mark 4/16；盲角用弧度。
- [GetRevolutionAngle](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IRevolveFeatureData2~GetRevolutionAngle.html)：读回方向一角度。
- [GetAxisType](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IRevolveFeatureData2~GetAxisType.html)：轴类型由 swSelectType_e 表达。
- [IRevolveFeatureData2](https://help.solidworks.com/2010/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IRevolveFeatureData2_members.html)：轴、方向、薄壁/凸台、合并与访问/释放。

校准必须先读取安装的官方 `swconst.tlb` 和 `sldworks.tlb`：核对实际接口成员、
`FeatureRevolve2` 参数数并记录签名；枚举取自类型库，不猜数字。
使用 `IsSame` 证明选中轴和定义读回轴相同，不能用名字代替对象身份。

## 验证与失败边界

独立解析预期为 `V=πr²h`、`A=2πr(r+h)`、草图局部质心
`(0,(min_y+max_y)/2,0)`，经实际刚体坐标变换校验模型质心。
必须获得一实体、原生 `Revolution` 定义、整圈角、轴身份、凸台/非薄壁及健康诊断。
在三个原点标准平面保存 `.SLDPRT`，记录内容哈希后只读重开，重新定位被吸收轮廓、
重读定义和质量属性，核对哈希未变。不能用仅创建成功或仅文件存在代替验收。

已有实体（包括曲面）、轴穿过截面以及完整值 CAS 不匹配在原生创建前拒绝。
写入尝试前设置 `mutation.attempted/may_have_changed`；空返回或抛出也不声称未修改。
后续检查失败保留原始错误、已创建特征句柄和 cleanup 错误；不自动 CAD 回滚、不重试。

## 运行与证据分层

只在 `codex/swcli-revolve-feature` 分支手动 dispatch `ci.yml`，输入
`native_revolve_calibration=true,native_full=false`；默认关闭。
PR 或普通 push 不能进入有秘密的原生任务；现有完整原生与发布门禁保留。
校准每个原生/案例边界 600 秒，整组 1800 秒，单一自有宿主、不组内重启。

- 便携：`tests/test_revolve.py` 和全套 unit / SDK 检查；不能证明 COM 可用。
- 内部校准：`scripts/ci/verify-revolve-calibration.py`，原始 report、trace、模型与 ZIP。
- 公开验收：尚未完成。未来开门需真实客户端→daemon→COM worker 的原生保存重开证据，
  包括 lease、stamp、后台身份与只读拒绝；本分支不会因为内部校准而自动开门。
