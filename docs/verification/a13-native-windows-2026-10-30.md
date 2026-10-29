# a13 多边形原生证明（内部校准）

Windows CI [40966909385](https://github.com/YJBeetle/SWCLI/actions/runs/40966909385)
在提交 `0f24eb714b9cd0a0973fdf1063301eaf46379b68` 整条成功。
原生回执来自 artifact `12941260274`，ZIP SHA256：
`9c3f80d4e0cc7bd0226db68655d9f9dc6cace5ffdbb026d4d345c6e981b1c0a8`。
`polygon-calibration/report.json` SHA256：
`2b8779e4fd92d90a3c71558f266b9ff15b3cd1fabce6d6b2af53c74fba541f92`。

独立下载核对三角形/L 形 × 顺逆时针 × boss/blind cut × front/top/right × 正反向
全部 48 例。单个隐藏 owned SOLIDWORKS 33.5.0 宿主连续执行，无组内重启或失败重试。
所有原生轮廓恰有一个 `IsClosed=true` contour，全部非构造直线形成请求端点的唯一闭环。
创建与只读重开后的解析体积、表面积逐项复核，最大绝对差为
`1.8189894035458565e-12`；质心通过原生 MathPoint/ModelToSketchTransform 独立校验。
48 个 SLDPRT 的 SHA256 与回执一致，重开诊断健康且未截断，保存状态和文件哈希不变，
`cleanup_errors=[]`。后续现有 full19 也成功。

这次使用内部原生适配器，`full_acceptance_eligible=false`，没有通过公共
`sketch.polygon` 或安装后的公共多边形 CLI。后续 full19 必须包含公共 polygon-model
48 例，Windows 与 Wine 分别取得完整回执后才可宣称 a13 公共能力已验收。
MacSW 未参与这轮验证。
