# 42818564935 portable 首错与最小字节捕获修复

旧运行 [42818564935](https://github.com/YJBeetle/SWCLI/actions/runs/42818564935) / 精确 head `473b26a06e09538a4565cc0adb765988f61b44ee` 保持 **failure**。两 Windows 矩阵均仅两个 `test_unit_cli_frontend` compare 断言失败；首个是读取的 fresh/helper 原字节不一致：fresh `b'{\r\n'`，旧 `StringIO` helper `b'{\n'`。不是identity mismatch，也不是native setter或CAD错误。

| 矩阵 | 测试数 | failures | skipped | 耗时 |
| --- | ---: | ---: | ---: | ---: |
| Windows / Python 3.9 | 1960 | 2 | 11 | 245.823s |
| Windows / Python 3.14 | 1960 | 2 | 4 | 184.297s |

最早按时间记录的失败是3.14的 `test_actual_cli_read_changed_and_all_guard_refusals_match_without_restarts`，UTC `2026-11-10T12:49:09.9024458Z`。第二个为 `test_protocol_and_parser_failures_match_without_business_rpc`。native job因portable前置失败而 **skipped，零CAD**；私有校准及公共CLI/SDK/MCP原生case均0，本run没有native原件ZIP。SDK/脚本解析等后续Windows阶段也未到达。不用之前run的CLI139/SDK15补齐这一head。

## 已保存官方原件

统筹下载的原失败日志直接复制，未重复下载；SHA256 `8d614a43c26f600194b6c0fa3e503475acacd73b2cba5667359dfeb11be848a4`。官方terminal run/jobs/artifacts各取一次；四个官方artifact ZIP各下载一次，size/head/run及下载SHA与官方digest全部一致：

- dist `13766028046`，1643447 bytes，SHA256 `a80489c6a9a35bbb8401676ee4b4239d7e5669166f192086e974f7a87d83bde3`。
- package summary `13765898140`，1014 bytes，SHA256 `c6bd22a941b36d48fc23a3e4afd6f1ec30e2c3676d7ebfa356a2d4f8cd78dfe0`。
- portable3.14 summary `13765683939`，1147 bytes，SHA256 `fb4ab17b20811cbe39659bbd42988d04e2c76b6f6da688dca4ac40813c84ada2`。
- portable3.9 summary `13764544642`，1147 bytes，SHA256 `54fec4142a05823656fae925a79e6d886d361821e86f1fc5eeab838759f49223`。

原ZIP和安全解压在 `/Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI/evidence/units-profile/public-frontend-42818564935/artifacts/<id>/`，原日志为同级 `failed.original.log`。原initial snapshot/dispatch记录未修改，新增terminal metadata、digest清单及 `portable-failure-audit.json` 位于同名 `docs/evidence/`。独立标准库审计不导入产品/gate/COM，核原日志、四原ZIP及失败head的git worker源码；复跑一致，错误head/ZIP两个负向检查拒绝。

## 先确认标准writer，再修捕获

Python [TextIOWrapper](https://docs.python.org/3.9/library/io.html#io.TextIOWrapper) 的 `newline=None` 在写出时采用平台默认换行；`StringIO` 不是这个平台字节writer。fresh Windows CRLF与旧helper LF的日志及本地独立writer/CRLF仿真均印证首因。已包含合法中文、真实LF、CRLF与孤立CR；没有对比较或原始字节做replace，也不删除既有CR（标准writer生成的CRCRLF同样保留）。

另外，[隔离模式 `-I`](https://docs.python.org/3.14/using/cmdline.html#cmdoption-I) 忽略PYTHON环境变量，故设置 `PYTHONIOENCODING` 不能证明隔离进程stderr编码。产品 `cli.main` 首先自行reconfigure stdout为UTF-8；stderr遵循该真实进程的启动codec/errors，Windows管道可能使用系统ANSI编码，见 [sys标准流说明](https://docs.python.org/3.14/library/sys.html#sys.stdout)。本机实际 `-I` probe记录 `ignore_environment=1`；本机codec不外推为Windows实测。

只改两个CI helper及关联测试：worker用 `TextIOWrapper(BytesIO, newline=None)` 执行原CLI main，stdout UTF-8、stderr实际codec/errors，flush后拿到原bytes。frame同时携带严格base64原stdout/stderr及只供审计的文本/codec；parent严格base64 decode、严格文本解码核一致后，`CompletedProcess`直接用原bytes，不再由text encode重建stderr。CP932存在不同byte映射同一字符的情况，测试用原 `8790` 与decode再encode的 `81e0` 实证原字节不被重建改变。非法UTF-8仍保留base64原件并拒绝，不替换坏字节。

metadata明示 `platform-text-writers-raw-bytes-base64`，ready记录真实codec、换行策略和base64方式。UTF-8 JSON frame仍严格解码；原identity/PID/version/CLI SHA、序号、未知结果/异常/EOF/超时、raw原件fsync、不重发不重启与一次退出机制未削弱。argv与RPC原bytes、产品CLI/SDK/COM、其他业务helper、137有限域/26后态、三类型独立冷启动读探针、417case、600/1800、geometry及本run句柄收尾均未改。

## 最终本地验证及统筹批准

- 关联90项/25.396s通过：真实fresh CLI/隔离helper TCP字节对照、中文JSON字段和中文多行解析stderr、默认及CRLF独立writer（UTF-8/cp1252/cp932）、不可逆codec原bytes、坏base64/UTF-8/text mismatch拒绝；原guard/417synthetic/三cold probe/生命周期关联全部保留。
- 完整portable1966项/101.419s通过（26skipped）；SDK generator/strict6文件/8个consumer typing拒绝通过；四文件Python3.9 AST及diff检查通过。日志/hash/四源码SHA在 `stdio-fix-validation.json`。
- 统筹另亲跑两stdio/frontend模块17项/9.866s通过并锁定四文件SHA，实际本地四SHA完全匹配。其条件批准：以上检查全部通过、四文件不再变化且无其他业务/src/workflow/geometry/预算变化时，中文提交推送后可自行一次必要新公共验收，派前核远端/干净/同head未派/并发。

本地结果和CRLF仿真不是新Windows portable或CAD通过证明。VM未用、main未合、没有发布。下一次必要CI仍需Windows3.9/3.14实际前置成功、再核新run公共原生417+三额外独立读/同host-worker/持久化/geometry/600-1800及真实退出原件；正常一次初始快照后停，不连续poll，旧失败不翻绿。

```sh
cd /Users/YJBeetle/.codex/worktrees/docprops-units-expanded/SWCLI
python3 docs/verification/audit-units-portable-42818564935.py --metadata-dir docs/evidence/units-profile/public-frontend-42818564935 --raw-dir evidence/units-profile/public-frontend-42818564935 --repo-root .
PYTHONPATH=src:tests /private/tmp/swcli-units-write-env/bin/python -m unittest tests.test_unit_cli_stdio tests.test_unit_cli_frontend -q
```
