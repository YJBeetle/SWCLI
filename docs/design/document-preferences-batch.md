# 文档属性批次公共契约（开发中）

本批在 `codex/document-properties-batch` 隔离开发；起始于 `60c6f463560b2541a17f91e0d6c5d84fe317b8bd`，按用户最新要求已整合到 0.2.4 冻结提交 `a4df72120a951f851e13d1cde569cbc3f754a197`，保留安全连接、工作区文件传输和 Typed Python SDK。尚未发布、尚未完成本批安装后的公共原生门禁。已有 A16/A17/A18 行为保持；本批不能代表整个“选项 → 文档属性”页面完成，剩余类别见[覆盖矩阵](document-properties-coverage.md)。

| 组 | 公共操作 | 明确字段及边界 |
| --- | --- | --- |
| 总注释字体 | `document.annotation-font`、`document.annotation-font-set` | 读取17字段及17原生成员；修改字体名、毫米高度、点数高度、粗体、斜体、下划线、删除线。仅总注释字体19/option0，不扩展为尺寸/表格等所有子类型字体，不承诺现有各注释自动更新或实际字形渲染。 |
| 显示/网格/虚拟交点 | `document.display-options`、`document.display-option-set` | 网格显示、主间距、每主网格细分数、每细分捕捉数、虚拟交点样式，另加基准面前/后颜色、交线颜色、透明度、交线显示。P/A各10项，D仅前5项；颜色保留原生整数，不自行解释RGB通道或宣称显示效果验收。 |
| 总体绘图标准 | `document.drafting-standard`、`document.drafting-standard-set` | 读取已知及未知原生值；写入仅明确校准的类型/来源/目标/固定profile四元组。当前校准白名单为空，真实证明通过后才登记。自定义或未知来源只读，不允许任意`.sldstd`路径、注入reader或原生ID。 |

所有命令使用 `swcli`；MCP沿用0.2.3接口，新六项通过现有 `execute` 与同一操作目录发现，无独立COM旁路；启用客户端workspace时的upload/download工具与本批独立。读操作支持后台显式文档/session，禁止lease参数；写操作要求session写租约、`--if-update-stamp`和字段CAS，原生调用前重复核对文档类型、读写权限和编辑/前台上下文，不自动保存，不重试、不回滚。

字体写命令是 `swcli document annotation-font-set FIELD VALUE --if-font JSON --if-update-stamp STAMP --lease TOKEN`；`--if-font`必须是刚读取的完整17字段 `font` 对象。数值或布尔按字段解析；毫米与点数写会明确核对最终模式。字体对象属性赋值可能已经修改live对象，故partial mutation标记在赋值前设置。备用字号原生表示变化以 `native_normalizations` 明确记录，不推断固定换算；当前生效字号、模式、其他未请求字段和保存重开raw快照保持严格验证。

显示写命令是 `swcli document display-option-set FIELD VALUE --if-value OLD --if-update-stamp STAMP --lease TOKEN`。字段公共单位为毫米；原生米只在内部转换，整数预值保留signed Int32范围，已知写域逐项限定。工程图基准面字段直接拒绝；未知虚拟交点原生值可以读取，但不作为可写值。

标准写命令是 `swcli document drafting-standard-set NAME --if-snapshot JSON --if-update-stamp STAMP --lease TOKEN`；完整snapshot含 `standard` 和 `observed_defaults`。`drafting-defaults-v1`固定覆盖A18七项、总字体17成员、五项原生长度单位、该类型10/5显示项及四个基础标准option。标准切换允许这些默认值联动，返回before/after/final和是否发生联动；该有限profile不宣称捕获所有未观测尺寸/表格/字体设置。整体改动通过后标dirty，最终观察必须与after完全一致。

同值请求必须使用新鲜完整CAS，在clean文档上保持描述符且零属性赋值、零原生setter、零SaveFlag。失败在首次原因停止，并保留是否已经尝试/可能改变的回执；乐观CAS不等于对所有原生客户端的全局原子锁。

安装后的公共门禁复用已准备的P/A/D输入与同一owned隐藏daemon，三组分别保持600秒请求、1800秒组预算。字体每字段独立另存只读重开；标准每个有限转换独立另存只读重开；显示比较全部适用字段后另存重开。每组另核显式lease、版本戳、值冲突、后台状态、clean/dirty同值零写、fresh文档ID、原输入hash、所有保存文件hash与零件几何。公共native trace逐请求核完整getter周期、唯一写入、partial信息及清理，不以私有校准代替公共验收。
