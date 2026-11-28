# Linear 尺寸字体读回

`swcli document font-scopes --include-linear --document d-xxxxxx --json`
在原生 Windows SOLIDWORKS 33.5.0 工程图上附加顶层 `linear` 观测值。
`fonts.dimensions` 始终使用总默认 `swDetailingDimension`。原有四范围
`fonts` 以及 Notes 的四范围 CAS 继续使用相同结构。Linear 通过
`swDetailingDimensionTextFormat` 和 `swDetailingLinearDimension` 读取，
以已安装 `swconst.tlb` 为准。

## 原生依据

基线 `4b9f48b39bb44fad7f3fe3394c378e7dc101ad29`，SOLIDWORKS 33.5.0。
工程图由安装的 GB 模板生成，是单页无模型视图且有两个水平显示尺寸的专用样件。
源图 SHA-256 `e6f442b605320ac1209d80a4893bf2e00591ae0616c12a3f6311fe3d84b0a35e`，
只读重开产物 SHA-256 `7edfcb6bdac65fe3740ab86cbe474bd04e3e2bdd6fa204e2d1c35ea6d586b097`，
完整 Windows 证据 ZIP SHA-256 `0ac09be1cc9d186cefb09b9c4813dcbebe7458044fdac776c414ed20fc6da798`。
只改 Linear 的 typeface 后，setter 后、保存前和实际只读重开时 D1 的继承字体和
显示字体均为 Arial 3.5 mm，总默认和 D2 的 17 项原始格式保持。Linear 的
非活动点数从 13 变成 14，活动高度和单位保持。

公开只读验收使用候选 `e7d8c1b67b77e21b0330219fc0a727df8244b2c0`。
安装态 `swcli.exe` 经同一独立 daemon 和同一 SOLIDWORKS 宿主打开并读回工程图，
核对实际只读、文档身份、更新戳、旧四范围快照和原文件摘要。默认调用的字体结果仍为
既有的 `fonts`，显式调用另外返回 Arial 3.5 mm，尺寸总默认仍为 Century Gothic 3.5 mm。
八项实际命令和两个进程的终态检查均通过。验收原始 ZIP 的 SHA-256 为
`0334650ab4c1b1da0f3367639478fff6e7388e0fcf8f968fcf441297b3f5fae4`。

## 写入边界

公开 `document.font-scope-set` 仍只支持既有 Notes 写入配置，Linear 既不在
写入枚举内，也不进入既有四范围 CAS。已验证的对照仅支持固定 GB 样件的
水平尺寸。公开接口还没有经过原生验证、能可靠确认普通工程图全部受影响尺寸及
局部覆盖的资格检查，因此暂无 Linear 公开写入配置。

候选包附带可运行的固定源图对照，使用独立证据目录和 owned 宿主。按照包内说明
以候选原生运行一次，先验收公开读回与拒写，再对固定副本执行仅限 typeface 的内部
对照。操作结束后保留首错、保存产物和清理回执，以独立审计核对。
