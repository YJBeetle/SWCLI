# STEP export options (internal calibration)

`document.export` accepts `step_protocol` (`ap203`, `ap214`) together with
`step_geometry` (`solid-surface`, `wireframe`, `wireframe-sketches`). Both are
required when either is present, only for `.step`/`.stp`. AP242 and unknown
fields/values are rejected before native export. Omitting both preserves the
existing export behavior. These options currently support saved, rebuilt,
writable parts outside sketch editing; assemblies remain fail closed.

**Public option writes are not enabled:** the native revision allowlist is
empty. Requests return `StepCalibrationRequired` on an isolated host, or
`StepIsolationRequired` on visible/shared hosts. A successful internal targeted
run is not public acceptance and does not change that allowlist.

CLI contract (currently returns the gate error):

```sh
swcli document export part.STEP --document d-ab12cd \
  --lease l-ab12cd34ef56 --expected-update-stamp 5 \
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
`public_gate` records the expected default rejection separately from the six
internal combinations. Logs and original output files are retained in the
uploaded artifact. This is diagnostic evidence with
`full_acceptance_eligible=false`; public CLI/SDK/MCP native acceptance and any
revision promotion remain separate work.

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
have not run yet; they do not enable the empty public revision allowlist.

The independent observer explicitly scopes neutral-format import settings: it
resolves `swMultiCAD_Enable3DInterconnect`, `swImportNeutral_SolidandSurface`
and `swImportNeutral_FreeCurvesAndPoints` from installed SwConst, selects the
legacy solids+free-curves-as-sketch profile before importing generated outputs,
and restores/verifies its complete original snapshot in `finally`. These are
test-only observer settings; production export does not change import options.
Every import must still return error code zero and pass the same geometry and
save/reopen checks. No failed import is retried in its group.

- [Neutral-format import API preferences](https://help.solidworks.com/2023/English/api/swconst/FileOpenOptionsSTEPIGESACIS.htm)
- [STEP import entities, including free curves/points as sketches](https://help.solidworks.com/2025/english/SolidWorks/sldworks/t_reading_step_iges_acis_sw.htm)
- [3D Interconnect API toggle](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IImport3DInterconnectData.html)

The observer uses the official void `ISldWorks.SetUserPreferenceToggle`
contract and verifies each effect through the complete boolean readback;
production integer preference setters retain their separate boolean contract.
[Toggle setter API](https://help.solidworks.com/2019/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~setuserpreferencetoggle.html).
