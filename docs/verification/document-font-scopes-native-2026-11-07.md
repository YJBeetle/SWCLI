# 默认字体范围原生验证记录

状态：**尚未验收、尚非 merge-ready，公开写入保持 fail closed**。

## 首轮：42262037827

- [GitHub run](https://github.com/YJBeetle/SWCLI/actions/runs/42262037827)，head `a1860400953c85cf1cdbd6ca5229ae4c07c6c25d`。
- 参数 `calibrate_font_scopes=true,native_full=false`，目标本分支；普通 portable/package/full-native/release 跳过，Windows 字体便携检查通过。
- 安装 SOLIDWORKS `33.5.0`；内部组 24.058 秒，首失败停止，cleanup 无错误，无 API 重试/回滚/宿主重启。
- 原 artifact ID `13525673864`，ZIP SHA-256 `174f27e8e10a31e153ab0945c7553361a4a65d6d8558f4748f0b299a89097df3`，独立下载重算与 GitHub digest 一致。
- 原 ZIP、解包文件、元数据和独立 trace 审计保存在本 worktree 的 `artifacts/font-scopes/run-42262037827-*`，原文件未改写。
- 只运行到 PRT：三范围各 typeface、bold、italic、underline、strikeout、height_mm，共 18 次变化写入与原生读回。每次已独立匹配唯一 request、1 属性赋值、1 文档 setter、12 次字体 getter，CAS 与其他范围/字段、背景状态保持。
- 未到字号 points、改变后 save/reopen、ASM 或 DRW；不能将上述局部通过升级为范围可写验收。
- 实测官方符号为：dimensions `1/200`，notes `0/0`，tables `17/0`，annotations `19/0`（preference/option）。
- 源夹具 SHA-256 `7523b8d2efcc651c58331152406e6c0c5fc8df6a152c170053acfa3e41cfb67f` 前后相同。

第一真实失败：新校准器把两次打开实例的 metrics 字典逐位比较。
实体数 `1`、体积 `11999.999999999998 mm³`、面积 `3799.9999999999995 mm²` 全部精确相同；
仅 Y 质心从 `6.286572655403011e-16` 到 `5.514537417020185e-16 mm`，差 `-7.720352383828262e-17 mm`。
此结果保留为失败，没有通过重新解释原产物改为成功。

## 经用户批准的修复

用户明确批准替换此新增逐位比较并做一次修复校准：
记录同一 writable 实例写前几何，直接复用现有 `verify-document-annotations.py::same_geometry`。
原固定标准为实体数精确、体积/面积 rel=1e-9 abs=1e-6、质心 abs=1e-6 mm；没有改动该 helper。
既有 analytic box 断言保留，并增加毫米和磅值模式保存重开后的几何比较。
新增便携回归保留首失败数值，另断言实体数量、体积、面积、1e-5 mm 质心偏移均被拒绝。

后续结果必须以新的精确 head 和新原产物记录；当前不宣称原生、继承或公共 CLI 门禁完成。
