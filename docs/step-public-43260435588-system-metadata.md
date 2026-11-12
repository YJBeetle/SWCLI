# 43260435588：保留首失败并核对六种系统目录

本轮只做离线原件审计、已安装官方帮助核对和本地候选准备。没有新增推送、CI、VM、CAD 或未修改重试。当前公共原生验收仍失败，不能把静态审计通过写成 8/8。

## 新原件与首失败

[机器审计](evidence/step-public-43260435588-audit.json)固定 [run 43260435588](https://github.com/YJBeetle/SWCLI/actions/runs/43260435588)、head `bcb6237d27b87aa09010e20d2613cad31ecb45b3`、job 131332551714、artifact 13965037252。原 ZIP SHA256 为 `0712bc46320cd6499710884f07e96c66545e760c8d1a82782de2fddf6ec9d0f3`，job 日志 SHA256 为 `5bd143bbc284e649ff3d27e1517274871f8a3219830670a2860907622fb45c8f`。脚本核对保留的 run/jobs/artifact/dispatch 元数据与全部 106 个展开文件；原件存于忽略目录 `step-evidence/public-original-43260435588/`。本地 dispatch 记录为一次，不用它推断其他人的全局 dispatch 历史。

writer 成功生成 8 份公开输出，文件哈希与实际 8 次 native SaveAs3 配对均核对；wire 原始 STEP 的 12/320mm、18/560mm 向量也一致。reader 计划 8、开始 2、完成 1，其余 6 项未尝试。

- case0 AP203 实体：导入返回文档/errors0，体积/面积/质心、native 保存、只读重开 errors/warnings0 与 clean 状态均通过。保存文件 46355 bytes，SHA256 `a1a5a31ed64febef5c6c57bcb009ceb6476ba994f5b1f248f6b94399d4ba8790`；save_warnings 原值为 null，不补写成 0。
- case1 AP203 wire：唯一预选 227/明确 NULL 调用返回 CDispatch/errors0；按原返回包装完成。观察器先记录 CommentsFolder（ID8），再记录 FavoriteFolder（ID23、Favorites、depth0），随即严格拒绝该未知类型。原业务错误是 `Sketch observer refused: unexpected feature type FavoriteFolder`。
- 此时尚未读取草图健康码、GetSketchSegments 或 GetLength，也未执行 wire native 保存或重开。`complete=false`、0 段、空向量只是首停前的部分记录，**不是物理空几何或通过**。FavoriteFolder 的子节点也尚未枚举，不能推断其后有哪些或没有哪些节点。

相对 e039 的唯一偏好候选 NeutralFree=true 后，这个样本现在返回 wire 文档；这是一项观测进展，尚不证明全部文件的 translator 优先级或根因已完全解决。两项仍各一次 LoadFile4；八值 CAS、112/14 和 104/13 的 reads/stages、3 项 owned 写入及反序恢复完整。主 trace 604 行/302 配对，唯一 error 位于上述观察器；观察 trace 98 行/49 配对，无 error。六项源码哈希精确匹配 bcb6237 的 Git LF→CRLF checkout 字节，不声称原始 LF 哈希相等或 native DLL 内存证明。owned reader1924/writer9664 均 33.5.0，cleanup[]、Exit/wait/handle close 完成；没有全局进程清单证明。

## 六种目录的精确依据

[可复核来源表](evidence/step-system-metadata-types.json)将**实际类型字符串**与**官方 UI 目录语义**连接起来，属于明确说明依据的分类推断。安装的 2025 API `IFeature.GetTypeName2` 表没有列出以下六个内部字符串；不得杜撰 FavoriteFolder→ISelectionSetFolder 或其他 GetSpecificFeature2 映射。Selection Sets 和 Favorites 是两个不同的目录。

以下类型都已在保留的 33.5.0 Windows 原件 run42365535291/head `d6505f7384911b43b28a5f273ab14262032c4698`、artifact13571478417 中实际观察到。其 ZIP SHA256 为 `b2e70c0786e67a9e97ff7a0af60234516eb2fd2a4884bf9b8506d7e6c9af1475`。这是同修订旧宿主 PID4924 的证据，不是本次 PID1924 或同一 Windows 镜像的证明，更不改变旧失败。

| GetTypeName2 精确值 | 原件显示名与位置 | 官方帮助语义；仅允许容器节点本身 |
| --- | --- | --- |
| FavoriteFolder | Favorites，ID23，depth0 | [Favorites](https://help.solidworks.com/2025/English/SolidWorks/sldworks/c_fmdt_favorites.htm)引用常用特征、草图、参考几何；编辑影响树中同一对象的各个实例 |
| HistoryFolder | History，ID24，depth0 | [History](https://help.solidworks.com/2025/English/SolidWorks/sldworks/t_accessing_recent_features.htm)提供最近创建或编辑特征的访问入口 |
| SelectionSetFolder | Selection Sets，ID25，depth0 | [Selection Sets](https://help.solidworks.com/2025/English/SolidWorks/sldworks/c_selection_sets.htm)保存已有项目的选择集合 |
| SensorFolder | Sensors，ID22，depth0 | [Sensors](https://help.solidworks.com/2025/English/SolidWorks/sldworks/c_Sensors_OH.htm)容纳属性监视与警戒值 |
| InkMarkupFolder | Markups，ID21，depth0 | [Markups](https://help.solidworks.com/2025/English/SolidWorks/sldworks/r_markups.htm)组织协作标注及图片/PDF 输出 |
| NotesAreaFtrFolder | Notes，ID17，parent1/depth1；还观察到同类型 `Notes1___EndTag___` | [Notes Area](https://help.solidworks.com/2025/English/SolidWorks/sldworks/c_annotation_view_flat_to_screen.htm)容纳 Annotations 下的注释区域视图；没有按结束标记名称跳过任意类型 |

以上六页均从已安装 2025 简体中文 UI CHM 只读提取，CHM SHA256 `27ae6a82721af973bf67acd16964bd34f881fbfe2f83740d5432c2bfa4b8c8bd`。API CHM SHA256 `3a46af7f0c11e958661beecc22158fedc360939193f5d967182724c9ddbec24e`，GetTypeName2 页 SHA256 `6184824334d62e2ebccebf62c0f7e1adcd25408ccaeb3581f9c4ae0a32d0505d`。来源表保留各页的完整成员名、字节数、SHA256、旧原件 JSON 路径及各显示名例子；网页访问受版本路由影响时仍以已核哈希的安装帮助为本轮依据。

## 修复边界

候选只给显式草图观察器增加上述六个精确容器类型。`_wire_features` 保持完整顶层和子树遍历、native ID 去重及循环/深度限制。遇到目录只跳过该节点的长度测量，生成器恢复后仍枚举其全部子节点；不会按 `*Folder`、大小写近似、显示名或结束标记名称放行，也不剪枝。

子节点仍只接受既有两种草图，先核 GetErrorCode2 精确整数0，再读取长度；未知几何、混合 reference、空草图、9/260、不完整12/18向量、健康错误、保存/只读重开或哈希问题均失败。生产 STEP 导出保护、默认 reference 诊断、导入绑定、偏好组合和 CI 入口均不在本次修复中更改。候选需要后续统筹亲审，当前没有新的 native 通过证据。

离线复核入口：`scripts/ci/audit-step-public-43260435588.py --bundle <固定原件目录> --output <原件目录外报告>`；六类型来源入口：`scripts/ci/audit-step-system-metadata.py --original <42365535291原ZIP> --ui-chm <安装sldworks.chm> --api-chm <安装sldworksapi.chm> --output <来源报告>`。对临时替换 ZIP 的负向检查已确认拒绝；原 ZIP 从未为该检查改写。
