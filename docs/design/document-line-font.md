# Drawing Line Font defaults (internal evidence audited; public acceptance pending)

The independent `document.line-font` read and `document.line-font-set` guarded write
surface cover four **drawing document defaults** only:

| Field | Official preference | Bounded write values |
| --- | --- | --- |
| visible_edges.style | swLineFontVisibleEdgesStyle | 0 continuous, 1 hidden |
| visible_edges.weight | swLineFontVisibleEdgesThickness | 0 thin, 1 normal |
| hidden_edges.style | swLineFontHiddenEdgesStyle | 0 continuous, 1 hidden |
| hidden_edges.weight | swLineFontHiddenEdgesThickness | 0 thin, 1 normal |

SOLIDWORKS's documented API is `IModelDocExtension.GetUserPreferenceInteger` /
`SetUserPreferenceInteger`, with `swDetailingNoOptionSpecified`. Preference IDs
are resolved by name from the installed official
`C:\Program Files\SOLIDWORKS\swconst.tlb`; missing or ambiguous enums fail closed.
Reads retain all native integer values, including unsupported/custom sentinels.
No arbitrary preference IDs or global `ISldWorks` settings are accepted.

## Protection and current gate

Internal evidence from [run 42260712677](https://github.com/YJBeetle/SWCLI/actions/runs/42260712677)
was independently audited against head `6f531a595a50bbadeeab2c0f005d89c0246c7ee5`,
original artifact digest, per-request trace, and saved/reopened fixture digest.
Public writes are limited to exact host revision **33.5.0** and these conversions:
visible style 0→1, visible weight 1→0, hidden style 1→0, hidden weight 0→1.
Same-value 0/1 requests are observations with no setter. Reverse conversions,
other versions, weight 2, custom and layer sentinels remain closed. The adapter's
internal calibration flag is not a protocol or CLI parameter.

Public CLI/daemon save/reopen validation remains a separate gate; internal
calibration does not establish public acceptance. Dispatch `line_font_public=true`
on this branch only, with `line_font_calibration=false`, `native_full=false`.
It has an independent concurrency group and skips unrelated full gates.
SDK typed read/noop and MCP live bridge execute/noop are included; MCP stdio
transport is not claimed by this gate.

Requests use selected document identity, expected update stamp, and existing
lease ownership rules. The complete `expected_options` snapshot contains all
four raw integer values; stale values fail CAS even when SOLIDWORKS's stamp is
unchanged. Writable state and normal sheet context are required. Background
reads/writes preserve foreground, sheet/view/sketch identities, dirty state and
read stamps. A setter runs at most once; failure retains attempted / may-have-
changed receipts, with no retry or rollback. Readback must match the requested
field and preserve all other covered fields.

Example read: `swcli document line-font --document DOCUMENT_ID --json`.
The guarded write command accepts `FIELD VALUE --if-options '{...}'` plus the
usual document/lease/update-stamp options. The Python SDK and MCP catalog expose
the same schemas.

Excluded: parts/assemblies, custom physical thickness, weight-table editing,
end caps, entities/layers/components, line-pattern definitions, annotation
arrows, grid/plane display, global system options. The current implementation
supports only the standard installed swconst location above.

## Native calibration

Dispatch `CI` on `codex/docprops-line-style` with `line_font_calibration=true`,
`native_full=false`. This selects the installed Windows calibration only and
skips unrelated full native modeling/property/annotation gates. Private native
jobs remain unavailable to PR events. Stages stop on first failure, with 600s
native stage and 1800s group budgets, no restart/retry/rollback. Original report,
trace, process log and saved fixture are uploaded by the existing evidence step.
The fixture uses one owned host, a background drawing, a separate foreground
part, four single-field changes, public write refusal, save/reopen and readonly
refusal. This is internal calibration, not public CLI end-to-end write acceptance. The original closed-gate proof is retained in the historical artifact; subsequent internal runs do not invoke a public mutation on an already calibrated revision.

## Official API references

- [Document Properties > Line Font](https://help.solidworks.com/2019/english/api/swconst/DP_LineFont.htm)
- [Line styles](https://help.solidworks.com/2025/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swLineStyles_e.html)
- [Line weights](https://help.solidworks.com/2024/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swLineWeights_e.html?id=2.10.1.472)
- [Document integer setter](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IModelDocExtension~SetUserPreferenceInteger.html)

The Line Font page explicitly excludes `swLineDEFAULT` for edge styles. Layer,
custom and negative weight sentinels are not in this write subset.
