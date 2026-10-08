# Linux/Wine rejected-cut sequence investigation — 2026-10-08

The early probes below are diagnostic controls, not release gate passes; later
sections record independently verified candidate delivery. This is not an a5
release announcement or a confirmed Wine source defect. Earlier native Windows
**visible-mode** sequences
passed. Subsequent matched **hidden-mode** controls reproduce a related native
Windows failure as well, at a different COM call/HRESULT. Calling this a
Wine-only defect is no longer supported by the evidence.

## Environment and experimental boundary

- Trusted `workspaceroot`: Ubuntu 22.04.5, x86_64, Wine 11.16,
  SOLIDWORKS 2025 SP5 (`33.5.0`), Podman.
- Isolated diagnostic image `localhost/swcli-a5-probe:20261008`, based on
  `ghcr.io/yjbeetle/sw-executable:sha-9b73e84`. Its SWCLI snapshot `966a8be`
  has no runtime `src/` differences from `e8f78a5`; later changes are test/docs
  changes. This is not verification of the new hosted CI candidate image.
- Each `fresh-*` case starts a new container/writable Wine prefix from the
  same image. The preceding diagnostic container is stopped and archived,
  never reused as an input. No restart, native retry or assertion weakening
  occurs inside a case. One daemon-owned COM host executes the whole case.
- The helper uses only public CLI operations, generated unsaved parts and
  exact document IDs. It preserves checkpoint JSON, elapsed times, stderr,
  native Wine SEH output and final document/host observations. It does not
  touch user models, attach a debugger or change licensing settings.
- The diagnostic helper's process exit alone is not the verdict: its JSON
  `target_passed`, recorded errors and cleanup state must be inspected.

Evidence root on the test host:
`/tmp/swcli-wine-20261008.UV2nYN/evidence-context-20261008`.
One parameterized `probe-context.py` and `run-fresh.sh` serve public CLI cases.
Later `probe-direct-adapters.py` / `run-direct.sh` remove the daemon and document
registry: one owned STA calls the same native adapters and holds exact returned
COM objects. Completed case directories preserve helper copies/checksums.
The user's Windows VM uses that same helper/current checkout under
`C:\Workspace\SWCLI-tests\wine-sequence-controls-20261008`. These source-adapter
experiments are not installed-wheel or hosted-installer proof.
The VM is ARM64 Windows 10.0.26100 with AMD64 Python 3.14.7 (`win-amd64`)
running under Windows emulation; native Windows here means the Windows COM
host rather than Wine, not a physical x86_64 workstation. The final read-only
inventory confirmed no remaining SOLIDWORKS process, an isolated installed
`0.1.0a5.dev0` candidate, and unchanged global/regular-project `0.1.0a4` installs.

## Minimal public sequence

Using one explicit session and returned document/sketch IDs:

1. Require a connected owned host and an empty document list.
2. `document create`; front-plane rectangle 40×30 mm; extrude 10 mm.
3. Front-plane radius-2 mm circle centered at x=1000 mm.
4. `feature cut-extrude <outside-sketch> --depth-mm 10` must return
   `CutExtrusionFailed`, without cleanup warnings.
5. Document/sketch inspection must succeed with `editing=false`; measurement
   must still report one solid and 12000 mm³.
6. Either retain that document, or close it and require an empty list before
   creating a fresh foreground part.
7. Create a front-plane radius-8 mm circle centered at (3,4) mm in the selected
   target; require final native geometry verification and `editing=false`.
8. Close only case-owned documents, require an empty list and inspect health.

The matched no-cut control omits only step 4. There are no exports, dimensions,
leases or external paths in this smaller sequence. Thus those features are
not necessary inputs to this reproduction.

## Completed fresh-prefix controls

| Case | Resident mode | Target after rejected cut | Result |
| --- | --- | --- | --- |
| `fresh-hidden-foreground-no-cut` | Hidden | Close base, fresh foreground part; cut omitted | Passed; target circle 1.236 s |
| `fresh-hidden-foreground-cut` | Hidden | Close base, fresh foreground part | Failed at InsertSketch after 59.077 s, `0x800703E6` |
| `fresh-visible-foreground-cut` | Visible | Close base, fresh foreground part | Passed; target circle 16.511 s |
| `fresh-hidden-same-cut` | Hidden | Keep base, add circle in that same part | Passed; target circle 0.915 s |
| `fresh-hidden-new-with-base-cut` | Hidden | Keep base, create another part | Passed; target circle 1.277 s |
| `fresh-hidden-foreground-cut-repeat` | Hidden | Repeat close base, fresh foreground part | Failed at InsertSketch after 58.588 s, `0x800703E6` |
| `fresh-hidden-placeholder-cut` | Hidden | Open a blank placeholder before closing base, then create target | Failed at InsertSketch after 57.298 s, `0x800703E6` |
| `fresh-hidden-same-then-foreground-cut` | Hidden | Successfully add another circle in base, then close/create target | Passed; same-part circle 1.030 s, target circle 1.204 s |

The first four completed with empty cleanup errors and zero remaining documents.
Their original native PIDs respectively remained **612, 608, 608, 616**,
connected with `worker_alive=true`. PID values belong to independent Wine
prefixes: matching numeric PIDs across cases do not mean the same process.

In the failing foreground case, the rejected cut itself completed in 0.621 s;
closing the base, checking an empty list and creating the next part all
succeeded. New-document creation took 1.707 s. The failure occurs specifically
at `sketch-enter / InsertSketch`, before circle geometry creation. Returned
editing state was false and the host was not restarted. This extends the
earlier background-document reproduction: background activation is not required.

The native stderr file `fresh-hidden-foreground-cut/native-runtime-stderr/`
`swclid-start-error.h3nZOv` contains a caught `c0000005` read access violation
at `0x45ae70f0`, attempting address `0xb38`. The previously captured module map
places this address range in `sldappu.dll`. This is an observed native exception,
not a first-chance call stack or proof that Wine's implementation caused it.
The placeholder control also captured the actual native process's module map;
its stderr includes a caught execute access violation before the eventual
COM error. No native debugger or source patch was used.

## No-daemon and native Windows controls

All direct cases require an initially empty document set, owned native host,
one 12000 mm³ solid after the rejected cut, no active sketch, exact case-owned
cleanup and unchanged host PID/revision. There are no protocol requests, leases,
document registry entries or public client path conversions in these cases.

| Platform / case | Single changed condition | Result |
| --- | --- | --- |
| Wine `fresh-direct-hidden-cut` | Direct adapters, hidden | Target InsertSketch failed after 54.279 s, `0x800703E6` |
| Wine `fresh-direct-hidden-release-before-close-cut` | Release profile COM references before, not after, close | Target InsertSketch failed after 58.235 s, `0x800703E6` |
| Wine `fresh-direct-hidden-command-in-progress-cut` | `CommandInProgress=true` for the API sequence | Target InsertSketch failed after 58.303 s, `0x800703E6`; original flag restored |
| Windows initial `wine-sequence-hidden-20261008` | Same direct sequence, hidden | Target NewDocument failed after 9.387 s, `0x80010105` / `RPC_E_SERVERFAULT` |
| Windows `hidden-no-cut` | Omit only the rejected cut | Passed; target create 0.390 s, circle 0.124 s |
| Windows `visible-cut` | Visible resident host | Passed; target create 0.567 s, circle 2.385 s |
| Windows `hidden-observe-command-cut` | Hidden repeat, add only read-only command observations | Target NewDocument failed after 8.344 s, `0x80010105` |

The Windows failures do **not** reproduce the exact Wine InsertSketch exception:
they fail earlier, at NewDocument. They do disprove the earlier inference that
native Windows cannot reproduce the sequence-sensitive hidden-mode problem.
Both platforms' initial getters reported `UserControl=true`,
`UserControlBackground=true`, `Visible=false`, `CommandInProgress=false`.
Template/language and native Python version differ between hosts; identical
underlying source cause is not yet established.

`ExitApp()` being called is not proof that the native process exited. The
Windows hidden failures retained an otherwise responsive owned SOLIDWORKS PID
after that call. Its PID/name/start-time were checked against the experiment
record before terminating only that owned process between fresh cases. Some
Wine probes completed their JSON record but hung during subsequent shutdown;
the external 420-second budget stopped only their diagnostic container. Those
shutdown observations are separate from the measured failing COM call.

## Native command-state evidence

Read-only `GetRunningCommandInfo` uses explicit by-reference integer, string and
boolean arguments on the original STA. On native Windows and Wine it reports:

| Checkpoint | Command ID | UI active |
| --- | --- | --- |
| Before rejected cut | -3 | false |
| After rejected cut | 10 | false |
| After closing its document | 10 | false |
| After creating the next Wine document | 10 | false |

The official [command enumeration](https://help.solidworks.com/2025/english/api/swcommands/SolidWorks.Interop.swcommands~SolidWorks.Interop.swcommands.swCommands_e.html?id=cec41382bfc941eb83f24f6c8425852b)
maps -3 to `NoCommand` and 10 to `ExtrudedCut`.
[GetRunningCommandInfo](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~GetRunningCommandInfo.html)
reports command and UI activity separately: `ui_active=false` must not be
interpreted as no running command. This is evidence of residual native command
state, not yet proof of which component owns its incorrect lifetime.

The documented [CommandInProgress](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~CommandInProgress.html)
performance flag was set/read back/restored in one fresh Wine case and did not
clear that state or fix the failure. It is not adopted as a runtime workaround.

## Documented native cleanup controls

Independent fresh hosts add exactly one cleanup call after the rejected cut;
there is no retry, visibility change or native host replacement.

| Cleanup / host | Return/readback | Following result |
| --- | --- | --- |
| Standard Cancel (`RunCommand(3043, "")`), Windows | true, command remains 10 | NewDocument fails after 7.440 s, `0x80010105` |
| Standard Cancel, Wine | true, command remains 10 | InsertSketch still fails, `0x800703E6` |
| PropertyManager Cancel (`RunCommand(-1, "")`), Windows | true, command remains 10 | NewDocument fails after 7.974 s, `0x80010105` |
| `SetPickMode()`, Windows | void/None; command becomes -3 and stays -3 through close/create | Passed; target create 0.476 s, circle 0.134 s |
| `SetPickMode()`, Wine | void/None; command becomes -3 and stays -3 through close/create | Passed; target create 1.209 s, circle 0.835 s |

The official [RunCommand](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~RunCommand.html)
boolean means that the command ran; these negative controls show that it does
not prove the residual operation ended. The documented
[SetPickMode](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~SetPickMode.html)
returns the document to default selection mode. It is a void method, so its
None return must not be misclassified as failure.

These controls support incomplete native-command cleanup as an actionable
adapter defect on both hosts. They do not prove an internal Wine source defect.
The narrow runtime change in `e164b50` ends only an attempted native cut that
returned no feature or raised, preserves its original failure and independently
reports cleanup errors; successful cuts and pre-call rejections are unchanged.
Direct controls alone are not full installed public CLI/gate proof.

## Candidate adapter verification

The portable suite after runtime/CI changes ran **568 tests**: **560 passed**,
eight Windows-only execution tests skipped on macOS. All Windows CI PowerShell
scripts parsed on the native VM. The cleanup tests cover void return semantics,
ordering before selection cleanup, one native attempt, retention of the primary
error, independent cleanup warnings, and no command cancellation on pre-call
rejections or completed features with later verification errors.

A wheel containing the `e164b50` runtime change was built and passed Twine
validation. SHA-256:
`1e9828245ef7baf9e697a78ab7bcffb119e60b01743cfd431417fcc126a2ea12`.
It was force-installed without dependency/source overrides into the existing
isolated Windows environment. Isolated Python imported `windows_cuts.py` from
that environment's `Lib\site-packages`, not the checkout; regular/global a4
installations were not upgraded.

| Hidden public sequence | Evidence / result |
| --- | --- |
| Windows installed wheel, core modeling then driving | `C:\Workspace\SWCLI-tests\pick-cleanup-public-hidden-20261008-v2`; 85 modeling events, all three core cases; 242 driving events on front/top/right; unchanged PID 3992, empty cleanup errors, clean daemon stop |
| Windows updated complete host wrapper (`-Hidden`) | `C:\Workspace\SWCLI-tests\pick-cleanup-wrapper-hidden-20261008-v2`; installed-sample/modeling/driving gates, native save/reopen/render/STEP, public Unicode plate example and owned/attached disconnect/shutdown checks passed |
| Wine fresh foreground CLI reproduction | `fresh-hidden-adapter-cleanup`; no diagnostic SetPickMode call, no restart/retry; target passed, same PID 608, empty cleanup errors/documents |
| Wine fresh background CLI reproduction + complete shared modeling/driving | `fresh-hidden-adapter-gates`; 97 modeling events including samples and rejected-cut continuation, 242 driving events on front/top/right; unchanged PID 616, empty cleanup errors, empty final document list |

The Wine candidate uses a separate `source-pick-cleanup` snapshot; the earlier
unfixed source remains intact for the controls above. No native retries or
intervening daemon/host restarts occurred within these consecutive sequences.
The same hidden Wine PID 616 subsequently completed the unmodified DockerSW
six-export script. Both STEP files contain `ISO-10303-21;`, both PDF files were
identified as PDF 1.4, and both DWG files were identified as AutoCAD 2000 DWG.
The formal script returned zero and the final document list was empty:

| Artifact | Bytes |
| --- | ---: |
| `Paper Airplane.STEP` | 113426 |
| `bezel moldbase.STEP` | 3491004 |
| `bezel moldbase.PDF` | 222097 |
| `bezel moldbase.DWG` | 424267 |
| `cabinet_bath.PDF` | 320213 |
| `cabinet_bath.DWG` | 472759 |

Files and `export.log` are retained in `fresh-hidden-adapter-gates/output` and
its case directory. This local order was modeling -> driving -> exports; the
fresh hosted DockerSW candidate must independently verify its delivery order
exports -> modeling -> driving and image promotion. No publication/promotion
is implied by the local artifact or gate passes.

A read-only audit against the current Schemas checked 479 complete captured
protocol-response positions, 404 CLI result positions, 474 business-result
positions and 18 capabilities positions across the installed hidden Windows
and hidden Wine public records, with no mismatch. These counts include repeated
evidence positions, not independent calls. Only documented CLI metadata absent
from an operation's result Schema was removed; business `session_id` fields
required by an operation were retained. Missing original request packets were
not reconstructed as evidence.

Two diagnostic harness mistakes were preserved rather than counted as native
failures: the first Windows public-gate launcher passed Select-String arguments
positionally and failed before modeling; the first Wine driving invocation
omitted `--cli-command`, so isolated Linux Python reported `No module named
swcli` during its CLI projection. Corrected invocations used new evidence
directories/fresh owned hosts and did not retry a failed native operation.

The first complete hidden Windows wrapper passed public modeling/driving but
its Windows-only equation fixture could not attach via `GetActiveObject`
(`0x800401E3`, stage `attach-existing-host`). That fixture now remains mandatory
in the separate visible CI run. Hidden mode does not switch visibility or
Dispatch another host for equation setup; all public gates and lifecycle
assertions remain mandatory. Its failed first record is retained under the
original `pick-cleanup-wrapper-hidden-20261008` directory.

## Interpretation and remaining work

- The same-document/new-document-while-base-remains passes argue against
  treating any rejected cut as an immediately unusable COM host. Keeping a
  placeholder open still fails, so an empty-document interval is not necessary.
- The no-daemon reproduction excludes daemon registry/transport as necessary
  inputs; changing profile COM release order alone does not fix it.
- A successful same-part sketch before closing the affected document lets the
  fresh target pass. This is a diagnostic control, not a hidden modeling retry
  or approved production workaround. Documented native cleanup controls above
  identify a narrower candidate without adding geometry or an artificial delay.
- The visible control changes **both** residency and visibility, not just
  rendering: current SWCLI uses `UserControl=true, Visible=true` versus
  `UserControlBackground=true, Visible=false`. The official
  [UserControl](https://help.solidworks.com/2023/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControl.html)
  and [UserControlBackground](https://help.solidworks.com/2022/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControlBackground.html)
  descriptions explain this distinction. Getter observations above also show
  that setter paths cannot be inferred from one residency boolean alone. Visible
  passes do not establish a general fix; Wine visible calls were much slower.
- A prior case reused an old container after a manual daemon restart and
  timed out during new-document creation; subsequent startup failed. That
  confounded result is retained as `hidden-foreground-v2`, but is not used as
  a fresh-prefix cut-trigger proof.
- The adapter cleanup passed the shared public modeling/driving sequences
  above on both hidden hosts. The later hosted Windows dual-mode and DockerSW
  delivery passes below are independent evidence, not implied by local success.
  A successful cancellation return alone remains insufficient evidence.

For earlier CI and Windows evidence, see
[the a5 verification record](a5-2026-10-07.md).

## Earlier visible DockerSW CI timeout

[DockerSW run 37697651663](https://github.com/YJBeetle/DockerSW/actions/runs/37697651663)
at `9067827` completed with a failure in `Build & Verify SolidWorks Images` /
`Smoke test SWCLI modeling & protocol`: the step exceeded its ten-minute limit.
The public artifact `sw-cli-export-smoke-37697651663` contains all six formal
exports, but modeling checkpoint state is `running`, stage
`sketch.circle.started`, with zero completed cases. Its last in-flight command
is a Top-plane radius-8 mm circle centered at (120,20) mm in the first model.
The prior extrusion completed successfully; the recorded host was visible,
owned and PID 608. Several ordinary modeling calls consumed 40–80 seconds.

There is no recorded `InsertSketch / 0x800703E6` or lease-expiry failure in that
unfinished checkpoint, and it never reached the later rejected-cut continuation
case. The empty cleanup-error array in a killed/running record is not proof of
successful cleanup. Driving/localized gates and image promotion did not run.
The timeout is distinct from the hidden-mode native defect above.

DockerSW `ac0959c` retains the ten-minute budget and tests the actual default
hidden delivery host, including a strict `host.visible=false` startup readback.
Visible-mode performance remains a separate observation; switching the delivery
gate to its real default is not a claim that the slower visible path was fixed.

## Hosted hidden Wine delivery verified

[DockerSW run 37702494347](https://github.com/YJBeetle/DockerSW/actions/runs/37702494347)
passed the full workflow at DockerSW `60840b1`, pinning SWCLI `4657a27` with the
`e164b50` runtime cleanup. It reused the verified SOLIDWORKS installation layers;
it is a fresh candidate/container delivery test, not a new official MSI install.

The downloaded `sw-cli-export-smoke-37702494347` artifact confirms:

- Startup, all four shared modeling cases (**97 events**) and all three driving
  planes (**242 events**) use the same hidden owned PID **608**, revision 33.5.0.
  No worker/host restart, native retry or cleanup-warning acceptance occurs.
  The negative cut retains `CutExtrusionFailed`; both gate records are completed
  and successful, with empty cleanup errors and unchanged final host descriptors.
- All six formal exports have valid STEP/PDF/DWG signatures, independently
  checked after artifact download. The sequence is exports -> modeling ->
  driving, unlike the earlier local candidate order.
- The export/startup step took **74 seconds**, shared modeling **57 seconds**,
  and driving **57 seconds**. Every phase retained its existing ten-minute
  budget; no timeout was increased to obtain this pass.
- Reopened diameter-discovery stamps remain **166 -> 166** on front/top/right,
  and expired handles are rejected. A separate Schema audit of captured JSON
  checked 239 complete protocol-response positions, 214 CLI result positions,
  237 business-result positions and nine capabilities positions, with no drift.

The separate `sw-language-smoke-37702494347` artifact verifies the zh-cn UI
language and a real Paper Airplane STEP export. It does not claim that the full
driving suite ran under that locale.

The `Publish verified CLI images & promote atomically` step completed after
these gates. It published immutable `sw-executable:sha-60840b1-cli` and promoted
`sw-executable:2025-cli` to OCI index digest
`sha256:18c0d4aec22eff2de35f22b023675a5facd3cb64811884cba1d1e460df479c40`.
The preinstalled and zh-cn image variants were also promoted. This closes the
hosted Wine delivery gate for this exact candidate. The separate Windows
dual-mode proof follows; a5 publication remains a distinct, unfinished step.
An independent read-only registry check from `workspaceroot` compared the full
manifests of `2025-cli` and `sha-60840b1-cli`; they were identical after promotion.
The five idle containers from this investigation were then stopped after their
last host/document/log snapshots were saved under `closure-20261008`. Container
filesystems and bind-mounted evidence were retained; no unrelated workloads or
base images were removed. The Windows VM remained running.

## Hosted Windows dual-mode verification

[SWCLI run 37702208212](https://github.com/YJBeetle/SWCLI/actions/runs/37702208212)
passed every job at `4657a27`: Python 3.9/3.14 unit tests, built/installed wheel
resource checks, and a fresh official SOLIDWORKS installation followed by the
same complete Windows wrapper in both modes. The real COM job used AMD64
Windows 10.0.26100 and AMD64 Python **3.12.10**, distinct from the local ARM64 VM
control and the unit-test matrix. Its complete dual-mode smoke step took
**8 minutes 43 seconds**.

The downloaded `swcli-windows-hosted-37702208212-1` artifact confirms:

| Mode | Readback | Modeling | Driving | Continuous native PID |
| --- | --- | --- | --- | --- |
| Visible | `host.visible=true` | Four cases, 97 events | All planes, 242 events | 9144 |
| Hidden | `host.visible=false` | Four cases, 97 events | All planes, 242 events | 9080 |

Each mode's modeling/driving records completed successfully, with unchanged
host descriptors, empty cleanup errors, rejection continuation and native
save/reopen discovery. The modes intentionally start separate owned hosts;
there is no restart or retry within either consecutive modeling/driving chain.
Both STEP signatures and both **800×600×24-bit** BMP headers were independently
checked after download.

The visible equation fixture remains mandatory and passed: native Add2 index 0,
Status 0, count 0 -> 1; typed mutation returns `DimensionExternallyControlled`
with diameter 16 mm, geometry/measurement and stamp **164 -> 164** unchanged.
Hidden mode does not claim ROT equation-bootstrap proof. Both wrapper modes
also passed their owned/attached disconnect, explicit recovery and shutdown
assertions, including preserving the live interactive host when stopping an
attached daemon.

A Schema audit checked 521 complete protocol-response positions, 464 CLI result
positions, 497 business-result positions and 46 capabilities positions, without
drift. Counts include duplicated evidence positions. The auditor honors explicit
UTF-8/UTF-16 evidence BOMs; it neither reconstructs absent packets nor treats
Schema objects embedded in capabilities as runtime results.

The hidden-mode failed-cut continuation is now covered by portable failure
tests, the user's installed-wheel VM, fresh hosted AMD64 Windows and the
independent hidden Wine delivery gate. MacSW/macOS execution and a published a5
package are not inferred from these passes. Visible Wine performance remains
the separate limitation recorded above; no Wine source patch/MR is claimed.
