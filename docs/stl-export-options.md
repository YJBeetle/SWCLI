# STL export options: bounded native qualification

`document.export` accepts an optional closed `stl_options` object only for `.stl` outputs. All four fields are required, so the requested tessellation does not inherit unknown host defaults:

| Field | SWCLI values / product bounds | Official native setting |
| --- | --- | --- |
| `encoding` | `binary`, `ascii` | `swSTLBinaryFormat` toggle |
| `unit` | `mm`, `cm`, `m`, `inch`, `foot` | `swExportStlUnits`, `swLengthUnit_e` |
| `deviation_mm` | 0.01 through 1.0 mm | `swSTLDeviation`, converted to meters |
| `angle_degrees` | 0.5 through 30 degrees | `swSTLAngleTolerance`, converted to radians |

Custom tolerances also select `swSTLQuality_Custom`. The bounds above are conservative SWCLI limits, not a claim about every model's legal native tolerance range. A native refusal or normalized readback is an error, never a reason to clamp, relax assertions or retry. No STL parameter applies to GLB, AMF or 3MF in this contract.

Official references: [STL option mapping](https://help.solidworks.com/2019/english/api/swconst/filesaveasstloptions.htm), [custom quality enum](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swSTLQuality_e.html), [API units convention](https://help.solidworks.com/2024/english/api/sldworksapiprogguide/Overview/Units.htm?id=1.4.71). Exact preference/quality/unit IDs are loaded by name from the installed `swconst.tlb` during calibration and retained in result evidence.

## Availability

Ordinary/shared/interactive hosts fail closed. Public writes are enabled only with `GITHUB_ACTIONS=true`, `RUNNER_OS=Windows`, `SWCLI_STL_EXCLUSIVE_RUNNER=1`, no internal calibration toggle, an owned hidden worker, exactly one native SOLIDWORKS process, native revision `33.5.0`, exact installed enum mapping, an explicit `d-...` document ID/lease/stamp and one of the six tuples below. `SWCLI_STL_SWCONST` must name the installed official type library. Parts are qualified; assembly options, other native versions, Wine and other platforms remain closed.

The schema bounds in the table above are **candidate bounds**, not a promise that every value inside them is supported. SOLIDWORKS normalized a requested `0.5 mm` deviation to `0.5335936864527374 mm` on the generated cylinder. That request was refused before saving and remains unqualified. No rounding/interpolation/clamping fallback is used. Exact accepted profiles are exposed by `document.export` schema extension `x-swcli-qualified-stl` and by `swcli.stl_calibrated_profiles.PROFILES`:

| Profile | Encoding | Unit | Deviation mm | Angle degrees |
| --- | --- | --- | --- | --- |
| coarse | binary | mm | 0.5335936864527374 | 30 |
| deviation-fine | binary | mm | 0.015392125570752039 | 30 |
| angle-fine | binary | mm | 0.5335936864527374 | 10 |
| fine | binary | mm | 0.015392125570752039 | 10 |
| ascii-inch | ascii | inch | 0.015392125570752039 | 10 |
| binary-meter | binary | m | 0.015392125570752039 | 10 |

A different model may normalize even these physical values. Exact per-request readback still refuses that case before export; qualification does not authorize normalized substitutes. `cm`/`foot`, other combinations and arbitrary tolerances remain unqualified. Internal native evidence passed and was independently audited before this list was opened for the separate public gate; public acceptance is recorded separately in `WORK_HANDOFF.md`.

The existing optionless export contract is preserved. The additive CLI flags are `--stl-encoding`, `--stl-unit`, `--stl-deviation-mm`, `--stl-angle-degrees`. They require an explicit document ID, lease token and fresh `--if-update-stamp`. The SDK exposes the same four-field typed object; MCP forwards it through the same operation and context. Example for the isolated calibration host:

```sh
swcli document export curved.stl --document d-ab12cd --lease l-ab12cd34ef56 --if-update-stamp 7 --strict --stl-encoding binary --stl-unit mm --stl-deviation-mm 0.015392125570752039 --stl-angle-degrees 10 --json
```

## Temporary preference transaction

Worker registration, request isolation and public profile qualification require actual `sys.platform == "win32"`, independently of runner environment labels. The runtime obtains the loaded `ntdll.dll` through [GetModuleHandleW](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getmodulehandlew), verifies the known `NtClose` export, then checks `wine_get_version` through [GetProcAddress](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getprocaddress). Wine is refused. An absent Wine export is accepted only with explicit `ERROR_PROC_NOT_FOUND` (127); missing APIs/modules, exceptions and unknown probe results refuse writes. `ctypes` uses pointer-sized API signatures and `use_last_error=True`. All existing runner opt-in and isolation requirements still apply.

One serialized COM worker owns the request. A named Windows mutex excludes cooperating STL transactions, and complete process inventory refuses any other SOLIDWORKS instance; the disposable runner supplies isolation from interactive users. Shared/interactive attached hosts are rejected. The worker snapshots the entire coupled preference vector, compares the complete vector again before mutation, selects custom quality and the requested encoding/unit/tolerances, suppresses preview/info dialogs and forces a single output file. Integer/double setters must return true; `ISldWorks.SetUserPreferenceToggle` has an official `void` signature and must return `None` through pywin32. Exact full-vector readback must match before one `SaveAs3` call. Native setter return types/values are retained as evidence.

A `finally` block restores all original values and reads the complete vector again. Restoration touches only the temporary export environment. It does not roll back CAD content. `stl_preferences` retains original/requested/readback/restored vectors, exact constants, mutation-attempt state and cleanup errors. A native exception or nonzero save code remains the primary error even if restoration also fails. Unknown restoration retires the worker; it cannot serve another CAD request.

The existing temporary-file content validation and atomic publication remain. STL encoding is checked against the actual bytes before publication. Source title/path/type/save flag/update stamp/configuration must remain unchanged. On failure, `stl_source_state` records observed partial state or an observation error without hiding the first native failure. Read-only/view-only and unobservable identities are rejected. No CAD rollback or native operation retry occurs.

## Evidence levels

Portable tests cover contract forwarding, finite bounds, STL-only semantics, lease/stamp/read-only refusal, vector CAS/readback, setter partial mutation, mutex contention/abandonment, restoration failure, original error preservation, encoding mismatch and target preservation. Synthetic cylinder tests validate the independent mesh analyzer; they do not validate SOLIDWORKS.

Manual CI input `stl_options_targeted=true`, with `native_full=false`, selects only this branch's internal calibration. It defaults off, requires successful portable/package jobs, retains secret access only inside the repository's existing manual native guard, and uses `swcli-stl-options-${github.ref}` with cancellation disabled. Default full and release behavior retains the original concurrency group and gates. The targeted group has a 1800-second limit and 600-second native requests, one host, no replacement/restart/retry.

The installed verifier creates a radius-10 mm, height-15 mm cylinder through the client/daemon/COM worker, saves/reopens the native part, then exports it in the background while retaining a separate foreground document. Coarse, deviation-only-fine, angle-only-fine and combined-fine outputs must show individual triangle-count/analytic-volume improvement; encoded inch and meter variants must preserve scaled geometry. It parses actual binary/ASCII triangles, measures curved-wall chord error and analytic volume error, verifies source-file SHA256 and exact preference restoration between every output. Internal reports mark `public_acceptance=false` and `full_acceptance=false`; original files/traces must be retained even after failure.

`ISldWorks.SetUserPreferenceToggle` is [documented as void](https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~SetUserPreferenceToggle.html). This differs from document-extension toggle setters and from the app integer/double setters; their return conventions must not be merged.

The separate default-off manual input `stl_options_public=true` (with both `stl_options_targeted=false` and `native_full=false`) runs the installed public CLI plus SDK/MCP on a fresh exclusive runner without `SWCLI_STL_CALIBRATION`. It repeats the six qualified cases, checks SDK/MCP fine output, exact foreground/current catalog restoration and stale-stamp/foreign-lease/unproven-profile/read-only refusals. Its concurrency group is separate from internal calibration and default full/release. It must pass independent retained-byte/trace audit before this branch is called public accepted or merge-ready.

The internal qualification is [run 42272270166](https://github.com/YJBeetle/SWCLI/actions/runs/42272270166), head `d8df4a874cc0c8460cf8615964420e7e9c20ff7b`. Independent analysis found 48 coarse triangles, 232 deviation-fine/fine triangles and 144 angle-fine triangles; max curved-wall chord errors were 0.3407421, 0.0151856 and 0.0380535 mm respectively. Inch ASCII and meter binary variants retained 232 triangles and matching scaled volume. Installed wheel backend files were byte-compared to that exact git head. The native ZIP/report/trace/source hashes are pinned in the qualification module and preserved with original files locally.

## Bounded public acceptance

[Public run 42279951554](https://github.com/YJBeetle/SWCLI/actions/runs/42279951554) passed at code head `2bc0504fd3889d920c091961a26b31c61e03e67d`. Retained original native/dist ZIP digests matched GitHub; thirteen installed wheel source files matched that exact head. The public evidence used no internal-calibration toggle. Its eight outputs covered the six CLI tuples, typed TCP SDK and official MCP SDK stdio; each had one native save, exact requested/readback preferences and full verified restoration. All four stale-stamp/foreign-lease/unqualified-tuple/read-only refusals had no preference setter or export call. Native source save/reopen, unchanged bytes and exact foreground/current/configuration/stamp were verified. The existing independent retained-byte/trace audit passed.

Native original ZIP SHA256: `54a228101376c5ec081100045460b8a474aedee3b5490f3fedf9175112644085`. Distribution ZIP SHA256: `19352cf06e0f74d18760d7e014ebe8c63c04aace4c088216334bbd2cd5fb02b9`. Persistent paths and report/trace/source/audit digests are in `WORK_HANDOFF.md`.

Acceptance is limited to the explicit environment and exact tuples above. It is not general desktop/Wine/assembly/continuous-range support or overall series/release acceptance. Final review/integration remains coordinator-owned; the series must meet its complete frozen scope before a release.

The coordinator identified a missing actual Windows/Wine probe after the old public run. The original run remains evidence for its old head; the added fail-closed platform probe requires a new matching-head public gate before integration. See the current status at the top of `WORK_HANDOFF.md`.
