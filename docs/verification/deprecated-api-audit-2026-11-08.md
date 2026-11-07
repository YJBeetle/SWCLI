# 弃用 API 核验与本批迁移决定

核验日期：2026-11-08（Asia/Shanghai）。生产代码基线：
`2d83afdc6c5c56b1a72157a84d54ee15cde770ab`。本项目当前仅以
SOLIDWORKS 2025 为开发和验收基线，不引入旧版本兼容或失败回退路径。

## 已确认的三个实际调用

| 旧调用 | 本基线生产位置 | 决定 |
| --- | --- | --- |
| `IModelDoc2.SaveAs3` | windows_documents.py:850、windows_parts.py:380、windows_native_files.py:80，共三处 | 直接迁移到 `IModelDocExtension.SaveAs3`；不在同样已被后续接口取代的 Extension.SaveAs/SaveAs2 停留 |
| `IModelDoc2.GetActiveConfiguration` | windows_documents.py:401/816/899/942、windows_custom_properties.py:90，共五处 | 使用 `IConfigurationManager.ActiveConfiguration` 属性；只观察，不切换配置 |
| `IDimension.GetSystemValue2` | windows_dimensions.py:263，一处 | 使用 `GetSystemValue3`，保留明确配置范围、系统单位和严格结果解包 |

官方依据：

- [GetActiveConfiguration（2025）](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~GetActiveConfiguration.html)
  与 [ActiveConfiguration（2025）](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IConfigurationManager~ActiveConfiguration.html)。
- [GetSystemValue2（2025）](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetSystemValue2.html)
  明确指向 GetSystemValue3；新方法的配置参数及返回对象语义见
  [GetSystemValue3 官方说明](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetSystemValue3.html)。
  本轮工具未取得该方法2025页完整正文，最终参数绑定仍须由安装的2025类型库和原生结果核验。
- [旧 ModelDoc2.SaveAs3 官方说明](https://help.solidworks.com/2017/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~SaveAs3.html)、
  [Extension.SaveAs2（2025）](https://help.solidworks.com/2025/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldocextension~saveas2.html?format=P&value=)
  和 [Extension.SaveAs3 官方签名](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs3.html)。

这确认了报告所列三项，不是对全部SOLIDWORKS API的穷尽扫描，也不保证其他开发分支没有新增命中。
调用位置随合并变化，后续以符号及精确提交定位。

## 特征数据 v1/v2 结论的限制

`IExtrudeFeatureData`、`IRevolveFeatureData`、`ISimpleFilletFeatureData` 的旧接口与
相应 v2 接口必须区分。当前生产代码通过 `IFeature.GetDefinition` 取得对象，再按成员名访问；
没有查到这三种 v1 接口的显式类型绑定，也没有查到足以证明实际返回接口版本的身份核验。

因此，不能仅因 v2 存在同名成员，就推出晚期绑定必然取得 v2、绝对无需处理；也不能反过来
仅凭 `GetDepth` 等同名调用或trace标签就认定代码绑定了 v1。官方
[特征定义接口说明（2025）](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~IGetDefinition.html)
要求区分实际特征数据对象/接口。

在后续本批已有必要原生验收中，只读记录实际定义对象的类型信息和接口 IID，结合安装的
SOLIDWORKS 类型库核对 v2。若证实已用 v2，保留现行同名成员；若实际绑定旧接口，再做有证据的迁移。
不盲目改名或强制转换，不为猜测另开无信息的 CAD 重跑。

## 实施及验收边界

- SaveAs3 在独立 `codex/saveas3-modern` 实现。当前实现候选 `5a1b48d`，
  原生完整验证 [42369257219](https://github.com/YJBeetle/SWCLI/actions/runs/42369257219)
  在实现线程最近一次快照中运行；本记录未将它声明为已通过。
- 另外两项在独立 `codex/native-api-observation-modern` 实现，分别逻辑提交，
  由统筹本人审查。新配置读取不得改变配置、身份、前台、stamp、dirty或CAS语义；
  新尺寸读取不得把多配置数组的任意首元素当成目标配置值。
- SaveAs3 必须保留真实 bool/errors/warnings，未知旧警告null不能改写成现代接口的0。
  更新本版活跃schema、SDK、fixture及trace审核，历史原始产物和失败不改写。
- 不重试原生失败，不自动回退已弃用接口，不自动回滚或组内重启。
  COM参数绑定和保存重开、实际导出与尺寸/配置读回须有真实SW2025证据，portable不能代替。
- 保留正常原地保存 `IModelDoc2.Save3`。现代保存是否解决GLB缺BIN，仍须实际文件证明。
- 三项迁移纳入当前系列收口；系列完成后再准备发布，发布前由用户最终确认。
