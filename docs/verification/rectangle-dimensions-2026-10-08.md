# Rectangle size / positioning feasibility — 2026-10-08

This is an internal direct-STA probe of installed SWCLI a5 primitives plus
native COM dimension calls. It is not an implemented CLI operation, a release
gate, general constraint support or Wine/macOS proof.

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
