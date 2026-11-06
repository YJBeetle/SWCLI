# Drawing Line Font defaults (internal calibration pending)

The independent `document.line-font` read and `document.line-font-set` guarded write
surface cover four **drawing document defaults** only:

| Field | Official preference | Bounded write values |
| --- | --- | --- |
| visible_edges.style | swLineFontVisibleEdgesStyle | 0 continuous, 1 hidden |
| visible_edges.weight | swLineFontVisibleEdgesThickness | 0 thin, 1 normal, 2 thick |
| hidden_edges.style | swLineFontHiddenEdgesStyle | 0 continuous, 1 hidden |
| hidden_edges.weight | swLineFontHiddenEdgesThickness | 0 thin, 1 normal, 2 thick |

SOLIDWORKS's documented API is `IModelDocExtension.GetUserPreferenceInteger` /
`SetUserPreferenceInteger`, with `swDetailingNoOptionSpecified`. Preference IDs
are resolved by name from the installed official
`C:\Program Files\SOLIDWORKS\swconst.tlb`; missing or ambiguous enums fail closed.
Reads retain all native integer values, including unsupported/custom sentinels.
No arbitrary preference IDs or global `ISldWorks` settings are accepted.

## Protection and current gate

Public writes always return `DocumentLineFontUncalibrated` without invoking a
setter, including no-op requests. Internal calibration explicitly opts into the
adapter only; there is no protocol parameter, environment variable, or CLI flag
to bypass the gate. Passing portable tests or internal calibration does not open
this gate or establish public acceptance.

Requests use selected document identity, expected update stamp, and existing
lease ownership rules. The complete `expected_options` snapshot contains all
four raw integer values; stale values fail CAS even when SOLIDWORKS's stamp is
unchanged. Writable state and normal sheet context are required. Background
reads/writes preserve foreground, sheet/view/sketch identities, dirty state and
read stamps. A setter runs at most once; failure retains attempted / may-have-
changed receipts, with no retry or rollback. Readback must match the requested
field and preserve all other covered fields.

Example read: `swcli document line-font --document DOCUMENT_ID --json`.
The closed write command accepts `FIELD VALUE --if-options '{...}'` plus the
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
refusal. This is internal calibration, not public CLI end-to-end write acceptance.

## Official API references

- [Document Properties > Line Font](https://help.solidworks.com/2019/english/api/swconst/DP_LineFont.htm)
- [Line styles](https://help.solidworks.com/2025/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swLineStyles_e.html)
- [Line weights](https://help.solidworks.com/2024/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swLineWeights_e.html?id=2.10.1.472)
- [Document integer setter](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IModelDocExtension~SetUserPreferenceInteger.html)

The Line Font page explicitly excludes `swLineDEFAULT` for edge styles. Layer,
custom and negative weight sentinels are not in this write subset.
