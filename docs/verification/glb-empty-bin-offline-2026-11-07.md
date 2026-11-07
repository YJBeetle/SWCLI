# GLB 空 BIN 的历史原件离线核查

本轮只读取现存历史原件、导出调用源码及官方文档。文档品质已由统筹合入 main `c1b251b326c39e426e8eb82fcd8109e0a9e577ca`，其已验收范围冻结。GLB 导出仍是当前系列的未完成项。

## 原始完整验收对照

两份 ZIP 的 SHA-256 均与仓库对应验收记录中的原件 digest 相符。原 ZIP、两份 GLB 和原 modeling.json 已复制到持久证据目录，复制后再次核 hash。

| 原运行 | 原 ZIP SHA-256 | 隐藏宿主 | 零件 BIN | 装配 BIN |
| --- | --- | --- | --- | --- |
| 42173065847 / a18 | `ef7dee25e3d995c5cc918d8a41d8d2cb4fc08a59f574fe6c941e12f8f4c323f4` | Windows 33.5.0，owned，visible=false | 0 / 声明720 bytes | 720 / 声明720 bytes |
| 42199134982 / 0.2.0a1 | `bb200e9a0fd5e67381107c69fdc333aabe96086b9cd1898c5a9aa3dfcea060b5` | Windows 33.5.0，owned，visible=false | 0 / 声明720 bytes | 720 / 声明720 bytes |

两个运行的对应 GLB 字节完全相同。

- `component-export.GLB` 为3800 bytes，SHA-256 `2d49602f1bbd443d60b8975d249b4ed8defb5a5948b869eabfddacb1974a2c5c`。JSON chunk 3772 bytes，BIN chunk 0。当前严格 validator 拒绝该文件。历史回执中的 ok=true 来自此前只验证 mesh 声明的容器检查。
- `assembly-export.GLB` 为4748 bytes，SHA-256 `4091246c9af29a4c858ba73e815c9150dbc37d4c4f9e52d6dabbc4f71e345421`。JSON chunk 4000 bytes，BIN chunk 720。严格诊断器实际读取 positions、normals、indices，得到24 positions、24 normals、36 indices、12 triangles。
- 同一运行的两份文件在 buffers、bufferViews、accessors、meshes 四部分完全相同。零件输出只有声明可供比较，不能用声明计数补足缺失网格。装配实际二进制与这些声明匹配。
- 两个 GLB 导出回执的 target 均 active=true、current=true，且源文件 clean。历史建模组先按 STL、3MF、AMF、GLB 顺序导出零件，再在生成装配后按相同顺序导出装配。该组没有 document.render 请求。
- 两份源码来源均已使用 owned host 的 `native_api_sequence`。当前导出经 `temporary_activation`，在 SaveAs3 调用期间激活选定目标，再恢复前台文档。因此现有失败的最终回执 active=false 不能说明 SaveAs3 对后台句柄直接执行。

历史完整回执的“导出通过”不能直接充当零件 GLB 的有效二进制网格证明。严格检查后，历史零件文件也被拒绝。此缺陷早于本轮 image-quality 字段。

## 与当前圆柱失败的联系

当前 42301795947 的 `cylinder-coarse.invalid-native.glb` 宣称3696 buffer bytes，BIN实际0。它与42265919228的原 GLB 完全相同，虽然前者使用ASCII单扩展暂存名，后者使用旧多点暂存名。因此暂存文件名假设已被原字节对照否定。

历史装配在同一隐藏宿主生成了实际二进制，说明隐藏状态不能单独解释所有输出。历史零件 active=true 仍有空BIN，说明目标激活也不能单独解释该缺陷。零件和装配的缓存/序列化路径差异仍需区分。

## 官方 API 与图形依赖

当前实现调用 `IModelDoc2.SaveAs3(path, 0, 1)`，返回整数错误码。官方将该方法标为 obsolete，推荐后继为 `IModelDocExtension.SaveAs`。这提供了一个有据的调用路径差异，尚不能据此断言后继方法会修复空BIN。[IModelDoc2.SaveAs3](https://help.solidworks.com/2016/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldoc2~saveas3.html)

`IModelDocExtension.SaveAs` 用扩展名决定格式，返回 bool 和独立 errors/warnings。其 ExportData 文档说明 PDF 数据。已核的 `swExportDataFileType_e` 仅列 `swExportPdfData=1`，未提供 GLTF ExportData 对象依据。GLB 六个XR选项的公开自动化映射继续未证实。[SaveAs](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SaveAs.html) [ExportData enum](https://help.solidworks.com/2024/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swExportDataFileType_e.html)

官方 OpenDoc7 文档说明，打开模型会创建 SceneGraph，零件与装配不共享相同的 SceneGraph buffer。DocumentVisible控制加载时的文档显示状态，隐形创建的文档需要关闭并重新打开才能显示。它与应用级 Visible 是不同设置。此信息支持分别检查零件/装配的图形缓存，但目前没有原生 cache/triangle 读数证明本次空BIN源于图形缓存。源码路径未发现调用 DocumentVisible。[OpenDoc7](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~OpenDoc7.html) [DocumentVisible](https://help.solidworks.com/2022/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~documentvisible.html)

`IPartDoc.GetTessTriangles` 提供图形显示三角形。它可以作为以后区分“图形数据是否存在”和“导出是否写入BIN”的只读观测，不能替代原生GLB产物或作为凭空修补BIN的数据源。[GetTessTriangles](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IPartDoc~GetTessTriangles.html?format=P&value=)

## 已定位范围与未证明首因

已确认历史零件GLB一直存在同形缺数据问题，同宿主装配可写出实际网格。文件名、隐藏宿主这一单条件、后台目标这一单条件均不足以解释现象。根因尚不能在旧SaveAs3调用路径与零件SceneGraph/序列化行为间定案。

下一次相关原生验证应首先只隔离旧 `IModelDoc2.SaveAs3` 与官方后继 `IModelDocExtension.SaveAs` 的调用路径，固定原生输入、隐藏状态和导出选项，每个受控输入一次调用并保留原 errors/warnings、源状态与严格BIN解码。图形数据观测用于解释结果。该验证属于当前GLB首因核查，尚未派发。本轮产品源码与已验收字段均未更改。

## 独立离线复跑

持久根为 `/Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107`。

- 脚本为 `audit-glb-history.py`。
- 结果为 `glb-history-offline/comparison.json`。
- 每个运行的原ZIP、GLB、modeling.json位于 `glb-history-offline/42173065847` 和 `glb-history-offline/42199134982`。
- 新原件缺BIN对照仍位于 `run-42301795947/independent-glb-first-failure.json`。

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-export-options/SWCLI
PYTHONPATH=src:scripts/ci /private/tmp/swcli-a14-test-env/bin/python \
  /Users/YJBeetle/.codex/task-artifacts/docprops-export-options/20261107/audit-glb-history.py
```

离线脚本直接读取已核hash的完整ZIP，只对实际BIN进行网格解析。重复运行使用持久ZIP，更新独立离线摘要，原ZIP字节不变。
