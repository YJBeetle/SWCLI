# STL export options: isolated calibration boundary

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

Ordinary calls fail closed. A newly daemon-owned SOLIDWORKS process is insufficient isolation for per-user global preferences. This branch enables option writes only inside an explicitly opted-in disposable GitHub Windows runner, with a worker-owned hidden process and an exact-one-process inventory. There is no public parameter that can assert isolation or bypass the existing daemon. Public acceptance remains incomplete until a safe non-calibration isolation contract is implemented and accepted.

The existing optionless export contract is preserved. The additive CLI flags are `--stl-encoding`, `--stl-unit`, `--stl-deviation-mm`, `--stl-angle-degrees`. They require an explicit document ID, lease token and fresh `--if-update-stamp`. The SDK exposes the same four-field typed object; MCP forwards it through the same operation and context. Example for the isolated calibration host:

```sh
swcli document export curved.stl --document d-ab12cd --lease l-ab12cd34ef56 --if-update-stamp 7 --strict --stl-encoding binary --stl-unit mm --stl-deviation-mm 0.01 --stl-angle-degrees 0.5 --json
```

## Temporary preference transaction

One serialized COM worker owns the request. A named Windows mutex excludes cooperating STL transactions, and complete process inventory refuses any other SOLIDWORKS instance; the disposable runner supplies isolation from interactive users. Shared/interactive attached hosts are rejected. The worker snapshots the entire coupled preference vector, compares the complete vector again before mutation, selects custom quality and the requested encoding/unit/tolerances, suppresses preview/info dialogs and forces a single output file. Integer/double setters must return true; `ISldWorks.SetUserPreferenceToggle` has an official `void` signature and must return `None` through pywin32. Exact full-vector readback must match before one `SaveAs3` call. Native setter return types/values are retained as evidence.

A `finally` block restores all original values and reads the complete vector again. Restoration touches only the temporary export environment. It does not roll back CAD content. `stl_preferences` retains original/requested/readback/restored vectors, exact constants, mutation-attempt state and cleanup errors. A native exception or nonzero save code remains the primary error even if restoration also fails. Unknown restoration retires the worker; it cannot serve another CAD request.

The existing temporary-file content validation and atomic publication remain. STL encoding is checked against the actual bytes before publication. Source title/path/type/save flag/update stamp/configuration must remain unchanged. On failure, `stl_source_state` records observed partial state or an observation error without hiding the first native failure. Read-only/view-only and unobservable identities are rejected. No CAD rollback or native operation retry occurs.

## Evidence levels

Portable tests cover contract forwarding, finite bounds, STL-only semantics, lease/stamp/read-only refusal, vector CAS/readback, setter partial mutation, mutex contention/abandonment, restoration failure, original error preservation, encoding mismatch and target preservation. Synthetic cylinder tests validate the independent mesh analyzer; they do not validate SOLIDWORKS.

Manual CI input `stl_options_targeted=true`, with `native_full=false`, selects only this branch's internal calibration. It defaults off, requires successful portable/package jobs, retains secret access only inside the repository's existing manual native guard, and uses `swcli-stl-options-${github.ref}` with cancellation disabled. Default full and release behavior retains the original concurrency group and gates. The targeted group has a 1800-second limit and 600-second native requests, one host, no replacement/restart/retry.

The installed verifier creates a radius-10 mm, height-15 mm cylinder through the client/daemon/COM worker, saves/reopens the native part, then exports it in the background while retaining a separate foreground document. Coarse, deviation-only-fine, angle-only-fine and combined-fine outputs must show individual triangle-count/analytic-volume improvement; encoded inch and meter variants must preserve scaled geometry. It parses actual binary/ASCII triangles, measures curved-wall chord error and analytic volume error, verifies source-file SHA256 and exact preference restoration between every output. Reports mark `public_acceptance=false` and `full_acceptance=false`; original files/traces must be retained even after failure.

`ISldWorks.SetUserPreferenceToggle` is [documented as void](https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~SetUserPreferenceToggle.html). This differs from document-extension toggle setters and from the app integer/double setters; their return conventions must not be merged.
