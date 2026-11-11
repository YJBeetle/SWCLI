# 历史 GLB 成功与当前失败对照

2026-11-12：用户确认此前 SWCLI 导出的 GLB 曾在 Blender 中实际导入可用。这是重要的历史成功线索，保留为用户的实际使用观察。用户尚未指出具体文件/运行；现有原件中未找到可把该 Blender 使用记录绑定到某一 SHA 的 receipt，**不擅自把下列装配体认作用户当时导入的文件，也不要求用户复测**。

本次只读核对已有本地 ZIP、原始 receipt、对应已记录 tested-head 源码和 GLB 字节，没有网络查询/CI重跑/CAD或Blender运行。两次历史成功装配体原件已找到、CRC/外层SHA/已保留副本逐字节核对，使用当前严格 BIN/accessor/mesh 解析重放通过。

## 已找到的成功原件

42173065847 与 42199134982 的 `assembly-export.GLB` 完全相同：

- SHA256：`4091246c9af29a4c858ba73e815c9150dbc37d4c4f9e52d6dabbc4f71e345421`。
- 4748B，JSON4000，BIN720；1 mesh、36 indices、24 positions、24 normals、12 triangles；无 Draco/其他 required extension。
- 实际解码包围盒约为 `(-20,-15,0)` 至 `(20,15,10)` mm，和 receipt 中的单组件40×30×10盒子相符。模型包含默认塑料材质和1相机。
- 仓库保存一份[未改动成功原件](../evidence/glb-history-2026-11-12/assembly-export.GLB)。这是网格成功证据；本轮未启动 Blender，所以不新增 Blender 导入验收。

同组 `component-export.GLB` SHA 均为 `2d49602f1bbd443d60b8975d249b4ed8defb5a5948b869eabfddacb1974a2c5c`，3800B，JSON3772/BIN0，声明无URI buffer720；当前严格解析拒绝。保留[原始失败对照](../evidence/glb-history-2026-11-12/component-export.GLB)，不拼接或补写数据。part/assembly 四类几何声明 buffers/bufferViews/accessors/meshes 相等，只有真实字节可判定网格是否存在。

## 文档、宿主和生命周期差异

| 原件/范围 | 文档与源模型 | 保存/重开上下文 | SW/host 与可见状态 | API、GLB结果 |
| --- | --- | --- | --- | --- |
| 42173065847 / 42199134982 成功 assembly | type2，generated.SLDASM，含上述component.SLDPRT唯一组件；Default | 新建→加组件→save-as→in-place save→STL/3MF/AMF/GLB；**GLB在第一次关闭/重开前**。其后rw/RO重开另有收据，没有重开后GLB | 两次SW均33.5.0；owned daemon PID5464/8284；启动缓存Visible=false，导出时实际Visible/UserControl/CIP布尔值未保留 | 记录tested-head源码为旧 IModelDoc2.SaveAs3(Name,0,1)，4748B/BIN720/12tris |
| 同组历史 part | type1，40×30×10矩形拉伸，volume≈12000mm³、6faces/12edges；Default | save-as→close→**RO reopen**新document_id→测量/结构检查→STL/3MF/AMF/GLB | 同一组owned host，与assembly共享报告版本；瞬时可见状态仍unknown | 相同旧API与参数；3800B/BIN0，旧CLI receipt ok=true，当前严格解析失败 |
| 42405530053 modern CI part | type1，同尺寸夹具，独立源文件hash | save-as→close→**RO reopen**→前三格式→唯一GLB失败，尚未创建本轮assembly | SW33.5.0，owned daemon PID3424；Visible=false为启动缓存，实际瞬时unknown；有CIP scope进入/恢复轨迹，无原始布尔值 | extension现代七参；实际True/0/0，但3800B/BIN0，SHA同历史part；当前严格门禁首停 |
| 本地70d8c9e hidden part | type1，同尺寸新夹具，源hash独立 | native save后**仍为原新建可写文档**，未关闭重开；前三格式后单次GLB | SW33.5.0，owned direct-adapter PID8772；harness输入hidden，实际Visible/CIP当时未读 | 现代七参True/0/0；3732B/JSON3704/BIN0，SHA `04b83d8e…da2ba` |
| 本地70d8c9e visible-startup part | type1，同尺寸新夹具，源hash独立 | 同上新建、保存后可写文档；不重开 | SW33.5.0，PID1912；实际Visible=true、CIP=false、UserControl=true、Background=true | 现代七参True/0/0；3732B/JSON3704/BIN0，SHA `7c4b0df7…c75e9` |

历史组中的 part 与 assembly 确在同一 owned host 先后执行，但文档类型、文档身份、RO/重开及装配上下文并不相同，不能当作只改变绑定的一组因果实验。不同运行的源文件 hash 不同；相同几何尺寸和 GLB 声明不等于完全相同原生输入文件。

## 固定源模型 hash

| 原件 | component.SLDPRT | generated.SLDASM |
| --- | --- | --- |
| 42173065847 | `f81d835b3351081b3521392075d04c9fd9736a685d4f1a5885dad232b4d7d7dd`，50325B | `fb43ab674b662efe8544265f4433569829bca84eec651ef2bda78589dc6f7364`，35977B |
| 42199134982 | `0d8c2bc2ebe2f52c8d635f74da72eac280cdde0cd558f50f8f982672c5abab54`，50332B | `0a3bf76a9573077ecd6fcec8c1133eea71f9cc33d3e0fe5ac523217611cb2aa9`，36370B |
| 42405530053 | `dccee2900406901b279297a2e3519966d3bcb558b04215b516f16b8518591079` | 本轮GLB首停，未到达 |
| hidden本地70d | `4f975836ffbf38a58d05802c943701c8bab67f0ae0388b1e913e0a8f1df0f7b5` | 不在该单part夹具范围 |
| visible本地70d | `3eb244dd0d27f98a77f10838be6043a1aef70a24c17e6f07cbc69073189ec292` | 不在该单part夹具范围 |

历史两个component/assembly原生文件的ZIP实际SHA均与原generated_assembly receipt相同。历史CLI命令明确为Python3.12.10 x64；实际COM工作进程解释器路径没有在这些GLB receipt单独记录，不补写。

## API 参数与旧“success”的解释边界

历史两次已记录tested-head为254d1ad/77be93d，读取的Git blob均调用 `int(document.SaveAs3(str(export_path), 0, 1))`，内部路径沿用 `.stem.<uuid>.swcli.GLB`。这是**旧三参API的整数保存错误码**；导出receipt没有原始SaveAs3返回值、api_saved、save_errors或save_warnings，不能回填成现代接口的bool True/0/0。相同源码只有save_error==0才继续，故0只是根据控制流的推断。

当前现代Python路径为 extension.SaveAs3(Name,0,1,显式null IDispatch,显式null IDispatch,两项BYREF I4)，其True/0/0来自实际receipt。后续C#候选保持七参数值和staging字符串，只改变调用路径，并根据实际装机PIA使用[In,Out] ref Int32。

历史part即使BIN0也曾被旧CLI记为ok：本次重放对应旧export_validation源码，历史part和assembly均返回True；旧规则核容器/mesh声明，未验证嵌入buffer实际覆盖。当前严格规则分别拒绝part、接受assembly，且assembly能实际解出网格。**旧报告中存在过宽校验，与确实存在有效的历史GLB输出同时成立。** 这也不能否定用户在Blender中的历史使用观察。

历史API参数依据现存验证文档记录的tested-head及Git源码，不冒充本轮重新核验部署wheel或已有原生参数trace；相关blob SHA都写入结构化证据。历史与当前都报告33.5.0，但旧exe/完整运行时模块hash未齐，不能单凭版本字符串排除环境差异或归因版本；不能把old/modern差异直接当首因。

## 原件与复核入口

[结构化审计](../evidence/glb-history-offline-2026-11-12.json)包含外层ZIP SHA、member CRC、完整GLB SHA/解析、原模型hash、实际document_id与保存/重开事件序号、host原字段、源代码hash及三个近期失败原件。历史原始ZIP仍位于现存 `docprops-export-options/20261107/glb-history-offline/` 两个run目录，未改动。

[复核脚本](audit-glb-history-2026-11-12.py)从这些已有原件重新计算并在临时目录逐字节重放新旧校验；无网络/COM调用。对应最新C#准备见[候选说明](../../scripts/diagnostics/typed_glb/README.md)。用户的Blender文件SHA、确切文档类型、当时软件/宿主状态仍保留未知，不用推测填充，也不在本轮新增运行。
