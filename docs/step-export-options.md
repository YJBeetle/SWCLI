# STEP export options

`document.export` accepts `step_protocol` (`ap203`, `ap214`) together with
`step_geometry` (`solid-surface`, `wireframe`, `wireframe-sketches`). Both are
required when either is present, only for `.step`/`.stp`. AP242 and unknown
fields/values are rejected before native export. Omitting both preserves the
existing export behavior. These options currently support saved, rebuilt,
writable parts outside sketch editing; assemblies remain fail closed.

The development branch enables **native Windows SOLIDWORKS revision `33.5.0`
only** for the separate public acceptance gate. Other revisions return
`StepCalibrationRequired`; Wine/non-Windows returns `StepNativePlatformRequired`;
visible/shared hosts return `StepIsolationRequired`. Internal evidence is
complete. Public run `42303929271` also passed on head `ee7f0ea5`; a reviewed
runtime/peer/worker-postflight safeguard repair now requires one new public
gate before this branch is merge-ready.

CLI contract:

```sh
swcli document export part.STEP --document d-ab12cd \
  --lease l-ab12cd34ef56 --if-update-stamp 5 \
  --step-protocol ap214 --step-geometry solid-surface --json
```

SDK contract:

```python
client.document.export(output="part.STEP", step_protocol="ap214",
    step_geometry="solid-surface", document_id="d-ab12cd",
    lease_id="l-ab12cd34ef56", expected_update_stamp=5)
```

MCP uses `execute` with `operation="document.export"`, the same `parameters`,
and top-level `document_id`, `lease_id`, `expected_update_stamp`. Discover the
contract with `capabilities(operation="document.export")`. There is no public
COM bypass, calibration request field, environment toggle, host restart or
native retry. A live lease and fresh update stamp are required for option writes.

The serialized worker establishes ownership independently of request data.
The adapter resolves enum names from installed `swconst.tlb`, snapshots both
integer preferences, compares the complete snapshot immediately before writing,
checks every setter and readback, then restores and verifies originals in
`finally`. Restore failure prevents output publication and stops further worker
requests. If export failed first, its original error is preserved alongside
`preference_restore_errors` and possible mutation evidence. Restoration concerns
application preferences; it never rolls back CAD state. Existing output is
replaced only after preference restoration, STEP schema/entity verification and
source identity/configuration/stamp checks succeed.

The manual `CI` input `native_step_targeted=true` is accepted only on
`codex/swcli-step-export-options`, after portable test and package jobs. It is
off by default, has no PR trigger, and uses a STEP/profile+ref concurrency group
with `cancel-in-progress=false`; existing full/tag concurrency is preserved.
Dispatch with `native_full=false`. The native script owns one invisible host,
stops on first failure, bounds native calls at 600 seconds and the group at
1800 seconds. It records official type-library enums, complete preference
snapshots, actual Part 21 `FILE_SCHEMA`, SHA256, analytic box or wireframe
geometry after STEP import, and native save/read-only reopen comparisons.
`public_gate` records the default rejection for uncalibrated revisions. On
an already audited revision it records a skip, so internal calibration still
performs only one export per combination; public proof uses its separate gate.
Logs and original output files are retained in the uploaded artifact. This is diagnostic evidence with
`full_acceptance_eligible=false`; public CLI/SDK/MCP native acceptance and any
revision promotion remain separate work. Internal run
[42278790303](https://github.com/YJBeetle/SWCLI/actions/runs/42278790303), head
`193ab6c64fac32c42783704f8e66a1804c751cc4`, passed all six combinations on
revision `33.5.0`. Original artifact `13537145378` has SHA256
`cf257c569e2d62ebb727c4a49041ab2a1b9c536b6f6d17e8b7208d5d3dc1b6cf`.
Independent original-file audit verified actual AP203/AP214 headers, solid
1-body/6-face/12-edge/8-vertex topology, wire vectors, zero-error imports and
source/imported native readonly reopens, complete preference restoration and
one owned hidden host with confirmed exit. This proves the generated-box
fixture and exact option combinations; it does not prove assemblies, other
revisions, Wine, AP242 or arbitrary CAD content.

Official references:

- [STEP API options, including AP203/AP214 integer values](https://help.solidworks.com/2016/english/api/swconst/FileSaveAsSTEPOptions.htm)
- [Geometry preference enum](https://help.solidworks.com/2023/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swAcisOutputGeometryPreference_e.html)
- [STEP export behavior](https://help.solidworks.com/2025/english/SolidWorks/sldworks/HIDD_EXPORT_OPTION_STEP.htm)
- [STEP import interface and LoadFile4](https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IImportStepData.html)

- [Sketch segment length readback](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchSegment~GetLength.html)
- [System preference setter result](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~SetUserPreferenceIntegerValue.html)


Public acceptance preparation uses a separate default-off
`native_step_public_targeted` profile. The public writer group performs six CLI
exports plus SDK/MCP bridge exports, rejects stale CAS/foreign lease/readonly
writes, and reopens the saved source through the CLI. After this host exits,
an independent observer group reads the exact SHA256-pinned public output
files with `LoadFile4`, then saves and reopens imported native geometry. Each
group owns one host with no failure retry or replacement. These prepared paths
passed in public run
[42303929271](https://github.com/YJBeetle/SWCLI/actions/runs/42303929271), exact
head `ee7f0ea51cc23924cf84462f7688800dc6bca626`. Original artifact `13546292159`
has SHA256 `4623ccc98e3cd4f745d31680bbef53560a855e85f6aef982553be0678acfd717`.
Independent original-file audit correlated all eight frontend request IDs to
exactly one native SaveAs3 call each, checked raw Part21 headers and wire-line
vectors, and verified eight native imports/save/readonly reopens. Stale CAS,
foreign lease, AP242 and readonly writes were rejected; complete preferences,
source identity and both owned-host lifecycles passed. This retained result
predates the runtime/peer/postflight review repair; the repaired head needs its
own public evidence.

The independent observer explicitly scopes the General import settings for
its disabled-3D-Interconnect host: `swMultiCAD_Enable3DInterconnect`,
`swImportSolidSurface`, `swImportFreeCurves`, and `swImportCurvePreference`.
All exact names and the `swGeneralImportAs3dCurves` value are resolved from the
installed SwConst enum owners. It imports free curves as native reference
curves, then restores/verifies the complete mixed boolean/integer snapshot in
`finally`. These are test-only observer settings; production export does not
change import options.
Every import must still return error code zero and pass the same geometry and
save/reopen checks. No failed import is retried in its group.

- [Neutral-format import API preferences](https://help.solidworks.com/2023/English/api/swconst/FileOpenOptionsSTEPIGESACIS.htm)
- [STEP import entities, including free curves/points as sketches](https://help.solidworks.com/2025/english/SolidWorks/sldworks/t_reading_step_iges_acis_sw.htm)
- [3D Interconnect API toggle](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IImport3DInterconnectData.html)

The observer uses the official void `ISldWorks.SetUserPreferenceToggle`
contract and verifies each effect through the complete boolean readback;
production integer preference setters retain their separate boolean contract.
[Toggle setter API](https://help.solidworks.com/2019/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~setuserpreferencetoggle.html).

The acceptance fixture is a 40×30×10 mm box with a center-rectangle source
sketch. Before export, independent sketch inspection requires four outline
lines (30,30,40,40 mm) and two construction diagonals (50,50 mm). Wireframe
requires exactly 12 box edges / 320 mm. Wireframe with sketches requires these
edges plus all six sketch lines: exactly 18 segments / 560 mm. Readback checks
the complete sorted length vector and native save/reopen with unchanged
precision bounds. The previous 460 mm oracle omitted construction diagonals;
its failed run and original ZIP remain recorded.
[Rectangle construction lines](https://help.solidworks.com/2025/english/SolidWorks/sldworks/HIDD_DVE_SKETCH_RECTANGLES.htm).

The native runtime check resolves `ntdll.dll` with `GetModuleHandleW`, requires
known `NtClose` to resolve, then accepts absent `wine_get_version` only when
`GetProcAddress` explicitly reports `ERROR_PROC_NOT_FOUND` (127). Missing APIs,
missing known exports, Wine, other errors and exceptions fail before preference
setters or SaveAs3. Runner labels do not establish runtime identity.

Before setters, after a successful native export and after preference restoration,
STEP verifies the
foreground peer's identity, type, configuration, update stamp, modified flag,
title and path as well as the source state. A changed peer blocks publication;
no CAD state is rolled back. Worker command finalization/result-schema failure
retains a trusted mutation boundary, first native error and valid preference
receipt, returns failure and retires the worker. An already published output is
reported in that failure receipt rather than silently retried or rolled back.

Public guard-repair run
[42361918322](https://github.com/YJBeetle/SWCLI/actions/runs/42361918322), head
`b5b2d1d2894e7ea78b81642b2b1b0b9dd593b7fa`, passed all eight public exports,
including the narrow native probe and foreground peer checks. Its independent
reader completed seven files; the last MCP wireframe imported with error 0 but
the top-level observer read nine segments, so the run failed. Original artifact
`13570691525` SHA256 is
`d113f76a96f31d27aee5a776ad357b1998fe5404651f264dd62f736888ce55be`.
The actual last STEP contains all twelve expected box edges. The retained trace
cannot distinguish missing imported geometry from skipped nested sketches.

The observer now visits bounded top-level and subfeature graphs, deduplicates
by document-unique native feature ID, and retains feature inventory/partial
lengths before failing. Exact 12/18 segment counts, complete length vectors,
all error-code and save/reopen gates, and all precision bounds remain unchanged.
There is no reread/reimport/rebuild/retry or host replacement. The next unique
public gate must establish complete geometry; nested sketches are an unresolved
explanation, not an accepted result from the failed run.
[Feature traversal](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature_members.html)
and [document-unique feature IDs](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~GetID.html).

Observer-coverage run
[42365535291](https://github.com/YJBeetle/SWCLI/actions/runs/42365535291), head
`d6505f7384911b43b28a5f273ab14262032c4698`, still failed: the fifth AP214
wireframe import returned error 0 but yielded nine sketch segments / 260 mm;
one of three imported sketches was empty. Its complete top/subfeature inventory
contains no omitted nested sketch, refuting that explanation. Four earlier
native cases completed; all eight public writes and foreground/restore/cleanup
checks passed. Original artifact `13571478417` SHA256 is
`b2e70c0786e67a9e97ff7a0af60234516eb2fd2a4884bf9b8506d7e6c9af1475`.
The original ZIP, job log, official summary and partial inventory are retained;
this failed run is not accepted or retried.

The official `GetSketchSegments` contract warns that sketches with errors can
produce an incomplete array. The retained evidence does not establish the
underlying sketch solver/import error, so no successful geometric proof is
inferred from its zero import code. The corrected observer selects
`swImportNeutral_CurvesAndPointsOption` =
`swImportNeutralCurvesAndPointsOptions_As3DCurves` before its single import,
resolving both names and enum ownership from installed SwConst. The three
existing import toggles plus this integer setting share complete snapshot/CAS,
checked setter/readback and original restoration. This is test-only import
representation; production export and its options are unchanged.

The reader then uses `IReferenceCurve.GetSegmentCount/GetSegments`, calls
`IEdge.GetCurve` before `GetCurveParams3`, and measures each trimmed edge using
`ICurve.GetLength3` with its documented parameter range. Reversed negative
ranges are normalized according to `ICurveParamData.Sense`. Native segment
counts must agree with the edge array and the exact same 12/18 analytic length
vectors before and after native save/readonly reopen. There is no automatic
fallback, reimport, rebuild, healing or in-process-only enumerator. The previous
sketch observation is preserved as failed evidence; all precision/count bounds
remain unchanged. The repaired profile still requires its own public gate.

- [Sketch array limitation](https://help.solidworks.com/2016/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISketch~GetSketchSegments.html)
- [Native integer preference name](https://help.solidworks.com/2018/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swUserPreferenceIntegerValue_e.html?id=2.10.1.774)
- [Neutral curve representation enum](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swImportNeutralCurvesAndPointsOptions_e.html)
- [Reference curve segments](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IReferenceCurve~GetSegments.html)
- [Feature type/interface mapping](https://help.solidworks.com/2022/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~GetTypeName2.html)
- [Edge curve parameters and required call order](https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IEdge~GetCurveParams3.html)
- [Parameter orientation](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ICurveParamData~UMaxValue.html)
- [Trimmed curve length](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICurve~GetLength3.html?format=P&value=)

Reference-profile run
[42405019483](https://github.com/YJBeetle/SWCLI/actions/runs/42405019483), head
`b36375197873820c1197ea3cb6174382ba9fd49d`, passed eight public writes but
completed only the first independent solid roundtrip. The second AP203 wire
import returned error 0 yet produced a nonempty `3DProfileFeature`; the reader
stopped at its representation check before any segment length call. Its
partial 0-segment/0-length record means **not measured**, not zero geometry.
All raw STEP wire vectors are complete. Original artifact `13587497385` SHA256
is `5149d2d543cab9461ab6fd826fa465a239577866d4326aa51655dab12e49e945`.
The original ZIP, job log, official summary and partial accounting are retained.

This run exposed a concrete option-family mismatch: the test disabled
3D Interconnect but configured `swImportNeutral_CurvesAndPointsOption` instead
of the documented General import controls for that mode. The corrected profile
uses `swImportFreeCurves` and `swImportCurvePreference` =
`swGeneralImportAs3dCurves`, alongside `swImportSolidSurface`. It does not infer
geometry or alter any precision/count assertion. The reader now records real
partial sketch lengths before rejecting an unexpected type, and marks
incomplete observations explicitly. `LoadFile4` retains argument `"r"`, whose
official meaning is a new document, not a curve representation selector.
The corrected installed-enum mapping and full eight-file roundtrip still need
a new necessary gate; this is not a claim that the prior sketch losses are
fully diagnosed.

- [General import API mapping](https://help.solidworks.com/2019/English/api/swconst/FileOpenOptionsGeneral.htm)
- [General curve/solid controls with 3D Interconnect disabled](https://help.solidworks.com/2026/english/solidworks/sldworks/hidd_options_import_general.htm)
- [General curve representation enum](https://help.solidworks.com/2021/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swGeneralImportFreePointCurveEntityOptions_e.html?id=2.10.1.357)
- [LoadFile4 argument semantics](https://help.solidworks.com/2015/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~LoadFile4.html)

The General-profile gate
[42413805736](https://github.com/YJBeetle/SWCLI/actions/runs/42413805736), exact
head `060f26178b4deabc330ef0959b9ec0f1704159cf`, also failed. All eight public
writes succeeded; the independent reader completed only its first solid
roundtrip. The second AP203 wireframe `LoadFile4` returned error 1 and no
retained model, before geometry observation. Its native object/geometry count
and total length are unavailable, not zero. General enum IDs were resolved and
all four requested values read back/restored, but those checks did not prove
the translator honored the intended representation. Earlier claims that this
option-family change was a sufficient fix are therefore unproven.

Original artifact `13591430613` SHA256 is
`de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7`.
Raw exported topology/line vectors remain verified, and original logs, official
summary and partial accounting are retained. There is no substantiated next
correction and no new CI dispatch. STEP remains a series release blocker.
The smallest next diagnostic would record both General and neutral preference
families before one import, explicitly persist returned-object/error metadata,
and collect all supported readable geometry before a representation assertion.
That diagnostic is now applied and covered by portable regressions; it remains
unverified natively and is not a proven repair. See the
[offline research and single-run plan](step-import-offline-research.md) for byte/geometry
comparison, installed interface contracts, remaining unknowns and a coordinator-reviewed
readback of immutable original outputs. No new native dispatch accompanies it.
