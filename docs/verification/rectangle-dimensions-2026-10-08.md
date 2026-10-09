# Rectangle size / positioning feasibility — 2026-10-08

The first sections record internal direct-STA feasibility probes of installed
SWCLI a5 primitives plus native COM dimension calls. Later sections record
source-only a6 internal adapters. None is a public CLI/release gate, general
constraint support or Wine/macOS proof; pending lists in earlier sections
describe that stage's evidence boundary, not the latest adapter state.

## Installed public size controls — 2026-10-10

Candidate `9380bc9` passed the existing shared modeling and driving scripts from
an isolated **installed wheel** on Windows ARM64 / Python `3.14.7` / SOLIDWORKS
`33.5.0`. This is local native execution, not hosted CI, Wine or a published a6.

| Mode | Owned SW PID throughout modeling and dimensions | Rectangle planes |
| --- | --- | --- |
| Visible | 7924 | front, top, right |
| Hidden | 9180 | front, top, right |

Each mode continuously ran modeling, diameter edits/discovery, explicit center
fixes and rectangle size creation/inspection/editing without a host replacement
or retry. Rectangles were explicitly fixed at (3,4,0) mm before size creation.
After a 10 mm boss, width 40→50 mm preserved height 30 mm and measured 15000 mm³;
height 30→35 mm preserved width 50 mm and measured 17500 mm³. Both edits preserved
the center on all planes. Native controls, geometry, complete rebuild diagnostics
and independent body measures passed. Lease/stamp/duplicate refusals, leased
background read-only inspection, foreground restoration and expired IDs also
passed. Front-plane creation/edit used the installed CLI with `--document`
before the positional handle. All four terminal modeling/driving records have
`success: true`, `stage: completed` and empty cleanup errors. Both daemons stopped
normally; the VM remained running.

Evidence: `C:\Workspace\SWCLI-tests\a6-public-linear-f44c8189`, copied locally to
`/private/tmp/swcli-a6-public-linear-proof`. Each mode contains
`modeling/modeling.json`, `driving/driving-dimensions.json`, native call logs and
daemon status/stop records. Wheel SHA-256:
`4062d60f2aa5aca4f9037bdf177d0c80b6b0efe63375bdd8e0bbf17da842c15e`.
The exact shared-script hashes are retained in `gate-sha256.json`.

This candidate predates public saved-size discovery. Its successful native
center/diameter reopen tests are **not** rectangle-width/height reopen proof.

The same size candidate then passed
[hosted Windows CI 37976308927](https://github.com/YJBeetle/SWCLI/actions/runs/37976308927).
Downloaded public artifact `swcli-windows-hosted-37976308927-1` independently
confirms visible PID **2812** and hidden PID **1384**. Each completed 97 modeling
events and 532 driving events, including all three rectangle planes, with the
same PID before/after both gates, `success: true`, terminal `completed` stages
and empty cleanup errors. All six rectangle edits per mode measured 15000 then
17500 mm³ and retained center (3,4,0) mm within 1e-6 mm. Python 3.9/3.14 unit
jobs, distribution build and the native installation/runtime job also passed.
This remains size-control proof, not the later saved-size discovery candidate.
The downloaded evidence is retained at `/private/tmp/swcli-ci-37976308927.BIdU8v`.

## Matched independent cases

Two fresh owned **visible** Windows hosts, SOLIDWORKS revision `33.5.0`, tested
front/top/right planes. Each created a native center rectangle **40×30 mm**,
center **(3,4) mm**, with four profile lines and two construction diagonals.
The native unique horizontal/vertical pairs were selected by geometry, not
names/creation order. Annotation positions used the inverse model-to-sketch
transform. Horizontal and vertical native dimensions matched their exact owner
and driving values, then a 10 mm boss was created. Width changed to 50 mm and
height to 35 mm in the current configuration, with rebuild/diagnosis after
each edit and final native geometry/body measurements.

| Positioning case | Center after width edit | Center after height edit | Final volume |
| --- | --- | --- | --- |
| No additional position constraint (PID 7236) | (8,4) mm | (8,6.5) mm | 17500 mm³ |
| Explicit fixed native center (PID 7516) | (3,4) mm | (3,4) mm | 17500 mm³ |

All three planes matched these observations to 1e-6 mm. The fixed-center case
uniquely observed and selected the existing center point at (3,4,0), then used
`SketchAddConstraints('sgFIXED')` before creating size dimensions. This was an
explicit probe flag, not a silent fallback after an operation failure. Final
area was 5200 mm² in both cases. Each independent case completed with no cleanup
errors and left no SOLIDWORKS process running. No mutation was retried and
visibility was never changed within a case.

Native observations: width/height display types 11/12, dimension type 0,
driving state 2, integer late-bound ReadOnly 0. Constraint-status readback was
2 initially; with the fixed center plus both dimensions it became 3 and stayed
3 after editing. These numeric observations alone are **not** used as a claim
that arbitrary profiles can be made fully defined. Native dimension names were
recorded only as diagnostic evidence, not used for lookup.

Evidence is retained under:

- `C:\Workspace\SWCLI-tests\a6-rectangle-feasibility-20261008`
- `C:\Workspace\SWCLI-tests\a6-rectangle-feasibility-20261008-fixed-center`

Each has `result.json`, the exact probe and scope notes. Local evidence copies
are under `/private/tmp/swcli-a6-rectangle-evidence-20261008` and
`/private/tmp/swcli-a6-rectangle-fixed-center-evidence-20261008`. They are
diagnostic artifacts, not installed product capabilities or a new permanent
smoke framework.

## Conclusion and still-unproved boundaries

Native width/height creation and absorbed-profile editing are feasible on this
visible Windows host. Correct size/volume does not prove correct placement.
Keep size and explicit positioning semantics separate as described in the
[next-slice design](../design/rectangle-driving-dimensions.md).

Exact native relation readback, controlled/ambiguous dimension refusals,
save/reopen discovery, installed typed protocol, background-document guards,
hidden Windows and Wine remain to be proved. Neither this record nor a MacSW
version follow-up claims those gates passed.

API reference entry points:
[AddHorizontalDimension2](https://help.solidworks.com/2016/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~AddHorizontalDimension2.html),
[AddVerticalDimension2](https://help.solidworks.com/2016/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~AddVerticalDimension2.html),
[SketchAddConstraints](https://help.solidworks.com/2022/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldoc2~sketchaddconstraints.html).

## Native dimension identity boundary

The first internal rectangle adapter attempt stopped after creating two native
dimensions. On an independent visible Windows host (PID 6452, revision
`33.5.0`), `IsSame(width, height)` returned **2**, not 0. That is the documented
`swObjectUnsupported` outcome, not proof of different dimensions. Comparing
each dimension to itself returned 1. The width/height display chain reported
types 11/12; repeated `GetDimension2(0)` observations matched their respective
canonical `IUnknown` interfaces and differed from the other axis's interface.

The dimension-specific identity reader therefore preserves known native 0/1
results and uses canonical COM identity only for the explicit native result 2.
Unknown enums, busy/failed native comparisons and unavailable QI identity fail
closed. A QI/equality failure cannot establish which interface failed, so it
must not expire an otherwise registered dimension. Feature/display comparisons
are unchanged; this is not a generic truthiness or name-based identity fallback.
References are live STA-local COM objects, not persisted addresses.

Evidence: `C:\Workspace\SWCLI-tests\a6-rectangle-adapter-20261008\identity-before-fix.json`.
This intentionally failed probe is identity evidence, not a successful public
modeling gate. Portable tests cover registry reuse, deferred cleanup, failed QI
and candidate disconnect, as well as strict metadata readers.

Primary references: [SOLIDWORKS object equality enum](https://help.solidworks.com/2024/english/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swObjectEquality.html),
[COM identity rules](https://learn.microsoft.com/en-us/windows/win32/com/rules-for-implementing-queryinterface),
[pywin32 canonical comparison implementation](https://github.com/mhammond/pywin32/blob/main/com/win32com/src/PyIUnknown.cpp).

## Internal creation adapter and live registry proof

After the identity repair, a source-checkout probe on one independently owned
**visible** Windows host (PID 2312, revision `33.5.0`) completed nine independent
cases: front/top/right, each with the following three explicit positioning
conditions. Native calls ran on the same COM STA inside the existing API batch
wrapper. Each case closed its own part without saving it; the host exited after
all cases. The VM stayed running.

| Case on each plane | Expected result | Native geometry / downstream evidence |
| --- | --- | --- |
| Unanchored 40×30 mm rectangle, dimensions set to its current size | Success | Center (3,4) mm preserved; 10 mm boss volume 12000 mm³ |
| Explicit fixed-center fixture, dimensions set to 50×35 mm | Success | Center (3,4) mm preserved; 10 mm boss volume 17500 mm³ |
| Unanchored rectangle, width requested as 50 mm | Refusal after the width mutation | Width matched, center drifted to (8,4) mm; `DimensionVerificationFailed`, exact width handle retained, no height dimension created |

The fixed-center relation was an explicit test-fixture action performed before
calling the adapter, never a fallback or silent constraint added by it. The
refusals are expected evidence of placement checking, not successful mutations
or rollback. The adapter reports `modification_may_have_happened: true` and
retains the observed failed step.

All six successful cases also registered the exact width/height handles under
distinct internal dimension IDs. Fresh `GetDimension2(0)` observations from the
native display chain reused the respective IDs, demonstrating canonical COM
identity without names or Python proxy identity. This is internal registry
identity proof only: public linear inspect/set metadata is not yet implemented.

All nine cases restored the dimension-value prompt, left sketch editing closed
and reported no cleanup errors. No failed mutation was retried; neither daemon
nor SOLIDWORKS was restarted between cases.

Evidence and the exact probe are retained at:

- `C:\Workspace\SWCLI-tests\a6-rectangle-adapter-20261008\verified-with-registry.json`
- `C:\Workspace\SWCLI-tests\a6-rectangle-adapter-20261008\probe.py`

The isolated Windows Python environment used the shared source checkout, not a
new installed wheel. Portable tests cover strict metadata, topology, partial
creation, independently checked size/center, configuration changes, owned edit
cleanup and preference/selection failures. Installed public protocol, linear
handle ownership metadata, relation readback, save/reopen discovery, hidden
Windows and Wine remain unproved; no release or shared gate is claimed here.

## Read-only linear inspection proof

The next source-checkout probe (base commit `7464b99` plus the internal read
adapter) repeated the nine creation cases on one owned **visible** Windows
host, PID 6024, revision `33.5.0`. It completed with no cleanup errors and the
same expected size/placement outcomes. Exact source-file SHA-256 values are in
the evidence, so the source-only adapter result is distinguishable from an
installed wheel or later implementation.

For each of the six successful parts, width and height were inspected both
before absorption and after creating the 10 mm boss. The latter two reads ran
with a second fresh part in the foreground. All **24 exact dimension reads**
matched the rectangle geometry and reported unchanged update stamp,
configuration and edit state. All six background cases retained the second
part in the foreground, without activation/selection/edit/rebuild. Semantic
registry entries explicitly read back `width/rectangle` and `height/rectangle`;
repeat observations reused their respective IDs.

Each background case also deliberately supplied the width handle with the
height role. It returned `DimensionVerificationFailed`, preserved the update
stamp and foreground document, and never reinterpreted the parameter as a
height. This is an internal adapter misuse refusal, not an added public command.
The existing public inspect/set surface still rejects internal linear bindings
before activation while its result contracts remain diameter-only.

Portable tests additionally cover stale ownership, absorbed traversal, cyclic
or incomplete display chains, contradictory duplicate presentations, strict
native metadata, externally controlled/driven/read-only observation, geometry
mismatch and changed configuration/stamp/edit state. Reading does not claim
writability, full definition or preserved positioning under a future mutation.

Evidence and exact probe:

- `C:\Workspace\SWCLI-tests\a6-linear-inspection-20261008\verified-inspection.json`
- `C:\Workspace\SWCLI-tests\a6-linear-inspection-20261008\probe.py`

The host exited after closing its own parts; the VM remains running. Native
linear set/positioning, save/reopen discovery, installed public contracts,
hidden Windows and Wine are still separate pending gates.

## Single-axis linear edit proof

A source-checkout probe (base `f64c0d1` plus the internal edit adapter) completed
the same nine creation/inspection cases on one owned **visible** Windows host,
PID 5300, revision `33.5.0`, then tested the registered absorbed dimensions.
Exact adapter source hashes are retained in the evidence.

On each of front/top/right, the explicit fixed-center fixture's 50×35 mm profile
and 10 mm boss were edited sequentially without a host restart:

| Edit | Final width / height | Verified unchanged center | Measured volume |
| --- | --- | --- | --- |
| Exact width handle → 60 mm | 60×35 mm | (3,4) mm | 21000 mm³ |
| Exact height handle → 45 mm | 60×45 mm | (3,4) mm | 27000 mm³ |

All six positive edits passed native value/type/owner/control/configuration
reads, independently observed rectangle size/center, complete rebuild
diagnostics and fresh before/after body measurements. The fixed relation still
belongs to the explicit fixture, not the size adapter. No dimension was looked
up by name and no position relation was created during an edit.

Each of the three unanchored 40×30 mm parts also received a width edit to 50 mm
after absorption. The native setter returned 0 and the requested size matched,
but the center drifted. Every case returned `DimensionVerificationFailed` with
`center_preserved: false` and `modification_may_have_happened: true`, rather than
claiming a correct model or undo. Failed mutations were never retried.

Portable edit tests additionally cover height/width scope, changed other axis,
pre-existing/foreign edits, exact ownership, corrupted profiles, controlled
dimensions, unknown setter/rebuild metadata, false native success, changed
configuration/stamp, failed measurements, disappearing bodies and truncated
or unhealthy diagnostics. State changes before mutation block the setter;
failure after any attempted setter reports possible mutation, including a
nonzero result or a COM exception.

Evidence and exact probe:

- `C:\Workspace\SWCLI-tests\a6-linear-set-20261008\verified-linear-edits.json`
- `C:\Workspace\SWCLI-tests\a6-linear-set-20261008\probe.py`

All parts were closed without saving, the owned host exited, and cleanup errors
were empty. This is source-only internal adapter proof, not a typed/public CLI
or installed-wheel gate. Explicit native relation readback, saved discovery,
public Schema/guards, hidden Windows and Wine remain pending. The DockerSW
production gitlink is not advanced to unverified a6 development code.

## Exact center relation identity and readback

The first native center-relation probe (owned visible PID 828, revision `33.5.0`)
created a FIXED relation but failed its point-object `IsSame == 1` assertion.
Native `IsSame` returned **0** for the point obtained from relation entities
versus the point from `GetSketchPoints2`. Both had point ID `(0,1)`, identical
coordinates and the same exact owning sketch. This was a failed probe, not a
successful gate or an unsupported-2 COM identity fallback. Do not override
native equality results in the dimension or feature comparers.

The documented point/segment GetID semantics instead allow typed ID-pair
comparison **within the exact owning sketch**. Points and lines may share a
pair; identical pairs in different sketches also do not establish identity.
These IDs are not persistent-reference IDs. An independent native probe on
PID 8368 observed front/top/right centers at (3,4) mm and a front-plane origin
case, checking exact owner/type/ID and both internal/definition entities.

For each off-origin case, the center point had exactly two unsuppressed
COINCIDENT (9) relations, each binding Point (2) to one distinct construction
Line (3) joining opposite native profile corners. FIXED (17), added through
`SketchRelationManager.AddRelation` with a dispatch array containing only the
center point, read back that same point and survived sketch exit. The origin
case also had an automatic point/origin coincidence, so it cannot be treated as
an unpositioned off-origin profile or safely given another constraint blindly.
This native relation experiment is not a solver-validity proof for the origin
case after its experimental extra fix.

The internal read adapter (`2849d68`) then passed on a new visible host,
PID 4164: three planes before/after an explicit fixture fix returned exact
attachment/fix evidence with unchanged update stamp, configuration and edit
state. The origin case returned `UnsupportedCenterConstraint` with unchanged
state. The primitive validates native corner/diagonal connectivity, relation
definitions, counts, types and suppression; coordinates alone are insufficient.
Portable tests cover ID/owner/type collisions, stray centers, inconsistent
definitions, disconnected corners, ordering and changing/incomplete reads.

Evidence under `C:\Workspace\SWCLI-tests\a6-center-relations-20261008`:

- `native-relations.json` and `identity-first-probe.py`: failed equality assertion.
- `owner-local-identity.json` and `identity-probe.py`: independent native ID observation.
- `adapter-read.json` and `read-adapter.py`: internal read adapter and origin refusal.

Primary references: [point GetID scope](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISketchPoint~GetID.html),
[segment GetID scope](https://help.solidworks.com/2023/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isketchsegment~getid.html?format=P&value=),
[relation definitions](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchRelation~IGetDefinitionEntities2.html),
[relation suppression](https://help.solidworks.com/2019/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchRelation~Suppressed.html).

## Explicit center-fix adapter proof

The separate internal fix adapter (`973bcf0`) completed a fresh source-only
probe on one owned **visible** host, PID 2996, revision `33.5.0`. It invoked
the product's internal adapter instead of the earlier `sgFIXED` fixture.
On each front/top/right plane, in the same STA/host without restarting or
retrying an operation:

1. Create the native 40×30 mm center rectangle at (3,4) mm.
2. Explicitly fix the verified center point through `AddRelation`; independently
   re-observe its exact relation and unchanged geometry after sketch exit.
3. Invoke fix again: read-only success with `created: false` and unchanged stamp.
4. Create exact native driving width/height 50×35 mm, then a 10 mm boss:
   one native solid body, volume 17500 mm³.
5. Edit the absorbed width to 60 mm, then height to 45 mm: volumes 21000 and
   27000 mm³ respectively; unchanged center (3,4) mm within 1e-6 mm.
6. After each edit, read the retained exact fixed-center relation from the
   absorbed sketch without changing its stamp, configuration or edit state.

The independent origin case refused the extra position relation **before
mutation**, with no returned relation, unchanged stamp and no active edit.
All cases closed their own unsaved parts; the owned host exited cleanly and
the VM stayed running. Native source hashes are retained in the result.

The initial fix/edit harness stopped on its own incorrect `body_count` JSON
field after successful front-plane fix/no-op/dimension/extrusion steps. The
failure is retained separately; a corrected harness reads the measurement
`metrics.solid_body_count` and `metrics.volume_mm3` and independently completed
the full new-model run above. It did not retry a failed CAD mutation or hide a
runtime failure by restarting partway through the successful sequence.

Evidence in the same directory:

- `adapter-fix-edit.json` and `measurement-field-first-probe.py`: harness field error.
- `adapter-fix-edit-verified.json` and `fix-adapter.py`: full adapter proof.

25 additional portable tests cover exact single-point dispatch arrays, existing
fix no-ops, external/fully constrained/unknown/autosolve-off refusals, changed
configurations, lost/suppressed/wrong returned relations, failed native
creation and possible partial mutation. Both normal exit and failure cleanup
verify the exact owned edit; a newly active foreign sketch is never closed.
Cleanup failure cannot turn into success or erase the primary native failure.

References: [AddRelation](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchRelationManager~AddRelation.html),
[native solver states](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swConstrainedStatus_e.html?id=2.10.1.179).

Current proof boundary: internal visible-Windows size creation/inspection/edit
and explicit center fixing are verified. The development `sketch.fix-center`
catalog/request/result/CLI contract is implemented in `720c637`, but installed
public Windows, saved linear discovery, hidden Windows and Wine remain pending.
The 763-test portable suite passes with eight Windows-only cases skipped on
macOS; that skip is not native proof. Existing hosted public gates at `08ffaee`
passed before these center adapters and do not exercise them. DockerSW stays
at its published a5 production gitlink until a6 delivery is independently gated.

## Development public center gate (2026-10-09)

The existing `scripts/ci/verify-driving-dimensions.py` now checks explicit
center fixing after each plane's diameter workflow on the same daemon/SW PID.
It verifies exact 40×30 mm geometry at (3,4) mm, first creation and repeated
no-op, contender/old-stamp refusal, foreground/current restoration, front-plane
origin refusal and native save/close/reopen with newly discovered sketch handles.
Closed handles are rejected; persisted fixes remain read-only no-ops, including
when the saved part is reopened read-only. It uses public typed operations only.
The installed front-plane CLI places `--document` before the positional ID.
The updated portable suite runs 774 tests successfully, with eight Windows-only
cases skipped on macOS.

Portable gate tests inject geometry drift, false success, duplicate fixes,
unexpected stamp mutation, lost saved fixes and foreground changes. These are
gate/contract evidence, not SOLIDWORKS execution evidence. Windows CI already
runs this shared gate in visible and hidden modes after modeling; no duplicate
PowerShell modeling flow or extra host restart was added.

Local public VM verification is blocked: Parallels refused to start Windows
because its disk requires at least 6537 MB of additional free space. No user
files were removed. Hosted installed-package proof is still required before
advertising this capability or updating DockerSW's production pin.

## First installed public Windows gate — 2026-10-09

[SWCLI CI 37830499698](https://github.com/YJBeetle/SWCLI/actions/runs/37830499698)
at `138cbb61050e543878af202e325061b5bf636e4c` passed both Python unit-test
matrices, packaging and native installation. The real smoke step failed in the
first front-plane center case **before** invoking `sketch.fix-center`:
`sketch.rectangle` returned `SketchVerificationFailed` for 40×30 mm at (3,4) mm.
Its reported line bounds were x=[-23,23], y=[-11,19] mm, versus requested
x=[-17,23], y=[-11,19] mm; it reported six segments, four profile segments.
Keep the assertion unchanged and investigate the native geometry/creation
state separately. This is not proof of a center-fix failure or of the unrelated
MacSW hosted cut timeout. Public center delivery remains blocked pending
native evidence and a passing unchanged gate.

### Exact rectangle creation repair — 2026-10-09

[SWCLI CI 37832962358](https://github.com/YJBeetle/SWCLI/actions/runs/37832962358)
at `d5fc84bf42c4672413ccfa3f2cbdd6e4cdf9905c` repeated the same bounds mismatch
after passing the shared modeling gate. Rectangle creation still used the UI
inference path, unlike the existing direct circle adapter. The repair shares
the circle's scoped `SketchManager.AddToDB` enable/readback/restore logic with
`CreateCenterRectangle`. It changes no global snapping/display preference,
requested coordinates, final geometry assertions, retries or host lifetime.
The documented direct-database mode bypasses grid/entity snapping:
[SOLIDWORKS AddToDB](https://help.solidworks.com/2020/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isketchmanager~addtodb.html).

Five additional portable tests cover the observed 40-to-46 mm drift model,
restoration before sketch close, native failure, failed mode enable, and failed
restore without false success. The full portable suite passes 784 tests with
eight Windows-only skips. These tests establish the adapter's mode handling,
not the native root cause or installed delivery; the unchanged hosted gate must
still pass. Local Parallels startup now reports 1591 MB of missing disk space;
no unrelated user files were removed.

### Native inference comparison and follow-up — 2026-10-09

[SWCLI CI 37884860398](https://github.com/YJBeetle/SWCLI/actions/runs/37884860398)
at `e06313680f5e410b29ea0ffb457b738252f20eb5` still returned x=[-23,23] mm.
The preceding AddToDB-only candidate was therefore insufficient, despite its
portable tests. A correctly installed local Mac/Wine package reproduced exactly
the same failure after shared modeling on the same visible SW 2025 instance.
Do not count the earlier local run importing an older installed package as
candidate verification.

An independent native comparison used fresh parts on front/top/right planes,
the unchanged requested center (3,4) and 40x30 mm size, and AddToDB enabled.
With application `swSketchInference` enabled, all three returned x=[-23,23].
Disabling only that toggle made all three return x=[-17,23], y=[-11,19] mm,
with six native segments and four profile edges. The preference was restored
and the exclusively created instance exited normally. Enum value 249 was read
from the installed SOLIDWORKS 2025 `swconst.tlb`, not guessed from UI labels.

The follow-up adapter scopes this toggle around the single native rectangle
creation, reads it back, and restores it before closing the sketch. It does not
retry creation or adjust final coordinates. Four added portable tests cover
inference remaining active despite AddToDB, original on/off restoration, unknown
or rejected state, native failure, and failed restore without false success.
The suite passes 788 tests with eight Windows-only skips. The complete unchanged
modeling/dimension gate and hosted Windows verification remain required;
this local hardware-rendered Wine comparison does not establish the cause of
MacSW hosted software-renderer stalls.

### CLI presentation metadata in the shared gate — 2026-10-09

With the inference guard installed, local shared modeling passed and the
subsequent front rectangle and center-fix operation both returned the requested
40x30 mm geometry at (3,4). The gate then rejected its CLI assertion view because
the public CLI adds the response `request_id` to the flat business payload.
The operation-result schema correctly excludes response-envelope metadata.

The gate now retains complete CLI JSON in its evidence but removes only the
known presentation keys `request_id` and `replayed` from its business assertion
view. Unknown business keys still reach strict validation. Its fake CLI now
uses the real `_typed_payload` formatter, so portable center tests exercise the
same presentation boundary. This is a gate-format repair, not a change to the
native result schema or geometry tolerances. The full suite passes 789 tests,
eight skipped. The next local run advanced to the origin fixture, where a
separate assumption about automatically inferred origin relations needs review.

### Real origin-bound negative fixture — 2026-10-09

The user chose to retain the origin-rejection gate with an actually constrained
native sample. With inference disabled, a newly created rectangle centered at
(0,0) has no additional origin coincidence and can legitimately be fixed;
the previous fixture inferred a relation from coordinates that are not proof.
No origin-positive replacement or coordinate-based refusal was adopted.

The new [native fixture](../../scripts/ci/fixtures/README.md) was generated with
explicit inference enabled in an exclusively created visible SW 2025 instance.
Native center relations show two point-line coincidences plus an additional
point-point origin coincidence. Geometry and relation arrays remain identical
after saving and reopening read-only, and the existing adapter rejects both
observations as `UnsupportedCenterConstraint`. The shared gate checks a fixed
checksum, copies to its existing shared output directory and opens read-only.
It preserves refusal, unchanged update stamp, closed edit and exact foreground
restoration assertions. No raw COM is sent by the shared gate; regeneration is
a separate maintainer-only Windows tool. The source distribution includes the
asset so all three host projects consume the same fixture.

All 791 portable tests pass (eight Windows-only skips), and the built source
distribution contains the fixture, generator and README. Local native front
center persistence and the real origin refusal pass after shared modeling on
the same visible SW instance. The complete three-plane and hosted gates remain
the delivery requirement, not this partial observation.

The complete local visible sequence subsequently passed: 85 modeling and 361
driving/center events, the same SW PID 504 throughout, all three planes including
native save/reopen persistence, actual origin-relation refusal and zero cleanup
errors. The final document list was empty and the owned daemon stopped normally.
This uses the local hardware renderer, not the hosted software-only environment.

[SWCLI CI 37889825232](https://github.com/YJBeetle/SWCLI/actions/runs/37889825232)
passed both Windows unit jobs but stopped at `Build wheel / Build and inspect
distributions`: its existing no-CAD source policy also rejected this newly
authorized, generated test fixture, so no native job ran. The packaging follow-up
permits only this fixed path, checksum, regular file and <=64 KiB size; duplicates
and every other CAD/media/registry payload still fail. A real built sdist passes
the verifier; 793 portable tests pass (eight skipped). Hosted runtime proof is
still required separately.

### Explicit fresh center topology in hidden mode — 2026-10-09

[SWCLI CI 37890798587](https://github.com/YJBeetle/SWCLI/actions/runs/37890798587)
passed packaging, both portable Windows jobs and the complete visible native
driving gate. Hidden mode failed at the first center fix: native creation had
four corners but no center point. Independent local macOS/Wine observations
reproduced four points in hidden and five points with two center-diagonal
coincidences in visible mode on all three planes in the same SW instance.
This is therefore not a Mac-only failure or an origin-fixture refusal.

Fresh rectangle creation now completes only a verified four-corner/two-diagonal
sketch with an actual native `CreatePoint` and two `AddRelation(COINCIDENT)`
calls. Existing valid five-point topology is observed without mutation. The
native owner, sketch-local IDs, geometry and relation entities must all agree,
including after edit closure; no existing sketch or extra origin relation is
repaired. A NULL empty relation array is accepted only with an independently
observed zero relation count. Failures keep their public error code and restore
the original inference/AddToDB settings, without a second creation attempt.
See the official [point creation](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchManager~CreatePoint.html)
and [relation creation](https://help.solidworks.com/2017/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchRelationManager~AddRelation.html)
contracts; `CreateCenterRectangle` documents returned edges/diagonals, not a
guarantee of the hidden UI center-point side effect.

The corrected local hidden sequence passed 85 modeling and 361 driving events
on the same SW PID 728 / 33.5.0, including the real origin refusal, three-plane
center fixes, repeated no-op fixes and native save/reopen. Both cleanup arrays
were empty and the final document list was empty. Evidence is retained under
`/private/tmp/swcli-nativecheck.V946aT/center-final-hidden-*`. This is a local
hardware-host result, not proof of hosted macOS software-renderer CI. The latter
must run the corrected source pin separately.

The same wheel subsequently passed the full native Windows VM sequence in
both visible (SW PID 6024) and hidden (SW PID 7400) modes: each completed 85
modeling and 361 driving events, kept its original host throughout and cleaned
all owned documents without errors. Three-plane center fixes, no-op repeated
calls and saved/reopened fixes passed; the real origin fixture still returned
`UnsupportedCenterConstraint`, with unchanged stamp 142 and no active edit.
An independent read-only checker confirmed native installed source hashes
matched the candidate. Evidence is retained at
`C:\Workspace\SWCLI-tests\a6-center-repair-installed-20261009\{visible,hidden}`.
The isolated test environment did not upgrade the normal Windows installation;
owned test processes exited and an unrelated SW instance was left untouched.
The portable suite passes 803 tests (eight skipped).

The corrected wheel also passed a second fresh local macOS/Wine visible host
(SW PID 1044 / 33.5.0): 85 modeling and 361 driving events, both cleanup arrays
empty, three-plane center persistence and real origin refusal verified. Its
owned instance stopped normally; the original GUI was restored and the two
installed adapter source hashes still match the tested candidate. Thus both
local Windows and macOS visible/hidden matrices pass. Local evidence remains
distinct from the hosted software-renderer run.

[SWCLI CI 37893909056](https://github.com/YJBeetle/SWCLI/actions/runs/37893909056)
passed at `a857b75`, including packaging, Windows/Python 3.9 and 3.14 tests,
and fresh hosted native Windows installation/runtime. Downloaded artifacts
independently confirm visible SW PID 7124 and hidden SW PID 8608: each mode
completed 97 modeling and 361 driving events on its unchanged host, with empty
cleanup arrays. The 12 additional modeling events are the installed-sample
export case, not a change to the generated-part assertions.

Both modes preserve the actual origin-relation refusal and stamp 142, closed
edit state, three-plane center fixes, repeated no-op calls and saved/reopened
fixed relations. Installed samples remain read-only. Each mode produced nine
native parts, four STEP files and two 800x600 color BMPs; the copied origin
fixture is input, not a generated output. Export/render records succeeded,
STEP signatures and BMP dimensions/color content were checked. These are
hosted Windows results, distinct from the macOS evidence below.

[MacSW CI 37894268328](https://github.com/YJBeetle/MacSW/actions/runs/37894268328)
also passed in full at MacSW `4e9e002` with the exact same SWCLI `a857b75`
source pin. Its fresh installation and hosted Apple Software Renderer completed
both visible (SW PID 504) and hidden (SW PID 464) sequences: each mode has 85
modeling and 361 driving events, an unchanged host across both gates and empty
cleanup arrays. Downloaded terminal artifacts were independently reviewed;
all 22 runtime commands exited zero and the runtime record is complete.

Three-plane center fixes, repeated no-op calls and native save/reopen preserve
the exact point/diagonal identities and geometry. The genuinely origin-bound
fixture still returns `UnsupportedCenterConstraint`, with stamp 142 unchanged,
no active edit and its prior foreground document restored. All eight native
bitmap cases pass with Apple Software Renderer, expected pixel counts and zero
GL errors; arm64 and Rosetta x86_64 CGL software contexts also pass.

This closes the installed public center-fix matrix for the tested candidate,
not the unfinished public linear-dimension/discovery contracts or an a6
release. A completed sequence does not establish the root cause or universal
absence of historical Wine stalls/close exceptions. The later MacSW cache
changes are a separate run and are not covered by this evidence.
