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
