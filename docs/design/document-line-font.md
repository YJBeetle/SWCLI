# Drawing Line Font defaults

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
Public writes require a positively identified native Windows host, exact host
revision **33.5.0**, and these conversions:
visible style 0→1, visible weight 1→0, hidden style 1→0, hidden weight 0→1.
Same-value 0/1 requests are observations with no setter. Reverse conversions,
other versions, weight 2, custom and layer sentinels remain closed. The adapter's
internal calibration flag is not a protocol or CLI parameter.

Public CLI/daemon save/reopen validation is a separate gate; internal
calibration does not establish public acceptance. Public run [42282239432](https://github.com/YJBeetle/SWCLI/actions/runs/42282239432)
passed at product head `80b61334537d9394b19da03dee9d7baa08da58e8`. Its original ZIP,
metadata, trace, file hashes and foreground observations passed local first-level
artifact checks; final integration review belongs to the orchestrator. This is
the bounded subset described here, not full-series release acceptance. Dispatch `line_font_public=true`
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

## Partial receipts and same-object foreground protection

The adapter snapshots target title/path/access and confirms the live document
remains open. A distinct foreground peer must preserve kind, configuration,
update stamp, dirty flag, title/path, access and the existing sketch/sheet editing context. An unchanged
ActiveDoc pointer alone is insufficient. Unreadable state fails closed. Detected
drift is not restored or rolled back; a previously attempted setter retains its
partial mutation receipt. When the target itself is foreground, its legitimate
stamp/dirty changes remain allowed while identity/access/context stay protected.

If document descriptor finalization fails after adapter return, the handler
returns `ok=false`, preserves the original `mutation` and original `error` exactly,
and adds optional typed `finalization_error: {type, message}`. It does not fabricate
a post-operation document descriptor. The real worker error envelope, SDK and MCP
bridge retain that partial result. Portable fault-injection evidence covers both
native success and first business failure followed by descriptor failure; those
mocks do not constitute native acceptance.

## Native Windows host boundary

Every setter request, including same-value noops and private calibration, first
requires the real `sys.platform == "win32"`. The adapter loads kernel32 with
`use_last_error=True`, obtains the loaded ntdll module with `GetModuleHandleW`,
and verifies the known `NtClose` export through `GetProcAddress`. It then clears
the last error and queries `wine_get_version`. Only a null address with exactly
`ERROR_PROC_NOT_FOUND` (127) admits writes. No queried export is invoked.

A Wine export, missing module/known export, lookup errors 0/5/126, probe
exceptions, non-Windows platforms, and unknown results fail closed before any
preference getter/setter, dirty marking, or save. The revision check alone never
establishes this host boundary. Read requests retain their previous state
protection and do not invoke this host probe. All existing CAS, lease/stamp,
foreground, identity/access, edit-context and partial-receipt guards remain.

The earlier successful public run at `80b6133` predates this host fix and does
not establish acceptance for the changed product. A separate exact-head public
gate is required before integration review can close. Portable OS-probe tests
are fault-injection evidence, not native Windows acceptance.

Official Win32 references: [GetModuleHandleW](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getmodulehandlew),
[GetProcAddress](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getprocaddress),
and [system error codes](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-).
