# a13: one simple closed polygon in an origin-plane sketch

Owner-authorized next slice after a12. This is a development design, not a
published capability or native acceptance claim. MacSW is excluded; Windows VM
and subsequent Windows/Wine CI supply the runtime proof.

## Contract

`sketch.polygon` takes an explicit standard `plane` and 3–64 ordered `vertices_mm`
objects `{x, y}` in sketch-local XY millimeters. Closure is implicit from the last
vertex to the first: repeating the first vertex is an error, never silently
normalized. Both clockwise and counterclockwise simple polygons are supported,
including concave L profiles. Coordinates determine placement; this slice creates
no driving dimensions, fixes or fully-defined constraint guarantee. There are no
holes, arcs, disjoint contours, automatic hulls or self-intersection repair.

CLI spelling: `sketch polygon --plane front --vertices-mm '[[0,0],[20,0],[0,15]]'`.
The CLI converts explicit numeric pairs to the same object-array protocol field;
malformed, boolean, nonfinite and ambiguous geometry is refused before mutation.
Document, lease and CAS requirements match existing circle/rectangle creation.

Pure preflight rejects repeated/tolerance-ambiguous vertices, zero/very short
edges, redundant collinear adjacent vertices, self crossings, nonadjacent touching
or edges closer than the observation tolerance, zero/sliver area and coordinates
whose floating-point representation cannot resolve the tolerance. It retains the
user's order and winding, with no guessed profile or name-based feature lookup.

## Native boundary

Use existing worker COM-thread fresh-sketch lifecycle, explicit native plane and
exact feature identity. Create lines with scoped AddToDB and restore its previous
value; leave application inference and DisplayWhenAdded preferences untouched.
After closing/solving, independently read every
native nonconstruction line and endpoint: the exact expected undirected edge
cycle, count, finite XY coordinates and zero Z must agree, without truncated or
extra native segments. Native contour closure and solid geometry must also be
proven in Windows. On partial creation/verification failure retain the exact
created sketch when available, report editing/cleanup evidence, do not roll back,
retry native creation or advertise success after state-restoration failure.

Existing blind extrusion/cut already consume an exact unabsorbed sketch; verify
polygon use through that public route before extending eligibility. Through-all
and blind feature-depth editing currently have circle/rectangle profile guards:
this slice must not silently broaden those guards without separate proof and
contract tests. a13 first covers polygon creation plus blind boss/cut use; no
general polygon constraint or depth-edit authority is implied.

## Proof plan

Independent analytic triangle and concave L fixtures, translated away from the
origin, both winding orders and all three planes. Windows native proof records
exact endpoints / closed contour, volume, surface area and centroid for blind
normal/reverse bosses and cuts; save/read-only reopen, fresh handles, healthy and
clean state, source hashes and cleanup follow. Preserve the existing user's
documents/foreground/preferences and never ExitApp on an attached host.

The opt-in `calibrate_polygon` Windows CI input runs 48 cases before the existing
full CAD gate: triangle/L × clockwise/counterclockwise × blind boss/cut × three
planes × normal/reverse. It reuses the existing owned-host calibration runner,
marks `full_acceptance_eligible=false`, stops on first native failure and does not
claim public a13 polygon acceptance. Product request timeouts remain unchanged.
The local VM was stopped and refused startup due to insufficient disk space;
no VM hardware configuration or user's files were changed to bypass that refusal.

Native API references: [GetSketchContours](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketch~GetSketchContours.html)
and [IsClosed](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchContour~IsClosed.html).
The IsClosed documentation's return-value prose conflicts with its method name;
record the actual boolean and corroborate it with native solid/analytic geometry.

Then exercise installed public CLI, lease/CAS/cross-document refusals and failure
continuation, integrate into full19 without weakening older assertions, run full
Windows and Wine and validate original final-version CI packages. Record runtime,
distribution and publication separately. Release approval remains a final step.

## Implementation status

The internal 48-case proof is complete; see
[the exact Windows artifact and limits](../verification/a13-native-windows-2026-10-30.md).
The development catalog now includes `sketch.polygon`, recursive object/array
parameter validation, pair-array CLI parsing and exact surviving sketch handles
on partial native failure. Successful results require the closed native cycle,
consistent readback geometry, complete metadata and closed edit state.
The existing full native-model set additionally runs `polygon-model` with 48
installed public cases; core11 and full19 group topology are unchanged. This
new public path still requires its own Windows/Wine receipts before acceptance.
